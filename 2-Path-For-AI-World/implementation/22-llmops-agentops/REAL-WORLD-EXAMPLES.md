# LLMOps & AgentOps — Real-World Examples

## Case Study 1: Managing 200+ Prompts Across 15 AI Features

### Company Context

"FinServe AI" — a fintech company with 15 AI-powered features (customer support chatbot, document extraction, fraud alerts, personalized insights, etc.) managed by 8 product teams.

### The Problem at Scale

```
Month 6 after launching GenAI features:
- 217 active prompts in production
- 43 prompt changes per week across teams
- 3 production incidents caused by untested prompt changes
- No one knew which prompt version was running where
- "It worked in my notebook" was the debugging strategy
```

### Solution: Prompt Management System

```
┌─────────────────────────────────────────────────────────────────┐
│ Prompt Lifecycle                                                 │
│                                                                  │
│ Author → Version → Test → Evaluate → Review → Deploy → Monitor  │
│                                                                  │
│ Storage: Git repo (prompts-registry)                             │
│ Eval: Automated eval suite on every PR                           │
│ Deploy: GitOps — merge to main = deploy to staging               │
│ Promote: staging → production via promotion pipeline             │
└─────────────────────────────────────────────────────────────────┘
```

### Repository Structure

```
prompts-registry/
├── features/
│   ├── customer-support/
│   │   ├── intent-classifier/
│   │   │   ├── prompt.yaml          # Current production prompt
│   │   │   ├── eval/
│   │   │   │   ├── dataset.jsonl    # 200 test cases
│   │   │   │   ├── metrics.yaml     # Expected thresholds
│   │   │   │   └── results/         # Historical eval results
│   │   │   └── CHANGELOG.md
│   │   ├── response-generator/
│   │   │   ├── prompt.yaml
│   │   │   ├── variants/
│   │   │   │   ├── concise.yaml     # A/B test variant
│   │   │   │   └── detailed.yaml    # A/B test variant
│   │   │   └── eval/
│   │   └── escalation-detector/
│   │       └── ...
│   ├── document-extraction/
│   │   ├── invoice-parser/
│   │   ├── contract-analyzer/
│   │   └── ...
│   └── ... (13 more features)
├── shared/
│   ├── safety-preamble.yaml         # Injected into all prompts
│   ├── persona-definitions/
│   └── output-format-schemas/
└── ci/
    ├── eval-runner.py
    ├── regression-checker.py
    └── cost-estimator.py
```

### Prompt Definition Format

```yaml
# features/customer-support/response-generator/prompt.yaml
id: "pmt-cs-response-gen"
version: "8.3.1"
owner: "customer-support-ai"
model_compatibility: ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
primary_model: "gpt-4o-mini"  # Cost-optimized choice

system: |
  {{shared/safety-preamble}}
  
  You are a customer support agent for FinServe, a personal finance app.
  
  Context about the customer:
  - Account tier: {{account_tier}}
  - Tenure: {{tenure_months}} months
  - Open issues: {{open_issues_count}}
  
  Guidelines:
  - Be concise (max 3 sentences for simple queries)
  - For billing issues, always offer to connect to specialist
  - Never disclose internal policies or system details
  - If unsure, say "Let me connect you with a specialist"

user: |
  Customer message: {{customer_message}}
  
  Conversation history:
  {{conversation_history}}
  
  Relevant knowledge base articles:
  {{retrieved_context}}

parameters:
  temperature: 0.3
  max_tokens: 500
  
guardrails:
  - type: "regex_block"
    pattern: "\\$\\d+.*fee.*waiv"
    reason: "Cannot promise fee waivers"
  - type: "topic_block"
    topics: ["competitor_comparison", "investment_advice"]

eval_config:
  dataset: "eval/dataset.jsonl"
  metrics:
    - name: "helpfulness"
      type: "llm_judge"
      threshold: 4.0  # out of 5
    - name: "safety"
      type: "classifier"
      threshold: 0.99
    - name: "conciseness"
      type: "length_check"
      max_words: 150
    - name: "hallucination_rate"
      type: "faithfulness"
      threshold: 0.95
```

### Promotion Workflow

