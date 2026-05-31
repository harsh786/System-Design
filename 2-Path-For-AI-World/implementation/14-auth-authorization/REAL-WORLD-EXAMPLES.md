# Auth & Authorization for AI Systems: Real-World Examples

## Case Study 1: Multi-Tenant SaaS with Permission-Filtered RAG

### Company Context

A B2B document intelligence platform serves 200+ enterprise tenants. Each tenant uploads contracts, invoices, and legal documents. An AI assistant answers questions about documents — but Tenant A must **never** see Tenant B's data, even if semantically similar.

### The Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  MULTI-TENANT PERMISSION-FILTERED RAG                                    │
│                                                                          │
│  User Query                                                              │
│      │                                                                   │
│      ▼                                                                   │
│  ┌─────────────────────────────────┐                                    │
│  │ 1. Authentication               │                                    │
│  │    - JWT validation             │                                    │
│  │    - Extract: tenant_id,        │                                    │
│  │      user_id, roles             │                                    │
│  └─────────────┬───────────────────┘                                    │
│                │                                                         │
│                ▼                                                         │
│  ┌─────────────────────────────────┐                                    │
│  │ 2. Permission Resolution        │                                    │
│  │    - User's document groups     │                                    │
│  │    - Classification clearance   │                                    │
│  │    - Project access list        │                                    │
│  └─────────────┬───────────────────┘                                    │
│                │                                                         │
│                ▼                                                         │
│  ┌─────────────────────────────────┐                                    │
│  │ 3. Vector Search with           │                                    │
│  │    PRE-FILTER                   │                                    │
│  │                                 │                                    │
│  │    WHERE tenant_id = 'acme'     │                                    │
│  │    AND classification <= 'conf' │                                    │
│  │    AND project_id IN (p1, p3)   │                                    │
│  │                                 │                                    │
│  │    THEN: similarity_search(q)   │                                    │
│  └─────────────┬───────────────────┘                                    │
│                │                                                         │
│                ▼                                                         │
│  ┌─────────────────────────────────┐                                    │
│  │ 4. Post-Retrieval Validation    │                                    │
│  │    - Double-check each doc's    │                                    │
│  │      permissions (defense in    │                                    │
│  │      depth)                     │                                    │
│  │    - Remove any that slipped    │                                    │
│  │      through (metadata lag)     │                                    │
│  └─────────────┬───────────────────┘                                    │
│                │                                                         │
│                ▼                                                         │
│  ┌─────────────────────────────────┐                                    │
│  │ 5. LLM Generation              │                                    │
│  │    - Only authorized docs in    │                                    │
│  │      context                    │                                    │
│  │    - Audit: log which docs used │                                    │
│  └─────────────────────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### Vector DB Schema (Pinecone)

```python
# Each vector stored with permission metadata
{
    "id": "doc_abc123_chunk_7",
    "values": [0.023, -0.156, ...],  # 1536-dim embedding
    "metadata": {
        "tenant_id": "acme_corp",           # HARD boundary
        "document_id": "contract_2024_001",
        "project_id": "project_alpha",
        "classification": "confidential",    # public < internal < confidential < restricted
        "department": "legal",
        "uploaded_by": "user_jane",
        "accessible_to_groups": ["legal_team", "exec_team"],  # Fine-grained
        "chunk_index": 7,
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

### Query with Pre-Filter

```python
async def permission_filtered_search(
    query: str, 
    user: AuthenticatedUser,
    top_k: int = 10
) -> list[Document]:
    # Resolve user's effective permissions
    permissions = await resolve_permissions(user)
    # Returns: {tenant_id: "acme_corp", groups: ["legal_team"], 
    #           max_classification: "confidential", projects: ["project_alpha", "project_gamma"]}
    
    # Build filter (applied BEFORE similarity search in the vector DB)
    metadata_filter = {
        "tenant_id": {"$eq": permissions.tenant_id},  # Mandatory
        "classification": {"$lte": classification_to_int(permissions.max_classification)},
        "accessible_to_groups": {"$in": permissions.groups},
    }
    
    # Optionally scope to project
    if permissions.project_scope:
        metadata_filter["project_id"] = {"$in": permissions.projects}
    
    # Vector search with filter
    embedding = await embed(query)
    results = await pinecone_index.query(
        vector=embedding,
        filter=metadata_filter,
        top_k=top_k,
        include_metadata=True
    )
    
    # Post-filter validation (defense in depth)
    validated = []
    for match in results.matches:
        if await validate_access(user, match.metadata["document_id"]):
            validated.append(match)
        else:
            logger.warning(f"Post-filter caught unauthorized doc: {match.id}")
            metrics.increment("post_filter_catch")
    
    return validated
