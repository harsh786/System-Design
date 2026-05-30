# Authentication & Authorization Diagrams

## 1. End-to-End Auth Flow in AI Systems

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant IdP as Identity Provider (OIDC)
    participant Gateway as API Gateway
    participant Agent as AI Agent
    participant Retriever as Permission-Filtered Retriever
    participant VectorDB as Vector DB
    participant Tool as Tool Backend
    participant Audit as Audit Log

    User->>Frontend: Login
    Frontend->>IdP: Authorization Code + PKCE
    IdP-->>Frontend: ID Token + Access Token
    Frontend->>Gateway: Request + Bearer Token
    Gateway->>Gateway: Validate JWT (signature, expiry, issuer)
    Gateway->>Gateway: Extract permissions, tenant, roles
    Gateway->>Agent: Request + UserContext
    
    Note over Agent: Agent operates with user's permissions only
    
    Agent->>Agent: Exchange token (user → agent, reduced scope)
    Agent->>Retriever: Query + UserContext
    Retriever->>Retriever: Expand groups, build ACL filter
    Retriever->>VectorDB: Semantic search + ACL filter + tenant namespace
    VectorDB-->>Retriever: Filtered results (only permitted docs)
    Retriever->>Retriever: Post-retrieval permission verification
    Retriever-->>Agent: Permission-verified documents
    
    Agent->>Agent: Generate response from permitted data
    Agent->>Agent: Exchange token (agent → tool, single-use)
    Agent->>Tool: Execute with scoped tool token
    Tool->>Tool: Validate tool token, check permissions
    Tool-->>Agent: Tool result
    
    Agent-->>Gateway: Response
    Gateway->>Audit: Log full request chain
    Gateway-->>Frontend: Response
    Frontend-->>User: Display result
```

## 2. Token Exchange Flow (User → Agent → Tool)

```mermaid
sequenceDiagram
    participant User
    participant TokenService as Token Exchange Service
    participant Agent
    participant Tool

    Note over User: Access Token<br/>Scope: docs:read, calendar:*, email:send<br/>TTL: 1 hour<br/>Type: user

    User->>TokenService: Exchange(user_token, agent_id, scopes=[docs:read, calendar:read])
    TokenService->>TokenService: Validate user token
    TokenService->>TokenService: Intersect scopes (reduce only)
    TokenService->>TokenService: Set TTL = min(15min, user_token_remaining)
    TokenService->>TokenService: Add to delegation chain
    TokenService-->>Agent: Agent Token

    Note over Agent: Agent Token<br/>Scope: docs:read, calendar:read (REDUCED)<br/>TTL: 15 minutes (SHORTER)<br/>Type: agent<br/>original_user: user_123

    Agent->>TokenService: Exchange(agent_token, tool="calendar_search", perms=[calendar:read])
    TokenService->>TokenService: Validate agent token
    TokenService->>TokenService: Verify permissions subset
    TokenService->>TokenService: Set TTL = 30 seconds
    TokenService->>TokenService: Mark single_use = true
    TokenService-->>Tool: Tool Token

    Note over Tool: Tool Token<br/>Scope: calendar:read (MINIMAL)<br/>TTL: 30 seconds (SHORTEST)<br/>Type: tool<br/>single_use: true<br/>delegation_chain: [user→agent→tool]

    Tool->>Tool: Execute with minimal privilege
    Tool->>Tool: Token expires/consumed after single use
