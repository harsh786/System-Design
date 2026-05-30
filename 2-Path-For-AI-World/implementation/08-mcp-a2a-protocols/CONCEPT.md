# MCP and A2A Protocols — Deep Conceptual Guide

## 1. Model Context Protocol (MCP)

### 1.1 What Is MCP?

MCP (Model Context Protocol) is an open standard created by Anthropic that provides a universal interface for LLM applications to connect with external tools, data sources, and services. Think of it as "USB-C for AI" — a single protocol that replaces bespoke integrations.

**Why it exists:**
- Before MCP, every AI application built its own tool integrations (N×M problem)
- Tool definitions were scattered, inconsistent, and hard to govern
- No standard way to discover, authorize, or audit tool usage
- MCP reduces this to N+M: N clients speak MCP, M servers speak MCP

### 1.2 Architecture

```
┌─────────────────────────────────────────────┐
│                  HOST                        │
│  (e.g., Claude Desktop, IDE, Agent Runtime) │
│                                             │
│  ┌─────────────┐  ┌─────────────┐          │
│  │  MCP Client │  │  MCP Client │  ...     │
│  └──────┬──────┘  └──────┬──────┘          │
└─────────┼────────────────┼──────────────────┘
          │                │
          ▼                ▼
   ┌──────────────┐ ┌──────────────┐
   │  MCP Server  │ │  MCP Server  │
   │  (Database)  │ │  (GitHub)    │
   └──────────────┘ └──────────────┘
```

**Host:** The application that embeds the LLM (Claude Desktop, an IDE plugin, a custom agent runtime). The host manages security boundaries and user consent.

**Client:** A protocol-level session within the host. Each client connects to exactly one server. The host may have many clients.

**Server:** A lightweight process or service that exposes capabilities (tools, resources, prompts) via MCP. Servers are purpose-built and narrowly scoped.

### 1.3 Primitives

#### Tools (Model-Controlled)
Functions the LLM can invoke. The model decides when to call them based on context.

```json
{
  "name": "query_database",
  "description": "Execute a read-only SQL query against the analytics database",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "SQL SELECT statement" }
    },
    "required": ["query"]
  }
}
```

**Key properties:**
- Tools have side effects (create tickets, send emails, execute queries)
- Tools require explicit user approval before execution (in well-designed systems)
- Tools return structured results

#### Resources (Application-Controlled)
Data the application can read. Think of these as files/documents the context window can access.

```json
{
  "uri": "file:///project/README.md",
  "name": "Project README",
  "mimeType": "text/markdown"
}
```

**Key properties:**
- Resources are read-only
- Application decides when to fetch them (not the model)
- Support subscriptions for live updates

#### Prompts (User-Controlled)
Reusable prompt templates that users can select.

```json
{
  "name": "code_review",
  "description": "Review code for bugs and style",
  "arguments": [
    { "name": "code", "description": "Code to review", "required": true }
  ]
}
```

### 1.4 Transports

#### stdio (Local Servers)
- Host spawns server as a subprocess
- Communication over stdin/stdout
- Best for local tools (file system, local databases)
- No network exposure, inherently secure transport

#### HTTP + SSE (Remote Servers)
- Server runs as an HTTP service
- Client sends requests via HTTP POST
- Server streams responses via Server-Sent Events (SSE)
- Supports authentication headers
- Suitable for shared/remote services

#### Streamable HTTP (Newer)
- Simplified HTTP transport without persistent SSE connection
- Server can optionally upgrade to SSE for streaming
- Better for serverless/stateless deployments

### 1.5 Authorization

MCP itself delegates authorization to the transport layer, but production systems need:

1. **OAuth 2.1 for remote servers** — Client authenticates to server using OAuth flows
2. **Token scoping** — Access tokens should be narrowly scoped (read-only DB, specific repos)
3. **User consent** — Host must get user approval before first tool invocation
4. **Per-invocation approval** — High-risk tools require approval each time

### 1.6 Server Trust

**Trust levels for MCP servers:**

