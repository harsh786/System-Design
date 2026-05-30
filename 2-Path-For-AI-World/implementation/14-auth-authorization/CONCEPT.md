# Authentication & Authorization for AI Systems

## Why Auth is Different in AI Systems

Traditional auth: User authenticates → requests resources → server checks permissions → returns data.

AI system auth: User authenticates → agent acts on behalf of user → agent calls tools → tools access data → data filtered by user permissions → response generated from permitted data only.

The fundamental challenge: **an AI agent is an intermediary that must never escalate privileges beyond what the user possesses.**

---

## 1. Authentication Methods

### 1.1 OAuth2 & OpenID Connect (OIDC)

OAuth2 provides delegated authorization. OIDC adds identity layer on top.

**Why critical for AI systems:**
- Users grant scoped access to agents (not full credentials)
- Agents can request specific scopes per tool
- Token refresh handles long-running agent tasks
- Token revocation immediately cuts agent access

**Flows relevant to AI:**
- Authorization Code + PKCE: User-facing AI apps
- Client Credentials: Service-to-service (agent → tool backend)
- Token Exchange (RFC 8693): User token → agent token → tool token
- On-Behalf-Of: Agent acts as user with reduced scope

### 1.2 JWT (JSON Web Tokens)

Stateless tokens carrying claims. In AI systems, JWTs carry:
- `sub`: User identity
- `scope`: Permitted operations
- `tenant_id`: Tenant isolation
- `agent_id`: Which agent is acting
- `tool_permissions`: Which tools the agent can invoke
- `exp`: Short expiry (minutes, not hours)

**Critical rule**: Agent JWTs must have SHORTER expiry than user JWTs. An agent should never outlive its delegator's session.

### 1.3 mTLS (Mutual TLS)

Service-to-service authentication where both parties present certificates.

**Use in AI systems:**
- Agent ↔ Tool backend communication
- Agent ↔ Vector DB connections
- Cross-service calls in agent pipelines
- Prevents man-in-the-middle between agent components

### 1.4 API Keys

Simple but dangerous. Use only for:
- Development/testing
- Server-to-server where mTLS is impractical
- Always with additional controls (IP allowlist, rate limits)

**Never**: Give an agent a user's API key. The agent should have its own scoped credential.

### 1.5 Service Accounts

Non-human identities for agents and tools. Each agent instance gets its own service account with:
- Minimum required permissions
- Audit trail tied to the service account
- Separate from any user's permissions
- Rotatable credentials

### 1.6 Short-Lived Tokens

For tool execution, generate tokens that:
- Expire in seconds to minutes (not hours)
- Are scoped to exactly one operation
- Cannot be reused
- Carry the full delegation chain (user → agent → tool)

### 1.7 Token Exchange (RFC 8693)

```
User Token (broad scope) 
  → Exchange → Agent Token (reduced scope, shorter TTL)
    → Exchange → Tool Token (single-operation scope, seconds TTL)
```

Each exchange REDUCES privilege. Never escalates.

### 1.8 On-Behalf-Of Flow

Agent requests a token that represents "agent acting on behalf of user":
- Token carries both agent identity AND user identity
- Downstream services see WHO requested AND WHO delegated
- Audit logs capture the full chain
- If user's permissions change, agent's derived permissions change immediately

---

## 2. Authorization Models

### 2.1 RBAC (Role-Based Access Control)

```
User → Role → Permissions
```

**In AI context:**
- Roles determine which tools an agent can use on behalf of user
- Role hierarchy: admin > editor > viewer
- Agent inherits user's role but can be further restricted

**Limitations**: Coarse-grained. A "viewer" might need access to some documents but not others.

### 2.2 ABAC (Attribute-Based Access Control)

```
IF user.department == "engineering" 
AND resource.classification <= "internal"
AND time.hour BETWEEN 9 AND 17
AND request.source == "corporate_network"
THEN allow
```

**In AI context:**
- Dynamic rules based on context (time, location, device, data classification)
- Can restrict agent behavior based on data sensitivity
- Enables nuanced policies impossible with RBAC alone

### 2.3 ReBAC (Relationship-Based Access Control)

```
User --member-of--> Team --owns--> Project --contains--> Document
User can access Document because of the relationship chain
```

**In AI context:**
- Natural for organizational hierarchies
- "Can this user's agent access this document?" = "Does a relationship path exist?"
- Efficient for permission-filtered retrieval (expand relationships → filter)
- Used by Google Zanzibar, AuthZed SpiceDB, Ory Keto

