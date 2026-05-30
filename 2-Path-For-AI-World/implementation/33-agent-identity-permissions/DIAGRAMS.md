# Agent Identity and Permissions - Diagrams

## 1. Agent Identity Architecture

```mermaid
graph TB
    subgraph "Identity Layer"
        AIR[Agent Identity Registry]
        CM[Credential Manager]
        TV[Token Validator]
    end

    subgraph "Agent Identities"
        A1[Agent: code-review-bot<br/>Type: INTERACTIVE<br/>Trust: INTERNAL]
        A2[Agent: deploy-agent<br/>Type: AUTONOMOUS<br/>Trust: INTERNAL]
        A3[Agent: external-scanner<br/>Type: BATCH<br/>Trust: VERIFIED_EXTERNAL]
    end

    subgraph "Credential Store"
        CS[Client Secrets<br/>hashed, rotatable]
        CERT[Certificates<br/>X.509, mTLS]
        KEYS[Signing Keys<br/>RSA/EC key pairs]
    end

    subgraph "Boundaries"
        PB1[Permission Boundary<br/>repo:read, issue:create<br/>deny: admin:*]
        PB2[Permission Boundary<br/>deploy:staging, deploy:prod<br/>deny: database:*]
    end

    A1 --> AIR
    A2 --> AIR
    A3 --> AIR
    AIR --> CM
    CM --> CS
    CM --> CERT
    CM --> KEYS
    A1 --> PB1
    A2 --> PB2
    CM --> TV
```

## 2. On-Behalf-Of Flow Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant P as Platform
    participant A as Agent
    participant TS as Token Service
    participant PE as Policy Engine
    participant T as Tool
    participant S as Service

    U->>P: Authenticate (SSO/MFA)
    P->>U: user_token (session)
    
    U->>P: Delegate to Agent (scopes, resources, constraints)
    P->>P: Create DelegationGrant
    P->>U: delegation_id

    U->>A: Request action
    A->>A: Determine needed tools

    A->>TS: Request OBO token<br/>(agent_id, user_id, delegation_id, scope)
    TS->>TS: Validate agent identity
    TS->>TS: Validate delegation active
    TS->>TS: Compute intersection<br/>(user_perms ∩ delegation ∩ agent_boundary)
    TS->>A: OBO token (short-lived, narrow scope)

    A->>PE: Check permission (tool, action, resource)
    PE->>PE: Evaluate policies
    PE->>A: ALLOW + constraints

    A->>T: Execute with OBO token
    T->>T: Validate token scope
    T->>S: Call downstream with OBO context
    S->>S: Authorize (user_id from token)
    S->>T: Result
    T->>A: Tool result

    Note over A,S: Token expires in 5 minutes
    Note over A,S: Audit: user=U, agent=A, tool=T, action=X
```

## 3. Delegated Authorization Model

```mermaid
graph TB
    subgraph "User Permissions (Full)"
        UP[repo:read, repo:write, repo:delete<br/>deploy:staging, deploy:production<br/>database:read, database:write<br/>admin:users]
    end

    subgraph "Delegation Grant"
        DG[Delegated Scopes:<br/>repo:read, repo:write:branch<br/>database:read<br/><br/>Constraints:<br/>- 100 actions/hour<br/>- 09:00-17:00 UTC only<br/>- Approval for deploy:*<br/>- Expires in 8 hours]
    end

    subgraph "Agent Permission Boundary"
        APB[Allowed: repo:*, database:read<br/>Denied: admin:*, deploy:production<br/>Max token: 15 min<br/>Max actions: 1000/hr]
    end

    subgraph "Effective Permissions (Intersection)"
        EP[repo:read ✓<br/>repo:write:branch ✓<br/>database:read ✓<br/><br/>repo:delete ✗ not delegated<br/>deploy:* ✗ not in boundary<br/>admin:* ✗ denied by boundary<br/>database:write ✗ not delegated]
    end

    UP -->|"User delegates subset"| DG
    DG -->|"Intersect with boundary"| EP
    APB -->|"Agent ceiling"| EP

    style EP fill:#90EE90
