"""
Right-to-Delete Implementation for AI Systems
===============================================
Comprehensive deletion across all AI components: databases, vector indexes,
memory systems, logs, traces, caches, eval datasets, and vendor systems.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DELETION REQUEST MANAGEMENT
# =============================================================================

class DeletionStatus(Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    DISCOVERING = "discovering"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class DeletionScope(Enum):
    ALL_DATA = "all_data"                     # Complete account deletion
    CONVERSATIONS = "conversations"           # Chat history only
    MEMORIES = "memories"                     # Agent memories only
    DOCUMENTS = "documents"                   # Uploaded documents/embeddings
    SPECIFIC_CONVERSATION = "specific_conv"   # Single conversation
    ANALYTICS = "analytics"                   # Analytics data
    TRAINING_DATA = "training_data"           # Data used for training


@dataclass
class DeletionRequest:
    request_id: str
    user_id: str
    scope: DeletionScope
    status: DeletionStatus
    requested_at: datetime
    requested_by: str  # user, admin, automated
    reason: str = ""
    scope_filter: dict = field(default_factory=dict)  # Additional filters
    discovery_results: dict = field(default_factory=dict)
    deletion_results: dict = field(default_factory=dict)
    verification_results: dict = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None  # Regulatory deadline (e.g., 30 days GDPR)


class DeletionRequestManager:
    """Manages the lifecycle of deletion requests."""

    def __init__(self, deadline_days: int = 30):
        self._requests: dict[str, DeletionRequest] = {}
        self._deadline_days = deadline_days

    def create_request(
        self,
        user_id: str,
        scope: DeletionScope,
        requested_by: str = "user",
        reason: str = "",
        scope_filter: Optional[dict] = None,
    ) -> DeletionRequest:
        """Create a new deletion request."""
        request = DeletionRequest(
            request_id=str(uuid.uuid4()),
            user_id=user_id,
            scope=scope,
            status=DeletionStatus.RECEIVED,
            requested_at=datetime.utcnow(),
            requested_by=requested_by,
            reason=reason,
            scope_filter=scope_filter or {},
            deadline=datetime.utcnow() + timedelta(days=self._deadline_days),
        )
        self._requests[request.request_id] = request
        logger.info(f"Deletion request created: {request.request_id} for user {user_id}")
        return request

    def validate_request(self, request_id: str, authenticated: bool) -> bool:
        """Validate the deletion request (authentication, authorization)."""
        request = self._requests.get(request_id)
        if not request:
            return False
        if not authenticated:
            request.status = DeletionStatus.FAILED
            return False
        request.status = DeletionStatus.VALIDATED
        return True

    def get_request(self, request_id: str) -> Optional[DeletionRequest]:
        return self._requests.get(request_id)

    def get_overdue_requests(self) -> list[DeletionRequest]:
        """Find requests past their deadline."""
        now = datetime.utcnow()
        return [
            r for r in self._requests.values()
            if r.deadline and now > r.deadline and r.status not in (
                DeletionStatus.COMPLETED, DeletionStatus.FAILED
            )
        ]


# =============================================================================
# DATA INVENTORY DISCOVERY
# =============================================================================

class DataStore(ABC):
    """Abstract base for any system that may hold user data."""

    @property
    @abstractmethod
    def store_name(self) -> str:
        pass

    @abstractmethod
    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        """Find all data belonging to a user in this store."""
        pass

    @abstractmethod
    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        """Delete user data from this store."""
        pass

    @abstractmethod
    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        """Verify that user data has been deleted."""
        pass


class ConversationStore(DataStore):
    """Conversation/chat history storage."""

    @property
    def store_name(self) -> str:
        return "conversation_store"

    def __init__(self):
        self._conversations: dict[str, list[dict]] = {}  # user_id -> conversations

    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        conversations = self._conversations.get(user_id, [])
        return {
            "store": self.store_name,
            "item_count": len(conversations),
            "items": [{"id": c.get("id"), "created_at": c.get("created_at")} for c in conversations],
            "estimated_size_bytes": sum(len(json.dumps(c)) for c in conversations),
        }

    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        count = len(self._conversations.get(user_id, []))
        self._conversations.pop(user_id, None)
        return {"store": self.store_name, "deleted_count": count, "success": True}

    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        remaining = self._conversations.get(user_id, [])
        return {
            "store": self.store_name,
            "verified": len(remaining) == 0,
            "remaining_items": len(remaining),
        }


class VectorIndexStore(DataStore):
    """Vector database / embedding storage."""

    @property
    def store_name(self) -> str:
        return "vector_index"

    def __init__(self):
        self._embeddings: dict[str, list[dict]] = {}  # user_id -> embeddings
        self._reindex_queue: list[str] = []

    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        embeddings = self._embeddings.get(user_id, [])
        return {
            "store": self.store_name,
            "item_count": len(embeddings),
            "items": [{"id": e.get("id"), "source_doc": e.get("source")} for e in embeddings],
            "note": "Deletion requires re-indexing affected collections",
        }

    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        count = len(self._embeddings.get(user_id, []))
        # In real implementation: delete vectors by ID from vector DB
        # Then trigger re-indexing of affected collections
        self._embeddings.pop(user_id, None)
        self._reindex_queue.append(user_id)
        return {
            "store": self.store_name,
            "deleted_count": count,
            "success": True,
            "reindex_queued": True,
        }

    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        remaining = self._embeddings.get(user_id, [])
        # In real implementation: query vector DB for any vectors with user's metadata
        return {
            "store": self.store_name,
            "verified": len(remaining) == 0,
            "remaining_items": len(remaining),
        }


class MemoryStore(DataStore):
    """Agent memory system."""

    @property
    def store_name(self) -> str:
        return "memory_store"

    def __init__(self):
        self._memories: dict[str, list[dict]] = {}  # user_id -> memories
        self._shared_memories: list[dict] = []  # memories referencing multiple users

    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        direct_memories = self._memories.get(user_id, [])
        shared = [m for m in self._shared_memories if user_id in m.get("users", [])]
        return {
            "store": self.store_name,
            "direct_memories": len(direct_memories),
            "shared_memories": len(shared),
            "items": {
                "direct": [{"id": m.get("id"), "type": m.get("type")} for m in direct_memories],
                "shared": [{"id": m.get("id"), "users": m.get("users")} for m in shared],
            },
            "note": "Shared memories will be redacted, not fully deleted",
        }

    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        # Delete direct memories
        direct_count = len(self._memories.get(user_id, []))
        self._memories.pop(user_id, None)

        # Redact user from shared memories
        shared_redacted = 0
        for memory in self._shared_memories:
            if user_id in memory.get("users", []):
                memory["users"].remove(user_id)
                memory["content"] = memory.get("content", "").replace(user_id, "[DELETED_USER]")
                shared_redacted += 1

        return {
            "store": self.store_name,
            "direct_deleted": direct_count,
            "shared_redacted": shared_redacted,
            "success": True,
        }

    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        direct = self._memories.get(user_id, [])
        shared_refs = [m for m in self._shared_memories if user_id in m.get("users", [])]
        return {
            "store": self.store_name,
            "verified": len(direct) == 0 and len(shared_refs) == 0,
            "remaining_direct": len(direct),
            "remaining_shared_refs": len(shared_refs),
        }


class LogStore(DataStore):
    """Application logs and observability traces."""

    @property
    def store_name(self) -> str:
        return "log_store"

    def __init__(self):
        self._logs: list[dict] = []

    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        user_logs = [l for l in self._logs if user_id in json.dumps(l)]
        return {
            "store": self.store_name,
            "item_count": len(user_logs),
            "note": "Logs will be redacted in place (user ID replaced with hash)",
            "log_systems": ["application_logs", "access_logs", "trace_spans"],
        }

    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        # Redact user data from logs (don't delete log entries, redact PII)
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:12]
        redacted_count = 0
        for log_entry in self._logs:
            log_str = json.dumps(log_entry)
            if user_id in log_str:
                # In real implementation: update log entries in place
                redacted_count += 1

        return {
            "store": self.store_name,
            "redacted_count": redacted_count,
            "replacement": f"[DELETED:{user_hash}]",
            "success": True,
            "note": "Log structure preserved, PII redacted",
        }

    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        remaining = [l for l in self._logs if user_id in json.dumps(l)]
        return {
            "store": self.store_name,
            "verified": len(remaining) == 0,
            "remaining_references": len(remaining),
        }


class EvalDatasetStore(DataStore):
    """Evaluation datasets that may contain user data."""

    @property
    def store_name(self) -> str:
        return "eval_dataset_store"

    def __init__(self):
        self._datasets: dict[str, list[dict]] = {}  # dataset_id -> entries
        self._provenance: dict[str, list[str]] = {}  # entry_id -> [user_ids]

    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        affected_entries = []
        for dataset_id, entries in self._datasets.items():
            for entry in entries:
                entry_id = entry.get("id", "")
                if user_id in self._provenance.get(entry_id, []):
                    affected_entries.append({
                        "dataset_id": dataset_id,
                        "entry_id": entry_id,
                    })
        return {
            "store": self.store_name,
            "affected_entries": len(affected_entries),
            "affected_datasets": list({e["dataset_id"] for e in affected_entries}),
            "items": affected_entries,
        }

    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        removed = 0
        for item in discovery.get("items", []):
            dataset_id = item["dataset_id"]
            entry_id = item["entry_id"]
            if dataset_id in self._datasets:
                self._datasets[dataset_id] = [
                    e for e in self._datasets[dataset_id] if e.get("id") != entry_id
                ]
                removed += 1
        return {
            "store": self.store_name,
            "entries_removed": removed,
            "success": True,
            "note": "Eval datasets may need re-validation after removal",
        }

    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        remaining = []
        for dataset_id, entries in self._datasets.items():
            for entry in entries:
                if user_id in self._provenance.get(entry.get("id", ""), []):
                    remaining.append(entry.get("id"))
        return {
            "store": self.store_name,
            "verified": len(remaining) == 0,
            "remaining_entries": len(remaining),
        }


class CacheStore(DataStore):
    """Distributed caches (Redis, CDN, application caches)."""

    @property
    def store_name(self) -> str:
        return "cache_store"

    def __init__(self):
        self._caches: dict[str, dict] = {}  # cache_name -> {key: value}

    async def discover_user_data(self, user_id: str, scope: DeletionScope) -> dict:
        affected_keys = []
        for cache_name, cache_data in self._caches.items():
            for key in cache_data:
                if user_id in key:
                    affected_keys.append({"cache": cache_name, "key": key})
        return {
            "store": self.store_name,
            "affected_keys": len(affected_keys),
            "items": affected_keys,
            "cache_systems": list(self._caches.keys()),
        }

    async def delete_user_data(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        invalidated = 0
        for item in discovery.get("items", []):
            cache_name = item["cache"]
            key = item["key"]
            if cache_name in self._caches and key in self._caches[cache_name]:
                del self._caches[cache_name][key]
                invalidated += 1
        return {
            "store": self.store_name,
            "invalidated_keys": invalidated,
            "success": True,
        }

    async def verify_deletion(self, user_id: str, scope: DeletionScope) -> dict:
        remaining = 0
        for cache_data in self._caches.values():
            for key in cache_data:
                if user_id in key:
                    remaining += 1
        return {"store": self.store_name, "verified": remaining == 0, "remaining_keys": remaining}


# =============================================================================
# DELETION ORCHESTRATOR
# =============================================================================

@dataclass
class DeletionPlan:
    """Ordered plan for executing deletion across systems."""
    request_id: str
    steps: list[dict]  # Ordered deletion steps
    dependencies: dict[str, list[str]]  # step -> depends_on
    estimated_duration_seconds: int = 0


class DeletionOrchestrator:
    """Orchestrates deletion across all data stores."""

    def __init__(self):
        self._stores: list[DataStore] = []
        self._request_manager = DeletionRequestManager()
        self._audit_log: list[dict] = []

    def register_store(self, store: DataStore):
        """Register a data store for deletion processing."""
        self._stores.append(store)

    async def process_deletion(self, request: DeletionRequest) -> DeletionRequest:
        """Execute full deletion workflow."""
        try:
            # Phase 1: Discovery
            request.status = DeletionStatus.DISCOVERING
            self._audit("discovery_started", request)
            
            discovery = await self._discover_all(request.user_id, request.scope)
            request.discovery_results = discovery
            self._audit("discovery_completed", request, details={"stores_found": len(discovery)})

            # Phase 2: Deletion
            request.status = DeletionStatus.IN_PROGRESS
            self._audit("deletion_started", request)
            
            results = await self._delete_all(request.user_id, request.scope, discovery)
            request.deletion_results = results
            self._audit("deletion_executed", request)

            # Phase 3: Verification
            request.status = DeletionStatus.VERIFYING
            verification = await self._verify_all(request.user_id, request.scope)
            request.verification_results = verification

            # Determine final status
            all_verified = all(v.get("verified", False) for v in verification.values())
            if all_verified:
                request.status = DeletionStatus.COMPLETED
                request.completed_at = datetime.utcnow()
                self._audit("deletion_completed", request)
            else:
                request.status = DeletionStatus.PARTIALLY_COMPLETED
                self._audit("deletion_partial", request, details={"verification": verification})

        except Exception as e:
            request.status = DeletionStatus.FAILED
            self._audit("deletion_failed", request, details={"error": str(e)})
            raise

        return request

    async def _discover_all(self, user_id: str, scope: DeletionScope) -> dict:
        """Discover user data across all stores."""
        discovery = {}
        tasks = [store.discover_user_data(user_id, scope) for store in self._stores]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for store, result in zip(self._stores, results):
            if isinstance(result, Exception):
                discovery[store.store_name] = {"error": str(result)}
            else:
                discovery[store.store_name] = result

        return discovery

    async def _delete_all(self, user_id: str, scope: DeletionScope, discovery: dict) -> dict:
        """Execute deletion across all stores."""
        results = {}
        # Execute in order: caches first, then primary stores, then logs
        priority_order = ["cache_store", "conversation_store", "memory_store",
                         "vector_index", "eval_dataset_store", "log_store"]

        for store_name in priority_order:
            store = next((s for s in self._stores if s.store_name == store_name), None)
            if store and store_name in discovery:
                try:
                    result = await store.delete_user_data(user_id, scope, discovery[store_name])
                    results[store_name] = result
                except Exception as e:
                    results[store_name] = {"success": False, "error": str(e)}

        # Handle any stores not in priority order
        for store in self._stores:
            if store.store_name not in results and store.store_name in discovery:
                try:
                    result = await store.delete_user_data(user_id, scope, discovery[store.store_name])
                    results[store.store_name] = result
                except Exception as e:
                    results[store.store_name] = {"success": False, "error": str(e)}

        return results

    async def _verify_all(self, user_id: str, scope: DeletionScope) -> dict:
        """Verify deletion across all stores."""
        verification = {}
        tasks = [store.verify_deletion(user_id, scope) for store in self._stores]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for store, result in zip(self._stores, results):
            if isinstance(result, Exception):
                verification[store.store_name] = {"verified": False, "error": str(result)}
            else:
                verification[store.store_name] = result

        return verification

    def _audit(self, action: str, request: DeletionRequest, details: Optional[dict] = None):
        """Record audit trail entry (never includes the deleted data itself)."""
        self._audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "request_id": request.request_id,
            "user_id_hash": hashlib.sha256(request.user_id.encode()).hexdigest()[:16],
            "scope": request.scope.value,
            "status": request.status.value,
            "details": details or {},
        })

    def generate_deletion_certificate(self, request: DeletionRequest) -> dict:
        """Generate a certificate proving deletion was completed."""
        return {
            "certificate_id": str(uuid.uuid4()),
            "request_id": request.request_id,
            "user_id_hash": hashlib.sha256(request.user_id.encode()).hexdigest(),
            "scope": request.scope.value,
            "requested_at": request.requested_at.isoformat(),
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "status": request.status.value,
            "stores_processed": list(request.deletion_results.keys()),
            "verification_passed": all(
                v.get("verified", False)
                for v in request.verification_results.values()
            ),
            "issued_at": datetime.utcnow().isoformat(),
        }

    def get_audit_trail(self, request_id: str) -> list[dict]:
        """Get audit trail for a specific deletion request."""
        return [e for e in self._audit_log if e["request_id"] == request_id]


# =============================================================================
# CASCADING DELETION
# =============================================================================

class CascadingDeletionEngine:
    """Handles cascading deletion across dependent systems."""

    def __init__(self):
        self._dependencies: dict[str, list[str]] = {}  # system -> depends_on

    def register_dependency(self, system: str, depends_on: str):
        """Register that one system's deletion depends on another."""
        if system not in self._dependencies:
            self._dependencies[system] = []
        self._dependencies[system].append(depends_on)

    def get_deletion_order(self) -> list[list[str]]:
        """Get deletion order respecting dependencies (topological sort)."""
        # Kahn's algorithm for topological sort
        in_degree: dict[str, int] = {}
        all_nodes = set()

        for node, deps in self._dependencies.items():
            all_nodes.add(node)
            all_nodes.update(deps)

        for node in all_nodes:
            in_degree[node] = 0

        for node, deps in self._dependencies.items():
            in_degree[node] = len(deps)

        # Start with nodes that have no dependencies
        queue = [n for n in all_nodes if in_degree[n] == 0]
        levels = []

        while queue:
            levels.append(sorted(queue))
            next_queue = []
            for node in queue:
                for dependent, deps in self._dependencies.items():
                    if node in deps:
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            next_queue.append(dependent)
            queue = next_queue

        return levels


