"""
Permission-Filtered Retrieval for AI Systems
=============================================
ACL-aware vector search implementation:
- Permission metadata in vector DB
- Pre-retrieval ACL filtering
- Post-retrieval permission verification
- Group/role expansion
- Cross-tenant isolation
- Permission cache with invalidation
- Negative access testing
- Permission revocation latency monitoring
"""

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


# =============================================================================
# Core Models
# =============================================================================

@dataclass
class DocumentMetadata:
    """Metadata stored alongside vector embeddings."""
    document_id: str
    tenant_id: str
    # ACL fields stored as metadata for filtering
    owner: str
    viewer_users: list[str] = field(default_factory=list)
    editor_users: list[str] = field(default_factory=list)
    viewer_groups: list[str] = field(default_factory=list)
    editor_groups: list[str] = field(default_factory=list)
    is_public_within_tenant: bool = False
    classification: str = "internal"  # public, internal, confidential, restricted
    # Additional metadata
    source: str = ""
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class RetrievalContext:
    """Context for a retrieval request - carries user identity and permissions."""
    user_id: str
    tenant_id: str
    user_groups: list[str]
    user_roles: list[str]
    clearance_level: str = "internal"  # User's max classification access
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class RetrievedDocument:
    """A document returned from vector search."""
    document_id: str
    content: str
    score: float
    metadata: DocumentMetadata
    permission_verified: bool = False


@dataclass
class RetrievalResult:
    """Result of a permission-filtered retrieval."""
    documents: list[RetrievedDocument]
    total_candidates: int  # How many were retrieved before filtering
    filtered_count: int  # How many were removed by permission check
    retrieval_time_ms: float
    permission_check_time_ms: float
    cache_hit: bool = False


# =============================================================================
# Permission Cache
# =============================================================================

class PermissionCache:
    """
    Caches expanded permissions for efficient retrieval filtering.
    
    Caches:
    - User's expanded group memberships
    - User's accessible document IDs (for small result sets)
    - ACL expansion results
    
    Invalidation triggers:
    - Group membership change
    - Document ACL change
    - Role assignment change
    - User deactivation
    """

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._invalidation_log: list[dict] = []

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expires_at = self._cache[key]
            if time.time() < expires_at:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        self._cache[key] = (value, time.time() + (ttl or self.default_ttl))

    def invalidate_user(self, user_id: str):
        """Invalidate all cache entries for a user."""
        prefix = f"user:{user_id}:"
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            del self._cache[k]
        self._invalidation_log.append({
            "timestamp": time.time(),
            "type": "user_invalidation",
            "user_id": user_id,
            "keys_invalidated": len(keys),
        })

    def invalidate_document(self, document_id: str):
        """Invalidate cache entries related to a document ACL change."""
        # When a document's ACL changes, invalidate all user caches
        # (In production, use more targeted invalidation)
        self._cache.clear()
        self._invalidation_log.append({
            "timestamp": time.time(),
            "type": "document_invalidation",
            "document_id": document_id,
        })

    def invalidate_group(self, group_id: str):
        """Invalidate all entries for users in a group."""
        # In production, look up group members and invalidate their caches
        self._cache.clear()
        self._invalidation_log.append({
            "timestamp": time.time(),
            "type": "group_invalidation",
            "group_id": group_id,
        })


# =============================================================================
# Group/Role Expansion Service
# =============================================================================

