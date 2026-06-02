# Model Lifecycle & MLOps Decision Workflows

> Staff architect guide: End-to-end model lifecycle management, from problem definition through monitoring, retraining, and retirement.

---

## Diagram 1: Complete Model Lifecycle

```mermaid
flowchart TD
    A[Problem Definition] --> B[Data Collection & Labeling]
    B --> C[EDA & Feasibility Assessment]
    C --> D{Feasible?}
    D -->|No: insufficient data,<br/>no signal, too noisy| E[Redefine Problem<br/>or Acquire More Data]
    E --> A
    D -->|Yes: signal exists,<br/>data sufficient| F[Feature Engineering]
    F --> G[Model Development]
    G --> H[Offline Evaluation]
    H --> I{Meets threshold?}
    I -->|No: below baseline<br/>or business requirement| G
    I -->|Yes: exceeds baseline<br/>+ minimum quality| J[A/B Test in Production]
    J --> K{Wins A/B test?}
    K -->|No: no significant<br/>lift vs control| G
    K -->|Yes: significant<br/>improvement| L[Full Production Deployment]
    L --> M[Monitor & Maintain]
    M --> N{Performance Degraded?}
    N -->|Yes| O[Retrain or Rebuild]
    O --> G
    N -->|No| M
    M --> P{Still Needed?}
    P -->|No: business pivot,<br/>feature deprecated| Q[Retire Model]
    Q --> R[Archive artifacts + redirect traffic]

    style A fill:#25d,color:#fff
    style L fill:#2d5,color:#fff
    style Q fill:#d52,color:#fff
```

### Why Each Step Exists (Skip at Your Peril)

| Step | WHY it exists | What goes wrong if skipped |
|------|--------------|--------------------------|
| **Problem Definition** | Ensures ML is the right solution | Build model for wrong problem, waste months |
| **Data Collection** | Garbage in = garbage out | Model learns noise, not signal |
| **EDA & Feasibility** | Validates signal exists in data | Spend weeks training on random noise |
| **Feature Engineering** | Raw data rarely useful directly | Weak model, miss obvious patterns |
| **Offline Evaluation** | Cheap to test before production | Deploy bad model, damage user trust |
| **A/B Test** | Offline metrics ≠ real-world impact | Model "works" offline but hurts business metrics |
| **Monitoring** | Models degrade silently over time | Serving stale/wrong predictions for months |
| **Retirement** | Dead models accumulate tech debt | Paying infra costs for unused models |

---

## Diagram 2: MLOps Maturity Levels

```mermaid
flowchart LR
    L0[Level 0<br/>Manual ML] --> L1[Level 1<br/>Pipeline Automation]
    L1 --> L2[Level 2<br/>CI/CD for ML]
    L2 --> L3[Level 3<br/>Auto-ML Operations]
    
    L0 --- L0a[Jupyter notebooks]
    L0 --- L0b[Manual deployment via SSH]
    L0 --- L0c[No versioning]
    L0 --- L0d[No monitoring]
    
    L1 --- L1a[Automated training<br/>Airflow/Kubeflow]
    L1 --- L1b[Model registry<br/>MLflow]
    L1 --- L1c[Basic monitoring<br/>accuracy tracking]
    L1 --- L1d[Reproducible runs]
    
    L2 --- L2a[Automated testing<br/>data + model tests]
    L2 --- L2b[Feature store<br/>Feast/Tecton]
    L2 --- L2c[Canary deployments<br/>A/B testing]
    L2 --- L2d[Full observability<br/>Prometheus + Grafana]
    
    L3 --- L3a[Auto-retrain on drift]
    L3 --- L3b[Automated feature<br/>discovery]
    L3 --- L3c[Self-healing pipelines]
    L3 --- L3d[Minimal human<br/>intervention]

    style L0 fill:#d33,color:#fff
    style L1 fill:#d93,color:#fff
    style L2 fill:#2d5,color:#fff
    style L3 fill:#25d,color:#fff
```

### Maturity Level Details