### 2.4 Row-Level Security

Database enforces that queries only return rows the user can see:
```sql
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id'));
```

**In AI context:**
- RAG queries against SQL databases automatically filtered
- Agent cannot accidentally retrieve cross-tenant data
- Enforcement at data layer, not application layer

### 2.5 Document-Level Permissions

Each document in the knowledge base has an ACL:
```json
{
  "doc_id": "doc_123",
  "acl": {
    "viewers": ["user_1", "group_engineering"],
    "editors": ["user_2"],
    "owners": ["user_3"]
  }
}
```

Vector search must respect these ACLs. Two approaches:
1. **Pre-filter**: Add ACL filter to vector query (faster, less accurate)
2. **Post-filter**: Retrieve more results, filter after (accurate, slower)

### 2.6 Tenant Isolation

Each tenant's data is completely invisible to other tenants:
- Separate vector namespaces per tenant
- Separate encryption keys per tenant
- Network-level isolation where possible
- No shared caches across tenants

### 2.7 Scoped Tool Permissions

Each tool declares required permissions:
```python
@tool(permissions=["files:read", "calendar:read"])
def search_files(query: str): ...

@tool(permissions=["email:send"])  
def send_email(to: str, body: str): ...
```

Agent can only invoke tools where user has ALL required permissions.

### 2.8 Policy Engines

Centralized policy evaluation (OPA, Cedar, Cerbos):
```rego
# OPA policy
allow {
    input.user.role == "engineer"
    input.action == "query"
    input.resource.classification != "restricted"
}
```

**Benefits for AI:**
- Policies are auditable, version-controlled
- Single source of truth for all authorization decisions
- Can be evaluated without code changes
- Supports complex multi-factor decisions

### 2.9 Approval Workflows

High-risk actions require human approval:
```
Agent wants to: delete_production_database
Policy says: requires approval from user.manager
Flow: Agent pauses → notification sent → manager approves/rejects → agent proceeds or aborts
```

---

## 3. Correct Pattern: Identity-Propagated Authorization

```
User logs in (OIDC)
  → Identity token issued
    → Agent receives delegated token (reduced scope)
      → Agent calls retriever WITH user's permissions
        → Vector DB returns ONLY documents user can access
          → Agent calls tool WITH user's permissions
            → Tool executes with LEAST PRIVILEGE
              → Action is AUDITED with full identity chain
```

**Key principles:**
1. User identity flows through EVERY layer
2. Each layer can only REDUCE permissions, never escalate
3. Every action is traceable to original user
4. Retrieval is filtered BEFORE the LLM sees data
5. Tools cannot do more than the user could do manually

---

## 4. Wrong Pattern: Super-Admin Agent

```
User logs in
  → Agent uses SHARED ADMIN CREDENTIAL
    → Agent queries ALL documents (no filtering)
      → Agent calls tools with FULL ADMIN ACCESS
        → No audit trail to original user
```

**Why this is catastrophic:**
- Prompt injection → admin-level data exfiltration
- No accountability (which user caused which action?)
- One compromised agent = full system compromise
- Violates principle of least privilege
- Compliance violations (SOC2, HIPAA, GDPR)

---

## 5. Identity Propagation in AI Systems

### The Challenge

In a traditional web app, the user's session is directly tied to their request. In AI systems, the agent is an intermediary — how do downstream services know WHO the agent is acting for?

### Solution: Delegation Chain

Every request in the agent pipeline carries:
```json
{
  "original_user": "user_123",
  "delegation_chain": [
    {"entity": "user_123", "granted_at": "2024-01-01T00:00:00Z"},
    {"entity": "agent_orchestrator", "granted_at": "2024-01-01T00:00:01Z"},
    {"entity": "retrieval_tool", "granted_at": "2024-01-01T00:00:02Z"}
  ],
  "effective_permissions": ["docs:read", "calendar:read"],
  "denied_permissions": ["docs:write", "admin:*"]
}
```

### Implementation Approaches

1. **Token-based**: Each hop exchanges token, new token carries history
2. **Header-based**: `X-Original-User` + `X-Delegation-Chain` headers (simpler, less secure)
3. **Context object**: Passed through agent framework's context (in-process only)

---

## 6. Permission-Filtered Retrieval

### The Problem

Vector similarity search returns the MOST SIMILAR documents. But the user might not have permission to see the most similar ones.

### Pre-Retrieval Filtering

