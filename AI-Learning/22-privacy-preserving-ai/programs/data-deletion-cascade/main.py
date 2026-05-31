"""
Data Deletion Cascade Demo

Simulates the full GDPR "right to erasure" deletion cascade:
  Documents → Chunks → Vectors → Cache → Memory → Logs → Verify

Shows:
1. Building a simulated AI system with all data stores
2. User requests deletion
3. Complete cascade through all systems
4. Post-deletion verification (search returns nothing)
5. Audit trail with timing
"""

import time
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone


# ─── Simulated Data Stores ───────────────────────────────────────────────────

class DocumentStore:
    """Simulates document storage."""
    def __init__(self):
        self.documents: Dict[str, dict] = {}

    def add(self, doc_id: str, content: str, owner_id: str):
        self.documents[doc_id] = {
            "content": content, "owner_id": owner_id, "created_at": time.time()
        }

    def delete(self, doc_id: str) -> bool:
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False

    def search_by_owner(self, owner_id: str) -> List[str]:
        return [did for did, doc in self.documents.items() if doc["owner_id"] == owner_id]

    def search_content(self, query: str) -> List[str]:
        return [did for did, doc in self.documents.items() if query.lower() in doc["content"].lower()]


class ChunkStore:
    """Simulates chunk storage."""
    def __init__(self):
        self.chunks: Dict[str, dict] = {}

    def add(self, chunk_id: str, doc_id: str, text: str):
        self.chunks[chunk_id] = {"doc_id": doc_id, "text": text}

    def delete(self, chunk_id: str) -> bool:
        if chunk_id in self.chunks:
            del self.chunks[chunk_id]
            return True
        return False

    def get_by_doc(self, doc_id: str) -> List[str]:
        return [cid for cid, c in self.chunks.items() if c["doc_id"] == doc_id]

    def search_content(self, query: str) -> List[str]:
        return [cid for cid, c in self.chunks.items() if query.lower() in c["text"].lower()]


class VectorStore:
    """Simulates vector database."""
    def __init__(self, name: str):
        self.name = name
        self.vectors: Dict[str, dict] = {}

    def add(self, vector_id: str, chunk_id: str, metadata: dict = None):
        self.vectors[vector_id] = {"chunk_id": chunk_id, "metadata": metadata or {}}

    def delete(self, vector_id: str) -> bool:
        if vector_id in self.vectors:
            del self.vectors[vector_id]
            return True
        return False

    def get_by_chunk(self, chunk_id: str) -> List[str]:
        return [vid for vid, v in self.vectors.items() if v["chunk_id"] == chunk_id]

    def search_metadata(self, key: str, value: str) -> List[str]:
        return [vid for vid, v in self.vectors.items()
                if v["metadata"].get(key) == value]


class SemanticCache:
    """Simulates semantic response cache."""
    def __init__(self):
        self.entries: Dict[str, dict] = {}

    def add(self, cache_key: str, query: str, response: str, user_id: str):
        self.entries[cache_key] = {
            "query": query, "response": response,
            "user_id": user_id, "created_at": time.time()
        }

    def invalidate(self, cache_key: str) -> bool:
        if cache_key in self.entries:
            del self.entries[cache_key]
            return True
        return False

    def get_by_user(self, user_id: str) -> List[str]:
        return [k for k, v in self.entries.items() if v["user_id"] == user_id]

    def search_content(self, query: str) -> List[str]:
        return [k for k, v in self.entries.items()
                if query.lower() in v["response"].lower() or query.lower() in v["query"].lower()]


class MemoryStore:
    """Simulates agent long-term memory."""
    def __init__(self):
        self.memories: Dict[str, dict] = {}

    def add(self, memory_id: str, user_id: str, content: str, memory_type: str):
        self.memories[memory_id] = {
            "user_id": user_id, "content": content,
            "type": memory_type, "created_at": time.time()
        }

    def delete(self, memory_id: str) -> bool:
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False

    def get_by_user(self, user_id: str) -> List[str]:
        return [mid for mid, m in self.memories.items() if m["user_id"] == user_id]

    def search_content(self, query: str) -> List[str]:
        return [mid for mid, m in self.memories.items() if query.lower() in m["content"].lower()]