```

## 4. Tool Permission Check Flow

```mermaid
flowchart TD
    Start[Agent requests tool execution] --> C1

    C1{Tool registered?}
    C1 -->|No| DENY1[DENY: Tool not registered]
    C1 -->|Yes| C2

    C2{Agent identity valid?}
    C2 -->|No| DENY2[DENY: Invalid agent]
    C2 -->|Yes| C3

    C3{Delegation active?}
    C3 -->|No| DENY3[DENY: Delegation expired/revoked]
    C3 -->|Yes| C4

    C4{Scopes in delegation?}
    C4 -->|No| DENY4[DENY: Scope not delegated]
    C4 -->|Yes| C5

    C5{Within agent boundary?}
    C5 -->|No| DENY5[DENY: Outside boundary]
    C5 -->|Yes| C6

    C6{User still has permission?}
    C6 -->|No| DENY6[DENY: User permission revoked]
    C6 -->|Yes| C7

    C7{Resource in allowed patterns?}
    C7 -->|No| DENY7[DENY: Resource not allowed]
    C7 -->|Yes| C8

    C8{Rate limit OK?}
    C8 -->|No| RL[RATE_LIMITED]
    C8 -->|Yes| C9

    C9{Risk requires approval?}
    C9 -->|Yes| APPROVAL[REQUIRE_APPROVAL]
    C9 -->|No| ALLOW

    ALLOW[ALLOW: Generate scoped token<br/>lifetime: 5 min<br/>scope: minimal<br/>single-use]

    style ALLOW fill:#90EE90
    style DENY1 fill:#FFB6C1
    style DENY2 fill:#FFB6C1
    style DENY3 fill:#FFB6C1
    style DENY4 fill:#FFB6C1
    style DENY5 fill:#FFB6C1
    style DENY6 fill:#FFB6C1
    style DENY7 fill:#FFB6C1
    style RL fill:#FFD700
    style APPROVAL fill:#FFD700
```

## 5. Just-in-Time Privilege Sequence

```mermaid
sequenceDiagram
    participant A as Agent
    participant JIT as JIT Service
    participant PE as Policy Engine
    participant U as User
    participant AW as Approval Workflow

    Note over A: Agent operates at BASE privilege<br/>(read-only, non-sensitive)

    A->>A: Determines write access needed
    A->>JIT: Request elevation<br/>(scopes: [repo:write], reason: "push fix", duration: 10min)

    JIT->>PE: Assess risk of requested scopes
    
    alt Low/Medium Risk
        PE->>JIT: AUTO-GRANT (within policy)
        JIT->>JIT: Create time-limited credential
        JIT->>A: Elevation granted<br/>(elevation_id, expires in 10min)
        
        A->>A: Perform privileged action
        A->>JIT: Release elevation
        JIT->>JIT: Revoke elevated credential
        
        Note over A: Returns to BASE privilege
    
    else High/Critical Risk
        PE->>JIT: REQUIRES APPROVAL
        JIT->>AW: Create approval request
        AW->>U: Notify (push/email/in-app)
        
        alt User Approves
            U->>AW: Approve (+ MFA if critical)
            AW->>JIT: Approval token
            JIT->>A: Elevation granted (5min)
            A->>A: Perform privileged action
            A->>JIT: Release elevation
        else User Denies / Timeout
            U->>AW: Deny
            AW->>JIT: Denied
            JIT->>A: Elevation denied
            Note over A: Remains at BASE privilege
        end
    end
