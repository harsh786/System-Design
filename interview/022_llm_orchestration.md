# LLM Orchestration and Chaining (Questions 106-110)

## Q106: Design a production LLM orchestration framework

### Problem
Build a production-grade LLM orchestration framework with error handling, retries, streaming, observability, and cost management for multi-step workflows.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   LLM Orchestration Framework                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     Workflow Engine                       │    │
│  │  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐            │    │
│  │  │Step 1│──▶│Step 2│──▶│Step 3│──▶│Step N│            │    │
│  │  └──────┘   └──────┘   └──────┘   └──────┘            │    │
│  │       │           │          │          │               │    │
│  │       ▼           ▼          ▼          ▼               │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │          Middleware Pipeline                      │    │    │
│  │  │  [Retry] [Circuit Break] [Rate Limit] [Cache]   │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                       │
│  ┌───────────────┐  ┌───┴────────────┐  ┌──────────────────┐   │
│  │  Cost Manager │  │  Observability  │  │  Stream Manager  │   │
│  │  (budget,     │  │  (traces, logs, │  │  (SSE, backpres- │   │
│  │   accounting) │  │   metrics)      │  │   sure, merge)   │   │
│  └───────────────┘  └────────────────┘  └──────────────────┘   │
│                          │                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Provider Abstraction Layer                   │    │
│  │  [OpenAI] [Anthropic] [Google] [Azure] [Local/vLLM]     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
from typing import AsyncIterator, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import time

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class StepConfig:
    name: str
    provider: str = "openai"
    model: str = "gpt-4"
    max_retries: int = 3
    timeout_seconds: float = 30.0
    max_cost_usd: float = 0.50
    cache_ttl: int = 3600
    fallback_model: str = None

@dataclass 
class WorkflowContext:
    workflow_id: str
    step_results: dict = field(default_factory=dict)
    total_cost: float = 0.0
    total_tokens: int = 0
    trace_id: str = ""

class LLMOrchestrator:
    def __init__(self, providers: dict, tracer, cost_tracker):
        self.providers = providers
        self.tracer = tracer
        self.cost_tracker = cost_tracker
        self.circuit_breakers = {}

    async def execute_workflow(self, steps: list[StepConfig], 
                               input_data: dict) -> WorkflowContext:
        ctx = WorkflowContext(workflow_id=generate_id(), trace_id=self.tracer.new_trace())
        
        for step in steps:
            with self.tracer.span(step.name, trace_id=ctx.trace_id):
                try:
                    result = await self._execute_step(step, input_data, ctx)
                    ctx.step_results[step.name] = result
                    input_data = {**input_data, **result}  # chain outputs
                except WorkflowBudgetExceeded:
                    self.tracer.log_event("budget_exceeded", ctx)
                    break
                except StepFailedAfterRetries as e:
                    if step.fallback_model:
                        result = await self._execute_with_fallback(step, input_data, ctx)
                        ctx.step_results[step.name] = result
                    else:
                        raise
        return ctx

    async def _execute_step(self, step: StepConfig, input_data: dict, 
                            ctx: WorkflowContext) -> dict:
        # Check circuit breaker
        cb = self.circuit_breakers.get(step.provider)
        if cb and cb.is_open():
            raise CircuitBreakerOpen(step.provider)

        # Check cost budget
        if ctx.total_cost >= step.max_cost_usd:
            raise WorkflowBudgetExceeded(ctx.total_cost)

        # Retry with exponential backoff
        for attempt in range(step.max_retries + 1):
            try:
                provider = self.providers[step.provider]
                result = await asyncio.wait_for(
                    provider.complete(model=step.model, **input_data),
                    timeout=step.timeout_seconds
                )
                # Track costs
                cost = self.cost_tracker.calculate(step.model, result.usage)
                ctx.total_cost += cost
                ctx.total_tokens += result.usage.total_tokens
                
                return {"output": result.content, "usage": result.usage}
                
            except (RateLimitError, TimeoutError) as e:
                if attempt < step.max_retries:
                    wait = min(2 ** attempt + random.uniform(0, 1), 30)
                    await asyncio.sleep(wait)
                else:
                    self.circuit_breakers.setdefault(
                        step.provider, CircuitBreaker()
                    ).record_failure()
                    raise StepFailedAfterRetries(step.name, attempt)

    async def execute_streaming(self, step: StepConfig, 
                                 input_data: dict) -> AsyncIterator[str]:
        """Stream tokens with backpressure support."""
        provider = self.providers[step.provider]
        buffer = asyncio.Queue(maxsize=100)  # backpressure at 100 chunks
        
        async def producer():
            async for chunk in provider.stream(model=step.model, **input_data):
                await buffer.put(chunk)
            await buffer.put(None)  # sentinel
        
        task = asyncio.create_task(producer())
        while True:
            chunk = await buffer.get()
            if chunk is None:
                break
            yield chunk
        await task