```

## 3. Permission-Filtered Retrieval

```mermaid
flowchart TD
    A[User Query + UserContext] --> B[Expand User Groups]
    B --> C[Build ACL Filter]
    
    C --> D{Partition Strategy}
    D -->|Namespace| E[Tenant Namespace Filter]
    D -->|Collection| F[Tenant-Specific Collection]
    D -->|Database| G[Tenant-Specific DB]
    
    E --> H[Pre-Filter: Tenant + Groups + Classification]
    F --> H
    G --> H
    
    H --> I[Vector Similarity Search<br/>with metadata filter]
    I --> J[Oversample Results<br/>top_k × 3]
    
    J --> K[Post-Retrieval Verification]
    K --> L{For each document}
    
    L -->|Check 1| M[Tenant matches?]
    M -->|No| N[REJECT]
    M -->|Yes| O[Classification ≤ clearance?]
    O -->|No| N
    O -->|Yes| P[User in ACL?]
    P -->|No| Q[User's groups in ACL?]
    Q -->|No| R[Document public in tenant?]
    R -->|No| N
    R -->|Yes| S[INCLUDE]
    P -->|Yes| S
    Q -->|Yes| S
    
    S --> T[Return top-K verified results]
    N --> U[Increment filtered_count]
    U --> L
    
    T --> V[Final Leakage Check]
    V --> W[Return to Agent]
```

## 4. RBAC / ABAC / ReBAC Comparison

```mermaid
flowchart LR
    subgraph RBAC["RBAC (Role-Based)"]
        direction TB
        U1[User] -->|assigned| R1[Role: Editor]
        R1 -->|grants| P1[docs:read]
        R1 -->|grants| P2[docs:write]
        R1 -->|inherits| R2[Role: Viewer]
        R2 -->|grants| P3[docs:read]
    end

    subgraph ABAC["ABAC (Attribute-Based)"]
        direction TB
        U2[User<br/>dept=engineering<br/>clearance=secret] --> Rule1{Rule Engine}
        Res[Resource<br/>classification=internal<br/>type=design_doc] --> Rule1
        Ctx[Context<br/>time=business_hours<br/>network=corporate] --> Rule1
        Rule1 -->|ALL conditions match| Dec1[ALLOW]
    end

    subgraph ReBAC["ReBAC (Relationship-Based)"]
        direction TB
        U3[User: alice] -->|member_of| T1[Team: AI]
        T1 -->|owns| Proj[Project: ML Platform]
        Proj -->|contains| Doc[Document: Design Spec]
        U3 -.->|can read via path| Doc
    end
```

## 5. Multi-Tenant Isolation Architecture

```mermaid
flowchart TB
    subgraph Ingress["Ingress Layer"]
        GW[API Gateway]
        GW --> TE[Tenant Extractor]
    end

    TE --> TC{Tenant Check}
    TC -->|Valid + Active| Route
    TC -->|Invalid/Inactive| Reject[403 Reject]

    subgraph Route["Tenant Routing"]
        RL[Rate Limiter] --> Budget[Budget Check]
        Budget --> Model[Model Router]
    end

    Model --> Tier{Tenant Tier}

    subgraph Free["Free/Starter (Shared)"]
        direction TB
        SharedAgent[Shared Agent Pool]
        SharedDB[(Shared DB<br/>namespace isolation)]
        SharedCache[(Shared Cache<br/>prefix isolation)]
    end

    subgraph Pro["Professional (Dedicated)"]
        direction TB
        DedicatedAgent[Dedicated Agent]
        DedicatedDB[(Dedicated Collection)]
        DedicatedCache[(Dedicated Cache)]
    end

    subgraph Ent["Enterprise (Isolated)"]
        direction TB
        IsolatedAgent[Isolated Agent<br/>Dedicated Compute]
        IsolatedDB[(Isolated Database<br/>Separate Cluster)]
        IsolatedCache[(Isolated Cache<br/>Dedicated Instance)]
        IsolatedNet[Private Network]
    end

    Tier -->|Free/Starter| Free
    Tier -->|Professional| Pro
    Tier -->|Enterprise| Ent

    subgraph Guards["Cross-Tenant Guards"]
        G1[Response Leakage Check]
        G2[Output Sanitization]
        G3[Audit Logging]
    end

    Free --> Guards
    Pro --> Guards
    Ent --> Guards
```

## 6. On-Behalf-Of Flow Sequence

```mermaid
sequenceDiagram
    participant User
    participant App as AI Agent App
    participant IdP as Identity Provider
    participant API1 as Retrieval Service
    participant API2 as Calendar API
    
    User->>App: Request (Bearer user_token)
    App->>App: Validate user_token
    
    Note over App: Need to call Retrieval Service<br/>as this user

    App->>IdP: OBO Request<br/>assertion=user_token<br/>scope=retrieval.read<br/>resource=retrieval-service
    IdP->>IdP: Validate user_token
    IdP->>IdP: Check user consented to scope
    IdP->>IdP: Mint OBO token<br/>sub=user, act=agent_app
    IdP-->>App: obo_token_1 (for retrieval service)

    App->>API1: Request (Bearer obo_token_1)
    API1->>API1: Validate token
    API1->>API1: See sub=user (apply user's permissions)
    API1->>API1: See act=agent_app (audit: agent acting)
    API1-->>App: Filtered results

    Note over App: Now need Calendar API<br/>with different scope

    App->>IdP: OBO Request<br/>assertion=user_token<br/>scope=calendar.read<br/>resource=calendar-api
    IdP-->>App: obo_token_2 (for calendar API)

    App->>API2: Request (Bearer obo_token_2)
    API2->>API2: Validate, enforce user permissions
    API2-->>App: Calendar events (user's only)

    App-->>User: Combined response
```

## 7. Authorization Decision Flow

```mermaid
flowchart TD
    Request[Authorization Request<br/>subject + action + resource + context] --> TenantCheck

    subgraph TenantCheck["Layer 1: Tenant Isolation"]
        T1{Resource belongs<br/>to requester's tenant?}
        T1 -->|No| DENY1[DENY - Tenant Violation]
    end
    T1 -->|Yes| PolicyEngine

    subgraph PolicyEngine["Layer 2: Policy Engine"]
        direction TB
        
        subgraph RBAC["RBAC Check"]
            R1[Get user roles]
            R1 --> R2[Expand role hierarchy]
            R2 --> R3{Permission exists?}
        end
        
        subgraph ABAC["ABAC Check"]
            A1[Get subject attributes]
            A1 --> A2[Get resource attributes]
            A2 --> A3[Evaluate context]
            A3 --> A4{Rules match?}
        end
        
        subgraph ReBAC_Check["ReBAC Check"]
            B1[Find relationship path]
            B1 --> B2{Path exists?}
        end
    end

    R3 --> Combine
    A4 --> Combine
    B2 --> Combine

    subgraph Combine["Layer 3: Combining Algorithm"]
        C1{Deny Overrides}
        C1 -->|Any DENY| DENY2[DENY]
        C1 -->|All ALLOW/ABSTAIN| C2{At least one ALLOW?}
        C2 -->|No| DENY3[DENY - Default]
        C2 -->|Yes| ALLOW1[ALLOW]
    end

    ALLOW1 --> ToolCheck

    subgraph ToolCheck["Layer 4: Tool-Specific"]
        TC1{Tool requires approval?}
        TC1 -->|Yes| Approval[Pause for human approval]
        TC1 -->|No| TC2{Within rate limit?}
        TC2 -->|No| DENY4[DENY - Rate Limited]
        TC2 -->|Yes| FINAL[ALLOW - Execute]
    end

    Approval -->|Approved| FINAL
    Approval -->|Rejected| DENY5[DENY - Rejected]

    FINAL --> Audit[Audit Log Entry]
    DENY1 --> Audit
    DENY2 --> Audit
    DENY3 --> Audit
    DENY4 --> Audit
    DENY5 --> Audit
```

## 8. Zero-Trust Architecture for AI Agents

```mermaid
flowchart TB
    subgraph External["External Boundary"]
        User[User Device]
    end

    subgraph Edge["Zero-Trust Edge"]
        WAF[WAF + DDoS Protection]
        IdProxy[Identity-Aware Proxy]
        MFA[MFA Verification]
    end

    subgraph AgentZone["Agent Compute Zone"]
        direction TB
        Orch[Agent Orchestrator]
        
        subgraph PerRequest["Per-Request Verification"]
            V1[mTLS Certificate Check]
            V2[JWT Validation]
            V3[Permission Evaluation]
            V4[Rate Limit Check]
            V5[Anomaly Detection]
        end
        
        Orch --> PerRequest
    end

    subgraph DataZone["Data Zone (Segmented)"]
        direction TB
        VDB[(Vector DB)]
        SQL[(SQL DB)]
        Cache[(Cache)]
        
        subgraph DataGuards["Data Access Guards"]
            RLS[Row-Level Security]
            Encrypt[Encryption at Rest]
            TenantFilter[Tenant Filter]
        end
    end

    subgraph ToolZone["Tool Zone (Segmented)"]
        direction TB
        Tool1[Search Tool]
        Tool2[Calendar Tool]
        Tool3[Email Tool]
        
        subgraph ToolGuards["Tool Guards"]
            ToolAuth[Per-Tool Auth]
            ToolScope[Scope Validation]
            ToolAudit[Action Audit]
        end
    end

    subgraph Monitoring["Continuous Monitoring"]
        AuditLog[Immutable Audit Log]
        Anomaly[Anomaly Detector]
        Alert[Alert System]
        Revoke[Auto-Revocation]
    end

    User --> Edge
    Edge --> AgentZone
    AgentZone -->|mTLS + scoped token| DataZone
    AgentZone -->|mTLS + tool token| ToolZone
    
    AgentZone --> Monitoring
    DataZone --> Monitoring
    ToolZone --> Monitoring
    
    Anomaly -->|Suspicious activity| Revoke
    Revoke -->|Invalidate tokens| AgentZone

    style External fill:#fee,stroke:#f00
    style Edge fill:#ffe,stroke:#f90
    style AgentZone fill:#eff,stroke:#09f
    style DataZone fill:#efe,stroke:#0a0
    style ToolZone fill:#fef,stroke:#90f
    style Monitoring fill:#eee,stroke:#666
```

## Key Design Principles Summary

| Principle | Implementation |
|-----------|---------------|
| Never trust, always verify | Every hop validates identity + permissions |
| Least privilege | Each token has minimum scope for its task |
| Defense in depth | Multiple layers: tenant → policy → tool → data |
| Assume breach | Short-lived tokens, single-use where possible |
| Identity propagation | Original user identity flows through all layers |
| Audit everything | Every decision logged with full delegation chain |
| Fail closed | Default deny, explicit allow only |
| Separation of concerns | Auth decisions separated from business logic |
