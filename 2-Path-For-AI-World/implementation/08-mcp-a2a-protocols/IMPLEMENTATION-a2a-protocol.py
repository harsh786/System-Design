"""
A2A (Agent-to-Agent) Protocol Implementation
=============================================
Complete implementation of Google's A2A protocol:
1. Agent Card definition and serving
2. Agent registry (register, discover, query)
3. Task lifecycle management (state machine)
4. Agent authentication (OAuth2 between agents)
5. Task delegation with policy enforcement
6. Human approval for delegated tasks
7. Task tracing and observability
8. Supervisor agent orchestrating remote agents
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Optional

import aiohttp  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


# ============================================================================
# Core A2A Types
# ============================================================================


class TaskState(Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ContentType(Enum):
    TEXT = "text"
    FILE = "file"
    DATA = "data"


@dataclass
class AgentSkill:
    """A capability that an agent offers."""
    id: str
    name: str
    description: str
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])
    tags: list[str] = field(default_factory=list)


@dataclass
class AgentAuthentication:
    """Authentication configuration for an agent."""
    schemes: list[str] = field(default_factory=lambda: ["oauth2"])
    oauth2_token_url: Optional[str] = None
    oauth2_scopes: list[str] = field(default_factory=list)


@dataclass
class AgentCard:
    """
    Agent Card — the identity and capability descriptor for an A2A agent.
    Published at /.well-known/agent.json
    """
    name: str
    description: str
    url: str
    version: str
    skills: list[AgentSkill]
    authentication: AgentAuthentication = field(default_factory=AgentAuthentication)
    capabilities: dict[str, bool] = field(default_factory=lambda: {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    })
    default_input_modes: list[str] = field(default_factory=lambda: ["text"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text"])
    provider: Optional[str] = None
    documentation_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "skills": [asdict(s) for s in self.skills],
            "authentication": {
                "schemes": self.authentication.schemes,
                "oauth2": {
                    "tokenUrl": self.authentication.oauth2_token_url,
                    "scopes": self.authentication.oauth2_scopes,
                } if self.authentication.oauth2_token_url else None,
            },
            "capabilities": self.capabilities,
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "provider": self.provider,
            "documentationUrl": self.documentation_url,
        }


@dataclass
class ContentPart:
    """A piece of content in a message or artifact."""
    type: str  # "text", "file", "data"
    text: Optional[str] = None
    file_uri: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    data: Optional[dict[str, Any]] = None


@dataclass
class Message:
    """A message in the task conversation."""
    role: str  # "user" or "agent"
    parts: list[ContentPart]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Artifact:
    """An output artifact produced by the agent."""
    name: str
    parts: list[ContentPart]
    description: Optional[str] = None
    index: int = 0


@dataclass
class TaskStatus:
    """Current status of a task."""
    state: TaskState
    message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TraceContext:
    """Distributed tracing context (W3C Trace Context compatible)."""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: Optional[str] = None
    delegation_chain: list[dict[str, str]] = field(default_factory=list)


@dataclass
class Task:
    """A task in the A2A protocol."""
    id: str
    session_id: str
    status: TaskStatus
    messages: list[Message] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    history: list[TaskStatus] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    trace: TraceContext = field(default_factory=TraceContext)

    def transition(self, new_state: TaskState, message: Optional[str] = None) -> None:
        """Transition task to a new state with validation."""
        valid_transitions: dict[TaskState, set[TaskState]] = {
            TaskState.SUBMITTED: {TaskState.WORKING, TaskState.FAILED, TaskState.CANCELED},
            TaskState.WORKING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.INPUT_REQUIRED, TaskState.CANCELED},
            TaskState.INPUT_REQUIRED: {TaskState.WORKING, TaskState.FAILED, TaskState.CANCELED},
            TaskState.COMPLETED: set(),  # Terminal
            TaskState.FAILED: set(),  # Terminal
            TaskState.CANCELED: set(),  # Terminal
        }

        allowed = valid_transitions.get(self.status.state, set())
        if new_state not in allowed:
            raise InvalidStateTransition(
                f"Cannot transition from {self.status.state.value} to {new_state.value}"
            )

        self.history.append(self.status)
        self.status = TaskStatus(state=new_state, message=message)


class InvalidStateTransition(Exception):
    pass


# ============================================================================
# Agent Authentication (OAuth2 between agents)
# ============================================================================


@dataclass
class TokenInfo:
    access_token: str
    token_type: str = "Bearer"
    expires_at: float = 0.0
    scopes: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class AgentAuthenticator:
    """
    Handles OAuth2 authentication between agents.
    Supports client_credentials and token_exchange flows.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self._token_cache: dict[str, TokenInfo] = {}

    async def get_token(self, target_agent: AgentCard, scopes: list[str] | None = None) -> str:
        """
        Get an access token for communicating with a target agent.
        Uses client_credentials flow with caching.
        """
        cache_key = f"{target_agent.url}:{','.join(scopes or [])}"

        # Check cache
        cached = self._token_cache.get(cache_key)
        if cached and not cached.is_expired:
            return cached.access_token

        # Request new token
        requested_scopes = scopes or target_agent.authentication.oauth2_scopes
        token_info = await self._request_token(requested_scopes)
        self._token_cache[cache_key] = token_info
        return token_info.access_token

    async def _request_token(self, scopes: list[str]) -> TokenInfo:
        """Request a new token from the authorization server."""
        async with aiohttp.ClientSession() as session:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": " ".join(scopes),
            }
            async with session.post(self.token_url, data=data) as resp:
                if resp.status != 200:
                    raise AuthenticationError(f"Token request failed: {resp.status}")
                body = await resp.json()
                return TokenInfo(
                    access_token=body["access_token"],
                    token_type=body.get("token_type", "Bearer"),
                    expires_at=time.time() + body.get("expires_in", 3600) - 60,
                    scopes=body.get("scope", "").split(),
                )

    async def exchange_token(
        self,
        user_token: str,
        target_agent: AgentCard,
        scopes: list[str],
    ) -> str:
        """
        Exchange a user token for an agent-scoped token (on-behalf-of flow).
        Used when delegating tasks that need to maintain user context.
        """
        async with aiohttp.ClientSession() as session:
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": user_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": " ".join(scopes),
                "audience": target_agent.url,
            }
            async with session.post(self.token_url, data=data) as resp:
                if resp.status != 200:
                    raise AuthenticationError(f"Token exchange failed: {resp.status}")
                body = await resp.json()
                return body["access_token"]