```
LEVEL 0: Manual ML
├── PROBLEMS:
│   ├── "It worked on my machine" - can't reproduce results
│   ├── No audit trail - which model is in production?
│   ├── Manual deployment takes days, error-prone
│   └── Nobody knows when model degrades
├── WHO: Individual data scientists, early startups
└── COST OF STAYING HERE: Models break silently, team can't scale

LEVEL 1: Pipeline Automation
├── IMPROVEMENTS:
│   ├── Reproducible: rerun same pipeline, get same model
│   ├── Versioned: know exactly which model is deployed
│   ├── Scheduled: retraining happens automatically
│   └── Tracked: experiments logged with metrics
├── STILL MISSING: CI/CD, feature stores, proper testing
└── WHO: Growing ML teams (3-5 data scientists)

LEVEL 2: CI/CD for ML
├── IMPROVEMENTS:
│   ├── Production-grade reliability (SLA guarantees)
│   ├── Automated quality gates (bad models can't deploy)
│   ├── Feature consistency (feature store)
│   ├── Safe deployments (canary, rollback)
│   └── Full observability (know exactly what's happening)
├── INVESTMENT: Dedicated ML platform team (2-4 engineers)
└── WHO: Companies where ML is core to product

LEVEL 3: Auto-ML Operations
├── IMPROVEMENTS:
│   ├── Self-healing: pipeline detects and fixes issues
│   ├── Auto-retrain: drift detected → new model deployed
│   ├── Auto-feature: discovers useful new features
│   └── Human role: set guardrails, handle edge cases
├── REALITY CHECK: Very few orgs actually achieve this fully
└── WHO: Google, Meta, Netflix (ML at massive scale)
```

---

## Diagram 3: Model Monitoring & Retraining Triggers

```mermaid
sequenceDiagram
    participant Prod as Production Model
    participant Mon as Monitoring System
    participant Alert as Alert System
    participant Pipeline as Retrain Pipeline
    participant Registry as Model Registry
    participant Gate as Quality Gate
    participant Deploy as Deployment

    Note over Prod,Deploy: === CONTINUOUS MONITORING LOOP ===

    loop Every prediction batch
        Prod->>Mon: Log predictions, features, confidence scores
    end
    
    loop Every hour
        Mon->>Mon: Compute PSI<br/>(Population Stability Index)
        Mon->>Mon: Compute feature drift<br/>(KS test per feature)
        Mon->>Mon: Compute prediction<br/>distribution shift
        Mon->>Mon: Check prediction latency<br/>(p50, p95, p99)
    end
    
    loop Daily (when labels arrive)
        Mon->>Mon: Compute actual accuracy,<br/>precision, recall, AUC
        Mon->>Mon: Compute per-segment<br/>performance
    end

    Note over Mon,Alert: === ALERT TRIGGERS ===
    
    alt PSI > 0.1 (minor drift)
        Mon->>Alert: WARN: Input distribution shifting
        Note over Alert: Action: Log, watch trend,<br/>no immediate action
    end
    
    alt PSI > 0.2 (significant drift)
        Mon->>Alert: ALERT: Significant data drift
        Note over Alert: WHY PSI > 0.2: Input distribution<br/>has materially changed. Model was<br/>trained on different distribution.
        Alert->>Pipeline: Trigger retraining<br/>(if auto-retrain enabled)
    end
    
    alt Accuracy drops > 5% (labels available)
        Mon->>Alert: CRITICAL: Model degradation confirmed
        Note over Alert: WHY: Concept drift confirmed.<br/>Relationship between X and Y<br/>has fundamentally changed.
        Alert->>Pipeline: Trigger URGENT retraining
    end
    
    alt Latency p99 > SLA
        Mon->>Alert: WARN: Serving latency degraded
        Note over Alert: Action: Scale infra or<br/>optimize model (quantize/distill)
    end

    Note over Pipeline,Deploy: === RETRAINING FLOW ===
    
    Pipeline->>Pipeline: Pull recent data<br/>(last N days window)
    Pipeline->>Pipeline: Run feature pipeline<br/>(same code as production)
    Pipeline->>Pipeline: Train new model<br/>(same hyperparams or re-tune)
    Pipeline->>Gate: Submit for evaluation
    
    Gate->>Gate: Evaluate on holdout set
    Gate->>Gate: Evaluate on recent labeled data
    Gate->>Gate: Run bias/fairness checks
    Gate->>Gate: Check latency on sample requests
    Gate->>Gate: Compare vs current production model
    
    alt New model better by > 1% on primary metric
        Gate->>Registry: Register as candidate
        Registry->>Deploy: Canary deploy (5% traffic)
        Note over Deploy: WHY canary: Catch issues that<br/>offline eval misses (edge cases,<br/>integration bugs, real traffic patterns)
        Deploy->>Mon: Monitor canary metrics (1 hour)
        Mon->>Deploy: Canary healthy
        Deploy->>Deploy: Ramp 25% → 50% → 100%
    else New model NOT better
        Gate->>Alert: Retraining unsuccessful
        Note over Alert: Action: Human investigation needed.<br/>Possible causes: label quality,<br/>fundamental concept shift,<br/>feature staleness
    end
```