```

### Cost Management

| Model | Input $/1M tokens | Output $/1M tokens | Budget Strategy |
|-------|-------------------|--------------------|-----------------| 
| GPT-4o | $2.50 | $10.00 | Use for complex reasoning only |
| Claude Sonnet | $3.00 | $15.00 | Primary for long context |
| GPT-4o-mini | $0.15 | $0.60 | Default for simple tasks |
| Llama 3 (self-hosted) | ~$0.10 | ~$0.10 | High-volume classification |

### Production Considerations
- **Idempotency**: Each step gets a deterministic ID; cache results for replay
- **Dead letter queue**: Failed workflows go to DLQ for manual review
- **Observability**: OpenTelemetry traces span entire workflow; each LLM call is a child span
- **Graceful degradation**: If premium model is down, auto-route to fallback
- **Token budgeting**: Pre-estimate token usage; abort before exceeding per-request limits

---

## Q107: Design a router that dynamically selects the best LLM for each request

### Problem
Route requests to optimal LLM based on query type, cost, latency, and quality requirements.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LLM Router                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐     ┌──────────────────────┐              │
│  │  Request  │────▶│  Query Classifier    │              │
│  │           │     │  (complexity, domain, │              │
│  └──────────┘     │   intent)            │              │
│                    └──────────────────────┘              │
│                              │                           │
│                              ▼                           │
│                    ┌──────────────────────┐              │
│                    │  Routing Policy      │              │
│                    │  Engine              │              │
│                    └──────────────────────┘              │
│                     │    │    │    │                     │
│                     ▼    ▼    ▼    ▼                     │
│              ┌─────┐ ┌─────┐ ┌─────┐ ┌───────┐         │
│              │GPT-4│ │Claude│ │Llama│ │Mistral│         │
│              └─────┘ └─────┘ └─────┘ └───────┘         │
│                     │    │    │    │                     │
│                     ▼    ▼    ▼    ▼                     │
│              ┌──────────────────────────────┐           │
│              │  Quality Monitor & Feedback   │           │
│              └──────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class RoutingConstraints:
    max_latency_ms: float = 5000
    max_cost_per_request: float = 0.10
    min_quality_score: float = 0.8
    required_capabilities: list = None  # e.g., ["function_calling", "vision"]

@dataclass
class ModelProfile:
    name: str
    provider: str
    latency_p50_ms: float
    latency_p99_ms: float
    cost_per_1k_input: float
    cost_per_1k_output: float
    quality_scores: dict  # domain -> score
    capabilities: set
    current_load: float  # 0-1
    error_rate_1h: float

class LLMRouter:
    def __init__(self, models: list[ModelProfile]):
        self.models = {m.name: m for m in models}
        self.classifier = self._load_query_classifier()
        self.routing_history = []  # for learning

    async def route(self, query: str, constraints: RoutingConstraints) -> str:
        """Select best model for the given query and constraints."""
        
        # Step 1: Classify query
        classification = self.classifier.predict(query)
        # Returns: {domain: "code", complexity: 0.8, estimated_tokens: 500}

        # Step 2: Filter eligible models
        eligible = self._filter_models(classification, constraints)
        if not eligible:
            # Relax constraints and retry
            eligible = self._filter_models(classification, self._relax(constraints))

        # Step 3: Score and rank
        scored = []
        for model in eligible:
            score = self._score_model(model, classification, constraints)
            scored.append((model.name, score))
        
        scored.sort(key=lambda x: -x[1])
        return scored[0][0]

    def _filter_models(self, classification: dict, 
                       constraints: RoutingConstraints) -> list[ModelProfile]:
        eligible = []
        for model in self.models.values():
            # Hard constraints
            if model.latency_p99_ms > constraints.max_latency_ms:
                continue
            estimated_cost = self._estimate_cost(model, classification["estimated_tokens"])
            if estimated_cost > constraints.max_cost_per_request:
                continue
            if constraints.required_capabilities:
                if not set(constraints.required_capabilities).issubset(model.capabilities):
                    continue
            if model.error_rate_1h > 0.05:  # >5% error rate = unhealthy
                continue
            eligible.append(model)
        return eligible

    def _score_model(self, model: ModelProfile, classification: dict,
                     constraints: RoutingConstraints) -> float:
        """Multi-objective scoring."""
        domain = classification["domain"]
        quality = model.quality_scores.get(domain, 0.7)
        cost = self._estimate_cost(model, classification["estimated_tokens"])
        latency_norm = 1 - (model.latency_p50_ms / constraints.max_latency_ms)
        cost_norm = 1 - (cost / constraints.max_cost_per_request)
        load_penalty = max(0, model.current_load - 0.8) * 2  # penalize >80% load

        # Weighted combination (tunable per use case)
        weights = {"quality": 0.5, "cost": 0.25, "latency": 0.2, "reliability": 0.05}
        
        return (
            weights["quality"] * quality +
            weights["cost"] * cost_norm +
            weights["latency"] * latency_norm +
            weights["reliability"] * (1 - model.error_rate_1h) -
            load_penalty
        )

    def update_profiles(self, model_name: str, latency: float, 
                        quality: float, success: bool):
        """Online learning: update model profiles from production data."""
        model = self.models[model_name]
        # Exponential moving average
        alpha = 0.05
        model.latency_p50_ms = (1 - alpha) * model.latency_p50_ms + alpha * latency
        if not success:
            model.error_rate_1h = min(1.0, model.error_rate_1h + 0.01)
```

