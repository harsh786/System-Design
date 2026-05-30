# MCP & A2A Protocol Diagrams

## 1. MCP Architecture (Host / Client / Server)

```mermaid
graph TB
    subgraph Host["HOST (e.g., Claude Desktop, IDE)"]
        LLM[LLM Engine]
        MC1[MCP Client 1]
        MC2[MCP Client 2]
        MC3[MCP Client 3]
        LLM --> MC1
        LLM --> MC2
        LLM --> MC3
    end

    subgraph Servers["MCP Servers"]
        S1[Database Server<br/>stdio transport]
        S2[GitHub Server<br/>HTTP+SSE transport]
        S3[File System Server<br/>stdio transport]
    end

    MC1 -->|"JSON-RPC over stdio"| S1
    MC2 -->|"JSON-RPC over HTTP"| S2
    MC3 -->|"JSON-RPC over stdio"| S3

    S1 --> DB[(PostgreSQL)]
    S2 --> GH[GitHub API]
    S3 --> FS[Local Files]
```

## 2. MCP Request/Response Flow

```mermaid
sequenceDiagram
    participant User
    participant Host
    participant Client as MCP Client
    participant Server as MCP Server
    participant Tool as External Service

    User->>Host: Ask question
    Host->>Client: initialize
    Client->>Server: initialize (protocol version, capabilities)
    Server-->>Client: serverInfo, capabilities

    Host->>Client: tools/list
    Client->>Server: tools/list
    Server-->>Client: [tool definitions]
    Client-->>Host: Available tools

    Host->>Host: LLM decides to use tool
    Host->>User: Request approval (high-risk)
    User-->>Host: Approve

    Host->>Client: tools/call (name, arguments)
    Client->>Server: tools/call
    Server->>Server: Validate input
    Server->>Server: Check authorization
    Server->>Tool: Execute operation
    Tool-->>Server: Result
    Server->>Server: Audit log
    Server-->>Client: ToolResult (content)
    Client-->>Host: Tool output
    Host->>Host: LLM incorporates result
    Host-->>User: Final answer
```

## 3. A2A Task Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> submitted: Task received

    submitted --> working: Agent starts processing
    submitted --> failed: Validation error
    submitted --> canceled: Client cancels

    working --> completed: Success
    working --> failed: Error
    working --> input_required: Need more info
    working --> canceled: Client cancels

    input_required --> working: Input provided
    input_required --> failed: Timeout
    input_required --> canceled: Client cancels

    completed --> [*]
    failed --> [*]
    canceled --> [*]

    note right of submitted: Task queued
    note right of working: Agent processing
    note right of input_required: Waiting for user/agent input
    note right of completed: Artifacts available
    note right of failed: Error details in status
```

## 4. Agent Card Discovery Flow

```mermaid
sequenceDiagram
    participant Orchestrator as Orchestrator Agent
    participant Registry as Agent Registry
    participant Target as Target Agent
    participant WellKnown as /.well-known/agent.json

    Orchestrator->>Registry: Query: "Find agent for expense processing"
    Registry-->>Orchestrator: [AgentCard URLs matching query]

    Orchestrator->>WellKnown: GET /.well-known/agent.json
    WellKnown-->>Orchestrator: Agent Card (name, skills, auth, capabilities)

    Orchestrator->>Orchestrator: Evaluate delegation policy
    Orchestrator->>Orchestrator: Select best agent for task

    Note over Orchestrator: Authentication
    Orchestrator->>Target: POST /oauth/token (client_credentials)
    Target-->>Orchestrator: access_token

    Orchestrator->>Target: tasks/send (with bearer token)
    Target-->>Orchestrator: Task {id, status: "submitted"}

    loop Poll until complete
        Orchestrator->>Target: tasks/get {id}
        Target-->>Orchestrator: Task {status: "working"}
    end

    Target-->>Orchestrator: Task {status: "completed", artifacts: [...]}
