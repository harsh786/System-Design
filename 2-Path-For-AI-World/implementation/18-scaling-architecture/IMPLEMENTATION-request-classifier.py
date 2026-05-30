"""
Request Classification and Routing for AI Scaling.

Classifies incoming requests by type, complexity, and latency requirements,
then routes them to appropriate infrastructure (queues, worker pools, models).
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Request Classes
# ---------------------------------------------------------------------------

class RequestClass(Enum):
    CHAT_SIMPLE = "chat_simple"          # Single-turn, low complexity
    CHAT_COMPLEX = "chat_complex"        # Multi-step reasoning
    RETRIEVAL = "retrieval"              # RAG-heavy request
    TOOL_ACTION = "tool_action"          # Tool-calling dominant
    EVAL = "eval"                        # Evaluation job
    LONG_RUNNING = "long_running"        # Multi-minute job (research, bulk)
    STREAMING = "streaming"              # Real-time streaming response


class Priority(Enum):
    CRITICAL = 0   # System health, admin
    HIGH = 1       # Paid tier, real-time user
    NORMAL = 2     # Standard user request
    LOW = 3        # Background, eval, batch
    BULK = 4       # Bulk processing, can be delayed


class LatencyTier(Enum):
    REALTIME = "realtime"       # < 500ms TTFT
    INTERACTIVE = "interactive"  # < 2s TTFT
    BACKGROUND = "background"    # < 30s
    BATCH = "batch"              # minutes acceptable


# ---------------------------------------------------------------------------
# Request Model
# ---------------------------------------------------------------------------

@dataclass
class IncomingRequest:
    """Raw incoming request before classification."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    message: str = ""
    conversation_history_length: int = 0
    has_file_attachments: bool = False
    requested_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    # Populated by classifier
    tier: str = "free"  # free, pro, enterprise


@dataclass
class ClassifiedRequest:
    """Request after classification with routing information."""

    request: IncomingRequest
    request_class: RequestClass
    priority: Priority
    latency_tier: LatencyTier
    estimated_steps: int
    estimated_tokens: int
    target_queue: str
    target_worker_pool: str
    model_tier: str  # fast, standard, premium
    timeout_seconds: float
    is_async: bool
    routing_metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Classification Rules Engine
# ---------------------------------------------------------------------------

