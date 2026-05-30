# LLMOps & AgentOps: Comprehensive Guide

## 1. LLMOps Lifecycle

LLMOps is the discipline of operationalizing LLM-based systems in production. Unlike traditional MLOps, the artifacts are fundamentally different: prompts replace feature pipelines, evaluations replace accuracy metrics, and human judgment replaces ground truth labels.

### 1.1 The Complete LLMOps Lifecycle Loop

```
Dataset Creation → Prompt/Model/Retriever Development → Offline Evaluation → Safety Evaluation
→ Regression Testing → Canary Release → Online Monitoring → Human Feedback
→ Dataset Update → Continuous Improvement → (loop)
```

#### Stage 1: Dataset Creation
- **Golden datasets**: Curated examples representing expected behavior across diverse scenarios
- **Production-mined datasets**: Real user interactions (anonymized) that capture distribution shifts
- **Adversarial datasets**: Deliberately crafted inputs to test edge cases and failure modes
- **Schema definition**: Each example has input, expected output, metadata (difficulty, category, source)
- **Quality gates**: Inter-annotator agreement, coverage metrics, diversity scores
- **Versioning**: Every dataset change is tracked with full lineage back to source

#### Stage 2: Prompt/Model/Retriever Development
- **Prompt engineering**: Systematic iteration on system prompts, few-shot examples, formatting instructions
- **Model selection**: Evaluating base models (GPT-4, Claude, Llama) against task requirements
- **Retriever tuning**: Chunk size, embedding model, reranking strategy, context window optimization
- **Configuration management**: All parameters tracked as versioned artifacts
- **Experiment tracking**: Every combination of (prompt, model, retriever config) logged with results

#### Stage 3: Offline Evaluation
- **Automated metrics**: BLEU, ROUGE, semantic similarity, task-specific metrics
- **LLM-as-judge**: Using a stronger model to evaluate outputs on dimensions like correctness, helpfulness, safety
- **Human evaluation**: Expert annotators rating outputs on rubrics
- **Slice-based evaluation**: Performance broken down by category, difficulty, user segment
- **Statistical rigor**: Confidence intervals, significance testing, effect sizes

#### Stage 4: Safety Evaluation
- **Toxicity detection**: Checking outputs for harmful, biased, or inappropriate content
- **Jailbreak testing**: Attempting to bypass safety guardrails with known attack vectors
- **PII leakage**: Verifying no training data or user data is exposed
- **Hallucination detection**: Measuring factual accuracy against known sources
- **Bias auditing**: Testing for demographic bias across protected categories
- **Compliance checking**: Regulatory requirements (GDPR, HIPAA, SOC2)

#### Stage 5: Regression Testing
- **Baseline comparison**: New version vs. current production on the full eval suite
- **No-regression gates**: Hard thresholds that must not degrade (safety, correctness)
- **Improvement tracking**: Metrics that should improve with the change
- **Edge case coverage**: Specific known failure cases that must remain fixed

#### Stage 6: Canary Release
- **Traffic splitting**: 1% → 5% → 25% → 50% → 100% progressive rollout
- **Canary metrics**: Latency, error rate, user satisfaction, safety flags
- **Automatic rollback triggers**: If canary metrics degrade beyond threshold
- **Cohort comparison**: Canary users vs. control on key business metrics

#### Stage 7: Online Monitoring
- **Real-time dashboards**: Latency, throughput, error rates, cost per request
- **Quality monitoring**: LLM-judge scoring a sample of production responses
- **Drift detection**: Input distribution shift, output distribution shift
- **Anomaly detection**: Sudden spikes in failures, latency, or cost
- **User behavior signals**: Thumbs up/down, regeneration rate, task completion

#### Stage 8: Human Feedback
- **Explicit feedback**: User ratings, corrections, complaints
- **Implicit feedback**: Regeneration, abandonment, follow-up clarification questions
- **Expert review**: Domain experts reviewing flagged or sampled outputs
- **Feedback routing**: Triaging feedback to appropriate team (safety, quality, product)