### Monitoring Metrics Cheat Sheet

| Metric | What it measures | Threshold | Action |
|--------|-----------------|-----------|--------|
| PSI | Input distribution shift | > 0.2 | Retrain |
| KS statistic | Per-feature drift | > 0.1 | Investigate feature |
| Accuracy/AUC | Model correctness | > 5% drop | Urgent retrain |
| Prediction entropy | Model confidence | Increasing trend | Model uncertain on new data |
| Latency p99 | Serving speed | > SLA | Scale or optimize |
| Null feature rate | Data quality | > baseline | Fix upstream pipeline |

---

## Diagram 4: CI/CD Pipeline for ML

```mermaid
flowchart TD
    A[Code Push / PR] --> B[Trigger CI Pipeline]
    
    B --> C[Data Tests]
    B --> D[Unit Tests]
    
    C --> C1[Schema validation]
    C --> C2[Feature range checks]
    C --> C3[Train/test split verification]
    C --> C4[No data leakage check]
    
    C1 --> C1a[WHY: Catch upstream format changes<br/>before they silently corrupt features]
    C2 --> C2a[WHY: Catch upstream bugs that produce<br/>impossible values e.g. negative age]
    C3 --> C3a[WHY: Catch temporal leakage where<br/>future data leaks into training set]
    C4 --> C4a[WHY: Target variable must not<br/>appear in features directly or indirectly]
    
    D --> D1[Feature engineering functions]
    D --> D2[Data transformation logic]
    D --> D3[Model load + inference works]
    D --> D4[Preprocessing pipeline runs]
    
    D1 --> D1a[WHY: Logic correctness -<br/>edge cases handled]
    D2 --> D2a[WHY: Null handling, type casting,<br/>boundary conditions]
    D3 --> D3a[WHY: Serialization format compatible,<br/>dependencies resolved]
    
    C1a --> E[Integration Tests]
    D1a --> E
    
    E --> E1[End-to-end pipeline on sample data]
    E --> E2[Model trains to convergence on tiny dataset]
    E --> E3[Serving endpoint responds correctly]
    E --> E4[Feature store read/write works]
    
    E1 --> E1a[WHY: Full flow works end-to-end,<br/>not just individual pieces]
    E2 --> E2a[WHY: Code runs without crashing,<br/>loss decreases - basic sanity]
    E3 --> E3a[WHY: Deployment actually serves<br/>predictions with correct format]
    
    E --> F[Model Quality Gate]
    
    F --> F1[Metrics > threshold on validation set]
    F --> F2[No regression vs production model]
    F --> F3[Latency < SLA on sample requests]
    F --> F4[Bias/fairness metrics within bounds]
    F --> F5[Model size within deployment limits]
    
    F --> G{All gates pass?}
    G -->|No| H[Block merge + report failures]
    G -->|Yes| I[Merge to main]
    
    I --> J[Deploy Pipeline]
    J --> J1[Build serving container]
    J1 --> J2[Deploy canary - 5% traffic]
    J2 --> J3{Metrics stable<br/>for 1 hour?}
    J3 -->|No| J4[Auto-rollback + alert]
    J3 -->|Yes| J5[Ramp to 25%]
    J5 --> J6[Ramp to 50%]
    J6 --> J7[Ramp to 100%]

    style H fill:#d33,color:#fff
    style J4 fill:#d33,color:#fff
    style J7 fill:#2d5,color:#fff
```

