# Observability & Monitoring for ML Systems

## Overview

ML monitoring is fundamentally different from traditional software monitoring. Software bugs are deterministic — ML models can silently degrade while returning valid responses. A model returning 200 OK with 95% confidence on a wrong prediction is harder to detect than a 500 error.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML MONITORING LAYERS                                                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Layer 4: BUSINESS METRICS                                         │    │
│  │  Revenue, CTR, Conversion, User Satisfaction                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Layer 3: MODEL PERFORMANCE                                        │    │
│  │  Accuracy, Precision, Recall, AUC, Calibration                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Layer 2: DATA QUALITY & DRIFT                                     │    │
│  │  Input distributions, Feature drift, Schema violations            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Layer 1: INFRASTRUCTURE                                           │    │
│  │  Latency, Throughput, GPU util, Memory, Errors                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Detection Speed:   Layer 1 (seconds) → Layer 4 (days/weeks)              │
│  Root Cause Value:  Layer 1 (low) → Layer 4 (high)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ML-Specific Monitoring Challenges

| Challenge | Why It's Hard | Traditional Software Equivalent |
|-----------|--------------|-------------------------------|
| Silent failures | Model returns valid output but wrong prediction | No equivalent — errors are explicit |
| Delayed feedback | Ground truth arrives hours/days/months later | Immediate error detection |
| Distribution shift | Input data changes over time | Inputs are well-defined by API |
| Feedback loops | Model predictions change future inputs | Rarely exists |
| Non-stationarity | Optimal behavior changes (seasonality, trends) | Business logic is stable |
| Fairness degradation | Model becomes biased on subgroups | Not applicable |

---

## Data Drift Detection

### Types of Drift

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TYPES OF DRIFT                                                         │
│                                                                          │
│  1. COVARIATE SHIFT (Input drift)                                      │
│     P(X) changes, P(Y|X) stays same                                   │
│     Example: User demographics shift (younger users join)              │
│                                                                          │
│  2. CONCEPT DRIFT (Relationship changes)                               │
│     P(Y|X) changes                                                     │
│     Example: What "spam" looks like evolves                            │
│                                                                          │
│  3. PRIOR PROBABILITY SHIFT (Label distribution changes)               │
│     P(Y) changes                                                       │
│     Example: Fraud rate increases during holiday season                │
│                                                                          │
│  Timeline:                                                              │
│  ┌─────┐  ┌─────────────┐  ┌──────────────────────────────────┐      │
│  │Train │  │ Deploy      │  │  Production (drift accumulates) │      │
│  │Data  │  │ (matches    │  │                                  │      │
│  │      │  │  training)  │  │  ~~~~gradual drift~~~~~          │      │
│  └─────┘  └─────────────┘  │         OR                       │      │
│                              │  ████ sudden shift ████          │      │
│                              └──────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Statistical Tests for Drift Detection

| Test | Type | Use Case | Pros | Cons |
|------|------|----------|------|------|
| KS Test | Non-parametric | Continuous features | No assumptions | Sensitive to sample size |
| Chi-Square | Parametric | Categorical features | Well-understood | Assumes large samples |
| PSI (Population Stability Index) | Binning-based | Any distribution | Industry standard | Bin selection matters |
| Jensen-Shannon Divergence | Information theory | Any distribution | Symmetric, bounded | Less interpretable |
| MMD (Maximum Mean Discrepancy) | Kernel-based | High-dimensional | Multivariate | Computationally expensive |
| Wasserstein Distance | Optimal transport | Continuous | Interpretable magnitude | Expensive for high-dim |
| Page-Hinkley | Sequential | Streaming detection | Low memory | Sensitive to threshold |

### PSI (Population Stability Index) Implementation

```python
import numpy as np

def calculate_psi(reference, current, bins=10):
    """
    PSI < 0.1: No significant change
    0.1 <= PSI < 0.2: Moderate change (investigate)
    PSI >= 0.2: Significant change (action required)
    """
    # Create bins from reference distribution
    breakpoints = np.quantile(reference, np.linspace(0, 1, bins + 1))
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    
    # Calculate proportions
    ref_counts = np.histogram(reference, bins=breakpoints)[0]
    cur_counts = np.histogram(current, bins=breakpoints)[0]
    
    ref_pct = ref_counts / len(reference) + 1e-6
    cur_pct = cur_counts / len(current) + 1e-6
    
    # PSI formula
    psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return psi
```

