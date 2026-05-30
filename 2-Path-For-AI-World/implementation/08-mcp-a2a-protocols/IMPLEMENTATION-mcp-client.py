"""
MCP Client Implementation
==========================
Full MCP client with:
- Session management (initialize, maintain, shutdown)
- Tool discovery and capability listing
- Tool invocation with error handling and retries
- Resource reading with subscriptions
- Prompt template fetching
- Transport handling (stdio and HTTP+SSE)
- Connection pooling and retry logic
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

import aiohttp  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


# ============================================================================
# Core Types
# ============================================================================


@dataclass
class ServerCapabilities:
    tools: bool = False
    tools_list_changed: bool = False
    resources: bool = False
    resources_subscribe: bool = False
    prompts: bool = False


@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ResourceInfo:
    uri: str
    name: str
    description: str
    mime_type: str


@dataclass
class PromptInfo:
    name: str
    description: str
    arguments: list[dict[str, Any]]


@dataclass
class ToolCallResult:
    content: list[dict[str, Any]]
    is_error: bool = False
    latency_ms: float = 0.0


@dataclass
class ResourceContent:
    uri: str
    mime_type: str
    text: Optional[str] = None
    blob: Optional[bytes] = None


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


# ============================================================================
# Transport Layer
# ============================================================================


class MCPTransport(ABC):
    """Abstract transport for MCP communication."""

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...


class StdioTransport(MCPTransport):
    """
    Transport over stdio — communicates with a subprocess MCP server.
    The host spawns the server process and communicates via stdin/stdout.
    """

    def __init__(self, command: list[str], env: dict[str, str] | None = None):
        self.command = command
        self.env = env
        self._process: Optional[asyncio.subprocess.Process] = None
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    async def connect(self) -> None:
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )
        logger.info(f"Started MCP server process: {self.command[0]} (PID: {self._process.pid})")

    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise ConnectionError("Transport not connected")

        async with self._write_lock:
            payload = json.dumps(message) + "\n"
            self._process.stdin.write(payload.encode())
            await self._process.stdin.drain()

        async with self._read_lock:
            line = await self._process.stdout.readline()
            if not line:
                raise ConnectionError("Server closed connection")
            return json.loads(line.decode())

    async def close(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None


class HTTPSSETransport(MCPTransport):
    """
    Transport over HTTP + Server-Sent Events for remote MCP servers.
    - Client sends requests via HTTP POST
    - Server can stream responses via SSE
    """

    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self.extra_headers = headers or {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def connect(self) -> None:
        self._session = aiohttp.ClientSession(
            headers=self._build_headers(),
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )
        self._connected = True
        logger.info(f"Connected to MCP server at {self.base_url}")

    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        if not self._session:
            raise ConnectionError("Transport not connected")

        url = f"{self.base_url}/mcp"
        async with self._session.post(url, json=message) as resp:
            if resp.status == 401:
                raise PermissionError("Authentication failed")
            if resp.status == 429:
                retry_after = int(resp.headers.get("Retry-After", "60"))
                raise RateLimitError(f"Rate limited. Retry after {retry_after}s", retry_after)
            resp.raise_for_status()
            return await resp.json()

    async def send_streaming(self, message: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Send a request and receive SSE streaming response."""
        if not self._session:
            raise ConnectionError("Transport not connected")

        url = f"{self.base_url}/mcp/stream"
        async with self._session.post(url, json=message) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                decoded = line.decode("utf-8").strip()
                if decoded.startswith("data: "):
                    data = decoded[6:]
                    if data == "[DONE]":
                        break
                    yield json.loads(data)

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._session is not None


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


# ============================================================================
# Retry Logic
# ============================================================================


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_errors: tuple[type, ...] = (ConnectionError, TimeoutError, aiohttp.ClientError)