```

## 6. Audit Trail Architecture

```mermaid
graph TB
    subgraph "Event Sources"
        TE[Tool Executions]
        PE[Permission Checks]
        DE[Delegation Events]
        AE[Approval Events]
    end

    subgraph "Audit Pipeline"
        EB[Event Builder<br/>sanitize params<br/>compute hash<br/>assign severity]
        
        subgraph "Parallel Processing"
            AS[Append-Only Store<br/>immutable<br/>indexed]
            RS[Real-time Stream<br/>pub/sub<br/>filtered]
            AD[Anomaly Detector<br/>pattern matching<br/>behavioral baselines]
        end
    end

    subgraph "Storage Tiers"
        HOT[HOT: 0-30 days<br/>Fast query<br/>Full detail]
        WARM[WARM: 30-365 days<br/>Slower query<br/>Full detail]
        COLD[COLD: 1-7 years<br/>Archive<br/>Compressed]
        FROZEN[FROZEN: Legal holds<br/>Cannot delete]
    end

    subgraph "Consumers"
        SM[Security Monitoring<br/>SOC dashboard]
        CR[Compliance Reports<br/>SOC2, GDPR, HIPAA]
        FR[Forensics<br/>incident investigation]
        AL[Alerts<br/>anomaly notifications]
    end

    TE --> EB
    PE --> EB
    DE --> EB
    AE --> EB
    
    EB --> AS
    EB --> RS
    EB --> AD

    AS --> HOT
    HOT --> WARM
    WARM --> COLD
    COLD --> FROZEN

    RS --> SM
    AS --> CR
    AS --> FR
    AD --> AL
```

## 7. Correct vs Wrong Pattern Comparison

```mermaid
graph LR
    subgraph "CORRECT Pattern ✓"
        direction TB
        C1[User authenticates<br/>MFA + SSO] --> C2
        C2[User delegates to agent<br/>scoped, time-limited] --> C3
        C3[Agent receives context<br/>user_id, scopes, constraints] --> C4
        C4[Policy engine checks<br/>every action, every tool] --> C5
        C5[Scoped token issued<br/>5 min, single tool, one resource] --> C6
        C6[Tool executes<br/>with minimal credential] --> C7
        C7[Action audited<br/>user + agent + outcome]
        
        style C1 fill:#90EE90
        style C2 fill:#90EE90
        style C3 fill:#90EE90
        style C4 fill:#90EE90
        style C5 fill:#90EE90
        style C6 fill:#90EE90
        style C7 fill:#90EE90
    end

    subgraph "WRONG Pattern ✗"
        direction TB
        W1[Agent deployed<br/>with admin API key] --> W2
        W2[Agent uses same key<br/>for all operations] --> W3
        W3[No user context<br/>agent acts as itself] --> W4
        W4[No per-action checks<br/>blanket access] --> W5
        W5[Token never expires<br/>permanent access] --> W6
        W6[No audit trail<br/>or incomplete audit] --> W7
        W7[Compromise = total access<br/>no containment]
        
        style W1 fill:#FFB6C1
        style W2 fill:#FFB6C1
        style W3 fill:#FFB6C1
        style W4 fill:#FFB6C1
        style W5 fill:#FFB6C1
        style W6 fill:#FFB6C1
        style W7 fill:#FFB6C1
    end