### Drift Detection Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DRIFT DETECTION PIPELINE                                               │
│                                                                          │
│  ┌──────────────┐                                                      │
│  │  Production  │    ┌───────────────────────────────────────────┐     │
│  │  Predictions │───▶│  Drift Detection Service                  │     │
│  │  (sampled)   │    │                                           │     │
│  └──────────────┘    │  ┌─────────────────────────────────────┐ │     │
│                       │  │  Reference Distribution             │ │     │
│  ┌──────────────┐    │  │  (from training data)               │ │     │
│  │  Reference   │───▶│  └─────────────────────────────────────┘ │     │
│  │  Data        │    │                                           │     │
│  └──────────────┘    │  For each feature:                       │     │
│                       │  ├── Compute PSI                         │     │
│                       │  ├── KS test p-value                     │     │
│                       │  ├── Mean/std shift                      │     │
│                       │  └── Null rate change                    │     │
│                       │                                           │     │
│                       │  Aggregate drift score                   │     │
│                       └──────────────────┬────────────────────────┘     │
│                                           │                              │
│                              ┌────────────┼────────────┐                │
│                              ▼            ▼            ▼                │
│                        ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│                        │  Green   │ │  Yellow  │ │   Red    │         │
│                        │ PSI<0.1  │ │0.1-0.2   │ │ PSI>0.2  │         │
│                        │ No action│ │Investigate│ │ Alert!   │         │
│                        └──────────┘ └──────────┘ └──────────┘         │
│                                                          │              │
│                                                          ▼              │
│                                                   ┌──────────────┐     │
│                                                   │ Auto-trigger │     │
│                                                   │ retraining   │     │
│                                                   └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Model Performance Monitoring

### When Ground Truth is Delayed

```
┌─────────────────────────────────────────────────────────────────┐
│  MONITORING WITH DELAYED LABELS                                  │
│                                                                   │
│  Prediction Time     Label Available     Delay                  │
│  ──────────────      ───────────────     ─────                  │
│  Fraud detection     After investigation  Days-Weeks            │
│  Ad click prediction After ad shown       Minutes               │
│  Loan default        After loan term      Months-Years          │
│  Content recommendation After engagement  Hours                 │
│                                                                   │
│  Proxy Metrics (available immediately):                         │
│  ├── Prediction distribution stability                          │
│  ├── Prediction confidence distribution                         │
│  ├── Feature importance stability                               │
│  ├── Prediction correlations with known signals                │
│  └── Agreement with shadow model                               │
│                                                                   │
│  Timeline:                                                       │
│  ┌─────┬────────┬──────────┬──────────────────────┐            │
│  │Pred │ Proxy  │  Partial │  Full Ground Truth   │            │
│  │     │Metrics │  Labels  │  (delayed)           │            │
│  │ t=0 │  t=0   │  t+hours │  t+days/weeks        │            │
│  └─────┴────────┴──────────┴──────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Monitoring Dashboard Metrics

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MODEL PERFORMANCE DASHBOARD                                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  Real-time Metrics (no labels needed)                        │       │
│  │  ├── Prediction volume (QPS)         [████████░░] 8.2K      │       │
│  │  ├── Prediction distribution         Mean: 0.34, Std: 0.21 │       │
│  │  ├── Confidence distribution         P50: 0.89, P10: 0.62  │       │
│  │  ├── Latency (p50/p95/p99)          8ms / 15ms / 42ms     │       │
│  │  ├── Error rate                      0.01%                  │       │
│  │  └── Feature completeness            99.2%                  │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  Delayed Metrics (with labels, updated daily)                │       │
│  │  ├── AUC-ROC                         0.941 (↓0.003)        │       │
│  │  ├── Precision @ 1% FPR             0.67  (↓0.02)         │       │
│  │  ├── Calibration error               0.018 (stable)        │       │
│  │  ├── Segment performance:                                   │       │
│  │  │   ├── New users:    AUC 0.91 (↓0.01)                   │       │
│  │  │   ├── Power users:  AUC 0.96 (stable)                  │       │
│  │  │   └── Region-EU:    AUC 0.93 (↓0.005)                  │       │
│  │  └── Fairness metrics:                                      │       │
│  │      ├── Demographic parity: 0.95 (OK)                     │       │
│  │      └── Equal opportunity:  0.92 (OK)                      │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Concept Drift Detection

### Approaches

```
┌─────────────────────────────────────────────────────────────────┐
│  CONCEPT DRIFT DETECTION METHODS                                 │
│                                                                   │
│  1. Error-Rate Based (requires labels)                          │
│     ┌─────────────────────────────────┐                         │
│     │  ADWIN (Adaptive Windowing)     │                         │
│     │  - Maintains variable window    │                         │
│     │  - Detects when error rate      │                         │
│     │    in recent window differs     │                         │
│     │    significantly from history   │                         │
│     └─────────────────────────────────┘                         │
│                                                                   │
│  2. Distribution-Based (no labels needed)                       │
│     ┌─────────────────────────────────┐                         │
│     │  Monitor P(Y_hat) over time     │                         │
│     │  If prediction distribution     │                         │
│     │  shifts → likely concept drift  │                         │
│     └─────────────────────────────────┘                         │
│                                                                   │
│  3. Model-Based                                                  │
│     ┌─────────────────────────────────┐                         │
│     │  Train a "drift detector" model │                         │
│     │  that classifies: "old" vs "new"│                         │
│     │  distribution data              │                         │
│     │  High accuracy → drift exists   │                         │
│     └─────────────────────────────────┘                         │
│                                                                   │
│  4. Performance Decay Monitoring                                │
│     ┌─────────────────────────────────┐                         │
│     │  Track rolling performance:     │                         │
│     │  Week 1: AUC 0.95              │                         │
│     │  Week 2: AUC 0.94              │                         │
│     │  Week 3: AUC 0.92 ← trigger   │                         │
│     │  Threshold: >2% drop           │                         │
│     └─────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Alerting Strategies

