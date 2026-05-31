# LLMOps and AgentOps

## LLMOps: Operations for LLM-Based Systems

LLMOps is **DevOps for AI applications**. Just as DevOps brought discipline to software deployment (CI/CD, monitoring, rollbacks), LLMOps brings the same discipline to LLM-powered applications.

The key difference from traditional MLOps: in LLMOps, you're not training models — you're managing **prompts, configurations, and orchestration** around pre-trained models. Your "code" is a combination of prompts, tool definitions, and routing logic.

```
Traditional Software:  Code → Build → Test → Deploy → Monitor
MLOps:                 Data → Train → Evaluate → Deploy → Monitor
LLMOps:               Prompts → Evaluate → Deploy → Monitor → Improve
AgentOps:             Agent Design → Test → Deploy → Monitor → Improve
```

## LLMOps Lifecycle

```mermaid
graph LR
    A[1. Develop] --> B[2. Evaluate]
    B --> C[3. Deploy]
    C --> D[4. Monitor]
    D --> E[5. Improve]
    E --> A
    
    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#e8f5e9
    style D fill:#fff3e0
    style E fill:#fce4ec
```

### 1. Develop (Prompts, Tools, Pipelines)
- Write and iterate on prompts locally
- Define tool schemas and integrations
- Build orchestration pipelines (chains, graphs)
- Use playground environments for rapid iteration
- Version control everything (prompts are code)

### 2. Evaluate (Test Against Golden Sets)
- Run prompts against evaluation datasets
- Measure: accuracy, relevance, faithfulness, toxicity
- Compare against baseline (previous version)
- Automated evaluation with judge LLMs
- Human evaluation for subjective quality

### 3. Deploy (Version, Canary, Rollout)
- Deploy new prompt version to registry
- Canary: route 5% of traffic to new version
- Monitor quality metrics during canary
- If quality holds, gradually increase to 100%
- If quality drops, instant rollback

### 4. Monitor (Quality, Cost, Latency)
- Track per-request quality scores
- Monitor cost trends and anomalies
- Alert on latency spikes
- Detect quality drift over time
- Dashboard for real-time visibility

### 5. Improve (Feedback, Tuning, Iteration)
- Collect user feedback (thumbs up/down)
- Identify failure patterns
- Fine-tune prompts based on failures
- Add few-shot examples for common errors
- Update evaluation sets with new edge cases

## AgentOps: Operations for Agent-Based Systems

AgentOps extends LLMOps for **autonomous agents**. Agents are harder to operate because they make decisions, use tools, and have multi-step workflows. A single prompt change can cascade into completely different behavior.

Think of the difference like this:
- **LLMOps** = managing a call center script (predictable flow)
- **AgentOps** = managing a field agent (autonomous decisions, unpredictable paths)

## AgentOps Lifecycle

```mermaid
graph LR
    A[1. Design] --> B[2. Evaluate]
    B --> C[3. Deploy]
    C --> D[4. Monitor]
    D --> E[5. Improve]
    E --> A
    
    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#e8f5e9
    style D fill:#fff3e0
    style E fill:#fce4ec
```

### 1. Design (Agent Architecture, Tools, Guardrails)
- Define agent's purpose and boundaries
- Select tools the agent can access
- Set guardrails (what it cannot do)
- Design escalation paths (when to involve humans)
- Define success criteria

### 2. Evaluate (Trajectory Testing, Safety Testing)
- **Trajectory testing:** Does the agent take correct steps?
- **Safety testing:** Can it be jailbroken? Does it stay in bounds?
- **Tool usage testing:** Does it call the right tools with right params?
- **Multi-turn testing:** Does it maintain coherence over long conversations?
- **Adversarial testing:** What happens with malicious inputs?

### 3. Deploy (Staged Rollout, Feature Flags)
- Deploy with feature flags (enable for internal users first)
- Staged rollout: internal → beta → 10% → 50% → 100%
- Shadow mode: agent runs but humans approve actions
- Parallel mode: agent + human both handle, compare results

### 4. Monitor (Agent Behavior, Tool Usage, Failures)
- Track tool call patterns (is it using tools correctly?)
- Monitor loop detection (is it stuck in a cycle?)
- Alert on unusual behavior (10x normal tool calls)
- Track success/failure rates per task type
- Cost per agent run (agents can be expensive)