async def with_retry(
    func: Callable,
    config: RetryConfig,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a function with exponential backoff retry."""
    last_error: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == config.max_retries:
                raise
            await asyncio.sleep(e.retry_after)
            last_error = e
        except config.retryable_errors as e:
            if attempt == config.max_retries:
                raise
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay,
            )
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
            last_error = e

    raise last_error or RuntimeError("Retry exhausted")


# ============================================================================
# Connection Pool
# ============================================================================


class ConnectionPool:
    """
    Pool of MCP client connections for managing multiple servers.
    Supports health checks and automatic reconnection.
    """

    def __init__(self, max_connections_per_server: int = 5):
        self.max_per_server = max_connections_per_server
        self._pools: dict[str, list[MCPClient]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_client(self, server_id: str, factory: Callable[[], MCPClient]) -> MCPClient:
        """Get or create a client connection from the pool."""
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()

        async with self._locks[server_id]:
            pool = self._pools.setdefault(server_id, [])

            # Find an available healthy client
            for client in pool:
                if client.state == ConnectionState.CONNECTED:
                    return client

            # Create new if under limit
            if len(pool) < self.max_per_server:
                client = factory()
                await client.connect()
                pool.append(client)
                return client

            # All connections busy — wait and retry
            raise ConnectionError(f"Connection pool exhausted for {server_id}")

    async def close_all(self) -> None:
        """Close all connections in all pools."""
        for pool in self._pools.values():
            for client in pool:
                await client.disconnect()
        self._pools.clear()

    async def health_check(self) -> dict[str, list[str]]:
        """Check health of all pooled connections."""
        status: dict[str, list[str]] = {}
        for server_id, pool in self._pools.items():
            status[server_id] = [c.state.value for c in pool]
        return status


# ============================================================================
# MCP Client
# ============================================================================


class MCPClient:
    """
    Full MCP client implementation.

    Manages the lifecycle of a connection to a single MCP server:
    - Initialize handshake
    - Discover tools, resources, prompts
    - Invoke tools with error handling
    - Read resources
    - Handle notifications
    """

    def __init__(
        self,
        transport: MCPTransport,
        client_info: dict[str, str] | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self.transport = transport
        self.client_info = client_info or {"name": "mcp-client", "version": "1.0.0"}
        self.retry_config = retry_config or RetryConfig()

        self.state = ConnectionState.DISCONNECTED
        self.server_info: dict[str, Any] = {}
        self.capabilities = ServerCapabilities()

        self._request_id = 0
        self._tools_cache: list[ToolInfo] | None = None
        self._resources_cache: list[ResourceInfo] | None = None
        self._prompts_cache: list[PromptInfo] | None = None
        self._notification_handlers: dict[str, list[Callable]] = {}

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _make_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            msg["params"] = params
        return msg

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and return the result."""
        request = self._make_request(method, params)

        response = await with_retry(
            self.transport.send, self.retry_config, request
        )

        if "error" in response:
            err = response["error"]
            raise MCPServerError(
                code=err.get("code", -32603),
                message=err.get("message", "Unknown error"),
                data=err.get("data"),
            )

        return response.get("result")

    # ---- Lifecycle ----

    async def connect(self) -> None:
        """Connect to the MCP server and perform initialization handshake."""
        self.state = ConnectionState.CONNECTING
        try:
            await self.transport.connect()
            result = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": self.client_info,
            })

            self.server_info = result.get("serverInfo", {})
            caps = result.get("capabilities", {})
            self.capabilities = ServerCapabilities(
                tools="tools" in caps,
                tools_list_changed=caps.get("tools", {}).get("listChanged", False),
                resources="resources" in caps,
                resources_subscribe=caps.get("resources", {}).get("subscribe", False),
                prompts="prompts" in caps,
            )

            # Send initialized notification
            await self.transport.send({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })

            self.state = ConnectionState.CONNECTED
            logger.info(f"Connected to MCP server: {self.server_info.get('name', 'unknown')}")

        except Exception as e:
            self.state = ConnectionState.ERROR
            raise ConnectionError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully disconnect from the server."""
        if self.state == ConnectionState.CONNECTED:
            try:
                await self.transport.send({
                    "jsonrpc": "2.0",
                    "method": "notifications/cancelled",
                    "params": {"reason": "client_shutdown"},
                })
            except Exception:
                pass  # Best effort
        await self.transport.close()
        self.state = ConnectionState.DISCONNECTED
        self._invalidate_caches()

    # ---- Tool Discovery ----

    async def list_tools(self, force_refresh: bool = False) -> list[ToolInfo]:
        """
        List all tools available on the server.
        Results are cached until invalidated by a notification.
        """
        if self._tools_cache is not None and not force_refresh:
            return self._tools_cache

        result = await self._send_request("tools/list")
        tools_data = result.get("tools", [])
        self._tools_cache = [
            ToolInfo(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]
        return self._tools_cache

    async def get_tool(self, name: str) -> Optional[ToolInfo]:
        """Get a specific tool by name."""
        tools = await self.list_tools()
        return next((t for t in tools if t.name == name), None)

    # ---- Tool Invocation ----

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> ToolCallResult:
        """
        Invoke a tool on the MCP server.

        Args:
            name: Tool name
            arguments: Tool input arguments
            timeout: Optional timeout override

        Returns:
            ToolCallResult with content and error status
        """
        self._ensure_connected()

        start = time.time()
        try:
            result = await self._send_request("tools/call", {
                "name": name,
                "arguments": arguments or {},
            })

            latency = (time.time() - start) * 1000
            return ToolCallResult(
                content=result.get("content", []),
                is_error=result.get("isError", False),
                latency_ms=latency,
            )

        except MCPServerError as e:
            latency = (time.time() - start) * 1000
            return ToolCallResult(
                content=[{"type": "text", "text": f"Server error: {e.message}"}],
                is_error=True,
                latency_ms=latency,
            )

    async def call_tool_safe(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> tuple[str, bool]:
        """
        Convenience method: call a tool and return (text_content, is_error).
        Extracts text from the first content block.
        """
        result = await self.call_tool(name, arguments)
        text = ""
        for block in result.content:
            if block.get("type") == "text":
                text += block.get("text", "")
        return text, result.is_error

    # ---- Resources ----

    async def list_resources(self, force_refresh: bool = False) -> list[ResourceInfo]:
        """List all resources available on the server."""
        if self._resources_cache is not None and not force_refresh:
            return self._resources_cache

        result = await self._send_request("resources/list")
        resources_data = result.get("resources", [])
        self._resources_cache = [
            ResourceInfo(
                uri=r["uri"],
                name=r.get("name", ""),
                description=r.get("description", ""),
                mime_type=r.get("mimeType", "text/plain"),
            )
            for r in resources_data
        ]
        return self._resources_cache

    async def read_resource(self, uri: str) -> ResourceContent:
        """Read the content of a specific resource."""
        self._ensure_connected()
        result = await self._send_request("resources/read", {"uri": uri})
        contents = result.get("contents", [])
        if not contents:
            raise ValueError(f"No content returned for resource: {uri}")

        content = contents[0]
        return ResourceContent(
            uri=content.get("uri", uri),
            mime_type=content.get("mimeType", "text/plain"),
            text=content.get("text"),
            blob=content.get("blob"),
        )

    async def subscribe_resource(self, uri: str) -> None:
        """Subscribe to updates for a resource."""
        if not self.capabilities.resources_subscribe:
            raise NotImplementedError("Server does not support resource subscriptions")
        await self._send_request("resources/subscribe", {"uri": uri})

    # ---- Prompts ----

    async def list_prompts(self, force_refresh: bool = False) -> list[PromptInfo]:
        """List all prompt templates available on the server."""
        if self._prompts_cache is not None and not force_refresh:
            return self._prompts_cache

        result = await self._send_request("prompts/list")
        prompts_data = result.get("prompts", [])
        self._prompts_cache = [
            PromptInfo(
                name=p["name"],
                description=p.get("description", ""),
                arguments=p.get("arguments", []),
            )
            for p in prompts_data
        ]
        return self._prompts_cache

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get a rendered prompt template.

        Returns list of messages (role + content).
        """
        self._ensure_connected()
        result = await self._send_request("prompts/get", {
            "name": name,
            "arguments": arguments or {},
        })
        return result.get("messages", [])

    # ---- Notifications ----

    def on_notification(self, method: str, handler: Callable) -> None:
        """Register a handler for server notifications."""
        self._notification_handlers.setdefault(method, []).append(handler)

    def _handle_notification(self, method: str, params: dict[str, Any]) -> None:
        """Process an incoming notification."""
        if method == "notifications/tools/list_changed":
            self._tools_cache = None
        elif method == "notifications/resources/list_changed":
            self._resources_cache = None

        for handler in self._notification_handlers.get(method, []):
            handler(params)

    # ---- Helpers ----

    def _ensure_connected(self) -> None:
        if self.state != ConnectionState.CONNECTED:
            raise ConnectionError(f"Client not connected (state: {self.state.value})")

    def _invalidate_caches(self) -> None:
        self._tools_cache = None
        self._resources_cache = None
        self._prompts_cache = None