### Alert Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ML ALERTING DECISION TREE                                              │
│                                                                          │
│  Anomaly Detected                                                       │
│  │                                                                       │
│  ├── Infrastructure issue?                                              │
│  │   ├── Yes → Page on-call SRE (P1)                                  │
│  │   │   Examples: GPU OOM, service down, latency spike                │
│  │   └── No ↓                                                          │
│  │                                                                       │
│  ├── Data quality issue?                                                │
│  │   ├── Yes → Alert data engineering team (P2)                        │
│  │   │   Examples: Missing features, schema change, stale data         │
│  │   │   Action: Activate fallback model or cached predictions         │
│  │   └── No ↓                                                          │
│  │                                                                       │
│  ├── Feature drift (input distribution)?                               │
│  │   ├── Gradual → Monitor, schedule investigation (P3)               │
│  │   └── Sudden → Investigate immediately (P2)                         │
│  │       Action: Check upstream data sources                           │
│  │                                                                       │
│  ├── Model performance degradation?                                     │
│  │   ├── Mild (<5% drop) → Schedule retraining (P3)                   │
│  │   ├── Moderate (5-15%) → Expedite retraining (P2)                  │
│  │   └── Severe (>15%) → Rollback to previous model (P1)             │
│  │                                                                       │
│  └── Fairness violation?                                                │
│      ├── Regulatory concern → Immediate rollback (P1)                  │
│      └── Non-critical → Schedule fix, document (P2)                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Alert Configuration Best Practices

```yaml
# Example alerting rules (Prometheus + custom metrics)
alerts:
  - name: model_latency_high
    condition: p99_latency_ms > 100
    for: 5m
    severity: P2
    action: scale_up_replicas
    
  - name: prediction_volume_drop
    condition: qps < 0.5 * rolling_avg_7d
    for: 10m
    severity: P1
    action: page_oncall
    
  - name: feature_drift_detected
    condition: max_feature_psi > 0.2
    for: 1h  # sustained drift, not transient
    severity: P3
    action: trigger_investigation
    
  - name: model_accuracy_degraded
    condition: rolling_auc_7d < 0.90
    severity: P2
    action: trigger_retraining
    
  - name: prediction_distribution_shift
    condition: js_divergence(pred_dist, reference_dist) > 0.1
    for: 30m
    severity: P2
    action: investigate_and_shadow_compare
```