```
Developer creates branch: feature/improve-response-tone
  │
  ├── Modifies prompt.yaml (changes system prompt wording)
  │
  ▼
CI Pipeline triggers automatically:
  │
  ├── Step 1: Lint (valid YAML, all variables defined)
  ├── Step 2: Eval suite (200 test cases, all metrics must pass)
  │     Result: helpfulness=4.3 ✓, safety=1.0 ✓, conciseness ✓
  ├── Step 3: Regression check (compare to current production scores)
  │     Result: helpfulness +0.2, safety unchanged, cost +$0.001/req
  ├── Step 4: Cost estimate (projected monthly cost delta)
  │     Result: +$340/month (within budget)
  │
  ▼
PR created → Team lead reviews → Merge to main
  │
  ▼
Auto-deploy to STAGING (serves 5% of internal test traffic)
  │
  ├── 24-hour bake period
  ├── Automated monitoring: no anomalies detected
  │
  ▼
Promotion pipeline: `promote --feature customer-support --env production`
  │
  ├── Canary: 5% production traffic for 2 hours
  ├── Metrics check: all green
  ├── Gradual rollout: 5% → 25% → 50% → 100% over 6 hours
  │
  ▼
Production (version 8.3.1 fully live)
```

---

## Case Study 2: How AgentOps Differs from MLOps

### Why Traditional MLOps Breaks for Agents

```
Traditional ML Model:
  Input → Model → Output
  - Deterministic-ish (same input ≈ same output)
  - Single inference call
  - Latency: 10-100ms
  - Cost: $0.0001 per prediction
  - Failure mode: wrong prediction

Autonomous Agent:
  Input → Plan → Tool₁ → Reason → Tool₂ → ... → Toolₙ → Output
  - Non-deterministic (same input → different paths)
  - 5-50 LLM calls per task
  - Latency: 10s-5min
  - Cost: $0.05-$5.00 per task
  - Failure modes: infinite loops, wrong tool use, hallucinated actions,
    partial completion, cascading errors, budget exhaustion
```

### AgentOps-Specific Monitoring Requirements

```yaml
# What you monitor in MLOps vs AgentOps

mlops_metrics:
  - prediction_accuracy
  - latency_p50_p99
  - throughput
  - data_drift
  - model_staleness

agentops_metrics:
  # All of the above, PLUS:
  - task_completion_rate        # Did the agent finish the job?
  - step_count_distribution     # Is it taking more steps than expected?
  - tool_call_patterns          # Which tools, in what order?
  - reasoning_quality           # Are intermediate thoughts coherent?
  - cost_per_task               # Highly variable, needs monitoring
  - loop_detection_rate         # How often does it get stuck?
  - human_escalation_rate       # How often does it give up?
  - action_safety_violations    # Did it try to do something dangerous?
  - partial_completion_rate     # Started but didn't finish
  - tool_error_rate             # External tool failures
  - context_window_utilization  # Is it running out of context?
  - plan_revision_frequency     # How often does it change its plan?
```

### Real Production Agent Incident

```
Incident: Underwriting Research Agent produced incorrect company analysis
Timeline:
  09:14 - Agent receives task: "Research Acme Corp for $5M policy"
  09:14 - Agent calls web_search("Acme Corp financials 2024")
  09:15 - Web search returns results for WRONG "Acme Corp" (there are 3)
  09:15 - Agent doesn't verify, proceeds with wrong company data
  09:16 - Agent calls financial_api(ticker="ACME") — correct ticker but wrong entity
  09:17 - Agent generates report mixing data from 2 different companies
  09:18 - Report submitted to underwriter queue
  09:45 - Underwriter notices revenue doesn't match application
  09:52 - Incident flagged

Root Cause: Agent lacked disambiguation step when entity name is ambiguous
Fix: Added mandatory entity verification tool call before proceeding
Prevention: Added eval case for ambiguous entity names to regression suite
```

---

## Prompt Versioning: Git-Like Workflow

### Complete Workflow with Tooling