### 5. Improve (Tune Prompts, Add Tools, Adjust Guardrails)
- Analyze failure trajectories
- Add new tools for gaps in capability
- Tighten guardrails where agent misbehaves
- Add few-shot examples for tricky scenarios
- Update system prompts based on patterns

## Key Operational Requirements

### Version Control for Prompts (Git for Prompts)

Prompts are code. They need the same rigor:

```yaml
# prompt-v3.yaml
id: customer-support-agent
version: 3
author: jane@company.com
created: 2024-03-15
description: "Added tone guidelines after negative feedback"
template: |
  You are a helpful customer support agent for {{company_name}}.
  Always be empathetic and solution-oriented.
  Never blame the customer.
  ...
changelog:
  - v3: Added empathy guidelines
  - v2: Added refund policy context
  - v1: Initial version
```

### Rollback Capability
When a new prompt version causes quality issues:
```
[Alert: Quality score dropped 15% after deploying prompt v3]
[Action: Rollback to v2]
[Result: Quality restored in < 60 seconds]
```

### Canary Deployments
```
Time 0:   100% → v2 (current)
Time 1:   95% → v2, 5% → v3 (canary)
Time 2:   Monitor quality metrics...
Time 3:   If good: 80% → v2, 20% → v3
Time 4:   If good: 50% → v2, 50% → v3
Time 5:   If good: 0% → v2, 100% → v3
           If bad at any step: 100% → v2 (instant rollback)
```

### A/B Testing
Compare two models or prompts head-to-head:
```
Experiment: "claude-vs-gpt4-for-summarization"
Control:    GPT-4o (current)
Variant:    Claude 3.5 Sonnet
Split:      50/50
Metrics:    quality_score, latency_p95, cost_per_request
Duration:   7 days
Result:     Claude 3.5 wins on quality (+5%), loses on cost (+10%)
Decision:   Switch to Claude for premium tier, keep GPT-4o for standard
```

### Feature Flags
Enable/disable agent capabilities without code deployment:
```json
{
  "agent_features": {
    "can_issue_refunds": true,
    "can_access_billing": true,
    "can_escalate_to_human": true,
    "can_send_emails": false,
    "max_tool_calls_per_turn": 5,
    "allowed_models": ["gpt-4o", "gpt-4o-mini"]
  }
}
```

### Audit Trails
Every change is logged:
```
2024-03-15 10:30 | jane@co.com | Updated prompt "customer-support" v2→v3
2024-03-15 10:35 | system      | Canary started: 5% traffic to v3
2024-03-15 11:00 | system      | Quality alert: v3 score 0.72 (threshold: 0.80)
2024-03-15 11:01 | system      | Auto-rollback to v2
2024-03-15 11:05 | jane@co.com | Investigating rollback cause
```

## LLMOps vs AgentOps Comparison

| Dimension | LLMOps | AgentOps |
|-----------|--------|----------|
| **Unit of work** | Single LLM call | Multi-step agent trajectory |
| **Testing** | Input/output pairs | Trajectory correctness |
| **Failure modes** | Wrong answer | Stuck in loop, wrong tool, unsafe action |
| **Cost predictability** | Predictable (fixed prompt) | Variable (agent decides how many steps) |
| **Rollback scope** | Prompt version | Agent config + tools + prompts |
| **Monitoring** | Quality per response | Behavior patterns over sessions |
| **Safety** | Output filtering | Action-level guardrails |

## Tooling Landscape

| Category | Tools |
|----------|-------|
| **Prompt Management** | PromptLayer, Humanloop, Langfuse |
| **Evaluation** | Braintrust, Ragas, DeepEval |
| **Observability** | Langfuse, LangSmith, Arize Phoenix |
| **Deployment** | LangServe, Modal, Replicate |
| **Agent Frameworks** | LangGraph, CrewAI, AutoGen |
| **Feature Flags** | LaunchDarkly, Statsig |

## Key Takeaways

