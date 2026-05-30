# Agent Fundamentals — Deep Concept Guide

## 1. What Is an AI Agent?

An AI agent is a **software system that uses an LLM as its reasoning engine** to autonomously decide what actions to take in pursuit of a goal. Unlike a simple chatbot (which generates text) or a pipeline (which follows fixed steps), an agent has:

| Component | Description |
|-----------|-------------|
| **Goal** | A high-level objective provided by the user or system (e.g., "book the cheapest flight to Tokyo") |
| **Instructions** | System prompt + behavioral guidelines that constrain how the agent operates |
| **Tools** | Functions the agent can invoke (APIs, databases, code execution, search) |
| **State** | Current context: what has happened so far, what the agent knows right now |
| **Memory** | Persistent knowledge across turns (working memory) and across sessions (long-term memory) |
| **Planning** | The ability to decompose a goal into sub-steps before acting |
| **Execution Loop** | The core cycle: observe → think → act → observe result → decide next step |
| **Observation Handling** | Parsing and interpreting tool outputs, errors, and environment changes |
| **Guardrails** | Safety constraints that prevent harmful, costly, or unauthorized actions |
| **Evaluation** | Mechanisms to judge whether the goal has been achieved or progress is being made |
| **Monitoring** | Observability into what the agent is doing, token spend, latency, success rate |

### The Critical Distinction

```
Chatbot:    User → LLM → Response
Pipeline:   Input → Step1 → Step2 → Step3 → Output
Agent:      Goal → [Observe → Plan → Act → Observe]* → Result
```

The asterisk `*` means the loop repeats an **unknown number of times**. This is what makes agents powerful and dangerous — they have variable execution paths, variable cost, and variable outcomes.

---

## 2. The Basic Agent Loop

```
┌─────────────────────────────────────────────┐
│              AGENT EXECUTION LOOP            │
├─────────────────────────────────────────────┤
│                                             │
│   ┌──────────┐                              │
│   │ OBSERVE  │ ← Receive input/tool result  │
│   └────┬─────┘                              │
│        │                                    │
│        ▼                                    │
│   ┌──────────┐                              │
│   │  PLAN    │ ← LLM reasons about state    │
│   └────┬─────┘                              │
│        │                                    │
│        ▼                                    │
│   ┌──────────┐                              │
│   │   ACT    │ ← Execute tool/respond       │
│   └────┬─────┘                              │
│        │                                    │
│        ▼                                    │
│   ┌──────────┐                              │
│   │ OBSERVE  │ ← See result of action       │
│   └────┬─────┘                              │
│        │                                    │
│        ▼                                    │
│   ┌──────────────┐                          │
│   │CONTINUE/STOP │ ← Goal met? Max steps?   │
│   └──────────────┘                          │
│                                             │
└─────────────────────────────────────────────┘
```

### Loop Termination Conditions

1. **Goal achieved** — Agent determines task is complete
2. **Max steps reached** — Hard limit prevents infinite loops
3. **Token budget exhausted** — Cost ceiling hit
4. **Timeout** — Wall-clock time exceeded
5. **Unrecoverable error** — Tool failure with no fallback
6. **Human intervention** — Agent escalates or is stopped
7. **Guardrail triggered** — Safety constraint blocks continuation

---

## 3. Agent Types (15 Types)

### Type 1: Simple Tool-Calling Agent

**What:** Single LLM call that may invoke one or more tools, then returns.

**Use Cases:** Customer support Q&A with knowledge base lookup, simple calculations, single API calls.

**When to use:** Task can be completed in 1-3 tool calls. No complex reasoning required.

```
User → LLM (decides tool) → Tool → LLM (formats result) → User
```

---

### Type 2: Workflow Agent (Deterministic)

**What:** Pre-defined sequence of steps with conditional branching. The LLM is used at specific nodes but the overall flow is fixed.

**Use Cases:** Order processing, insurance claim handling, onboarding flows, document review pipelines.

**When to use:** Process is well-understood, compliance matters, you need predictability.