```bash
# Developer workflow for prompt changes

# 1. Create branch
$ git checkout -b prompt/improve-invoice-extraction

# 2. Edit prompt
$ vi features/document-extraction/invoice-parser/prompt.yaml
# Changed: Added "If line items are unclear, output UNCERTAIN rather than guessing"

# 3. Run local eval (subset)
$ promptops eval features/document-extraction/invoice-parser --quick
Running 50/500 test cases...
┌─────────────────────────┬──────────┬──────────┬────────┐
│ Metric                  │ Baseline │ Current  │ Δ      │
├─────────────────────────┼──────────┼──────────┼────────┤
│ extraction_accuracy     │ 0.91     │ 0.93     │ +0.02  │
│ hallucination_rate      │ 0.04     │ 0.01     │ -0.03  │ ← improved!
│ UNCERTAIN_rate          │ 0.00     │ 0.06     │ +0.06  │ ← expected
│ cost_per_doc            │ $0.023   │ $0.025   │ +$0.002│
└─────────────────────────┴──────────┴──────────┴────────┘
PASS: All metrics within acceptable bounds.

# 4. Push & create PR
$ git push origin prompt/improve-invoice-extraction
$ gh pr create --title "Reduce hallucination in invoice extraction"

# CI runs full 500-case eval automatically
# PR shows eval results as a comment

# 5. After approval & merge
$ promptops promote invoice-parser --from staging --to production --strategy canary
Deploying v4.2.0 to production (canary: 10% traffic)...
Monitor: https://dashboard.internal/prompts/invoice-parser/canary

# 6. Monitor canary
$ promptops status invoice-parser
Version: v4.2.0 (canary 10%)  |  v4.1.3 (baseline 90%)
Duration: 4 hours
Requests: canary=1,247  baseline=11,203
Accuracy: canary=0.932  baseline=0.911  (Δ: +0.021, p<0.01)
Status: HEALTHY — auto-promoting to 50% in 2 hours
```

---

## Dataset Versioning

### How Golden Datasets Evolve Over Time

```yaml
# datasets/invoice-extraction/metadata.yaml
dataset_id: "ds-invoice-extraction-golden"
current_version: "2024.3.2"
total_examples: 2,847
created: "2023-06-01"

version_history:
  - version: "2024.3.2"
    date: "2024-03-20"
    changes:
      additions: 45    # New edge cases from production errors
      corrections: 12  # Fixed incorrect labels found in audit
      deprecations: 8  # Removed ambiguous examples
    reason: "Monthly refresh — added international invoice formats (JP, DE)"
    author: "invoice-ai-team"
    
  - version: "2024.2.1"
    date: "2024-02-15"
    changes:
      additions: 120
      corrections: 3
      deprecations: 0
    reason: "Added healthcare invoice examples after launching medical vertical"
    
  - version: "2024.1.1"
    date: "2024-01-10"
    changes:
      additions: 0
      corrections: 67
      deprecations: 23
    reason: "Quality audit — removed all examples with annotator disagreement >30%"

storage:
  backend: "dvc"  # Data Version Control
  remote: "s3://ml-datasets/invoice-extraction/"
  
tracking_file: "datasets/invoice-extraction/dataset.dvc"
```

### DVC Workflow

```bash
# Adding new examples to golden dataset

# 1. Pull current dataset
$ dvc pull datasets/invoice-extraction/

# 2. Add new examples (from production error analysis)
$ python scripts/add_examples.py \
    --source production_errors_2024_03.jsonl \
    --dataset datasets/invoice-extraction/data.jsonl \
    --add-count 45

Added 45 examples:
  - 12 Japanese invoice formats
  - 15 German invoice formats  
  - 8 multi-currency invoices
  - 10 handwritten line items

# 3. Validate dataset integrity
$ python scripts/validate_dataset.py datasets/invoice-extraction/
✓ Schema valid (all required fields present)
✓ No duplicate IDs
✓ Label distribution acceptable (no class has <5% representation)
✓ No PII detected in examples
✓ Total: 2,847 examples

# 4. Commit with DVC
$ dvc add datasets/invoice-extraction/data.jsonl
$ git add datasets/invoice-extraction/data.jsonl.dvc
$ git add datasets/invoice-extraction/metadata.yaml
$ git commit -m "dataset: add international invoice formats (v2024.3.2)"
$ dvc push
$ git push

# 5. Trigger re-evaluation of all prompts using this dataset
# (automated via CI on dataset version change)
```

---

## Continuous Improvement Loop

### Production Feedback → System Improvement