### What to Test at Each Level

```
UNIT TESTS (fast, run on every commit):
├── Feature engineering: test_log_transform_handles_zero()
├── Preprocessing: test_null_imputation_strategy()
├── Encoding: test_category_encoding_unknown_values()
└── Runtime: < 30 seconds total

INTEGRATION TESTS (medium, run on PR):
├── Pipeline: full training pipeline on 100 rows
├── Serving: load model, send request, get response
├── Feature store: write features, read back correctly
└── Runtime: < 10 minutes

MODEL QUALITY (slow, run before deploy):
├── Full evaluation on validation set
├── Comparison vs production baseline
├── Stress test: 1000 concurrent requests
└── Runtime: < 1 hour
```

---

## Diagram 5: Training-Serving Skew Prevention

```mermaid
flowchart LR
    A[Training-Serving Skew<br/>THE #1 SILENT KILLER] --> B[CAUSES]
    A --> C[FIXES]
    A --> D[DETECTION]
    
    B --> B1[Different code paths<br/>Python training vs Java serving]
    B --> B2[Different library versions<br/>sklearn 1.0 vs 1.2 changes output]
    B --> B3[Data leakage in training<br/>Used future information]
    B --> B4[Different preprocessing<br/>Fitted scaler on ALL data vs train only]
    B --> B5[Stale features in serving<br/>Cached from yesterday]
    B --> B6[Different feature order<br/>Columns shuffled between train/serve]
    
    C --> C1[Feature Store<br/>Single source of truth for features]
    C --> C2[Containerize everything<br/>Pin all library versions]
    C --> C3[Point-in-time joins<br/>Only use features available at prediction time]
    C --> C4[Save fitted transformers<br/>Serialize and reuse in serving]
    C --> C5[Feature freshness SLA<br/>Monitor + alert on stale features]
    C --> C6[Feature contract<br/>Schema defines expected order + types]
    
    D --> D1[Log serving features<br/>Compare distribution to training]
    D --> D2[Shadow mode<br/>Run new model alongside old]
    D --> D3[Reconstruction test<br/>Rebuild training features from<br/>serving logs - should match]
    D --> D4[Integration test<br/>Send known input, assert<br/>exact same output as offline]

    B1 -.->|FIX| C1
    B2 -.->|FIX| C2
    B3 -.->|FIX| C3
    B4 -.->|FIX| C4
    B5 -.->|FIX| C5
    B6 -.->|FIX| C6

    style A fill:#d33,color:#fff
    style C1 fill:#2d5,color:#fff
    style C2 fill:#2d5,color:#fff
    style C3 fill:#2d5,color:#fff
```

### Real-World Skew Examples

```
EXAMPLE 1: Feature computed differently
  Training: user_age = current_date - birth_date (computed at training time)
  Serving: user_age = cached value from user profile (updated monthly)
  RESULT: Model sees "stale" ages, predictions slightly off

EXAMPLE 2: Preprocessing difference
  Training: StandardScaler().fit_transform(all_data)  ← WRONG (uses test info)
  Serving: StandardScaler loaded, but fitted on different data
  RESULT: Features have different scale, model produces garbage

EXAMPLE 3: Data leakage
  Training: feature = "average purchase amount" (includes FUTURE purchases)
  Serving: feature = "average purchase amount" (only PAST purchases)
  RESULT: Model looks great offline (95% AUC), terrible online (60% AUC)

PREVENTION CHECKLIST:
□ Single feature computation code path (feature store)
□ All transformers serialized with model artifact
□ Point-in-time correctness validated
□ Integration test: same input → same output (train vs serve)
□ Feature distribution monitoring (train vs serve distributions)
```

---

## Diagram 6: When to Retrain vs Rebuild