### Routing Decision Matrix

| Query Type | Preferred Model | Fallback | Rationale |
|-----------|----------------|----------|-----------|
| Complex reasoning | GPT-4o / Claude Opus | Claude Sonnet | Highest accuracy |
| Code generation | Claude Sonnet | GPT-4o | Best at code |
| Simple Q&A | GPT-4o-mini | Llama 3 70B | Cost efficiency |
| Long context (>50K) | Claude / Gemini | Chunked GPT-4o | Context window |
| Structured output | GPT-4o (JSON mode) | Mistral | Reliability |
| Low latency (<1s) | Llama 3 (local) | GPT-4o-mini | No network hop |

### Production Considerations
- **Shadow routing**: Route 5% of traffic to alternative model; compare quality offline
- **Sticky sessions**: Same user/conversation stays on same model for consistency
- **Gradual migration**: When adding new model, ramp traffic 1%→10%→50%→100%
- **Cost alerts**: Per-team/per-app budget with automatic downgrade at 80% threshold
- **Latency hedging**: For critical requests, fire to 2 models; use first response

---

## Q108: Design a parallel LLM execution framework with consensus

### Problem
Run multiple LLM calls simultaneously and synthesize results using consensus mechanisms.

### Architecture

```
┌──────────────────────────────────────────────────────┐
│           Parallel LLM Execution Framework            │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────┐                                        │
│  │  Query   │                                        │
│  └────┬─────┘                                        │
│       │                                              │
│       ▼                                              │
│  ┌─────────────────────────────────┐                 │
│  │    Parallel Dispatcher           │                 │
│  └─────────────────────────────────┘                 │
│    │         │         │         │                    │
│    ▼         ▼         ▼         ▼                   │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐                │
│  │LLM A│  │LLM B│  │LLM C│  │LLM A│ (diff temp)   │
│  └──┬──┘  └──┬──┘  └──┬──┘  └──┬──┘                │
│     │        │        │        │                     │
│     ▼        ▼        ▼        ▼                     │
│  ┌─────────────────────────────────────────┐         │
│  │        Consensus Engine                  │         │
│  │  [Majority Vote | Judge | Weighted Avg]  │         │
│  └─────────────────────────────────────────┘         │
│                    │                                  │
│                    ▼                                  │
│  ┌─────────────────────────────────────────┐         │
│  │     Disagreement Resolution              │         │
│  │  (escalate | re-query | human review)    │         │
│  └─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

class ConsensusStrategy(Enum):
    MAJORITY_VOTE = "majority_vote"
    LLM_JUDGE = "llm_judge"
    WEIGHTED_AVERAGE = "weighted_average"
    BEST_OF_N = "best_of_n"

@dataclass
class ParallelResult:
    outputs: List[str]
    consensus_output: str
    agreement_score: float  # 0-1
    strategy_used: ConsensusStrategy
    latency_ms: float
    total_cost: float

class ParallelLLMExecutor:
    def __init__(self, providers: dict, judge_model: str = "gpt-4o"):
        self.providers = providers
        self.judge_model = judge_model

    async def execute(self, prompt: str, models: List[str],
                      strategy: ConsensusStrategy = ConsensusStrategy.LLM_JUDGE,
                      timeout: float = 30.0) -> ParallelResult:
        """Execute prompt across multiple models in parallel."""
        
        start = time.time()
        
        # Launch all calls concurrently
        tasks = [
            asyncio.create_task(self._call_model(model, prompt))
            for model in models
        ]
        
        # Wait with timeout; collect what we can
        done, pending = await asyncio.wait(tasks, timeout=timeout,
                                           return_when=asyncio.ALL_COMPLETED)
        
        for task in pending:
            task.cancel()
        
        outputs = [t.result() for t in done if not t.exception()]
        
        if len(outputs) < 2:
            # Fallback: not enough results for consensus
            return ParallelResult(
                outputs=outputs,
                consensus_output=outputs[0] if outputs else "",
                agreement_score=1.0,
                strategy_used=strategy,
                latency_ms=(time.time() - start) * 1000,
                total_cost=sum(o.get("cost", 0) for o in outputs)
            )

        # Apply consensus strategy
        consensus, agreement = await self._resolve_consensus(
            [o["text"] for o in outputs], prompt, strategy
        )

        return ParallelResult(
            outputs=[o["text"] for o in outputs],
            consensus_output=consensus,
            agreement_score=agreement,
            strategy_used=strategy,
            latency_ms=(time.time() - start) * 1000,
            total_cost=sum(o["cost"] for o in outputs)
        )

    async def _resolve_consensus(self, outputs: List[str], original_prompt: str,
                                  strategy: ConsensusStrategy) -> tuple[str, float]:
        if strategy == ConsensusStrategy.MAJORITY_VOTE:
            return self._majority_vote(outputs)
        
        elif strategy == ConsensusStrategy.LLM_JUDGE:
            judge_prompt = f"""You are a judge evaluating multiple AI responses.
Original question: {original_prompt}

Responses:
{chr(10).join(f'Response {i+1}: {o[:500]}' for i, o in enumerate(outputs))}

Select the best response (number) and explain why. If responses agree, note the agreement level (0-1).
Output JSON: {{"best": <number>, "agreement": <float>, "reasoning": "<str>"}}"""
            
            result = await self.providers[self.judge_model].complete(judge_prompt)
            parsed = json.loads(result)
            return outputs[parsed["best"] - 1], parsed["agreement"]
        
        elif strategy == ConsensusStrategy.BEST_OF_N:
            # Score each output and return highest
            scores = await asyncio.gather(*[
                self._score_output(o, original_prompt) for o in outputs
            ])
            best_idx = max(range(len(scores)), key=lambda i: scores[i])
            agreement = 1.0 - (max(scores) - min(scores))
            return outputs[best_idx], agreement

    def _majority_vote(self, outputs: List[str]) -> tuple[str, float]:
        """For structured outputs: exact match voting."""
        from collections import Counter
        # Normalize outputs for comparison
        normalized = [o.strip().lower() for o in outputs]
        counts = Counter(normalized)
        most_common, count = counts.most_common(1)[0]
        agreement = count / len(outputs)
        # Return original (non-normalized) version
        idx = normalized.index(most_common)
        return outputs[idx], agreement
```

