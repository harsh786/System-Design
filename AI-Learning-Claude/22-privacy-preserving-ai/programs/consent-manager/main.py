"""
Consent Management System Demo

Demonstrates:
1. Multi-dimensional consent (storage, embedding, RAG, training, third-party)
2. Consent enforcement (operations blocked without consent)
3. Consent withdrawal with cascade effects
4. Audit logging of all consent changes and enforcement decisions
"""

from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ─── Data Models ─────────────────────────────────────────────────────────────

class ConsentStatus(Enum):
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    REVOKED = "REVOKED"


class Operation(Enum):
    STORAGE = "storage"
    EMBEDDING = "embedding"
    RAG_RETRIEVAL = "rag_retrieval"
    AI_PROCESSING = "ai_processing"
    TRAINING = "training"
    THIRD_PARTY = "third_party"
    ANALYTICS = "analytics"


@dataclass
class ConsentRecord:
    user_id: str
    operation: Operation
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    provider: Optional[str] = None  # For third-party consent


@dataclass
class AuditEntry:
    timestamp: datetime
    user_id: str
    action: str
    operation: str
    result: str
    details: str = ""


# ─── Consent Store ───────────────────────────────────────────────────────────

class ConsentStore:
    def __init__(self):
        self.consents: Dict[str, Dict[str, ConsentRecord]] = {}
        self.audit_log: List[AuditEntry] = []

    def grant(self, user_id: str, operation: Operation,
              expires_at: datetime = None, provider: str = None):
        key = f"{operation.value}:{provider or 'any'}"
        record = ConsentRecord(
            user_id=user_id,
            operation=operation,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            provider=provider,
        )
        self.consents.setdefault(user_id, {})[key] = record
        self._audit(user_id, "GRANT", operation.value, "SUCCESS",
                    f"Consent granted for {operation.value}")

    def revoke(self, user_id: str, operation: Operation, provider: str = None):
        key = f"{operation.value}:{provider or 'any'}"
        if user_id in self.consents and key in self.consents[user_id]:
            self.consents[user_id][key].status = ConsentStatus.REVOKED
            self.consents[user_id][key].revoked_at = datetime.now(timezone.utc)
            self._audit(user_id, "REVOKE", operation.value, "SUCCESS",
                        f"Consent revoked for {operation.value}")
        else:
            self._audit(user_id, "REVOKE", operation.value, "NOT_FOUND",
                        "No existing consent to revoke")

    def check(self, user_id: str, operation: Operation, provider: str = None) -> bool:
        key = f"{operation.value}:{provider or 'any'}"
        record = self.consents.get(user_id, {}).get(key)

        if not record:
            return False
        if record.status != ConsentStatus.GRANTED:
            return False
        if record.expires_at and datetime.now(timezone.utc) > record.expires_at:
            record.status = ConsentStatus.REVOKED
            self._audit(user_id, "AUTO_EXPIRE", operation.value, "EXPIRED",
                        "Consent auto-expired")
            return False
        return True

    def get_user_consents(self, user_id: str) -> Dict[str, ConsentRecord]:
        return self.consents.get(user_id, {})

    def _audit(self, user_id: str, action: str, operation: str,
               result: str, details: str = ""):
        self.audit_log.append(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            action=action,
            operation=operation,
            result=result,
            details=details,
        ))


# ─── Consent Gate (Enforcement) ─────────────────────────────────────────────

class ConsentGate:
    def __init__(self, store: ConsentStore):
        self.store = store

    def enforce(self, user_id: str, operation: Operation,
                provider: str = None) -> bool:
        """Check consent and log the enforcement decision."""
        allowed = self.store.check(user_id, operation, provider)
        self.store._audit(
            user_id, "ENFORCE", operation.value,
            "ALLOWED" if allowed else "BLOCKED",
            f"Operation {'allowed' if allowed else 'BLOCKED'}: {operation.value}"
        )
        return allowed


# ─── Simulated AI Pipeline ───────────────────────────────────────────────────