```

## 5. Tool Registry Approval Workflow

```mermaid
flowchart TD
    A[Developer submits tool] --> B{Auto-classify risk}

    B -->|Low| C[Auto-approve]
    B -->|Medium| D[Team Lead Review]
    B -->|High| E[Security Review]
    B -->|Critical| F[CISO Review]

    C --> G[Published to Registry]

    D --> H{Decision}
    E --> H
    F --> H

    H -->|Approve| I[Run integration tests]
    H -->|Reject| J[Return with feedback]
    H -->|Request Changes| K[Developer revises]

    K --> B

    I -->|Pass| G
    I -->|Fail| L[Block publication]

    G --> M[Monitor usage]
    M --> N{Anomaly detected?}
    N -->|Yes| O[Auto-revoke + alert]
    N -->|No| M

    subgraph Risk Classification
        B
        R1[Read-only, no PII → Low]
        R2[Writes, notifications → Medium]
        R3[PII, financial, external → High]
        R4[Irreversible, compliance → Critical]
    end
```

## 6. MCP vs A2A Decision Tree

```mermaid
flowchart TD
    A[Need to extend AI capabilities] --> B{What type of capability?}

    B -->|"Deterministic function<br/>(query, lookup, CRUD)"| C{Requires multi-step reasoning?}
    B -->|"Complex task requiring<br/>planning & judgment"| D[Use A2A]
    B -->|"Data access<br/>(files, DBs)"| E[Use MCP Resource]

    C -->|No| F[Use MCP Tool]
    C -->|Yes| G{Can be decomposed into<br/>independent subtasks?}

    G -->|Yes| H[Use A2A with specialist agents]
    G -->|No| I[Use MCP Tool with<br/>multi-step orchestration in host]

    F --> J["Examples:<br/>• SQL query<br/>• API call<br/>• File read/write<br/>• Search index"]

    D --> K["Examples:<br/>• Process expense report<br/>• Research topic<br/>• Code review<br/>• Customer onboarding"]

    H --> L["Examples:<br/>• Research + Write + Review<br/>• Collect data + Analyze + Report"]

    style F fill:#4CAF50,color:white
    style D fill:#2196F3,color:white
    style H fill:#9C27B0,color:white
    style E fill:#FF9800,color:white
```

## 7. Multi-Agent Delegation Sequence

```mermaid
sequenceDiagram
    participant User
    participant Supervisor as Supervisor Agent
    participant Policy as Delegation Policy
    participant Approval as Approval System
    participant Research as Research Agent
    participant Writing as Writing Agent
    participant Review as Review Agent

    User->>Supervisor: "Write a market analysis report"

    Supervisor->>Supervisor: Plan: Research → Write → Review

    Note over Supervisor,Policy: Step 1: Delegate Research
    Supervisor->>Policy: Can I delegate to Research Agent?
    Policy-->>Supervisor: ✓ Allowed (low risk, no approval needed)
    Supervisor->>Research: tasks/send "Research market trends for Q4"
    Research-->>Supervisor: {status: "working"}
    Research-->>Supervisor: {status: "completed", artifacts: [research_data]}

    Note over Supervisor,Approval: Step 2: Delegate Writing
    Supervisor->>Policy: Can I delegate to Writing Agent?
    Policy-->>Supervisor: ✓ Allowed (medium risk, no approval needed)
    Supervisor->>Writing: tasks/send "Write report based on {research_data}"
    Writing-->>Supervisor: {status: "input-required", message: "What tone?"}
    Supervisor->>Writing: tasks/send "Professional, executive audience"
    Writing-->>Supervisor: {status: "completed", artifacts: [draft_report]}

    Note over Supervisor,Approval: Step 3: Delegate Review (requires approval)
    Supervisor->>Policy: Can I delegate to Review Agent?
    Policy-->>Supervisor: ✓ Allowed but requires human approval
    Supervisor->>Approval: Request approval for review delegation
    Approval->>User: "Supervisor wants to send report to Review Agent. Approve?"
    User-->>Approval: Approved
    Approval-->>Supervisor: Approved

    Supervisor->>Review: tasks/send "Review this report for accuracy"
    Review-->>Supervisor: {status: "completed", artifacts: [reviewed_report]}

    Supervisor-->>User: Final report with review notes
