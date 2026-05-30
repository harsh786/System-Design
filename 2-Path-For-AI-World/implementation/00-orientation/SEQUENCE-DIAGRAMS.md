# Sequence Diagrams: Agentic AI System Flows

## 1. End-to-End Request Flow (User → Response)

This diagram shows the complete lifecycle of a user request through all architectural layers.

```mermaid
sequenceDiagram
    participant User
    participant Channel as Web/Mobile/Chat
    participant Gateway as API Gateway
    participant Auth as Identity Provider
    participant AIGateway as AI Gateway
    participant Cache as Semantic Cache
    participant Guardrails as Input Guardrails
    participant Router as Model Router
    participant Orchestrator as Agent Orchestrator
    participant Memory as Memory Store
    participant LLM as Language Model
    participant OutputGuard as Output Guardrails
    participant Eval as Evaluation Engine
    participant Audit as Audit Log
    participant Observability as Tracing

    User->>Channel: Send message
    Channel->>Gateway: POST /chat/completions
    Gateway->>Auth: Validate token
    Auth-->>Gateway: User context + permissions
    Gateway->>AIGateway: Forward request + user context

    Note over AIGateway: Start trace span
    AIGateway->>Observability: Create trace

    AIGateway->>Guardrails: Validate input
    Guardrails->>Guardrails: Check prompt injection
    Guardrails->>Guardrails: Check PII
    Guardrails->>Guardrails: Check topic policy
    alt Input Rejected
        Guardrails-->>AIGateway: Rejection reason
        AIGateway-->>User: Safe refusal response
    end
    Guardrails-->>AIGateway: Input approved

    AIGateway->>Cache: Check semantic cache
    alt Cache Hit (similarity > 0.95)
        Cache-->>AIGateway: Cached response
        AIGateway->>Audit: Log cache hit
        AIGateway-->>User: Return cached response
    end
    Cache-->>AIGateway: Cache miss

    AIGateway->>Router: Determine optimal model
    Router->>Router: Assess complexity, budget, latency needs
    Router-->>AIGateway: Selected model + provider

    AIGateway->>Orchestrator: Execute agent workflow
    Orchestrator->>Memory: Load conversation history
    Memory-->>Orchestrator: Previous context + long-term memory
    Orchestrator->>Orchestrator: Construct system prompt + context
    Orchestrator->>LLM: Generate response
    LLM-->>Orchestrator: Response (may include tool calls)

    Note over Orchestrator: If tool calls needed, see Tool-Calling Flow

    Orchestrator-->>AIGateway: Final response

    AIGateway->>OutputGuard: Validate output
    OutputGuard->>OutputGuard: Content safety check
    OutputGuard->>OutputGuard: PII leak detection
    OutputGuard->>OutputGuard: Factuality check
    OutputGuard-->>AIGateway: Output approved

    AIGateway->>Cache: Store in semantic cache
    AIGateway->>Eval: Score quality (async)
    AIGateway->>Audit: Log complete interaction
    AIGateway->>Memory: Update conversation memory
    AIGateway->>Observability: Complete trace span

    AIGateway-->>Channel: Stream response
    Channel-->>User: Display response
```

---

## 2. RAG Retrieval Flow

