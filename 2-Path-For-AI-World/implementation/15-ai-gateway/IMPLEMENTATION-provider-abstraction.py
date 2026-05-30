"""
Provider Abstraction Layer - Unified interface for all AI model providers.

Implements the Adapter pattern to normalize different provider APIs into
a common interface, handling format translation, streaming protocols,
error mapping, health monitoring, and automatic failover.
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)


# ============================================================================
# Unified Schema
# ============================================================================

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(str, Enum):
    STOP = "stop"
    MAX_TOKENS = "max_tokens"
    TOOL_CALL = "tool_call"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


@dataclass
class UnifiedMessage:
    role: Role
    content: str = ""
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    images: Optional[List[Dict[str, str]]] = None  # For vision: [{"url": "...", "detail": "high"}]


@dataclass
class UnifiedTool:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


@dataclass
class UnifiedRequest:
    """Provider-agnostic request format."""
    messages: List[UnifiedMessage]
    model: str
    max_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 1.0
    stop: Optional[List[str]] = None
    tools: Optional[List[UnifiedTool]] = None
    tool_choice: Optional[str] = None  # "auto", "none", or specific tool name
    stream: bool = False
    response_format: Optional[Dict[str, str]] = None  # {"type": "json_object"}
    seed: Optional[int] = None
    # Metadata (not sent to provider)
    request_id: str = ""
    timeout_ms: int = 30000


@dataclass
class UnifiedUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class UnifiedToolCall:
    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class UnifiedResponse:
    """Provider-agnostic response format."""
    content: str = ""
    model: str = ""
    finish_reason: FinishReason = FinishReason.STOP
    usage: UnifiedUsage = field(default_factory=UnifiedUsage)
    tool_calls: Optional[List[UnifiedToolCall]] = None
    # Metadata
    provider: str = ""
    provider_model: str = ""  # The actual model ID used by the provider
    latency_ms: float = 0.0
    request_id: str = ""


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    content: str = ""
    tool_call_delta: Optional[Dict[str, str]] = None
    finish_reason: Optional[FinishReason] = None
    usage: Optional[UnifiedUsage] = None  # Some providers include usage in final chunk


# ============================================================================
# Provider Errors
# ============================================================================

class ProviderErrorType(str, Enum):
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    INVALID_REQUEST = "invalid_request"
    AUTH_ERROR = "auth_error"
    CONTEXT_LENGTH_EXCEEDED = "context_length_exceeded"
    CONTENT_FILTERED = "content_filtered"
    MODEL_NOT_FOUND = "model_not_found"
    QUOTA_EXCEEDED = "quota_exceeded"
    UNKNOWN = "unknown"


@dataclass
class ProviderError(Exception):
    error_type: ProviderErrorType
    message: str
    provider: str
    status_code: Optional[int] = None
    retry_after_ms: Optional[int] = None
    raw_error: Optional[Dict] = None

    def __str__(self):
        return f"[{self.provider}] {self.error_type.value}: {self.message}"

    @property
    def is_retryable(self) -> bool:
        return self.error_type in [
            ProviderErrorType.RATE_LIMITED,
            ProviderErrorType.TIMEOUT,
            ProviderErrorType.SERVER_ERROR,
        ]


# ============================================================================
# Base Provider Adapter
# ============================================================================

class ProviderAdapter(ABC):
    """Base class for all provider adapters."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self._session: Optional[aiohttp.ClientSession] = None
        self._healthy = True
        self._last_error: Optional[ProviderError] = None
        self._request_count = 0
        self._error_count = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @abstractmethod
    async def complete(self, request: UnifiedRequest) -> UnifiedResponse:
        """Send a completion request and return unified response."""
        pass

    @abstractmethod
    async def stream(self, request: UnifiedRequest) -> AsyncGenerator[StreamChunk, None]:
        """Stream a completion request, yielding chunks."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable and healthy."""
        pass

    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """Return list of supported model IDs."""
        pass

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def error_rate(self) -> float:
        if self._request_count == 0:
            return 0.0
        return self._error_count / self._request_count


# ============================================================================
# OpenAI Adapter
# ============================================================================