class MCPServerError(Exception):
    """Error returned by an MCP server."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data


# ============================================================================
# Multi-Server Client Manager
# ============================================================================


class MCPClientManager:
    """
    Manages connections to multiple MCP servers.
    Provides unified tool discovery across all connected servers.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tool_map: dict[str, str] = {}  # tool_name -> server_id

    async def add_server(
        self,
        server_id: str,
        transport: MCPTransport,
        client_info: dict[str, str] | None = None,
    ) -> None:
        """Add and connect to an MCP server."""
        client = MCPClient(transport, client_info)
        await client.connect()
        self._clients[server_id] = client

        # Index tools
        tools = await client.list_tools()
        for tool in tools:
            if tool.name in self._tool_map:
                logger.warning(
                    f"Tool '{tool.name}' from '{server_id}' shadows "
                    f"existing tool from '{self._tool_map[tool.name]}'"
                )
            self._tool_map[tool.name] = server_id

    async def remove_server(self, server_id: str) -> None:
        """Disconnect and remove a server."""
        if client := self._clients.pop(server_id, None):
            await client.disconnect()
            # Remove tool mappings
            self._tool_map = {k: v for k, v in self._tool_map.items() if v != server_id}

    async def list_all_tools(self) -> list[tuple[str, ToolInfo]]:
        """List all tools across all servers. Returns (server_id, tool_info) pairs."""
        all_tools: list[tuple[str, ToolInfo]] = []
        for server_id, client in self._clients.items():
            tools = await client.list_tools()
            all_tools.extend((server_id, t) for t in tools)
        return all_tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolCallResult:
        """Call a tool, routing to the correct server."""
        server_id = self._tool_map.get(name)
        if not server_id:
            raise ValueError(f"Tool '{name}' not found on any connected server")

        client = self._clients[server_id]
        return await client.call_tool(name, arguments)

    async def close_all(self) -> None:
        """Disconnect from all servers."""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()
        self._tool_map.clear()

    @property
    def connected_servers(self) -> list[str]:
        return [
            sid for sid, c in self._clients.items()
            if c.state == ConnectionState.CONNECTED
        ]