class RequestClassifier:
    """Classifies requests based on content analysis and heuristics."""

    # Complexity indicators
    COMPLEX_KEYWORDS = {
        "analyze", "compare", "explain in detail", "step by step",
        "research", "investigate", "comprehensive", "evaluate",
        "design", "architect", "plan", "strategy",
    }

    TOOL_KEYWORDS = {
        "run", "execute", "call", "create", "delete", "update",
        "send", "deploy", "build", "fetch", "query",
    }

    RETRIEVAL_KEYWORDS = {
        "find", "search", "look up", "what does", "according to",
        "in the docs", "documentation", "knowledge base",
    }

    def __init__(self):
        self._custom_rules: list[Callable[[IncomingRequest], RequestClass | None]] = []

    def add_rule(self, rule: Callable[[IncomingRequest], RequestClass | None]) -> None:
        """Add custom classification rule (checked first)."""
        self._custom_rules.append(rule)

    def classify(self, request: IncomingRequest) -> ClassifiedRequest:
        """Classify a request and determine routing."""

        # Check custom rules first
        req_class = None
        for rule in self._custom_rules:
            req_class = rule(request)
            if req_class:
                break

        if not req_class:
            req_class = self._classify_by_content(request)

        priority = self._assign_priority(request, req_class)
        latency_tier = self._determine_latency_tier(req_class)
        estimated_steps = self._estimate_steps(request, req_class)
        estimated_tokens = self._estimate_tokens(request, req_class, estimated_steps)
        model_tier = self._select_model_tier(req_class, priority, estimated_steps)
        is_async = req_class in (RequestClass.EVAL, RequestClass.LONG_RUNNING)

        return ClassifiedRequest(
            request=request,
            request_class=req_class,
            priority=priority,
            latency_tier=latency_tier,
            estimated_steps=estimated_steps,
            estimated_tokens=estimated_tokens,
            target_queue=self._select_queue(req_class, priority),
            target_worker_pool=self._select_worker_pool(req_class, priority),
            model_tier=model_tier,
            timeout_seconds=self._determine_timeout(req_class, latency_tier),
            is_async=is_async,
            routing_metadata={
                "classified_at": time.time(),
                "classifier_version": "1.0",
            },
        )

    def _classify_by_content(self, request: IncomingRequest) -> RequestClass:
        """Classify based on message content and metadata."""
        msg_lower = request.message.lower()

        # Long-running: file attachments + complex or explicit bulk
        if request.has_file_attachments and len(request.message) > 500:
            return RequestClass.LONG_RUNNING

        if any(kw in msg_lower for kw in ("bulk", "batch", "all files", "entire repo")):
            return RequestClass.LONG_RUNNING

        # Eval: explicit eval requests
        if any(kw in msg_lower for kw in ("evaluate", "score", "benchmark", "test quality")):
            return RequestClass.EVAL

        # Tool action: tool-heavy
        if request.requested_tools or sum(1 for kw in self.TOOL_KEYWORDS if kw in msg_lower) >= 2:
            return RequestClass.TOOL_ACTION

        # Retrieval: search/lookup heavy
        if sum(1 for kw in self.RETRIEVAL_KEYWORDS if kw in msg_lower) >= 2:
            return RequestClass.RETRIEVAL

        # Complex chat: long message, complex keywords, or long history
        complexity_score = (
            (1 if len(request.message) > 300 else 0)
            + sum(1 for kw in self.COMPLEX_KEYWORDS if kw in msg_lower)
            + (1 if request.conversation_history_length > 10 else 0)
        )
        if complexity_score >= 2:
            return RequestClass.CHAT_COMPLEX

        return RequestClass.CHAT_SIMPLE

    def _assign_priority(self, request: IncomingRequest, req_class: RequestClass) -> Priority:
        """Assign priority based on tenant tier and request class."""
        tier_priority = {
            "enterprise": Priority.HIGH,
            "pro": Priority.NORMAL,
            "free": Priority.LOW,
        }
        base = tier_priority.get(request.tier, Priority.NORMAL)

        # Eval and long-running are always lower priority
        if req_class == RequestClass.EVAL:
            return Priority.LOW
        if req_class == RequestClass.LONG_RUNNING:
            return Priority.BULK if request.tier == "free" else Priority.LOW

        return base

    def _determine_latency_tier(self, req_class: RequestClass) -> LatencyTier:
        return {
            RequestClass.CHAT_SIMPLE: LatencyTier.REALTIME,
            RequestClass.CHAT_COMPLEX: LatencyTier.INTERACTIVE,
            RequestClass.RETRIEVAL: LatencyTier.INTERACTIVE,
            RequestClass.TOOL_ACTION: LatencyTier.INTERACTIVE,
            RequestClass.STREAMING: LatencyTier.REALTIME,
            RequestClass.EVAL: LatencyTier.BATCH,
            RequestClass.LONG_RUNNING: LatencyTier.BATCH,
        }[req_class]

    def _estimate_steps(self, request: IncomingRequest, req_class: RequestClass) -> int:
        return {
            RequestClass.CHAT_SIMPLE: 1,
            RequestClass.CHAT_COMPLEX: 4,
            RequestClass.RETRIEVAL: 3,
            RequestClass.TOOL_ACTION: 5,
            RequestClass.STREAMING: 2,
            RequestClass.EVAL: 10,
            RequestClass.LONG_RUNNING: 20,
        }[req_class]

    def _estimate_tokens(self, request: IncomingRequest, req_class: RequestClass, steps: int) -> int:
        base_tokens = len(request.message.split()) * 1.5  # rough word->token
        context_tokens = request.conversation_history_length * 200
        per_step_output = 300
        return int((base_tokens + context_tokens) * steps + per_step_output * steps)

    def _select_model_tier(self, req_class: RequestClass, priority: Priority, steps: int) -> str:
        if req_class == RequestClass.CHAT_SIMPLE:
            return "fast"
        if req_class in (RequestClass.CHAT_COMPLEX, RequestClass.TOOL_ACTION):
            return "premium" if priority.value <= Priority.HIGH.value else "standard"
        if req_class == RequestClass.EVAL:
            return "standard"
        return "standard"

    def _select_queue(self, req_class: RequestClass, priority: Priority) -> str:
        if req_class in (RequestClass.EVAL, RequestClass.LONG_RUNNING):
            return "async-jobs"
        if priority == Priority.CRITICAL:
            return "priority-0"
        if priority == Priority.HIGH:
            return "priority-1"
        return "default"

    def _select_worker_pool(self, req_class: RequestClass, priority: Priority) -> str:
        if req_class == RequestClass.LONG_RUNNING:
            return "long-running-workers"
        if req_class == RequestClass.EVAL:
            return "eval-workers"
        if priority.value <= Priority.HIGH.value:
            return "premium-workers"
        return "standard-workers"

    def _determine_timeout(self, req_class: RequestClass, latency_tier: LatencyTier) -> float:
        return {
            LatencyTier.REALTIME: 10.0,
            LatencyTier.INTERACTIVE: 30.0,
            LatencyTier.BACKGROUND: 120.0,
            LatencyTier.BATCH: 600.0,
        }[latency_tier]


