# Authentication & Authorization for AI Systems

## Why Auth for AI is More Complex

Traditional auth answers: "Can this user access this resource?" AI auth must answer a harder question: **"Can THIS user, through THIS agent, using THIS tool, access THIS data, for THIS purpose?"**

The analogy: Traditional auth is like checking someone's badge at a door. AI auth is like checking a badge for someone who sent their assistant, who might use various tools, and who might ask for things their boss can access but they can't.

---

## Authentication Methods

### API Keys (Simple but Risky)

```python
# Simple but dangerous - treat like passwords
headers = {"Authorization": "Bearer sk-abc123..."}
```

**Pros:** Simple to implement, low latency.
**Cons:** No expiration by default, no scope limitation, easily leaked in code/logs, no user identity.

**When to use:** Internal services, development, low-risk prototypes.

### OAuth2/OIDC (Recommended for Production)

The standard for production AI systems. Users authenticate through an identity provider, get scoped tokens.

```
User → Login → Identity Provider → Access Token (scoped) → AI Service
```

**Pros:** Industry standard, supports scopes, token expiration, refresh tokens, third-party integration.
**Cons:** More complex to implement, token management overhead.

### JWT Tokens (Stateless Verification)

```python
# JWT contains user identity and permissions
{
  "sub": "user-123",
  "roles": ["analyst"],
  "permissions": ["read:reports", "query:public-data"],
  "department": "finance",
  "exp": 1700000000
}
```

**Pros:** Stateless (no DB lookup needed), self-contained claims, fast validation.

### Service-to-Service Auth (mTLS)

For AI microservices communicating with each other:
```
AI Gateway ←mTLS→ Embedding Service ←mTLS→ Vector DB
```

---

## Authorization Models

### RBAC (Role-Based Access Control)

```
Roles:
  admin → can access all documents, all tools, all models
  analyst → can query data, use standard models, no tool execution
  viewer → can only ask questions, no data export
```

**Simple but coarse.** Works for small teams, breaks down with complex requirements.

### ABAC (Attribute-Based Access Control)

Decisions based on attributes of user, resource, environment:

```python
def can_access(user, resource, action):
    return (
        user.clearance_level >= resource.classification_level
        and user.department in resource.allowed_departments
        and action in user.permitted_actions
        and current_time in user.active_hours
    )
```

**Flexible but complex.** Good for enterprises with nuanced access rules.

### ReBAC (Relationship-Based Access Control)

Authorization based on relationships between entities (like Google Zanzibar):

```
user:alice is owner of document:budget-2024
user:bob is member of team:finance
team:finance is viewer of folder:financial-reports
document:budget-2024 is in folder:financial-reports
→ Therefore: bob can view document:budget-2024
```

### Policy-as-Code (OPA/Cedar)

```rego
# OPA policy for AI access
allow {
    input.user.role == "analyst"
    input.action == "query"
    input.resource.classification != "top-secret"
    input.resource.department == input.user.department
}
```

---

## Auth Flow for AI Systems

```mermaid
sequenceDiagram
    participant U as User
    participant GW as API Gateway
    participant AUTH as Auth Service
    participant AI as AI Orchestrator
    participant RAG as RAG System
    participant VDB as Vector DB

    U->>GW: Request + JWT Token
    GW->>AUTH: Validate Token
    AUTH-->>GW: Token Valid + Claims (roles, dept, clearance)
    GW->>AI: Request + User Context
    AI->>RAG: Query + Permission Filter
    RAG->>VDB: Search WHERE department IN user.departments AND classification <= user.clearance
    VDB-->>RAG: Filtered Results (only authorized docs)
    RAG-->>AI: Authorized Context Only
    AI-->>GW: Response (built from authorized data only)
    GW-->>U: Response
    
    Note over GW,AI: Audit log: who accessed what, when, why
```

---

## Permission-Aware RAG

This is critical: your RAG system must filter results based on who's asking.

```python
def permission_aware_search(query: str, user: User) -> list[Document]:
    # Build filter based on user permissions
    permission_filter = {
        "department": {"$in": user.departments},
        "classification_level": {"$lte": user.clearance_level},
        "access_groups": {"$in": user.groups},
    }
    
    # Search with filter applied at the vector DB level
    results = vector_db.search(
        query=query,
        filter=permission_filter,  # User only sees authorized docs
        top_k=10
    )
    return results
```

**Without this:** A junior employee could ask "What are the executive compensation details?" and the RAG system would happily retrieve and summarize board-level documents.

---

## The "Confused Deputy" Problem

The confused deputy problem: an AI agent has broad permissions (it needs them to serve many users), but a user tricks it into using those permissions on their behalf.

**Example:**
- AI agent has access to all company documents (to serve all employees)
- User asks: "Summarize the HR investigation file about my colleague John"
- Agent has access, user doesn't — but the agent doesn't check user permissions before retrieving

**Solution:** The agent must always check: "Does THIS user have access to what I'm about to retrieve/do?"

```python
def handle_request(request, user):
    # Don't just check if the AGENT can access it
    # Check if the USER (through the agent) should access it
    if not user_authorized(user, request.target_resource):
        return "You don't have permission to access that information."
    
    # Only then proceed
    return process_with_agent(request)
```

---

## Agent Identity

When an AI agent acts on behalf of a user, we need dual identity:

```python
class AgentContext:
    agent_identity: str      # "customer-service-bot-v2"
    user_identity: str       # "user-123"
    delegated_scopes: list   # ["read:orders", "update:address"]
    
    # The agent can ONLY do what the user has delegated
    # Even if the agent technically has broader capabilities
```