```

### The Breach Scenario They Prevented

During a penetration test, a security researcher created a document with content semantically identical to another tenant's confidential contract. Without tenant_id pre-filtering, vector similarity search would have returned the other tenant's actual contract chunks (similarity score: 0.94). With pre-filtering, the search space was restricted to only that tenant's vectors — the cross-tenant document was never even considered.

---

## Case Study 2: Bank Agent Authorization (On-Behalf-Of Flow)

### Scenario

A major bank deploys an AI agent that can:
- Check account balances
- Initiate transfers (< $10K)
- Generate financial reports
- Flag suspicious transactions

The agent acts **on behalf of** a customer service representative, who acts on behalf of the customer. Every action must be traceable.

### The Authorization Chain

```
┌────────────────────────────────────────────────────────────────────────┐
│  ON-BEHALF-OF AUTHORIZATION CHAIN                                      │
│                                                                        │
│  Customer (identity verified via phone + MFA)                          │
│      │                                                                 │
│      │ Delegates to                                                    │
│      ▼                                                                 │
│  CSR Agent (Sarah, employee #4521)                                     │
│      │ authenticated via: SSO + badge + case assignment                │
│      │                                                                 │
│      │ Delegates to                                                    │
│      ▼                                                                 │
│  AI Assistant (service account: ai-banking-assist-prod)                │
│      │ authenticated via: mTLS + service token                         │
│      │ authorized for: customer's accounts ONLY                        │
│      │ scoped to: current case (case_id: CS-2024-78432)               │
│      │ time-limited: 30 minutes from case start                        │
│      │                                                                 │
│      │ Calls                                                           │
│      ▼                                                                 │
│  Banking API (core banking system)                                     │
│      │ validates: ai-assist token + OBO claim + scope                  │
│      │ checks: amount limits, account ownership, time window           │
│      │ logs: full audit trail                                          │
│      ▼                                                                 │
│  Transaction Executed (or rejected)                                    │
└────────────────────────────────────────────────────────────────────────┘
```

### Token Structure

```json
// AI Agent's scoped token (issued per-case)
{
  "iss": "https://auth.bigbank.com",
  "sub": "svc:ai-banking-assist-prod",
  "aud": "https://api.bigbank.com/core-banking",
  "iat": 1710500000,
  "exp": 1710501800,  // 30 minutes
  "obo": {
    "employee_id": "emp_4521",
    "employee_name": "Sarah Chen",
    "department": "customer_service"
  },
  "customer_context": {
    "customer_id": "cust_889234",
    "verified_via": "phone_mfa",
    "verified_at": "2024-03-15T14:20:00Z"
  },
  "scope": [
    "accounts:read:cust_889234",
    "transfers:initiate:cust_889234:max_10000",
    "reports:generate:cust_889234"
  ],
  "case_id": "CS-2024-78432",
  "restrictions": {
    "max_transfer_amount": 10000,
    "allowed_accounts": ["acct_001", "acct_002"],
    "blocked_operations": ["account_close", "loan_origination"]
  }
}
```

### Audit Trail (Every AI Action Logged)

```json
// Stored in immutable append-only audit log
{
  "event_id": "evt_a8f3c2d1",
  "timestamp": "2024-03-15T14:25:33.847Z",
  "actor": {
    "type": "ai_agent",
    "service_id": "ai-banking-assist-prod",
    "model_version": "v3.2.1",
    "on_behalf_of_employee": "emp_4521",
    "on_behalf_of_customer": "cust_889234"
  },
  "action": {
    "type": "transfer_initiate",
    "from_account": "acct_001",
    "to_account": "acct_002",
    "amount": 500.00,
    "currency": "USD"
  },
  "authorization": {
    "token_id": "tok_x9y8z7",
    "scope_used": "transfers:initiate:cust_889234:max_10000",
    "within_limits": true
  },
  "context": {
    "case_id": "CS-2024-78432",
    "user_request": "Please transfer $500 from checking to savings",
    "ai_reasoning": "Customer requested internal transfer between their own accounts. Amount within limits.",
    "confidence": 0.98
  },
  "result": "approved_and_executed"
}
```

---

## Token Exchange Chain: OAuth2 Delegation with Decreasing TTLs

### The Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TOKEN EXCHANGE CHAIN (RFC 8693)                                        │
│                                                                         │
│  Step 1: User authenticates                                             │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ User → IdP: Login (username + MFA)                   │               │
│  │ IdP → User: access_token_A                           │               │
│  │   TTL: 60 minutes                                    │               │
│  │   Scope: full_user_access                            │               │
│  │   Audience: ai-platform                              │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  Step 2: User delegates to AI Agent                                     │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ AI Platform → Token Service:                         │               │
│  │   grant_type: urn:ietf:params:oauth:grant-type:      │               │
│  │               token-exchange                         │               │
│  │   subject_token: access_token_A                      │               │
│  │   requested_scope: documents:read calendar:read      │               │
│  │   requested_token_type: access_token                 │               │
│  │                                                      │               │
│  │ Token Service → AI Platform: access_token_B          │               │
│  │   TTL: 15 minutes (reduced from 60)                  │               │
│  │   Scope: documents:read calendar:read (subset)       │               │
│  │   Actor: ai-agent-service                            │               │
│  │   Subject: original_user                             │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  Step 3: AI Agent delegates to Tool                                     │
│  ┌─────────────────────────────────────────────────────┐               │
│  │ AI Agent → Token Service:                            │               │
│  │   grant_type: token-exchange                         │               │
│  │   subject_token: access_token_B                      │               │
│  │   requested_scope: documents:read                    │               │
│  │   (further reduced — drops calendar:read)            │               │
│  │                                                      │               │
│  │ Token Service → Tool: access_token_C                 │               │
│  │   TTL: 5 minutes (further reduced)                   │               │
│  │   Scope: documents:read (single scope)               │               │
│  │   Actor: document-search-tool                        │               │
│  │   Subject: original_user                             │               │
│  │   Chain: user → ai-agent → document-tool             │               │
│  └─────────────────────────────────────────────────────┘               │
│                                                                         │
│  PRINCIPLE: Each hop REDUCES scope and TTL. Never increases.            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class TokenExchangeService:
    """Implements RFC 8693 with AI-specific constraints."""
    
    # Maximum TTL reduction ratios per hop
    TTL_REDUCTION = {
        "user_to_agent": 0.25,      # Agent gets 25% of user's remaining TTL
        "agent_to_tool": 0.33,      # Tool gets 33% of agent's remaining TTL
        "tool_to_subtool": 0.5,     # Sub-tool gets 50% of tool's remaining TTL
    }
    
    # Maximum delegation depth
    MAX_CHAIN_DEPTH = 4
    
    async def exchange(self, request: TokenExchangeRequest) -> Token:
        # Validate subject token
        subject_claims = await self.validate_token(request.subject_token)
        
        # Check chain depth
        chain = subject_claims.get("delegation_chain", [])
        if len(chain) >= self.MAX_CHAIN_DEPTH:
            raise AuthError("Maximum delegation depth exceeded")
        
        # Validate scope reduction (new scope must be subset)
        if not set(request.requested_scope).issubset(set(subject_claims["scope"])):
            raise AuthError("Cannot request scope broader than subject token")
        
        # Calculate TTL
        remaining_ttl = subject_claims["exp"] - time.time()
        hop_type = self.determine_hop_type(subject_claims, request)
        new_ttl = min(
            remaining_ttl * self.TTL_REDUCTION[hop_type],
            request.max_ttl or float('inf'),
            300  # Hard cap: 5 minutes for tool tokens
        )
        
        # Issue new token
        new_token = Token(
            sub=subject_claims["sub"],  # Original user remains subject
            actor=request.client_id,     # New actor in chain
            scope=request.requested_scope,
            exp=time.time() + new_ttl,
            delegation_chain=chain + [request.client_id],
            original_auth_time=subject_claims.get("auth_time"),
        )
        
        # Audit
        await self.audit_log.record_exchange(
            original_subject=subject_claims["sub"],
            from_actor=subject_claims.get("actor", subject_claims["sub"]),
            to_actor=request.client_id,
            scope_granted=request.requested_scope,
            ttl_granted=new_ttl,
        )
        
        return new_token
```

---

## Permission-Filtered Retrieval: Pre-Filter vs Post-Filter Performance

### Real Benchmark Data

**Dataset:** 10M document chunks across 500 tenants, Pinecone (p2 pod), 1536-dim embeddings

#### Pre-Filter Approach

```python
# Filter BEFORE similarity search
results = index.query(
    vector=query_embedding,
    filter={"tenant_id": "acme", "access_groups": {"$in": user_groups}},
    top_k=10
)
```

**Performance:**
| Metric | Value |
|--------|-------|
| p50 latency | 48ms |
| p95 latency | 82ms |
| p99 latency | 145ms |
| Accuracy (recall@10) | 0.89 |
| Security guarantee | 100% (unauthorized docs never searched) |

**Why lower accuracy:** Pre-filtering reduces the search space. If a tenant has only 50K chunks, the similarity search operates on 50K vectors instead of 10M, which can miss globally-similar chunks that happen to exist in other tenants (not a real problem — those are other tenant's data anyway).

#### Post-Filter Approach

```python
# Search ALL vectors, then filter results
results = index.query(
    vector=query_embedding,
    top_k=100  # Over-fetch to account for filtering
)
# Then filter
authorized = [r for r in results if check_permission(user, r.metadata)]
return authorized[:10]
```

**Performance:**
| Metric | Value |
|--------|-------|
| p50 latency | 195ms |
| p95 latency | 340ms |
| p99 latency | 520ms |
| Accuracy (recall@10) | 0.94 |
| Security guarantee | 99.7% (race condition risk during permission changes) |

**Why higher latency:** Must fetch 10x candidates, then run permission checks on each. Also 100 permission checks per query.

**Why 99.7% not 100%:** If a user's permissions are revoked between the vector search and the filter check, there's a brief window where they might see a result. Pre-filter doesn't have this race condition.

#### Recommendation

```
┌─────────────────────────────────────────────────────────────┐
│  DECISION MATRIX                                            │
│                                                             │
│  Use PRE-FILTER when:                                       │
│  ✓ Hard multi-tenant boundaries (compliance requirement)    │
│  ✓ Latency-sensitive applications                          │
│  ✓ Simple permission model (tenant + role)                 │
│                                                             │
│  Use POST-FILTER when:                                      │
│  ✓ Complex, dynamic permissions (changes every minute)     │
│  ✓ Accuracy is paramount over latency                      │
│  ✓ Permission model too complex for vector DB filters      │
│                                                             │
│  Use HYBRID (pre-filter tenant, post-filter fine-grained): │
│  ✓ Most production systems end up here                     │
│  ✓ Pre-filter: tenant_id (hard boundary)                   │
│  ✓ Post-filter: document-level ACLs (fine-grained)         │
│  ✓ Latency: 70-120ms (acceptable)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Row-Level Security for AI: Postgres RLS with RAG

### How It Works

Instead of filtering in application code, enforce access at the database level using Postgres Row-Level Security. Even if the AI agent's code has a bug, it physically cannot read unauthorized rows.

### Schema

```sql
-- Tenants
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL
);

-- Documents with tenant ownership
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    title TEXT,
    content TEXT,
    embedding vector(1536),  -- pgvector
    classification TEXT DEFAULT 'internal',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document access grants
CREATE TABLE document_access (
    document_id UUID REFERENCES documents(id),
    grantee_user_id UUID,
    grantee_group TEXT,
    permission TEXT CHECK (permission IN ('read', 'write', 'admin')),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- RLS Policies
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Policy 1: Tenant isolation (hardest boundary)
CREATE POLICY tenant_isolation ON documents
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Policy 2: Classification level
CREATE POLICY classification_access ON documents
    FOR SELECT
    USING (
        classification_to_int(classification) <= 
        classification_to_int(current_setting('app.user_clearance'))
    );

-- Policy 3: Explicit document grants
CREATE POLICY document_grants ON documents
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM document_access da
            WHERE da.document_id = documents.id
            AND (
                da.grantee_user_id = current_setting('app.current_user_id')::UUID
                OR da.grantee_group = ANY(
                    string_to_array(current_setting('app.user_groups'), ',')
                )
            )
            AND (da.expires_at IS NULL OR da.expires_at > NOW())
            AND da.permission IN ('read', 'write', 'admin')
        )
    );