```

## 8. Multi-Agent Identity Relationships

```mermaid
graph TB
    subgraph "Orchestrator Agent"
        OA[Orchestrator Agent<br/>Type: ORCHESTRATOR<br/>Trust: INTERNAL<br/>Boundary: full team scope]
    end

    subgraph "Sub-Agents (Registered by Orchestrator)"
        SA1[Code Review Agent<br/>Type: INTERACTIVE<br/>Boundary: repo:read, issue:create<br/>Parent: Orchestrator]
        SA2[Test Runner Agent<br/>Type: BATCH<br/>Boundary: repo:read, test:execute<br/>Parent: Orchestrator]
        SA3[Deploy Agent<br/>Type: AUTONOMOUS<br/>Boundary: deploy:staging<br/>Parent: Orchestrator]
    end

    subgraph "External Agents"
        EA1[Security Scanner<br/>Trust: VERIFIED_EXTERNAL<br/>Issuer: security-vendor<br/>Boundary: repo:read ONLY]
        EA2[Unknown Agent<br/>Trust: UNVERIFIED_EXTERNAL<br/>Boundary: SANDBOXED<br/>Read-only, rate-limited]
    end

    subgraph "Identity Relationships"
        OA -->|"registers"| SA1
        OA -->|"registers"| SA2
        OA -->|"registers"| SA3
        
        SA1 -.->|"boundary ⊂ parent"| OA
        SA2 -.->|"boundary ⊂ parent"| OA
        SA3 -.->|"boundary ⊂ parent"| OA
    end

    subgraph "Trust Verification"
        TV[Remote Agent Verifier]
        EA1 -->|"signed assertion"| TV
        EA2 -->|"challenge-response"| TV
        TV -->|"VERIFIED"| EA1
        TV -->|"UNVERIFIED"| EA2
    end

    subgraph "User Delegation"
        U[User] -->|"delegates scopes"| OA
        U -.->|"indirectly delegates via orchestrator"| SA1
        U -.->|"indirectly delegates via orchestrator"| SA2
    end

    style OA fill:#4169E1,color:white
    style SA1 fill:#6495ED,color:white
    style SA2 fill:#6495ED,color:white
    style SA3 fill:#6495ED,color:white
    style EA1 fill:#FFA500
    style EA2 fill:#FF6347
```

## 9. Secret Isolation Architecture

```mermaid
sequenceDiagram
    participant A as Agent
    participant GW as Sidecar/Gateway
    participant VM as Vault Manager
    participant S as External Service

    Note over A: Agent NEVER sees raw secrets

    A->>GW: "Call GitHub API, method=GET, path=/repos/org/repo"
    Note over A,GW: Agent passes operation description,<br/>NOT credentials

    GW->>VM: Request secret for "github-api-token"
    VM->>VM: Validate agent + user authorization
    VM->>GW: secret_value (short-lived, in-memory only)

    GW->>S: GET /repos/org/repo<br/>Authorization: Bearer {secret_value}
    S->>GW: Response data

    GW->>GW: Wipe secret from memory
    GW->>A: Response data (no secret exposure)

    Note over A: Agent received result<br/>without ever seeing the API token
```

## 10. Complete System Integration

```mermaid
graph TB
    subgraph "User Layer"
        USER[Authenticated User]
    end

    subgraph "Delegation Layer"
        DG[Delegation Grant<br/>scopes + constraints + expiry]
    end

    subgraph "Agent Layer"
        AI[Agent Identity<br/>+ Permission Boundary]
        AC[Agent Credentials<br/>rotatable, revocable]
    end

    subgraph "Authorization Layer"
        PE[Policy Engine]
        JIT[JIT Privilege Service]
        AW[Approval Workflow]
    end

    subgraph "Token Layer"
        OBO[OBO Token Service<br/>short-lived, scoped]
        STG[Scoped Token Generator<br/>per-tool, per-action]
    end

    subgraph "Execution Layer"
        TC[Tool Permission Checker]
        RL[Rate Limiter]
        TG[Tool Execution Guard]
    end

    subgraph "Tool Layer"
        T1[Tool: File Reader]
        T2[Tool: DB Query]
        T3[Tool: Deploy]
    end

    subgraph "Audit Layer"
        AS[Audit Store<br/>immutable]
        AD[Anomaly Detection]
        RS[Real-time Stream]
        CR[Compliance Reports]
    end

    USER -->|"authenticates + delegates"| DG
    DG -->|"grants"| AI
    AI -->|"authenticated by"| AC

    AI -->|"requests action"| PE
    PE -->|"evaluates"| JIT
    PE -->|"triggers"| AW
    AW -->|"approval to"| USER

    PE -->|"allowed"| OBO
    OBO -->|"issues"| STG

    STG -->|"token to"| TC
    TC -->|"checks"| RL
    TC -->|"guards"| TG

    TG --> T1
    TG --> T2
    TG --> T3

    TG -->|"every action"| AS
    AS --> AD
    AS --> RS
    AS --> CR

    style USER fill:#4169E1,color:white
    style AS fill:#2E8B57,color:white
    style PE fill:#DAA520
```