**Token delegation:** User grants the agent a subset of their own permissions:
```
User permissions: [read:all, write:own, admin:none]
Delegated to agent: [read:own-orders, read:product-catalog]
                    ↑ Subset of user's permissions
```

---

## Token Scope Limitation

Always issue the narrowest possible token:

```python
# BAD: Agent gets full access
token = issue_token(scopes=["*"])

# GOOD: Agent gets only what's needed for this interaction
token = issue_token(
    scopes=["read:user-profile", "read:order-history"],
    subject=user_id,
    expires_in=300,  # 5 minutes
    audience="customer-service-ai"
)
```

**Principle of least privilege** is even more important for AI because:
1. AI behavior is less predictable than traditional code
2. Prompt injection can redirect the AI's actions
3. The blast radius of a compromised AI with broad permissions is enormous

---

## Key Takeaways

1. **Never give AI agents more permissions than the user they serve**
2. **Filter data at retrieval time**, not after the LLM sees it (too late by then)
3. **Use short-lived, narrowly-scoped tokens** for all AI service interactions
4. **Audit everything** — who asked what, what was retrieved, what was returned
5. **Treat the AI agent as an untrusted intermediary** between user and data

---

## Staff-Level: Anti-Patterns, Trade-offs, and AI-Specific Auth Challenges

### Anti-Patterns in AI Authentication/Authorization

**1. Shared API Keys Across Users**
A single API key for all users means: no per-user audit trail, no per-user rate limiting, no way to revoke one user's access without affecting all, and if leaked, everyone is compromised. In AI systems this is worse because conversation history may be shared across the key's scope. Every user must have their own identity flowing through the entire AI pipeline — from API gateway through to vector DB queries.

**2. No Per-User Rate Limits**
Without per-user rate limiting, one abusive user can exhaust your entire LLM budget. More critically, automated attacks (model extraction, data exfiltration via repeated queries) look like normal traffic in aggregate but are obvious per-user. Rate limits should be: per-user, per-endpoint, per-time-window, AND per-cost-unit (tokens consumed, not just requests).

**3. Storing Conversation History Without Access Control**
Teams store all conversations in a shared database. Problems: support agents can read customer conversations, other users' context bleeds into responses if session isolation fails, and regulatory requirements (GDPR deletion) become impossible. Conversation history needs the same access control rigor as any sensitive data store — encrypted, access-controlled, with retention policies.

**4. Over-Privileged AI Agents**
The agent needs to call 3 APIs, so the team gives it admin access to everything "to avoid permission errors." Now a prompt injection attack has admin-level blast radius. AI agents should have the MINIMUM permissions needed for their current task, ideally scoped per-request, not per-deployment. If an agent needs database access for analytics queries, it gets SELECT on specific tables — not a DBA role.

### Trade-offs in AI Auth Architecture

| Trade-off | Option A | Option B | Staff Guidance |
|-----------|----------|----------|----------------|
| Token-based vs Session-based | JWT tokens (stateless, scalable, can't revoke instantly) | Server-side sessions (revocable, requires session store) | JWTs for short-lived operations (<5min). Session tokens for long-running agent tasks that may need emergency revocation. |
| Per-request vs Per-session auth | Authorize every tool call individually (secure, high latency) | Authorize at session start, cache decision (fast, stale permissions) | Hybrid: authorize at session start, re-authorize for high-risk tool calls. Cache low-risk decisions for 60s. |
| User impersonation vs Delegation | Agent uses user's actual credentials (simple, dangerous) | Agent has own identity + delegated scopes (complex, safer) | Always delegation. Agent identity + user context. Never let agents hold user credentials. Use OAuth2 token exchange (RFC 8693). |
| Coarse vs Fine-grained permissions | Role-based (admin/user/viewer — simple, over-permissive) | Attribute-based (field-level, context-aware — precise, complex) | Start RBAC, add ABAC for sensitive resources. Field-level access control for RAG (some users see redacted fields). |

### AI-Specific Auth Challenges

**The Agent Acting on Behalf of User Problem:**
Traditional OAuth2 has the "on-behalf-of" flow, but AI agents create new challenges:
- The agent may need to chain multiple services (user → agent → service A → service B)
- Each hop needs to carry the original user's authorization context
- The agent shouldn't accumulate permissions across multiple users it serves
- Long-running agent tasks may outlive the user's session/token

**Solution pattern — Token Exchange Chain:**
```
User token (broad) → Exchange for agent-scoped token (narrow) → 
Each tool call gets a purpose-specific token (narrowest)
```

**The Multi-Tenant Agent Problem:**
A single agent deployment serves multiple organizations. It must:
- Never mix context between tenants (tenant A's docs never appear for tenant B)
- Enforce tenant-specific policies (tenant A allows external search, tenant B doesn't)
- Maintain separate rate limits and budgets per tenant
- Support tenant-specific model configurations and guardrails

**The Autonomous Agent Auth Problem:**
When agents operate autonomously (scheduled tasks, background processing), who is the "user"?
- Service accounts with explicit scope documentation
- Time-bounded permissions that auto-expire
- Mandatory human approval for actions above a risk threshold
- Full audit trail attributing every action to the originating authorization grant

### Staff Interview Insight

A staff-level answer to "How would you design auth for an AI agent system?" demonstrates:
1. Understanding that the agent is an untrusted intermediary (confused deputy awareness)
2. Token scoping strategy (narrow, short-lived, purpose-bound)
3. Separation of agent identity from user identity
4. Data-layer enforcement (permissions at the DB/vector store level, not just application logic)
5. Monitoring strategy (detect permission escalation attempts, anomalous access patterns)