```

### RAG Query with RLS

```python
async def rag_search_with_rls(
    query: str, 
    user: AuthenticatedUser, 
    db: AsyncSession
) -> list[Document]:
    """
    The beauty of RLS: The query looks simple. Security is enforced by Postgres.
    Even a SQL injection in the query can't bypass tenant isolation.
    """
    # Set session variables for RLS policies
    await db.execute(text(
        "SET app.current_tenant_id = :tid"
    ), {"tid": str(user.tenant_id)})
    await db.execute(text(
        "SET app.current_user_id = :uid"
    ), {"uid": str(user.id)})
    await db.execute(text(
        "SET app.user_clearance = :clearance"
    ), {"clearance": user.clearance_level})
    await db.execute(text(
        "SET app.user_groups = :groups"
    ), {"groups": ",".join(user.groups)})
    
    # Simple similarity search — RLS handles the rest
    embedding = await embed(query)
    results = await db.execute(text("""
        SELECT id, title, content, 
               1 - (embedding <=> :query_vec) AS similarity
        FROM documents
        ORDER BY embedding <=> :query_vec
        LIMIT 10
    """), {"query_vec": str(embedding)})
    
    # Postgres automatically filters out rows the user can't see
    # No application-level filtering needed
    return results.fetchall()
```

---

## Multi-Tenant Vector Isolation: Architecture Comparison

### Three Approaches Benchmarked

#### Approach 1: Namespace Isolation (Pinecone)

```
┌──────────────────────────────────────────┐
│  Single Index, Multiple Namespaces       │
│                                          │
│  Index: "production"                     │
│  ├── Namespace: "tenant_acme"   (200K)  │
│  ├── Namespace: "tenant_globex" (150K)  │
│  ├── Namespace: "tenant_initech"(500K)  │
│  └── Namespace: "tenant_..."    (...)   │
│                                          │
│  Query: index.query(                     │
│    namespace="tenant_acme",              │
│    vector=embedding,                     │
│    top_k=10                              │
│  )                                       │
└──────────────────────────────────────────┘
```

| Metric | Value |
|--------|-------|
| Isolation guarantee | Strong (namespace = hard boundary) |
| Query latency (p50) | 35ms |
| Cost (500 tenants, 10M total vectors) | $70/month (s1 pod) |
| Scaling | All tenants share index resources |
| Tenant onboarding | Instant (create namespace) |
| Tenant deletion | Fast (delete namespace) |
| Cross-tenant search | Impossible (by design) |
| Max tenants | ~10,000 namespaces per index |

#### Approach 2: Collection Isolation (Qdrant/Weaviate)

```
┌──────────────────────────────────────────┐
│  Separate Collection Per Tenant          │
│                                          │
│  ├── Collection: "acme_docs"      (200K)│
│  ├── Collection: "globex_docs"    (150K)│
│  ├── Collection: "initech_docs"   (500K)│
│  └── Collection: "..."                   │
│                                          │
│  Query: client.search(                   │
│    collection_name="acme_docs",          │
│    query_vector=embedding,               │
│    limit=10                              │
│  )                                       │
└──────────────────────────────────────────┘
```

| Metric | Value |
|--------|-------|
| Isolation guarantee | Strongest (separate storage + index) |
| Query latency (p50) | 25ms (smaller index = faster search) |
| Cost (500 tenants, 10M total vectors) | $200/month (more resources needed) |
| Scaling | Per-tenant scaling possible |
| Tenant onboarding | 2-5 seconds (create collection + index) |
| Tenant deletion | Clean (drop collection) |
| Cross-tenant search | Impossible |
| Max tenants | Limited by memory (each collection has overhead) |

#### Approach 3: Metadata Filtering (Single Collection)

```
┌──────────────────────────────────────────┐
│  Single Collection, Filter by Metadata   │
│                                          │
│  Collection: "all_documents" (10M)       │
│  Each vector has: {tenant_id: "acme"}    │
│                                          │
│  Query: client.search(                   │
│    collection_name="all_documents",      │
│    query_vector=embedding,               │
│    query_filter=Filter(                  │
│      must=[                              │
│        FieldCondition(                   │
│          key="tenant_id",               │
│          match=MatchValue(value="acme") │
│        )                                 │
│      ]                                   │
│    ),                                    │
│    limit=10                              │
│  )                                       │
└──────────────────────────────────────────┘
```

| Metric | Value |
|--------|-------|
| Isolation guarantee | Application-level only (bug = breach) |
| Query latency (p50) | 52ms (filters 10M vectors) |
| Cost (500 tenants, 10M total vectors) | $50/month (most efficient) |
| Scaling | Shared resources |
| Tenant onboarding | Instant (just start inserting) |
| Tenant deletion | Slow (delete by filter across millions) |
| Cross-tenant search | Possible if filter is missing (risk!) |
| Max tenants | Unlimited |

### Recommendation by Use Case

```
Regulated industry (finance, health, gov) → Collection Isolation
  - Compliance requires provable data separation
  - Worth the extra cost for audit-proof isolation