# ============================================================================
# Example Usage
# ============================================================================


async def demo() -> None:
    """Demonstrate MCP client usage."""

    # --- stdio transport example ---
    print("=== MCP Client Demo ===\n")

    # Create client with stdio transport (connects to local server)
    transport = StdioTransport(
        command=["python3", "IMPLEMENTATION-mcp-server.py"],
    )
    client = MCPClient(
        transport=transport,
        client_info={"name": "demo-client", "version": "1.0.0"},
    )

    try:
        # Connect
        await client.connect()
        print(f"Connected to: {client.server_info.get('name')}")
        print(f"Capabilities: tools={client.capabilities.tools}, resources={client.capabilities.resources}")

        # Discover tools
        tools = await client.list_tools()
        print(f"\nAvailable tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:60]}...")

        # Call a tool
        result = await client.call_tool("search_documents", {"query": "rate limiting"})
        print(f"\nTool call result (latency: {result.latency_ms:.0f}ms):")
        print(f"  Error: {result.is_error}")
        print(f"  Content: {result.content[0]['text'][:100]}...")

        # List resources
        resources = await client.list_resources()
        print(f"\nResources ({len(resources)}):")
        for r in resources:
            print(f"  - {r.uri}: {r.name}")

    finally:
        await client.disconnect()

    # --- HTTP+SSE transport example ---
    print("\n=== HTTP+SSE Transport ===\n")
    http_transport = HTTPSSETransport(
        base_url="https://mcp.example.com",
        auth_token="your-oauth-token",
    )
    http_client = MCPClient(transport=http_transport)
    # await http_client.connect()  # Would connect to remote server

    # --- Multi-server manager example ---
    print("\n=== Multi-Server Manager ===\n")
    manager = MCPClientManager()

    # In production, you'd add multiple servers:
    # await manager.add_server("sql", StdioTransport(["python3", "sql_server.py"]))
    # await manager.add_server("kb", StdioTransport(["python3", "kb_server.py"]))
    # await manager.add_server("crm", HTTPSSETransport("https://crm-mcp.internal"))

    # Then call tools without knowing which server hosts them:
    # result = await manager.call_tool("execute_query", {"query": "SELECT 1"})
    # result = await manager.call_tool("search_documents", {"query": "..."})

    print("Multi-server manager ready (no servers connected in demo)")
    await manager.close_all()


if __name__ == "__main__":
    asyncio.run(demo())
