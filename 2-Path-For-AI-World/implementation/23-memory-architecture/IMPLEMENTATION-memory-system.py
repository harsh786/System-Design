"""
Memory Architecture - Complete Memory System Implementation

Production-grade memory system for AI agents with 9 memory types,
write/read controllers, classification, expiration, and persistence.
"""

import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import numpy as np


# =============================================================================
# ENUMS AND TYPES
# =============================================================================

class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    TOOL = "tool"
    PROJECT = "project"
    ORGANIZATION = "organization"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class Sensitivity(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class Importance(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Memory:
    """Core memory unit stored in the system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    user_id: str = ""
    project_id: str = ""
    org_id: str = ""
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    importance: Importance = Importance.MEDIUM
    source: str = ""  # What created this memory
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: Optional[int] = None  # None = no expiration
    is_deleted: bool = False
    confidence: float = 1.0  # 0.0 to 1.0

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "org_id": self.org_id,
            "sensitivity": self.sensitivity.value,
            "importance": self.importance.value,
            "source": self.source,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
            "confidence": self.confidence,
        }


@dataclass
class MemoryQuery:
    """Query parameters for memory retrieval."""
    text: str = ""
    user_id: str = ""
    project_id: str = ""
    org_id: str = ""
    memory_types: list[MemoryType] = field(default_factory=list)
    min_importance: Importance = Importance.LOW
    max_sensitivity: Sensitivity = Sensitivity.RESTRICTED
    tags: list[str] = field(default_factory=list)
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    limit: int = 10
    # Retrieval weights
    recency_weight: float = 0.3
    relevance_weight: float = 0.5
    importance_weight: float = 0.2


@dataclass
class WriteDecision:
    """Decision from the write controller about whether/how to store a memory."""
    should_store: bool = True
    memory_type: MemoryType = MemoryType.EPISODIC
    importance: Importance = Importance.MEDIUM
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    ttl_seconds: Optional[int] = None
    reason: str = ""
    requires_consent: bool = False
    pii_detected: list[str] = field(default_factory=list)
    redacted_content: Optional[str] = None


# =============================================================================
# EMBEDDING SERVICE (Interface)
# =============================================================================

class EmbeddingService(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        pass


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service for demonstration. Replace with OpenAI/Cohere/etc."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        # Deterministic mock: hash text to get consistent embeddings
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype(float)
        # Normalize
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


# =============================================================================
# MEMORY STORE (Backend)
# =============================================================================

class MemoryStore(ABC):
    """Abstract memory storage backend."""

    @abstractmethod
    def store(self, memory: Memory) -> str:
        pass

    @abstractmethod
    def get(self, memory_id: str) -> Optional[Memory]:
        pass

    @abstractmethod
    def search(self, query: MemoryQuery, query_embedding: Optional[list[float]] = None) -> list[Memory]:
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        pass

    @abstractmethod
    def update(self, memory: Memory) -> bool:
        pass

    @abstractmethod
    def get_by_user(self, user_id: str, memory_type: Optional[MemoryType] = None) -> list[Memory]:
        pass


class InMemoryStore(MemoryStore):
    """In-memory store for development/testing. Replace with PostgreSQL+pgvector in production."""

    def __init__(self):
        self._memories: dict[str, Memory] = {}

    def store(self, memory: Memory) -> str:
        self._memories[memory.id] = memory
        return memory.id

    def get(self, memory_id: str) -> Optional[Memory]:
        mem = self._memories.get(memory_id)
        if mem and not mem.is_deleted and not mem.is_expired:
            mem.last_accessed = datetime.utcnow()
            mem.access_count += 1
            return mem
        return None

    def search(self, query: MemoryQuery, query_embedding: Optional[list[float]] = None) -> list[Memory]:
        candidates = []
        for mem in self._memories.values():
            if mem.is_deleted or mem.is_expired:
                continue
            # Access control: user isolation
            if query.user_id and mem.user_id and mem.user_id != query.user_id:
                # Only allow org-level memories if same org
                if mem.memory_type != MemoryType.ORGANIZATION:
                    continue
                if mem.org_id != query.org_id:
                    continue
            # Filter by type
            if query.memory_types and mem.memory_type not in query.memory_types:
                continue
            # Filter by importance
            if mem.importance.value < query.min_importance.value:
                continue
            # Filter by sensitivity
            if mem.sensitivity.value > query.max_sensitivity.value:
                continue
            # Filter by time range
            if query.time_range_start and mem.created_at < query.time_range_start:
                continue
            if query.time_range_end and mem.created_at > query.time_range_end:
                continue
            # Filter by tags
            if query.tags and not any(t in mem.tags for t in query.tags):
                continue
            candidates.append(mem)

        # Score candidates
        scored = []
        now = datetime.utcnow()
        for mem in candidates:
            # Recency score (exponential decay, half-life = 7 days)
            age_hours = (now - mem.created_at).total_seconds() / 3600
            recency_score = np.exp(-0.004 * age_hours)  # ~0.5 at 7 days

            # Relevance score (cosine similarity)
            relevance_score = 0.0
            if query_embedding and mem.embedding:
                relevance_score = float(np.dot(query_embedding, mem.embedding))

            # Importance score (normalized 0-1)
            importance_score = mem.importance.value / 4.0

            # Combined score
            final_score = (
                query.recency_weight * recency_score
                + query.relevance_weight * relevance_score
                + query.importance_weight * importance_score
            )
            scored.append((final_score, mem))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Update access metadata
        results = []
        for _, mem in scored[:query.limit]:
            mem.last_accessed = now
            mem.access_count += 1
            results.append(mem)

        return results

    def delete(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            self._memories[memory_id].is_deleted = True
            return True
        return False

    def update(self, memory: Memory) -> bool:
        if memory.id in self._memories:
            memory.updated_at = datetime.utcnow()
            self._memories[memory.id] = memory
            return True
        return False

    def get_by_user(self, user_id: str, memory_type: Optional[MemoryType] = None) -> list[Memory]:
        results = []
        for mem in self._memories.values():
            if mem.is_deleted or mem.is_expired:
                continue
            if mem.user_id == user_id:
                if memory_type is None or mem.memory_type == memory_type:
                    results.append(mem)
        return results

    def count(self) -> int:
        return sum(1 for m in self._memories.values() if not m.is_deleted and not m.is_expired)

    def cleanup_expired(self) -> int:
        """Remove expired memories. Returns count of removed."""
        removed = 0
        for mem in list(self._memories.values()):
            if mem.is_expired and not mem.is_deleted:
                mem.is_deleted = True
                removed += 1
        return removed


# =============================================================================
# WORKING MEMORY MANAGER
# =============================================================================

class WorkingMemoryManager:
    """
    Manages current task state and context window.
    Working memory is ephemeral—cleared after task completion.
    Analogous to human working memory: limited capacity, active manipulation.
    """

    def __init__(self, max_items: int = 20, max_tokens: int = 8000):
        self.max_items = max_items
        self.max_tokens = max_tokens
        self._state: dict[str, Any] = {}
        self._items: list[dict[str, Any]] = []
        self._task_context: Optional[dict] = None

    def set_task(self, task_id: str, description: str, metadata: dict = None):
        """Set the current active task."""
        self._task_context = {
            "task_id": task_id,
            "description": description,
            "started_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

    def add_item(self, key: str, value: Any, token_estimate: int = 0):
        """Add an item to working memory. Evicts oldest if at capacity."""
        item = {
            "key": key,
            "value": value,
            "added_at": time.time(),
            "token_estimate": token_estimate,
        }
        self._items.append(item)
        self._state[key] = value

        # Evict if over capacity
        while len(self._items) > self.max_items:
            evicted = self._items.pop(0)
            self._state.pop(evicted["key"], None)

        # Evict if over token budget
        total_tokens = sum(i["token_estimate"] for i in self._items)
        while total_tokens > self.max_tokens and self._items:
            evicted = self._items.pop(0)
            self._state.pop(evicted["key"], None)
            total_tokens -= evicted["token_estimate"]

    def get(self, key: str) -> Any:
        return self._state.get(key)

    def get_context(self) -> dict:
        """Get full working memory context for prompt construction."""
        return {
            "task": self._task_context,
            "items": self._items[-self.max_items:],
            "state": self._state,
        }

    def clear(self):
        """Clear all working memory (task complete)."""
        self._state.clear()
        self._items.clear()
        self._task_context = None

    @property
    def token_usage(self) -> int:
        return sum(i["token_estimate"] for i in self._items)


# =============================================================================
# EPISODIC MEMORY STORE
# =============================================================================

class EpisodicMemoryStore:
    """
    Stores conversation history and event logs as episodic memories.
    Each episode is a timestamped event with context.
    """

    def __init__(self, store: MemoryStore, embedding_service: EmbeddingService):
        self.store = store
        self.embedder = embedding_service

    def record_event(
        self,
        user_id: str,
        event_type: str,
        content: str,
        context: dict = None,
        importance: Importance = Importance.MEDIUM,
        project_id: str = "",
        ttl_days: Optional[int] = 90,
    ) -> Memory:
        """Record an episodic event."""
        memory = Memory(
            content=content,
            memory_type=MemoryType.EPISODIC,
            user_id=user_id,
            project_id=project_id,
            importance=importance,
            source=f"event:{event_type}",
            tags=[event_type],
            metadata={"event_type": event_type, "context": context or {}},
            embedding=self.embedder.embed(content),
            ttl_seconds=ttl_days * 86400 if ttl_days else None,
        )
        self.store.store(memory)
        return memory

    def record_conversation_turn(
        self,
        user_id: str,
        role: str,
        content: str,
        session_id: str,
        project_id: str = "",
    ) -> Memory:
        """Record a single conversation turn."""
        summary = content[:500]  # Truncate for storage
        memory = Memory(
            content=summary,
            memory_type=MemoryType.EPISODIC,
            user_id=user_id,
            project_id=project_id,
            importance=Importance.LOW,
            source=f"conversation:{session_id}",
            tags=["conversation", role],
            metadata={"session_id": session_id, "role": role, "full_length": len(content)},
            embedding=self.embedder.embed(summary),
            ttl_seconds=30 * 86400,  # 30 days default
        )
        self.store.store(memory)
        return memory

    def get_session_history(self, user_id: str, session_id: str) -> list[Memory]:
        """Retrieve all memories from a specific session."""
        query = MemoryQuery(
            user_id=user_id,
            memory_types=[MemoryType.EPISODIC],
            tags=["conversation"],
            limit=100,
        )
        all_memories = self.store.search(query)
        return [m for m in all_memories if m.metadata.get("session_id") == session_id]


# =============================================================================
# SEMANTIC MEMORY STORE
# =============================================================================

class SemanticMemoryStore:
    """
    Stores durable facts, user preferences, and learned knowledge.
    Facts are deduplicated and versioned with conflict resolution.
    """

    def __init__(self, store: MemoryStore, embedding_service: EmbeddingService):
        self.store = store
        self.embedder = embedding_service

    def store_fact(
        self,
        user_id: str,
        fact: str,
        category: str = "general",
        confidence: float = 0.9,
        source: str = "inferred",
        project_id: str = "",
        org_id: str = "",
    ) -> Memory:
        """Store a semantic fact. Checks for duplicates/contradictions first."""
        # Check for existing similar facts
        existing = self._find_similar_facts(user_id, fact, threshold=0.9)

        if existing:
            # Update existing fact if more recent
            best_match = existing[0]
            best_match.content = fact
            best_match.updated_at = datetime.utcnow()
            best_match.confidence = max(best_match.confidence, confidence)
            best_match.metadata["update_count"] = best_match.metadata.get("update_count", 0) + 1
            best_match.metadata["last_source"] = source
            self.store.update(best_match)
            return best_match

        # Store new fact
        memory = Memory(
            content=fact,
            memory_type=MemoryType.SEMANTIC,
            user_id=user_id,
            project_id=project_id,
            org_id=org_id,
            importance=Importance.HIGH,
            source=source,
            tags=[category, "fact"],
            metadata={"category": category, "update_count": 0},
            embedding=self.embedder.embed(fact),
            confidence=confidence,
            # Semantic memories don't expire by default
            ttl_seconds=None,
        )
        self.store.store(memory)
        return memory

    def store_preference(
        self,
        user_id: str,
        preference: str,
        category: str = "preference",
        confidence: float = 0.8,
    ) -> Memory:
        """Store a user preference (a special type of semantic fact)."""
        return self.store_fact(
            user_id=user_id,
            fact=preference,
            category=category,
            confidence=confidence,
            source="user_preference",
        )

    def get_facts(self, user_id: str, category: Optional[str] = None, limit: int = 20) -> list[Memory]:
        """Retrieve all known facts for a user."""
        tags = ["fact"]
        if category:
            tags.append(category)
        query = MemoryQuery(
            user_id=user_id,
            memory_types=[MemoryType.SEMANTIC],
            tags=tags,
            limit=limit,
            importance_weight=0.5,
            relevance_weight=0.3,
            recency_weight=0.2,
        )
        return self.store.search(query)

    def _find_similar_facts(self, user_id: str, fact: str, threshold: float = 0.9) -> list[Memory]:
        """Find facts similar to the given one (for deduplication)."""
        embedding = self.embedder.embed(fact)
        query = MemoryQuery(
            user_id=user_id,
            memory_types=[MemoryType.SEMANTIC],
            limit=5,
            relevance_weight=1.0,
            recency_weight=0.0,
            importance_weight=0.0,
        )
        results = self.store.search(query, query_embedding=embedding)
        # Filter by similarity threshold
        return [m for m in results if m.embedding and float(np.dot(embedding, m.embedding)) > threshold]


# =============================================================================
# PROCEDURAL MEMORY STORE
# =============================================================================

@dataclass
class Workflow:
    """A learned workflow/procedure."""
    name: str
    steps: list[str]
    trigger: str  # When to suggest this workflow
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None


class ProceduralMemoryStore:
    """
    Stores learned workflows, patterns, and procedures.
    Workflows are refined over time based on success/failure feedback.
    """

    def __init__(self, store: MemoryStore, embedding_service: EmbeddingService):
        self.store = store
        self.embedder = embedding_service

    def store_workflow(
        self,
        user_id: str,
        name: str,
        steps: list[str],
        trigger: str,
        project_id: str = "",
    ) -> Memory:
        """Store a learned workflow."""
        content = f"Workflow: {name}\nTrigger: {trigger}\nSteps:\n" + "\n".join(
            f"  {i+1}. {step}" for i, step in enumerate(steps)
        )
        memory = Memory(
            content=content,
            memory_type=MemoryType.PROCEDURAL,
            user_id=user_id,
            project_id=project_id,
            importance=Importance.HIGH,
            source="workflow_learning",
            tags=["workflow", name],
            metadata={
                "name": name,
                "steps": steps,
                "trigger": trigger,
                "success_count": 0,
                "failure_count": 0,
            },
            embedding=self.embedder.embed(f"{trigger} {name} {' '.join(steps)}"),
        )
        self.store.store(memory)
        return memory

    def find_relevant_workflows(self, user_id: str, context: str, limit: int = 3) -> list[Memory]:
        """Find workflows relevant to the current context."""
        embedding = self.embedder.embed(context)
        query = MemoryQuery(
            user_id=user_id,
            memory_types=[MemoryType.PROCEDURAL],
            tags=["workflow"],
            limit=limit,
            relevance_weight=0.7,
            importance_weight=0.2,
            recency_weight=0.1,
        )
        return self.store.search(query, query_embedding=embedding)

    def record_outcome(self, memory_id: str, success: bool):
        """Record whether a workflow execution succeeded or failed."""
        mem = self.store.get(memory_id)
        if mem:
            if success:
                mem.metadata["success_count"] = mem.metadata.get("success_count", 0) + 1
            else:
                mem.metadata["failure_count"] = mem.metadata.get("failure_count", 0) + 1
            mem.metadata["last_used"] = datetime.utcnow().isoformat()
            # Increase importance for reliable workflows
            success_rate = mem.metadata["success_count"] / max(
                1, mem.metadata["success_count"] + mem.metadata["failure_count"]
            )
            if success_rate > 0.8 and mem.metadata["success_count"] >= 3:
                mem.importance = Importance.CRITICAL
            self.store.update(mem)


# =============================================================================
# TOOL MEMORY (CACHE)
# =============================================================================

class ToolMemoryCache:
    """
    Caches past tool invocation results to avoid redundant calls.
    Short-lived with invalidation on mutations.
    """

    def __init__(self, store: MemoryStore, default_ttl_seconds: int = 300):
        self.store = store
        self.default_ttl = default_ttl_seconds
        self._invalidation_rules: dict[str, list[str]] = {}

    def cache_result(
        self,
        user_id: str,
        tool_name: str,
        tool_input: dict,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> Memory:
        """Cache a tool result."""
        cache_key = self._make_cache_key(tool_name, tool_input)
        content = json.dumps({"tool": tool_name, "input": tool_input, "result": result}, default=str)

        memory = Memory(
            content=content,
            memory_type=MemoryType.TOOL,
            user_id=user_id,
            importance=Importance.LOW,
            source=f"tool:{tool_name}",
            tags=["tool_cache", tool_name],
            metadata={"cache_key": cache_key, "tool_name": tool_name, "tool_input": tool_input},
            ttl_seconds=ttl_seconds or self.default_ttl,
        )
        self.store.store(memory)
        return memory

    def get_cached(self, user_id: str, tool_name: str, tool_input: dict) -> Optional[Any]:
        """Get cached result if available and not expired."""
        cache_key = self._make_cache_key(tool_name, tool_input)
        query = MemoryQuery(
            user_id=user_id,
            memory_types=[MemoryType.TOOL],
            tags=[tool_name],
            limit=5,
        )
        results = self.store.search(query)
        for mem in results:
            if mem.metadata.get("cache_key") == cache_key and not mem.is_expired:
                data = json.loads(mem.content)
                return data.get("result")
        return None

    def invalidate(self, user_id: str, tool_name: str):
        """Invalidate all cached results for a tool (e.g., after a mutation)."""
        memories = self.store.get_by_user(user_id, MemoryType.TOOL)
        for mem in memories:
            if mem.metadata.get("tool_name") == tool_name:
                self.store.delete(mem.id)

    def register_invalidation_rule(self, mutating_tool: str, invalidates: list[str]):
        """Register that calling mutating_tool should invalidate caches for the listed tools."""
        self._invalidation_rules[mutating_tool] = invalidates

    def on_tool_call(self, user_id: str, tool_name: str):
        """Call after any tool execution to trigger invalidation rules."""
        if tool_name in self._invalidation_rules:
            for invalidated_tool in self._invalidation_rules[tool_name]:
                self.invalidate(user_id, invalidated_tool)

    def _make_cache_key(self, tool_name: str, tool_input: dict) -> str:
        input_str = json.dumps(tool_input, sort_keys=True, default=str)
        return hashlib.sha256(f"{tool_name}:{input_str}".encode()).hexdigest()[:16]


# =============================================================================
# MEMORY WRITE CONTROLLER
# =============================================================================

class MemoryWriteController:
    """
    Decides what to remember from each interaction.
    Applies classification, importance scoring, and policy checks.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        importance_threshold: Importance = Importance.LOW,
    ):
        self.embedder = embedding_service
        self.importance_threshold = importance_threshold
        self._pii_patterns = [
            "email", "phone", "ssn", "social security", "credit card",
            "password", "api key", "secret", "token", "private key",
        ]
        self._preference_signals = [
            "i prefer", "i like", "i always", "i never", "i want",
            "please always", "please never", "don't ever", "my favorite",
        ]
        self._fact_signals = [
            "we use", "our team", "the project", "our stack",
            "the database is", "we deploy", "our ci",
        ]

    def evaluate(self, content: str, context: dict = None) -> WriteDecision:
        """Evaluate whether content should be stored and how."""
        context = context or {}
        decision = WriteDecision()

        # Check for PII
        content_lower = content.lower()
        pii_found = [p for p in self._pii_patterns if p in content_lower]
        if pii_found:
            decision.pii_detected = pii_found
            decision.sensitivity = Sensitivity.RESTRICTED
            # Don't store credentials/secrets
            if any(p in pii_found for p in ["password", "api key", "secret", "token", "private key"]):
                decision.should_store = False
                decision.reason = f"Contains sensitive credentials: {pii_found}"
                return decision
            # Other PII requires consent
            decision.requires_consent = True

        # Classify memory type and importance
        if any(signal in content_lower for signal in self._preference_signals):
            decision.memory_type = MemoryType.SEMANTIC
            decision.importance = Importance.HIGH
            decision.reason = "User preference detected"
        elif any(signal in content_lower for signal in self._fact_signals):
            decision.memory_type = MemoryType.SEMANTIC
            decision.importance = Importance.HIGH
            decision.reason = "Project/team fact detected"
        elif "step 1" in content_lower or "workflow" in content_lower or "process" in content_lower:
            decision.memory_type = MemoryType.PROCEDURAL
            decision.importance = Importance.MEDIUM
            decision.reason = "Procedural knowledge detected"
        else:
            decision.memory_type = MemoryType.EPISODIC
            decision.importance = Importance.LOW
            decision.reason = "General episodic event"

        # Apply importance threshold
        if decision.importance.value < self.importance_threshold.value:
            decision.should_store = False
            decision.reason = f"Below importance threshold ({self.importance_threshold.name})"

        # Set TTL based on type
        ttl_map = {
            MemoryType.EPISODIC: 90 * 86400,    # 90 days
            MemoryType.SEMANTIC: None,            # No expiry
            MemoryType.PROCEDURAL: None,          # No expiry
            MemoryType.TOOL: 300,                 # 5 minutes
            MemoryType.SHORT_TERM: 3600,          # 1 hour
        }
        decision.ttl_seconds = ttl_map.get(decision.memory_type, 30 * 86400)

        return decision


# =============================================================================
# MEMORY READ CONTROLLER
# =============================================================================

class MemoryReadController:
    """
    Decides what memories to retrieve for a given context.
    Applies access control, relevance filtering, and context window management.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_service: EmbeddingService,
        max_memories: int = 10,
        max_tokens: int = 4000,
    ):
        self.store = store
        self.embedder = embedding_service
        self.max_memories = max_memories
        self.max_tokens = max_tokens

    def retrieve(
        self,
        user_id: str,
        context: str,
        project_id: str = "",
        org_id: str = "",
        memory_types: Optional[list[MemoryType]] = None,
        purpose: str = "general",
    ) -> list[Memory]:
        """
        Retrieve relevant memories for the current context.
        Applies access control and fits within token budget.
        """
        # Adjust weights based on purpose
        weights = self._get_weights_for_purpose(purpose)

        query = MemoryQuery(
            text=context,
            user_id=user_id,
            project_id=project_id,
            org_id=org_id,
            memory_types=memory_types or [],
            limit=self.max_memories * 2,  # Over-fetch then trim
            recency_weight=weights["recency"],
            relevance_weight=weights["relevance"],
            importance_weight=weights["importance"],
        )

        query_embedding = self.embedder.embed(context) if context else None
        memories = self.store.search(query, query_embedding=query_embedding)

        # Fit within token budget (rough estimate: 1 token ≈ 4 chars)
        selected = []
        token_count = 0
        for mem in memories:
            mem_tokens = len(mem.content) // 4
            if token_count + mem_tokens > self.max_tokens:
                break
            selected.append(mem)
            token_count += mem_tokens
            if len(selected) >= self.max_memories:
                break

        return selected

    def _get_weights_for_purpose(self, purpose: str) -> dict[str, float]:
        """Adjust retrieval weights based on the purpose of retrieval."""
        purpose_weights = {
            "general": {"recency": 0.3, "relevance": 0.5, "importance": 0.2},
            "question_answering": {"recency": 0.1, "relevance": 0.7, "importance": 0.2},
            "continuation": {"recency": 0.6, "relevance": 0.3, "importance": 0.1},
            "personalization": {"recency": 0.1, "relevance": 0.3, "importance": 0.6},
            "task_execution": {"recency": 0.2, "relevance": 0.4, "importance": 0.4},
        }
        return purpose_weights.get(purpose, purpose_weights["general"])


# =============================================================================
# MEMORY CLASSIFICATION
# =============================================================================

class MemoryClassifier:
    """Classifies memories by importance, sensitivity, and type."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedder = embedding_service

    def classify_importance(self, content: str, context: dict = None) -> Importance:
        """Classify the importance of a potential memory."""
        content_lower = content.lower()

        # Critical: corrections, explicit preferences, security-relevant
        critical_signals = ["always", "never", "important", "critical", "must", "security"]
        if any(s in content_lower for s in critical_signals):
            return Importance.CRITICAL

        # High: preferences, facts, decisions
        high_signals = ["prefer", "use", "our", "decided", "convention", "standard"]
        if any(s in content_lower for s in high_signals):
            return Importance.HIGH

        # Medium: task-related, contextual
        if context and context.get("task_relevant", False):
            return Importance.MEDIUM

        return Importance.LOW

    def classify_sensitivity(self, content: str) -> Sensitivity:
        """Classify the sensitivity level of content."""
        content_lower = content.lower()

        restricted_patterns = [
            "password", "secret", "private key", "ssn", "social security",
            "credit card", "bank account",
        ]
        if any(p in content_lower for p in restricted_patterns):
            return Sensitivity.RESTRICTED

        confidential_patterns = [
            "salary", "compensation", "medical", "health", "personal",
            "address", "phone number", "email",
        ]
        if any(p in content_lower for p in confidential_patterns):
            return Sensitivity.CONFIDENTIAL

        internal_patterns = ["internal", "proprietary", "company", "team"]
        if any(p in content_lower for p in internal_patterns):
            return Sensitivity.INTERNAL

        return Sensitivity.PUBLIC

    def classify_type(self, content: str) -> MemoryType:
        """Classify what type of memory this content represents."""
        content_lower = content.lower()

        if any(w in content_lower for w in ["step", "workflow", "process", "procedure", "how to"]):
            return MemoryType.PROCEDURAL
        if any(w in content_lower for w in ["prefer", "like", "use", "is", "are", "fact"]):
            return MemoryType.SEMANTIC
        return MemoryType.EPISODIC


# =============================================================================
# MEMORY EXPIRATION AND CLEANUP
# =============================================================================

class MemoryExpirationManager:
    """Manages memory lifecycle: expiration, cleanup, and consolidation."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self._max_memories_per_type: dict[MemoryType, int] = {
            MemoryType.WORKING: 20,
            MemoryType.SHORT_TERM: 100,
            MemoryType.EPISODIC: 1000,
            MemoryType.SEMANTIC: 500,
            MemoryType.PROCEDURAL: 100,
            MemoryType.TOOL: 50,
            MemoryType.PROJECT: 200,
            MemoryType.ORGANIZATION: 500,
            MemoryType.LONG_TERM: 2000,
        }

    def run_cleanup(self, user_id: str) -> dict[str, int]:
        """Run full cleanup cycle. Returns stats."""
        stats = {"expired": 0, "over_limit": 0}

        # 1. Remove expired memories
        if isinstance(self.store, InMemoryStore):
            stats["expired"] = self.store.cleanup_expired()

        # 2. Enforce per-type limits (remove oldest low-importance)
        for mem_type, max_count in self._max_memories_per_type.items():
            memories = self.store.get_by_user(user_id, mem_type)
            if len(memories) > max_count:
                # Sort by importance (asc) then recency (asc) — remove least important + oldest
                memories.sort(key=lambda m: (m.importance.value, m.last_accessed.timestamp()))
                to_remove = memories[:len(memories) - max_count]
                for mem in to_remove:
                    self.store.delete(mem.id)
                    stats["over_limit"] += 1

        return stats

    def set_type_limit(self, memory_type: MemoryType, max_count: int):
        self._max_memories_per_type[memory_type] = max_count


# =============================================================================
# CROSS-SESSION MEMORY PERSISTENCE
# =============================================================================

class MemoryPersistenceManager:
    """Handles saving and loading memory state across sessions."""

    def __init__(self, store: MemoryStore):
        self.store = store

    def export_user_memories(self, user_id: str) -> list[dict]:
        """Export all memories for a user (for backup or migration)."""
        memories = self.store.get_by_user(user_id)
        return [m.to_dict() for m in memories if not m.is_deleted]

    def get_session_bootstrap(self, user_id: str, project_id: str = "") -> dict:
        """
        Get memories needed to bootstrap a new session.
        Returns high-importance semantic + procedural memories.
        """
        query = MemoryQuery(
            user_id=user_id,
            project_id=project_id,
            memory_types=[MemoryType.SEMANTIC, MemoryType.PROCEDURAL, MemoryType.PROJECT],
            min_importance=Importance.HIGH,
            limit=20,
            importance_weight=0.6,
            recency_weight=0.3,
            relevance_weight=0.1,
        )
        memories = self.store.search(query)
        return {
            "user_preferences": [m.to_dict() for m in memories if m.memory_type == MemoryType.SEMANTIC],
            "workflows": [m.to_dict() for m in memories if m.memory_type == MemoryType.PROCEDURAL],
            "project_context": [m.to_dict() for m in memories if m.memory_type == MemoryType.PROJECT],
        }


# =============================================================================
# UNIFIED MEMORY SYSTEM
# =============================================================================

class AgentMemorySystem:
    """
    Unified memory system orchestrating all memory types and operations.
    This is the main entry point for agent memory operations.
    """

    def __init__(self, user_id: str, project_id: str = "", org_id: str = ""):
        self.user_id = user_id
        self.project_id = project_id
        self.org_id = org_id

        # Core services
        self.embedding_service = MockEmbeddingService()
        self.store = InMemoryStore()

        # Memory subsystems
        self.working_memory = WorkingMemoryManager()
        self.episodic = EpisodicMemoryStore(self.store, self.embedding_service)
        self.semantic = SemanticMemoryStore(self.store, self.embedding_service)
        self.procedural = ProceduralMemoryStore(self.store, self.embedding_service)
        self.tool_cache = ToolMemoryCache(self.store)

        # Controllers
        self.write_controller = MemoryWriteController(self.embedding_service)
        self.read_controller = MemoryReadController(self.store, self.embedding_service)
        self.classifier = MemoryClassifier(self.embedding_service)
        self.expiration_manager = MemoryExpirationManager(self.store)
        self.persistence = MemoryPersistenceManager(self.store)

        # Audit log
        self._audit_log: list[dict] = []

    def remember(self, content: str, source: str = "interaction", context: dict = None) -> Optional[Memory]:
        """
        Main entry point for storing a new memory.
        Runs through the full write pipeline: classify → check → store.
        """
        # 1. Write controller evaluates
        decision = self.write_controller.evaluate(content, context)

        # 2. Log the decision
        self._audit("write_decision", {
            "content_preview": content[:100],
            "decision": decision.should_store,
            "reason": decision.reason,
            "pii_detected": decision.pii_detected,
        })

        if not decision.should_store:
            return None

        if decision.requires_consent:
            # In production: check consent store or prompt user
            self._audit("consent_required", {"content_preview": content[:100]})
            return None  # Block until consent obtained

        # 3. Store based on classified type
        memory = None
        if decision.memory_type == MemoryType.SEMANTIC:
            memory = self.semantic.store_fact(
                user_id=self.user_id,
                fact=content,
                confidence=0.8,
                source=source,
                project_id=self.project_id,
            )
        elif decision.memory_type == MemoryType.PROCEDURAL:
            # Extract steps (simplified)
            memory = self.procedural.store_workflow(
                user_id=self.user_id,
                name=content[:50],
                steps=[content],
                trigger=content[:30],
                project_id=self.project_id,
            )
        else:
            memory = self.episodic.record_event(
                user_id=self.user_id,
                event_type=source,
                content=content,
                context=context,
                project_id=self.project_id,
            )

        if memory:
            self._audit("memory_stored", {"memory_id": memory.id, "type": memory.memory_type.value})

        return memory

    def recall(self, context: str, purpose: str = "general") -> list[Memory]:
        """
        Main entry point for retrieving relevant memories.
        """
        memories = self.read_controller.retrieve(
            user_id=self.user_id,
            context=context,
            project_id=self.project_id,
            org_id=self.org_id,
            purpose=purpose,
        )
        self._audit("memory_recall", {
            "context_preview": context[:100],
            "results_count": len(memories),
            "purpose": purpose,
        })
        return memories

    def forget(self, memory_id: str, reason: str = "user_request") -> bool:
        """Delete a specific memory."""
        success = self.store.delete(memory_id)
        self._audit("memory_deleted", {"memory_id": memory_id, "reason": reason, "success": success})
        return success

    def forget_all(self, reason: str = "user_request") -> int:
        """Delete all memories for this user (GDPR right to erasure)."""
        memories = self.store.get_by_user(self.user_id)
        count = 0
        for mem in memories:
            self.store.delete(mem.id)
            count += 1
        self._audit("all_memories_deleted", {"count": count, "reason": reason})
        return count

    def cleanup(self) -> dict:
        """Run cleanup cycle."""
        stats = self.expiration_manager.run_cleanup(self.user_id)
        self._audit("cleanup_run", stats)
        return stats

    def get_bootstrap_context(self) -> dict:
        """Get memories needed to start a new session."""
        return self.persistence.get_session_bootstrap(self.user_id, self.project_id)

    def get_audit_log(self) -> list[dict]:
        return self._audit_log

    def _audit(self, action: str, details: dict):
        self._audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": self.user_id,
            "action": action,
            "details": details,
        })


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main():
    """Demonstrate the memory system in action."""
    print("=" * 60)
    print("AGENT MEMORY SYSTEM - DEMONSTRATION")
    print("=" * 60)

    # Initialize memory system for a user
    memory_system = AgentMemorySystem(
        user_id="user_123",
        project_id="proj_abc",
        org_id="org_xyz",
    )

    # 1. Store some memories
    print("\n--- Storing Memories ---")

    # User preference (→ semantic memory)
    mem = memory_system.remember("I prefer TypeScript over JavaScript for all new projects")
    print(f"Stored preference: {mem.memory_type.value if mem else 'blocked'}")

    # Project fact (→ semantic memory)
    mem = memory_system.remember("We use PostgreSQL 15 with pgvector for our vector store")
    print(f"Stored fact: {mem.memory_type.value if mem else 'blocked'}")

    # Workflow (→ procedural memory)
    mem = memory_system.remember("Our deployment workflow: step 1 run tests, step 2 build, step 3 deploy to staging")
    print(f"Stored workflow: {mem.memory_type.value if mem else 'blocked'}")

    # Sensitive content (→ blocked)
    mem = memory_system.remember("My API key is sk-12345abcdef")
    print(f"Stored secret: {mem.memory_type.value if mem else 'BLOCKED (correct!)'}")

    # General event (→ episodic)
    mem = memory_system.remember("User asked about database optimization")
    print(f"Stored event: {mem.memory_type.value if mem else 'blocked'}")

    # 2. Recall memories
    print("\n--- Recalling Memories ---")
    memories = memory_system.recall("What database do we use?", purpose="question_answering")
    print(f"Found {len(memories)} relevant memories:")
    for m in memories:
        print(f"  [{m.memory_type.value}] {m.content[:80]}...")

    # 3. Tool caching
    print("\n--- Tool Memory Cache ---")
    memory_system.tool_cache.cache_result(
        user_id="user_123",
        tool_name="git_status",
        tool_input={"path": "/project"},
        result={"modified": ["src/main.ts", "README.md"]},
    )
    cached = memory_system.tool_cache.get_cached("user_123", "git_status", {"path": "/project"})
    print(f"Cached git_status result: {cached}")

    # 4. Working memory
    print("\n--- Working Memory ---")
    memory_system.working_memory.set_task("task_1", "Refactor auth module")
    memory_system.working_memory.add_item("current_file", "src/auth.ts", token_estimate=100)
    memory_system.working_memory.add_item("error", "Type mismatch on line 42", token_estimate=50)
    print(f"Working memory token usage: {memory_system.working_memory.token_usage}")
    print(f"Current file: {memory_system.working_memory.get('current_file')}")

    # 5. Session bootstrap
    print("\n--- Session Bootstrap ---")
    bootstrap = memory_system.get_bootstrap_context()
    print(f"Bootstrap context: {len(bootstrap['user_preferences'])} preferences, "
          f"{len(bootstrap['workflows'])} workflows, "
          f"{len(bootstrap['project_context'])} project items")

    # 6. Cleanup
    print("\n--- Cleanup ---")
    stats = memory_system.cleanup()
    print(f"Cleanup stats: {stats}")

    # 7. Audit log
    print("\n--- Audit Log (last 5 entries) ---")
    for entry in memory_system.get_audit_log()[-5:]:
        print(f"  [{entry['action']}] {entry['details']}")

    # 8. Deletion (GDPR)
    print("\n--- Memory Deletion ---")
    count = memory_system.forget_all(reason="gdpr_erasure_request")
    print(f"Deleted {count} memories (GDPR right to erasure)")


if __name__ == "__main__":
    main()