### When to Use Each Strategy

| Strategy | Use Case | Cost | Reliability |
|----------|----------|------|-------------|
| Majority vote | Classification, yes/no | Low (no judge) | High for discrete |
| LLM judge | Open-ended generation | Medium (+1 call) | High |
| Weighted average | Scoring/ranking | Low | Medium |
| Best-of-N | Creative tasks | Medium | High |

### Production Considerations
- **Cost**: 3x parallel = 3x cost; use only for high-stakes decisions
- **Latency**: Wall-clock = max(individual latencies), not sum
- **Disagreement escalation**: If agreement < 0.5, flag for human review
- **Caching**: Cache consensus results; invalidate if any model is updated
- **Metrics**: Track agreement rate over time; dropping agreement signals model drift

---

## Q109: Design a long-running AI agent architecture

### Problem
Build architecture for agents executing multi-hour tasks with checkpointing, recovery, approvals, and resource management.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│               Long-Running Agent Architecture                    │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                  Agent Supervisor                       │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────┐   │    │
│  │  │ Scheduler│  │ Checkpoint   │  │ Resource       │   │    │
│  │  │          │  │ Manager      │  │ Governor       │   │    │
│  │  └──────────┘  └──────────────┘  └────────────────┘   │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                      │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Agent Execution Engine                      │    │
│  │                                                         │    │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐            │    │
│  │  │ Step 1  │───▶│ Step 2  │───▶│ Step 3  │──▶ ...     │    │
│  │  │(complete)│    │(running)│    │(pending)│            │    │
│  │  └─────────┘    └─────────┘    └─────────┘            │    │
│  │       │               │              │                  │    │
│  │       ▼               ▼              ▼                  │    │
│  │  [checkpoint]   [checkpoint]    [approval gate]         │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                      │
│  ┌───────────────┐  ┌───┴───────────┐  ┌──────────────────┐   │
│  │ Human-in-Loop │  │ State Store   │  │ Dead Letter      │   │
│  │ Approval UI   │  │ (durable)     │  │ Queue            │   │
│  └───────────────┘  └───────────────┘  └──────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import asyncio
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