Detailed flow of how context is retrieved from knowledge bases to ground agent responses.

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant RAG as RAG Controller
    participant QueryProc as Query Processor
    participant EmbedSvc as Embedding Service
    participant VectorDB as Vector Store
    participant KeywordIdx as Keyword Index
    participant KGraph as Knowledge Graph
    participant Fusion as Fusion Engine
    participant Reranker as Re-ranker
    participant ACL as Access Control
    participant ContextMgr as Context Manager

    Agent->>RAG: Retrieve context for query
    RAG->>QueryProc: Process query

    Note over QueryProc: Query Enhancement
    QueryProc->>QueryProc: Detect intent
    QueryProc->>QueryProc: Extract entities
    QueryProc->>QueryProc: Generate sub-queries (if complex)
    QueryProc->>QueryProc: Apply query expansion

    par Parallel Retrieval
        QueryProc->>EmbedSvc: Embed query
        EmbedSvc-->>QueryProc: Query vector
        QueryProc->>VectorDB: Vector similarity search (top-k=20)
        VectorDB-->>Fusion: Vector results + scores
    and
        QueryProc->>KeywordIdx: BM25 keyword search
        KeywordIdx-->>Fusion: Keyword results + scores
    and
        QueryProc->>KGraph: Graph traversal query
        KGraph-->>Fusion: Graph results + relationships
    end

    Fusion->>Fusion: Reciprocal Rank Fusion (RRF)
    Fusion->>Fusion: Deduplicate results
    Fusion-->>Reranker: Fused candidate set (top-30)

    Reranker->>Reranker: Cross-encoder scoring
    Reranker-->>ACL: Ranked results (top-10)

    ACL->>ACL: Filter by user permissions
    ACL->>ACL: Check document classification
    ACL->>ACL: Apply data residency rules
    ACL-->>ContextMgr: Permitted results

    ContextMgr->>ContextMgr: Assess token budget
    ContextMgr->>ContextMgr: Select optimal context window
    ContextMgr->>ContextMgr: Order by relevance
    ContextMgr->>ContextMgr: Add source citations

    alt Context too large
        ContextMgr->>ContextMgr: Summarize lower-ranked chunks
        ContextMgr->>ContextMgr: Truncate to token budget
    end

    ContextMgr-->>Agent: Structured context with citations

    Note over Agent: Agent now has grounded context for generation
```

### RAG Ingestion Flow (Offline)

```mermaid
sequenceDiagram
    participant Source as Data Sources
    participant Crawler as Crawler/Connector
    participant Extract as Extractor
    participant Clean as Cleaner
    participant Chunk as Chunker
    participant Enrich as Enricher
    participant Embed as Embedder
    participant VDB as Vector Store
    participant KG as Knowledge Graph
    participant Monitor as Quality Monitor

    Source->>Crawler: New/updated content detected
    Crawler->>Extract: Raw content
    Extract->>Extract: Parse format (PDF, HTML, DOCX, etc.)
    Extract->>Extract: Extract text + tables + images
    Extract-->>Clean: Structured text

    Clean->>Clean: Remove boilerplate
    Clean->>Clean: Normalize formatting
    Clean->>Clean: Detect language
    Clean-->>Chunk: Cleaned text

    Chunk->>Chunk: Apply chunking strategy
    Note over Chunk: Semantic chunking at heading/paragraph boundaries<br/>Target: 256-512 tokens per chunk<br/>Overlap: 50-100 tokens
    Chunk-->>Enrich: Chunks with boundaries

    Enrich->>Enrich: Extract metadata (date, author, category)
    Enrich->>Enrich: Extract named entities
    Enrich->>Enrich: Generate summary per chunk
    Enrich->>Enrich: Assign topics/tags
    Enrich-->>Embed: Enriched chunks

    par Store Vectors and Graph
        Embed->>Embed: Generate embeddings (batch)
        Embed->>VDB: Upsert vectors + metadata
        VDB-->>Monitor: Index stats
    and
        Enrich->>KG: Upsert entities + relationships
        KG-->>Monitor: Graph stats
    end

    Monitor->>Monitor: Check coverage
    Monitor->>Monitor: Detect embedding drift
    Monitor->>Monitor: Alert on quality issues