```
Start → Classify → [Branch A | Branch B] → Validate → Complete
```

---

### Type 3: Planner-Executor Agent

**What:** Separates planning from execution. One LLM call creates a plan (list of steps), then a simpler executor runs each step.

**Use Cases:** Complex research tasks, multi-step data analysis, project planning.

**When to use:** Task requires 5+ steps, you want plan visibility before execution, you need plan approval.

```
Goal → Planner LLM → [Step1, Step2, ...StepN] → Executor → Results
```

---

### Type 4: ReAct Agent (Reason + Act)

**What:** Interleaves reasoning (chain-of-thought) with actions. Each step: Thought → Action → Observation.

**Use Cases:** General-purpose problem solving, debugging, research, any task where reasoning path matters.

**When to use:** Default choice when task complexity is unknown. Good balance of capability and observability.

```
Thought: I need to find the user's order status
Action: lookup_order(order_id="12345")
Observation: Order is "shipped", tracking: UPS1234
Thought: I have the information, I can respond
Action: respond("Your order has shipped. Tracking: UPS1234")
```

---

### Type 5: Reflection Agent

**What:** Agent generates output, then critiques its own output, then refines. May loop multiple times.

**Use Cases:** Code generation with self-review, essay writing, complex analysis where quality matters more than speed.

**When to use:** Output quality is critical, task has clear quality criteria, you can afford 2-3x token cost.

```
Generate → Critique → Refine → Critique → Final
```

---

### Type 6: Router Agent

**What:** Classifies incoming request and routes to specialized sub-agents or workflows.

**Use Cases:** Multi-domain support systems, API gateways, triage systems.

**When to use:** You have multiple specialized agents and need intelligent dispatch.

```
Input → Router LLM → [Agent A | Agent B | Agent C | Fallback]
```

---

### Type 7: Supervisor Agent

**What:** Orchestrator that manages multiple worker agents, assigns tasks, collects results, and synthesizes.

**Use Cases:** Complex projects requiring multiple skills, parallel research, collaborative document creation.

**When to use:** Task naturally decomposes into parallel sub-tasks requiring different tools/expertise.

```
Supervisor → [Worker1, Worker2, Worker3] → Supervisor (synthesize) → Result
```

---

### Type 8: Multi-Agent System

**What:** Multiple agents that communicate peer-to-peer (no central supervisor). May debate, negotiate, or collaborate.

**Use Cases:** Adversarial testing (red team vs blue team), debate for better reasoning, market simulations.

**When to use:** Problem benefits from multiple perspectives, or you need checks and balances.

```
Agent A ←→ Agent B ←→ Agent C (message passing)
```

---

### Type 9: Autonomous Agent

**What:** Long-running agent with persistent memory, self-directed goal pursuit, minimal human oversight.

**Use Cases:** Continuous monitoring, automated research assistants, self-improving systems.

**When to use:** Almost never in production. High risk. Only when: task is low-stakes, environment is sandboxed, and you have kill switches.

```
Goal → [Plan → Execute → Observe → Replan]* (runs for hours/days)
```

---

### Type 10: Human-in-the-Loop Agent

**What:** Agent that explicitly requests human approval at critical decision points.

**Use Cases:** Financial transactions, content publishing, code deployment, any high-stakes action.

**When to use:** Actions are irreversible, high-value, or have compliance requirements.

```
Agent → Proposes Action → Human Approves/Rejects → Agent Continues/Revises
```

---

### Type 11: Code-Execution Agent

**What:** Agent that writes and executes code in a sandbox to solve problems.

**Use Cases:** Data analysis, math problems, API integration testing, system administration.

**When to use:** Task is better solved by code than by natural language reasoning.

```
Problem → Write Code → Execute in Sandbox → Observe Output → Iterate
```

---

### Type 12: Research Agent

**What:** Agent specialized for gathering, synthesizing, and citing information from multiple sources.

**Use Cases:** Literature review, competitive analysis, due diligence, fact-checking.

**When to use:** Task requires synthesizing information from multiple sources with citations.