1. **Prompts are code** — version, test, deploy, and rollback them like software
2. **Canary deployments** prevent catastrophic quality drops from reaching all users
3. **AgentOps is harder** than LLMOps because agents are non-deterministic and multi-step
4. **Observability is non-negotiable** — you can't improve what you can't measure
5. **The feedback loop** is what separates good AI systems from great ones
6. **Start with LLMOps basics** (versioning + eval + monitoring) before adding AgentOps complexity

---

## Staff+ Deep Dive: Anti-Patterns, Trade-offs, and the Emerging Discipline

### Anti-Patterns to Avoid

**1. No Version Control for Prompts**
Prompts stored in application code, scattered across services, with no history of what changed when. When quality degrades, nobody knows which prompt change caused it. Worse: prompts edited in production UIs with no audit trail.

Fix: Prompts in a dedicated repository (or prompt management system) with full version history, ownership metadata, and mandatory eval before merge.

**2. Deploying Prompt Changes Without Eval**
"It's just a text change, what could go wrong?" — famous last words. A single word change in a prompt can shift output distribution dramatically. Without running evals against a representative test set before deployment, you're shipping blind.

The minimum bar: 50+ test cases covering edge cases, run automatically on PR, with regression alerts if scores drop >5%.

**3. No Rollback for Agent Behavior Changes**
Agents combine prompts, tools, and orchestration logic. When behavior changes, which component caused it? Without the ability to instantly revert to a known-good configuration (all three components together), you're stuck debugging in production while users suffer.

Fix: Atomic versioning of agent configurations — prompt version + tool versions + orchestration logic as a single deployable unit with one-click rollback.

**4. Treating LLM Updates Like Library Updates**
When OpenAI ships a new GPT-4 version, teams treat it like bumping a library version: "update and ship." But LLM updates can change behavior in subtle, task-specific ways. A model update might improve general quality but degrade performance on your specific financial analysis task.

Fix: Pin model versions. Test new versions against your eval suite. Upgrade deliberately, not automatically.

### Critical Trade-offs

**GitOps for Prompts vs. UI-Based Management**

| Dimension | GitOps (prompts in repo) | UI-Based (Promptflow, Langsmith) |
|-----------|--------------------------|----------------------------------|
| Change velocity | Slow (PR → review → merge → deploy) | Fast (edit → save → live) |
| Audit trail | Full git history | Platform-dependent |
| Who can edit | Engineers only | PMs, domain experts too |
| Eval integration | Natural (CI/CD) | Requires platform support |
| Best for | Production-critical prompts | Experimentation, iteration |

Most mature orgs use both: UI for experimentation, GitOps for promotion to production.

**Per-Model Config vs. Unified Config**
- Per-model: each model gets its own prompt, parameters, eval suite. Maximum optimization per model, but N× maintenance burden.
- Unified: one prompt template works across models with minor parameter tweaks. Simpler, but sacrifices model-specific optimization.
- Reality: unified for 80% of use cases, per-model only for the highest-value features where marginal quality matters.

### AgentOps as a Distinct Discipline

AgentOps is NOT just "LLMOps for agents." It's fundamentally different:

**Why AgentOps is Harder**:
- Non-deterministic execution paths: same input → different tool call sequences
- Multi-step failures: step 3 of 7 fails, but the error manifests at step 6
- Resource consumption is unpredictable: an agent might make 2 or 200 API calls
- Evaluation is harder: you can't just check the final answer, you need to evaluate the reasoning path

**What AgentOps Adds Beyond LLMOps**:
- Trace visualization (full execution DAG, not just request/response)
- Cost budgets per agent execution (kill runaway agents)
- Tool call monitoring (which tools are called, in what order, with what success rate)
- Behavioral drift detection (agent strategies changing over time)
- Human-in-the-loop escalation (when agent confidence is low)

**The Maturity Model**:
1. Level 0: No ops — deploy and pray
2. Level 1: LLMOps basics — prompt versioning, basic eval, cost monitoring
3. Level 2: Advanced LLMOps — canary deploys, automated eval, regression detection
4. Level 3: AgentOps — execution tracing, behavioral monitoring, agent-level SLOs
5. Level 4: Autonomous ops — self-healing agents, auto-rollback, continuous optimization