class AuthenticationError(Exception):
    pass


# ============================================================================
# Delegation Policy Engine
# ============================================================================


@dataclass
class DelegationRule:
    """A rule governing task delegation between agents."""
    source_agent: str  # Agent ID that can delegate
    target_agent: str  # Agent ID receiving delegation
    allowed_skills: list[str]  # Skill IDs allowed
    max_cost_tier: str = "medium"  # low, medium, high
    requires_human_approval: bool = False
    max_delegation_depth: int = 3
    timeout_seconds: int = 300
    data_classification_max: str = "internal"  # public, internal, confidential, restricted


class DelegationPolicy:
    """
    Enforces delegation policies between agents.
    Determines whether agent A can delegate task T to agent B.
    """

    def __init__(self, rules: list[DelegationRule] | None = None):
        self.rules = rules or []
        self._rules_index: dict[tuple[str, str], DelegationRule] = {}
        for rule in self.rules:
            self._rules_index[(rule.source_agent, rule.target_agent)] = rule

    def add_rule(self, rule: DelegationRule) -> None:
        self.rules.append(rule)
        self._rules_index[(rule.source_agent, rule.target_agent)] = rule

    def evaluate(
        self,
        source_agent_id: str,
        target_agent_id: str,
        skill_id: str,
        delegation_depth: int = 0,
        data_classification: str = "internal",
    ) -> DelegationDecision:
        """
        Evaluate whether a delegation is allowed.
        Returns a decision with reason.
        """
        key = (source_agent_id, target_agent_id)
        rule = self._rules_index.get(key)

        if not rule:
            return DelegationDecision(
                allowed=False,
                reason=f"No delegation rule from '{source_agent_id}' to '{target_agent_id}'",
            )

        if skill_id not in rule.allowed_skills and "*" not in rule.allowed_skills:
            return DelegationDecision(
                allowed=False,
                reason=f"Skill '{skill_id}' not allowed for this delegation path",
            )

        if delegation_depth >= rule.max_delegation_depth:
            return DelegationDecision(
                allowed=False,
                reason=f"Max delegation depth ({rule.max_delegation_depth}) exceeded",
            )

        classification_levels = ["public", "internal", "confidential", "restricted"]
        if classification_levels.index(data_classification) > classification_levels.index(rule.data_classification_max):
            return DelegationDecision(
                allowed=False,
                reason=f"Data classification '{data_classification}' exceeds maximum '{rule.data_classification_max}'",
            )

        return DelegationDecision(
            allowed=True,
            requires_approval=rule.requires_human_approval,
            timeout_seconds=rule.timeout_seconds,
            reason="Policy allows delegation",
        )