Standard B2B SaaS (< 1000 tenants) → Namespace Isolation
  - Good balance of isolation + simplicity
  - Hard boundary without per-collection overhead

High-scale / cost-sensitive (> 10K tenants) → Metadata Filtering + RLS
  - Must add defense-in-depth (double-check in application layer)
  - Accept the risk that a code bug could cause cross-tenant leakage
  - Mitigate with extensive testing + monitoring
```

---

## Zero-Trust for AI: Defense Contractor Implementation

### Context

A defense contractor builds an AI system for analyzing satellite imagery. Components: image ingestion service, embedding model, vector store, analysis LLM, reporting service. All must communicate securely with zero-trust assumptions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ZERO-TRUST AI SYSTEM (NIST SP 800-207 aligned)                        │
│                                                                         │
│  Every connection:                                                       │
│  ✓ Mutual TLS (both sides present certificates)                        │
│  ✓ Short-lived certificates (4 hours max)                              │
│  ✓ Service mesh (Istio) enforces policy                                │
│  ✓ No implicit trust between ANY components                            │
│                                                                         │
│  ┌──────────┐  mTLS   ┌──────────┐  mTLS   ┌──────────┐              │
│  │  Image   │────────►│ Embedding│────────►│  Vector  │              │
│  │ Ingestion│         │  Model   │         │  Store   │              │
│  └──────────┘         └──────────┘         └──────────┘              │
│       │                                          │                     │
│       │ mTLS                                     │ mTLS                │
│       ▼                                          ▼                     │
│  ┌──────────┐  mTLS   ┌──────────┐  mTLS   ┌──────────┐              │
│  │  Policy  │────────►│ Analysis │────────►│Reporting │              │
│  │  Engine  │         │   LLM    │         │ Service  │              │
│  └──────────┘         └──────────┘         └──────────┘              │
│                                                                         │
│  Cross-cutting:                                                         │
│  ├─ SPIFFE IDs for all workloads (spiffe://cluster/ns/ai/sa/embedding) │
│  ├─ Certificate rotation every 4 hours (automatic via cert-manager)    │
│  ├─ Network policies: explicit allow-list (deny-all default)           │
│  ├─ All data encrypted at rest (AES-256) and in transit (TLS 1.3)     │
│  └─ Air-gapped from internet (all models run on-premise)               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Service-to-Service Authorization

```yaml
# Istio AuthorizationPolicy — Embedding Model
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: embedding-model-access
  namespace: ai-pipeline