```

---

## 3. Agent Tool-Calling Flow

How an agent discovers, validates, and executes tools during task completion.

```mermaid
sequenceDiagram
    participant LLM as Language Model
    participant Agent as Agent Runtime
    participant Registry as Tool Registry
    participant Validator as Tool Validator
    participant Policy as Policy Engine
    participant AuthMgr as Auth Manager
    participant Executor as Tool Executor
    participant External as External System
    participant Audit as Audit Log
    participant Retry as Retry Handler

    Note over Agent: Agent determines it needs external data/action

    Agent->>LLM: Generate with tools available
    LLM-->>Agent: Tool call: {name, arguments}

    Agent->>Registry: Resolve tool by name
    Registry-->>Agent: Tool definition + schema + constraints

    Agent->>Validator: Validate tool call
    Validator->>Validator: Check argument types/ranges
    Validator->>Validator: Check required params present
    Validator->>Validator: Check argument safety (no injection)
    alt Validation Failed
        Validator-->>Agent: Validation error
        Agent->>LLM: Error feedback, retry generation
        LLM-->>Agent: Corrected tool call
        Agent->>Validator: Re-validate
    end
    Validator-->>Agent: Valid

    Agent->>Policy: Check execution policy
    Policy->>Policy: Is this tool allowed for this agent?
    Policy->>Policy: Is this action within autonomy level?
    Policy->>Policy: Is the scope within limits?
    alt Policy Denied
        Policy-->>Agent: Denial + reason
        Agent->>Agent: Handle gracefully (inform user, request approval)
    end
    Policy-->>Agent: Approved

    Agent->>AuthMgr: Get credentials for tool
    AuthMgr->>AuthMgr: Retrieve scoped token/key
    AuthMgr->>AuthMgr: Apply least-privilege scope
    AuthMgr-->>Executor: Scoped credentials

    Executor->>External: Execute tool call
    Note over External: Timeout: 30s default

    alt Success
        External-->>Executor: Result
        Executor->>Executor: Validate result format
        Executor->>Executor: Truncate if oversized
        Executor->>Audit: Log execution (sanitized)
        Executor-->>Agent: Tool result
    else Timeout/Error
        External-->>Executor: Error/timeout
        Executor->>Retry: Should retry?
        alt Retryable Error
            Retry->>Executor: Retry with backoff
            Executor->>External: Retry execution
            External-->>Executor: Result
        else Non-Retryable
            Retry-->>Agent: Error result
            Agent->>LLM: Tool failed, adjust plan
        end
    end

    Agent->>LLM: Provide tool result, continue reasoning
    LLM-->>Agent: Next action or final response

    Note over Agent: Loop continues until task complete or limits reached
```

---

## 4. Human-in-the-Loop Approval Flow

How the system handles high-risk actions that require human approval before execution.

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Policy as Policy Engine
    participant Approval as Approval Service
    participant Notify as Notification Service
    participant Human as Human Reviewer
    participant State as State Store
    participant Executor as Tool Executor
    participant External as External System
    participant User as End User

    Agent->>Policy: Request to execute high-risk action
    Note over Policy: Examples: financial transactions > $X,<br/>data deletion, external communications,<br/>production deployments, PII access

    Policy->>Policy: Evaluate risk level
    Policy-->>Agent: REQUIRES_APPROVAL

    Agent->>Approval: Submit approval request
    Note over Approval: Request includes:<br/>- Action description<br/>- Parameters<br/>- Context/reasoning<br/>- Risk assessment<br/>- Timeout

    Approval->>State: Store pending approval (TTL: 30min)
    Approval->>Notify: Alert appropriate reviewer

    par Notify Multiple Channels
        Notify->>Human: Slack notification
    and
        Notify->>Human: Email notification
    and
        Notify->>Human: Dashboard alert
    end

    Agent->>User: "This action requires approval. I've requested review."
    Agent->>State: Save agent state (can resume)

    Note over Human: Human reviews request

    alt Approved
        Human->>Approval: Approve (with optional modifications)
        Approval->>State: Update status: APPROVED
        Approval->>Agent: Resume with approval
        Agent->>Executor: Execute approved action
        Executor->>External: Perform action
        External-->>Executor: Result
        Executor-->>Agent: Success
        Agent->>User: "Action approved and completed: [result]"
    else Rejected
        Human->>Approval: Reject (with reason)
        Approval->>State: Update status: REJECTED
        Approval->>Agent: Resume with rejection
        Agent->>Agent: Adjust plan (find alternative)
        Agent->>User: "Action was not approved. [reason]. Here's an alternative..."
    else Timeout (30min)
        State->>Approval: TTL expired
        Approval->>Agent: Resume with timeout
        Agent->>User: "Approval timed out. Would you like me to escalate or try a different approach?"
    else Modified
        Human->>Approval: Approve with modifications
        Approval->>Agent: Resume with modified parameters
        Agent->>Agent: Validate modifications are compatible
        Agent->>Executor: Execute modified action
        Executor-->>Agent: Result
        Agent->>User: "Action completed with reviewer's modifications: [details]"
    end
```

