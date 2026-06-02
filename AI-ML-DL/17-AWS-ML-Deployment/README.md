# AWS ML Deployment at Scale

## The AWS ML Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER / APPLICATION                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │ API Gateway │  │     ALB     │  │  CloudFront │
     └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
            │                │                │
            ▼                ▼                ▼
   ┌────────────┐   ┌────────────┐   ┌────────────────┐
   │   Lambda   │   │  EKS/ECS   │   │   SageMaker    │
   │ (< 250MB)  │   │ (Custom)   │   │   Endpoints    │
   └────────────┘   └────────────┘   └────────────────┘
            │                │                │
            └────────────────┼────────────────┘
                             ▼
              ┌──────────────────────────┐
              │   Model Artifacts (S3)   │
              └──────────────────────────┘
                             ▲
                             │
              ┌──────────────────────────┐
              │   SageMaker Training     │
              │   (On-demand / Spot)     │
              └──────────────────────────┘
                             ▲
                             │
              ┌──────────────────────────┐
              │   Data (S3 / Feature     │
              │   Store / Glue)          │
              └──────────────────────────┘
```

## When to Use What

| Criteria | SageMaker Endpoint | EKS | Lambda | EC2 |
|----------|-------------------|-----|--------|-----|
| **Best for** | Standard ML serving | Complex/custom serving | Light models, bursty traffic | Full control, research |
| **Model size** | Any | Any | < 250MB | Any |
| **Latency** | ~50-200ms | ~10-100ms | 100ms-10s (cold start) | ~10-100ms |
| **Scaling** | Auto (managed) | HPA (manual config) | Auto (instant) | Manual/ASG |
| **GPU support** | Yes | Yes | No | Yes |
| **Cost (low traffic)** | $$ (always-on) | $$$ (cluster overhead) | $ (pay per use) | $$ |
| **Cost (high traffic)** | $$ | $ (most efficient) | $$$ (per-request adds up) | $ |
| **Ops burden** | Low | High | Very Low | Very High |
| **Flexibility** | Medium | Very High | Low | Very High |

## Decision Flowchart

```
START: Deploy an ML model
│
├─ Is the model < 250MB and latency-tolerant?
│  ├─ YES → Is traffic bursty/infrequent (< 1000 req/day)?
│  │         ├─ YES → Lambda + API Gateway
│  │         └─ NO  → SageMaker Serverless Inference
│  └─ NO ↓
│
├─ Do you need custom serving logic (ensembles, preprocessing, multi-framework)?
│  ├─ YES → EKS with Triton/KServe
│  └─ NO ↓
│
├─ Do you have 10+ models to serve?
│  ├─ YES → SageMaker Multi-Model Endpoint
│  └─ NO ↓
│
├─ Is request processing > 60s?
│  ├─ YES → SageMaker Async Inference
│  └─ NO ↓
│
└─ Default → SageMaker Real-time Endpoint
```

## Cost Comparison (us-east-1, approximate)

| Deployment | Monthly Cost (1M requests/day, 100ms avg) |
|------------|------------------------------------------|
| SageMaker Real-time (ml.g4dn.xlarge) | ~$535 |
| SageMaker Serverless (3GB, 200ms) | ~$450 |
| EKS (g4dn.xlarge + cluster) | ~$610 |
| Lambda (3GB, 200ms) | ~$1,200 |
| EC2 (g4dn.xlarge, reserved 1yr) | ~$340 |

*Lambda becomes expensive at high sustained traffic. Best for < 100K requests/day.*

## Prerequisites

- AWS Account with SageMaker, EKS, Lambda permissions
- AWS CLI v2 configured (`aws configure`)
- Python 3.9+ with `boto3`, `sagemaker` SDK
- Docker (for container-based deployments)
- CDK or Terraform (for IaC)
- Basic ML model ready (PyTorch, TensorFlow, or sklearn)

## Section Contents

| # | Topic | Key Takeaway |
|---|-------|--------------|
| 01 | SageMaker Training & Endpoints | Managed training + deployment, least ops burden |
| 02 | Container Deployment (EKS/ECS) | Full control, custom serving, GPU scheduling |
| 03 | Serverless ML (Lambda) | Pay-per-use, best for light/bursty workloads |
| 04 | CI/CD Pipeline | Automated train → evaluate → deploy → monitor |
| 05 | Observability (CloudWatch) | Model monitoring, drift detection, alerting |
| 06 | Cost Optimization | Spot training, right-sizing, multi-model endpoints |
| 07 | Full Production Workflow | End-to-end worked example, laptop → production |

## Key Principles

1. **Start with SageMaker** — Move to EKS only when you need custom control
2. **Always use spot for training** — 70% savings, checkpoints handle interruptions
3. **Monitor models, not just infra** — Drift kills models silently
4. **Automate everything** — Manual deployments don't scale
5. **Cost-aware from day one** — ML infra costs grow fast without guardrails