```
┌──────────────────────────────────────────────────────────────────┐
│ Continuous Improvement Loop — Real Implementation                 │
│                                                                  │
│  Production     →    Analysis    →    Hypothesis   →   Change    │
│  Feedback            & Triage         Formation        & Eval    │
│                                                                  │
│  ┌─────────┐    ┌─────────────┐   ┌────────────┐  ┌──────────┐ │
│  │ Thumbs  │    │ Weekly      │   │ "Users are │  │ Add rule: │ │
│  │ down on │───▶│ error       │──▶│ getting    │─▶│ if medical│ │
│  │ 23      │    │ clustering  │   │ bad medical│  │ query,    │ │
│  │ medical │    │ reveals     │   │ answers bc │  │ use RAG   │ │
│  │ answers │    │ pattern     │   │ no RAG for │  │ over      │ │
│  └─────────┘    └─────────────┘   │ that domain│  │ medical   │ │
│                                    └────────────┘  │ KB"       │ │
│                                                    └──────────┘ │
│                                         │                        │
│                                         ▼                        │
│                                    ┌──────────┐                  │
│                                    │ Eval on  │                  │
│                                    │ golden   │                  │
│                                    │ dataset  │                  │
│                                    │ +23 new  │                  │
│                                    │ cases    │                  │
│                                    └────┬─────┘                  │
│                                         │ Pass ✓                 │
│                                         ▼                        │
│                                    ┌──────────┐                  │
│                                    │ Deploy   │                  │
│                                    │ (canary) │                  │
│                                    └──────────┘                  │
└──────────────────────────────────────────────────────────────────┘
```

### Real Weekly Improvement Cycle

```python
# Weekly automated analysis pipeline

class WeeklyImprovementCycle:
    def run(self):
        # Step 1: Collect feedback signals
        signals = self.collect_signals(period="7d")
        # - Explicit: thumbs up/down, ratings, "was this helpful?"
        # - Implicit: user retried query, user contacted human support,
        #             user abandoned session, user edited AI output
        
        # Step 2: Cluster errors
        clusters = self.cluster_errors(signals.negative_feedback)
        # Uses embedding similarity to group related failures
        # Output: "12 failures related to date parsing",
        #         "8 failures related to multi-language input"
        
        # Step 3: Prioritize by impact
        prioritized = self.prioritize(clusters)
        # Priority = frequency × severity × fix_difficulty_inverse
        
        # Step 4: Generate improvement hypotheses
        for cluster in prioritized[:3]:  # Top 3 this week
            hypothesis = self.generate_hypothesis(cluster)
            # "Adding explicit date format instructions will reduce
            #  date parsing errors by 50%"
            
            # Step 5: Auto-generate candidate fix
            candidate_prompt = self.generate_fix(hypothesis)
            
            # Step 6: Eval against regression suite + new cases
            results = self.evaluate(candidate_prompt, 
                                   include_new_cases=cluster.examples)
            
            # Step 7: If passes, create PR for human review
            if results.passes_all_thresholds():
                self.create_pr(candidate_prompt, hypothesis, results)

# Output: 2-4 PRs per week with prompt improvements backed by data
```

---

## Agent Drift Detection

### Detecting Behavior Changes Without Code Changes

```yaml
# Agent drift detection configuration

drift_monitors:
  - agent: "agt-research-analyst-v2"
    
    # Behavioral baselines (computed from first 30 days of production)
    baselines:
      avg_steps_per_task: 8.3
      avg_tool_calls: 5.7
      tool_usage_distribution:
        web_search: 0.35
        sec_filing_lookup: 0.25
        news_aggregator: 0.20
        financial_data_api: 0.15
        calculator: 0.05
      avg_cost_per_task: $1.23
      avg_output_length_tokens: 847
      task_completion_rate: 0.94
      
    # Drift detection rules
    alerts:
      - name: "step_count_drift"
        condition: "rolling_7d_avg(steps) > baseline * 1.3"
        severity: "warning"
        possible_causes:
          - "Model provider update changed reasoning behavior"
          - "Retrieved content quality degraded"
          - "Tool API response format changed"
          
      - name: "tool_distribution_shift"
        condition: "jensen_shannon_divergence(current_dist, baseline_dist) > 0.15"
        severity: "warning"
        possible_causes:
          - "Model now prefers different tool ordering"
          - "One tool returning errors causing fallback to another"
          
      - name: "cost_spike"
        condition: "rolling_24h_avg(cost) > baseline * 2.0"
        severity: "critical"
        action: "pause_agent_and_alert"
        possible_causes:
          - "Model generating longer reasoning chains"
          - "Stuck in retry loops"
          - "Context window filling up causing re-prompts"
          
      - name: "completion_rate_drop"
        condition: "rolling_24h(completion_rate) < baseline - 0.10"
        severity: "critical"
        action: "alert_oncall"
```