---

## 5. Multi-Agent Delegation Flow

How a supervisor/orchestrator agent decomposes tasks and delegates to specialized sub-agents.

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator as Orchestrator Agent
    participant Planner as Planner
    participant Router as Agent Router
    participant ResearchAgent as Research Agent
    participant CodeAgent as Code Agent
    participant ReviewAgent as Review Agent
    participant Memory as Shared Memory
    participant State as Execution State

    User->>Orchestrator: Complex request requiring multiple skills

    Orchestrator->>Planner: Decompose into sub-tasks
    Planner->>Planner: Analyze dependencies
    Planner->>Planner: Identify required capabilities
    Planner->>Planner: Determine execution order
    Planner-->>Orchestrator: Execution plan

    Note over Orchestrator: Plan:<br/>1. Research (independent)<br/>2. Code implementation (depends on 1)<br/>3. Code review (depends on 2)

    Orchestrator->>State: Initialize execution state
    Orchestrator->>Memory: Store plan + shared context

    %% Step 1: Research (may be parallel)
    Orchestrator->>Router: Route "research" task
    Router->>Router: Match capabilities to agents
    Router-->>Orchestrator: ResearchAgent selected

    Orchestrator->>ResearchAgent: Execute research task
    Note over ResearchAgent: Research Agent has:<br/>- Web search tool<br/>- Documentation tool<br/>- Read-only DB access

    ResearchAgent->>ResearchAgent: Execute research steps
    ResearchAgent->>Memory: Store research findings
    ResearchAgent-->>Orchestrator: Research complete + results

    Orchestrator->>State: Update: Step 1 complete

    %% Step 2: Code Implementation
    Orchestrator->>Router: Route "code" task + research context
    Router-->>Orchestrator: CodeAgent selected

    Orchestrator->>Memory: Retrieve research findings
    Memory-->>Orchestrator: Research context

    Orchestrator->>CodeAgent: Implement based on research
    Note over CodeAgent: Code Agent has:<br/>- File read/write tools<br/>- Code execution sandbox<br/>- Test runner

    CodeAgent->>CodeAgent: Write implementation
    CodeAgent->>CodeAgent: Run tests
    alt Tests Fail
        CodeAgent->>CodeAgent: Fix and retry (max 3 attempts)
    end
    CodeAgent->>Memory: Store implementation details
    CodeAgent-->>Orchestrator: Implementation complete

    Orchestrator->>State: Update: Step 2 complete

    %% Step 3: Review
    Orchestrator->>Router: Route "review" task
    Router-->>Orchestrator: ReviewAgent selected

    Orchestrator->>Memory: Get implementation + research context
    Orchestrator->>ReviewAgent: Review implementation

    ReviewAgent->>ReviewAgent: Check code quality
    ReviewAgent->>ReviewAgent: Verify requirements met
    ReviewAgent->>ReviewAgent: Security review

    alt Issues Found
        ReviewAgent-->>Orchestrator: Review issues
        Orchestrator->>CodeAgent: Fix issues
        CodeAgent-->>Orchestrator: Fixes applied
        Orchestrator->>ReviewAgent: Re-review
    end

    ReviewAgent-->>Orchestrator: Review approved

    Orchestrator->>State: Update: All steps complete
    Orchestrator->>Orchestrator: Synthesize final response
    Orchestrator-->>User: Complete result with summary
