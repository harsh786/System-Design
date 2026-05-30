# Multi-Agent Systems — Deep Conceptual Guide

## Overview

Multi-agent systems (MAS) involve multiple AI agents collaborating, competing, or coordinating to solve problems that exceed the capability of a single agent. Each agent has its own role, tools, memory, and decision-making logic. The system's intelligence emerges from their interaction patterns.

**Core insight**: Multi-agent is NOT about having more agents. It's about having the RIGHT decomposition where each agent has a clear, bounded responsibility with well-defined interfaces.

---

## 9 Multi-Agent Patterns

### Pattern 1: Supervisor-Worker

```
┌─────────────┐
│  Supervisor  │ ← Decomposes task, assigns, monitors, aggregates
└──────┬──────┘
       │ assigns subtasks
  ┌────┼────┐
  ▼    ▼    ▼
┌───┐┌───┐┌───┐
│W1 ││W2 ││W3 │ ← Specialized workers execute subtasks
└───┘└───┘└───┘
```

**When to use**: Complex tasks that can be decomposed into independent subtasks.
**Key decisions**: How does supervisor decide when to delegate vs do itself? How does it handle worker failure?

**Supervisor responsibilities**:
- Task decomposition and dependency analysis
- Worker selection based on capability matching
- Load balancing across workers
- Result quality verification
- Retry/reassignment on failure
- Cost budget enforcement across all workers
- Termination decision (enough quality? budget exhausted?)

**Worker characteristics**:
- Narrow, well-defined capability
- Own tools and system prompt
- Report results back to supervisor
- Don't communicate with other workers directly
- Stateless (supervisor manages state)

---

### Pattern 2: Router-Specialist

```
User Query → [Router] → Specialist A (billing)
                      → Specialist B (technical)
                      → Specialist C (general)
```

**When to use**: Queries span multiple domains, each requiring deep expertise.
**Key insight**: Router is lightweight (classification only), specialists are heavyweight (deep domain).

**Router logic** (hybrid approach):
1. Rule-based: keyword matching, regex patterns → fast, cheap
2. LLM-based: intent classification with confidence score
3. Ensemble: rules first, LLM for ambiguous cases

**Specialist design**:
- Each specialist has domain-specific system prompt, tools, and knowledge
- Specialists don't know about each other
- Router handles handoff if conversation changes domain
- Each specialist maintains its own conversation context

**Fallback strategy**:
- If confidence < threshold → ask clarifying question
- If specialist fails → route to generalist
- If no specialist matches → escalate to human

---

### Pattern 3: Planner-Executor

```
User Goal → [Planner] → Step 1 → [Executor] → Result 1
                       → Step 2 → [Executor] → Result 2
                       → Step 3 → [Executor] → Result 3
                       → [Planner re-evaluates if needed]
```

**When to use**: Multi-step tasks where later steps depend on earlier results.
**Key insight**: Separation of "what to do" from "how to do it" enables replanning.

**Planner agent**:
- Receives high-level goal
- Produces ordered list of steps with dependencies
- Each step has: description, expected output, success criteria, estimated cost
- Can replan mid-execution if a step fails or produces unexpected results
- Maintains plan state (completed, in-progress, pending, failed)

**Executor agent**:
- Receives single step + context from prior steps
- Has access to tools (code execution, search, APIs)
- Returns structured result + success/failure indicator
- Stateless—doesn't know the overall plan

**Replanning triggers**:
- Step failure (after retries exhausted)
- Step output doesn't match expected format
- New information invalidates remaining plan
- Cost exceeds step estimate by >2x
- Human requests plan modification

---

### Pattern 4: Critic-Refiner

```
[Generator] → Draft → [Critic] → Feedback → [Generator] → Improved Draft
                                                              ↓
                                              [Critic] → "Good enough" → Final
```

**When to use**: Tasks where quality matters and iterative refinement helps (writing, code, designs).
**Key insight**: The critic has different evaluation criteria than the generator.