### Real Drift Incident

```
2024-03-15: OpenAI updates GPT-4-turbo (no version pin available)

Detection Timeline:
  06:00 - Model update goes live (no notification from OpenAI)
  06:30 - Agent step count begins increasing (8.3 → 11.2 avg)
  07:15 - Cost monitor triggers: rolling cost up 40%
  07:15 - Alert fires to on-call engineer
  07:30 - Engineer investigates: agent now "thinking out loud" more
          New model is more verbose in reasoning, generating more
          intermediate steps before tool calls
  08:00 - Temporary fix: adjusted max_steps from 15 to 20
  08:30 - Root cause: model's reasoning style changed, prompt needed
          adjustment to be more directive ("Act, don't explain")
  09:00 - Prompt fix deployed, step count back to 8.5 avg
  
Post-mortem action: Pin to specific model snapshot where possible,
add explicit "be concise in reasoning" to all agent system prompts
```

---

## Prompt Regression Testing

### Automated Test Suite

```python
# ci/eval-runner.py — Runs on every prompt change PR

class PromptRegressionSuite:
    """
    Three-tier evaluation strategy:
    1. Fast checks (seconds) — syntax, format, basic quality
    2. Eval suite (minutes) — golden dataset, metrics
    3. Comparative (minutes) — side-by-side vs current production
    """
    
    def tier1_fast_checks(self, prompt):
        """Run in <10 seconds, catches obvious issues"""
        results = []
        
        # Check: prompt renders without errors
        results.append(self.check_template_renders(prompt))
        
        # Check: output format is parseable
        sample_output = self.run_single(prompt, self.smoke_test_input)
        results.append(self.check_output_parseable(sample_output))
        
        # Check: no banned phrases in output
        results.append(self.check_no_banned_content(sample_output))
        
        # Check: within token budget
        results.append(self.check_token_count(prompt, max_input=4000))
        
        return results
    
    def tier2_eval_suite(self, prompt):
        """Run full golden dataset evaluation (~3 minutes)"""
        dataset = self.load_golden_dataset(prompt.eval_config.dataset)
        
        results = []
        for example in dataset:
            output = self.run_prompt(prompt, example.input)
            for metric in prompt.eval_config.metrics:
                score = metric.evaluate(output, example.expected)
                results.append(EvalResult(
                    example_id=example.id,
                    metric=metric.name,
                    score=score,
                    passed=score >= metric.threshold
                ))
        
        # Aggregate
        summary = {}
        for metric in prompt.eval_config.metrics:
            metric_scores = [r.score for r in results if r.metric == metric.name]
            summary[metric.name] = {
                "mean": np.mean(metric_scores),
                "pass_rate": sum(1 for s in metric_scores if s >= metric.threshold) / len(metric_scores),
                "threshold": metric.threshold,
                "passed": np.mean(metric_scores) >= metric.threshold
            }
        
        return summary
    
    def tier3_comparative(self, new_prompt, production_prompt):
        """Side-by-side comparison on 50 random production inputs"""
        sample = self.sample_recent_production_inputs(n=50)
        
        comparisons = []
        for input_data in sample:
            old_output = self.run_prompt(production_prompt, input_data)
            new_output = self.run_prompt(new_prompt, input_data)
            
            # LLM judge comparison
            preference = self.llm_judge_preference(
                input_data, old_output, new_output
            )
            comparisons.append(preference)
        
        win_rate = sum(1 for c in comparisons if c == "new") / len(comparisons)
        return {
            "new_wins": win_rate,
            "old_wins": 1 - win_rate,
            "recommendation": "ship" if win_rate > 0.55 else "review"
        }
```

### CI Output on PR

```markdown
## Prompt Eval Results — `invoice-parser v4.2.0`

### Tier 1: Fast Checks ✓
All 4 checks passed in 6 seconds.

### Tier 2: Golden Dataset (500 examples)
| Metric | Baseline (v4.1.3) | New (v4.2.0) | Δ | Status |
|--------|-------------------|--------------|---|--------|
| extraction_accuracy | 0.912 | 0.934 | +0.022 | ✓ PASS |
| hallucination_rate | 0.041 | 0.012 | -0.029 | ✓ PASS |
| format_compliance | 0.98 | 0.97 | -0.01 | ✓ PASS |
| cost_per_doc | $0.023 | $0.025 | +$0.002 | ✓ PASS |

### Tier 3: Comparative (50 production samples)
New version preferred 64% of the time by LLM judge.
Recommendation: **SHIP**

### Regressions Detected: 0
No individual test cases regressed by more than 10%.
```

