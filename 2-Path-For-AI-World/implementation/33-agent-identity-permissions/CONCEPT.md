# Agent Identity and Runtime Permissioning

## Senior Principle

> **"The agent should never be a hidden super-admin."**

Every action an agent takes must be traceable to a user delegation, bounded by policy, scoped to minimum privilege, and auditable. The agent is a delegate, not an authority.

---

## 1. Agent Identity

Agents are not users. They are autonomous software entities that act within a system, and they need their own identity — separate from any human user — for several critical reasons:

### Why Agents Need Their Own Identity

1. **Attribution**: When an agent modifies a database row, who did it? If the agent uses the user's token directly, you lose visibility into whether the human or the agent performed the action.
2. **Boundary enforcement**: An agent identity allows you to set agent-specific rate limits, permission ceilings, and behavioral policies that don't apply to human users.
3. **Revocation**: If an agent is compromised or misbehaving, you revoke the agent's credentials without affecting the user.
4. **Multi-tenancy**: The same agent code may serve multiple users/tenants. Its identity is the stable anchor; user context is injected per-request.

### Agent Identity Properties

```
AgentIdentity {
    agent_id: UUID            # Globally unique, immutable
    agent_name: string        # Human-readable (e.g., "code-review-agent-v2")
    agent_type: enum          # AUTONOMOUS, INTERACTIVE, BATCH, ORCHESTRATOR
    owner: UserID | OrgID     # Who registered/owns this agent
    created_at: timestamp
    credential_ids: [UUID]    # Associated credentials (can be multiple)
    permission_boundary: PolicyDocument  # Maximum permissions regardless of delegation
    trust_level: enum         # INTERNAL, VERIFIED_EXTERNAL, UNVERIFIED_EXTERNAL
    metadata: map             # Version, description, capabilities
}
```

### Agent vs. User vs. Service Identity

| Property | User Identity | Agent Identity | Service Identity |
|----------|--------------|----------------|------------------|
| Authentication | Password, MFA, SSO | Client credentials, mTLS, signed JWT | API key, mTLS |
| Lifetime | Long-lived (years) | Medium (months, rotated) | Long-lived |
| Delegation | Delegates to agents | Receives delegation | N/A |
| Audit | "User X did Y" | "Agent A on behalf of User X did Y" | "Service S did Y" |
| Revocation | Account disable | Credential rotation | Key rotation |

---

## 2. User Identity Propagation

When a user interacts with an agent, the user's identity context must flow through the entire call chain. This is not optional — it's the foundation of authorization.

### The Propagation Chain

```
User (authenticated) 
  → Agent receives user context (user_id, roles, tenant, session_id)
    → Agent calls Tool A with user context embedded in request
      → Tool A calls downstream service with on-behalf-of token
        → Downstream service validates user authorization
```

### What Gets Propagated

- **user_id**: The authenticated user's unique identifier
- **tenant_id**: The organizational boundary
- **roles/claims**: The user's permissions at the time of delegation
- **session_id**: Correlates all actions to a single user session
- **delegation_id**: Links back to the specific delegation grant
- **correlation_id**: End-to-end tracing across all services

### Critical Rule: Never Lose User Context

If at any point in the chain the user context is dropped and replaced with the agent's own identity acting as admin, you have created a **confused deputy** vulnerability. The agent becomes a privilege escalation vector.

---

## 3. Service Identity (Agent-to-Service Authentication)