```

### Parallel Multi-Agent Execution

```mermaid
sequenceDiagram
    participant Orchestrator as Orchestrator
    participant AgentA as Agent A (Research)
    participant AgentB as Agent B (Analysis)
    participant AgentC as Agent C (Visualization)
    participant Aggregator as Result Aggregator

    Note over Orchestrator: Independent tasks can run in parallel

    par Execute in Parallel
        Orchestrator->>AgentA: Research task
        AgentA->>AgentA: Working...
    and
        Orchestrator->>AgentB: Analysis task
        AgentB->>AgentB: Working...
    and
        Orchestrator->>AgentC: Visualization task
        AgentC->>AgentC: Working...
    end

    AgentA-->>Aggregator: Research results
    AgentB-->>Aggregator: Analysis results
    AgentC-->>Aggregator: Visualization results

    Aggregator->>Aggregator: Combine results
    Aggregator->>Aggregator: Resolve conflicts
    Aggregator->>Aggregator: Generate unified response
    Aggregator-->>Orchestrator: Aggregated result
```

---

## 6. Error & Fallback Flow

How the system handles various failure modes gracefully.

```mermaid
sequenceDiagram
    participant User
    participant AIGateway as AI Gateway
    participant CircuitBreaker as Circuit Breaker
    participant Primary as Primary Model (GPT-4o)
    participant Secondary as Secondary Model (Claude)
    participant Tertiary as Tertiary Model (GPT-4o-mini)
    participant Cache as Response Cache
    participant Fallback as Static Fallback
    participant Alert as Alerting
    participant Observability as Observability

    User->>AIGateway: Request

    AIGateway->>CircuitBreaker: Check primary provider status
    alt Circuit OPEN (provider known down)
        CircuitBreaker-->>AIGateway: Primary unavailable
        AIGateway->>Observability: Log circuit open bypass
        Note over AIGateway: Skip directly to secondary
    else Circuit CLOSED (normal)
        AIGateway->>Primary: Send request
        alt Success
            Primary-->>AIGateway: Response
            AIGateway-->>User: Return response
        else Rate Limited (429)
            Primary-->>AIGateway: 429 Too Many Requests
            AIGateway->>Observability: Log rate limit hit
            AIGateway->>AIGateway: Wait & retry (exponential backoff)
            AIGateway->>Primary: Retry
            alt Still Rate Limited
                Primary-->>AIGateway: 429
                Note over AIGateway: Fallback to secondary
            end
        else Timeout (30s)
            Primary-->>AIGateway: Timeout
            AIGateway->>CircuitBreaker: Record failure
            CircuitBreaker->>CircuitBreaker: Failures: 3/5 threshold
        else Server Error (500/503)
            Primary-->>AIGateway: 500 Error
            AIGateway->>CircuitBreaker: Record failure
            alt Threshold Reached
                CircuitBreaker->>CircuitBreaker: OPEN circuit
                CircuitBreaker->>Alert: Alert: Primary provider down
            end
        end
    end

    Note over AIGateway: Primary failed, try secondary

    AIGateway->>Secondary: Send request (same prompt)
    alt Success
        Secondary-->>AIGateway: Response
        AIGateway->>Observability: Log fallback to secondary
        AIGateway-->>User: Return response (with degradation note)
    else Secondary Also Fails
        Secondary-->>AIGateway: Error
        AIGateway->>Observability: Log double failure

        AIGateway->>Tertiary: Try with smaller/faster model
        alt Success with Degradation
            Tertiary-->>AIGateway: Response (lower quality)
            AIGateway-->>User: Response + "reduced capability" indicator
        else All Models Failed
            Tertiary-->>AIGateway: Error
            AIGateway->>Cache: Check for similar cached response
            alt Cache Has Relevant Response
                Cache-->>AIGateway: Stale but relevant response
                AIGateway-->>User: Cached response + "may be outdated" note
            else No Cache Available
                AIGateway->>Fallback: Get static fallback
                Fallback-->>AIGateway: Generic helpful response
                AIGateway-->>User: "I'm experiencing issues. Here's what I can help with..."
                AIGateway->>Alert: CRITICAL: All providers down
            end
        end
    end