---

## Model Lifecycle Management

### Handling Model Deprecation (Real Scenario: GPT-4-0314 → GPT-4-turbo)

```yaml
# Model deprecation response plan

deprecation_event:
  model: "gpt-4-0314"
  announced: "2024-01-15"
  deprecated: "2024-06-13"
  affected_prompts: 47
  affected_agents: 3

response_plan:
  phase_1_assessment: # Week 1
    - Inventory all prompts/agents using deprecated model
    - Categorize by risk: [critical=12, high=18, medium=17]
    - Identify replacement model: gpt-4-turbo-2024-04-09
    
  phase_2_testing: # Weeks 2-4
    - Run ALL eval suites against replacement model
    - Expected: 80% of prompts work without changes
    - Reality: 71% passed, 29% needed prompt adjustments
    - Common issues:
        - "New model is more verbose → exceeded token limits"
        - "New model follows instructions differently → format breaks"
        - "New model refuses some previously-accepted edge cases"
    
  phase_3_migration: # Weeks 5-8
    - Fix 14 prompts that failed eval with new model
    - Deploy to staging with new model
    - Run comparative eval (old model vs new model) for all 47 prompts
    - Canary deploy: 10% traffic on new model
    
  phase_4_cutover: # Weeks 9-10
    - Gradual rollout: 10% → 50% → 100%
    - Keep old model API key active until full cutover confirmed
    - Remove old model references from codebase
    
  lessons_learned:
    - "Always pin to dated model versions (gpt-4-0314 not gpt-4)"
    - "Maintain eval suites that can test any model swap in <1 hour"
    - "Budget 6 weeks for model migration, not 2"
    - "Some prompts are model-specific — document these explicitly"
```

### Multi-Model Fallback Strategy

```python
# Production model configuration with fallback chain

MODEL_CONFIG = {
    "customer-support-response": {
        "primary": {
            "provider": "openai",
            "model": "gpt-4o-mini-2024-07-18",
            "timeout_ms": 5000,
            "max_retries": 2
        },
        "fallback_chain": [
            {
                "provider": "anthropic",
                "model": "claude-3-haiku-20240307",
                "timeout_ms": 8000,
                "trigger": "primary_timeout OR primary_error_rate > 5%"
            },
            {
                "provider": "openai",
                "model": "gpt-3.5-turbo-0125",
                "timeout_ms": 3000,
                "trigger": "all_above_unavailable",
                "note": "Degraded quality acceptable for <5min outages"
            }
        ],
        "circuit_breaker": {
            "error_threshold": 10,  # errors in 60 seconds
            "action": "switch_to_next_fallback",
            "recovery_check_interval": 30  # seconds
        }
    }
}
```

---

## AgentOps Dashboard