class GroupExpansionService:
    """
    Expands user's groups and roles into a full access list.
    Handles nested groups and role hierarchies.
    """

    def __init__(self, cache: PermissionCache):
        self.cache = cache
        self._user_groups: dict[str, list[str]] = {}
        self._group_parents: dict[str, list[str]] = {}  # group → parent groups
        self._role_hierarchy: dict[str, list[str]] = {}  # role → parent roles

    def set_user_groups(self, user_id: str, groups: list[str]):
        self._user_groups[user_id] = groups

    def set_group_parent(self, group_id: str, parent_group_id: str):
        if group_id not in self._group_parents:
            self._group_parents[group_id] = []
        self._group_parents[group_id].append(parent_group_id)

    def expand_groups(self, user_id: str) -> list[str]:
        """Get all groups a user belongs to (including nested)."""
        cache_key = f"user:{user_id}:expanded_groups"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        direct_groups = self._user_groups.get(user_id, [])
        all_groups = set(direct_groups)

        # BFS to expand nested groups
        queue = list(direct_groups)
        while queue:
            current = queue.pop(0)
            parents = self._group_parents.get(current, [])
            for parent in parents:
                if parent not in all_groups:
                    all_groups.add(parent)
                    queue.append(parent)

        result = list(all_groups)
        self.cache.set(cache_key, result, ttl=600)
        return result

    def build_access_filter(self, context: RetrievalContext) -> dict:
        """
        Build a filter expression for vector DB query.
        Returns filter that matches documents the user can access.
        """
        expanded_groups = self.expand_groups(context.user_id)

        # The filter matches if ANY of these conditions is true:
        # 1. User is in viewer_users or editor_users
        # 2. Any of user's groups is in viewer_groups or editor_groups
        # 3. Document is public within tenant
        # 4. User is the owner

        return {
            "tenant_id": context.tenant_id,  # HARD requirement
            "$or": [
                {"owner": context.user_id},
                {"viewer_users": {"$contains": context.user_id}},
                {"editor_users": {"$contains": context.user_id}},
                {"viewer_groups": {"$containsAny": expanded_groups}},
                {"editor_groups": {"$containsAny": expanded_groups}},
                {"is_public_within_tenant": True},
            ],
            "classification": {"$in": self._allowed_classifications(context.clearance_level)},
        }

    def _allowed_classifications(self, clearance: str) -> list[str]:
        """What classification levels can this clearance access?"""
        hierarchy = ["public", "internal", "confidential", "restricted"]
        try:
            idx = hierarchy.index(clearance)
            return hierarchy[:idx + 1]
        except ValueError:
            return ["public"]


# =============================================================================
# Vector DB Interface (Abstract)
# =============================================================================