#### Stage 9: Dataset Update
- **Feedback incorporation**: Converting validated feedback into new eval examples
- **Production mining**: Extracting high-value examples from production traffic
- **Deduplication**: Ensuring new examples add diversity, not redundancy
- **Rebalancing**: Maintaining coverage across categories and difficulty levels

#### Stage 10: Continuous Improvement
- **Root cause analysis**: Understanding why failures occur (prompt? retriever? model limitation?)
- **Targeted fixes**: Addressing specific failure clusters with minimal scope changes
- **Hypothesis testing**: Formulating and testing improvement hypotheses
- **Prioritization**: Ranking improvements by impact, effort, and risk

---

## 2. AgentOps Lifecycle

AgentOps extends LLMOps to multi-step, tool-using agents where the complexity explodes due to compounding decisions, tool interactions, and longer trajectories.

### 2.1 The Complete AgentOps Lifecycle Loop

```
Agent Design → Tool Design → Permission Design → Trajectory Testing → Tool-Call Evaluation
→ Safety Red-Team → Deployment → Trace Monitoring → Failure Clustering
→ Policy/Prompt/Tool Update → (loop)
```

#### Stage 1: Agent Design
- **Goal decomposition**: Breaking complex goals into achievable sub-tasks
- **Architecture selection**: ReAct, Plan-and-Execute, Multi-agent, Hierarchical
- **Memory design**: What context persists across steps, conversation turns, sessions
- **Fallback strategy**: What happens when the agent gets stuck, loops, or fails
- **Termination conditions**: When does the agent stop (success, failure, timeout, budget)

#### Stage 2: Tool Design
- **Tool interface**: Clear input/output schemas with validation
- **Tool documentation**: Descriptions that help the LLM select and use tools correctly
- **Tool composition**: Which tools can be combined, ordering constraints
- **Error handling**: What errors each tool can return and how the agent should respond
- **Idempotency**: Ensuring repeated tool calls don't cause side effects
- **Rate limiting**: Protecting external services from excessive calls

#### Stage 3: Permission Design
- **Least privilege**: Agents get only the permissions they need for their task
- **Scoped access**: Time-limited, resource-limited, action-limited permissions
- **Human-in-the-loop gates**: High-risk actions require human approval
- **Audit trail**: Every permission use is logged with justification
- **Escalation paths**: When the agent needs permissions it doesn't have

#### Stage 4: Trajectory Testing
- **End-to-end scenarios**: Complete user goals tested from start to finish
- **Step-by-step validation**: Each intermediate step checked for correctness
- **Trajectory diversity**: Testing multiple valid paths to the same goal
- **Failure injection**: Simulating tool failures, timeouts, ambiguous results
- **Budget testing**: Verifying the agent stays within cost/time budgets

#### Stage 5: Tool-Call Evaluation
- **Tool selection accuracy**: Did the agent pick the right tool?
- **Parameter correctness**: Were the tool inputs correct?
- **Call necessity**: Were there unnecessary or redundant calls?
- **Ordering correctness**: Were tools called in a sensible order?
- **Error recovery**: Did the agent handle tool errors gracefully?

#### Stage 6: Safety Red-Team
- **Prompt injection via tools**: Malicious content in tool responses
- **Goal hijacking**: Attempting to redirect the agent to unintended goals
- **Privilege escalation**: Trying to get the agent to exceed its permissions
- **Data exfiltration**: Attempting to extract sensitive information through tool calls
- **Infinite loops**: Inputs that cause the agent to loop indefinitely
- **Resource exhaustion**: Inputs that cause excessive cost or API calls

#### Stage 7: Deployment
- **Progressive rollout**: Same canary approach as LLMOps but per-agent
- **Feature flags**: Enabling new tools or capabilities gradually
- **Version pinning**: Locking agent config (prompt + tools + model) as a deployable unit
- **Rollback readiness**: One-click revert to previous stable configuration

#### Stage 8: Trace Monitoring
- **Full trajectory logging**: Every LLM call, tool call, decision point
- **Latency breakdown**: Time spent in LLM inference vs. tool execution vs. waiting
- **Cost attribution**: Token usage, API calls, compute per trajectory
- **Success rate tracking**: Task completion rate over time
- **User satisfaction**: Correlation between trajectory patterns and user ratings

