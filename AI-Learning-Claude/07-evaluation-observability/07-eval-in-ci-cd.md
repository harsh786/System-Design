# Evaluation in CI/CD

## The Eval Gate Concept

**Analogy**: In manufacturing, quality control stops defective products from shipping. The eval gate does the same for AI — if quality drops, the deploy is blocked.

Traditional CI/CD gates:
- Tests pass ✓
- Lint passes ✓
- Build succeeds ✓

AI CI/CD gates add:
- Faithfulness > 0.9 ✓
- Hallucination rate < 5% ✓
- Latency P95 < 3s ✓
- No quality regression vs production ✓

## The CI/CD Evaluation Pipeline

```mermaid
graph TD
    PR[Pull Request] --> CI[CI Pipeline]

    CI --> Unit[Unit Tests]
    CI --> Lint[Lint & Format]
    CI --> Eval[Eval Suite]

    Eval --> GD[Run Against Golden Dataset<br>100 test cases]
    GD --> Scores[Compute Metrics<br>Faithfulness, Relevance, etc.]
    Scores --> Compare[Compare vs Production Baseline]

    Compare --> Gate{All Gates Pass?}
    Gate -->|No| Block[Block Merge ❌<br>Show regression report]
    Gate -->|Yes| Merge[Allow Merge ✓]

    Merge --> Staging[Deploy to Staging]
    Staging --> Shadow[Shadow Evaluation<br>Real queries, compare outputs]
    Shadow --> ShadowGate{Quality maintained?}
    ShadowGate -->|No| Rollback1[Rollback]
    ShadowGate -->|Yes| Canary[Canary Deploy 5%]

    Canary --> CanaryGate{Canary metrics OK?}
    CanaryGate -->|No| Rollback2[Rollback]
    CanaryGate -->|Yes| Full[Full Deploy 100%]
    Full --> Monitor[Continuous Monitoring]

    style Eval fill:#e1f5fe
    style Gate fill:#fff3e0
    style Block fill:#ffebee
    style Full fill:#e8f5e9
```

## The 6 Stages

### Stage 1: On PR — Run Eval Suite

Every pull request triggers evaluation against your golden dataset:

```yaml
# .github/workflows/ai-eval.yml
on: pull_request
jobs:
  eval:
    steps:
      - run: python eval/run_eval.py --dataset golden_dataset.json
      - run: python eval/compare.py --baseline production_scores.json
      - run: python eval/gate.py --thresholds thresholds.yaml
```

### Stage 2: Compare — New vs Production

Don't just check absolute scores. Check for **regression**:

```
Metric          | Production | This PR | Delta  | Status
----------------|-----------|---------|--------|-------
Faithfulness    | 0.94      | 0.93    | -0.01  | ✓ (within tolerance)
Relevance       | 0.91      | 0.88    | -0.03  | ⚠️ WARNING
Hallucination   | 3.1%      | 7.2%    | +4.1%  | ❌ FAIL
Latency P95     | 2.8s      | 2.9s    | +0.1s  | ✓
```

### Stage 3: Gate — Block if Quality Drops

Block the deployment if ANY critical metric crosses its threshold.

### Stage 4: Shadow — Deploy to Shadow

Shadow deployment processes real production queries but doesn't serve responses to users. Compare shadow outputs against production outputs.

### Stage 5: Canary — 5% Traffic

Route 5% of real traffic to the new version. Monitor quality metrics in real-time. If any degradation, roll back immediately.

### Stage 6: Full Deploy

Only after all gates pass: full production deployment with ongoing monitoring.

## Minimum Eval Gates

### Recommended Thresholds

```yaml
# thresholds.yaml
gates:
  # Quality gates (absolute minimums)
  faithfulness:
    min: 0.90
    description: "Answer must be grounded in context"

  answer_relevance:
    min: 0.85
    description: "Answer must address the question"

  hallucination_rate:
    max: 0.05
    description: "No more than 5% of answers contain hallucinations"

  # Performance gates
  latency_p95:
    max_seconds: 3.0
    description: "95th percentile response time"

  cost_per_request:
    max_dollars: 0.05
    description: "Average cost per request"

  # Regression gates (relative to production)
  max_regression:
    faithfulness: 0.02      # Allow max 2% drop
    relevance: 0.03         # Allow max 3% drop
    latency_p95: 0.5        # Allow max 500ms increase
```