@dataclass
class DelegationDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False
    timeout_seconds: int = 300


# ============================================================================
# Human Approval System
# ============================================================================


@dataclass
class ApprovalRequest:
    id: str
    source_agent: str
    target_agent: str
    skill_id: str
    task_summary: str
    data_preview: str
    requested_at: str
    status: str = "pending"  # pending, approved, rejected, expired
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    expiry: Optional[str] = None


class HumanApprovalSystem:
    """
    Manages human approval requests for high-risk delegations.
    In production: integrates with Slack, Teams, email, or custom UI.
    """

    def __init__(self, default_timeout_minutes: int = 30):
        self.default_timeout = default_timeout_minutes
        self._pending: dict[str, ApprovalRequest] = {}
        self._approval_callbacks: list[Callable] = []

    async def request_approval(
        self,
        source_agent: str,
        target_agent: str,
        skill_id: str,
        task_summary: str,
        data_preview: str = "",
    ) -> ApprovalRequest:
        """Create and submit an approval request."""
        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            source_agent=source_agent,
            target_agent=target_agent,
            skill_id=skill_id,
            task_summary=task_summary,
            data_preview=data_preview[:500],  # Truncate for safety
            requested_at=datetime.now(timezone.utc).isoformat(),
            expiry=(datetime.now(timezone.utc) + timedelta(minutes=self.default_timeout)).isoformat(),
        )
        self._pending[request.id] = request

        # Notify approval channels (Slack, email, etc.)
        await self._notify_approvers(request)
        logger.info(f"Approval requested: {request.id} ({source_agent} -> {target_agent})")
        return request

    async def wait_for_approval(
        self, request_id: str, timeout_seconds: int = 1800
    ) -> ApprovalRequest:
        """Wait for an approval decision (blocking with timeout)."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            request = self._pending.get(request_id)
            if not request:
                raise ValueError(f"Approval request {request_id} not found")
            if request.status != "pending":
                return request
            await asyncio.sleep(2)

        # Timeout — auto-reject
        request = self._pending[request_id]
        request.status = "expired"
        request.decided_at = datetime.now(timezone.utc).isoformat()
        return request

    async def approve(self, request_id: str, approver: str) -> None:
        """Approve a pending request."""
        request = self._pending.get(request_id)
        if not request or request.status != "pending":
            raise ValueError(f"Cannot approve request {request_id}")
        request.status = "approved"
        request.decided_by = approver
        request.decided_at = datetime.now(timezone.utc).isoformat()

    async def reject(self, request_id: str, approver: str, reason: str = "") -> None:
        """Reject a pending request."""
        request = self._pending.get(request_id)
        if not request or request.status != "pending":
            raise ValueError(f"Cannot reject request {request_id}")
        request.status = "rejected"
        request.decided_by = approver
        request.decided_at = datetime.now(timezone.utc).isoformat()

    async def _notify_approvers(self, request: ApprovalRequest) -> None:
        """Send notification to approval channels."""
        # In production: send Slack message, email, or push notification
        logger.info(
            f"[APPROVAL NEEDED] {request.source_agent} wants to delegate "
            f"'{request.skill_id}' to {request.target_agent}: {request.task_summary}"
        )


# ============================================================================
# Task Manager
# ============================================================================


class TaskManager:
    """
    Manages the lifecycle of A2A tasks.
    Handles creation, state transitions, and persistence.
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._sessions: dict[str, list[str]] = {}  # session_id -> [task_ids]

    def create_task(
        self,
        session_id: Optional[str] = None,
        initial_message: Optional[Message] = None,
        trace: Optional[TraceContext] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Task:
        """Create a new task in SUBMITTED state."""
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        session_id = session_id or f"session-{uuid.uuid4().hex[:12]}"

        task = Task(
            id=task_id,
            session_id=session_id,
            status=TaskStatus(state=TaskState.SUBMITTED),
            messages=[initial_message] if initial_message else [],
            trace=trace or TraceContext(),
            metadata=metadata or {},
        )

        self._tasks[task_id] = task
        self._sessions.setdefault(session_id, []).append(task_id)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_session_tasks(self, session_id: str) -> list[Task]:
        task_ids = self._sessions.get(session_id, [])
        return [self._tasks[tid] for tid in task_ids if tid in self._tasks]

    def update_status(
        self, task_id: str, new_state: TaskState, message: Optional[str] = None
    ) -> Task:
        """Transition a task to a new state."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.transition(new_state, message)
        return task

    def add_message(self, task_id: str, message: Message) -> Task:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.messages.append(message)
        return task

    def add_artifact(self, task_id: str, artifact: Artifact) -> Task:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        artifact.index = len(task.artifacts)
        task.artifacts.append(artifact)
        return task


# ============================================================================
# A2A Agent Client (for calling remote agents)
# ============================================================================


class A2AClient:
    """
    Client for communicating with remote A2A agents.
    Handles agent card discovery, task submission, and status polling.
    """

    def __init__(self, authenticator: Optional[AgentAuthenticator] = None):
        self.authenticator = authenticator
        self._agent_cards_cache: dict[str, AgentCard] = {}

    async def discover_agent(self, agent_url: str) -> AgentCard:
        """Fetch the Agent Card from a remote agent."""
        if cached := self._agent_cards_cache.get(agent_url):
            return cached

        well_known_url = f"{agent_url.rstrip('/')}/.well-known/agent.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(well_known_url) as resp:
                if resp.status != 200:
                    raise AgentDiscoveryError(f"Failed to fetch agent card from {well_known_url}: {resp.status}")
                data = await resp.json()

        card = AgentCard(
            name=data["name"],
            description=data["description"],
            url=data["url"],
            version=data["version"],
            skills=[
                AgentSkill(
                    id=s["id"],
                    name=s["name"],
                    description=s["description"],
                    input_modes=s.get("inputModes", ["text"]),
                    output_modes=s.get("outputModes", ["text"]),
                )
                for s in data.get("skills", [])
            ],
            capabilities=data.get("capabilities", {}),
        )
        self._agent_cards_cache[agent_url] = card
        return card

    async def submit_task(
        self,
        agent_card: AgentCard,
        message: Message,
        session_id: Optional[str] = None,
        trace: Optional[TraceContext] = None,
    ) -> Task:
        """Submit a new task to a remote agent."""
        headers = await self._get_auth_headers(agent_card)

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/send",
            "params": {
                "id": f"task-{uuid.uuid4().hex[:12]}",
                "sessionId": session_id or f"session-{uuid.uuid4().hex[:12]}",
                "message": {
                    "role": message.role,
                    "parts": [asdict(p) for p in message.parts],
                },
                "metadata": {
                    "trace": asdict(trace) if trace else None,
                },
            },
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(agent_card.url, json=payload) as resp:
                if resp.status != 200:
                    raise TaskSubmissionError(f"Task submission failed: {resp.status}")
                data = await resp.json()

        result = data.get("result", {})
        return Task(
            id=result["id"],
            session_id=result["sessionId"],
            status=TaskStatus(
                state=TaskState(result["status"]["state"]),
                message=result["status"].get("message"),
            ),
        )

    async def get_task_status(self, agent_card: AgentCard, task_id: str) -> Task:
        """Poll the status of a task on a remote agent."""
        headers = await self._get_auth_headers(agent_card)

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/get",
            "params": {"id": task_id},
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(agent_card.url, json=payload) as resp:
                if resp.status != 200:
                    raise TaskSubmissionError(f"Status check failed: {resp.status}")
                data = await resp.json()

        result = data.get("result", {})
        return Task(
            id=result["id"],
            session_id=result["sessionId"],
            status=TaskStatus(
                state=TaskState(result["status"]["state"]),
                message=result["status"].get("message"),
            ),
            artifacts=[
                Artifact(
                    name=a.get("name", ""),
                    parts=[ContentPart(**p) for p in a.get("parts", [])],
                )
                for a in result.get("artifacts", [])
            ],
        )

    async def send_input(
        self, agent_card: AgentCard, task_id: str, message: Message
    ) -> Task:
        """Send additional input to a task that requires it."""
        headers = await self._get_auth_headers(agent_card)

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": {
                    "role": message.role,
                    "parts": [asdict(p) for p in message.parts],
                },
            },
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(agent_card.url, json=payload) as resp:
                data = await resp.json()

        result = data.get("result", {})
        return Task(
            id=result["id"],
            session_id=result["sessionId"],
            status=TaskStatus(state=TaskState(result["status"]["state"])),
        )

    async def cancel_task(self, agent_card: AgentCard, task_id: str) -> None:
        """Cancel a running task."""
        headers = await self._get_auth_headers(agent_card)
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/cancel",
            "params": {"id": task_id},
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(agent_card.url, json=payload) as resp:
                if resp.status != 200:
                    raise TaskSubmissionError(f"Cancel failed: {resp.status}")

    async def _get_auth_headers(self, agent_card: AgentCard) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.authenticator and agent_card.authentication.oauth2_token_url:
            token = await self.authenticator.get_token(agent_card)
            headers["Authorization"] = f"Bearer {token}"
        return headers


class AgentDiscoveryError(Exception):
    pass


class TaskSubmissionError(Exception):
    pass


# ============================================================================
# A2A Agent Server (base for building agents)
# ============================================================================


class A2AAgentServer:
    """
    Base class for building A2A-compatible agent servers.
    Handles the protocol layer; subclass to implement agent logic.
    """

    def __init__(self, agent_card: AgentCard):
        self.agent_card = agent_card
        self.task_manager = TaskManager()
        self._skill_handlers: dict[str, Callable] = {}

    def register_skill_handler(self, skill_id: str, handler: Callable) -> None:
        """Register a handler function for a skill."""
        self._skill_handlers[skill_id] = handler

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "tasks/send":
                result = await self._handle_task_send(params)
            elif method == "tasks/get":
                result = await self._handle_task_get(params)
            elif method == "tasks/cancel":
                result = await self._handle_task_cancel(params)
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        except Exception as e:
            logger.exception(f"Error handling {method}")
            return self._error_response(req_id, -32603, str(e))

    async def _handle_task_send(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tasks/send — create or continue a task."""
        task_id = params.get("id")
        session_id = params.get("sessionId")
        msg_data = params.get("message", {})

        message = Message(
            role=msg_data.get("role", "user"),
            parts=[ContentPart(**p) for p in msg_data.get("parts", [])],
        )

        # Check if continuing existing task
        existing = self.task_manager.get_task(task_id) if task_id else None

        if existing:
            self.task_manager.add_message(task_id, message)
            self.task_manager.update_status(task_id, TaskState.WORKING)
            # Process asynchronously
            asyncio.create_task(self._process_task(existing))
            task = existing
        else:
            task = self.task_manager.create_task(
                session_id=session_id,
                initial_message=message,
            )
            # Override ID if provided
            if task_id:
                self.task_manager._tasks[task_id] = task
                task.id = task_id
            asyncio.create_task(self._process_task(task))

        return self._task_to_response(task)

    async def _handle_task_get(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("id")
        task = self.task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        return self._task_to_response(task)

    async def _handle_task_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("id")
        task = self.task_manager.update_status(task_id, TaskState.CANCELED, "Canceled by client")
        return self._task_to_response(task)

    async def _process_task(self, task: Task) -> None:
        """Process a task using registered skill handlers. Override in subclass."""
        try:
            self.task_manager.update_status(task.id, TaskState.WORKING)

            # Determine which skill to use based on message content
            # Simple matching — in production use intent classification
            handler = self._match_skill(task)
            if handler:
                await handler(task, self.task_manager)
            else:
                self.task_manager.update_status(
                    task.id, TaskState.FAILED, "No matching skill found"
                )
        except Exception as e:
            self.task_manager.update_status(task.id, TaskState.FAILED, str(e))

    def _match_skill(self, task: Task) -> Optional[Callable]:
        """Match a task to a skill handler. Simple keyword matching."""
        if not task.messages:
            return None
        text = " ".join(
            p.text or "" for m in task.messages for p in m.parts if p.type == "text"
        ).lower()
        for skill in self.agent_card.skills:
            keywords = skill.name.lower().split() + skill.tags
            if any(kw in text for kw in keywords):
                return self._skill_handlers.get(skill.id)
        # Default to first handler
        if self._skill_handlers:
            return next(iter(self._skill_handlers.values()))
        return None

    def _task_to_response(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "sessionId": task.session_id,
            "status": {
                "state": task.status.state.value,
                "message": task.status.message,
                "timestamp": task.status.timestamp,
            },
            "artifacts": [
                {"name": a.name, "parts": [asdict(p) for p in a.parts]}
                for a in task.artifacts
            ],
            "history": [
                {"state": s.state.value, "timestamp": s.timestamp}
                for s in task.history
            ],
        }

    def _error_response(self, req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ============================================================================
# Supervisor Agent (Orchestrates Remote Agents)
# ============================================================================


class SupervisorAgent:
    """
    A supervisor agent that orchestrates work across multiple remote agents.
    Implements delegation policy, approval workflows, and tracing.
    """

    def __init__(
        self,
        agent_id: str,
        a2a_client: A2AClient,
        policy: DelegationPolicy,
        approval_system: HumanApprovalSystem,
    ):
        self.agent_id = agent_id
        self.client = a2a_client
        self.policy = policy
        self.approval_system = approval_system
        self._known_agents: dict[str, AgentCard] = {}

    async def register_agent(self, agent_url: str) -> AgentCard:
        """Discover and register a remote agent."""
        card = await self.client.discover_agent(agent_url)
        self._known_agents[card.name] = card
        logger.info(f"Registered agent: {card.name} ({len(card.skills)} skills)")
        return card

    async def find_agent_for_skill(self, skill_description: str) -> Optional[AgentCard]:
        """Find a registered agent that can handle a skill."""
        # Simple keyword matching — in production use semantic similarity
        desc_lower = skill_description.lower()
        for card in self._known_agents.values():
            for skill in card.skills:
                if any(word in skill.description.lower() for word in desc_lower.split()):
                    return card
        return None

    async def delegate_task(
        self,
        target_agent: AgentCard,
        skill_id: str,
        message: Message,
        trace: Optional[TraceContext] = None,
        data_classification: str = "internal",
    ) -> Task:
        """
        Delegate a task to a remote agent with policy enforcement.

        Steps:
        1. Evaluate delegation policy
        2. Request human approval if required
        3. Submit task with trace context
        4. Return task handle
        """
        # Build trace context
        if trace is None:
            trace = TraceContext()
        child_trace = TraceContext(
            trace_id=trace.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=trace.span_id,
            delegation_chain=trace.delegation_chain + [
                {"agent": self.agent_id, "timestamp": datetime.now(timezone.utc).isoformat()}
            ],
        )

        # Evaluate policy
        decision = self.policy.evaluate(
            source_agent_id=self.agent_id,
            target_agent_id=target_agent.name,
            skill_id=skill_id,
            delegation_depth=len(child_trace.delegation_chain),
            data_classification=data_classification,
        )

        if not decision.allowed:
            raise DelegationDeniedError(decision.reason)

        # Human approval if required
        if decision.requires_approval:
            task_summary = " ".join(
                p.text or "" for p in message.parts if p.type == "text"
            )[:200]
            approval = await self.approval_system.request_approval(
                source_agent=self.agent_id,
                target_agent=target_agent.name,
                skill_id=skill_id,
                task_summary=task_summary,
            )
            approval = await self.approval_system.wait_for_approval(
                approval.id, timeout_seconds=decision.timeout_seconds
            )
            if approval.status != "approved":
                raise DelegationDeniedError(f"Approval {approval.status}: {approval.decided_by}")

        # Submit task
        task = await self.client.submit_task(
            agent_card=target_agent,
            message=message,
            trace=child_trace,
        )

        logger.info(
            f"Delegated task {task.id} to {target_agent.name} "
            f"(trace: {child_trace.trace_id})"
        )
        return task

    async def wait_for_completion(
        self,
        agent_card: AgentCard,
        task_id: str,
        timeout_seconds: int = 300,
        poll_interval: float = 2.0,
    ) -> Task:
        """Poll until task reaches a terminal state."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            task = await self.client.get_task_status(agent_card, task_id)
            if task.status.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
                return task
            if task.status.state == TaskState.INPUT_REQUIRED:
                return task  # Caller needs to provide input
            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout_seconds}s")

    async def orchestrate(
        self,
        plan: list[dict[str, Any]],
        trace: Optional[TraceContext] = None,
    ) -> list[Task]:
        """
        Execute a multi-step plan by delegating to appropriate agents.

        plan format:
        [
            {"skill": "process-expense", "input": "...", "agent": "expense-agent"},
            {"skill": "send-notification", "input": "...", "agent": "notification-agent"},
        ]
        """
        results: list[Task] = []
        trace = trace or TraceContext()

        for step in plan:
            agent_name = step["agent"]
            agent_card = self._known_agents.get(agent_name)
            if not agent_card:
                raise ValueError(f"Unknown agent: {agent_name}")

            message = Message(
                role="user",
                parts=[ContentPart(type="text", text=step["input"])],
            )

            task = await self.delegate_task(
                target_agent=agent_card,
                skill_id=step["skill"],
                message=message,
                trace=trace,
            )

            # Wait for completion
            completed = await self.wait_for_completion(agent_card, task.id)
            results.append(completed)

            if completed.status.state == TaskState.FAILED:
                logger.error(f"Step failed at {agent_name}: {completed.status.message}")
                break

        return results


class DelegationDeniedError(Exception):
    pass


# ============================================================================
# Example: Expense Processing Agent
# ============================================================================


class ExpenseAgent(A2AAgentServer):
    """Example agent that processes expense reports."""

    def __init__(self):
        card = AgentCard(
            name="expense-agent",
            description="Processes expense reports, validates receipts, routes for approval",
            url="https://expense-agent.internal",
            version="1.0.0",
            skills=[
                AgentSkill(
                    id="process-expense",
                    name="Process Expense Report",
                    description="Submit and validate an expense report",
                    input_modes=["text", "file"],
                    output_modes=["text"],
                    tags=["expense", "receipt", "reimbursement"],
                ),
            ],
            authentication=AgentAuthentication(
                schemes=["oauth2"],
                oauth2_token_url="https://auth.company.com/oauth/token",
                oauth2_scopes=["agent:expense:submit"],
            ),
        )
        super().__init__(card)
        self.register_skill_handler("process-expense", self._process_expense)

    async def _process_expense(self, task: Task, manager: TaskManager) -> None:
        """Process an expense report."""
        # Extract info from message
        text = " ".join(
            p.text or "" for m in task.messages for p in m.parts if p.type == "text"
        )

        # Simulate processing steps
        await asyncio.sleep(0.5)  # Validate receipts
        manager.update_status(task.id, TaskState.WORKING, "Validating receipts...")

        await asyncio.sleep(0.5)  # Check policy
        # Could transition to INPUT_REQUIRED if missing info

        # Complete
        manager.add_artifact(
            task.id,
            Artifact(
                name="expense-report",
                parts=[ContentPart(
                    type="text",
                    text=json.dumps({
                        "status": "approved",
                        "amount": 150.00,
                        "category": "travel",
                        "reimbursement_eta": "3-5 business days",
                    }),
                )],
                description="Processed expense report",
            ),
        )
        manager.update_status(task.id, TaskState.COMPLETED, "Expense report processed successfully")


# ============================================================================
# Demo
# ============================================================================


async def demo() -> None:
    """Demonstrate A2A protocol usage."""
    print("=== A2A Protocol Demo ===\n")

    # Create an expense agent
    expense_agent = ExpenseAgent()
    print(f"Agent Card: {expense_agent.agent_card.name}")
    print(f"Skills: {[s.name for s in expense_agent.agent_card.skills]}")

    # Simulate task submission
    request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tasks/send",
        "params": {
            "id": "task-001",
            "sessionId": "session-001",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Process my expense: $150 flight to NYC"}],
            },
        },
    }

    response = await expense_agent.handle_request(request)
    print(f"\nTask submitted: {json.dumps(response['result']['status'], indent=2)}")

    # Wait for processing
    await asyncio.sleep(1.5)

    # Check status
    get_request = {"jsonrpc": "2.0", "id": "2", "method": "tasks/get", "params": {"id": "task-001"}}
    response = await expense_agent.handle_request(get_request)
    print(f"\nTask result: {json.dumps(response['result'], indent=2)}")

    # Demonstrate delegation policy
    print("\n\n=== Delegation Policy Demo ===\n")
    policy = DelegationPolicy(rules=[
        DelegationRule(
            source_agent="orchestrator",
            target_agent="expense-agent",
            allowed_skills=["process-expense"],
            requires_human_approval=False,
        ),
        DelegationRule(
            source_agent="orchestrator",
            target_agent="payment-agent",
            allowed_skills=["initiate-payment"],
            requires_human_approval=True,
            max_cost_tier="high",
        ),
    ])

    decision = policy.evaluate("orchestrator", "expense-agent", "process-expense")
    print(f"Delegate to expense-agent: allowed={decision.allowed}, approval={decision.requires_approval}")

    decision = policy.evaluate("orchestrator", "payment-agent", "initiate-payment")
    print(f"Delegate to payment-agent: allowed={decision.allowed}, approval={decision.requires_approval}")

    decision = policy.evaluate("orchestrator", "unknown-agent", "some-skill")
    print(f"Delegate to unknown-agent: allowed={decision.allowed}, reason={decision.reason}")


if __name__ == "__main__":
    asyncio.run(demo())