#### Stage 9: Failure Clustering
- **Automated clustering**: Grouping similar failures by pattern (same tool fails, same step fails)
- **Root cause tagging**: Categorizing failures (tool error, bad plan, hallucination, timeout)
- **Impact scoring**: Which failures affect the most users or highest-value tasks
- **Trend detection**: New failure modes appearing, old ones resurfacing
- **Reproduction**: Generating minimal reproduction cases from production failures

#### Stage 10: Policy/Prompt/Tool Update
- **Targeted fixes**: Updating specific prompts, tools, or policies based on failure analysis
- **Tool improvements**: Better error messages, input validation, documentation
- **Policy tightening**: New guardrails based on observed misuse patterns
- **Prompt refinement**: Adding examples or instructions for common failure modes

---

## 3. Must-Have Capabilities

### 3.1 Prompt Versioning
- Git-like version control for prompts
- Branching for experimentation
- Diff visualization (semantic diff, not just text diff)
- Deployment tags (which version is in prod/staging/dev)
- Rollback with one command
- Change attribution (who changed what and why)

### 3.2 Dataset Versioning
- Immutable snapshots with content-addressable storage
- Schema evolution (adding fields, changing types)
- Subset selection and filtering
- Quality metrics per version
- Lineage tracking (where each example came from)
- Automated freshness checks

### 3.3 Model Versioning
- Model checkpoints linked to training data and hyperparameters
- Fine-tuning lineage (base model → adapted model)
- Performance benchmarks per version
- Deployment history (which model served when)
- Cost and latency characteristics per version

### 3.4 Eval Versioning
- Eval suite definitions as code
- Metric implementations versioned alongside eval sets
- Judge prompt versioning (for LLM-as-judge)
- Historical results queryable across versions
- Eval validity metrics (does this eval measure what we think?)

### 3.5 Tool Versioning
- Tool interface versions (breaking vs. non-breaking changes)
- Tool behavior tests per version
- Compatibility matrix (which agent versions work with which tool versions)
- Deprecation workflow (warning → migration → removal)

### 3.6 Rollback Strategy
- **Instant rollback**: Switch production to previous version in seconds
- **Gradual rollback**: Progressive traffic shift back to old version
- **Selective rollback**: Rollback specific components (prompt but not model)
- **Rollback triggers**: Automated (metric threshold) or manual (operator decision)
- **Post-rollback analysis**: Understanding what went wrong

### 3.7 Canary Deployments
- Traffic splitting at the request level
- Sticky sessions (same user stays on same version)
- Metric comparison framework (statistical significance)
- Automatic promotion or rollback
- Multi-stage canary (1% → 10% → 50% → 100%)

### 3.8 Online/Offline Eval Comparison
- Correlation analysis between offline metrics and production outcomes
- Offline eval validity scoring (does offline improvement translate to online improvement?)
- Drift alerts when online metrics diverge from offline predictions
- Calibration of offline evals to match online reality

### 3.9 Human Review Queue
- Priority-based queue (safety issues first, then quality, then optimization)
- Review assignment (expertise matching, load balancing)
- Review tools (side-by-side comparison, annotation, categorization)
- Review metrics (throughput, agreement, time-to-review)
- Feedback routing (review results feed into datasets, evals, prompts)

### 3.10 Production Feedback Mining
- Automated extraction of improvement signals from production data
- Clustering similar issues for batch resolution
- Identifying high-impact improvement opportunities
- Building eval examples from production failures
- Tracking improvement over time after changes

---

## 4. LLMOps vs MLOps: Key Differences