spec:
  selector:
    matchLabels:
      app: embedding-model
  rules:
  - from:
    - source:
        principals: 
          - "cluster.local/ns/ai-pipeline/sa/image-ingestion"
          # ONLY image-ingestion can call embedding model
    to:
    - operation:
        methods: ["POST"]
        paths: ["/v1/embeddings"]
  # Implicit deny-all for anything not matching above rules
```

### Data Classification Enforcement

```python
class ClassifiedDataHandler:
    """
    Each piece of data carries its classification level.
    Services can only process data at or below their clearance.
    """
    
    SERVICE_CLEARANCES = {
        "image-ingestion": "SECRET",
        "embedding-model": "SECRET",      # Can process SECRET imagery
        "vector-store": "SECRET",
        "analysis-llm": "TOP_SECRET",     # Can correlate multiple sources
        "reporting-service": "SECRET",     # Reports are downgraded
    }
    
    CLASSIFICATION_HIERARCHY = ["UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP_SECRET"]
    
    def validate_processing(self, service_id: str, data_classification: str) -> bool:
        service_clearance = self.SERVICE_CLEARANCES[service_id]
        return (
            self.CLASSIFICATION_HIERARCHY.index(service_clearance) >= 
            self.CLASSIFICATION_HIERARCHY.index(data_classification)
        )
    
    def enforce_output_classification(self, service_id: str, output_data: bytes) -> ClassifiedData:
        """Output is always classified at the HIGHEST level of any input."""
        return ClassifiedData(
            data=output_data,
            classification=self.highest_input_classification,
            handling_caveats=["NOFORN", "REL TO FVEY"],
            originator=service_id,
            timestamp=datetime.utcnow(),
        )
