# Agent Fundamentals — Diagrams

## 1. Basic Agent Loop (State Diagram)

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Observing: receive_goal
    Observing --> Planning: input_received
    Planning --> Acting: plan_ready
    Acting --> Observing: action_executed
    Observing --> Evaluating: observation_received
    Evaluating --> Planning: goal_not_met
    Evaluating --> Completed: goal_met
    Evaluating --> Failed: unrecoverable_error
    Planning --> Failed: max_steps_exceeded
    Acting --> Failed: timeout
    Completed --> [*]
    Failed --> [*]

    note right of Planning
        LLM reasons about current state,
        decides next action based on
        observations so far.
    end note

    note right of Acting
        Execute tool call, API request,
        code execution, or final response.
    end note
```

## 2. ReAct Agent Flow

```mermaid
flowchart TD
    START([User Goal]) --> THINK

    subgraph REACT_LOOP["ReAct Loop (max N steps)"]
        THINK["💭 THOUGHT\n(Chain-of-thought reasoning)"]
        ACT["⚡ ACTION\n(Tool call or respond)"]
        OBS["👁️ OBSERVATION\n(Tool result or error)"]

        THINK --> ACT
        ACT --> |tool_call| OBS
        OBS --> THINK
    end

    ACT --> |respond| RESPOND([Final Response])
    ACT --> |escalate| ESCALATE([Human Handoff])

    THINK --> |max_steps| TIMEOUT([Timeout/Max Steps])

    style THINK fill:#e1f5fe
    style ACT fill:#fff3e0
    style OBS fill:#e8f5e9
```

## 3. State Machine Agent with Transitions

```mermaid
stateDiagram-v2
    [*] --> intake

    intake --> classify: input_validated
    intake --> error_state: validation_failed

    classify --> simple_path: intent=simple
    classify --> complex_path: intent=complex
    classify --> escalation: intent=unknown

    simple_path --> response: answer_found
    simple_path --> complex_path: needs_more_info

    complex_path --> approval: high_risk_action
    complex_path --> execution: low_risk_action

    approval --> execution: human_approved
    approval --> escalation: human_rejected

    execution --> verification: action_complete
    execution --> retry: action_failed
    retry --> execution: retry_count<3
    retry --> error_state: retry_count>=3

    verification --> response: verified_ok
    verification --> execution: verification_failed

    response --> [*]
    escalation --> [*]
    error_state --> [*]

    note right of approval
        Human-in-the-loop gate
        for high-value actions
    end note

    note right of retry
        Exponential backoff
        with circuit breaker
    end note
```

## 4. Autonomy Levels Decision Tree

```mermaid
flowchart TD
    START{Is the action<br/>reversible?}

    START -->|No| IRR{High value?<br/>above $1000 or<br/>legal/compliance}
    START -->|Yes| REV{Real-time<br/>response needed?}

    IRR -->|Yes| L1["🔒 L1: Confirmation Required\n\nHuman approves every action\nExample: Fund transfers"]
    IRR -->|No| L2A["🔐 L2: Bounded Autonomy\n\nAgent acts within strict limits\nExample: Small refunds < $50"]

    REV -->|Yes| RT{Accuracy<br/>critical?}
    REV -->|No| NRT{Accuracy<br/>critical?}

    RT -->|Yes| L3["👁️ L3: Monitored Autonomy\n\nAgent acts, human reviews async\nExample: Live chat support"]
    RT -->|No| L4A["🚀 L4: Full Autonomy (recoverable)\n\nAgent operates independently\nExample: Auto-scaling infrastructure"]

    NRT -->|Yes| L2B["🔐 L2: Bounded Autonomy\n\nStrict guardrails + escalation\nExample: Content moderation"]
    NRT -->|No| L4B["🚀 L4: Full Autonomy (recoverable)\n\nRun freely, monitor after\nExample: Test generation"]

    style L1 fill:#ffcdd2
    style L2A fill:#fff9c4
    style L2B fill:#fff9c4
    style L3 fill:#c8e6c9
    style L4A fill:#bbdefb
    style L4B fill:#bbdefb
```

## 5. Agent Improvement Loop

```mermaid
flowchart TD
    PROD["📊 Production Traffic\n(Agent serves users)"]
    COLLECT["📝 Trace Collector\n(Log every execution)"]
    CLUSTER["🔍 Failure Clustering\n(Group by error type, tool, intent)"]
    ROOT["🏷️ Root Cause Labeling\n(Map to improvement lever)"]
    LEVER["🔧 Apply Lever\n(Prompt/Tool/Graph/Memory/Model)"]
    EVAL["✅ Golden Eval Set\n(Run against held-out tests)"]
    CANARY["🐤 Canary Release\n(5% traffic, 24-48h)"]
    MONITOR["📈 Monitor Metrics\n(Success rate, latency, cost)"]
    PROMOTE["🎉 Promote to 100%"]
    ROLLBACK["⏪ Rollback"]

    PROD --> COLLECT
    COLLECT --> CLUSTER
    CLUSTER --> ROOT
    ROOT --> LEVER
    LEVER --> EVAL

    EVAL -->|"passes + no regression"| CANARY
    EVAL -->|"fails or regresses"| LEVER

    CANARY --> MONITOR
    MONITOR -->|"improvement confirmed"| PROMOTE
    MONITOR -->|"regression detected"| ROLLBACK
    MONITOR -->|"inconclusive"| CANARY

    PROMOTE --> PROD
    ROLLBACK --> ROOT

    style PROD fill:#e3f2fd
    style EVAL fill:#e8f5e9
    style CANARY fill:#fff8e1
    style ROLLBACK fill:#ffebee