---

## Logging Best Practices for ML

### What to Log

```
┌─────────────────────────────────────────────────────────────────┐
│  ML PREDICTION LOG SCHEMA                                        │
│                                                                   │
│  {                                                               │
│    "request_id": "uuid",                                        │
│    "timestamp": "2024-01-20T10:30:00Z",                        │
│    "model_version": "fraud-v2.1.3",                            │
│    "model_name": "fraud_detection",                            │
│                                                                   │
│    "input": {                                                    │
│      "features": {                                              │
│        "transaction_amount": 299.99,                            │
│        "merchant_category": "electronics",                      │
│        "user_tenure_days": 45,                                  │
│        ...                                                       │
│      },                                                          │
│      "feature_source": "online_store_v3",                      │
│      "feature_freshness_ms": 120                               │
│    },                                                            │
│                                                                   │
│    "output": {                                                   │
│      "prediction": 0.87,                                        │
│      "label": "fraud",                                          │
│      "confidence": 0.87,                                        │
│      "explanation": {                                           │
│        "top_features": [                                        │
│          {"name": "amount", "contribution": 0.35},             │
│          {"name": "new_merchant", "contribution": 0.28}        │
│        ]                                                         │
│      }                                                           │
│    },                                                            │
│                                                                   │
│    "metadata": {                                                 │
│      "latency_ms": 12,                                          │
│      "gpu_id": "gpu-3",                                         │
│      "batch_size": 16,                                          │
│      "cache_hit": false,                                        │
│      "experiment_id": "ab-test-42",                            │
│      "treatment": "model_b"                                    │
│    }                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Log Sampling Strategy

```
Traffic Level      Sampling Rate    Storage Cost/Month    Use Case
< 100 QPS         100%             ~$50                  Full audit trail
100-1K QPS        50%              ~$200                 Detailed monitoring
1K-10K QPS        10%              ~$400                 Statistical monitoring
10K-100K QPS      1%               ~$500                 Drift detection
> 100K QPS        0.1% + adaptive  ~$300                 Anomaly-triggered full capture
```

---

## Distributed Tracing for ML Pipelines

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DISTRIBUTED TRACE: Recommendation Request                              │
│                                                                          │
│  Trace ID: abc123                                Total: 85ms            │
│                                                                          │
│  ├── API Gateway                                 [2ms]                  │
│  │   ├── Auth check                             [1ms]                  │
│  │   └── Rate limit check                       [1ms]                  │
│  │                                                                       │
│  ├── Feature Service                             [25ms]                 │
│  │   ├── User features (Redis)                  [3ms]                  │
│  │   ├── Item features (Redis)                  [4ms]                  │
│  │   ├── Real-time features (compute)           [15ms]  ← BOTTLENECK  │
│  │   └── Feature assembly                       [3ms]                  │
│  │                                                                       │
│  ├── Candidate Generation                        [20ms]                 │
│  │   ├── ANN lookup (Milvus)                    [12ms]                 │
│  │   └── Business rules filter                  [8ms]                  │
│  │                                                                       │
│  ├── Ranking Model                               [30ms]                 │
│  │   ├── Model inference (GPU)                  [18ms]                 │
│  │   ├── Post-processing                        [7ms]                  │
│  │   └── Diversity re-ranking                   [5ms]                  │
│  │                                                                       │
│  └── Response serialization                      [3ms]                  │
│                                                                          │
│  Tags: model_version=v2.1, experiment=control, user_segment=power      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ML MONITORING ARCHITECTURE                                                 │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │  Model Server   │  │  Feature Store  │  │  Training       │           │
│  │  (predictions)  │  │  (features)     │  │  Pipeline       │           │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘           │
│           │                     │                     │                     │
│           ▼                     ▼                     ▼                     │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  Collection Layer                                             │         │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │         │
│  │  │Prometheus│  │  Kafka   │  │ OpenTel  │                  │         │
│  │  │(metrics) │  │(events)  │  │(traces)  │                  │         │
│  │  └──────────┘  └──────────┘  └──────────┘                  │         │
│  └──────────────────────────────────────────────────────────────┘         │
│           │                     │                     │                     │
│           ▼                     ▼                     ▼                     │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  Processing Layer                                             │         │
│  │  ┌───────────────────┐  ┌────────────────────────────┐     │         │
│  │  │  Drift Detector   │  │  Performance Calculator    │     │         │
│  │  │  (Flink/custom)   │  │  (joins predictions+labels)│     │         │
│  │  └───────────────────┘  └────────────────────────────┘     │         │
│  └──────────────────────────────────────────────────────────────┘         │
│           │                     │                                           │
│           ▼                     ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  Storage & Visualization                                      │         │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │         │
│  │  │ InfluxDB │  │  Grafana │  │PagerDuty │                  │         │
│  │  │(time-series)│(dashboards)│ │(alerts)  │                  │         │
│  │  └──────────┘  └──────────┘  └──────────┘                  │         │
│  └──────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  Tools: Evidently AI, WhyLabs, Arize, Fiddler, NannyML                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Model Fairness & Bias Monitoring

### Fairness Metrics

| Metric | Definition | When to Use |
|--------|-----------|-------------|
| Demographic Parity | P(Ŷ=1\|A=0) = P(Ŷ=1\|A=1) | Equal positive rates across groups |
| Equal Opportunity | P(Ŷ=1\|Y=1,A=0) = P(Ŷ=1\|Y=1,A=1) | Equal TPR across groups |
| Equalized Odds | Equal TPR and FPR across groups | Strongest fairness guarantee |
| Calibration | P(Y=1\|Ŷ=p) = p for all groups | Probability estimates are accurate |
| Predictive Parity | PPV equal across groups | Equal precision |

### Fairness Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  FAIRNESS MONITORING                                             │
│                                                                   │
│  Model: loan_approval_v3                                        │
│  Protected Attributes: gender, race, age_group                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Approval Rate by Gender                                 │   │
│  │  Male:   ████████████████████ 62%                       │   │
│  │  Female: ████████████████░░░░ 58%                       │   │
│  │  Ratio: 0.94 (threshold: >0.80) ✓ PASS                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Equal Opportunity (TPR) by Race                         │   │
│  │  Group A: 0.85                                           │   │
│  │  Group B: 0.82                                           │   │
│  │  Group C: 0.71  ← WARNING (>10% gap)                   │   │
│  │  Ratio (min/max): 0.84 (threshold: >0.80) ⚠️  MONITOR  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Trend (last 30 days):                                          │
│  Fairness score: 0.91 → 0.88 → 0.84 → 0.82 ← degrading      │
│  Action: Investigation triggered, retraining with bias mitigation│
└─────────────────────────────────────────────────────────────────┘
```