```

---

## Agent Identity Management: 50 Service Accounts

### The Challenge

A platform team manages 50 AI agent service accounts across dev/staging/prod. Each agent has different permissions, secret credentials, and API keys that need regular rotation.

### Architecture

```python
class AgentIdentityManager:
    """
    Central management for all AI agent service accounts.
    Real system managing 50 agents across 3 environments = 150 identities.
    """
    
    def __init__(self):
        self.vault = HashiCorpVault(url="https://vault.internal:8200")
        self.identity_store = PostgresIdentityStore()
        self.rotation_scheduler = APScheduler()
    
    # Agent identity record
    AGENT_REGISTRY = {
        "ai-support-agent": {
            "environments": ["dev", "staging", "prod"],
            "permissions": {
                "prod": ["tickets:read", "tickets:respond", "kb:search"],
                "staging": ["tickets:read", "tickets:respond", "kb:search", "kb:write"],
                "dev": ["*"],  # Full access in dev
            },
            "secret_rotation_days": 7,
            "max_concurrent_sessions": 10,
            "rate_limit": "100/minute",
            "owner_team": "customer-experience",
            "alert_channel": "#ai-support-oncall",
        },
        "ai-analytics-agent": {
            "environments": ["dev", "staging", "prod"],
            "permissions": {
                "prod": ["data:read", "reports:generate"],
                "staging": ["data:read", "data:write", "reports:generate"],
                "dev": ["*"],
            },
            "secret_rotation_days": 30,
            "max_concurrent_sessions": 5,
            "rate_limit": "20/minute",
            "owner_team": "data-platform",
            "alert_channel": "#data-platform-oncall",
        },
        # ... 48 more agents
    }
    
    async def rotate_secrets(self, agent_id: str, env: str):
        """Automated secret rotation with zero-downtime."""
        
        # 1. Generate new credentials
        new_secret = secrets.token_urlsafe(64)
        new_api_key = f"ak_{secrets.token_urlsafe(32)}"
        
        # 2. Store in Vault with new version (old version still valid)
        await self.vault.write(
            path=f"secret/ai-agents/{agent_id}/{env}",
            data={"api_key": new_api_key, "secret": new_secret},
            cas=True  # Check-and-set to prevent conflicts
        )
        
        # 3. Update downstream services to accept new credentials
        await self.propagate_new_credentials(agent_id, env, new_api_key)
        
        # 4. Wait for propagation (all instances pick up new creds)
        await asyncio.sleep(60)
        
        # 5. Verify new credentials work
        health = await self.health_check(agent_id, env, new_api_key)
        if not health.ok:
            # Rollback
            await self.vault.rollback(f"secret/ai-agents/{agent_id}/{env}")
            await self.alert(f"Secret rotation failed for {agent_id}/{env}")
            return
        
        # 6. Revoke old credentials
        await self.vault.destroy_version(
            path=f"secret/ai-agents/{agent_id}/{env}",
            version=health.previous_version
        )
        
        # 7. Audit
        await self.audit_log.record(
            event="secret_rotation",
            agent_id=agent_id,
            environment=env,
            status="success",
            rotated_at=datetime.utcnow()
        )