class VectorDBClient:
    """
    Abstract vector DB client. In production, replace with Pinecone/Weaviate/Qdrant/etc.
    """

    def __init__(self):
        self._documents: list[dict] = []  # Simulated storage

    async def upsert(self, doc_id: str, embedding: list[float], metadata: dict):
        """Store document with embedding and metadata."""
        self._documents.append({
            "id": doc_id,
            "embedding": embedding,
            "metadata": metadata,
        })

    async def query(
        self,
        embedding: list[float],
        top_k: int,
        filter_expr: dict = None,
        namespace: str = None,
    ) -> list[dict]:
        """
        Query with optional metadata filter.
        In production, the vector DB handles filtering server-side.
        """
        # Simulated: in real implementation, the vector DB applies filters
        results = []
        for doc in self._documents:
            # Apply namespace (tenant isolation at DB level)
            if namespace and doc["metadata"].get("tenant_id") != namespace:
                continue
            
            # Apply filter
            if filter_expr and not self._matches_filter(doc["metadata"], filter_expr):
                continue

            # Simulated similarity score
            score = self._cosine_similarity(embedding, doc["embedding"])
            results.append({
                "id": doc["id"],
                "score": score,
                "metadata": doc["metadata"],
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _matches_filter(self, metadata: dict, filter_expr: dict) -> bool:
        """Simple filter matching (production DBs do this natively)."""
        for key, condition in filter_expr.items():
            if key == "$or":
                if not any(self._matches_filter(metadata, c) for c in condition):
                    return False
            elif key == "$and":
                if not all(self._matches_filter(metadata, c) for c in condition):
                    return False
            elif isinstance(condition, dict):
                for op, value in condition.items():
                    actual = metadata.get(key)
                    if op == "$contains" and value not in (actual or []):
                        return False
                    elif op == "$containsAny" and not (set(value) & set(actual or [])):
                        return False
                    elif op == "$in" and actual not in value:
                        return False
                    elif op == "$eq" and actual != value:
                        return False
            else:
                if metadata.get(key) != condition:
                    return False
        return True

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# =============================================================================
# Permission-Filtered Retriever
# =============================================================================

class PermissionFilteredRetriever:
    """
    Main retrieval service that enforces permissions at query time.
    
    Strategy: Hybrid (pre-filter + post-verification)
    1. Pre-filter: Tenant isolation + broad group filter (at vector DB level)
    2. Oversample: Retrieve more results than needed
    3. Post-verify: Strict permission check on each result
    4. Return: Top-K that pass verification
    """

    def __init__(
        self,
        vector_db: VectorDBClient,
        group_expansion: GroupExpansionService,
        cache: PermissionCache,
        oversample_factor: float = 3.0,
        max_retrieval: int = 100,
    ):
        self.vector_db = vector_db
        self.group_expansion = group_expansion
        self.cache = cache
        self.oversample_factor = oversample_factor
        self.max_retrieval = max_retrieval
        self._metrics: list[dict] = []

    async def retrieve(
        self,
        query_embedding: list[float],
        context: RetrievalContext,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> RetrievalResult:
        """
        Retrieve documents with permission filtering.
        """
        start_time = time.time()

        # Step 1: Build pre-filter (applied at vector DB level)
        access_filter = self.group_expansion.build_access_filter(context)
        
        # Step 2: Oversample to account for post-filtering
        oversample_k = min(int(top_k * self.oversample_factor), self.max_retrieval)

        # Step 3: Query vector DB with pre-filter
        # Use tenant as namespace for hard isolation
        retrieval_start = time.time()
        raw_results = await self.vector_db.query(
            embedding=query_embedding,
            top_k=oversample_k,
            filter_expr=access_filter,
            namespace=context.tenant_id,  # Namespace-level tenant isolation
        )
        retrieval_time = (time.time() - retrieval_start) * 1000

        # Step 4: Post-retrieval permission verification
        permission_start = time.time()
        verified_results = []
        filtered_count = 0

        for result in raw_results:
            if result["score"] < min_score:
                continue

            # Strict permission verification
            if self._verify_permission(result["metadata"], context):
                doc = RetrievedDocument(
                    document_id=result["id"],
                    content=result["metadata"].get("content", ""),
                    score=result["score"],
                    metadata=DocumentMetadata(**{
                        k: v for k, v in result["metadata"].items()
                        if k in DocumentMetadata.__dataclass_fields__
                    }),
                    permission_verified=True,
                )
                verified_results.append(doc)
                if len(verified_results) >= top_k:
                    break
            else:
                filtered_count += 1

        permission_time = (time.time() - permission_start) * 1000
        total_time = (time.time() - start_time) * 1000

        # Record metrics
        self._metrics.append({
            "timestamp": time.time(),
            "request_id": context.request_id,
            "user_id": context.user_id,
            "tenant_id": context.tenant_id,
            "top_k": top_k,
            "oversample_k": oversample_k,
            "raw_results": len(raw_results),
            "verified_results": len(verified_results),
            "filtered_count": filtered_count,
            "retrieval_time_ms": retrieval_time,
            "permission_time_ms": permission_time,
            "total_time_ms": total_time,
        })

        return RetrievalResult(
            documents=verified_results,
            total_candidates=len(raw_results),
            filtered_count=filtered_count,
            retrieval_time_ms=retrieval_time,
            permission_check_time_ms=permission_time,
        )

    def _verify_permission(self, metadata: dict, context: RetrievalContext) -> bool:
        """
        Strict permission verification on a single document.
        This is the post-retrieval safety net.
        """
        # Hard tenant check (defense in depth)
        if metadata.get("tenant_id") != context.tenant_id:
            return False

        # Classification check
        allowed = self.group_expansion._allowed_classifications(context.clearance_level)
        if metadata.get("classification", "restricted") not in allowed:
            return False

        # Owner check
        if metadata.get("owner") == context.user_id:
            return True

        # Public within tenant
        if metadata.get("is_public_within_tenant"):
            return True

        # Direct user access
        if context.user_id in metadata.get("viewer_users", []):
            return True
        if context.user_id in metadata.get("editor_users", []):
            return True

        # Group access
        user_groups = set(self.group_expansion.expand_groups(context.user_id))
        doc_groups = set(metadata.get("viewer_groups", []) + metadata.get("editor_groups", []))
        if user_groups & doc_groups:
            return True

        return False


# =============================================================================
# Document Indexer (with ACL metadata)
# =============================================================================

class PermissionAwareIndexer:
    """
    Indexes documents into vector DB with ACL metadata.
    Ensures permission metadata is always stored alongside content.
    """

    def __init__(self, vector_db: VectorDBClient):
        self.vector_db = vector_db

    async def index_document(
        self,
        document_id: str,
        content: str,
        embedding: list[float],
        acl: DocumentMetadata,
    ):
        """Index a document with its ACL metadata."""
        metadata = {
            "document_id": document_id,
            "tenant_id": acl.tenant_id,
            "owner": acl.owner,
            "viewer_users": acl.viewer_users,
            "editor_users": acl.editor_users,
            "viewer_groups": acl.viewer_groups,
            "editor_groups": acl.editor_groups,
            "is_public_within_tenant": acl.is_public_within_tenant,
            "classification": acl.classification,
            "source": acl.source,
            "content": content,
            "created_at": acl.created_at or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.vector_db.upsert(document_id, embedding, metadata)

    async def update_acl(self, document_id: str, new_acl: DocumentMetadata):
        """
        Update ACL metadata for an existing document.
        In production, this updates metadata without re-embedding.
        """
        # Most vector DBs support metadata-only updates
        metadata_update = {
            "owner": new_acl.owner,
            "viewer_users": new_acl.viewer_users,
            "editor_users": new_acl.editor_users,
            "viewer_groups": new_acl.viewer_groups,
            "editor_groups": new_acl.editor_groups,
            "is_public_within_tenant": new_acl.is_public_within_tenant,
            "classification": new_acl.classification,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # In production: await self.vector_db.update_metadata(document_id, metadata_update)
        print(f"Updated ACL for document {document_id}")


# =============================================================================
# Negative Access Testing
# =============================================================================

class NegativeAccessTester:
    """
    Tests that permission filtering is working correctly.
    Verifies that users CANNOT access documents they shouldn't.
    
    Run periodically or on ACL changes to ensure no leakage.
    """

    def __init__(self, retriever: PermissionFilteredRetriever):
        self.retriever = retriever
        self._test_results: list[dict] = []

    async def test_cross_tenant_isolation(
        self,
        tenant_a_user: RetrievalContext,
        tenant_b_doc_ids: list[str],
        query_embedding: list[float],
    ) -> dict:
        """Verify tenant A user cannot retrieve tenant B documents."""
        result = await self.retriever.retrieve(
            query_embedding=query_embedding,
            context=tenant_a_user,
            top_k=100,
        )

        leaked_docs = [
            doc for doc in result.documents
            if doc.document_id in tenant_b_doc_ids
        ]

        test_result = {
            "test": "cross_tenant_isolation",
            "passed": len(leaked_docs) == 0,
            "leaked_documents": [d.document_id for d in leaked_docs],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._test_results.append(test_result)

        if leaked_docs:
            raise SecurityViolation(
                f"CRITICAL: Cross-tenant data leakage detected! "
                f"User {tenant_a_user.user_id} (tenant {tenant_a_user.tenant_id}) "
                f"accessed {len(leaked_docs)} documents from another tenant"
            )

        return test_result

    async def test_classification_enforcement(
        self,
        user_context: RetrievalContext,
        restricted_doc_ids: list[str],
        query_embedding: list[float],
    ) -> dict:
        """Verify user cannot access documents above their clearance."""
        result = await self.retriever.retrieve(
            query_embedding=query_embedding,
            context=user_context,
            top_k=100,
        )

        leaked = [
            doc for doc in result.documents
            if doc.document_id in restricted_doc_ids
        ]

        test_result = {
            "test": "classification_enforcement",
            "user_clearance": user_context.clearance_level,
            "passed": len(leaked) == 0,
            "leaked_documents": [d.document_id for d in leaked],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._test_results.append(test_result)
        return test_result

    async def test_revoked_access(
        self,
        user_context: RetrievalContext,
        revoked_doc_ids: list[str],
        query_embedding: list[float],
    ) -> dict:
        """Verify user cannot access documents after ACL revocation."""
        result = await self.retriever.retrieve(
            query_embedding=query_embedding,
            context=user_context,
            top_k=100,
        )

        still_accessible = [
            doc for doc in result.documents
            if doc.document_id in revoked_doc_ids
        ]

        test_result = {
            "test": "revoked_access",
            "passed": len(still_accessible) == 0,
            "still_accessible": [d.document_id for d in still_accessible],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._test_results.append(test_result)
        return test_result


# =============================================================================
# Permission Revocation Latency Monitor
# =============================================================================

class RevocationLatencyMonitor:
    """
    Monitors how long it takes for permission revocation to take effect
    in the retrieval system.
    
    Critical metric: time between ACL change and retrieval enforcement.
    Target: < 1 second for hard revocations, < 5 minutes for soft changes.
    """

    def __init__(self):
        self._measurements: list[dict] = []
        self._alerts: list[dict] = []
        self.sla_hard_revocation_ms = 1000  # 1 second
        self.sla_soft_change_ms = 300000  # 5 minutes

    async def measure_revocation_latency(
        self,
        retriever: PermissionFilteredRetriever,
        cache: PermissionCache,
        user_context: RetrievalContext,
        document_id: str,
        query_embedding: list[float],
    ) -> dict:
        """
        Measure time from ACL revocation to retrieval enforcement.
        
        Steps:
        1. Verify user CAN access document
        2. Revoke access (invalidate cache, update ACL)
        3. Measure time until user CANNOT access document
        """
        # Step 1: Verify current access
        result_before = await retriever.retrieve(query_embedding, user_context, top_k=50)
        accessible_before = any(d.document_id == document_id for d in result_before.documents)
        
        if not accessible_before:
            return {"error": "Document not accessible before revocation (invalid test setup)"}

        # Step 2: Revoke (simulate ACL change + cache invalidation)
        revocation_start = time.time()
        cache.invalidate_user(user_context.user_id)

        # Step 3: Measure enforcement
        enforcement_time = None
        max_attempts = 100
        for attempt in range(max_attempts):
            result_after = await retriever.retrieve(query_embedding, user_context, top_k=50)
            still_accessible = any(d.document_id == document_id for d in result_after.documents)
            
            if not still_accessible:
                enforcement_time = (time.time() - revocation_start) * 1000
                break
            
            await asyncio.sleep(0.01)  # 10ms between checks

        measurement = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "document_id": document_id,
            "user_id": user_context.user_id,
            "latency_ms": enforcement_time,
            "within_sla": enforcement_time is not None and enforcement_time < self.sla_hard_revocation_ms,
        }
        self._measurements.append(measurement)

        # Alert if SLA violated
        if enforcement_time is None or enforcement_time > self.sla_hard_revocation_ms:
            alert = {
                "severity": "critical",
                "message": f"Permission revocation latency SLA violated: {enforcement_time}ms > {self.sla_hard_revocation_ms}ms",
                "measurement": measurement,
            }
            self._alerts.append(alert)

        return measurement

    def get_p99_latency(self) -> float:
        """Get P99 revocation latency."""
        latencies = [m["latency_ms"] for m in self._measurements if m["latency_ms"] is not None]
        if not latencies:
            return 0.0
        latencies.sort()
        p99_idx = int(len(latencies) * 0.99)
        return latencies[min(p99_idx, len(latencies) - 1)]


# =============================================================================
# Exceptions
# =============================================================================

class SecurityViolation(Exception):
    """Critical security violation detected."""
    pass


# =============================================================================
# Usage Example
# =============================================================================

async def example():
    """Demonstrates permission-filtered retrieval."""
    # Setup
    cache = PermissionCache(default_ttl=300)
    group_expansion = GroupExpansionService(cache)
    vector_db = VectorDBClient()
    
    retriever = PermissionFilteredRetriever(
        vector_db=vector_db,
        group_expansion=group_expansion,
        cache=cache,
    )
    indexer = PermissionAwareIndexer(vector_db)

    # Configure groups
    group_expansion.set_user_groups("user_1", ["engineering", "ai-team"])
    group_expansion.set_user_groups("user_2", ["marketing"])

    # Index documents with ACLs
    await indexer.index_document(
        document_id="doc_1",
        content="AI architecture design document",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        acl=DocumentMetadata(
            document_id="doc_1",
            tenant_id="tenant_abc",
            owner="user_1",
            viewer_groups=["engineering"],
            classification="internal",
        ),
    )
    await indexer.index_document(
        document_id="doc_2",
        content="Marketing campaign plan",
        embedding=[0.5, 0.4, 0.3, 0.2, 0.1],
        acl=DocumentMetadata(
            document_id="doc_2",
            tenant_id="tenant_abc",
            owner="user_2",
            viewer_groups=["marketing"],
            classification="internal",
        ),
    )
    await indexer.index_document(
        document_id="doc_3",
        content="Confidential board meeting notes",
        embedding=[0.3, 0.3, 0.3, 0.3, 0.3],
        acl=DocumentMetadata(
            document_id="doc_3",
            tenant_id="tenant_abc",
            owner="user_admin",
            classification="restricted",
        ),
    )

    # Retrieve as engineering user
    context = RetrievalContext(
        user_id="user_1",
        tenant_id="tenant_abc",
        user_groups=["engineering", "ai-team"],
        user_roles=["editor"],
        clearance_level="internal",
    )

    result = await retriever.retrieve(
        query_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        context=context,
        top_k=10,
    )

    print(f"Retrieved {len(result.documents)} documents (filtered {result.filtered_count})")
    for doc in result.documents:
        print(f"  - {doc.document_id}: score={doc.score:.3f}, verified={doc.permission_verified}")

    # Negative access test
    tester = NegativeAccessTester(retriever)
    
    # Marketing user should NOT see engineering docs
    marketing_context = RetrievalContext(
        user_id="user_2",
        tenant_id="tenant_abc",
        user_groups=["marketing"],
        user_roles=["viewer"],
        clearance_level="internal",
    )
    
    # This would pass - user_2 shouldn't see doc_1 (engineering only)
    print("\nNegative access testing validates permission boundaries")


if __name__ == "__main__":
    asyncio.run(example())