```

### Agent-Level Error Recovery

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant LLM as LLM
    participant Tool as Tool
    participant Recovery as Recovery Handler
    participant Human as Human Escalation
    participant State as State Manager

    Agent->>LLM: Generate action plan
    LLM-->>Agent: Plan with tool calls

    loop For each step (max 10 iterations)
        Agent->>Tool: Execute step
        alt Tool Error
            Tool-->>Agent: Error response
            Agent->>Agent: Increment error count
            alt Error Count < 3
                Agent->>LLM: "Tool failed: [error]. Adjust approach."
                LLM-->>Agent: Alternative approach
            else Error Count >= 3 (same tool)
                Agent->>Recovery: Tool consistently failing
                Recovery->>Recovery: Mark tool as degraded
                Recovery-->>Agent: Skip tool, use alternative
            end
        else Unexpected Output
            Tool-->>Agent: Unexpected format/content
            Agent->>LLM: "Got unexpected result. Validate and adapt."
            LLM-->>Agent: Interpretation or retry strategy
        else Timeout
            Tool-->>Agent: Timeout after 30s
            Agent->>State: Save current progress
            Agent->>Agent: Continue without this result
        end
    end

    alt Max Iterations Reached
        Agent->>Agent: Compile partial results
        Agent->>Human: Escalate with context
        Note over Human: "I completed X of Y steps.<br/>Blocked on: [specifics].<br/>Need help with: [specifics]"
    else Confidence Too Low
        Agent->>Agent: Self-assess quality
        Agent->>Human: "I'm not confident in this answer.<br/>Here's my best attempt + concerns."
    else Budget Exceeded
        Agent->>State: Save state for resume
        Agent->>Human: "Token budget reached.<br/>Progress so far: [summary].<br/>Remaining: [tasks]"
    end
```

### Guardrail Violation Flow

```mermaid
sequenceDiagram
    participant User
    participant InputGuard as Input Guardrails
    participant Agent as Agent
    participant OutputGuard as Output Guardrails
    participant Audit as Audit Log
    participant Security as Security Team

    User->>InputGuard: Potentially malicious input

    InputGuard->>InputGuard: Prompt injection classifier
    InputGuard->>InputGuard: Topic policy check
    InputGuard->>InputGuard: PII detection

    alt Prompt Injection Detected
        InputGuard->>Audit: Log injection attempt (HIGH severity)
        InputGuard->>Security: Alert if repeated attempts
        InputGuard-->>User: "I can't process that request."
    else PII in Input
        InputGuard->>InputGuard: Mask PII tokens
        InputGuard->>Agent: Sanitized input (PII replaced with [REDACTED])
        Agent->>Agent: Process with masked input
        Agent-->>OutputGuard: Response
        OutputGuard->>OutputGuard: Ensure no PII leaked back
        OutputGuard-->>User: Clean response
    else Off-Topic/Prohibited
        InputGuard->>Audit: Log policy violation (LOW severity)
        InputGuard-->>User: "I'm designed to help with [scope]. For [topic], please contact [resource]."
    end

    Note over Agent: Agent generates response normally

    Agent-->>OutputGuard: Generated response

    OutputGuard->>OutputGuard: Content safety scoring
    alt Harmful Content Detected
        OutputGuard->>Audit: Log harmful generation (HIGH severity)
        OutputGuard->>OutputGuard: Regenerate with safety prompt
        OutputGuard-->>User: Safe alternative response
    else Hallucination Detected
        OutputGuard->>OutputGuard: Flag low-groundedness sections
        OutputGuard-->>User: Response with [unverified] markers
    else Data Leak Risk
        OutputGuard->>OutputGuard: Redact sensitive information
        OutputGuard->>Audit: Log potential leak (MEDIUM severity)
        OutputGuard-->>User: Redacted response
    end
```

---

## Summary of Key Patterns

| Flow | Key Architectural Insight |
|------|--------------------------|
| End-to-End | Every request passes through multiple validation and control points |
| RAG | Retrieval is a multi-strategy pipeline, not a single vector search |
| Tool Calling | Every tool call goes through validation, policy, auth, and audit |
| Human-in-the-Loop | The system can pause, persist state, and resume after approval |
| Multi-Agent | Orchestration manages dependencies, parallelism, and aggregation |
| Error/Fallback | Multiple fallback levels ensure graceful degradation, never silent failure |