### Real Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AgentOps Dashboard — Last 24 Hours                          [Live 🟢]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ ┌─── Agent Health ───────────────────────────────────────────────────┐  │
│ │                                                                     │  │
│ │ Research Agent    ████████████████████░░  94.2% success  ($1,847)   │  │
│ │ Support Agent     █████████████████████░  97.1% success  ($892)    │  │
│ │ Doc Extractor     ███████████████████░░░  89.4% success  ($2,103)  │  │
│ │ Fraud Analyzer    █████████████████████░  96.8% success  ($445)    │  │
│ │ Code Reviewer     ████████████████░░░░░░  78.3% success  ($234)  ⚠ │  │
│ │                                                                     │  │
│ └─────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│ ┌─── Tool Usage Patterns ────────────────────────────────────────────┐  │
│ │                                                                     │  │
│ │ web_search          ████████████████ 2,347 calls  (12 errors, 0.5%)│  │
│ │ database_query      ███████████ 1,589 calls  (3 errors, 0.2%)      │  │
│ │ file_read           █████████ 1,203 calls  (0 errors)              │  │
│ │ api_call            ███████ 987 calls  (45 errors, 4.6%)  ⚠        │  │
│ │ calculator          ████ 534 calls  (0 errors)                      │  │
│ │                                                                     │  │
│ │ ⚠ api_call error rate elevated — SEC filing API returning 429s     │  │
│ └─────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│ ┌─── Error Categories ───────────────────────────────────────────────┐  │
│ │                                                                     │  │
│ │ Tool Timeout          ████████ 34 (mostly SEC API)                  │  │
│ │ Context Overflow      ████ 18 (Research Agent on long docs)         │  │
│ │ Loop Detected         ███ 12 (Code Reviewer retrying same fix)     │  │
│ │ Output Parse Fail     ██ 8 (JSON format violations)                │  │
│ │ Safety Filter Block   █ 4 (appropriate blocks)                     │  │
│ │ Budget Exceeded       █ 3 (Research Agent on complex tasks)        │  │
│ │                                                                     │  │
│ └─────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│ ┌─── Cost Trends (7-day) ────────────────────────────────────────────┐  │
│ │                                                                     │  │
│ │  $7K ┤                                                              │  │
│ │  $6K ┤         ╭─╮                                                  │  │
│ │  $5K ┤    ╭────╯ ╰──╮    ╭──                                       │  │
│ │  $4K ┤────╯         ╰────╯                                         │  │
│ │  $3K ┤                                                              │  │
│ │      └─────────────────────────────────                             │  │
│ │       Mon  Tue  Wed  Thu  Fri  Sat  Sun                             │  │
│ │                                                                     │  │
│ │  Daily avg: $5,521  |  Budget: $7,000/day  |  Utilization: 79%     │  │
│ └─────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│ ┌─── Recent Incidents ───────────────────────────────────────────────┐  │
│ │ 14:23 ⚠ Code Reviewer agent entered 5-step loop on PR #847        │  │
│ │ 11:07 ✓ Auto-recovered: SEC API timeout, switched to cached data   │  │
│ │ 08:45 ⚠ Research Agent cost $4.80 on single task (limit: $5.00)   │  │
│ └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Production Debugging

### Tracing a User Complaint to Root Cause

```
User complaint: "The chatbot told me my claim would be paid in 3 days, 
                 but that's not our policy"

Step 1: Find the conversation
─────────────────────────────
Search: user_id=U-4829 + timestamp=2024-03-14T14:30±30min
Result: conversation_id=conv-abc-789, trace_id=tr-xyz-456

Step 2: Pull the full trace
─────────────────────────────
$ agentops trace show tr-xyz-456

Trace: tr-xyz-456
├── Step 1: Intent Classification
│   ├── Prompt: pmt-cs-intent-v6.2.1
│   ├── Input: "When will I get paid for my fender bender claim?"
│   ├── Output: {"intent": "claim_status_inquiry", "confidence": 0.94}
│   └── Latency: 230ms
│
├── Step 2: Context Retrieval (RAG)
│   ├── Query: "claim payment timeline fender bender auto"
│   ├── Retrieved 4 chunks:
│   │   ├── chunk_1: "Standard auto claims are processed within 5-7 business days..."
│   │   ├── chunk_2: "Express claims for minor damage may be expedited to 3 days..."  ← PROBLEM
│   │   ├── chunk_3: "Payment is issued after adjuster approval..."
│   │   └── chunk_4: "Customers can track status in the app..."
│   ├── Retrieval scores: [0.89, 0.87, 0.82, 0.79]
│   └── Source: knowledge-base-v2024.02 (OUTDATED — v2024.03 exists)
│
├── Step 3: Response Generation
│   ├── Prompt: pmt-cs-response-gen-v8.2.0
│   ├── Model: gpt-4o-mini-2024-07-18
│   ├── Temperature: 0.3
│   ├── Input context included chunk_2 ("expedited to 3 days")
│   ├── Output: "Based on your minor fender bender claim, you should 
│   │           receive payment within approximately 3 business days..."
│   └── Latency: 890ms
│
└── Step 4: Guardrail Check
    ├── Toxicity: PASS
    ├── PII: PASS
    ├── Promise detection: MISS ← Should have caught "3 business days" as a promise
    └── Output delivered to user

ROOT CAUSE ANALYSIS:
1. Knowledge base was outdated (v2024.02, "3 day express" policy was removed in March)
2. Guardrail for "promise detection" didn't catch temporal commitments
3. Prompt lacked instruction: "Never commit to specific timelines"

FIXES DEPLOYED:
1. Updated knowledge base to v2024.03 (removed obsolete express timeline)
2. Added guardrail rule: block responses matching /\d+\s*(business\s+)?days?/
3. Added to prompt: "Never state specific timelines. Say 'typically' or 'usually'"
4. Added this case to regression test suite (example #2848)
```