```

### Dashboard View (What the Platform Team Sees)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AGENT IDENTITY DASHBOARD                                               │
│                                                                         │
│  Agents: 50 | Healthy: 47 | Warning: 2 | Critical: 1                  │
│                                                                         │
│  ┌─────────────────────┬──────┬───────────┬──────────┬───────────────┐ │
│  │ Agent               │ Env  │ Last Rot. │ Next Rot.│ Status        │ │
│  ├─────────────────────┼──────┼───────────┼──────────┼───────────────┤ │
│  │ ai-support-agent    │ prod │ 3 days    │ 4 days   │ ✓ Healthy     │ │
│  │ ai-analytics-agent  │ prod │ 28 days   │ 2 days   │ ⚠ Due soon   │ │
│  │ ai-code-review      │ prod │ 45 days   │ OVERDUE  │ ✗ Critical    │ │
│  │ ai-onboarding       │ prod │ 1 day     │ 6 days   │ ✓ Healthy     │ │
│  │ ...                 │      │           │          │               │ │
│  └─────────────────────┴──────┴───────────┴──────────┴───────────────┘ │
│                                                                         │
│  Recent Events:                                                         │
│  14:23 - ai-support-agent/prod: Secret rotated successfully            │
│  14:20 - ai-code-review/prod: Rotation FAILED (downstream timeout)     │
│  13:55 - ai-analytics-agent/staging: New permission granted (kb:write) │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Approval Workflows: High-Risk AI Actions

### Scenario

An AI assistant can draft and send emails on behalf of executives. Sending to external recipients requires real-time manager approval.

### Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  REAL-TIME APPROVAL WORKFLOW                                            │
│                                                                         │
│  1. User: "Send this proposal to client@external.com"                  │
│                                                                         │
│  2. AI Agent classifies action risk:                                    │
│     ├─ Internal email → LOW (auto-approve)                             │
│     ├─ External email, < 5 recipients → MEDIUM (notify manager)        │
│     ├─ External email, > 5 recipients → HIGH (require approval)        │
│     └─ External email + attachment → HIGH (require approval)           │
│                                                                         │
│  3. For HIGH risk: Workflow triggers                                    │
│     ┌──────────────────────────────────────────────────┐              │
│     │ Slack notification to manager:                    │              │
│     │                                                   │              │
│     │ 🔔 AI Action Approval Required                    │              │
│     │ Agent: exec-assistant-ai                          │              │
│     │ User: john.doe@company.com                        │              │
│     │ Action: Send email                                │              │
│     │ To: client@external.com                           │              │
│     │ Subject: "Q4 Partnership Proposal"                │              │
│     │ Has attachment: Yes (proposal_v3.pdf, 2.4MB)      │              │
│     │                                                   │              │
│     │ [✓ Approve] [✗ Deny] [👁 View Full Content]      │              │
│     │                                                   │              │
│     │ Auto-deny in: 15 minutes                          │              │
│     └──────────────────────────────────────────────────┘              │
│                                                                         │
│  4. Manager clicks [Approve]                                           │
│                                                                         │
│  5. AI Agent receives approval webhook, executes action                │
│                                                                         │
│  6. Audit log records: who requested, who approved, what was sent      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class ApprovalWorkflow:
    RISK_CLASSIFICATIONS = {
        "send_email_internal": "low",
        "send_email_external": "high",
        "modify_crm_record": "medium",
        "delete_data": "critical",       # Requires 2 approvers
        "transfer_funds": "critical",
        "update_permissions": "high",
    }
    
    APPROVAL_REQUIREMENTS = {
        "low": {"approvers": 0, "timeout": 0},
        "medium": {"approvers": 0, "timeout": 0, "notify": True},
        "high": {"approvers": 1, "timeout_minutes": 15, "auto_action": "deny"},
        "critical": {"approvers": 2, "timeout_minutes": 30, "auto_action": "deny"},
    }
    
    async def request_approval(
        self, action: AIAction, user: User, context: dict
    ) -> ApprovalResult:
        risk = self.RISK_CLASSIFICATIONS.get(action.type, "high")
        requirements = self.APPROVAL_REQUIREMENTS[risk]
        
        if requirements["approvers"] == 0:
            if requirements.get("notify"):
                await self.notify_manager(user.manager, action, "info_only")
            return ApprovalResult(approved=True, auto=True)
        
        # Create approval request
        request_id = await self.db.create_approval_request(
            action=action,
            requester=user,
            approvers_needed=requirements["approvers"],
            timeout=timedelta(minutes=requirements["timeout_minutes"]),
            context=context,
        )
        
        # Notify approvers
        approvers = await self.get_approvers(user, action)
        for approver in approvers:
            await self.send_approval_notification(approver, request_id, action)
        
        # Wait for response (with timeout)
        result = await self.wait_for_approval(
            request_id, 
            timeout=requirements["timeout_minutes"] * 60
        )
        
        # Record decision
        await self.audit_log.record(
            request_id=request_id,
            action=action.type,
            requester=user.id,
            decision=result.decision,
            decided_by=result.approver_id,
            decided_at=result.timestamp,
            time_to_decision_seconds=result.duration,
        )
        
        return result
```

### Production Metrics

```
Approval Workflow Stats (30-day rolling):
- Total actions requiring approval: 3,847
- Auto-approved (low risk): 12,493
- Manager-approved: 3,201 (83.2%)
- Manager-denied: 412 (10.7%)
- Timed out (auto-denied): 234 (6.1%)
- Average time to approval: 4.2 minutes
- Escalations (manager unavailable): 89
```

---

## Access Control Audit: "What Did the AI Access?"

### The Compliance Question

A compliance officer asks: *"For user john.doe, show me every piece of data the AI accessed on his behalf in the last 30 days, and whether that access was authorized."*

### Audit Log Schema

```sql
CREATE TABLE ai_access_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Who
    user_id UUID NOT NULL,
    user_email TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_version TEXT NOT NULL,
    session_id UUID NOT NULL,
    
    -- What was accessed
    resource_type TEXT NOT NULL,  -- 'document', 'database_row', 'api_endpoint'
    resource_id TEXT NOT NULL,
    resource_name TEXT,
    resource_classification TEXT,
    
    -- How it was accessed
    access_type TEXT NOT NULL,  -- 'read', 'write', 'delete', 'search_result'
    access_method TEXT,         -- 'rag_retrieval', 'tool_call', 'context_injection'
    
    -- Authorization details
    authorization_decision TEXT NOT NULL,  -- 'allowed', 'denied', 'elevated'
    authorization_policy TEXT,  -- Which policy granted access
    token_id TEXT,
    token_scopes TEXT[],
    
    -- Context
    user_query TEXT,           -- What the user asked (may be redacted)
    ai_reasoning TEXT,         -- Why the AI accessed this resource
    
    -- Metadata
    request_id UUID,
    trace_id TEXT,
    environment TEXT DEFAULT 'production'
);

-- Index for compliance queries
CREATE INDEX idx_audit_user_time ON ai_access_audit(user_id, timestamp DESC);
CREATE INDEX idx_audit_resource ON ai_access_audit(resource_id, timestamp DESC);
```