The agent authenticates to backend services using its own credentials (not the user's password). This is standard service-to-service authentication:

- **mTLS**: Agent presents its certificate; service validates against CA
- **Client credentials flow (OAuth2)**: Agent exchanges client_id + client_secret for an access token
- **Signed JWTs**: Agent signs a JWT with its private key; service validates with public key

The key insight: the agent authenticates as itself, but the authorization check is against the **user's permissions** (via on-behalf-of flow).

---

## 4. On-Behalf-Of Flow

This is the most critical pattern. The agent authenticates as itself but acts with the user's permissions (or a subset thereof).

### Flow

```
1. User authenticates to the platform (gets user_token)
2. User delegates to agent (creates delegation grant)
3. Agent requests OBO token: "I am agent A, acting on behalf of user U, for scope S"
4. Token service validates:
   - Agent identity is valid
   - Delegation grant exists and is active
   - Requested scope is within delegation scope
   - Requested scope is within agent's permission boundary
5. Token service issues OBO token:
   - Subject: user_id
   - Actor: agent_id
   - Scope: intersection(user_permissions, delegation_scope, agent_boundary)
   - Lifetime: short (minutes)
6. Agent uses OBO token to call tool/service
7. Service checks OBO token against its own policies
```

### Why Not Just Use the User's Token?

- User tokens are long-lived → agent compromise exposes user for extended period
- User tokens have full user scope → agent only needs a subset
- User tokens don't identify the agent → audit trail is incomplete
- User tokens can't be revoked without affecting the user's own sessions

---

## 5. Delegated Authorization

Delegation is the explicit grant from a user to an agent, specifying what the agent may do on the user's behalf.

### Delegation Grant Structure

```
DelegationGrant {
    delegation_id: UUID
    delegator: UserID         # The user granting permissions
    delegate: AgentID         # The agent receiving permissions
    scopes: [Scope]           # What the agent can do
    resources: [ResourcePattern]  # Which resources (glob patterns)
    constraints: {
        max_actions_per_hour: int
        allowed_time_window: TimeRange
        require_approval_for: [ActionPattern]
        ip_restrictions: [CIDR]
    }
    expires_at: timestamp     # Hard expiration
    revocable: bool           # Can be revoked before expiry
    created_at: timestamp
    status: ACTIVE | REVOKED | EXPIRED
}
```

### Scope Granularity

Scopes should be fine-grained:
- `repo:read` — read repository contents
- `repo:write:branch` — write to branches (not main)
- `issue:create` — create issues
- `deploy:staging` — deploy to staging (not production)
- `database:query:readonly` — run SELECT queries only

### The Intersection Rule

The effective permissions of an agent acting on behalf of a user are:

```
effective_permissions = intersection(
    user_current_permissions,    # What the user can do right now
    delegation_scopes,           # What the user delegated
    agent_permission_boundary,   # Agent's maximum ceiling
    tool_allowed_scopes          # What the specific tool supports
)
```

If any of these four sets doesn't include a permission, the agent doesn't have it.

---

## 6. Short-Lived Tool Tokens

Every token issued to a tool should be:

- **Short-lived**: 5-15 minutes maximum. If a tool execution takes longer, it re-requests.
- **Narrowly scoped**: Only the permissions needed for this specific tool invocation.
- **Single-use where possible**: Token is consumed and cannot be replayed.
- **Bound to context**: Token includes tool_id, action, resource — cannot be used for different actions.

### Why Short-Lived?

If a tool token is stolen (memory dump, log leak, network intercept):
- 5-minute token: attacker has 5 minutes of access to one specific action
- Permanent admin token: attacker has unlimited access forever

The cost of short-lived tokens is token refresh overhead. This is negligible compared to the security benefit.

---

## 7. Scoped Credentials (Per-Tool, Per-Action)

Each tool receives its own credential, scoped to exactly what it needs:

```
ToolCredential {
    token: string
    tool_id: ToolID
    action: ActionType         # e.g., "read_file", "write_database"
    resource: ResourceID       # e.g., "repo/main/src/*", "db/users/SELECT"
    user_id: UserID            # On whose behalf
    agent_id: AgentID          # Which agent is executing
    issued_at: timestamp
    expires_at: timestamp      # issued_at + 5 minutes
    max_uses: int              # 1 for single-use, N for batch operations
}
```

### Credential Isolation

- Tool A's credential cannot be used by Tool B
- A credential for `read_file` cannot be used for `write_file`
- A credential scoped to `repo-X` cannot access `repo-Y`
- Credentials are never shared between agent instances

---

## 8. Per-Tool Permission Checks

Before any tool executes, a permission check occurs:

```
PermissionCheck {
    Input:
        agent_id: who is the agent?
        user_id: on whose behalf?
        tool_id: which tool?
        action: what action?
        resource: on what resource?
        context: additional context (time, location, risk score)
    
    Checks:
        1. Is the agent identity valid and not revoked?
        2. Is the delegation grant active?
        3. Is this tool within the delegation scope?
        4. Is this action within the delegation scope?
        5. Is this resource within the delegation scope?
        6. Is the agent within its permission boundary?
        7. Does the user still have this permission? (real-time check)
        8. Are there rate limits being exceeded?
        9. Are there time-window restrictions?
        10. Is this action flagged for approval?
    
    Output:
        ALLOW | DENY | REQUIRE_APPROVAL
        reason: string
        constraints: any additional constraints on execution
}
```

### Policy Engine

Permission checks are evaluated by a policy engine (similar to AWS IAM or OPA):

```
# Policy example
{
    "effect": "allow",
    "agent_types": ["INTERACTIVE"],
    "actions": ["read_file", "list_directory"],
    "resources": ["repo/*/src/**"],
    "conditions": {
        "time_window": "09:00-17:00 UTC",
        "user_roles_include": ["developer"],
        "risk_score_below": 0.7
    }
}
```

---

## 9. Per-Action Approval

Some actions are too risky to execute automatically. They require explicit user approval:

### Risk Classification

| Risk Level | Examples | Approval Required |
|------------|----------|-------------------|
| LOW | Read file, list resources, query read-only | No |
| MEDIUM | Write to non-production, create branch | Configurable |
| HIGH | Delete resources, write to production, modify permissions | Always |
| CRITICAL | Deploy to production, modify security settings, access secrets | Always + MFA |

### Approval Flow

```
1. Agent determines it needs to execute a HIGH-risk action
2. Agent submits approval request:
   - What: "Delete 47 records from users table matching filter X"
   - Why: "User requested cleanup of test accounts"
   - Impact: "Irreversible data deletion"
   - Alternatives: "Could soft-delete instead"
3. User receives approval request (push notification, in-app, email)
4. User reviews and approves/denies
5. If approved: time-limited approval token issued (valid 5 min)
6. Agent executes with approval token
7. Action is audited with approval chain
```

### Approval Policies

```
ApprovalPolicy {
    actions: [ActionPattern]           # Which actions need approval
    approvers: [UserID | RoleID]       # Who can approve
    timeout: Duration                  # How long to wait for approval
    escalation: EscalationPolicy       # What happens on timeout
    require_mfa: bool                  # Additional authentication for approval
    allow_bulk: bool                   # Can multiple actions be approved at once
}
```

---

## 10. Just-in-Time Privilege

Agents should operate at minimum privilege and escalate only when needed:

### Normal Flow (Low Privilege)

```
Agent operates with: read-only access to non-sensitive resources
```

### Escalation Flow

```
1. Agent determines it needs elevated access
2. Agent requests JIT privilege: "I need write access to repo X for 10 minutes"
3. Policy engine evaluates:
   - Is this within the delegation scope?
   - Does the user have this permission?
   - Is there a policy allowing JIT escalation for this?
4. If allowed: temporary elevated credential issued
5. Agent performs privileged action
6. Credential expires (or agent explicitly releases it)
7. Agent returns to base privilege level
```

### Benefits

- Attack surface is minimized during normal operation
- Compromised agent at rest has minimal access
- Escalation events are highly auditable
- Forces agents to be explicit about why they need elevated access

---

## 11. Secret Isolation

**The agent should NEVER see raw secrets.** Secrets (API keys, passwords, connection strings) are:

### Secret Handling Architecture

```
User stores secret → Secret Manager (Vault)
Agent needs to call API that requires secret
Agent does NOT retrieve secret
Instead: Agent requests "call API X with method Y and payload Z"
         Secret injection happens at the gateway/sidecar level
         Agent receives only the result
```

### Implementation Patterns

1. **Sidecar proxy**: Agent calls localhost; sidecar injects credentials before forwarding
2. **Secret reference tokens**: Agent passes a reference ID; the tool runtime resolves it
3. **Sealed operations**: Agent describes the operation; a trusted executor adds secrets and runs it

### Why?

- If agent is compromised, attacker gets no secrets
- Secrets never appear in agent memory, logs, or traces
- Secret rotation doesn't require agent redeployment
- Agent code can be open-sourced without risk

---

## 12. Audit: Action as User+Agent

Every action must record BOTH the user and the agent:

### Audit Event Structure

```
AuditEvent {
    event_id: UUID
    timestamp: ISO8601
    
    # WHO
    user_id: UserID              # The human who delegated
    agent_id: AgentID            # The agent that executed
    delegation_id: DelegationID  # The delegation grant used
    
    # WHAT
    tool_id: ToolID              # Which tool
    action: string               # What action
    resource: ResourceID         # On what resource
    parameters: map              # With what parameters (sanitized)
    
    # CONTEXT
    session_id: SessionID        # User session correlation
    correlation_id: CorrelationID  # End-to-end trace
    risk_level: RiskLevel        # Computed risk of this action
    approval_id: ApprovalID?     # If approval was required
    
    # OUTCOME
    outcome: SUCCESS | FAILURE | DENIED
    error: string?               # If failed
    changes: ChangeSet?          # What was modified
    
    # METADATA
    tenant_id: TenantID
    environment: string          # prod, staging, dev
    agent_version: string
    policy_version: string       # Which policy was evaluated
}
```

### Audit Requirements

- **Immutable**: Once written, cannot be modified or deleted
- **Complete**: Every action, including denied ones
- **Searchable**: By user, agent, time range, resource, action
- **Real-time**: Available for monitoring within seconds
- **Retained**: Per compliance requirements (7 years for financial, etc.)

---

## 13. Tenant and Resource Boundaries

Agents must respect multi-tenancy:

### Boundary Rules

1. An agent acting for User A in Tenant X can NEVER access Tenant Y resources
2. Resource boundaries are enforced at the infrastructure level, not just policy
3. Cross-tenant operations require explicit cross-tenant delegation (rare, audited)
4. Agent credentials are tenant-scoped by default

### Resource Boundary Enforcement

```
ResourceBoundary {
    tenant_id: TenantID
    resource_types: [ResourceType]
    allowed_patterns: [GlobPattern]     # e.g., "org/team-a/**"
    denied_patterns: [GlobPattern]      # e.g., "org/team-a/secrets/**"
    network_boundaries: [NetworkPolicy] # e.g., VPC restrictions
}
```

---

## 14. Remote Agent Trust

When agents call other agents (multi-agent systems) or when external agents connect:

### Trust Levels

| Level | Description | Verification | Permissions |
|-------|-------------|--------------|-------------|
| INTERNAL | Same organization, same platform | mTLS with internal CA | High trust, policy-bounded |
| VERIFIED_EXTERNAL | Third-party, verified publisher | Signed identity, attestation | Medium trust, strict boundaries |
| UNVERIFIED_EXTERNAL | Unknown agent | Challenge-response only | Minimal trust, sandboxed |

### Remote Agent Authentication

```
1. Remote agent presents signed identity assertion
2. Platform verifies signature against known public keys
3. Platform checks agent registry for trust level and policies
4. Platform issues session-scoped credential for remote agent
5. All actions by remote agent are sandboxed and audited
6. Remote agent cannot escalate beyond its trust boundary
```

---

## 15. The Correct Pattern

```
USER AUTHENTICATES (MFA, SSO)
    ↓
USER DELEGATES TO AGENT (specific scopes, time-limited)
    ↓
AGENT RECEIVES USER CONTEXT (user_id, delegation_id, scopes)
    ↓
AGENT DETERMINES NEEDED ACTION
    ↓
POLICY ENGINE CHECKS (agent + user + tool + resource + context)
    ↓
    ├── DENIED → Action blocked, audit logged, user notified
    ├── REQUIRE_APPROVAL → Approval flow triggered
    └── ALLOWED → Continue
            ↓
SCOPED TOKEN GENERATED (tool-specific, short-lived, narrow scope)
    ↓
TOOL EXECUTES WITH SCOPED TOKEN
    ↓
ACTION AUDITED (user + agent + tool + action + outcome)
    ↓
TOKEN EXPIRES (or is revoked immediately after use)
```

---

## 16. The Wrong Pattern

```
❌ Agent has permanent admin API key
❌ Agent uses same credential for all tools
❌ Agent accesses secrets directly
❌ No user context in downstream calls
❌ No per-action permission checks
❌ No audit trail linking action to user
❌ Agent can access any tenant's data
❌ No approval for destructive actions
❌ Tokens never expire
❌ Agent identity cannot be revoked without system outage
```

### Why This Is Dangerous

- **Single point of compromise**: One leaked credential = total system access
- **No accountability**: Can't determine which user's request caused an action
- **No containment**: Compromised agent has unlimited blast radius
- **No compliance**: Fails every security audit and regulatory requirement
- **Privilege confusion**: Agent becomes an unaccountable super-admin

---

## 17. Design Principles Summary

1. **Least privilege**: Agent gets minimum permissions needed, nothing more
2. **Explicit delegation**: User explicitly grants, never implicit
3. **Short-lived credentials**: Minutes, not days
4. **Scoped credentials**: Per-tool, per-action, per-resource
5. **User context always flows**: Never lose the "on behalf of" chain
6. **Approval for risk**: Humans approve dangerous actions
7. **Complete audit**: Every action, both identities, searchable
8. **Secret isolation**: Agent never touches raw secrets
9. **Tenant isolation**: Hard boundaries between tenants
10. **Revocable**: Any credential, delegation, or identity can be instantly revoked
