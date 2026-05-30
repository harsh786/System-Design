# Multi-Agent Systems — Diagrams

## 1. Supervisor-Worker Architecture

```mermaid
graph TB
    User[User/Client] --> Supervisor
    
    subgraph Orchestration
        Supervisor[Supervisor Agent<br/>Task Decomposition<br/>Quality Verification]
    end
    
    subgraph Workers
        W1[Research Worker]
        W2[Code Worker]
        W3[Analysis Worker]
        W4[Writing Worker]
    end
    
    subgraph Safeguards
        Budget[Cost Budget]
        Timeout[Timeout Monitor]
        CB[Circuit Breakers]
    end
    
    Supervisor -->|assign| W1
    Supervisor -->|assign| W2
    Supervisor -->|assign| W3
    Supervisor -->|assign| W4
    
    W1 -->|result| Supervisor
    W2 -->|result| Supervisor
    W3 -->|result| Supervisor
    W4 -->|result| Supervisor
    
    Supervisor --- Budget
    Supervisor --- Timeout
    W1 --- CB
    W2 --- CB
    W3 --- CB
    W4 --- CB
    
    Supervisor -->|aggregated result| User
```

## 2. Router-Specialist Flow

```mermaid
flowchart TD
    Query[User Query] --> Router
    
    Router{Router Agent}
    Router -->|Rule Match| RuleEngine[Rule-Based<br/>Keywords/Regex]
    Router -->|Ambiguous| LLMClassify[LLM Classification]
    
    RuleEngine --> Confidence{Confidence<br/>> threshold?}
    LLMClassify --> Confidence
    
    Confidence -->|High| Route[Route to Specialist]
    Confidence -->|Low| Clarify[Ask Clarification]
    Confidence -->|None| Fallback[Generalist Fallback]
    
    Route --> Billing[Billing Specialist]
    Route --> Technical[Technical Specialist]
    Route --> Onboarding[Onboarding Specialist]
    
    Billing --> HealthCheck{Healthy?}
    Technical --> HealthCheck
    Onboarding --> HealthCheck
    
    HealthCheck -->|Yes| Execute[Execute & Respond]
    HealthCheck -->|No| Fallback
    
    Execute --> Response[Response to User]
    Fallback --> Response
    Clarify --> Query
```

## 3. Planner-Executor Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant P as Planner Agent
    participant H as Human Approver
    participant E as Executor Agent
    participant T as Tools
    
    U->>P: Goal: "Build rate limiter"
    P->>P: Decompose into steps
    P->>P: Estimate cost & time
    P->>P: Validate plan (no cycles, criteria)
    P->>H: Present plan for approval
    H->>P: Approved ✓
    
    loop For each step in plan
        P->>E: Execute Step N
        E->>T: Call required tool
        T->>E: Tool result
        E->>E: Check success criteria
        
        alt Step succeeded
            E->>P: Result + cost
            P->>P: Checkpoint progress
        else Step failed (retries exhausted)
            E->>P: Failure + context
            P->>P: Replan from failure point
            P->>H: Approve revised plan?
            H->>P: Approved ✓
        end
    end
    
    P->>U: Final aggregated result
```

## 4. Debate-Judge Protocol

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant A as Proposer A
    participant B as Proposer B
    participant J as Judge
    
    O->>A: Problem statement
    O->>B: Problem statement
    
    Note over A,B: Phase 1: Independent Proposals
    A->>O: Solution A (with evidence)
    B->>O: Solution B (with evidence)
    
    Note over A,B: Phase 2: Cross-Critique
    O->>A: Critique Solution B
    O->>B: Critique Solution A
    A->>O: Critique of B (weaknesses found)
    B->>O: Critique of A (weaknesses found)
    
    Note over A,B: Phase 3: Rebuttals
    O->>A: Defend against B's critique
    O->>B: Defend against A's critique
    A->>O: Rebuttal with counter-evidence
    B->>O: Rebuttal with counter-evidence
    
    Note over J: Phase 4: Judgment
    O->>J: All solutions + debate history
    J->>J: Score each criterion
    J->>J: Evaluate evidence quality
    
    alt Scores too close
        J->>O: Request another round
        Note over A,B: Additional round...
    else Clear winner
        J->>O: Winner + reasoning + scores
    end
    
    O->>O: Return final verdict
```

## 5. Multi-Agent Communication Patterns

```mermaid
graph LR
    subgraph "1. Request-Response"
        A1[Agent A] -->|request| B1[Agent B]
        B1 -->|response| A1
    end
    
    subgraph "2. Publish-Subscribe"
        A2[Agent A] -->|publish| EB[Event Bus]
        EB -->|notify| B2[Agent B]
        EB -->|notify| C2[Agent C]
    end
    
    subgraph "3. Blackboard"
        A3[Agent A] -->|write| BB[Shared State]
        B3[Agent B] -->|read| BB
        C3[Agent C] -->|read/write| BB
    end
    
    subgraph "4. Pipeline"
        A4[Agent A] -->|output| B4[Agent B] -->|output| C4[Agent C]
    end
    
    subgraph "5. Hierarchical"
        S[Supervisor] -->|assign| W1[Worker 1]
        S -->|assign| W2[Worker 2]
        W1 -->|report| S
        W2 -->|report| S
    end
```

## 6. Autonomy Levels Decision Tree