| Level | Description | Example |
|-------|-------------|---------|
| System | Shipped with the host, fully trusted | Built-in file tools |
| Verified | Reviewed and signed by registry | Official GitHub MCP server |
| Community | Published but unreviewed | Third-party integrations |
| Local | User-developed, untested | Custom scripts |

**Supply-chain risks:**
- Malicious tool descriptions that manipulate the LLM (prompt injection via tool schema)
- Tool shadowing: a malicious server redefines a trusted tool name
- Data exfiltration through tool parameters
- Dependency confusion in server packages

**Mitigations:**
- Pin server versions
- Verify server signatures
- Sandbox server execution
- Monitor tool invocation patterns
- Restrict tool access by user role

### 1.7 MCP Registry

A registry is a catalog of available MCP servers with metadata:

```yaml
servers:
  - name: "sql-readonly"
    version: "1.2.0"
    publisher: "internal-platform-team"
    risk_tier: "low"
    tools:
      - name: "execute_query"
        risk: "low"
        requires_approval: false
    transport: "stdio"
    checksum: "sha256:abc123..."
```

**Registry governance:**
- Approval workflow for new servers
- Risk classification (low/medium/high/critical)
- Version pinning and rollback
- Usage analytics and anomaly detection

### 1.8 Tool Discovery

1. Client connects to server
2. Client calls `tools/list` to enumerate available tools
3. Host presents tools to LLM with descriptions
4. LLM can call `tools/call` with arguments
5. Server executes and returns results

Dynamic discovery means the LLM sees only tools relevant to the current context.

### 1.9 Audit Logging

Every tool invocation should produce an audit record:

```json
{
  "timestamp": "2024-12-01T10:30:00Z",
  "user_id": "user-123",
  "session_id": "sess-456",
  "server": "sql-readonly",
  "tool": "execute_query",
  "input": { "query": "SELECT count(*) FROM orders" },
  "output_summary": "Returned 1 row",
  "latency_ms": 230,
  "approval": "auto-approved",
  "risk_tier": "low"
}
```

### 1.10 Sandboxing

MCP servers should run in restricted environments:
- **Container isolation** — Each server in its own container with minimal permissions
- **Network policies** — Servers can only reach their target service
- **Resource limits** — CPU, memory, timeout caps
- **File system restrictions** — Read-only mounts, no access to host filesystem
- **Capability dropping** — Remove all Linux capabilities except those explicitly needed

---

## 2. Agent-to-Agent Protocol (A2A)

### 2.1 What Is A2A?

A2A (Agent-to-Agent Protocol) is Google's open protocol for agents to communicate, delegate tasks, and collaborate — regardless of framework or vendor. While MCP connects an LLM to tools, A2A connects agents to other agents.

**Why it exists:**
- Enterprise systems will have many specialized agents (HR agent, finance agent, IT agent)
- These agents are built on different frameworks (LangChain, CrewAI, AutoGen, custom)
- They need a standard way to discover each other, delegate work, and track tasks
- No single vendor should own inter-agent communication

### 2.2 Agent Card

Every A2A-compatible agent publishes an Agent Card at a well-known URL (typically `/.well-known/agent.json`):

```json
{
  "name": "Expense Report Agent",
  "description": "Processes expense reports, validates receipts, routes for approval",
  "url": "https://expenses.internal.company.com",
  "version": "2.1.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": true
  },
  "skills": [
    {
      "id": "process-expense",
      "name": "Process Expense Report",
      "description": "Submit and process an expense report with receipt validation",
      "inputModes": ["text", "file"],
      "outputModes": ["text", "file"]
    }
  ],
  "authentication": {
    "schemes": ["oauth2"],
    "oauth2": {
      "tokenUrl": "https://auth.company.com/oauth/token",
      "scopes": ["agent:expense:submit", "agent:expense:read"]
    }
  },
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"]
}
```

### 2.3 Agent Discovery

**Mechanisms:**
1. **Well-known URL** — Fetch `https://<agent-host>/.well-known/agent.json`
2. **Agent Registry** — Central catalog that indexes Agent Cards
3. **DNS-based** — SRV records pointing to agent endpoints
4. **Manual configuration** — Hardcoded in orchestrator config