```
Question → Search → Read → Extract → Search More → Synthesize → Cite
```

---

### Type 13: Transactional Agent

**What:** Agent that performs real-world transactions (payments, bookings, orders) with ACID-like guarantees.

**Use Cases:** E-commerce purchasing, appointment booking, fund transfers.

**When to use:** Actions have real-world financial/legal consequences. Requires idempotency, rollback, confirmation.

```
Intent → Validate → Confirm → Execute → Verify → Receipt
```

---

### Type 14: Voice Agent

**What:** Agent operating in real-time voice conversation with streaming input/output.

**Use Cases:** Phone support, voice assistants, accessibility interfaces.

**When to use:** Interface is voice. Requires: low latency (<500ms), interrupt handling, turn-taking.

```
Audio In → STT → Agent → TTS → Audio Out (streaming, real-time)
```

---

### Type 15: Multimodal Agent

**What:** Agent that processes and generates multiple modalities (text, images, video, audio, files).

**Use Cases:** Design assistants, document processing (OCR + reasoning), video analysis, accessibility.

**When to use:** Task involves non-text inputs or requires non-text outputs.

```
[Image + Text] → Multimodal LLM → [Text + Generated Image] → Tools → Result
```

---

## 4. Autonomy Levels (L0–L5)

| Level | Name | Description | Human Role | Example |
|-------|------|-------------|-----------|---------|
| **L0** | No autonomy | LLM generates suggestions, human executes everything | Executor | Autocomplete, copilot suggestions |
| **L1** | Confirmation required | Agent proposes actions, human approves each one | Approver | PR review assistant that suggests changes |
| **L2** | Bounded autonomy | Agent executes within strict boundaries, escalates outside | Supervisor | Customer support bot with refund limit |
| **L3** | Monitored autonomy | Agent operates independently, human reviews async | Monitor | Code review bot, content moderation |
| **L4** | Full autonomy (recoverable) | Agent operates without oversight, but actions are reversible | Auditor | Automated testing, staging deployments |
| **L5** | Full autonomy (irreversible) | Agent performs irreversible actions without human oversight | None (post-hoc audit) | Autonomous trading (extremely rare) |

### Decision Framework for Choosing Autonomy Level

```
Is the action reversible?
├── No → Is it high-value (>$1000 or legal/compliance)?
│   ├── Yes → L1 (Confirmation required)
│   └── No → L2 (Bounded autonomy with escalation)
└── Yes → Is real-time response required?
    ├── Yes → L3 or L4 (Monitored/Full autonomy)
    └── No → Is accuracy critical?
        ├── Yes → L2 (Bounded with guardrails)
        └── No → L4 (Full autonomy, recoverable)
```

### Pro Rule: Start at L1, graduate to higher levels based on eval scores

Never deploy an agent at L3+ without:
- 95%+ success rate on held-out evals
- Comprehensive guardrails
- Kill switch
- Cost ceiling
- Monitoring and alerting

---

## 5. Agent Training & Improvement (10 Levers)

### Lever 1: Prompt Tuning

**What:** Refining the system prompt, few-shot examples, and output format instructions.

**Impact:** High (often 20-40% improvement)  
**Cost:** Low (no compute, no data collection)  
**When:** First lever to pull. Always.

**Techniques:**
- Add explicit failure mode examples
- Add "do NOT" constraints for common mistakes
- Structured output format with examples
- Chain-of-thought scaffolding in system prompt
- Dynamic few-shot selection based on input similarity

---

### Lever 2: Tool Tuning

**What:** Improving tool descriptions, parameter schemas, error messages, and adding/removing tools.

**Impact:** High (agent can only be as good as its tools)  
**Cost:** Low-Medium  
**When:** Agent calls wrong tools or uses tools incorrectly.

**Techniques:**
- Better tool descriptions with examples
- Clearer parameter descriptions and constraints
- Fewer tools (reduce choice paralysis — max 10-15 tools)
- Tool grouping/namespacing
- Better error messages from tools
- Adding "helper" tools that reduce multi-step patterns

---

