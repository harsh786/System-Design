# What is Agent-to-Agent (A2A) Protocol?

## The Problem: Isolated AI Agents

Imagine a company with multiple AI agents:
- A **Research Agent** that searches databases and papers
- A **Writing Agent** that drafts documents
- A **Review Agent** that checks quality

Today, these agents are isolated islands. If you want the Research Agent to hand off findings to the Writing Agent, you write custom glue code. Every combination of agents needs custom integration. Sound familiar? It's the same M×N problem MCP solves for tools — but now for **agents talking to agents**.

## The "Business-to-Business API for AI Agents" Analogy

Think of A2A as the **standard business protocol between companies**.

When Company A needs a service from Company B:
1. Company A looks at Company B's **catalog** (Agent Card)
2. Company A sends a **purchase order** (Task)
3. Company B does the work, sending **status updates** (Task lifecycle)
4. Company B delivers the **finished product** (Artifact)

A2A standardizes this workflow for AI agents, regardless of who built them or what framework they use.

---

## MCP vs A2A: Different Problems, Complementary Solutions

```mermaid
graph TB
    subgraph "MCP World"
        AI[AI Agent] -->|uses| T1[Tool: Database]
        AI -->|uses| T2[Tool: File System]
        AI -->|uses| T3[Tool: API]
    end

    subgraph "A2A World"
        A1[Agent: Coordinator] -->|delegates to| A2[Agent: Researcher]
        A1 -->|delegates to| A3[Agent: Writer]
        A2 -->|delegates to| A4[Agent: Data Analyst]
    end
```

| Aspect | MCP | A2A |
|--------|-----|-----|
| **Purpose** | AI ↔ Tools | Agent ↔ Agent |
| **Relationship** | Master-servant (AI controls tools) | Peer-to-peer (agents collaborate) |
| **Analogy** | Using a screwdriver | Hiring a contractor |
| **Who decides** | The AI decides what tools to use | Agents negotiate work |
| **State** | Stateless tool calls | Stateful task lifecycle |
| **Discovery** | Server declares capabilities | Agent Cards advertise skills |
| **Result** | Tool output | Task artifacts |

**Key insight:** MCP gives an agent *hands* (to use tools). A2A gives agents *colleagues* (to delegate work).

---

## A2A Core Concepts

### 1. Agent Card — The Agent's Business Card

Every A2A agent publishes an **Agent Card** — a JSON document describing who it is, what it can do, and how to reach it.

```json
{
  "name": "Research Agent",
  "description": "Finds and synthesizes information from multiple sources",
  "url": "https://research-agent.example.com",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "web-research",
      "name": "Web Research",
      "description": "Search and synthesize web content"
    }
  ],
  "authentication": {
    "schemes": ["bearer"]
  }
}
```

### 2. Task — The Unit of Work

A **Task** is a work request from one agent to another. It has a lifecycle:

```mermaid
stateDiagram-v2
    [*] --> submitted: Client sends task
    submitted --> working: Agent starts processing
    working --> completed: Work finished
    working --> failed: Error occurred
    working --> input_required: Agent needs more info
    input_required --> working: Client provides info
    working --> canceled: Client cancels
    completed --> [*]
    failed --> [*]
    canceled --> [*]
```

### 3. Message & Part — Communication Format

Agents communicate through **Messages**, which contain **Parts**:

```json
{
  "role": "user",
  "parts": [
    {
      "type": "text",
      "text": "Research the latest trends in quantum computing"
    },
    {
      "type": "file",
      "file": {
        "mimeType": "application/pdf",
        "data": "base64-encoded-content"
      }
    }
  ]
}
```

Parts can be:
- **TextPart** — plain text
- **FilePart** — binary files (images, PDFs, etc.)
- **DataPart** — structured JSON data

### 4. Artifact — The Work Product

When an agent completes work, it produces **Artifacts** — the deliverables:

```json
{
  "name": "research-report",
  "parts": [
    {
      "type": "text",
      "text": "# Quantum Computing Trends 2025\n\n..."
    }
  ]
}
```

Artifacts are different from messages — they represent the **final output**, not the conversation.

---

## Task Lifecycle in Detail

```mermaid
sequenceDiagram
    participant Client as Client Agent
    participant Server as Server Agent

    Client->>Server: POST /tasks/send {message: "Research quantum computing"}
    Server-->>Client: {id: "task-123", status: "working"}

    Note over Server: Agent processes the request...

    Client->>Server: GET /tasks/task-123
    Server-->>Client: {status: "working", progress: "Searching sources..."}

    Client->>Server: GET /tasks/task-123
    Server-->>Client: {status: "completed", artifacts: [...]}
```

### Task States Explained

| State | Meaning | What Happens Next |
|-------|---------|-------------------|
| `submitted` | Task received, queued | Agent picks it up |
| `working` | Agent is processing | Wait or poll for updates |
| `input-required` | Agent needs clarification | Client sends more info |
| `completed` | Work done successfully | Retrieve artifacts |
| `failed` | Something went wrong | Check error, maybe retry |
| `canceled` | Client or agent canceled | Cleanup |

---

## Agent Discovery: How Agents Find Each Other

A2A agents advertise themselves by hosting their Agent Card at a well-known URL:

```
https://agent.example.com/.well-known/agent.json
```

Discovery mechanisms:
1. **Direct URL** — you know where the agent is
2. **Registry** — a catalog of available agents (like a phone book)
3. **DNS-based** — agents advertise via DNS records