class AgentState(Enum):
    RUNNING = "running"
    PAUSED = "paused"  
    WAITING_APPROVAL = "waiting_approval"
    CHECKPOINTED = "checkpointed"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Checkpoint:
    step_index: int
    state: dict
    timestamp: float
    token_usage: int
    cost_usd: float

@dataclass
class AgentTask:
    id: str
    goal: str
    plan: list  # steps to execute
    state: AgentState = AgentState.RUNNING
    checkpoints: list = field(default_factory=list)
    current_step: int = 0
    budget: dict = field(default_factory=lambda: {
        "max_cost_usd": 5.0, "max_tokens": 500000, "max_duration_hours": 4
    })

class LongRunningAgent:
    def __init__(self, llm, tools, state_store, approval_service):
        self.llm = llm
        self.tools = tools
        self.state_store = state_store
        self.approval_service = approval_service

    async def execute(self, task: AgentTask):
        """Execute task with checkpointing and recovery."""
        # Resume from last checkpoint if exists
        if task.checkpoints:
            last = task.checkpoints[-1]
            task.current_step = last.step_index + 1
            self._restore_state(last.state)

        while task.current_step < len(task.plan):
            step = task.plan[task.current_step]
            
            # Budget check
            if self._budget_exceeded(task):
                task.state = AgentState.PAUSED
                await self._notify("Budget exceeded", task)
                return

            # Approval gate check
            if step.get("requires_approval"):
                task.state = AgentState.WAITING_APPROVAL
                await self.state_store.save(task)
                approved = await self.approval_service.request(
                    task_id=task.id,
                    step=step,
                    context=self._get_context(task),
                    timeout_hours=24
                )
                if not approved:
                    task.state = AgentState.PAUSED
                    return

            # Execute step with timeout
            try:
                task.state = AgentState.RUNNING
                result = await asyncio.wait_for(
                    self._execute_step(step, task),
                    timeout=step.get("timeout_seconds", 300)
                )
                
                # Checkpoint after each successful step
                checkpoint = Checkpoint(
                    step_index=task.current_step,
                    state=self._capture_state(),
                    timestamp=time.time(),
                    token_usage=self._total_tokens(task),
                    cost_usd=self._total_cost(task)
                )
                task.checkpoints.append(checkpoint)
                await self.state_store.save(task)
                
                task.current_step += 1
                
            except asyncio.TimeoutError:
                await self._handle_timeout(task, step)
            except Exception as e:
                await self._handle_failure(task, step, e)
                return

        task.state = AgentState.COMPLETED
        await self.state_store.save(task)

    async def _execute_step(self, step: dict, task: AgentTask) -> Any:
        """Execute a single step, potentially involving multiple LLM calls."""
        messages = self._build_messages(step, task)
        
        while True:  # Agent loop for this step
            response = await self.llm.complete(messages)
            
            if response.tool_calls:
                results = await self._execute_tools(response.tool_calls)
                messages.extend(results)
            else:
                return response.content

    async def _execute_tools(self, tool_calls: list) -> list:
        """Execute tools with safety checks."""
        results = []
        for call in tool_calls:
            tool = self.tools.get(call.name)
            if not tool:
                results.append({"error": f"Unknown tool: {call.name}"})
                continue
            # Safety: check if tool is allowed at this stage
            if tool.requires_confirmation:
                # Don't block; queue for batch approval
                pass
            result = await tool.execute(**call.arguments)
            results.append(result)
        return results

    def _budget_exceeded(self, task: AgentTask) -> bool:
        budget = task.budget
        if self._total_cost(task) >= budget["max_cost_usd"]:
            return True
        if self._total_tokens(task) >= budget["max_tokens"]:
            return True
        elapsed_hours = (time.time() - task.checkpoints[0].timestamp) / 3600 if task.checkpoints else 0
        return elapsed_hours >= budget["max_duration_hours"]