```

## 6. Agent Control Patterns Comparison

```mermaid
flowchart LR
    subgraph DETERMINISTIC["Pattern: Deterministic Workflow"]
        D1[Step 1] --> D2[Step 2] --> D3[Step 3] --> D4[Step 4]
    end

    subgraph ROUTER["Pattern: LLM Router"]
        R_IN[Input] --> R_LLM{LLM\nClassify}
        R_LLM -->|A| R_A[Handler A]
        R_LLM -->|B| R_B[Handler B]
        R_LLM -->|C| R_C[Handler C]
    end

    subgraph BOUNDED["Pattern: Bounded Loop"]
        B_START[Start] --> B_THINK[Think]
        B_THINK --> B_ACT[Act]
        B_ACT --> B_CHECK{Done?\nor\nmax steps?}
        B_CHECK -->|No| B_THINK
        B_CHECK -->|Yes| B_END[End]
    end

    subgraph SUPERVISOR["Pattern: Supervisor-Worker"]
        S_SUP[Supervisor] --> S_W1[Worker 1]
        S_SUP --> S_W2[Worker 2]
        S_SUP --> S_W3[Worker 3]
        S_W1 --> S_SYN[Synthesize]
        S_W2 --> S_SYN
        S_W3 --> S_SYN
    end
```

## 7. Human-in-the-Loop Approval Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant T as Tools
    participant H as Human Reviewer
    participant S as System

    U->>A: Request (goal)
    A->>A: Plan steps

    loop For each step
        A->>A: Assess risk level

        alt Low Risk (routine)
            A->>T: Execute tool
            T-->>A: Result
        else Medium Risk (notable)
            A->>S: Log for async review
            A->>T: Execute tool
            T-->>A: Result
            S-->>H: Notification (async)
        else High Risk (critical)
            A->>H: Request approval
            Note over A,H: Agent PAUSES here

            alt Approved
                H-->>A: ✅ Approved
                A->>T: Execute tool
                T-->>A: Result
            else Rejected
                H-->>A: ❌ Rejected (with reason)
                A->>A: Revise plan
            else Modified
                H-->>A: 🔄 Modified action
                A->>T: Execute modified action
                T-->>A: Result
            end
        end
    end

    A->>U: Final response
    A->>S: Log complete trace
```

## 8. Agent Types Selection Flowchart

```mermaid
flowchart TD
    START{What is the\ntask nature?}

    START -->|"Single Q&A\nor lookup"| SIMPLE["✅ Simple Tool-Calling Agent\n\n1-3 tool calls, immediate response"]

    START -->|"Known process\nwith fixed steps"| WORKFLOW["✅ Workflow Agent\n\nState machine, deterministic,\ncompliance-friendly"]

    START -->|"Complex reasoning\nunknown steps"| COMPLEX{How much\nautonomy?}

    START -->|"Multiple domains\nor intents"| ROUTER["✅ Router Agent\n\nClassify → dispatch to specialist"]

    START -->|"Real-time voice\nconversation"| VOICE["✅ Voice Agent\n\nStreaming, low-latency,\ninterrupt handling"]

    START -->|"Images, video,\nor mixed media"| MULTI["✅ Multimodal Agent\n\nProcess/generate\nmultiple modalities"]

    COMPLEX -->|"Agent decides\neverything"| AUTO{Is output\nquality critical?}
    COMPLEX -->|"Human approves\nactions"| HIL["✅ Human-in-the-Loop Agent\n\nPause at critical decisions"]
    COMPLEX -->|"Plan first,\nthen execute"| PLAN["✅ Planner-Executor Agent\n\nVisible plan before execution"]

    AUTO -->|Yes| REFLECT{Need multiple\nperspectives?}
    AUTO -->|No| REACT["✅ ReAct Agent\n\nThought-Action-Observation loop\nDefault choice for unknown complexity"]

    REFLECT -->|Yes| MULTI_AGENT["✅ Multi-Agent / Debate\n\nMultiple agents check each other"]
    REFLECT -->|No| REFLECTION["✅ Reflection Agent\n\nGenerate → Critique → Refine"]

    START -->|"Real transactions\n(money, bookings)"| TRANSACT["✅ Transactional Agent\n\nACID-like guarantees,\nconfirmation, rollback"]

    START -->|"Parallel sub-tasks\nrequiring coordination"| SUPERVISOR["✅ Supervisor Agent\n\nOrchestrate specialized workers"]

    START -->|"Code is better\nthan reasoning"| CODE["✅ Code-Execution Agent\n\nWrite + run code in sandbox"]

    START -->|"Gather + synthesize\nfrom many sources"| RESEARCH["✅ Research Agent\n\nSearch → Read → Extract → Cite"]

    style SIMPLE fill:#c8e6c9
    style WORKFLOW fill:#c8e6c9
    style REACT fill:#c8e6c9
    style ROUTER fill:#bbdefb
    style SUPERVISOR fill:#bbdefb
    style PLAN fill:#fff9c4
    style HIL fill:#fff9c4
    style REFLECTION fill:#e1bee7
    style MULTI_AGENT fill:#e1bee7
    style TRANSACT fill:#ffcdd2
    style VOICE fill:#ffe0b2
    style MULTI fill:#ffe0b2
    style CODE fill:#b2dfdb
    style RESEARCH fill:#b2dfdb
```