---

## Rollback Strategies

### Independent Rollback of Different Components

```yaml
# Rollback decision matrix

rollback_scenarios:

  prompt_regression:
    detection: "Eval score drops below threshold on hourly check"
    action: "Roll back prompt to previous version"
    scope: "Only the specific prompt, nothing else changes"
    speed: "< 60 seconds (config change, no deployment)"
    example: |
      $ promptops rollback pmt-cs-response-gen --to v8.1.3
      Rolled back from v8.2.0 to v8.1.3
      Effective immediately for new requests.
      In-flight requests will complete with v8.2.0.
    risk: "Low — prompts are stateless, no data migration needed"

  model_regression:
    detection: "A/B test shows treatment (new model) underperforming"
    action: "Switch traffic back to control model"
    scope: "Model endpoint routing change"
    speed: "< 5 minutes (update routing config)"
    example: |
      $ modelops rollback mdl-claims-severity --to v12.3.1
      Traffic routing updated: 100% → v12.3.1
      Model v12.4.0 pods will scale down in 10 minutes.
    risk: "Low — but check if any downstream systems depend on new output format"

  agent_configuration_rollback:
    detection: "Agent success rate drops or cost spikes"
    action: "Roll back agent config (tools, parameters, system prompt)"
    scope: "Agent-specific, may affect multiple prompts"
    speed: "< 2 minutes"
    example: |
      $ agentops rollback agt-research-analyst --to v2.0.3
      Rolled back: system_prompt, tool_list, max_steps, cost_limit
      Previous config (v2.1.0) preserved for investigation.
    risk: "Medium — agent behavior is complex, need to verify tool compatibility"

  retrieval_rollback:
    detection: "RAG quality degrades (relevance scores drop, user complaints)"
    action: "Point retrieval to previous index version"
    scope: "Vector index / knowledge base version"
    speed: "< 10 minutes (index swap)"
    example: |
      $ ragops rollback knowledge-base --to v2024.02
      Index alias updated: production → v2024.02
      New index (v2024.03) preserved for debugging.
    risk: "Medium — old index may be missing recent content"

  full_system_rollback:
    detection: "Multiple components failing simultaneously"
    action: "Roll back entire feature to last-known-good state"
    scope: "Prompt + model + agent config + retrieval index"
    speed: "< 15 minutes"
    when_to_use: "Only when root cause is unclear and user impact is severe"
    example: |
      $ platform rollback feature/customer-support --to snapshot-2024-03-10
      Rolling back:
        ✓ Prompt: v8.2.0 → v8.1.3
        ✓ Model: gpt-4o-mini-2024-07-18 (unchanged)
        ✓ Agent: v2.1.0 → v2.0.3
        ✓ Knowledge base: v2024.03 → v2024.02
      Full rollback complete. Monitor: https://dashboard/customer-support
    risk: "High — may revert intentional improvements. Use as last resort."
```

### Rollback Decision Flowchart

```
User complaint or metric alert fires
         │
         ▼
Is impact limited to one component?
    │              │
   YES            NO
    │              │
    ▼              ▼
Identify which    Is root cause clear?
component:           │          │
 • Prompt?          YES         NO
 • Model?           │           │
 • Agent?           ▼           ▼
 • RAG?        Fix forward   Full system
    │          (if fix is    rollback to
    ▼          < 30 min)     last snapshot
Roll back                        │
that one                         ▼
component                    Investigate
only                         from safe state
```

---

## Summary: LLMOps vs AgentOps Maturity Checklist

| Capability | LLMOps (Prompts/RAG) | AgentOps (Autonomous Agents) |
|-----------|----------------------|-------------------------------|
| Versioning | Prompt versions in Git | Agent config + prompt + tool versions |
| Testing | Eval suites per prompt | End-to-end task completion tests |
| Monitoring | Output quality, latency, cost | + step count, tool patterns, loops |
| Drift detection | Output quality degradation | Behavioral pattern shifts |
| Rollback | Prompt version swap | Multi-component coordinated rollback |
| Cost control | Per-request budget | Per-task budget with circuit breakers |
| Debugging | Single trace (input→output) | Multi-step trace with branching |
| Safety | Output filters | Action-level permissions + human-in-loop |