# =============================================================================
# SCHEDULED DELETION (RETENTION ENFORCEMENT)
# =============================================================================

class RetentionEnforcer:
    """Automatically deletes data past its retention period."""

    def __init__(self, orchestrator: DeletionOrchestrator):
        self._orchestrator = orchestrator
        self._policies: dict[str, int] = {}  # data_type -> retention_days

    def set_policy(self, data_type: str, retention_days: int):
        """Set retention policy for a data type."""
        self._policies[data_type] = retention_days

    async def enforce(self) -> list[dict]:
        """Run retention enforcement. Returns list of actions taken."""
        actions = []
        # In real implementation: query each store for expired data
        # and create deletion requests for them
        logger.info(f"Retention enforcement running with {len(self._policies)} policies")
        return actions


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def main():
    """Demonstrate right-to-delete workflow."""
    print("=" * 70)
    print("RIGHT-TO-DELETE WORKFLOW DEMONSTRATION")
    print("=" * 70)

    # Set up orchestrator with all stores
    orchestrator = DeletionOrchestrator()
    orchestrator.register_store(ConversationStore())
    orchestrator.register_store(VectorIndexStore())
    orchestrator.register_store(MemoryStore())
    orchestrator.register_store(LogStore())
    orchestrator.register_store(EvalDatasetStore())
    orchestrator.register_store(CacheStore())

    # Create deletion request
    request_mgr = DeletionRequestManager()
    request = request_mgr.create_request(
        user_id="user-12345",
        scope=DeletionScope.ALL_DATA,
        requested_by="user",
        reason="Account deletion request via settings page",
    )
    print(f"\n1. Request created: {request.request_id}")
    print(f"   Scope: {request.scope.value}")
    print(f"   Deadline: {request.deadline}")

    # Validate
    request_mgr.validate_request(request.request_id, authenticated=True)
    print(f"\n2. Request validated")

    # Process deletion
    print(f"\n3. Processing deletion...")
    result = await orchestrator.process_deletion(request)

    print(f"\n4. Results:")
    print(f"   Status: {result.status.value}")
    print(f"   Discovery: {len(result.discovery_results)} stores checked")
    print(f"   Deletion: {len(result.deletion_results)} stores processed")
    print(f"   Verification: all passed = {all(v.get('verified', False) for v in result.verification_results.values())}")

    # Generate certificate
    cert = orchestrator.generate_deletion_certificate(result)
    print(f"\n5. Deletion Certificate:")
    print(f"   Certificate ID: {cert['certificate_id']}")
    print(f"   Verification passed: {cert['verification_passed']}")

    # Audit trail
    trail = orchestrator.get_audit_trail(request.request_id)
    print(f"\n6. Audit Trail ({len(trail)} entries):")
    for entry in trail:
        print(f"   [{entry['timestamp']}] {entry['action']} - {entry['status']}")

    # Cascading deletion order
    print(f"\n7. Cascading Deletion Order:")
    cascade = CascadingDeletionEngine()
    cascade.register_dependency("vector_index", "conversation_store")
    cascade.register_dependency("cache_store", "conversation_store")
    cascade.register_dependency("log_store", "memory_store")
    cascade.register_dependency("eval_dataset_store", "conversation_store")

    order = cascade.get_deletion_order()
    for level_idx, level in enumerate(order):
        print(f"   Level {level_idx}: {', '.join(level)}")


if __name__ == "__main__":
    asyncio.run(main())