### Lever 3: Graph/Workflow Tuning

**What:** Changing the agent's execution graph — adding deterministic steps, changing routing, adding checkpoints.

**Impact:** Very High (architectural change)  
**Cost:** Medium (engineering effort)  
**When:** Agent fails on structural patterns (wrong order, missing steps, infinite loops).

**Techniques:**
- Add deterministic pre/post-processing steps
- Add classification router before open-ended reasoning
- Add validation checkpoints between steps
- Convert free-form agent to state machine for known workflows
- Add max-steps and circuit breakers

---

### Lever 4: Memory Tuning

**What:** Changing what the agent remembers, how it retrieves memories, and memory format.

**Impact:** Medium-High  
**Cost:** Medium  
**When:** Agent forgets context, repeats mistakes, or doesn't learn from past interactions.

**Techniques:**
- Summarize long conversations before continuing
- Store and retrieve user preferences
- Episode memory (successful past interactions as few-shot)
- Semantic memory (facts extracted from interactions)
- Memory decay (forget old, irrelevant memories)

---

### Lever 5: Retriever Tuning

**What:** Improving the RAG pipeline that feeds context to the agent.

**Impact:** High (garbage in, garbage out)  
**Cost:** Medium  
**When:** Agent has wrong information or can't find relevant context.

**Techniques:**
- Better chunking strategy
- Hybrid search (semantic + keyword)
- Re-ranking retrieved results
- Query expansion/rewriting
- Metadata filtering
- Smaller, more precise chunks with surrounding context

---

### Lever 6: Model Routing

**What:** Using different models for different tasks (cheap/fast for easy, expensive/smart for hard).

**Impact:** Medium (cost reduction + quality improvement)  
**Cost:** Low-Medium  
**When:** You're using one model for everything and either overpaying or under-performing.

**Techniques:**
- Classify difficulty → route to appropriate model
- Use small model for tool selection, large model for reasoning
- Use small model for summarization, large model for generation
- Cascade: try small model first, escalate if confidence is low

---

### Lever 7: Fine-Tuning

**What:** Training a model on your specific agent traces to improve tool calling, format adherence, domain knowledge.

**Impact:** High (but expensive and slow)  
**Cost:** High (data collection, compute, evaluation)  
**When:** All other levers exhausted, you have 1000+ high-quality traces, and you need consistent improvement on specific patterns.

**Techniques:**
- Fine-tune on successful agent traces
- Fine-tune for tool-calling format
- Fine-tune for domain-specific reasoning
- Fine-tune for output format adherence

---

### Lever 8: Distillation

**What:** Using a large model to generate training data for a smaller model.

**Impact:** Medium-High (cost reduction with quality maintenance)  
**Cost:** Medium  
**When:** You have a working agent on GPT-4 level and want to run it on GPT-3.5/small model for cost/latency.

**Techniques:**
- Generate traces with large model → fine-tune small model
- Use large model as judge to filter training data quality
- Progressive distillation (GPT-4 → GPT-4-mini → fine-tuned small)

---

### Lever 9: Human Feedback (RLHF/DPO)

**What:** Collecting human preferences on agent outputs to improve via reinforcement learning.

**Impact:** High (aligns with actual user preferences)  
**Cost:** Very High (human labeling, complex training)  
**When:** You have scale (>10k interactions/day), clear preference signals, and ML infrastructure.

**Techniques:**
- Thumbs up/down on agent responses
- Side-by-side comparison of agent variants
- Reward model training from preferences
- Direct Preference Optimization (DPO) — simpler than RLHF
- Constitutional AI (self-critique based on principles)

---

### Lever 10: Policy Tuning

**What:** Adjusting the rules, constraints, and boundaries the agent operates within.

**Impact:** Medium  
**Cost:** Low  
**When:** Agent is technically capable but makes poor decisions about WHEN to act.