| Dimension | Traditional MLOps | LLMOps |
|-----------|------------------|--------|
| **Primary artifact** | Model weights + feature pipeline | Prompts + retrieval config + model selection |
| **Training** | Custom training on labeled data | Prompt engineering + few-shot + fine-tuning |
| **Evaluation** | Accuracy, F1, AUC on held-out set | LLM-as-judge, human eval, task-specific rubrics |
| **Ground truth** | Clear labels exist | Often subjective, multiple valid outputs |
| **Iteration speed** | Days-weeks (retrain) | Minutes-hours (prompt change) |
| **Cost model** | Compute for training + inference | Per-token pricing, context window costs |
| **Failure modes** | Wrong prediction | Hallucination, harmful content, off-topic, verbose |
| **Monitoring** | Data drift, model decay | Prompt injection, quality drift, cost spikes |
| **Versioning** | Model checkpoints | Prompt versions + config versions + eval versions |
| **Testing** | Unit tests on predictions | Behavioral tests, adversarial tests, safety tests |
| **Deployment** | Model serving (batch/real-time) | Prompt deployment + guardrail deployment |
| **Rollback** | Revert model version | Revert prompt + config + guardrails independently |
| **Data pipeline** | Feature engineering + labeling | Dataset curation + feedback loops |
| **Human-in-loop** | Labeling for training | Evaluation, feedback, safety review |
| **Experimentation** | A/B test model versions | A/B test prompts, models, retrieval configs |

### Key Insight
In MLOps, the model IS the artifact. In LLMOps, the system around the model (prompts, retrieval, guardrails, routing) is equally or more important than the model itself.

---

## 5. Advanced Evaluation Topics

### 5.1 Eval Validity
- **Construct validity**: Does the eval measure what we think it measures?
- **Content validity**: Does the eval cover the full range of expected behavior?
- **Criterion validity**: Does the eval correlate with real-world outcomes?
- **Face validity**: Do experts agree the eval makes sense?

### 5.2 Eval Reliability
- **Test-retest reliability**: Same input produces same eval result across runs
- **Internal consistency**: Different items measuring the same construct agree
- **Parallel forms**: Alternative eval sets produce similar results
- **Inter-rater reliability**: Different judges (human or LLM) agree on scores

### 5.3 Inter-Rater Agreement
- **Cohen's Kappa**: Agreement between two raters beyond chance
- **Fleiss' Kappa**: Agreement among multiple raters
- **Krippendorff's Alpha**: Handles missing data, ordinal scales
- **Percent agreement**: Simple but doesn't account for chance agreement
- **Calibration sessions**: Regular alignment between raters on standards

### 5.4 Judge Calibration
- **Anchor examples**: Known-score examples to calibrate LLM judges
- **Position bias**: LLM judges prefer first or last option (mitigate with randomization)
- **Verbosity bias**: LLM judges prefer longer outputs (mitigate with length-controlled pairs)
- **Self-preference**: LLM judges prefer their own outputs (use different model as judge)
- **Calibration curves**: Mapping judge scores to human agreement rates