```

## 8. Security Layer Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        UI[User Interface]
        Auth[User Authentication]
    end

    subgraph "Orchestration Layer"
        GW[API Gateway]
        RL[Rate Limiter]
        OA[OAuth2 Authorization Server]
    end

    subgraph "Policy Layer"
        PE[Policy Engine]
        DP[Delegation Policies]
        TP[Tool Permissions]
        RiskEngine[Risk Classification Engine]
    end

    subgraph "Execution Layer"
        MCPHost[MCP Host]
        A2ASupervisor[A2A Supervisor]
    end

    subgraph "MCP Servers (Sandboxed)"
        S1[SQL Server<br/>Container]
        S2[Code Exec<br/>gVisor Sandbox]
        S3[CRM Server<br/>Container]
    end

    subgraph "A2A Agents"
        AG1[Research Agent]
        AG2[Writing Agent]
        AG3[Payment Agent]
    end

    subgraph "Observability"
        AL[Audit Logs]
        TR[Distributed Tracing]
        AN[Anomaly Detection]
        DASH[Security Dashboard]
    end

    UI --> Auth
    Auth --> GW
    GW --> RL
    RL --> OA
    OA --> PE

    PE --> MCPHost
    PE --> A2ASupervisor

    MCPHost --> S1
    MCPHost --> S2
    MCPHost --> S3

    A2ASupervisor --> AG1
    A2ASupervisor --> AG2
    A2ASupervisor --> AG3

    PE --> DP
    PE --> TP
    PE --> RiskEngine

    S1 --> AL
    S2 --> AL
    S3 --> AL
    AG1 --> TR
    AG2 --> TR
    AG3 --> TR
    AL --> AN
    TR --> AN
    AN --> DASH

    style PE fill:#FF5722,color:white
    style AL fill:#795548,color:white
    style AN fill:#E91E63,color:white
    style OA fill:#3F51B5,color:white
```

## 9. Combined MCP + A2A System Architecture

```mermaid
graph LR
    subgraph "User Interaction"
        U[User]
        CI[Chat Interface]
    end

    subgraph "Orchestrator Agent"
        ORC[Orchestrator<br/>LLM + Planning]
        MCP_C[MCP Clients]
        A2A_C[A2A Client]
    end

    subgraph "MCP Tools (Simple Operations)"
        T1[🔍 Search Tool]
        T2[📊 SQL Query Tool]
        T3[📅 Calendar Tool]
        T4[📁 File Tool]
    end

    subgraph "A2A Agents (Complex Tasks)"
        AG1[📝 Report Agent<br/>Planning + Writing]
        AG2[💰 Finance Agent<br/>Analysis + Compliance]
        AG3[🔬 Research Agent<br/>Search + Synthesis]
    end

    subgraph "Agent's Own MCP Tools"
        AG1_T[Writing Tools<br/>Grammar, Style]
        AG2_T[Financial Tools<br/>Calculations, Data]
        AG3_T[Search Tools<br/>Web, Papers, DBs]
    end

    U --> CI
    CI --> ORC
    ORC --> MCP_C
    ORC --> A2A_C

    MCP_C --> T1
    MCP_C --> T2
    MCP_C --> T3
    MCP_C --> T4

    A2A_C -->|"Task delegation"| AG1
    A2A_C -->|"Task delegation"| AG2
    A2A_C -->|"Task delegation"| AG3

    AG1 --> AG1_T
    AG2 --> AG2_T
    AG3 --> AG3_T
```