class SimulatedAIPipeline:
    """Simulates AI operations that require consent checks."""

    def __init__(self, gate: ConsentGate):
        self.gate = gate
        self.stored_docs: Dict[str, List[str]] = {}
        self.embedded_docs: Dict[str, List[str]] = {}
        self.training_data: List[dict] = []

    def store_document(self, user_id: str, doc: str) -> str:
        if not self.gate.enforce(user_id, Operation.STORAGE):
            return f"BLOCKED: User {user_id} has not consented to data storage"
        self.stored_docs.setdefault(user_id, []).append(doc)
        return f"OK: Document stored for {user_id}"

    def embed_document(self, user_id: str, doc: str) -> str:
        if not self.gate.enforce(user_id, Operation.EMBEDDING):
            return f"BLOCKED: User {user_id} has not consented to embedding"
        self.embedded_docs.setdefault(user_id, []).append(doc)
        return f"OK: Document embedded for {user_id}"

    def rag_query(self, user_id: str, query: str) -> str:
        if not self.gate.enforce(user_id, Operation.RAG_RETRIEVAL):
            return f"BLOCKED: User {user_id} has not consented to RAG retrieval"
        if not self.gate.enforce(user_id, Operation.AI_PROCESSING):
            return f"BLOCKED: User {user_id} has not consented to AI processing"
        return f"OK: RAG query processed for {user_id}: '{query}'"

    def add_to_training(self, user_id: str, data: dict) -> str:
        if not self.gate.enforce(user_id, Operation.TRAINING):
            return f"BLOCKED: User {user_id} has not consented to training"
        self.training_data.append({"user_id": user_id, **data})
        return f"OK: Data added to training set from {user_id}"

    def send_to_provider(self, user_id: str, provider: str, data: str) -> str:
        if not self.gate.enforce(user_id, Operation.THIRD_PARTY, provider=provider):
            return f"BLOCKED: User {user_id} has not consented to {provider}"
        return f"OK: Data sent to {provider} for {user_id}"


# ─── Revocation Handler ─────────────────────────────────────────────────────

class RevocationHandler:
    """Handles cascade effects when consent is withdrawn."""

    def __init__(self, store: ConsentStore, pipeline: SimulatedAIPipeline):
        self.store = store
        self.pipeline = pipeline

    def handle_revocation(self, user_id: str, operation: Operation) -> List[str]:
        """Revoke consent and handle downstream effects."""
        effects = []

        self.store.revoke(user_id, operation)
        effects.append(f"Consent revoked: {operation.value}")

        if operation == Operation.EMBEDDING:
            # Must delete all vectors
            count = len(self.pipeline.embedded_docs.get(user_id, []))
            self.pipeline.embedded_docs.pop(user_id, None)
            effects.append(f"Deleted {count} embeddings from vector store")

        elif operation == Operation.TRAINING:
            # Must remove from training data
            before = len(self.pipeline.training_data)
            self.pipeline.training_data = [
                d for d in self.pipeline.training_data if d["user_id"] != user_id
            ]
            removed = before - len(self.pipeline.training_data)
            effects.append(f"Removed {removed} entries from training dataset")

        elif operation == Operation.STORAGE:
            # Nuclear option — delete everything
            doc_count = len(self.pipeline.stored_docs.get(user_id, []))
            emb_count = len(self.pipeline.embedded_docs.get(user_id, []))
            self.pipeline.stored_docs.pop(user_id, None)
            self.pipeline.embedded_docs.pop(user_id, None)
            self.pipeline.training_data = [
                d for d in self.pipeline.training_data if d["user_id"] != user_id
            ]
            effects.append(f"FULL CASCADE: Deleted {doc_count} documents")
            effects.append(f"FULL CASCADE: Deleted {emb_count} embeddings")
            effects.append(f"FULL CASCADE: Removed from training data")
            # Also revoke dependent consents
            for op in [Operation.EMBEDDING, Operation.RAG_RETRIEVAL,
                       Operation.AI_PROCESSING, Operation.TRAINING]:
                self.store.revoke(user_id, op)
            effects.append("FULL CASCADE: All dependent consents revoked")

        return effects