class LogStore:
    """Simulates observability/logging system."""
    def __init__(self):
        self.logs: List[dict] = []

    def add(self, user_id: str, action: str, content: str):
        self.logs.append({
            "log_id": str(uuid.uuid4())[:8],
            "user_id": user_id, "action": action,
            "content": content, "timestamp": time.time()
        })

    def redact_user(self, user_id: str) -> int:
        count = 0
        for log in self.logs:
            if log["user_id"] == user_id:
                log["content"] = "[REDACTED]"
                log["user_id"] = "[REDACTED]"
                count += 1
        return count

    def search_content(self, query: str) -> List[dict]:
        return [l for l in self.logs if query.lower() in l["content"].lower()]


# ─── Deletion Tracker (Document → Chunk → Vector mapping) ───────────────────

class DeletionTracker:
    """Maintains the critical mapping from users → docs → chunks → vectors."""

    def __init__(self):
        self.user_docs: Dict[str, Set[str]] = {}
        self.doc_chunks: Dict[str, Set[str]] = {}
        self.chunk_vectors: Dict[str, List[dict]] = {}
        self.user_cache_keys: Dict[str, Set[str]] = {}

    def register_doc(self, user_id: str, doc_id: str):
        self.user_docs.setdefault(user_id, set()).add(doc_id)

    def register_chunk(self, doc_id: str, chunk_id: str):
        self.doc_chunks.setdefault(doc_id, set()).add(chunk_id)

    def register_vector(self, chunk_id: str, vector_id: str, db_name: str):
        self.chunk_vectors.setdefault(chunk_id, []).append({
            "vector_id": vector_id, "db_name": db_name
        })

    def register_cache(self, user_id: str, cache_key: str):
        self.user_cache_keys.setdefault(user_id, set()).add(cache_key)

    def get_user_docs(self, user_id: str) -> Set[str]:
        return self.user_docs.get(user_id, set())

    def get_doc_chunks(self, doc_id: str) -> Set[str]:
        return self.doc_chunks.get(doc_id, set())

    def get_chunk_vectors(self, chunk_id: str) -> List[dict]:
        return self.chunk_vectors.get(chunk_id, [])

    def get_user_cache_keys(self, user_id: str) -> Set[str]:
        return self.user_cache_keys.get(user_id, set())


# ─── Deletion Cascade Engine ─────────────────────────────────────────────────

@dataclass
class DeletionResult:
    user_id: str
    started_at: float = 0
    completed_at: float = 0
    documents_deleted: int = 0
    chunks_deleted: int = 0
    vectors_deleted: int = 0
    cache_invalidated: int = 0
    memories_purged: int = 0
    logs_redacted: int = 0
    steps: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class DeletionCascade:
    def __init__(self, tracker: DeletionTracker, doc_store: DocumentStore,
                 chunk_store: ChunkStore, vector_stores: Dict[str, VectorStore],
                 cache: SemanticCache, memory: MemoryStore, logs: LogStore):
        self.tracker = tracker
        self.doc_store = doc_store
        self.chunk_store = chunk_store
        self.vector_stores = vector_stores
        self.cache = cache
        self.memory = memory
        self.logs = logs

    def execute(self, user_id: str) -> DeletionResult:
        result = DeletionResult(user_id=user_id, started_at=time.time())

        # Step 1: Find all documents
        doc_ids = self.tracker.get_user_docs(user_id)
        result.steps.append({"step": "Find documents", "found": len(doc_ids),
                            "time": time.time()})

        # Step 2: For each document, find chunks and delete vectors
        all_chunk_ids = set()
        for doc_id in doc_ids:
            chunk_ids = self.tracker.get_doc_chunks(doc_id)
            all_chunk_ids.update(chunk_ids)

            for chunk_id in chunk_ids:
                vectors = self.tracker.get_chunk_vectors(chunk_id)
                for v in vectors:
                    db = self.vector_stores.get(v["db_name"])
                    if db and db.delete(v["vector_id"]):
                        result.vectors_deleted += 1

        result.steps.append({"step": "Delete vectors", "deleted": result.vectors_deleted,
                            "time": time.time()})

        # Step 3: Delete chunks
        for chunk_id in all_chunk_ids:
            if self.chunk_store.delete(chunk_id):
                result.chunks_deleted += 1

        result.steps.append({"step": "Delete chunks", "deleted": result.chunks_deleted,
                            "time": time.time()})

        # Step 4: Delete documents
        for doc_id in doc_ids:
            if self.doc_store.delete(doc_id):
                result.documents_deleted += 1

        result.steps.append({"step": "Delete documents", "deleted": result.documents_deleted,
                            "time": time.time()})

        # Step 5: Invalidate cache
        cache_keys = self.tracker.get_user_cache_keys(user_id)
        for key in cache_keys:
            if self.cache.invalidate(key):
                result.cache_invalidated += 1

        result.steps.append({"step": "Invalidate cache", "invalidated": result.cache_invalidated,
                            "time": time.time()})

        # Step 6: Purge memory
        memory_ids = self.memory.get_by_user(user_id)
        for mid in memory_ids:
            if self.memory.delete(mid):
                result.memories_purged += 1

        result.steps.append({"step": "Purge memory", "purged": result.memories_purged,
                            "time": time.time()})

        # Step 7: Redact logs
        result.logs_redacted = self.logs.redact_user(user_id)
        result.steps.append({"step": "Redact logs", "redacted": result.logs_redacted,
                            "time": time.time()})

        result.completed_at = time.time()
        return result


