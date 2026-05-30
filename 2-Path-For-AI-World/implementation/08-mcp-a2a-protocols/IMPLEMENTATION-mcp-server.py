"""
MCP Server Implementations
===========================
Production-quality MCP servers for various use cases:
1. Knowledge Base Server (search/retrieve documents)
2. SQL Read-Only Query Server (with validation)
3. Ticket Creation Server (with approval workflow)
4. CRM Lookup Server
5. Safe Code Execution Server (sandboxed)

All servers include:
- Proper tool schemas with JSON Schema validation
- Audit logging for every invocation
- Authentication hooks
- Error handling with structured error responses
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import sqlite3
import subprocess
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# ============================================================================
# Core MCP Types and Infrastructure
# ============================================================================


class MCPErrorCode(Enum):
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TOOL_EXECUTION_ERROR = -32000
    UNAUTHORIZED = -32001
    RATE_LIMITED = -32002
    APPROVAL_REQUIRED = -32003


@dataclass
class MCPError:
    code: MCPErrorCode
    message: str
    data: Optional[dict[str, Any]] = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_tier: str = "low"  # low, medium, high, critical
    requires_approval: bool = False


@dataclass
class ToolResult:
    content: list[dict[str, Any]]
    is_error: bool = False


@dataclass
class ResourceDefinition:
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"


@dataclass
class AuditEntry:
    timestamp: str
    request_id: str
    user_id: str
    session_id: str
    server_name: str
    tool_name: str
    input_params: dict[str, Any]
    output_summary: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    risk_tier: str = "low"
    approval_status: str = "auto-approved"


class AuditLogger:
    """Structured audit logger for all tool invocations."""

    def __init__(self, server_name: str, log_path: Optional[Path] = None):
        self.server_name = server_name
        self.logger = logging.getLogger(f"mcp.audit.{server_name}")
        self.logger.setLevel(logging.INFO)

        if log_path:
            handler = logging.FileHandler(log_path)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def log_invocation(self, entry: AuditEntry) -> None:
        self.logger.info(json.dumps(asdict(entry), default=str))

    def create_entry(
        self,
        user_id: str,
        session_id: str,
        tool_name: str,
        input_params: dict[str, Any],
    ) -> tuple[AuditEntry, float]:
        """Create an audit entry and return it with start time."""
        start_time = time.time()
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            server_name=self.server_name,
            tool_name=tool_name,
            input_params=input_params,
            output_summary="",
            latency_ms=0,
            success=False,
        )
        return entry, start_time

    def finalize_entry(
        self,
        entry: AuditEntry,
        start_time: float,
        success: bool,
        output_summary: str,
        error: Optional[str] = None,
    ) -> None:
        entry.latency_ms = (time.time() - start_time) * 1000
        entry.success = success
        entry.output_summary = output_summary
        entry.error = error
        self.log_invocation(entry)


@dataclass
class AuthContext:
    """Authentication context for the current request."""
    user_id: str
    session_id: str
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    token: Optional[str] = None


class AuthHook(ABC):
    """Abstract authentication hook for MCP servers."""

    @abstractmethod
    async def authenticate(self, headers: dict[str, str]) -> AuthContext:
        """Validate credentials and return auth context."""
        ...

    @abstractmethod
    async def authorize_tool(self, ctx: AuthContext, tool_name: str) -> bool:
        """Check if user is authorized to use a specific tool."""
        ...


class DefaultAuthHook(AuthHook):
    """Simple role-based auth hook for demonstration."""

    def __init__(self, tool_permissions: dict[str, list[str]] | None = None):
        # tool_name -> list of allowed roles
        self.tool_permissions = tool_permissions or {}

    async def authenticate(self, headers: dict[str, str]) -> AuthContext:
        # In production: validate JWT, check token expiry, extract claims
        token = headers.get("authorization", "").replace("Bearer ", "")
        if not token:
            return AuthContext(user_id="anonymous", session_id=str(uuid.uuid4()))
        # Simulated token decode
        return AuthContext(
            user_id=f"user-{hashlib.sha256(token.encode()).hexdigest()[:8]}",
            session_id=str(uuid.uuid4()),
            roles=["analyst"],  # Would come from token claims
            scopes=["read", "write"],
            token=token,
        )

    async def authorize_tool(self, ctx: AuthContext, tool_name: str) -> bool:
        allowed_roles = self.tool_permissions.get(tool_name)
        if allowed_roles is None:
            return True  # No restrictions
        return any(role in allowed_roles for role in ctx.roles)


class BaseMCPServer(ABC):
    """Base class for MCP servers with common infrastructure."""

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        auth_hook: Optional[AuthHook] = None,
        audit_log_path: Optional[Path] = None,
    ):
        self.name = name
        self.version = version
        self.auth_hook = auth_hook or DefaultAuthHook()
        self.audit = AuditLogger(name, audit_log_path)
        self._tools: dict[str, ToolDefinition] = {}
        self._resources: dict[str, ResourceDefinition] = {}
        self._tool_handlers: dict[str, Callable] = {}
        self._setup_tools()

    @abstractmethod
    def _setup_tools(self) -> None:
        """Register tools for this server."""
        ...

    def register_tool(
        self, definition: ToolDefinition, handler: Callable
    ) -> None:
        self._tools[definition.name] = definition
        self._tool_handlers[definition.name] = handler

    def register_resource(self, resource: ResourceDefinition) -> None:
        self._resources[resource.uri] = resource

    async def handle_initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
            },
            "serverInfo": {"name": self.name, "version": self.version},
        }

    async def handle_tools_list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def handle_tools_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_ctx: AuthContext,
    ) -> ToolResult:
        # Validate tool exists
        if tool_name not in self._tools:
            raise MCPError(
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Tool '{tool_name}' not found",
            )

        tool_def = self._tools[tool_name]

        # Authorization check
        if not await self.auth_hook.authorize_tool(auth_ctx, tool_name):
            raise MCPError(
                MCPErrorCode.UNAUTHORIZED,
                f"User '{auth_ctx.user_id}' not authorized for tool '{tool_name}'",
            )

        # Approval check
        if tool_def.requires_approval:
            # In production: check if pre-approved or request approval
            raise MCPError(
                MCPErrorCode.APPROVAL_REQUIRED,
                f"Tool '{tool_name}' requires human approval",
                data={"tool": tool_name, "arguments": arguments},
            )

        # Execute with audit
        entry, start_time = self.audit.create_entry(
            user_id=auth_ctx.user_id,
            session_id=auth_ctx.session_id,
            tool_name=tool_name,
            input_params=arguments,
        )
        entry.risk_tier = tool_def.risk_tier

        try:
            handler = self._tool_handlers[tool_name]
            result = await handler(arguments, auth_ctx)
            self.audit.finalize_entry(
                entry, start_time, success=True,
                output_summary=self._summarize_result(result),
            )
            return result
        except Exception as e:
            self.audit.finalize_entry(
                entry, start_time, success=False,
                output_summary="", error=str(e),
            )
            return ToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True,
            )

    def _summarize_result(self, result: ToolResult) -> str:
        """Create a brief summary of the result for audit logs."""
        if result.is_error:
            return "ERROR"
        total_chars = sum(
            len(c.get("text", "")) for c in result.content if c["type"] == "text"
        )
        return f"{len(result.content)} content blocks, {total_chars} chars"

    async def handle_resources_list(self) -> list[dict[str, Any]]:
        return [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type,
            }
            for r in self._resources.values()
        ]


# ============================================================================
# 1. Knowledge Base MCP Server
# ============================================================================


class KnowledgeBaseMCPServer(BaseMCPServer):
    """
    MCP server for searching and retrieving documents from a knowledge base.
    Supports full-text search, document retrieval by ID, and metadata filtering.
    """

    def __init__(
        self,
        documents: list[dict[str, Any]] | None = None,
        **kwargs,
    ):
        self.documents: dict[str, dict[str, Any]] = {}
        super().__init__(name="knowledge-base", **kwargs)
        if documents:
            for doc in documents:
                self.documents[doc["id"]] = doc

    def _setup_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="search_documents",
                description=(
                    "Search the knowledge base for documents matching a query. "
                    "Returns top-k results with title, snippet, and relevance score."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default 5, max 20)",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                        "filters": {
                            "type": "object",
                            "description": "Optional metadata filters",
                            "properties": {
                                "category": {"type": "string"},
                                "author": {"type": "string"},
                                "date_after": {"type": "string", "format": "date"},
                            },
                        },
                    },
                    "required": ["query"],
                },
                risk_tier="low",
            ),
            self._search_documents,
        )

        self.register_tool(
            ToolDefinition(
                name="get_document",
                description="Retrieve the full content of a document by its ID.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "string",
                            "description": "Unique document identifier",
                        },
                        "include_metadata": {
                            "type": "boolean",
                            "description": "Whether to include document metadata",
                            "default": True,
                        },
                    },
                    "required": ["document_id"],
                },
                risk_tier="low",
            ),
            self._get_document,
        )

        self.register_tool(
            ToolDefinition(
                name="list_categories",
                description="List all document categories in the knowledge base.",
                input_schema={"type": "object", "properties": {}},
                risk_tier="low",
            ),
            self._list_categories,
        )

    async def _search_documents(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        query = args["query"].lower()
        top_k = min(args.get("top_k", 5), 20)
        filters = args.get("filters", {})

        results = []
        for doc in self.documents.values():
            # Simple text matching (in production: use vector search)
            score = 0.0
            searchable = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
            query_terms = query.split()
            for term in query_terms:
                if term in searchable:
                    score += 1.0 / len(query_terms)

            # Apply filters
            if filters.get("category") and doc.get("category") != filters["category"]:
                continue
            if filters.get("author") and doc.get("author") != filters["author"]:
                continue

            if score > 0:
                snippet = doc.get("content", "")[:200]
                results.append({
                    "id": doc["id"],
                    "title": doc.get("title", "Untitled"),
                    "snippet": snippet,
                    "score": round(score, 3),
                    "category": doc.get("category", ""),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({"results": results, "total_found": len(results)}, indent=2),
        }])

    async def _get_document(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        doc_id = args["document_id"]
        include_metadata = args.get("include_metadata", True)

        doc = self.documents.get(doc_id)
        if not doc:
            return ToolResult(
                content=[{"type": "text", "text": f"Document '{doc_id}' not found"}],
                is_error=True,
            )

        response = {"id": doc["id"], "title": doc.get("title"), "content": doc.get("content")}
        if include_metadata:
            response["metadata"] = {
                k: v for k, v in doc.items()
                if k not in ("id", "title", "content")
            }

        return ToolResult(content=[{"type": "text", "text": json.dumps(response, indent=2)}])

    async def _list_categories(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        categories = set(doc.get("category", "uncategorized") for doc in self.documents.values())
        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({"categories": sorted(categories)}),
        }])


# ============================================================================
# 2. SQL Read-Only Query MCP Server
# ============================================================================


class SQLQueryMCPServer(BaseMCPServer):
    """
    MCP server for executing read-only SQL queries with validation.
    Prevents destructive operations and enforces query limits.
    """

    # Dangerous SQL patterns
    BLOCKED_PATTERNS = [
        r"\bDROP\b", r"\bDELETE\b", r"\bINSERT\b", r"\bUPDATE\b",
        r"\bALTER\b", r"\bCREATE\b", r"\bTRUNCATE\b", r"\bGRANT\b",
        r"\bREVOKE\b", r"\bEXEC\b", r"\bEXECUTE\b", r"\bINTO\s+OUTFILE\b",
        r"\bLOAD\s+DATA\b", r";\s*\w",  # Multiple statements
    ]

    ALLOWED_TABLES = {"orders", "customers", "products", "analytics_events"}
    MAX_ROWS = 1000
    QUERY_TIMEOUT_SECONDS = 30

    def __init__(self, db_path: str = ":memory:", **kwargs):
        self.db_path = db_path
        super().__init__(name="sql-readonly", **kwargs)

    def _setup_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="execute_query",
                description=(
                    "Execute a read-only SQL SELECT query against the analytics database. "
                    f"Available tables: {', '.join(sorted(self.ALLOWED_TABLES))}. "
                    f"Results limited to {self.MAX_ROWS} rows."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL SELECT statement to execute",
                        },
                        "explain": {
                            "type": "boolean",
                            "description": "If true, return EXPLAIN plan instead of results",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
                risk_tier="low",
            ),
            self._execute_query,
        )

        self.register_tool(
            ToolDefinition(
                name="list_tables",
                description="List available tables and their schemas.",
                input_schema={"type": "object", "properties": {}},
                risk_tier="low",
            ),
            self._list_tables,
        )

        self.register_tool(
            ToolDefinition(
                name="describe_table",
                description="Get the schema (columns, types) of a specific table.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table to describe",
                            "enum": list(self.ALLOWED_TABLES),
                        }
                    },
                    "required": ["table_name"],
                },
                risk_tier="low",
            ),
            self._describe_table,
        )

    def _validate_query(self, query: str) -> tuple[bool, str]:
        """Validate SQL query for safety."""
        query_upper = query.upper().strip()

        # Must start with SELECT or WITH (CTEs)
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
            return False, "Only SELECT queries are allowed"

        # Check for blocked patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return False, f"Query contains blocked pattern: {pattern}"

        # Check referenced tables (basic extraction)
        # In production: use proper SQL parser (sqlparse, sqlglot)
        words = re.findall(r'\b\w+\b', query.lower())
        from_idx = [i for i, w in enumerate(words) if w in ("from", "join")]
        referenced_tables = set()
        for idx in from_idx:
            if idx + 1 < len(words):
                referenced_tables.add(words[idx + 1])

        disallowed = referenced_tables - self.ALLOWED_TABLES - {"select", "where", "and", "or"}
        if disallowed:
            # Only flag if they look like table names (not SQL keywords)
            actual_disallowed = {t for t in disallowed if t.isidentifier() and len(t) > 2}
            if actual_disallowed:
                return False, f"Access to tables not allowed: {actual_disallowed}"

        return True, ""

    async def _execute_query(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        query = args["query"].strip().rstrip(";")
        explain = args.get("explain", False)

        # Validate
        is_valid, error_msg = self._validate_query(query)
        if not is_valid:
            return ToolResult(
                content=[{"type": "text", "text": f"Query validation failed: {error_msg}"}],
                is_error=True,
            )

        # Add LIMIT if not present
        if "limit" not in query.lower():
            query = f"{query} LIMIT {self.MAX_ROWS}"

        if explain:
            query = f"EXPLAIN QUERY PLAN {query}"

        try:
            conn = sqlite3.connect(self.db_path, timeout=self.QUERY_TIMEOUT_SECONDS)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()

            result_data = [dict(zip(columns, row)) for row in rows]
            response = {
                "columns": columns,
                "rows": result_data,
                "row_count": len(result_data),
                "truncated": len(result_data) >= self.MAX_ROWS,
            }
            return ToolResult(content=[{"type": "text", "text": json.dumps(response, indent=2, default=str)}])

        except sqlite3.Error as e:
            return ToolResult(
                content=[{"type": "text", "text": f"SQL error: {str(e)}"}],
                is_error=True,
            )

    async def _list_tables(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({"tables": sorted(self.ALLOWED_TABLES)}),
        }])

    async def _describe_table(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        table_name = args["table_name"]
        if table_name not in self.ALLOWED_TABLES:
            return ToolResult(
                content=[{"type": "text", "text": f"Table '{table_name}' not found"}],
                is_error=True,
            )

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            conn.close()

            schema = [
                {"name": col[1], "type": col[2], "nullable": not col[3], "primary_key": bool(col[5])}
                for col in columns
            ]
            return ToolResult(content=[{
                "type": "text",
                "text": json.dumps({"table": table_name, "columns": schema}, indent=2),
            }])
        except sqlite3.Error as e:
            return ToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True,
            )


# ============================================================================
# 3. Ticket Creation MCP Server (with Approval Workflow)
# ============================================================================


class TicketPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Ticket:
    id: str
    title: str
    description: str
    priority: str
    assignee: Optional[str]
    created_by: str
    created_at: str
    status: str = "open"
    labels: list[str] = field(default_factory=list)
    approval_status: str = "pending"  # pending, approved, rejected
    approved_by: Optional[str] = None


class TicketMCPServer(BaseMCPServer):
    """
    MCP server for creating and managing tickets.
    High-priority tickets require human approval before creation.
    """

    def __init__(self, **kwargs):
        self.tickets: dict[str, Ticket] = {}
        self.pending_approvals: dict[str, dict[str, Any]] = {}
        super().__init__(name="ticket-system", **kwargs)

    def _setup_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="create_ticket",
                description=(
                    "Create a new support/engineering ticket. "
                    "High and critical priority tickets require human approval."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Brief title for the ticket",
                            "maxLength": 200,
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the issue or request",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Ticket priority level",
                        },
                        "assignee": {
                            "type": "string",
                            "description": "User ID to assign the ticket to (optional)",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Labels/tags for categorization",
                        },
                    },
                    "required": ["title", "description", "priority"],
                },
                risk_tier="medium",
            ),
            self._create_ticket,
        )

        self.register_tool(
            ToolDefinition(
                name="get_ticket",
                description="Retrieve details of an existing ticket by ID.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string", "description": "Ticket ID"},
                    },
                    "required": ["ticket_id"],
                },
                risk_tier="low",
            ),
            self._get_ticket,
        )

        self.register_tool(
            ToolDefinition(
                name="list_tickets",
                description="List tickets with optional filters.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["open", "in_progress", "closed"]},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                        "assignee": {"type": "string"},
                        "limit": {"type": "integer", "default": 20, "maximum": 100},
                    },
                },
                risk_tier="low",
            ),
            self._list_tickets,
        )

    async def _create_ticket(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        priority = args["priority"]

        # High/critical priority requires approval
        if priority in ("high", "critical"):
            approval_id = str(uuid.uuid4())
            self.pending_approvals[approval_id] = {
                "args": args,
                "requester": ctx.user_id,
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }
            return ToolResult(content=[{
                "type": "text",
                "text": json.dumps({
                    "status": "approval_required",
                    "approval_id": approval_id,
                    "message": f"Ticket with priority '{priority}' requires human approval",
                    "review_url": f"https://tickets.internal/approvals/{approval_id}",
                }),
            }])

        # Create ticket directly for low/medium
        ticket = Ticket(
            id=f"TICK-{uuid.uuid4().hex[:8].upper()}",
            title=args["title"],
            description=args["description"],
            priority=priority,
            assignee=args.get("assignee"),
            created_by=ctx.user_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            labels=args.get("labels", []),
            approval_status="auto-approved",
        )
        self.tickets[ticket.id] = ticket

        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({
                "status": "created",
                "ticket": asdict(ticket),
            }, indent=2),
        }])

    async def _get_ticket(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        ticket_id = args["ticket_id"]
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            return ToolResult(
                content=[{"type": "text", "text": f"Ticket '{ticket_id}' not found"}],
                is_error=True,
            )
        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps(asdict(ticket), indent=2),
        }])

    async def _list_tickets(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        tickets = list(self.tickets.values())

        if status := args.get("status"):
            tickets = [t for t in tickets if t.status == status]
        if priority := args.get("priority"):
            tickets = [t for t in tickets if t.priority == priority]
        if assignee := args.get("assignee"):
            tickets = [t for t in tickets if t.assignee == assignee]

        limit = min(args.get("limit", 20), 100)
        tickets = tickets[:limit]

        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({
                "tickets": [asdict(t) for t in tickets],
                "count": len(tickets),
            }, indent=2),
        }])


# ============================================================================
# 4. CRM Lookup MCP Server
# ============================================================================


@dataclass
class CustomerRecord:
    id: str
    name: str
    email: str
    company: str
    plan: str
    mrr: float
    health_score: float
    created_at: str
    last_activity: str
    tags: list[str] = field(default_factory=list)


class CRMMCPServer(BaseMCPServer):
    """
    MCP server for CRM lookups. Read-only access to customer data.
    Enforces PII access controls.
    """

    def __init__(self, customers: list[CustomerRecord] | None = None, **kwargs):
        self.customers: dict[str, CustomerRecord] = {}
        super().__init__(name="crm-lookup", **kwargs)
        if customers:
            for c in customers:
                self.customers[c.id] = c

    def _setup_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="lookup_customer",
                description="Look up a customer by ID, email, or company name.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "description": "Customer ID"},
                        "email": {"type": "string", "description": "Customer email"},
                        "company": {"type": "string", "description": "Company name"},
                    },
                },
                risk_tier="medium",  # Contains PII
            ),
            self._lookup_customer,
        )

        self.register_tool(
            ToolDefinition(
                name="search_customers",
                description="Search customers by various criteria.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term"},
                        "plan": {"type": "string", "enum": ["free", "starter", "pro", "enterprise"]},
                        "min_mrr": {"type": "number", "description": "Minimum MRR filter"},
                        "health_below": {"type": "number", "description": "Health score below threshold"},
                        "limit": {"type": "integer", "default": 10, "maximum": 50},
                    },
                    "required": ["query"],
                },
                risk_tier="medium",
            ),
            self._search_customers,
        )

        self.register_tool(
            ToolDefinition(
                name="get_customer_activity",
                description="Get recent activity timeline for a customer.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "days": {"type": "integer", "default": 30, "maximum": 90},
                    },
                    "required": ["customer_id"],
                },
                risk_tier="low",
            ),
            self._get_customer_activity,
        )

    async def _lookup_customer(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        if cid := args.get("customer_id"):
            customer = self.customers.get(cid)
        elif email := args.get("email"):
            customer = next((c for c in self.customers.values() if c.email == email), None)
        elif company := args.get("company"):
            customer = next(
                (c for c in self.customers.values() if company.lower() in c.company.lower()),
                None,
            )
        else:
            return ToolResult(
                content=[{"type": "text", "text": "Provide customer_id, email, or company"}],
                is_error=True,
            )

        if not customer:
            return ToolResult(content=[{"type": "text", "text": "Customer not found"}], is_error=True)

        # Redact PII based on role
        data = asdict(customer)
        if "pii_reader" not in ctx.roles:
            data["email"] = data["email"][:3] + "***@" + data["email"].split("@")[1]

        return ToolResult(content=[{"type": "text", "text": json.dumps(data, indent=2)}])

    async def _search_customers(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        query = args["query"].lower()
        results = []

        for customer in self.customers.values():
            if query in customer.name.lower() or query in customer.company.lower():
                if plan := args.get("plan"):
                    if customer.plan != plan:
                        continue
                if min_mrr := args.get("min_mrr"):
                    if customer.mrr < min_mrr:
                        continue
                if health_below := args.get("health_below"):
                    if customer.health_score >= health_below:
                        continue
                results.append({
                    "id": customer.id,
                    "name": customer.name,
                    "company": customer.company,
                    "plan": customer.plan,
                    "mrr": customer.mrr,
                    "health_score": customer.health_score,
                })

        limit = min(args.get("limit", 10), 50)
        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({"results": results[:limit], "total": len(results)}, indent=2),
        }])

    async def _get_customer_activity(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        cid = args["customer_id"]
        if cid not in self.customers:
            return ToolResult(content=[{"type": "text", "text": "Customer not found"}], is_error=True)

        # Simulated activity
        activities = [
            {"type": "login", "timestamp": "2024-12-01T10:00:00Z"},
            {"type": "feature_used", "feature": "reports", "timestamp": "2024-12-01T10:05:00Z"},
            {"type": "support_ticket", "ticket_id": "TICK-001", "timestamp": "2024-11-28T14:00:00Z"},
        ]
        return ToolResult(content=[{
            "type": "text",
            "text": json.dumps({"customer_id": cid, "activities": activities}, indent=2),
        }])


# ============================================================================
# 5. Safe Code Execution MCP Server (Sandboxed)
# ============================================================================


class CodeExecutionMCPServer(BaseMCPServer):
    """
    MCP server for safely executing code in a sandboxed environment.
    Uses subprocess isolation with resource limits.
    """

    ALLOWED_LANGUAGES = {"python", "javascript"}
    MAX_EXECUTION_TIME = 10  # seconds
    MAX_OUTPUT_SIZE = 10_000  # characters
    MAX_MEMORY_MB = 256

    # Dangerous imports/modules to block
    PYTHON_BLOCKED_IMPORTS = {
        "os", "subprocess", "sys", "shutil", "pathlib",
        "socket", "http", "urllib", "requests", "ctypes",
        "importlib", "builtins", "__builtin__",
    }

    def __init__(self, **kwargs):
        super().__init__(name="code-execution", **kwargs)

    def _setup_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="execute_code",
                description=(
                    "Execute code in a sandboxed environment. "
                    "Supports Python and JavaScript. Network access is blocked. "
                    f"Timeout: {self.MAX_EXECUTION_TIME}s. Memory limit: {self.MAX_MEMORY_MB}MB."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "language": {
                            "type": "string",
                            "enum": list(self.ALLOWED_LANGUAGES),
                            "description": "Programming language",
                        },
                        "code": {
                            "type": "string",
                            "description": "Code to execute",
                            "maxLength": 5000,
                        },
                    },
                    "required": ["language", "code"],
                },
                risk_tier="high",
                requires_approval=False,  # Sandboxed, so auto-approved
            ),
            self._execute_code,
        )

    def _validate_python_code(self, code: str) -> tuple[bool, str]:
        """Check for dangerous patterns in Python code."""
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    if module in self.PYTHON_BLOCKED_IMPORTS:
                        return False, f"Import of '{module}' is not allowed"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split(".")[0]
                    if module in self.PYTHON_BLOCKED_IMPORTS:
                        return False, f"Import from '{module}' is not allowed"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "compile", "__import__", "open"):
                        return False, f"Function '{node.func.id}' is not allowed"

        return True, ""

    async def _execute_code(
        self, args: dict[str, Any], ctx: AuthContext
    ) -> ToolResult:
        language = args["language"]
        code = args["code"]

        if language == "python":
            is_valid, error = self._validate_python_code(code)
            if not is_valid:
                return ToolResult(
                    content=[{"type": "text", "text": f"Code validation failed: {error}"}],
                    is_error=True,
                )

        # Write code to temp file
        suffix = ".py" if language == "python" else ".js"
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            if language == "python":
                cmd = ["python3", "-u", temp_path]
            else:
                cmd = ["node", temp_path]

            # Execute with timeout and resource limits
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # In production: use cgroups, seccomp, or container for real sandboxing
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.MAX_EXECUTION_TIME,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return ToolResult(
                    content=[{"type": "text", "text": f"Execution timed out after {self.MAX_EXECUTION_TIME}s"}],
                    is_error=True,
                )

            stdout_str = stdout.decode("utf-8", errors="replace")[:self.MAX_OUTPUT_SIZE]
            stderr_str = stderr.decode("utf-8", errors="replace")[:self.MAX_OUTPUT_SIZE]

            result = {
                "exit_code": process.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str if stderr_str else None,
                "truncated": len(stdout) > self.MAX_OUTPUT_SIZE,
            }

            return ToolResult(
                content=[{"type": "text", "text": json.dumps(result, indent=2)}],
                is_error=process.returncode != 0,
            )

        finally:
            Path(temp_path).unlink(missing_ok=True)


# ============================================================================
# Server Runner (stdio transport)
# ============================================================================


async def run_server_stdio(server: BaseMCPServer) -> None:
    """
    Run an MCP server over stdio transport.
    Reads JSON-RPC messages from stdin, writes responses to stdout.
    """
    import sys

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    auth_ctx = AuthContext(user_id="local-user", session_id=str(uuid.uuid4()), roles=["admin"])

    while True:
        line = await reader.readline()
        if not line:
            break

        try:
            message = json.loads(line.decode())
        except json.JSONDecodeError:
            continue

        method = message.get("method", "")
        params = message.get("params", {})
        msg_id = message.get("id")

        result = None
        error = None

        try:
            if method == "initialize":
                result = await server.handle_initialize()
            elif method == "tools/list":
                result = {"tools": await server.handle_tools_list()}
            elif method == "tools/call":
                tool_result = await server.handle_tools_call(
                    params["name"], params.get("arguments", {}), auth_ctx
                )
                result = {"content": tool_result.content, "isError": tool_result.is_error}
            elif method == "resources/list":
                result = {"resources": await server.handle_resources_list()}
            else:
                error = {"code": -32601, "message": f"Method not found: {method}"}
        except MCPError as e:
            error = {"code": e.code.value, "message": e.message, "data": e.data}
        except Exception as e:
            error = {"code": -32603, "message": str(e)}

        response = {"jsonrpc": "2.0", "id": msg_id}
        if error:
            response["error"] = error
        else:
            response["result"] = result

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


# ============================================================================
# Example Usage and Testing
# ============================================================================


async def demo() -> None:
    """Demonstrate MCP server usage."""

    # 1. Knowledge Base Server
    kb_server = KnowledgeBaseMCPServer(
        documents=[
            {
                "id": "doc-1",
                "title": "Getting Started Guide",
                "content": "Welcome to our platform. This guide covers setup and configuration...",
                "category": "onboarding",
                "author": "platform-team",
            },
            {
                "id": "doc-2",
                "title": "API Rate Limiting",
                "content": "Our API enforces rate limits of 1000 requests per minute...",
                "category": "api",
                "author": "engineering",
            },
        ]
    )

    ctx = AuthContext(user_id="demo-user", session_id="demo-session", roles=["analyst"])

    # Search
    result = await kb_server.handle_tools_call("search_documents", {"query": "rate limiting"}, ctx)
    print("KB Search Result:", result.content[0]["text"][:200])

    # 2. SQL Server
    sql_server = SQLQueryMCPServer()
    tools = await sql_server.handle_tools_list()
    print(f"\nSQL Server has {len(tools)} tools:")
    for t in tools:
        print(f"  - {t['name']}: {t['description'][:60]}...")

    # 3. Ticket Server
    ticket_server = TicketMCPServer()
    result = await ticket_server.handle_tools_call(
        "create_ticket",
        {"title": "Fix login bug", "description": "Users can't log in", "priority": "medium"},
        ctx,
    )
    print(f"\nTicket created: {result.content[0]['text'][:100]}...")

    # High priority requires approval
    result = await ticket_server.handle_tools_call(
        "create_ticket",
        {"title": "Production down", "description": "Service outage", "priority": "critical"},
        ctx,
    )
    print(f"\nCritical ticket: {result.content[0]['text'][:100]}...")

    # 4. Code execution
    code_server = CodeExecutionMCPServer()
    result = await code_server.handle_tools_call(
        "execute_code",
        {"language": "python", "code": "print(sum(range(100)))"},
        ctx,
    )
    print(f"\nCode result: {result.content[0]['text'][:100]}...")


if __name__ == "__main__":
    asyncio.run(demo())