# ─── Main Demo ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("CONSENT MANAGEMENT SYSTEM DEMO")
    print("=" * 70)

    store = ConsentStore()
    gate = ConsentGate(store)
    pipeline = SimulatedAIPipeline(gate)
    revocation = RevocationHandler(store, pipeline)

    # ─── Setup Users with Different Consent Levels ───────────────────────

    print("\n--- SETTING UP USER CONSENT ---\n")

    # User A (Alice): Full consent
    print("User A (Alice): FULL consent")
    for op in Operation:
        store.grant("alice", op)
    print("  Granted: storage, embedding, rag, ai_processing, training, third_party, analytics")

    # User B (Bob): Partial consent
    print("\nUser B (Bob): PARTIAL consent")
    store.grant("bob", Operation.STORAGE)
    store.grant("bob", Operation.EMBEDDING)
    store.grant("bob", Operation.RAG_RETRIEVAL)
    store.grant("bob", Operation.AI_PROCESSING)
    store.grant("bob", Operation.ANALYTICS)
    # NOT: training, third_party
    print("  Granted: storage, embedding, rag, ai_processing, analytics")
    print("  DENIED: training, third_party")

    # User C (Carol): Minimal consent
    print("\nUser C (Carol): MINIMAL consent")
    store.grant("carol", Operation.STORAGE)
    store.grant("carol", Operation.ANALYTICS)
    # NOT: embedding, rag, ai_processing, training, third_party
    print("  Granted: storage, analytics")
    print("  DENIED: embedding, rag, ai_processing, training, third_party")

    # ─── Test Operations ─────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("TESTING OPERATIONS")
    print("=" * 70)

    users = ["alice", "bob", "carol"]
    operations = [
        ("Store document", lambda u: pipeline.store_document(u, "Test document content")),
        ("Embed document", lambda u: pipeline.embed_document(u, "Test document content")),
        ("RAG query", lambda u: pipeline.rag_query(u, "What is the policy?")),
        ("Add to training", lambda u: pipeline.add_to_training(u, {"text": "example"})),
        ("Send to OpenAI", lambda u: pipeline.send_to_provider(u, "openai", "data")),
    ]

    print(f"\n{'Operation':<20} {'Alice':<30} {'Bob':<30} {'Carol':<30}")
    print("─" * 110)

    for op_name, op_func in operations:
        results = []
        for user in users:
            result = op_func(user)
            status = "✓ ALLOWED" if result.startswith("OK") else "✗ BLOCKED"
            results.append(status)
        print(f"{op_name:<20} {results[0]:<30} {results[1]:<30} {results[2]:<30}")

    # ─── Consent Withdrawal Demo ─────────────────────────────────────────

    print("\n" + "=" * 70)
    print("CONSENT WITHDRAWAL — CASCADE EFFECTS")
    print("=" * 70)

    # First, add some data for Bob
    pipeline.store_document("bob", "Bob's important document 1")
    pipeline.store_document("bob", "Bob's important document 2")
    pipeline.embed_document("bob", "Bob's important document 1")
    pipeline.embed_document("bob", "Bob's important document 2")

    print(f"\nBob's data before revocation:")
    print(f"  Stored documents: {len(pipeline.stored_docs.get('bob', []))}")
    print(f"  Embedded documents: {len(pipeline.embedded_docs.get('bob', []))}")

    # Bob revokes embedding consent
    print(f"\n--- Bob revokes EMBEDDING consent ---")
    effects = revocation.handle_revocation("bob", Operation.EMBEDDING)
    for effect in effects:
        print(f"  → {effect}")

    print(f"\nBob's data after embedding revocation:")
    print(f"  Stored documents: {len(pipeline.stored_docs.get('bob', []))}")
    print(f"  Embedded documents: {len(pipeline.embedded_docs.get('bob', []))}")

    # Now Bob tries to embed again — should be blocked
    print(f"\n  Bob tries to embed again:")
    result = pipeline.embed_document("bob", "New document")
    print(f"    {result}")

    # Alice revokes STORAGE (nuclear option)
    print(f"\n--- Alice revokes STORAGE consent (NUCLEAR) ---")
    pipeline.store_document("alice", "Alice doc 1")
    pipeline.store_document("alice", "Alice doc 2")
    pipeline.embed_document("alice", "Alice doc 1")
    pipeline.add_to_training("alice", {"text": "alice training example"})

    print(f"\nAlice's data before revocation:")
    print(f"  Stored documents: {len(pipeline.stored_docs.get('alice', []))}")
    print(f"  Embedded documents: {len(pipeline.embedded_docs.get('alice', []))}")
    print(f"  Training entries: {len([d for d in pipeline.training_data if d['user_id'] == 'alice'])}")

    effects = revocation.handle_revocation("alice", Operation.STORAGE)
    for effect in effects:
        print(f"  → {effect}")

    print(f"\nAlice's data AFTER storage revocation:")
    print(f"  Stored documents: {len(pipeline.stored_docs.get('alice', []))}")
    print(f"  Embedded documents: {len(pipeline.embedded_docs.get('alice', []))}")
    print(f"  Training entries: {len([d for d in pipeline.training_data if d['user_id'] == 'alice'])}")

    # ─── Audit Log ───────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("CONSENT AUDIT LOG (last 20 entries)")
    print("=" * 70)
    print(f"\n{'Timestamp':<12} {'User':<8} {'Action':<12} {'Operation':<15} {'Result':<10} {'Details'}")
    print("─" * 100)

    for entry in store.audit_log[-20:]:
        ts = entry.timestamp.strftime("%H:%M:%S")
        print(f"{ts:<12} {entry.user_id:<8} {entry.action:<12} "
              f"{entry.operation:<15} {entry.result:<10} {entry.details[:40]}")

    # ─── Final Consent State ─────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("FINAL CONSENT STATE")
    print("=" * 70)

    for user in users:
        print(f"\n  {user.upper()}:")
        consents = store.get_user_consents(user)
        for key, record in consents.items():
            status_icon = "✓" if record.status == ConsentStatus.GRANTED else "✗"
            print(f"    {status_icon} {record.operation.value}: {record.status.value}")

    print(f"\n  Total audit entries: {len(store.audit_log)}")


if __name__ == "__main__":
    main()
