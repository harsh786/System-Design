# Production ML Architecture & MLOps

## Overview

Production ML systems are fundamentally different from research/notebook ML. A model is typically <5% of a production ML system — the remaining 95% is infrastructure, data pipelines, monitoring, serving, and operational tooling.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION ML SYSTEM ANATOMY                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │   Data   │  │ Feature  │  │  Model   │  │  Model   │  │  Model  │ │
│  │Collection│─▶│Engineering│─▶│ Training │─▶│Validation│─▶│ Serving │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│       │              │              │              │              │     │
│       ▼              ▼              ▼              ▼              ▼     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    MONITORING & OBSERVABILITY                     │  │
│  │  Data Drift │ Model Perf │ Infra Metrics │ Business KPIs        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│       │              │              │              │              │     │
│       ▼              ▼              ▼              ▼              ▼     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    INFRASTRUCTURE LAYER                           │  │
│  │  Compute │ Storage │ Networking │ Security │ Cost Management     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## ML System Maturity Levels

| Level | Description | Characteristics | Team Size |
|-------|-------------|-----------------|-----------|
| 0 - Manual | Jupyter notebooks, manual deployment | No automation, no monitoring | 1-2 DS |
| 1 - Pipeline | Automated training pipeline | Basic CI/CD, scheduled retraining | 3-5 |
| 2 - Managed | Feature store, model registry | Experiment tracking, A/B testing | 5-10 |
| 3 - Automated | Full MLOps, auto-retraining | Drift detection, auto-rollback | 10-20 |
| 4 - Autonomous | Self-healing, self-optimizing | AutoML, automated feature eng. | 20+ |

## Architecture Patterns

### Pattern 1: Train-Once-Serve-Forever (Level 0-1)
```
Data → Train Model → Deploy → Serve (until manually retrained)
```
- Suitable for: stable domains, infrequent data changes
- Risk: silent model degradation

### Pattern 2: Periodic Retraining (Level 2)
```
Data → Scheduled Pipeline → Validate → Deploy → Serve
                                ↓
                         Monitor → Trigger Retrain
```
- Suitable for: moderate drift, daily/weekly patterns
- Common in: e-commerce, content recommendation

### Pattern 3: Continuous Training (Level 3-4)
```
Streaming Data → Feature Store → Online Training → Shadow Deploy → Promote
                      ↓                                    ↓
              Offline Training → Validate → Canary Deploy → Full Deploy
                      ↓
              Drift Detection → Auto-trigger retraining
```
- Suitable for: high-velocity domains, real-time personalization
- Common in: ad-tech, fraud detection, trading

## Key Challenges in Production ML

1. **Training-Serving Skew**: Features computed differently in training vs serving
2. **Data Distribution Shift**: Production data differs from training data
3. **Feedback Loops**: Model predictions influence future training data
4. **Reproducibility**: Cannot reproduce results due to data/code/env changes
5. **Technical Debt**: ML systems accumulate debt faster than traditional software
6. **Testing**: Traditional testing insufficient; need data tests, model tests, infra tests
7. **Compliance**: Model explainability, fairness, audit trails

## Production ML vs Traditional Software

| Dimension | Traditional Software | Production ML |
|-----------|---------------------|---------------|
| Testing | Unit/integration tests | + Data tests, model tests, fairness tests |
| Versioning | Code only | Code + Data + Model + Config |
| Monitoring | Errors, latency | + Drift, performance degradation |
| Deployment | Blue/green, canary | + Shadow mode, A/B, multi-armed bandit |
| Rollback | Revert code | Revert model + potentially retrain |
| Debugging | Stack traces | + Data issues, distribution shifts |
| Dependencies | Libraries, services | + Training data, feature pipelines |

## Cost Reality Check

| Component | % of Total ML Cost | Notes |
|-----------|-------------------|-------|
| Data Engineering | 40-50% | Collection, cleaning, labeling |
| Infrastructure | 20-30% | GPU compute, storage, serving |
| Model Development | 10-15% | Research, experimentation |
| Operations | 10-20% | Monitoring, incident response |

## Directory Structure

```
05-Production-Architecture/
├── README.md (this file)
├── 01-MLOps/
│   └── README.md - MLOps maturity, CI/CD, experiment tracking
├── 02-Model-Serving-and-Scaling/
│   └── README.md - Serving patterns, scaling, deployment strategies
├── 03-Observability-and-Monitoring/
│   └── README.md - Drift detection, alerting, monitoring
├── 04-System-Design-Patterns/
│   └── README.md - Architecture patterns for ML systems
└── 05-Data-Infrastructure/
    └── README.md - Data lakes, streaming, vector DBs
```

## Interview Focus Areas

For Staff/Principal level interviews, expect questions on:
- Designing end-to-end ML platforms
- Handling training-serving skew at scale
- Cost optimization for GPU workloads
- Multi-region ML deployment
- Compliance and governance for ML systems
- Incident response for model failures
- Building vs buying ML infrastructure decisions