```

### Resource Governance

| Resource | Limit | Action on Exceed |
|----------|-------|-----------------|
| Cost | $5/task default | Pause + notify |
| Tokens | 500K total | Pause + summarize context |
| Duration | 4 hours | Checkpoint + pause |
| Tool calls | 100/step | Force step completion |
| Retries | 3/step | Mark step failed |

### Production Considerations
- **Durable state**: Store checkpoints in PostgreSQL/DynamoDB; survive process restarts
- **Heartbeat**: Agent sends heartbeat every 30s; supervisor restarts if missed
- **Context window management**: Summarize completed steps to avoid context overflow
- **Observability**: Stream step status to UI; users see real-time progress
- **Cancellation**: User can cancel at any checkpoint; cleanup hooks run

---

## Q110: Design a function calling / tool use architecture

### Problem
Allow LLMs to safely invoke external APIs with authentication, rate limiting, validation, and rollback.

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│             Function Calling Architecture                    │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────────────────────────────────┐  │
│  │   LLM    │───▶│       Tool Gateway                    │  │
│  │ (tool    │    │  ┌──────────────────────────────────┐ │  │
│  │  calls)  │    │  │  Schema Validator                 │ │  │
│  └──────────┘    │  │  (JSON Schema enforcement)        │ │  │
│                  │  └──────────────────────────────────┘ │  │
│                  │  ┌──────────────────────────────────┐ │  │
│                  │  │  Permission Engine                 │ │  │
│                  │  │  (RBAC + scope-based)              │ │  │
│                  │  └──────────────────────────────────┘ │  │
│                  │  ┌──────────────────────────────────┐ │  │
│                  │  │  Rate Limiter                      │ │  │
│                  │  │  (per-user, per-tool, global)      │ │  │
│                  │  └──────────────────────────────────┘ │  │
│                  │  ┌──────────────────────────────────┐ │  │
│                  │  │  Execution Sandbox                 │ │  │
│                  │  │  (timeout, resource limits)        │ │  │
│                  │  └──────────────────────────────────┘ │  │
│                  └──────────────────────────────────────┘ │  │
│                              │                            │  │
│                              ▼                            │  │
│  ┌──────────────────────────────────────────────────────┐│  │
│  │              External APIs / Services                  ││  │
│  │  [Stripe] [GitHub] [Jira] [DB] [Email] [Slack]       ││  │
│  └──────────────────────────────────────────────────────┘│  │
│                              │                            │  │
│                              ▼                            │  │
│  ┌──────────────────────────────────────────────────────┐│  │
│  │         Audit Log + Rollback Registry                 ││  │
│  └──────────────────────────────────────────────────────┘│  │
└────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from typing import Any, Callable, Optional
from dataclasses import dataclass
from jsonschema import validate, ValidationError
import time

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict  # JSON Schema
    handler: Callable
    permissions: list  # required scopes
    rate_limit: dict  # {"calls": 10, "period_seconds": 60}
    is_destructive: bool  # requires confirmation for write operations
    rollback_handler: Optional[Callable] = None
    timeout_seconds: float = 10.0

class ToolGateway:
    def __init__(self, tools: list[ToolDefinition], auth_service, audit_log):
        self.tools = {t.name: t for t in tools}
        self.auth_service = auth_service
        self.audit_log = audit_log
        self.rate_counters = {}  # tool_name:user_id -> (count, window_start)
        self.execution_history = []  # for rollback

    async def execute_tool_call(self, tool_name: str, arguments: dict,
                                 user_context: dict) -> dict:
        """Execute a tool call with full safety pipeline."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}", "status": "rejected"}

        # 1. Validate arguments against schema
        try:
            validate(instance=arguments, schema=tool.parameters_schema)
        except ValidationError as e:
            return {"error": f"Invalid arguments: {e.message}", "status": "rejected"}

        # 2. Check permissions
        if not self.auth_service.has_scopes(user_context, tool.permissions):
            await self.audit_log.log("permission_denied", tool_name, user_context)
            return {"error": "Insufficient permissions", "status": "denied"}

        # 3. Rate limiting
        if self._is_rate_limited(tool_name, user_context["user_id"], tool.rate_limit):
            return {"error": "Rate limit exceeded", "status": "rate_limited"}

        # 4. Destructive action confirmation (if applicable)
        if tool.is_destructive:
            # In async flow, this was pre-approved; log the approval
            await self.audit_log.log("destructive_action_executing", tool_name, arguments)

        # 5. Execute with timeout and resource limits
        try:
            import asyncio
            result = await asyncio.wait_for(
                tool.handler(**arguments, _context=user_context),
                timeout=tool.timeout_seconds
            )
            
            # 6. Record for potential rollback
            self.execution_history.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
                "timestamp": time.time(),
                "user": user_context["user_id"],
                "rollback_handler": tool.rollback_handler
            })
            
            await self.audit_log.log("tool_executed", tool_name, {
                "arguments": arguments, "result_summary": str(result)[:200]
            })
            
            return {"result": result, "status": "success"}

        except asyncio.TimeoutError:
            return {"error": f"Tool timed out after {tool.timeout_seconds}s", "status": "timeout"}
        except Exception as e:
            await self.audit_log.log("tool_error", tool_name, {"error": str(e)})
            return {"error": str(e), "status": "error"}

    async def rollback(self, n_steps: int = 1) -> list:
        """Rollback last N tool executions."""
        rolled_back = []
        for _ in range(min(n_steps, len(self.execution_history))):
            entry = self.execution_history.pop()
            if entry["rollback_handler"]:
                try:
                    await entry["rollback_handler"](entry["arguments"], entry["result"])
                    rolled_back.append({"tool": entry["tool"], "status": "rolled_back"})
                except Exception as e:
                    rolled_back.append({"tool": entry["tool"], "status": "rollback_failed", "error": str(e)})
            else:
                rolled_back.append({"tool": entry["tool"], "status": "no_rollback_available"})
        return rolled_back

    def _is_rate_limited(self, tool_name: str, user_id: str, limit: dict) -> bool:
        key = f"{tool_name}:{user_id}"
        now = time.time()
        count, window_start = self.rate_counters.get(key, (0, now))
        
        if now - window_start > limit["period_seconds"]:
            self.rate_counters[key] = (1, now)
            return False
        
        if count >= limit["calls"]:
            return True
        
        self.rate_counters[key] = (count + 1, window_start)
        return False

# Example tool registration
create_jira_ticket = ToolDefinition(
    name="create_jira_ticket",
    description="Create a Jira ticket in the specified project",
    parameters_schema={
        "type": "object",
        "properties": {
            "project": {"type": "string", "pattern": "^[A-Z]{2,10}$"},
            "summary": {"type": "string", "maxLength": 200},
            "description": {"type": "string", "maxLength": 5000},
            "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]}
        },
        "required": ["project", "summary"]
    },
    handler=jira_create_handler,
    permissions=["jira:write"],
    rate_limit={"calls": 10, "period_seconds": 60},
    is_destructive=True,
    rollback_handler=jira_delete_handler
)
```

### Safety Matrix

| Tool Category | Auth | Rate Limit | Confirmation | Rollback |
|---------------|------|-----------|--------------|----------|
| Read-only (search, get) | Token | 100/min | No | N/A |
| Create (post, create) | Token + scope | 20/min | Optional | Delete |
| Update (patch, put) | Token + scope | 10/min | Yes | Restore previous |
| Delete (delete, revoke) | Token + scope + MFA | 5/min | Always | Undelete/recreate |
| Financial (charge, refund) | Token + scope + approval | 3/min | Always + human | Reverse transaction |

### Production Considerations
- **Schema evolution**: Version tool schemas; reject calls with outdated schemas
- **Dry-run mode**: Execute tool in simulation mode first; show user what would happen
- **Audit compliance**: Immutable audit log with who/what/when for SOC2
- **Circuit breaker**: If external API errors > 50%, disable tool temporarily
- **Cost tracking**: Some tools have per-call costs (APIs); track and budget