class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI's Chat Completions API."""

    def __init__(self, api_key: str, org_id: Optional[str] = None,
                 base_url: str = "https://api.openai.com/v1"):
        super().__init__("openai")
        self._api_key = api_key
        self._org_id = org_id
        self._base_url = base_url

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._org_id:
            headers["OpenAI-Organization"] = self._org_id
        return headers

    def _transform_request(self, request: UnifiedRequest) -> Dict[str, Any]:
        """Transform unified request to OpenAI format."""
        messages = []
        for msg in request.messages:
            m: Dict[str, Any] = {"role": msg.role.value, "content": msg.content}
            if msg.name:
                m["name"] = msg.name
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            # Vision support
            if msg.images:
                content_parts = [{"type": "text", "text": msg.content}]
                for img in msg.images:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": img["url"], "detail": img.get("detail", "auto")}
                    })
                m["content"] = content_parts
            messages.append(m)

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in request.tools
            ]
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        if request.response_format:
            payload["response_format"] = request.response_format
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.stream:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}

        return payload

    def _transform_response(self, data: Dict, latency_ms: float, request_id: str) -> UnifiedResponse:
        """Transform OpenAI response to unified format."""
        choice = data["choices"][0]
        message = choice["message"]
        usage = data.get("usage", {})

        # Map finish reason
        finish_reason_map = {
            "stop": FinishReason.STOP,
            "length": FinishReason.MAX_TOKENS,
            "tool_calls": FinishReason.TOOL_CALL,
            "content_filter": FinishReason.CONTENT_FILTER,
        }

        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                UnifiedToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
                for tc in message["tool_calls"]
            ]

        return UnifiedResponse(
            content=message.get("content") or "",
            model=request_id,
            finish_reason=finish_reason_map.get(choice.get("finish_reason", "stop"), FinishReason.STOP),
            usage=UnifiedUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cached_tokens=usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
            ),
            tool_calls=tool_calls,
            provider=self.provider_name,
            provider_model=data.get("model", ""),
            latency_ms=latency_ms,
            request_id=request_id,
        )

    def _map_error(self, status_code: int, error_body: Dict) -> ProviderError:
        """Map OpenAI error to unified error type."""
        error_msg = error_body.get("error", {}).get("message", "Unknown error")
        error_type_map = {
            400: ProviderErrorType.INVALID_REQUEST,
            401: ProviderErrorType.AUTH_ERROR,
            403: ProviderErrorType.AUTH_ERROR,
            404: ProviderErrorType.MODEL_NOT_FOUND,
            429: ProviderErrorType.RATE_LIMITED,
            500: ProviderErrorType.SERVER_ERROR,
            502: ProviderErrorType.SERVER_ERROR,
            503: ProviderErrorType.SERVER_ERROR,
        }
        if "context_length" in error_msg.lower() or "maximum context" in error_msg.lower():
            error_type = ProviderErrorType.CONTEXT_LENGTH_EXCEEDED
        else:
            error_type = error_type_map.get(status_code, ProviderErrorType.UNKNOWN)

        retry_after = None
        if status_code == 429:
            retry_after = 60000  # Default 60s for rate limits

        return ProviderError(
            error_type=error_type,
            message=error_msg,
            provider=self.provider_name,
            status_code=status_code,
            retry_after_ms=retry_after,
            raw_error=error_body,
        )

    async def complete(self, request: UnifiedRequest) -> UnifiedResponse:
        self._request_count += 1
        start = time.time()
        session = await self._get_session()
        payload = self._transform_request(request)

        try:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    self._error_count += 1
                    raise self._map_error(resp.status, body)
                latency_ms = (time.time() - start) * 1000
                self._healthy = True
                return self._transform_response(body, latency_ms, request.request_id)
        except aiohttp.ClientError as e:
            self._error_count += 1
            self._healthy = False
            raise ProviderError(
                error_type=ProviderErrorType.TIMEOUT,
                message=str(e),
                provider=self.provider_name,
            )

    async def stream(self, request: UnifiedRequest) -> AsyncGenerator[StreamChunk, None]:
        self._request_count += 1
        request.stream = True
        session = await self._get_session()
        payload = self._transform_request(request)

        try:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
            ) as resp:
                if resp.status != 200:
                    body = await resp.json()
                    self._error_count += 1
                    raise self._map_error(resp.status, body)

                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str or not line_str.startswith("data: "):
                        continue
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        delta = chunk_data["choices"][0].get("delta", {})
                        finish = chunk_data["choices"][0].get("finish_reason")

                        chunk = StreamChunk(
                            content=delta.get("content", ""),
                            finish_reason=FinishReason.STOP if finish == "stop" else None,
                        )
                        # Check for usage in final chunk
                        if "usage" in chunk_data:
                            u = chunk_data["usage"]
                            chunk.usage = UnifiedUsage(
                                input_tokens=u.get("prompt_tokens", 0),
                                output_tokens=u.get("completion_tokens", 0),
                                total_tokens=u.get("total_tokens", 0),
                            )
                        yield chunk
                    except json.JSONDecodeError:
                        continue
        except aiohttp.ClientError as e:
            self._error_count += 1
            raise ProviderError(
                error_type=ProviderErrorType.TIMEOUT,
                message=str(e),
                provider=self.provider_name,
            )

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/models",
                headers=self._build_headers(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                self._healthy = resp.status == 200
                return self._healthy
        except Exception:
            self._healthy = False
            return False

    def get_supported_models(self) -> List[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini"]


# ============================================================================
# Anthropic Adapter
# ============================================================================

class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic's Messages API."""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1"):
        super().__init__("anthropic")
        self._api_key = api_key
        self._base_url = base_url
        self._api_version = "2023-06-01"

    def _build_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "anthropic-version": self._api_version,
        }

    def _transform_request(self, request: UnifiedRequest) -> Dict[str, Any]:
        """Transform unified request to Anthropic format."""
        system_content = ""
        messages = []

        for msg in request.messages:
            if msg.role == Role.SYSTEM:
                system_content += msg.content + "\n"
            elif msg.role == Role.TOOL:
                messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.content}]
                })
            else:
                content: Any = msg.content
                # Vision support
                if msg.images:
                    content = [{"type": "text", "text": msg.content}]
                    for img in msg.images:
                        if img["url"].startswith("data:"):
                            # Base64 image
                            media_type = img["url"].split(";")[0].split(":")[1]
                            data = img["url"].split(",")[1]
                            content.append({
                                "type": "image",
                                "source": {"type": "base64", "media_type": media_type, "data": data}
                            })
                        else:
                            content.append({
                                "type": "image",
                                "source": {"type": "url", "url": img["url"]}
                            })
                messages.append({"role": msg.role.value, "content": content})

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if system_content.strip():
            payload["system"] = system_content.strip()
        if request.stop:
            payload["stop_sequences"] = request.stop
        if request.tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in request.tools
            ]
        if request.stream:
            payload["stream"] = True

        return payload

    def _transform_response(self, data: Dict, latency_ms: float, request_id: str) -> UnifiedResponse:
        """Transform Anthropic response to unified format."""
        # Extract text content
        content = ""
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(UnifiedToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=json.dumps(block["input"]),
                ))

        # Map stop reason
        stop_reason_map = {
            "end_turn": FinishReason.STOP,
            "stop_sequence": FinishReason.STOP,
            "max_tokens": FinishReason.MAX_TOKENS,
            "tool_use": FinishReason.TOOL_CALL,
        }

        usage = data.get("usage", {})

        return UnifiedResponse(
            content=content,
            model=request_id,
            finish_reason=stop_reason_map.get(data.get("stop_reason", "end_turn"), FinishReason.STOP),
            usage=UnifiedUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                cached_tokens=usage.get("cache_read_input_tokens", 0),
            ),
            tool_calls=tool_calls if tool_calls else None,
            provider=self.provider_name,
            provider_model=data.get("model", ""),
            latency_ms=latency_ms,
            request_id=request_id,
        )

    def _map_error(self, status_code: int, error_body: Dict) -> ProviderError:
        error_msg = error_body.get("error", {}).get("message", "Unknown error")
        error_type_map = {
            400: ProviderErrorType.INVALID_REQUEST,
            401: ProviderErrorType.AUTH_ERROR,
            403: ProviderErrorType.AUTH_ERROR,
            404: ProviderErrorType.MODEL_NOT_FOUND,
            429: ProviderErrorType.RATE_LIMITED,
            500: ProviderErrorType.SERVER_ERROR,
            529: ProviderErrorType.SERVER_ERROR,  # Anthropic overloaded
        }
        return ProviderError(
            error_type=error_type_map.get(status_code, ProviderErrorType.UNKNOWN),
            message=error_msg,
            provider=self.provider_name,
            status_code=status_code,
            retry_after_ms=60000 if status_code == 429 else None,
            raw_error=error_body,
        )

    async def complete(self, request: UnifiedRequest) -> UnifiedResponse:
        self._request_count += 1
        start = time.time()
        session = await self._get_session()
        payload = self._transform_request(request)

        try:
            async with session.post(
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    self._error_count += 1
                    raise self._map_error(resp.status, body)
                latency_ms = (time.time() - start) * 1000
                self._healthy = True
                return self._transform_response(body, latency_ms, request.request_id)
        except aiohttp.ClientError as e:
            self._error_count += 1
            self._healthy = False
            raise ProviderError(
                error_type=ProviderErrorType.TIMEOUT,
                message=str(e),
                provider=self.provider_name,
            )

    async def stream(self, request: UnifiedRequest) -> AsyncGenerator[StreamChunk, None]:
        self._request_count += 1
        request.stream = True
        session = await self._get_session()
        payload = self._transform_request(request)

        try:
            async with session.post(
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
            ) as resp:
                if resp.status != 200:
                    body = await resp.json()
                    self._error_count += 1
                    raise self._map_error(resp.status, body)

                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str.startswith("data: "):
                        continue
                    try:
                        event_data = json.loads(line_str[6:])
                        event_type = event_data.get("type", "")

                        if event_type == "content_block_delta":
                            delta = event_data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield StreamChunk(content=delta.get("text", ""))
                        elif event_type == "message_delta":
                            stop = event_data.get("delta", {}).get("stop_reason")
                            if stop:
                                usage = event_data.get("usage", {})
                                yield StreamChunk(
                                    finish_reason=FinishReason.STOP,
                                    usage=UnifiedUsage(output_tokens=usage.get("output_tokens", 0))
                                )
                    except json.JSONDecodeError:
                        continue
        except aiohttp.ClientError as e:
            self._error_count += 1
            raise ProviderError(
                error_type=ProviderErrorType.TIMEOUT,
                message=str(e),
                provider=self.provider_name,
            )

    async def health_check(self) -> bool:
        # Anthropic doesn't have a dedicated health endpoint
        # Use a minimal request or just check connectivity
        try:
            session = await self._get_session()
            async with session.post(
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json={"model": "claude-3-5-haiku-latest", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                self._healthy = resp.status == 200
                return self._healthy
        except Exception:
            self._healthy = False
            return False

    def get_supported_models(self) -> List[str]:
        return ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"]


# ============================================================================
# Azure OpenAI Adapter
# ============================================================================

class AzureOpenAIAdapter(ProviderAdapter):
    """Adapter for Azure OpenAI Service."""

    def __init__(self, api_key: str, endpoint: str, api_version: str = "2024-08-01-preview",
                 deployment_map: Optional[Dict[str, str]] = None):
        super().__init__("azure_openai")
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version
        # Map model names to Azure deployment names
        self._deployment_map = deployment_map or {
            "gpt-4o": "gpt-4o",
            "gpt-4o-mini": "gpt-4o-mini",
        }

    def _get_deployment_url(self, model: str) -> str:
        deployment = self._deployment_map.get(model, model)
        return f"{self._endpoint}/openai/deployments/{deployment}/chat/completions?api-version={self._api_version}"

    def _build_headers(self) -> Dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _transform_request(self, request: UnifiedRequest) -> Dict[str, Any]:
        """Azure OpenAI uses same format as OpenAI."""
        messages = []
        for msg in request.messages:
            m: Dict[str, Any] = {"role": msg.role.value, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            messages.append(m)

        payload: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in request.tools
            ]
        if request.stream:
            payload["stream"] = True
        return payload

    async def complete(self, request: UnifiedRequest) -> UnifiedResponse:
        self._request_count += 1
        start = time.time()
        session = await self._get_session()
        payload = self._transform_request(request)
        url = self._get_deployment_url(request.model)

        try:
            async with session.post(
                url,
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    self._error_count += 1
                    raise ProviderError(
                        error_type=ProviderErrorType.SERVER_ERROR,
                        message=body.get("error", {}).get("message", "Unknown error"),
                        provider=self.provider_name,
                        status_code=resp.status,
                    )

                latency_ms = (time.time() - start) * 1000
                choice = body["choices"][0]
                usage = body.get("usage", {})
                self._healthy = True

                tool_calls = None
                if choice["message"].get("tool_calls"):
                    tool_calls = [
                        UnifiedToolCall(id=tc["id"], name=tc["function"]["name"], arguments=tc["function"]["arguments"])
                        for tc in choice["message"]["tool_calls"]
                    ]

                return UnifiedResponse(
                    content=choice["message"].get("content") or "",
                    model=request.request_id,
                    finish_reason=FinishReason.STOP,
                    usage=UnifiedUsage(
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                    ),
                    tool_calls=tool_calls,
                    provider=self.provider_name,
                    provider_model=body.get("model", ""),
                    latency_ms=latency_ms,
                    request_id=request.request_id,
                )
        except aiohttp.ClientError as e:
            self._error_count += 1
            self._healthy = False
            raise ProviderError(error_type=ProviderErrorType.TIMEOUT, message=str(e), provider=self.provider_name)

    async def stream(self, request: UnifiedRequest) -> AsyncGenerator[StreamChunk, None]:
        self._request_count += 1
        request.stream = True
        session = await self._get_session()
        payload = self._transform_request(request)
        url = self._get_deployment_url(request.model)

        async with session.post(url, headers=self._build_headers(), json=payload,
                                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000)) as resp:
            if resp.status != 200:
                body = await resp.json()
                raise ProviderError(error_type=ProviderErrorType.SERVER_ERROR,
                                    message=str(body), provider=self.provider_name, status_code=resp.status)
            async for line in resp.content:
                line_str = line.decode("utf-8").strip()
                if not line_str.startswith("data: ") or line_str == "data: [DONE]":
                    continue
                try:
                    chunk = json.loads(line_str[6:])
                    delta = chunk["choices"][0].get("delta", {})
                    yield StreamChunk(content=delta.get("content", ""))
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            # Use a simple models list endpoint
            url = f"{self._endpoint}/openai/models?api-version={self._api_version}"
            async with session.get(url, headers=self._build_headers(), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                self._healthy = resp.status == 200
                return self._healthy
        except Exception:
            self._healthy = False
            return False

    def get_supported_models(self) -> List[str]:
        return list(self._deployment_map.keys())


# ============================================================================
# Self-Hosted Adapter (vLLM / Ollama / TGI)
# ============================================================================

class SelfHostedAdapter(ProviderAdapter):
    """Adapter for self-hosted models via OpenAI-compatible API (vLLM, Ollama, TGI)."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, models: Optional[List[str]] = None):
        super().__init__("self_hosted")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._models = models or []

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def complete(self, request: UnifiedRequest) -> UnifiedResponse:
        self._request_count += 1
        start = time.time()
        session = await self._get_session()

        # Most self-hosted solutions support OpenAI-compatible format
        payload = {
            "model": request.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        try:
            async with session.post(
                f"{self._base_url}/v1/chat/completions",
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    self._error_count += 1
                    raise ProviderError(
                        error_type=ProviderErrorType.SERVER_ERROR,
                        message=str(body),
                        provider=self.provider_name,
                        status_code=resp.status,
                    )

                latency_ms = (time.time() - start) * 1000
                choice = body["choices"][0]
                usage = body.get("usage", {})
                self._healthy = True

                return UnifiedResponse(
                    content=choice["message"].get("content", ""),
                    model=request.request_id,
                    finish_reason=FinishReason.STOP,
                    usage=UnifiedUsage(
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                    ),
                    provider=self.provider_name,
                    provider_model=body.get("model", request.model),
                    latency_ms=latency_ms,
                    request_id=request.request_id,
                )
        except aiohttp.ClientError as e:
            self._error_count += 1
            self._healthy = False
            raise ProviderError(error_type=ProviderErrorType.TIMEOUT, message=str(e), provider=self.provider_name)

    async def stream(self, request: UnifiedRequest) -> AsyncGenerator[StreamChunk, None]:
        self._request_count += 1
        session = await self._get_session()
        payload = {
            "model": request.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }

        async with session.post(
            f"{self._base_url}/v1/chat/completions",
            headers=self._build_headers(),
            json=payload,
            timeout=aiohttp.ClientTimeout(total=request.timeout_ms / 1000),
        ) as resp:
            async for line in resp.content:
                line_str = line.decode("utf-8").strip()
                if not line_str.startswith("data: ") or line_str == "data: [DONE]":
                    continue
                try:
                    chunk = json.loads(line_str[6:])
                    delta = chunk["choices"][0].get("delta", {})
                    yield StreamChunk(content=delta.get("content", ""))
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/health",
                headers=self._build_headers(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                self._healthy = resp.status == 200
                return self._healthy
        except Exception:
            # Try /v1/models as fallback
            try:
                session = await self._get_session()
                async with session.get(
                    f"{self._base_url}/v1/models",
                    headers=self._build_headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    self._healthy = resp.status == 200
                    return self._healthy
            except Exception:
                self._healthy = False
                return False

    def get_supported_models(self) -> List[str]:
        return self._models


# ============================================================================
# Provider Manager - Orchestrates all adapters with failover
# ============================================================================

class ProviderManager:
    """
    Manages all provider adapters with health monitoring and automatic failover.
    """

    def __init__(self, health_check_interval: int = 30):
        self._adapters: Dict[str, ProviderAdapter] = {}
        self._health_check_interval = health_check_interval
        self._health_check_task: Optional[asyncio.Task] = None

    def register(self, name: str, adapter: ProviderAdapter):
        self._adapters[name] = adapter

    def get_adapter(self, name: str) -> Optional[ProviderAdapter]:
        return self._adapters.get(name)

    def get_healthy_adapters(self) -> List[Tuple[str, ProviderAdapter]]:
        return [(name, adapter) for name, adapter in self._adapters.items() if adapter.is_healthy]

    async def complete_with_failover(
        self,
        request: UnifiedRequest,
        preferred_provider: str,
        fallback_providers: List[str]
    ) -> UnifiedResponse:
        """Try preferred provider, then fallbacks in order."""
        providers_to_try = [preferred_provider] + fallback_providers

        last_error = None
        for provider_name in providers_to_try:
            adapter = self._adapters.get(provider_name)
            if not adapter or not adapter.is_healthy:
                continue
            try:
                return await adapter.complete(request)
            except ProviderError as e:
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {e}")
                if not e.is_retryable:
                    raise  # Don't try fallbacks for non-retryable errors
                continue

        raise last_error or ProviderError(
            error_type=ProviderErrorType.SERVER_ERROR,
            message="All providers failed",
            provider="none",
        )

    async def start_health_checks(self):
        """Start periodic health checking for all providers."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self):
        while True:
            await asyncio.sleep(self._health_check_interval)
            for name, adapter in self._adapters.items():
                try:
                    healthy = await adapter.health_check()
                    if not healthy:
                        logger.warning(f"Provider {name} health check failed")
                except Exception as e:
                    logger.error(f"Health check error for {name}: {e}")

    async def close_all(self):
        if self._health_check_task:
            self._health_check_task.cancel()
        for adapter in self._adapters.values():
            await adapter.close()


# ============================================================================
# Usage Example
# ============================================================================

async def main():
    # Initialize providers
    manager = ProviderManager()

    # Register adapters (use env vars for keys in production)
    manager.register("openai", OpenAIAdapter(api_key="sk-..."))
    manager.register("anthropic", AnthropicAdapter(api_key="sk-ant-..."))
    manager.register("azure", AzureOpenAIAdapter(
        api_key="...",
        endpoint="https://my-resource.openai.azure.com",
    ))
    manager.register("self_hosted", SelfHostedAdapter(
        base_url="http://localhost:8080",
        models=["llama-3-70b"]
    ))

    # Start health checks
    await manager.start_health_checks()

    # Make a request with failover
    request = UnifiedRequest(
        messages=[
            UnifiedMessage(role=Role.SYSTEM, content="You are a helpful assistant."),
            UnifiedMessage(role=Role.USER, content="What is the capital of France?"),
        ],
        model="gpt-4o",
        max_tokens=100,
        temperature=0.7,
        request_id="req-123",
    )

    try:
        response = await manager.complete_with_failover(
            request,
            preferred_provider="openai",
            fallback_providers=["azure", "anthropic", "self_hosted"]
        )
        print(f"Response: {response.content}")
        print(f"Provider: {response.provider}")
        print(f"Tokens: {response.usage.total_tokens}")
        print(f"Latency: {response.latency_ms:.0f}ms")
    except ProviderError as e:
        print(f"All providers failed: {e}")
    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(main())