**Registry-based discovery flow:**
1. Agent registers its Agent Card with the registry
2. Orchestrator queries registry: "Find agents that can process expenses"
3. Registry returns matching Agent Cards ranked by capability match
4. Orchestrator selects and initiates task

### 2.4 Task Lifecycle

A2A defines a strict task state machine:

```
                    ┌──────────────┐
                    │  submitted   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌─────│   working    │─────┐
              │     └──────┬───────┘     │
              │            │             │
     ┌────────▼────────┐   │    ┌────────▼────────┐
     │ input-required  │   │    │     failed      │
     └────────┬────────┘   │    └─────────────────┘
              │            │
              └────────────┘
                           │
                    ┌──────▼───────┐
                    │  completed   │
                    └──────────────┘
```

**States:**
- **submitted** — Task received, queued for processing
- **working** — Agent is actively processing the task
- **input-required** — Agent needs additional information from the caller
- **completed** — Task finished successfully with output artifacts
- **failed** — Task failed with error details

**Task object:**
```json
{
  "id": "task-789",
  "sessionId": "session-abc",
  "status": {
    "state": "working",
    "message": "Validating receipts...",
    "timestamp": "2024-12-01T10:31:00Z"
  },
  "artifacts": [],
  "history": [
    { "state": "submitted", "timestamp": "2024-12-01T10:30:00Z" },
    { "state": "working", "timestamp": "2024-12-01T10:30:05Z" }
  ]
}
```

### 2.5 Authentication Between Agents

Agents authenticate to each other using standard OAuth 2.1:

1. **Client credentials flow** — For agent-to-agent (no user context)
2. **On-behalf-of flow** — When acting on behalf of a user
3. **Token exchange** — Convert user token to agent-scoped token

**Trust chain:**
```
User → Orchestrator Agent (user's token)
     → Specialist Agent (exchanged token with delegated scope)
     → Tool/Service (agent's service account)
```

### 2.6 Delegated Task Policy

Policies control what an agent can delegate:

```yaml
delegation_policies:
  - agent: "orchestrator-agent"
    can_delegate_to:
      - agent: "expense-agent"
        max_cost_tier: "medium"
        requires_human_approval: false
        allowed_skills: ["process-expense"]
      - agent: "payment-agent"
        max_cost_tier: "high"
        requires_human_approval: true
        allowed_skills: ["initiate-payment"]
```

### 2.7 Human Approval for Delegated Tasks

High-risk delegations require human-in-the-loop:

1. Orchestrator wants to delegate to Payment Agent
2. Policy says `requires_human_approval: true`
3. System pauses task, notifies human via Slack/email/UI
4. Human reviews: what's being delegated, to whom, with what data
5. Human approves/rejects
6. If approved, delegation proceeds with audit trail

### 2.8 Task Traceability

Every task carries a trace context (W3C Trace Context compatible):

```json
{
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "spanId": "00f067aa0ba902b7",
  "parentSpanId": "a3ce929d0e0e4736",
  "delegationChain": [
    { "agent": "orchestrator", "timestamp": "..." },
    { "agent": "expense-agent", "timestamp": "..." }
  ]
}
```

This enables:
- End-to-end latency tracking
- Blame assignment when tasks fail
- Cost attribution across agents
- Compliance audit trails

### 2.9 Cross-Framework Interoperability

A2A is framework-agnostic. Agents built with any stack can participate:

| Framework | A2A Compatibility |
|-----------|------------------|
| LangGraph | Wrap as A2A endpoint |
| CrewAI | A2A adapter available |
| AutoGen | Custom A2A wrapper |
| Semantic Kernel | Native A2A support planned |
| Custom Python | Implement A2A HTTP endpoints |

The protocol is just HTTP + JSON — any agent that can serve HTTP can participate.

---

## 3. MCP vs A2A — When to Use Which