```
1. Expand user's groups/roles → list of accessible ACL entries
2. Add filter to vector query: WHERE acl_entries OVERLAP user_access_list
3. Vector DB returns only matching + accessible documents
```

**Pros**: Efficient, no wasted retrieval
**Cons**: May miss semantically relevant results if user has limited access

### Post-Retrieval Filtering

```
1. Retrieve top-K * oversample_factor results (e.g., top-100 instead of top-10)
2. For each result, check user permissions
3. Return first K permitted results
```

**Pros**: Better semantic relevance
**Cons**: Slower, may need multiple rounds if many results filtered out

### Hybrid Approach (Recommended)

```
1. Pre-filter by tenant (hard boundary)
2. Pre-filter by broad access group (reduces search space)
3. Retrieve with oversample
4. Post-filter by specific document permissions
5. Return top-K permitted results
```

---

## 7. Tool-Level Authorization

Each tool invocation requires authorization check:

```python
async def execute_tool(tool_name: str, user_context: UserContext):
    tool = get_tool(tool_name)
    
    # Check: does user have ALL permissions this tool requires?
    if not user_context.has_permissions(tool.required_permissions):
        raise AuthorizationError(f"User lacks permissions for {tool_name}")
    
    # Check: is this tool approved for this user's role?
    if not policy_engine.evaluate(user_context, "invoke", tool_name):
        raise AuthorizationError(f"Policy denies {tool_name} for user role")
    
    # Generate short-lived token scoped to this tool execution
    tool_token = mint_tool_token(user_context, tool_name, ttl=30)
    
    # Execute with scoped token
    return await tool.execute(token=tool_token)
```

---

## 8. Multi-Tenant Isolation Patterns

### Namespace Isolation
- Each tenant gets its own vector DB namespace/collection
- Queries cannot cross namespace boundaries
- Even with bugs, data doesn't leak

### Encryption Isolation
- Each tenant's data encrypted with tenant-specific key
- Key rotation per tenant
- Compromised key affects only one tenant

### Compute Isolation
- Dedicated agent instances per tenant (highest isolation)
- Or: shared compute with strict context separation
- Never share in-memory caches across tenants

### Network Isolation
- Tenant-specific VPCs/VNets where required
- Network policies prevent cross-tenant traffic

---

## 9. Token Lifecycle in Agentic Systems

```
T=0s:   User authenticates, gets access_token (TTL: 1 hour)
T=1s:   Agent receives delegated token (TTL: 15 minutes)
T=2s:   Agent starts task, requests tool token (TTL: 30 seconds)
T=32s:  Tool token expires (single use)
T=5m:   Agent needs another tool, requests new tool token
T=15m:  Agent token expires, must re-request from user token
T=60m:  User token expires, user must re-authenticate
```

**Critical rules:**
- Each derived token has SHORTER TTL than its parent
- Tool tokens are single-use where possible
- Token refresh is proactive (before expiry, not after)
- Revocation propagates immediately (check revocation list)

---

## 10. Zero-Trust Architecture for AI Agents

### Principles

1. **Never trust, always verify**: Every request authenticated, even internal
2. **Least privilege**: Agents get minimum permissions for current task
3. **Assume breach**: Design as if any component could be compromised
4. **Verify explicitly**: Check permissions at every boundary, not just the edge

### Implementation

```
┌─────────────────────────────────────────────────┐
│ Every agent-to-service call:                      │
│  1. mTLS (identity of both parties verified)      │
│  2. JWT validation (delegation chain intact)      │
│  3. Permission check (does delegated user have    │
│     access to this specific resource?)            │
│  4. Rate limit check (is this within budget?)     │
│  5. Anomaly check (is this behavior expected?)    │
│  6. Audit log (record everything)                 │
└─────────────────────────────────────────────────┘
```

### Micro-segmentation for AI

- Agent orchestrator can reach retriever, not database directly
- Retriever can reach vector DB, not external APIs
- Tools can reach their specific backends, not other tools' backends
- LLM inference endpoint is isolated from data stores

---

## Summary: Auth Checklist for AI Systems

- [ ] User identity propagates to every downstream service
- [ ] Agents use delegated tokens, never user credentials
- [ ] Token TTLs decrease at each delegation hop
- [ ] Retrieval is filtered by user permissions BEFORE LLM sees data
- [ ] Each tool checks authorization independently
- [ ] Multi-tenant data is physically or logically isolated
- [ ] High-risk actions require human approval
- [ ] Every action is audited with full identity chain
- [ ] Policies are centralized and version-controlled
- [ ] Zero-trust: verify at every boundary