```mermaid
flowchart TD
    Start[New Agent Task] --> Reversible{Is the action<br/>reversible?}
    
    Reversible -->|No| HighRisk{High cost<br/>if wrong?}
    Reversible -->|Yes| Frequency{How frequent<br/>is this task?}
    
    HighRisk -->|Yes| L1[L1: Human approves<br/>every action]
    HighRisk -->|No| Regulated{Regulatory<br/>requirements?}
    
    Regulated -->|Yes| L2[L2: Human<br/>approves plan]
    Regulated -->|No| L3[L3: Bounded<br/>autonomous]
    
    Frequency -->|Rare| Proven{Agent proven<br/>reliable?}
    Frequency -->|Frequent| Proven
    
    Proven -->|No| L2
    Proven -->|Yes, <1000 runs| L3
    Proven -->|Yes, >1000 runs<br/>low error rate| L4[L4: Monitored<br/>autonomous]
    
    L4 --> FullyProven{Error rate < 0.01%<br/>AND low-risk<br/>AND reversible?}
    FullyProven -->|Yes| L5[L5: Fully<br/>autonomous]
    FullyProven -->|No| L4
    
    style L1 fill:#ff6b6b
    style L2 fill:#feca57
    style L3 fill:#48dbfb
    style L4 fill:#0abde3
    style L5 fill:#10ac84
```

## 7. Failure Mode Detection

```mermaid
flowchart TD
    Monitor[Orchestrator Monitor] --> Check1{Token count<br/>growing between<br/>agents?}
    Check1 -->|Yes| F1[🚨 Token Explosion<br/>Fix: Summarize at handoff]
    Check1 -->|No| Check2{Cost rate<br/>> expected?}
    
    Check2 -->|Yes| F2[🚨 Cost Explosion<br/>Fix: Global budget + circuit breaker]
    Check2 -->|No| Check3{Delegation<br/>cycle detected?}
    
    Check3 -->|Yes| F3[🚨 Circular Delegation<br/>Fix: Max depth + graph tracking]
    Check3 -->|No| Check4{Task unhandled<br/>> 30s?}
    
    Check4 -->|Yes| F4[🚨 Unclear Ownership<br/>Fix: Default handler + responsibility matrix]
    Check4 -->|No| Check5{Agent outputs<br/>contradict?}
    
    Check5 -->|Yes| F5[🚨 Conflicting Instructions<br/>Fix: Global invariants + hierarchy]
    Check5 -->|No| Check6{Quality metrics<br/>degrading?}
    
    Check6 -->|Yes| F6[🚨 Weak Evals<br/>Fix: Per-agent validation + E2E tests]
    Check6 -->|No| Check7{Agent using<br/>unexpected tools?}
    
    Check7 -->|Yes| F7[🚨 Overly Broad Permissions<br/>Fix: Least privilege per agent]
    Check7 -->|No| Check8{Iteration count<br/>> max?}
    
    Check8 -->|Yes| F8[🚨 No Termination<br/>Fix: Max iterations + done criteria]
    Check8 -->|No| OK[✅ System Healthy]
```

## 8. Multi-Agent Orchestration Architecture

```mermaid
graph TB
    subgraph Client Layer
        User[User/API Client]
    end
    
    subgraph Orchestration Layer
        Orch[Orchestrator]
        Registry[Agent Registry]
        Router[Message Router]
        State[Shared State Store]
        Budget[Budget Controller]
        Monitor[Health Monitor]
        Log[Audit Logger]
    end
    
    subgraph Agent Layer
        A1[Agent 1<br/>Research]
        A2[Agent 2<br/>Code Gen]
        A3[Agent 3<br/>Review]
        A4[Agent 4<br/>Deploy]
    end
    
    subgraph Tool Layer
        T1[Search API]
        T2[Code Exec]
        T3[Linters]
        T4[CI/CD]
    end
    
    subgraph Safety Layer
        Kill[Kill Switch]
        CB[Circuit Breakers]
        Trace[Distributed Tracing]
    end
    
    User --> Orch
    Orch --> Registry
    Orch --> Router
    Orch --> State
    Orch --> Budget
    Orch --> Monitor
    Orch --> Log
    
    Router --> A1
    Router --> A2
    Router --> A3
    Router --> A4
    
    A1 --> T1
    A2 --> T2
    A3 --> T3
    A4 --> T4
    
    Monitor --> CB
    Kill --> Orch
    Log --> Trace
    
    A1 -.->|read/write| State
    A2 -.->|read/write| State
    A3 -.->|read/write| State
```

## 9. Agent Composition Strategies

```mermaid
flowchart TD
    subgraph "Decomposition (Breaking Down)"
        Complex[Complex Agent<br/>Full-Stack Dev] --> FE[Frontend Agent]
        Complex --> BE[Backend Agent]
        Complex --> DB[Database Agent]
        Complex --> Test[Testing Agent]
    end
    
    subgraph "When to Decompose"
        D1[System prompt > 2000 words]
        D2[Needs conflicting personas]
        D3[Tool set too broad]
        D4[Different parts need different models]
        D5[Team wants independent dev/test]
    end
    
    subgraph "Composition (Building Up)"
        Search[Search Agent] --> Research[Research Agent]
        Summarize[Summarize Agent] --> Research
        
        Code[Code Agent] --> TDD[TDD Agent]
        UnitTest[Test Agent] --> TDD
    end
    
    subgraph "When to Compose"
        C1[Two agents always called together]
        C2[Context loss at boundary]
        C3[Latency of handoff unacceptable]
        C4[Agents too granular]
    end
    
    subgraph "Decision"
        Q1{Does single agent<br/>have too many<br/>responsibilities?}
        Q1 -->|Yes| Decompose[Decompose]
        Q1 -->|No| Q2{Are multiple agents<br/>always used together<br/>with context loss?}
        Q2 -->|Yes| Compose[Compose]
        Q2 -->|No| KeepAsIs[Keep Current Structure]
    end
```