### Real Audit Query Results

```sql
-- Compliance officer's query
SELECT 
    timestamp,
    agent_id,
    resource_type,
    resource_name,
    resource_classification,
    access_type,
    authorization_decision,
    authorization_policy,
    LEFT(user_query, 100) as query_preview
FROM ai_access_audit
WHERE user_id = 'usr_john_doe_123'
AND timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;
```

**Results:**

```
┌─────────────────────┬────────────────────┬───────────┬────────────────────────┬────────┬────────┬──────────┬────────────────────────────────────────────┐
│ timestamp           │ agent_id           │ res_type  │ resource_name          │ classif│ access │ decision │ query_preview                              │
├─────────────────────┼────────────────────┼───────────┼────────────────────────┼────────┼────────┼──────────┼────────────────────────────────────────────┤
│ 2024-03-15 14:22:01 │ support-agent      │ document  │ order_history_q1.pdf   │ internal│ read  │ allowed  │ "What was my last order?"                  │
│ 2024-03-15 14:22:01 │ support-agent      │ document  │ returns_policy.md      │ public │ read  │ allowed  │ "What was my last order?"                  │
│ 2024-03-14 09:11:33 │ analytics-agent    │ db_row    │ transactions.id=8834   │ confid.│ read  │ allowed  │ "Show me spending trends"                  │
│ 2024-03-14 09:11:33 │ analytics-agent    │ db_row    │ transactions.id=8835   │ confid.│ read  │ allowed  │ "Show me spending trends"                  │
│ 2024-03-14 09:11:33 │ analytics-agent    │ db_row    │ transactions.id=8836   │ confid.│ read  │ allowed  │ "Show me spending trends"                  │
│ 2024-03-12 16:45:00 │ email-agent        │ email     │ draft_proposal.eml     │ confid.│ write │ allowed  │ "Draft email to team about project X"      │
│ 2024-03-10 11:00:22 │ search-agent       │ document  │ competitor_analysis.pdf│ restric│ read  │ DENIED   │ "Find info on competitor pricing"          │
│ 2024-03-10 11:00:22 │ search-agent       │ document  │ market_report_pub.pdf  │ public │ read  │ allowed  │ "Find info on competitor pricing"          │
└─────────────────────┴────────────────────┴───────────┴────────────────────────┴────────┴────────┴──────────┴────────────────────────────────────────────┘
```

### Audit Summary Report (Auto-Generated for Compliance)

```markdown
## AI Access Audit Report
**User:** john.doe@company.com
**Period:** 2024-02-15 to 2024-03-15
**Generated:** 2024-03-15 by compliance-bot

### Summary
- Total AI-mediated accesses: 847
- Unique resources accessed: 234
- Access decisions:
  - Allowed: 831 (98.1%)
  - Denied: 16 (1.9%)
- Resource classifications accessed:
  - Public: 312 (37%)
  - Internal: 445 (53%)
  - Confidential: 74 (9%)
  - Restricted: 0 (0%) — 16 attempts denied

### Anomalies Detected
1. **2024-03-10 11:00** — Attempted access to RESTRICTED document 
   "competitor_analysis.pdf" via search-agent. Access DENIED by policy 
   "classification_ceiling_policy". User's clearance: CONFIDENTIAL.
   **Action:** No escalation needed (policy worked correctly).

2. **2024-03-08 22:45** — Unusual access time (10:45 PM). User accessed 
   47 documents via analytics-agent in 3 minutes.
   **Action:** Flagged for review. Determined to be legitimate batch report.

### Recommendations
- User has no access to RESTRICTED documents but attempted access once.
  Consider: Does the user need elevated clearance for their role?
```

---

## Summary: Auth & Authorization Design Principles for AI

1. **Pre-filter at the data layer** — Don't rely on application code to filter. Use RLS, namespace isolation, or vector DB filters.
2. **Token delegation with scope reduction** — Each hop in the chain gets fewer permissions and shorter TTL.
3. **Audit everything** — Every resource the AI touches must be logged with who, what, when, why.
4. **Tenant isolation is non-negotiable** — In regulated industries, use hard boundaries (separate collections/namespaces), not just metadata filters.
5. **Real-time approval for high-risk actions** — Don't let AI execute irreversible actions without human confirmation.
6. **Secret rotation is automated or it doesn't happen** — Manual rotation at scale (50+ agents) is a fiction.
7. **Zero-trust between components** — AI services don't trust each other implicitly. mTLS + policy enforcement everywhere.
8. **Defense in depth** — Pre-filter + post-filter + RLS. If one layer fails, others catch it.
9. **On-behalf-of is traceable** — The original user's identity flows through the entire chain for audit.
10. **Compliance queries must be instant** — If it takes 3 days to answer "what did the AI access?", your audit system failed.