```mermaid
flowchart TD
    A[Performance Dropped] --> B{What changed?}
    
    B -->|Input distribution<br/>DATA DRIFT| C{How severe?}
    C -->|Mild: PSI 0.1-0.2| C1[Retrain on recent data]
    C -->|Major: PSI > 0.25| C2[Rebuild features + model]
    C1 --> C1a[WHY: Same features still relevant,<br/>model just needs to see new distribution]
    C2 --> C2a[WHY: Old features may not capture<br/>new patterns in shifted data]
    
    B -->|Target relationship changed<br/>CONCEPT DRIFT| D{How sudden?}
    D -->|Gradual| D1[Scheduled retraining<br/>weekly or monthly]
    D -->|Sudden| D2[Emergency retrain +<br/>investigate root cause]
    D1 --> D1a[WHY: Continuous adaptation<br/>keeps model current]
    D2 --> D2a[WHY: Something fundamental changed<br/>e.g. new competitor, policy change, COVID]
    
    B -->|New business requirements| E{What's needed?}
    E -->|New input signals| E1[Add features → retrain]
    E -->|Different objective| E2[Rebuild with new loss function]
    E -->|Different latency SLA| E3[Architecture change<br/>distill or quantize]
    E -->|New fairness constraints| E4[Add constraints → retrain<br/>or rebuild if infeasible]
    
    B -->|Nothing obvious changed<br/>but accuracy dropping| F[Label Quality Issue]
    F --> F1[Audit recent labels]
    F1 --> F2{Labels correct?}
    F2 -->|No: labelers confused,<br/>guidelines changed| F3[Fix labels → retrain]
    F2 -->|Yes: labels fine| F4[Deep investigation:<br/>hidden feature staleness,<br/>serving bug, skew]

    %% Effort indicators
    C1 -.->|Effort: Low<br/>1-2 days| EFFORT
    C2 -.->|Effort: High<br/>1-2 weeks| EFFORT
    D1 -.->|Effort: Automated<br/>0 days| EFFORT
    E2 -.->|Effort: High<br/>2-4 weeks| EFFORT
    E3 -.->|Effort: Medium<br/>1 week| EFFORT

    style C1 fill:#2d5,color:#fff
    style D1 fill:#2d5,color:#fff
    style C2 fill:#d93,color:#fff
    style D2 fill:#d33,color:#fff
    style E2 fill:#d93,color:#fff
```

### Decision Quick Reference

| Situation | Action | Effort | Timeline |
|-----------|--------|--------|----------|
| Mild data drift | Retrain same model | Low | 1-2 days |
| Major data drift | Rebuild features + model | High | 1-2 weeks |
| Gradual concept drift | Automate weekly retraining | Setup once | Ongoing |
| Sudden concept drift | Emergency retrain + RCA | Medium | 2-3 days |
| Need new features | Add features, retrain | Medium | 3-5 days |
| Need new objective | Redesign model | High | 2-4 weeks |
| Need lower latency | Distill/quantize | Medium | 1 week |
| Label quality degraded | Audit + fix + retrain | Medium | 1 week |

### Retraining Strategy Patterns

```
PATTERN 1: Sliding Window
  Train on last N days of data
  WHY: Recent data most relevant, old data may hurt
  WHEN: Fast-changing domains (ads, recommendations)

PATTERN 2: Growing Window  
  Train on ALL historical data
  WHY: More data = better generalization
  WHEN: Slow-changing domains (credit scoring, medical)

PATTERN 3: Weighted Window
  Train on all data, but weight recent data higher
  WHY: Best of both - history for rare events, recency for trends
  WHEN: Mixed domains (fraud - need rare historical fraud + recent patterns)

PATTERN 4: Trigger-based
  Retrain only when drift detected (not on schedule)
  WHY: Avoid unnecessary retraining costs
  WHEN: Stable domains where drift is rare but impactful
```

---

## Summary: MLOps Decision Framework

1. **Lifecycle** → Every step exists for a reason; skipping any creates silent failures
2. **Maturity** → Match investment to business criticality; not everyone needs Level 3
3. **Monitoring** → PSI for drift, accuracy for degradation, latency for SLA
4. **CI/CD** → Test data, code, and model quality; automate deployment with rollback
5. **Skew** → Use feature stores + containerization; the #1 cause of "works offline, fails online"
6. **Retrain vs Rebuild** → Severity of change determines response; automate the common case