# ---------------------------------------------------------------------------
# Queue Router
# ---------------------------------------------------------------------------

@dataclass
class QueueConfig:
    name: str
    max_depth: int = 10_000
    max_message_age_seconds: float = 300.0
    consumer_count: int = 10
    dead_letter_queue: str = ""


class QueueRouter:
    """Routes classified requests to appropriate queues."""

    def __init__(self):
        self.queues: dict[str, QueueConfig] = {
            "priority-0": QueueConfig("priority-0", max_depth=100, max_message_age_seconds=5, consumer_count=20),
            "priority-1": QueueConfig("priority-1", max_depth=1000, max_message_age_seconds=30, consumer_count=15),
            "default": QueueConfig("default", max_depth=10000, max_message_age_seconds=300, consumer_count=10),
            "async-jobs": QueueConfig("async-jobs", max_depth=50000, max_message_age_seconds=3600, consumer_count=5),
        }
        self._queue_depths: dict[str, int] = {q: 0 for q in self.queues}

    def route(self, classified: ClassifiedRequest) -> dict[str, Any]:
        """Route request to queue, handling overflow."""
        target = classified.target_queue
        queue_cfg = self.queues.get(target, self.queues["default"])

        # Check if queue is full — overflow to next tier or reject
        current_depth = self._queue_depths.get(target, 0)
        if current_depth >= queue_cfg.max_depth:
            if classified.priority.value >= Priority.LOW.value:
                return {
                    "action": "reject",
                    "reason": "queue_full",
                    "queue": target,
                    "retry_after_seconds": 30,
                }
            # High priority overflows to priority queue
            target = "priority-0"

        self._queue_depths[target] = self._queue_depths.get(target, 0) + 1

        return {
            "action": "enqueue",
            "queue": target,
            "worker_pool": classified.target_worker_pool,
            "priority": classified.priority.value,
            "timeout": classified.timeout_seconds,
            "is_async": classified.is_async,
            "message_id": classified.request.request_id,
        }

    def submit_async_job(self, classified: ClassifiedRequest) -> dict[str, Any]:
        """Submit a long-running job and return a job handle."""
        job_id = f"job-{classified.request.request_id}"
        return {
            "action": "async_submit",
            "job_id": job_id,
            "queue": "async-jobs",
            "estimated_duration_seconds": classified.timeout_seconds,
            "poll_url": f"/jobs/{job_id}/status",
            "webhook_supported": True,
        }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main():
    classifier = RequestClassifier()
    router = QueueRouter()

    test_requests = [
        IncomingRequest(message="Hi, what's the weather?", tier="free"),
        IncomingRequest(
            message="Analyze the performance regression in our API and compare it with last month's metrics step by step",
            tier="enterprise",
            conversation_history_length=15,
        ),
        IncomingRequest(
            message="Search the knowledge base for our deployment procedures",
            tier="pro",
        ),
        IncomingRequest(
            message="Run the database migration and deploy to staging",
            tier="enterprise",
            requested_tools=["db_migrate", "deploy"],
        ),
        IncomingRequest(
            message="Process all 500 documents in the uploaded folder and generate summaries",
            tier="pro",
            has_file_attachments=True,
        ),
    ]

    print("=" * 70)
    print("REQUEST CLASSIFICATION AND ROUTING DEMO")
    print("=" * 70)

    for req in test_requests:
        classified = classifier.classify(req)
        route_result = router.route(classified)

        if classified.is_async:
            job = router.submit_async_job(classified)
            route_result["async_job"] = job

        print(f"\nMessage: {req.message[:60]}...")
        print(f"  Class:       {classified.request_class.value}")
        print(f"  Priority:    {classified.priority.name}")
        print(f"  Latency:     {classified.latency_tier.value}")
        print(f"  Model Tier:  {classified.model_tier}")
        print(f"  Steps (est): {classified.estimated_steps}")
        print(f"  Queue:       {route_result.get('queue', 'N/A')}")
        print(f"  Workers:     {classified.target_worker_pool}")
        print(f"  Async:       {classified.is_async}")
        print(f"  Timeout:     {classified.timeout_seconds}s")


if __name__ == "__main__":
    main()