**Techniques:**
- Tighter/looser escalation thresholds
- Confidence-based routing (low confidence → human)
- Cost-based policies (don't spend >$X on a single task)
- Time-based policies (don't run longer than N minutes)
- Scope policies (what the agent IS and ISN'T allowed to do)

---

## 6. Agent Improvement Loop (Production System)

```
Production Traces
       │
       ▼
┌──────────────┐
│ Collect &    │ ← Log every agent run: inputs, steps, tools, outputs, latency, cost
│ Store Traces │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Failure    │ ← Cluster failures by: error type, tool used, user intent,
│  Clustering  │   step where failure occurred, confidence at failure point
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Root Cause  │ ← Label each cluster: wrong tool? bad prompt? missing context?
│   Labeling   │   model limitation? tool bug? ambiguous input?
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Choose Lever │ ← Map root cause to improvement lever (see table below)
│  & Implement │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Eval on    │ ← Run against golden eval set (held-out test cases)
│  Golden Set  │   Must improve target metric without regressing others
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Canary     │ ← Deploy to 5% of traffic, monitor for 24-48h
│   Release    │   Compare metrics vs control
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Monitor    │ ← Track: success rate, latency, cost, user satisfaction
│  & Iterate   │   If regression → rollback. If improvement → promote to 100%
└──────────────┘
```

### Root Cause → Lever Mapping

| Root Cause | First Lever | Second Lever |
|-----------|-------------|--------------|
| Agent calls wrong tool | Tool tuning | Prompt tuning |
| Agent uses tool incorrectly | Tool tuning (better schemas) | Few-shot examples |
| Agent reasoning is wrong | Prompt tuning (CoT) | Model upgrade |
| Agent misses information | Retriever tuning | Memory tuning |
| Agent loops infinitely | Graph tuning (circuit breaker) | Max steps |
| Agent acts when it shouldn't | Policy tuning | Guardrails |
| Agent is too slow | Model routing (smaller model) | Graph tuning |
| Agent is too expensive | Model routing | Distillation |
| Agent format is wrong | Prompt tuning (structured output) | Fine-tuning |
| Agent doesn't escalate | Policy tuning | Confidence thresholds |

---

## 7. Pro Rules

### Rule 1: "Use deterministic workflows where possible"

> If you can solve it with an if-statement, don't use an LLM.

**Why:** LLMs are stochastic. Every LLM call introduces:
- Latency (200ms-30s)
- Cost ($0.001-$0.10 per call)
- Unpredictability (different output each time)
- Failure modes (hallucination, refusal, wrong format)

**Application:**
- Use LLM for classification/routing → use code for execution
- Use LLM for understanding intent → use database queries for data
- Use LLM for generating plans → use deterministic execution for known steps
- Use LLM for edge cases → use rules for common cases

### Rule 2: "Train the agent system before training the model"

> Exhaust Levers 1-6 before touching Levers 7-10.

**Why:**
- Prompt/tool/graph changes are instant, free, and reversible
- Fine-tuning takes weeks, costs thousands, and can regress
- 80% of agent problems are system problems (wrong tools, bad prompts, missing context)
- Only 20% are model capability problems

**Priority Order:**
1. Fix the prompt (hours, free)
2. Fix the tools (days, cheap)
3. Fix the workflow/graph (days, moderate)
4. Fix the retrieval/memory (week, moderate)
5. Route to a better model (minutes, increases cost)
6. Fine-tune (weeks, expensive, risky)

---

## 8. Agent Control Patterns

### Pattern 1: Deterministic Workflow

**What:** Fixed DAG of steps. LLM used only at specific nodes.

**Guarantees:** Predictable execution path, bounded cost, auditable.

**When:** Process is well-understood, compliance required.

```python
# Pseudocode
result = classify(input)       # LLM
data = fetch_data(result.id)   # Deterministic
validated = validate(data)     # Code
output = format(validated)     # Code/LLM
```

---

### Pattern 2: LLM Router

**What:** Single LLM call classifies intent, routes to specialized handler.

**Guarantees:** Bounded to N possible paths. Each path can be independently tested.

```python
route = llm_classify(input, options=["billing", "technical", "general"])
handlers[route].handle(input)
```

---

### Pattern 3: Bounded Loop

**What:** Agent loop with hard maximum iterations.

**Guarantees:** Will terminate. Cost is bounded at N × (cost per step).

```python
for step in range(MAX_STEPS):
    action = agent.think(state)
    if action.type == "finish":
        return action.result
    state = execute(action)
raise MaxStepsExceeded()
```

---

### Pattern 4: State Machine

**What:** Explicit states with defined transitions. Agent can only move between valid states.

**Guarantees:** No invalid states. Clear audit trail. Resumable.

```python
states = {
    "intake": ["classify"],
    "classify": ["simple_response", "complex_handling", "escalate"],
    "complex_handling": ["review", "escalate"],
    "review": ["complete", "revise"],
}
```

---

### Pattern 5: Human Approval Gate

**What:** Agent pauses at critical points and waits for human approval.

**Guarantees:** No high-stakes action without human consent.

```python
if action.risk_level > THRESHOLD:
    approval = await request_human_approval(action)
    if not approval.granted:
        return handle_rejection(approval.reason)
```

---

### Pattern 6: Plan-Then-Execute

**What:** Agent first generates complete plan, plan is validated/approved, then executed step by step.

**Guarantees:** Plan visibility before execution. Can reject bad plans cheaply.

```python
plan = planner.create_plan(goal)
validated_plan = validator.check(plan)  # or human review
for step in validated_plan.steps:
    executor.execute(step)
```

---

### Pattern 7: Supervisor-Worker

**What:** Supervisor agent delegates to specialized workers, synthesizes results.

**Guarantees:** Separation of concerns. Workers are independently testable. Supervisor handles coordination.

```python
sub_tasks = supervisor.decompose(task)
results = await asyncio.gather(*[
    worker_pool.assign(sub_task) for sub_task in sub_tasks
])
final = supervisor.synthesize(results)
```

---

### Pattern 8: Critic-Verifier

**What:** One agent generates, another agent verifies/critiques. Output only accepted if verifier approves.

**Guarantees:** Quality gate. Catches errors before they reach user.

```python
output = generator.generate(input)
critique = verifier.verify(output, criteria)
if critique.passed:
    return output
else:
    return generator.revise(output, critique.feedback)
```

---

### Pattern 9: Fallback Chain

**What:** Try preferred approach first, fall back to simpler/safer alternatives on failure.

**Guarantees:** Graceful degradation. Something always works.

```python
for strategy in [autonomous_agent, guided_workflow, human_handoff]:
    try:
        return await strategy.handle(input, timeout=30)
    except (Timeout, Failure):
        continue
raise AllStrategiesFailed()
```

---

### Pattern 10: Circuit Breaker

**What:** If failure rate exceeds threshold, stop calling the failing component and return cached/default response.

**Guarantees:** Prevents cascade failures. Protects downstream services. Auto-recovers.

```python
if circuit_breaker.is_open(tool_name):
    return fallback_response()

try:
    result = call_tool(tool_name, params)
    circuit_breaker.record_success(tool_name)
    return result
except Exception:
    circuit_breaker.record_failure(tool_name)
    if circuit_breaker.should_open(tool_name):
        circuit_breaker.open(tool_name, cooldown=60)
    raise
```

---

## Summary: When to Use What

| Situation | Pattern | Autonomy Level |
|-----------|---------|---------------|
| Known, repeatable process | Deterministic Workflow | L2 |
| Multiple domains/intents | Router + Specialized Agents | L2-L3 |
| Complex reasoning needed | ReAct with Bounded Loop | L2-L3 |
| High-stakes actions | Human Approval Gate | L1 |
| Quality-critical output | Critic-Verifier | L3 |
| Parallel sub-tasks | Supervisor-Worker | L3 |
| Unknown complexity | Plan-Then-Execute | L2 |
| Unreliable tools | Circuit Breaker + Fallback | L2-L4 |
| Long-running tasks | State Machine (resumable) | L3-L4 |
| Adversarial/safety-critical | Multi-Agent (checks & balances) | L1-L2 |