### 5.5 Statistical Significance
- **Paired tests**: Comparing two systems on the same examples (paired t-test, Wilcoxon)
- **Bootstrap confidence intervals**: Non-parametric estimation of metric uncertainty
- **Multiple comparison correction**: Bonferroni, Holm-Bonferroni when testing many hypotheses
- **Effect size**: Practical significance beyond statistical significance (Cohen's d)
- **Power analysis**: How many examples needed to detect a meaningful difference

### 5.6 Confidence Intervals
- **Bootstrap CIs**: Resample eval results to estimate metric distribution
- **Wilson score interval**: For binary metrics (pass/fail)
- **Normal approximation**: For large sample sizes
- **Reporting**: Always report CIs alongside point estimates

### 5.7 Slice-Based Evaluation
- **Demographic slices**: Performance across user groups
- **Difficulty slices**: Easy, medium, hard examples
- **Category slices**: Different task types or domains
- **Length slices**: Short vs. long inputs/outputs
- **Temporal slices**: Performance over time periods
- **Source slices**: Performance on synthetic vs. production examples

### 5.8 Counterfactual Evals
- **Minimal pairs**: Change one aspect of input, measure output change
- **Sensitivity testing**: Which input features most affect output quality?
- **Robustness testing**: Does paraphrasing the input change the output inappropriately?
- **Invariance testing**: Changes that shouldn't affect output (e.g., user name)

### 5.9 Adversarial Evals
- **Prompt injection**: Attempting to override system instructions
- **Jailbreaking**: Bypassing safety guidelines
- **Data extraction**: Attempting to extract training data or system prompts
- **Logical traps**: Inputs designed to cause reasoning failures
- **Edge cases**: Extremely long inputs, empty inputs, special characters

### 5.10 Longitudinal Evals
- **Temporal consistency**: Does quality remain stable over weeks/months?
- **Degradation detection**: Catching slow quality decline
- **Seasonal patterns**: Quality variations with usage patterns
- **Model deprecation impact**: Catching issues when providers update models

### 5.11 Production Shadow Evals
- **Shadow scoring**: Running evals on production traffic without affecting responses
- **Sampling strategy**: Which requests to evaluate (random, stratified, triggered)
- **Delayed evaluation**: Scoring after user behavior reveals quality signal
- **Cost management**: Balancing eval coverage with judge API costs

### 5.12 A/B Testing
- **Randomization unit**: User-level, session-level, or request-level
- **Metric selection**: Primary metric, guardrail metrics, secondary metrics
- **Duration planning**: Running long enough for statistical power
- **Interference**: Ensuring variants don't affect each other (network effects)
- **Analysis**: Intent-to-treat, per-protocol, segmented analysis

### 5.13 Canary Evals
- **Progressive evaluation**: Increase eval depth as canary progresses
- **Early stopping**: Halt canary if early eval signals are negative
- **Comparison framework**: Statistical comparison between canary and control
- **Eval cost scaling**: More expensive evals only at higher traffic percentages

---

## 6. Continuous Improvement Loop

### The Flywheel

```
Production Data → Failure Detection → Root Cause Analysis → Hypothesis Formation
→ Targeted Fix → Offline Evaluation → Regression Test → Deploy → Monitor → (loop)
```

### Principles
1. **Data-driven**: Every improvement motivated by production evidence
2. **Targeted**: Fix specific failure modes, not broad rewrites
3. **Measurable**: Every change has a measurable expected improvement
4. **Safe**: Changes go through full eval pipeline before production
5. **Fast**: Minimize time from failure detection to fix deployment
6. **Compound**: Each improvement makes future improvements easier (better data, evals)

### Anti-Patterns
- Prompt changes without evaluation ("it looks better to me")
- Broad prompt rewrites that fix one thing but break others
- Ignoring production signals in favor of offline metrics only
- Shipping without regression testing
- Not tracking what changed and why

---

## 7. Version Control for AI Artifacts

### What to Version
| Artifact | Format | Storage | Diff Strategy |
|----------|--------|---------|---------------|
| System prompts | Text/Markdown | Git | Text diff + semantic diff |
| Few-shot examples | JSON/YAML | Git + Object store | Structural diff |
| Model configs | YAML | Git | Key-value diff |
| Retrieval configs | YAML | Git | Key-value diff |
| Tool definitions | JSON Schema | Git | Schema diff |
| Eval definitions | Python + YAML | Git | Code diff |
| Eval datasets | JSONL | Object store (content-addressed) | Row-level diff |
| Guardrail configs | YAML | Git | Key-value diff |
| Deployment configs | YAML/Terraform | Git | Standard IaC diff |

### Versioning Principles
1. **Atomic deployments**: All related artifacts version together
2. **Immutable versions**: Once created, never modified
3. **Linkage**: Every deployment links to exact artifact versions
4. **Reproducibility**: Any historical configuration can be recreated
5. **Auditability**: Full history of who changed what and why

---

## 8. Experiment Tracking

### What to Track
- **Inputs**: Prompt version, model, retrieval config, dataset version, eval version
- **Outputs**: All metric values, per-example results, latency, cost
- **Metadata**: Timestamp, author, hypothesis, notes
- **Context**: Git commit, environment, dependencies

### Experiment Lifecycle
1. **Hypothesis**: "Changing X will improve Y by Z%"
2. **Design**: Choose eval dataset, metrics, success criteria
3. **Execute**: Run experiment with full logging
4. **Analyze**: Compare results against baseline and hypothesis
5. **Decide**: Ship, iterate, or abandon
6. **Document**: Record learnings regardless of outcome

### Best Practices
- Never delete failed experiments (they contain learnings)
- Always compare against a fixed baseline (not just previous experiment)
- Track cost alongside quality (Pareto frontier)
- Tag experiments with categories for later analysis
- Share experiment results with team (avoid duplicate work)