### Gate Decision Logic

```python
def check_gates(scores, thresholds, production_baseline):
    failures = []

    # Absolute gates
    if scores["faithfulness"] < thresholds["faithfulness"]["min"]:
        failures.append(f"Faithfulness {scores['faithfulness']:.2f} < {thresholds['faithfulness']['min']}")

    if scores["hallucination_rate"] > thresholds["hallucination_rate"]["max"]:
        failures.append(f"Hallucination {scores['hallucination_rate']:.1%} > {thresholds['hallucination_rate']['max']:.1%}")

    # Regression gates
    faith_drop = production_baseline["faithfulness"] - scores["faithfulness"]
    if faith_drop > thresholds["max_regression"]["faithfulness"]:
        failures.append(f"Faithfulness regression: {faith_drop:.2f} > allowed {thresholds['max_regression']['faithfulness']}")

    return len(failures) == 0, failures
```

## Statistical Significance

### How Many Eval Samples Do You Need?

Running eval on 5 examples tells you nothing. You need enough samples for statistical confidence.

| Desired Precision | Samples Needed | Reasoning |
|---|---|---|
| ±10% | ~50 | Quick sanity check |
| ±5% | ~200 | Reasonable for CI |
| ±2% | ~1,000 | High confidence |
| ±1% | ~5,000 | Research-grade |

**Rule of thumb**: 100-200 golden dataset examples is the sweet spot for CI/CD — fast enough to run on every PR, large enough to detect real regressions.

### Detecting Real Regressions vs Noise

Use confidence intervals:

```python
import numpy as np
from scipy import stats

def is_significant_regression(old_scores, new_scores, alpha=0.05):
    """Test if new scores are significantly worse than old scores."""
    t_stat, p_value = stats.ttest_ind(old_scores, new_scores, alternative='greater')
    return p_value < alpha  # True = statistically significant regression
```

## Regression Detection and Rollback

### Automatic Rollback Triggers

| Trigger | Condition | Action |
|---|---|---|
| Quality crash | Faithfulness < 0.8 for 5 min | Immediate rollback |
| Gradual degradation | Quality trending down 3 consecutive hours | Alert + auto-rollback |
| Error spike | Error rate > 10% for 5 min | Immediate rollback |
| Cost explosion | Cost > 5x normal for 15 min | Rate limit + alert |

### Rollback Strategy

```mermaid
graph TD
    Monitor[Production Monitoring] --> Detect{Regression Detected?}
    Detect -->|No| Monitor
    Detect -->|Yes| Severity{Severity?}

    Severity -->|Critical<br>Quality < 0.8| Auto[Auto Rollback<br>Immediate]
    Severity -->|High<br>Quality dropping| Alert[Alert Team<br>+ Prepare Rollback]
    Severity -->|Medium<br>Minor regression| Log[Log & Investigate<br>No rollback yet]

    Auto --> Previous[Revert to Previous Version]
    Alert --> Decision{Team Decision}
    Decision -->|Rollback| Previous
    Decision -->|Accept| Monitor

    Previous --> Verify[Verify Rollback Quality]
    Verify --> Postmortem[Post-mortem Analysis]

    style Auto fill:#ffebee
    style Alert fill:#fff3e0
    style Log fill:#e1f5fe
```

## Putting It All Together

A complete CI/CD eval workflow:

1. **Developer changes prompt/code** → Opens PR
2. **CI runs eval suite** (2 min) → 150 golden examples evaluated
3. **Gate checks** → All metrics above threshold, no significant regression
4. **PR merged** → Deploy to staging
5. **Shadow evaluation** (1 hour) → Compare against production on real queries
6. **Canary deploy** (2 hours) → 5% traffic, monitor quality
7. **Full deploy** → 100% traffic
8. **Continuous monitoring** → Alert on any degradation
9. **Auto-rollback** → If quality drops below critical threshold

## Key Takeaways

1. **Eval gates block bad deployments** — like tests, but for AI quality
2. **Compare against production** — absolute scores AND regression detection
3. **Progressive deployment** — shadow → canary → full, with gates at each stage
4. **Statistical significance matters** — 100+ examples minimum for CI
5. **Auto-rollback on quality crashes** — don't wait for humans when quality collapses
6. **Version everything** — prompts, golden datasets, thresholds, eval code

---

*Next: Programs — hands-on implementation of evaluation systems*