**Generator agent**: Optimizes for creativity, completeness, coherence.
**Critic agent**: Evaluates against rubric—accuracy, clarity, edge cases, security, performance.

**Convergence strategy**:
- Max iterations (typically 2-3)
- Quality threshold (critic scores above bar)
- Diminishing improvement detection (delta < epsilon)
- Cost budget exceeded

---

### Pattern 5: Debate/Judge

```
[Proposer A] → Solution A ─┐
                            ├→ [Judge] → Winner + Reasoning
[Proposer B] → Solution B ─┘

Multi-round variant:
[A] → [B critiques] → [A rebuts] → [Judge]
```

**When to use**: High-stakes decisions, reducing hallucination, exploring solution space.
**Key insight**: Adversarial pressure surfaces weaknesses that single-agent misses.

**Structured debate protocol**:
1. Round 1: Each proposer generates solution independently
2. Round 2: Each proposer critiques the other's solution
3. Round 3: Each proposer rebuts criticisms
4. Judge evaluates based on: evidence quality, logical soundness, practical feasibility

**Judge criteria**:
- Doesn't generate solutions (avoids bias)
- Has clear rubric
- Must justify decision with evidence from debate
- Can declare "no winner" and request more rounds

---

### Pattern 6: Blackboard

```
┌──────────────────────────────────┐
│         BLACKBOARD (shared state) │
│  - Hypotheses                     │
│  - Evidence                       │
│  - Constraints                    │
│  - Partial solutions              │
└──────────────────────────────────┘
    ↑↓          ↑↓          ↑↓
[Agent A]   [Agent B]   [Agent C]
(reads blackboard, contributes when it can)
```

**When to use**: Problems requiring integration of multiple knowledge sources where agents can contribute asynchronously.
**Key insight**: Agents don't communicate directly—they communicate through shared state.

**Blackboard protocol**:
- Any agent can read the full blackboard
- Any agent can add hypotheses/evidence
- A controller decides which agent to activate next
- Agents contribute only when they have relevant expertise
- Solution emerges from accumulated contributions

**Use cases**: Complex diagnosis, research synthesis, collaborative writing.

---

### Pattern 7: Market/Auction

```
[Task Announcer] → "Who can do X for <$Y in <Z seconds?"
    ↓
[Agent A]: "I can, $0.03, 2s, confidence: 0.9"
[Agent B]: "I can, $0.01, 5s, confidence: 0.7"
[Agent C]: "I cannot"
    ↓
[Announcer selects Agent A] → Execute → Result
```

**When to use**: Dynamic task allocation where multiple agents COULD handle a task, and you want optimal selection.
**Key insight**: Agents bid based on their confidence, cost, and speed. Market dynamics optimize allocation.

**Bid parameters**:
- Estimated cost (tokens/API calls)
- Estimated latency
- Confidence score (how well can I handle this?)
- Current load (am I busy?)

**Selection criteria**: Weighted combination of cost, speed, confidence, past performance.

---

### Pattern 8: Human-Agent Team

```
[Agent] → Plan → [Human Review] → Approved? → [Agent Executes]
                                 → Rejected? → [Agent Revises Plan]
                                 → Modified? → [Agent Adapts]
```

**When to use**: High-stakes tasks requiring human judgment, compliance, or domain expertise.
**Key insight**: The agent augments human capability; the human provides judgment and accountability.

**Human-in-the-loop patterns**:
- **Approval gate**: Agent proposes, human approves/rejects
- **Steering**: Human provides direction, agent executes details
- **Exception handling**: Agent handles routine, escalates edge cases
- **Audit trail**: Agent acts, human reviews asynchronously

**Critical design decisions**:
- What requires human approval? (Cost threshold, risk level, reversibility)
- How long to wait for human? (Timeout → safe default action)
- How to present information to human? (Concise, actionable, with context)

---

### Pattern 9: A2A Remote Collaboration (Agent-to-Agent)