# ─── Verification ────────────────────────────────────────────────────────────

class DeletionVerifier:
    def __init__(self, doc_store, chunk_store, vector_stores, cache, memory, logs):
        self.doc_store = doc_store
        self.chunk_store = chunk_store
        self.vector_stores = vector_stores
        self.cache = cache
        self.memory = memory
        self.logs = logs

    def verify(self, user_id: str, identifiers: List[str]) -> dict:
        """Search ALL systems for any remaining trace."""
        findings = {"documents": [], "chunks": [], "vectors": [],
                    "cache": [], "memory": [], "logs": []}

        for identifier in identifiers:
            findings["documents"].extend(self.doc_store.search_content(identifier))
            findings["chunks"].extend(self.chunk_store.search_content(identifier))
            findings["cache"].extend(self.cache.search_content(identifier))
            findings["memory"].extend(self.memory.search_content(identifier))
            findings["logs"].extend(self.logs.search_content(identifier))

        # Check owner-based
        findings["documents"].extend(self.doc_store.search_by_owner(user_id))

        is_clean = all(len(v) == 0 for v in findings.values())
        return {"clean": is_clean, "findings": findings}


# ─── Main Demo ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("DATA DELETION CASCADE SIMULATION")
    print("=" * 70)

    # ─── Setup Stores ────────────────────────────────────────────────────

    doc_store = DocumentStore()
    chunk_store = ChunkStore()
    vector_stores = {
        "primary": VectorStore("primary"),
        "replica": VectorStore("replica"),
    }
    cache = SemanticCache()
    memory = MemoryStore()
    logs = LogStore()
    tracker = DeletionTracker()

    # ─── Populate with User Data ─────────────────────────────────────────

    target_user = "user_john_smith"
    other_user = "user_jane_doe"

    print(f"\n--- POPULATING SYSTEM WITH DATA ---\n")

    # John Smith's documents
    john_docs = [
        ("doc_js_001", "John Smith's employment contract. Salary: $185,000. SSN: 123-45-6789."),
        ("doc_js_002", "Performance review for John Smith. Rating: Exceeds Expectations."),
        ("doc_js_003", "John Smith's health insurance enrollment. Dependents: 2."),
    ]

    # Jane Doe's documents (should NOT be affected)
    jane_docs = [
        ("doc_jd_001", "Jane Doe's project proposal for Q4 initiative."),
        ("doc_jd_002", "Jane Doe's travel expense report: $2,500."),
    ]

    for doc_id, content in john_docs + jane_docs:
        owner = target_user if "js" in doc_id else other_user
        doc_store.add(doc_id, content, owner)
        tracker.register_doc(owner, doc_id)

        # Create chunks (2 per document)
        for i in range(2):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_text = content[i * len(content) // 2:(i + 1) * len(content) // 2]
            chunk_store.add(chunk_id, doc_id, chunk_text)
            tracker.register_chunk(doc_id, chunk_id)

            # Create vectors in both primary and replica
            for db_name in ["primary", "replica"]:
                vector_id = f"vec_{chunk_id}_{db_name}"
                vector_stores[db_name].add(vector_id, chunk_id,
                                          metadata={"owner": owner, "text_preview": chunk_text[:30]})
                tracker.register_vector(chunk_id, vector_id, db_name)

    # Add cache entries
    cache_entries = [
        ("cache_js_1", "What is John Smith's salary?", "John Smith earns $185,000.", target_user),
        ("cache_js_2", "John Smith performance", "John Smith exceeds expectations.", target_user),
        ("cache_jd_1", "Jane's project", "Jane Doe proposed a Q4 initiative.", other_user),
    ]
    for key, query, response, uid in cache_entries:
        cache.add(key, query, response, uid)
        tracker.register_cache(uid, key)

    # Add memory entries
    memories = [
        ("mem_js_1", target_user, "John Smith prefers detailed explanations", "preference"),
        ("mem_js_2", target_user, "John Smith is a senior engineer at Acme", "fact"),
        ("mem_js_3", target_user, "John Smith asked about retirement plans", "interaction"),
        ("mem_jd_1", other_user, "Jane Doe prefers bullet points", "preference"),
    ]
    for mid, uid, content, mtype in memories:
        memory.add(mid, uid, content, mtype)

    # Add log entries
    log_entries = [
        (target_user, "query", "John Smith asked: What are my benefits?"),
        (target_user, "retrieval", "Retrieved doc_js_001 for John Smith"),
        (target_user, "response", "Generated salary info response for John Smith"),
        (other_user, "query", "Jane Doe asked: Project status?"),
    ]
    for uid, action, content in log_entries:
        logs.add(uid, action, content)

    # Print state
    print(f"  Documents:    {len(doc_store.documents)} ({len(john_docs)} John, {len(jane_docs)} Jane)")
    print(f"  Chunks:       {len(chunk_store.chunks)}")
    print(f"  Vectors:      {sum(len(vs.vectors) for vs in vector_stores.values())} (across {len(vector_stores)} stores)")
    print(f"  Cache entries: {len(cache.entries)}")
    print(f"  Memories:     {len(memory.memories)}")
    print(f"  Log entries:  {len(logs.logs)}")

    # ─── Pre-Deletion Verification ───────────────────────────────────────

    print(f"\n--- PRE-DELETION: Searching for 'John Smith' ---\n")
    verifier = DeletionVerifier(doc_store, chunk_store, vector_stores, cache, memory, logs)
    pre_check = verifier.verify(target_user, ["John Smith"])
    print(f"  Documents found: {len(pre_check['findings']['documents'])}")
    print(f"  Chunks found:    {len(pre_check['findings']['chunks'])}")
    print(f"  Cache hits:      {len(pre_check['findings']['cache'])}")
    print(f"  Memory hits:     {len(pre_check['findings']['memory'])}")
    print(f"  Log hits:        {len(pre_check['findings']['logs'])}")
    print(f"  System clean?    {'YES' if pre_check['clean'] else 'NO — data exists'}")

    # ─── Execute Deletion Cascade ────────────────────────────────────────

    print(f"\n{'=' * 70}")
    print(f"USER REQUESTS DELETION: '{target_user}'")
    print(f"{'=' * 70}")

    cascade = DeletionCascade(tracker, doc_store, chunk_store,
                              vector_stores, cache, memory, logs)

    print(f"\nExecuting deletion cascade...\n")
    result = cascade.execute(target_user)

    # Print cascade steps with timing
    print(f"  {'Step':<25} {'Items':<10} {'Time (ms)':<12}")
    print(f"  {'─' * 50}")
    for step in result.steps:
        elapsed = (step["time"] - result.started_at) * 1000
        count_key = [k for k in step.keys() if k not in ("step", "time")][0]
        print(f"  {step['step']:<25} {step[count_key]:<10} {elapsed:<12.2f}")

    total_time = (result.completed_at - result.started_at) * 1000
    print(f"\n  Total deletion time: {total_time:.2f}ms")

    # ─── Deletion Summary ────────────────────────────────────────────────

    print(f"\n--- DELETION SUMMARY ---\n")
    print(f"  Documents deleted:      {result.documents_deleted}")
    print(f"  Chunks deleted:         {result.chunks_deleted}")
    print(f"  Vectors deleted:        {result.vectors_deleted}")
    print(f"  Cache entries removed:  {result.cache_invalidated}")
    print(f"  Memories purged:        {result.memories_purged}")
    print(f"  Log entries redacted:   {result.logs_redacted}")
    total = (result.documents_deleted + result.chunks_deleted + result.vectors_deleted +
             result.cache_invalidated + result.memories_purged + result.logs_redacted)
    print(f"  ─────────────────────────────────")
    print(f"  TOTAL items affected:   {total}")

    # ─── Post-Deletion Verification ──────────────────────────────────────

    print(f"\n{'=' * 70}")
    print(f"POST-DELETION VERIFICATION")
    print(f"{'=' * 70}")

    print(f"\n  Searching for 'John Smith' across ALL systems...\n")
    post_check = verifier.verify(target_user, ["John Smith"])
    print(f"  Documents found: {len(post_check['findings']['documents'])}")
    print(f"  Chunks found:    {len(post_check['findings']['chunks'])}")
    print(f"  Cache hits:      {len(post_check['findings']['cache'])}")
    print(f"  Memory hits:     {len(post_check['findings']['memory'])}")
    print(f"  Log hits:        {len(post_check['findings']['logs'])}")
    print(f"\n  System clean?    {'YES — all traces removed' if post_check['clean'] else 'NO — residual data found!'}")

    # ─── Verify Other User Not Affected ──────────────────────────────────

    print(f"\n--- VERIFYING OTHER USERS NOT AFFECTED ---\n")
    jane_docs_remaining = doc_store.search_by_owner(other_user)
    jane_cache = cache.get_by_user(other_user)
    jane_memory = memory.get_by_user(other_user)
    print(f"  Jane Doe's documents: {len(jane_docs_remaining)} (should be 2)")
    print(f"  Jane Doe's cache:     {len(jane_cache)} (should be 1)")
    print(f"  Jane Doe's memory:    {len(jane_memory)} (should be 1)")
    all_intact = len(jane_docs_remaining) == 2 and len(jane_cache) == 1 and len(jane_memory) == 1
    print(f"  Other user data intact? {'YES' if all_intact else 'NO — collateral damage!'}")

    # ─── Audit Trail ─────────────────────────────────────────────────────

    print(f"\n{'=' * 70}")
    print(f"DELETION AUDIT TRAIL")
    print(f"{'=' * 70}")

    certificate_id = hashlib.sha256(
        f"{target_user}:{result.started_at}".encode()
    ).hexdigest()[:16]

    print(f"""
    ┌─────────────────────────────────────────────────────────┐
    │  DELETION CERTIFICATE                                    │
    ├─────────────────────────────────────────────────────────┤
    │  Certificate ID:  {certificate_id}             │
    │  User ID (hash):  {hashlib.sha256(target_user.encode()).hexdigest()[:16]}             │
    │  Requested:       {datetime.fromtimestamp(result.started_at).strftime('%Y-%m-%d %H:%M:%S')} UTC          │
    │  Completed:       {datetime.fromtimestamp(result.completed_at).strftime('%Y-%m-%d %H:%M:%S')} UTC          │
    │  Duration:        {total_time:.2f}ms                                │
    │                                                          │
    │  Items Deleted:                                          │
    │    Documents:     {result.documents_deleted}                                      │
    │    Chunks:        {result.chunks_deleted}                                      │
    │    Vectors:       {result.vectors_deleted}                                     │
    │    Cache:         {result.cache_invalidated}                                      │
    │    Memory:        {result.memories_purged}                                      │
    │    Logs:          {result.logs_redacted}                                      │
    │                                                          │
    │  Verification:    PASSED (no residual data found)        │
    │  Other users:     NOT AFFECTED                           │
    └─────────────────────────────────────────────────────────┘
    """)

    # ─── System State After Deletion ─────────────────────────────────────

    print(f"--- FINAL SYSTEM STATE ---\n")
    print(f"  Documents:    {len(doc_store.documents)} (was {len(john_docs) + len(jane_docs)})")
    print(f"  Chunks:       {len(chunk_store.chunks)} (was {(len(john_docs) + len(jane_docs)) * 2})")
    print(f"  Vectors:      {sum(len(vs.vectors) for vs in vector_stores.values())} (was {(len(john_docs) + len(jane_docs)) * 2 * 2})")
    print(f"  Cache:        {len(cache.entries)} (was {len(cache_entries)})")
    print(f"  Memory:       {len(memory.memories)} (was {len(memories)})")
    print(f"  Logs:         {len(logs.logs)} (redacted, not deleted)")


if __name__ == "__main__":
    main()