```mermaid
graph LR
    subgraph "Agent Discovery"
        C[Client Agent] -->|1. Query registry| R[Agent Registry]
        R -->|2. Return agent URLs| C
        C -->|3. Fetch agent card| A1["Agent A<br/>/.well-known/agent.json"]
        C -->|4. Send task| A1
    end
```

---

## Complete A2A Flow

```mermaid
sequenceDiagram
    participant User
    participant Coordinator as Coordinator Agent
    participant Registry as Agent Registry
    participant Specialist as Specialist Agent

    User->>Coordinator: "Write a report on AI trends"
    
    Coordinator->>Registry: Find agents with "research" skill
    Registry-->>Coordinator: [Research Agent URL]
    
    Coordinator->>Specialist: GET /.well-known/agent.json
    Specialist-->>Coordinator: Agent Card (capabilities, auth)
    
    Coordinator->>Specialist: POST /tasks/send {message: "Research AI trends"}
    Specialist-->>Coordinator: {task_id: "abc", status: "working"}
    
    Note over Specialist: Researching...
    
    Coordinator->>Specialist: GET /tasks/abc
    Specialist-->>Coordinator: {status: "completed", artifacts: [report]}
    
    Coordinator->>User: "Here's your report on AI trends..."
```

---

## Key Takeaway

- **MCP** = how an agent uses tools (like a person using a hammer)
- **A2A** = how agents collaborate (like coworkers delegating tasks)
- Together, they form a complete ecosystem: agents use MCP to access tools, and A2A to work with other agents.

---

## Staff-Level Considerations

### Anti-Patterns

**1. Using A2A When Simple API Calls Work**
A2A adds task lifecycle management, agent cards, discovery, and message formatting. If Agent B is always called by Agent A with the same parameters and returns immediately — that's just an API call. A2A's value is in multi-step, asynchronous, discoverable collaboration. Don't over-engineer simple function calls into agent protocols.

**2. No Agent Card**
Deploying an A2A agent without a properly structured Agent Card means it's undiscoverable and unverifiable. Other agents can't know what you do, what inputs you accept, or how to authenticate. It's like opening a business with no sign, no phone number, and no menu.

**3. Assuming All Agents Speak the Same Protocol**
In a real enterprise, some "agents" are legacy services, some are LangChain apps, some are AutoGen, some are custom. A2A is a standard, but adoption is early. You need protocol adapters and graceful fallback — not blind assumptions of A2A support.

**4. No Task Lifecycle Management**
Sending a task and never checking status, never handling `input_required`, never implementing cancellation — this creates zombie tasks that consume resources indefinitely. Every task sender must implement polling or push notification handling and respect terminal states.

### Trade-offs

| Decision | A2A Protocol | Direct Integration |
|----------|-------------|-------------------|
| **Discovery** | Standard agent cards | Hardcoded endpoints |
| **Flexibility** | Any A2A agent is substitutable | Tightly coupled |
| **Overhead** | Task lifecycle, message format | Direct call, minimal |
| **Observability** | Built-in state transitions | Custom logging |
| **When to choose** | Multi-vendor, discoverable agents | Internal, stable, performance-critical |

| Decision | Standardized Discovery | Custom Registry |
|----------|----------------------|-----------------|
| **Interop** | Any A2A client works | Only your clients |
| **Control** | Limited to spec | Full flexibility |
| **Metadata** | A2A schema only | Custom fields (cost, SLA, etc.) |
| **When to choose** | Public/multi-org agents | Enterprise-internal |

### When A2A Actually Adds Value

- Agents are built by **different teams or organizations**
- Tasks are **long-running** (minutes to hours) and need lifecycle tracking
- You need **substitutability** — swap one research agent for another
- Agents need to **negotiate** — request clarification, reject tasks
- You want **audit trails** of inter-agent delegation

### When to Skip A2A

- All agents are in the same codebase/deployment
- Communication is synchronous and sub-second
- There's exactly one consumer of each agent
- You control both sides and won't expose to third parties

---

## A2A Maturity Model

| Level | Characteristics | Typical Setup |
|-------|----------------|---------------|
| **L1 — Ad hoc** | Direct API calls between agents, custom protocols | Internal microservices calling each other |
| **L2 — Structured** | A2A protocol adopted, Agent Cards published, basic task delegation | Two teams sharing agents via standard interface |
| **L3 — Managed** | Registry/discovery, SLA tracking, auth standardized | Platform team manages agent marketplace |
| **L4 — Federated** | Cross-org agent collaboration, trust frameworks, billing | Enterprise-to-enterprise agent delegation |

## Adoption Readiness Checklist

Before implementing A2A, confirm:

- [ ] **Multiple distinct agents exist** that need to collaborate (not just one agent with tools)
- [ ] **Organizational boundary**: Agents are owned by different teams or organizations
- [ ] **Async requirements**: Tasks take minutes-hours, not sub-second
- [ ] **Agent Card defined**: You can clearly describe your agent's capabilities, endpoint, auth
- [ ] **Task lifecycle needed**: You need progress tracking, cancellation, resumption
- [ ] **Push updates required**: Long-running tasks need to stream status back
- [ ] **Auth model clear**: You know how agents will authenticate to each other (OAuth, API keys)
- [ ] **Fallback plan**: If the remote agent is down/slow, your system degrades gracefully

**Staff insight**: A2A adoption is premature for most teams in 2025. The protocol is well-designed but the ecosystem is nascent. Implement A2A when you have a concrete multi-org agent collaboration need — not speculatively.