---

## Explainability in Production

### SHAP at Scale

```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION EXPLAINABILITY ARCHITECTURE                          │
│                                                                   │
│  Option 1: Real-time SHAP (expensive)                           │
│  Request → Model Server → SHAP computation → Response + reasons │
│  Latency penalty: +50-500ms per request                         │
│  Use for: High-stakes decisions (loan approval, medical)        │
│                                                                   │
│  Option 2: Async SHAP (practical)                               │
│  Request → Model Server → Response (fast)                       │
│       └──── Async queue → SHAP Worker → Store explanations      │
│  User can request explanation later                             │
│  Use for: Most production systems                               │
│                                                                   │
│  Option 3: Pre-computed approximations                          │
│  - Store global feature importance (updated daily)             │
│  - Use LIME for local explanations (faster than SHAP)          │
│  - Template-based explanations for common patterns             │
│  Use for: Consumer-facing explanations                          │
│                                                                   │
│  Option 4: Surrogate Model                                      │
│  - Train interpretable model (decision tree) to mimic complex  │
│  - Serve explanations from surrogate                           │
│  - Update surrogate weekly                                     │
│  Use for: Regulatory compliance                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Incident Response for ML Systems

### ML Incident Runbook

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ML INCIDENT RESPONSE PLAYBOOK                                          │
│                                                                          │
│  1. DETECT (automated)                                                  │
│     Alert fires → On-call notified                                     │
│                                                                          │
│  2. TRIAGE (5 min)                                                      │
│     ├── Is it infrastructure? (check latency, errors, GPU)            │
│     ├── Is it data? (check feature freshness, null rates)             │
│     ├── Is it model? (check prediction distribution)                  │
│     └── Is it upstream? (check data source health)                    │
│                                                                          │
│  3. MITIGATE (15 min)                                                   │
│     ├── Infra issue → Scale up / restart                              │
│     ├── Data issue → Switch to cached features / fallback model       │
│     ├── Model issue → Rollback to previous version                    │
│     └── Upstream → Activate stale-data mode                           │
│                                                                          │
│  4. RESOLVE (hours-days)                                                │
│     ├── Root cause analysis                                            │
│     ├── Fix and validate                                               │
│     ├── Deploy fix                                                     │
│     └── Verify metrics recovered                                       │
│                                                                          │
│  5. POST-MORTEM                                                         │
│     ├── Timeline of events                                             │
│     ├── Impact quantification (users affected, revenue impact)        │
│     ├── Root cause                                                     │
│     ├── What monitoring missed                                         │
│     └── Action items to prevent recurrence                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Real-World Case Studies

### Case Study: Zillow's Zestimate Failure (2021)
- **What happened**: Home price prediction model over-predicted during market shift
- **Impact**: $500M+ loss, 25% workforce layoff
- **Root cause**: Concept drift — COVID changed housing market dynamics; model trained on historical data couldn't adapt to unprecedented demand/price shifts
- **Monitoring gap**: Delayed ground truth (home actually sells months later)
- **Learning**: For high-stakes predictions with delayed labels, monitor proxy signals aggressively and maintain conservative confidence intervals

### Case Study: Amazon Recruiting Tool Bias (2018)
- **What happened**: Resume screening model penalized female candidates
- **Root cause**: Trained on 10 years of historical hiring data (predominantly male hires in tech)
- **Monitoring gap**: No fairness monitoring; model was in production for years before detection
- **Learning**: Fairness monitoring must be a first-class concern, not an afterthought

### Production Incident: Feature Store Staleness
- **Symptom**: Fraud model precision dropped 30% overnight
- **Root cause**: Redis (online feature store) ran out of memory, stopped accepting writes. Features were stale (24h old) but no staleness alert existed
- **Fix**: Added feature freshness monitoring, TTL enforcement, fallback to real-time computation
- **Learning**: Monitor feature freshness, not just feature existence

---

## Interview Questions

1. **Design a monitoring system for 100 ML models in production**
   - Focus: Centralized vs per-model, alerting hierarchy, drift detection at scale

2. **How do you detect concept drift when labels arrive 30 days late?**
   - Focus: Proxy metrics, prediction distribution monitoring, rolling accuracy

3. **Design an alerting system that minimizes false positives while catching real issues**
   - Focus: Multi-signal correlation, adaptive thresholds, alert fatigue management

4. **How would you implement explainability for a model serving 50K QPS?**
   - Focus: Async computation, caching, pre-computed explanations, sampling

5. **Your model's accuracy dropped 10% overnight. Walk through your debugging process.**
   - Focus: Systematic approach — infra → data → features → model → upstream

---

## Production War Stories

Real-world incidents related to ML observability and monitoring. These stories show why monitoring ML systems requires fundamentally different approaches than traditional software.

---

### War Story 9: The Data Drift That Broke Everything

**Company:** Multi-product financial services company

**What Happened:**
In March 2020, COVID-19 changed user behavior overnight. Every ML model in the company degraded simultaneously:
- Demand forecasting: predicted normal patterns, actual demand was 5x for some categories, 0 for others
- Credit scoring: historical risk factors became meaningless (employed people suddenly defaulting)
- Recommendation engine: user interests shifted entirely (travel → home fitness)
- Pricing model: supply/demand relationships inverted

**Root Cause Analysis:**
- All models were trained on 2-3 years of historical data
- No concept of "regime change" or distribution shift detection
- Population Stability Index (PSI) wasn't monitored
- No rapid retraining capability — retraining took 2 weeks minimum
- Models assumed stationarity (past ≈ future)

**How It Was Detected:**
- Business metrics collapsed across all product lines simultaneously
- Manual escalation from product teams
- PSI analysis (done retroactively) showed values > 0.5 on most features (catastrophic drift)

**How It Was Fixed:**
1. Immediate: Switched to rule-based systems and human decision-making for critical paths
2. Short-term:
   - Emergency retraining with last 2 weeks of data only
   - Higher weight on recent data in training
   - Daily PSI monitoring with alerts at PSI > 0.1 (warning) and > 0.25 (critical)
3. Long-term:
   - Rapid retraining pipeline: can retrain and deploy any model in < 4 hours
   - Drift detection on all input features (KL divergence, PSI, Wasserstein distance)
   - Concept drift detection on predictions vs outcomes
   - "Break glass" procedures: documented fallbacks for every ML service
   - Ensemble models mixing recent and historical data with adaptive weighting

**Key Takeaway:**
External events can invalidate all your models simultaneously. Have a rapid retraining capability and documented fallback procedures for every ML-powered feature.

**Prevention Checklist:**
- [ ] PSI/KL divergence monitoring on all input features
- [ ] Concept drift detection (prediction vs outcome correlation)
- [ ] Rapid retraining pipeline (target: < 4 hours from trigger to deployment)
- [ ] Documented fallback for every ML service (rule-based, human, cached)
- [ ] Regime change detection (sudden shifts vs gradual drift)
- [ ] Adaptive training windows (weight recent data more heavily)
- [ ] Regular disaster recovery drills for ML systems

---

### War Story 10: The Label Leak in Production

**Company:** Healthcare analytics company

**What Happened:**
A patient readmission prediction model achieved 99.5% accuracy in training — suspiciously high for a problem that typically tops out at 75-80%. It was deployed to production where it appeared to work well initially. After 3 months, accuracy dropped to 55% and clinicians lost trust in the system.

**Root Cause Analysis:**
- A feature `discharge_summary_update_timestamp` was highly correlated with readmission
- Patients who were readmitted had their discharge summaries updated (to add readmission notes)
- This feature effectively leaked the label — it was computed AFTER the outcome occurred
- In production, this feature didn't have the "future" information, so the model lost its most predictive signal
- The initial "good" performance was because some historical backfill data still had the leak

**How It Was Detected:**
- Feature importance monitoring showed one feature had 95% importance (red flag)
- Model accuracy degraded as backfilled data aged out of the serving window
- A data scientist investigated why one feature dominated

**How It Was Fixed:**
1. Immediate: Removed the leaked feature, retrained
2. Short-term:
   - Feature importance monitoring: alert if any single feature > 50% importance
   - Temporal validation: strict time-based train/test splits (no future data leakage)
   - Feature auditing: every feature reviewed for temporal validity
3. Long-term:
   - Automated "point-in-time" feature computation (features only use data available at prediction time)
   - Feature lineage tracking: know exactly when each feature value was computed
   - Regular feature importance reviews (monthly)
   - "Suspiciously good" model detection: alert if accuracy exceeds domain benchmarks

**Key Takeaway:**
Monitor feature importance over time. Sudden changes or single-feature dominance indicate problems. If your model is too good to be true, it probably is.

**Prevention Checklist:**
- [ ] Feature importance monitoring with alerts on dominance/shifts
- [ ] Strict temporal validation (point-in-time correctness)
- [ ] Feature audit for every new feature (can it be computed at prediction time?)
- [ ] Feature lineage and timestamp tracking
- [ ] Domain-expert review of suspiciously high accuracy
- [ ] Automated checks for target leakage in training pipeline

---

### War Story 11: The Monitoring System That Cried Wolf

**Company:** Ad-tech platform

**What Happened:**
The ML platform team set up comprehensive monitoring — 200+ metrics with alerts. Within a month, the on-call engineer received ~500 alerts per day. The team started ignoring alerts entirely ("alert fatigue"). When a real incident occurred (bid prediction model serving stale predictions for 6 hours), nobody noticed because the alert was buried among hundreds of false positives. Cost: ~$2M in lost ad revenue.

**Root Cause Analysis:**
- Static thresholds on naturally noisy metrics (e.g., alerting on prediction latency > 50ms when normal variance was 30-80ms)
- No alert severity levels (everything was "critical")
- Correlated metrics firing separate alerts (one issue → 50 alerts)
- No regular alert tuning or review process
- Metrics that should have been dashboards were configured as alerts

**How It Was Detected:**
- The real incident was caught by a customer complaint 6 hours after it started
- Post-mortem revealed the alert fired but was ignored among 47 other alerts that hour

**How It Was Fixed:**
1. Immediate: Alert audit — disabled 80% of alerts (moved to dashboards)
2. Short-term:
   - Dynamic thresholds: rolling mean ± 3 standard deviations (seasonal adjustments)
   - Three severity levels: P1 (page immediately), P2 (Slack, respond within 1 hour), P3 (daily review)
   - Alert grouping: correlated alerts collapse into one notification
3. Long-term:
   - Weekly alert review: prune any alert that fired > 5 times without action
   - Alert SLO: < 5 P1 alerts per week, < 95% of alerts should be actionable
   - Anomaly detection instead of static thresholds (Isolation Forest on metric streams)
   - On-call handoff includes alert health report

**Key Takeaway:**
Alert fatigue is as dangerous as no alerts. Every alert must be actionable. If you're ignoring alerts, your monitoring is broken.

**Prevention Checklist:**
- [ ] Dynamic thresholds (not static) for all noisy metrics
- [ ] Severity levels with clear response expectations
- [ ] Alert grouping for correlated metrics
- [ ] Weekly alert review: prune noisy alerts
- [ ] Alert SLO: track actionability rate (target > 90%)
- [ ] Distinguish alerts (action needed) from dashboards (informational)
- [ ] On-call feedback loop: every ignored alert is reviewed

---

### War Story 12: The Adversarial Attack in Production

**Company:** Payment fraud detection platform

**What Happened:**
The fraud detection model's precision dropped from 92% to 40% over 6 weeks on a specific transaction pattern — small-amount gift card purchases. Fraudsters were successfully bypassing the model with a specific pattern of transactions that exploited the decision boundary.

**Root Cause Analysis:**
- Fraudsters discovered that transactions under $25 for gift cards from specific merchants were consistently approved
- They likely probed the API with thousands of small test transactions to map the decision boundary
- The model had a sharp boundary: amount < $25.37 AND merchant_category = "gift_cards" → almost always approved
- No rate limiting on prediction API
- No monitoring for systematic probing patterns
- Single model (no ensemble diversity) made the boundary easy to find

**How It Was Detected:**
- Chargeback rate for gift card transactions spiked 800%
- Manual investigation revealed a pattern of small, similar transactions from new accounts
- Forensic analysis showed probe-like behavior (systematic amount variations) in historical logs

**How It Was Fixed:**
1. Immediate: Added rule-based blocks for the specific pattern
2. Short-term:
   - Rate limiting on prediction API (max 10 predictions/minute per user)
   - Input perturbation: add small random noise to feature values before prediction
   - Monitoring for systematic probing (detect sweep patterns)
3. Long-term:
   - Ensemble of diverse models (tree-based + neural + rule-based) — harder to reverse-engineer all simultaneously
   - Model rotation: swap models periodically so boundaries change
   - Adversarial training: include adversarial examples in training data
   - Prediction API returns coarser outputs (approve/deny only, no confidence scores)
   - Honeypot features: decoy signals that identify probing attempts

**Key Takeaway:**
Models in adversarial environments need defense in depth. Assume attackers will probe your model. Rate limit, diversify, rotate, and never expose more information than necessary.

**Prevention Checklist:**
- [ ] Rate limiting on all prediction APIs
- [ ] Never expose raw confidence scores to untrusted users
- [ ] Ensemble of diverse model types (harder to attack all at once)
- [ ] Model rotation on a schedule
- [ ] Adversarial probing detection (monitor for systematic exploration)
- [ ] Adversarial training (include attack patterns in training data)
- [ ] Red team exercises: try to attack your own models quarterly
- [ ] Decision boundary smoothing (avoid sharp, exploitable thresholds)