```
┌─────────────────┐         ┌─────────────────┐
│  Organization A  │  A2A    │  Organization B  │
│  ┌───────────┐  │ Protocol│  ┌───────────┐  │
│  │  Agent A   │←─┼────────┼─→│  Agent B   │  │
│  └───────────┘  │         │  └───────────┘  │
│  (Travel Agent) │         │  (Hotel Agent)  │
└─────────────────┘         └─────────────────┘
```

**When to use**: Cross-organization agent collaboration, microservice-style agent architectures.
**Key insight**: Agents from different systems/orgs collaborate via standardized protocol (Google's A2A).

**A2A Protocol concepts**:
- **Agent Card**: Published capability description (like an API spec for agents)
- **Task**: Unit of work with lifecycle (submitted → working → completed/failed)
- **Message**: Communication between agents within a task
- **Artifact**: Output produced by an agent

**Design considerations**:
- Trust boundaries between agents
- Authentication and authorization
- Rate limiting and quota management
- Schema versioning for agent cards
- Fallback when remote agent is unavailable

---

## Smart Autonomous Agents

### Goal Decomposition
```
High-level goal: "Migrate our API from REST to GraphQL"
    ↓ decompose
Sub-goals:
  1. Analyze existing REST endpoints
  2. Design GraphQL schema
  3. Implement resolvers
  4. Update client code
  5. Test and validate
  6. Deploy with feature flag
    ↓ decompose further
Sub-sub-goals:
  1.1 List all endpoints
  1.2 Document request/response shapes
  1.3 Identify relationships between resources
  ...
```

**Decomposition strategies**:
- **Functional**: Break by capability needed (research, code, test)
- **Sequential**: Break by order of execution
- **Hierarchical**: Break into layers of abstraction
- **Risk-based**: Isolate high-risk steps for extra verification

### Planning

Agents plan by:
1. Analyzing goal and constraints
2. Identifying required capabilities and tools
3. Generating candidate plans (possibly multiple)
4. Evaluating plans (cost, risk, feasibility)
5. Selecting best plan
6. Monitoring execution and replanning as needed

**Plan representation**:
```python
Plan = {
    "steps": [
        {"id": 1, "action": "search", "deps": [], "est_cost": 0.01},
        {"id": 2, "action": "analyze", "deps": [1], "est_cost": 0.05},
        {"id": 3, "action": "generate", "deps": [2], "est_cost": 0.10},
    ],
    "total_est_cost": 0.16,
    "estimated_time": "45s",
    "success_criteria": "Generated code passes all tests"
}
```

### Tool Use

Agents extend their capabilities through tools:
- **Information tools**: Search, database queries, API calls
- **Action tools**: Code execution, file operations, deployments
- **Communication tools**: Email, Slack, notifications
- **Verification tools**: Tests, linters, validators

**Tool selection strategy**:
- Agent receives tool descriptions in system prompt
- LLM decides which tool to call based on current step
- Tool results feed back into agent's context
- Agent decides if more tool calls needed or task complete

### Memory

**Memory types for agents**:
1. **Working memory**: Current conversation/task context (context window)
2. **Short-term memory**: Recent interactions, scratchpad (session-scoped)
3. **Long-term memory**: Persistent knowledge, learned patterns (vector DB, KV store)
4. **Episodic memory**: Past task executions and outcomes (for learning)

**Memory architecture**:
```
[Agent] → writes to → [Working Memory (context)]
        → summarizes to → [Short-term Memory (session)]
        → extracts to → [Long-term Memory (vector DB)]
        → logs to → [Episodic Memory (task history)]
```

### Reflection

Agents improve through self-reflection:
```
After task completion:
  1. Did I achieve the goal? (outcome evaluation)
  2. What worked well? (positive reinforcement)
  3. What failed? Why? (root cause analysis)
  4. What would I do differently? (strategy improvement)
  5. Store reflection in episodic memory
```

### Self-Correction

```
[Agent produces output]
    ↓
[Self-check against criteria]
    ↓
Pass? → Return output
Fail? → Identify error → Generate correction → Re-check
    ↓
Max retries exceeded? → Escalate to human/supervisor
```

### Delegation

Agent decides to delegate when:
- Task requires capability it doesn't have
- Task is parallelizable and delegation saves time
- Task requires different permission level
- Workload exceeds capacity

### Human Approval

Triggered when:
- Cost exceeds threshold
- Action is irreversible (delete, deploy, send)
- Confidence is below threshold
- Policy requires human sign-off
- First time performing this action type

### State Persistence

```python
AgentState = {
    "task_id": "uuid",
    "status": "in_progress",
    "plan": [...],
    "completed_steps": [...],
    "current_step": 3,
    "context": {...},
    "cost_so_far": 0.23,
    "created_at": "2024-01-01T00:00:00Z",
    "last_checkpoint": "2024-01-01T00:05:00Z"
}
# Persisted to DB → agent can resume after crash
```

### Auditability

Every agent action is logged:
```json
{
    "timestamp": "2024-01-01T00:05:00Z",
    "agent_id": "planner-001",
    "action": "tool_call",
    "tool": "code_executor",
    "input": "...",
    "output": "...",
    "cost": 0.003,
    "latency_ms": 1200,
    "decision_reasoning": "Step 3 requires code execution to validate schema"
}
```

### Sandboxing

Agents operate within boundaries:
- **Resource limits**: Max tokens, max cost, max time
- **Permission boundaries**: Which tools, which APIs, which data
- **Action restrictions**: Read-only vs read-write, approved action list
- **Network isolation**: Cannot access unauthorized endpoints
- **Output validation**: Results checked before returning to user

---

## Autonomy Levels (L0–L5)

| Level | Name | Description | Human Role | Example |
|-------|------|-------------|------------|---------|
| L0 | LLM Only | Single prompt→response, no tools | Initiator | ChatGPT basic Q&A |
| L1 | Tool-Assisted | LLM + tools, human approves each action | Approver per action | Copilot with confirmation |
| L2 | Guided Autonomous | Agent executes plan, human approves plan | Plan approver | "Here's my plan, ok?" |
| L3 | Bounded Autonomous | Agent acts within guardrails, escalates edge cases | Exception handler | Customer support bot |
| L4 | Monitored Autonomous | Agent acts freely, human monitors async | Auditor | Code review bot |
| L5 | Fully Autonomous | Agent acts without human oversight | None (post-hoc audit) | Autonomous trading |

### Selecting Autonomy Level

```
Decision factors:
  - Reversibility of actions (irreversible → lower level)
  - Cost of mistakes (high cost → lower level)
  - Frequency of task (high frequency → higher level after trust built)
  - Regulatory requirements (regulated → lower level)
  - Confidence in agent capability (proven → higher level)
  - Organizational risk tolerance
```

### Enterprise Principle

> **"Most production agents should be L2–L4, not fully autonomous L5."**

**Rationale**:
- L5 is appropriate ONLY for low-risk, reversible, well-understood tasks
- Enterprise environments have compliance, audit, liability requirements
- Human oversight is a feature, not a limitation
- Progressive autonomy: start at L2, prove reliability, graduate to L3/L4
- Even L4 requires monitoring dashboards, alerting, kill switches

**Graduation criteria** (L2→L3→L4):
1. 1000+ successful executions without human override
2. Error rate < 0.1%
3. No safety incidents in 30 days
4. Cost within 10% of estimates
5. Stakeholder sign-off

---

## 8 Failure Modes

### 1. Agents Talk Too Much (Token Explosion)
**Symptom**: Agents pass increasingly long messages to each other, context grows exponentially.
**Cause**: No summarization between agent handoffs, full history forwarded.
**Fix**: 
- Summarize context at each handoff
- Fixed-size message protocol between agents
- Token budget per agent-to-agent message

### 2. Cost Explosion
**Symptom**: Multi-agent task costs 100x more than expected.
**Cause**: No global cost budget, each agent optimizes locally.
**Fix**:
- Global cost budget with per-agent allocation
- Cost tracking at orchestrator level
- Circuit breaker: stop all agents if budget exceeded
- Cost estimation before execution

### 3. Circular Delegation
**Symptom**: Agent A delegates to B, B delegates to C, C delegates back to A.
**Cause**: Unclear task boundaries, agents unsure of their responsibility.
**Fix**:
- Delegation graph tracking (detect cycles)
- Max delegation depth (typically 2-3)
- Each agent has explicit "I own this" criteria
- Supervisor pattern prevents peer-to-peer delegation

### 4. Unclear Ownership
**Symptom**: Task falls through cracks—no agent handles it. Or multiple agents duplicate work.
**Cause**: Overlapping or gapped agent responsibilities.
**Fix**:
- Explicit responsibility matrix
- Default handler for unmatched tasks
- Router with exhaustive classification
- Overlap detection in agent capabilities

### 5. Conflicting Instructions
**Symptom**: Agent A's output contradicts Agent B's requirements.
**Cause**: Agents have inconsistent system prompts or goals.
**Fix**:
- Global invariants enforced by orchestrator
- Consistency checking between agent outputs
- Single source of truth for shared constraints
- Hierarchical authority (supervisor overrides workers)

### 6. Weak Evals
**Symptom**: System seems to work but quality degrades silently.
**Cause**: No automated quality checks between agents, no end-to-end evaluation.
**Fix**:
- Per-agent output validation
- End-to-end task success metrics
- Automated eval suite (not just vibes)
- A/B testing multi-agent vs single-agent

### 7. Overly Broad Tool Permissions
**Symptom**: Agent uses powerful tool inappropriately (deletes data, sends emails).
**Cause**: All agents have access to all tools.
**Fix**:
- Principle of least privilege per agent
- Tool permissions scoped to agent role
- Dangerous tools require explicit approval
- Separate read/write tool sets

### 8. No Termination Condition
**Symptom**: Agents loop forever, continuously "improving" or "checking."
**Cause**: No clear definition of "done."
**Fix**:
- Explicit success criteria per task
- Max iterations/rounds
- Time budget
- "Good enough" threshold (not perfection)
- Orchestrator enforces termination

---

## When to Use Multi-Agent (vs Alternatives)

### Use Single Agent When:
- Task is well-scoped and doesn't require diverse expertise
- Latency is critical (multi-agent adds overhead)
- Cost is constrained (multi-agent multiplies LLM calls)
- Task doesn't benefit from separation of concerns
- You're prototyping (start simple, add agents later)

### Use Deterministic Workflow When:
- Steps are known in advance and don't change
- No reasoning needed for routing/planning
- High volume, low cost requirement
- Reliability > flexibility
- Traditional software engineering suffices

### Use Multi-Agent When:
- Task requires diverse expertise (research + code + review)
- Quality benefits from adversarial checking (debate pattern)
- Task is complex enough to benefit from decomposition
- You need different autonomy levels for different subtasks
- Parallel execution provides meaningful speedup
- Different parts need different tool permissions

### Decision Framework:
```
Is the task decomposable into independent subtasks?
  No → Single agent
  Yes ↓
Do subtasks require different capabilities/tools?
  No → Single agent with multiple tools
  Yes ↓
Does quality benefit from separation of concerns?
  No → Single agent with role-switching prompts
  Yes ↓
Is the added cost/latency acceptable?
  No → Single agent (accept quality tradeoff)
  Yes → Multi-agent system
```

---

## Communication Patterns Between Agents

### 1. Request-Response (Synchronous)
```
Agent A → request → Agent B
Agent A ← response ← Agent B
```
Simple, easy to reason about. Blocks caller.

### 2. Fire-and-Forget (Asynchronous)
```
Agent A → message → Queue → Agent B (processes later)
```
Non-blocking, but no immediate result.

### 3. Publish-Subscribe
```
Agent A → publishes event → Event Bus
Agent B (subscribed) → receives event
Agent C (subscribed) → receives event
```
Decoupled, but harder to trace.

### 4. Shared State (Blackboard)
```
Agent A → writes to → Shared State
Agent B → reads from → Shared State
```
No direct communication, state is the medium.

### 5. Streaming
```
Agent A → token stream → Agent B (processes incrementally)
```
Low latency for dependent sequential work.

---

## State Sharing and Coordination

### Shared State Options:

| Approach | Pros | Cons |
|----------|------|------|
| Pass in messages | Simple, explicit | Context grows, repetition |
| Shared memory/DB | Agents see latest state | Concurrency issues |
| Event sourcing | Full history, replayable | Complex, storage cost |
| Blackboard | Flexible, async | Harder to debug |

### Coordination Strategies:

1. **Centralized (Supervisor)**: One agent coordinates all others. Simple but single point of failure.
2. **Decentralized (Peer-to-peer)**: Agents coordinate directly. Flexible but complex.
3. **Hierarchical**: Tree of supervisors. Scalable but rigid.
4. **Market-based**: Agents bid for tasks. Adaptive but unpredictable.

---

## Agent Composition and Decomposition Strategies

### Composition (Building Up):
```
Simple Agent + Simple Agent = Composite Agent
[Search Agent] + [Summarize Agent] = [Research Agent]
[Code Agent] + [Test Agent] = [TDD Agent]
```

### Decomposition (Breaking Down):
```
Complex Agent → Multiple Simple Agents
[Full-Stack Agent] → [Frontend Agent] + [Backend Agent] + [DB Agent]
```

### When to decompose:
- Agent's system prompt exceeds ~2000 words (too many responsibilities)
- Agent needs conflicting personas (creative vs critical)
- Agent's tool set is too broad (security risk)
- Different parts need different models (cheap/fast vs expensive/smart)
- Team wants to develop/test agents independently

### When to compose:
- Two agents always called together (reduce overhead)
- Context loss at boundary hurts quality
- Latency of handoff is unacceptable
- Agents are too granular (overhead > benefit)

---

## Production Safeguards for Multi-Agent Systems

### 1. Global Budget Enforcement
```python
class GlobalBudget:
    max_cost: float = 1.00          # USD
    max_time: float = 120.0         # seconds
    max_total_tokens: int = 100000
    max_agent_invocations: int = 20
```

### 2. Circuit Breakers
- Per-agent failure threshold (3 failures → disable agent)
- Global failure threshold (5 total failures → abort task)
- Cost rate detection (spending too fast → pause and alert)

### 3. Observability
- Distributed tracing (trace ID across all agents)
- Per-agent metrics (latency, cost, success rate)
- Agent communication logs (who said what to whom)
- Dashboard showing active agents, task progress, budget usage

### 4. Kill Switch
- Immediate termination of all agents
- Graceful shutdown (complete current step, then stop)
- Selective shutdown (disable specific agent)

### 5. Replay and Debug
- All agent interactions logged with timestamps
- Can replay a multi-agent task step-by-step
- Can modify and re-run from any checkpoint

### 6. Testing Strategy
- Unit test: each agent in isolation
- Integration test: agent pairs
- End-to-end test: full multi-agent flow
- Chaos test: inject agent failures, slow responses
- Cost test: verify budget enforcement works

---

## Summary

Multi-agent systems are powerful but complex. The key principles:

1. **Start with single agent**, add agents only when needed
2. **Clear boundaries**: each agent has ONE job
3. **Explicit communication**: no implicit assumptions between agents
4. **Budget enforcement**: global cost/time limits are non-negotiable
5. **Termination conditions**: every loop must end
6. **Observability**: you must see what every agent is doing
7. **Progressive autonomy**: start supervised, earn independence
8. **Eval-driven**: measure multi-agent vs single-agent quality/cost tradeoff