| Dimension | MCP | A2A |
|-----------|-----|-----|
| **Purpose** | Connect LLM to tools/data | Connect agent to agent |
| **Relationship** | Client-server (tool usage) | Peer-to-peer (task delegation) |
| **Statefulness** | Stateless tool calls | Stateful task lifecycle |
| **Who decides** | LLM decides which tool | Agent decides which agent |
| **Complexity** | Simple request/response | Multi-step with status tracking |
| **Use when** | Need to query DB, call API, read file | Need to delegate complex work to specialist |
| **Example** | "Look up customer in CRM" | "Process this expense report end-to-end" |

**They're complementary, not competing:**
```
User → Orchestrator Agent
         │
         ├── (A2A) → Research Agent
         │              └── (MCP) → Web Search Tool
         │              └── (MCP) → Document Store
         │
         ├── (A2A) → Writing Agent
         │              └── (MCP) → Text Editor Tool
         │
         └── (MCP) → Calendar Tool (simple, no agent needed)
```

**Decision rule:**
- If a single tool call suffices → MCP
- If multi-step reasoning/planning is needed → A2A to a specialist agent
- If the capability requires its own judgment → A2A
- If it's a deterministic function → MCP

---

## 4. Security Principles

### For MCP:
1. **Least privilege** — Each server gets minimal permissions
2. **User consent** — Never invoke tools without user awareness
3. **Input validation** — Servers must validate all inputs (never trust LLM output)
4. **Output sanitization** — Tool outputs may contain prompt injections
5. **Rate limiting** — Prevent runaway tool loops
6. **Audit everything** — Every invocation logged with full context
7. **Sandbox execution** — Servers run in isolated environments
8. **Pin versions** — Don't auto-update servers without review

### For A2A:
1. **Mutual authentication** — Both agents verify identity
2. **Scoped delegation** — Delegated tasks carry minimal necessary permissions
3. **Policy enforcement** — Central policies govern who can delegate what
4. **Human escalation** — High-risk delegations require approval
5. **Trace propagation** — Full audit trail across agent boundaries
6. **Data minimization** — Only pass necessary data in task payloads
7. **Timeout enforcement** — Tasks that run too long are killed
8. **Idempotency** — Tasks can be safely retried

---

## 5. Tool and Agent Registries

### Risk Tiering

| Tier | Description | Approval | Examples |
|------|-------------|----------|----------|
| **Low** | Read-only, no PII | Auto-approved | Search docs, list files |
| **Medium** | Writes non-critical data | Team lead approval | Create ticket, send notification |
| **High** | Financial, PII, or external | Security review + approval | Process payment, access customer data |
| **Critical** | Irreversible, compliance-sensitive | CISO approval + audit | Delete data, modify access controls |

### Governance Process

1. **Submission** — Developer submits tool/agent with metadata, risk assessment
2. **Automated scan** — Static analysis, dependency check, schema validation
3. **Risk classification** — Auto-assigned based on capabilities, can be overridden
4. **Review** — Appropriate approver reviews based on risk tier
5. **Testing** — Integration tests in sandbox environment
6. **Publication** — Added to registry with version tag
7. **Monitoring** — Ongoing usage analytics, anomaly detection
8. **Deprecation** — Graceful sunset with migration path

### Registry Schema

```json
{
  "registry": {
    "tools": [
      {
        "id": "tool-001",
        "name": "sql_query",
        "server": "sql-readonly-server",
        "version": "1.2.0",
        "risk_tier": "low",
        "approved_by": "platform-team",
        "approved_at": "2024-11-15",
        "permissions": {
          "roles": ["analyst", "engineer"],
          "users": ["user-specific-override"]
        },
        "rate_limits": {
          "per_user_per_hour": 100,
          "global_per_hour": 10000
        },
        "audit_retention_days": 90
      }
    ],
    "agents": [
      {
        "id": "agent-001",
        "name": "Expense Agent",
        "agent_card_url": "https://expense.internal/.well-known/agent.json",
        "risk_tier": "high",
        "delegation_policies": ["policy-finance-001"],
        "owner_team": "finance-platform",
        "sla_p99_seconds": 30
      }
    ]
  }
}
```
