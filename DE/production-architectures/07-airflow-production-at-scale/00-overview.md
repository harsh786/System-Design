# Apache Airflow Production at Scale - Overview

## Context: Why This Exists

This folder explains **every Airflow concept** through **10 real production problems** that companies
like Stripe, Uber, Airbnb, Netflix, and large banks face daily when processing **billions of transactions**.

Instead of learning Airflow in isolation, each problem teaches specific concepts in context.

---

## The 10 Real Production Problems

| # | Problem | Company Scale | Airflow Concepts Covered |
|---|---------|--------------|--------------------------|
| 1 | Payment Reconciliation Pipeline | Stripe-scale: 2B txns/day | DAG basics, scheduling, retries, execution_date, idempotency |
| 2 | Multi-Region Data Warehouse Load | Uber-scale: 500TB+ | Cross-DAG deps, Datasets, ExternalTaskSensor, TriggerDagRun |
| 3 | Real-Time Fraud Batch Aggregation | Banking: 10B events/day | Dynamic DAGs, TaskFlow API, XCom, task mapping |
| 4 | SLA-Critical Regulatory Reporting | Finance: SOX/Basel compliance | SLA monitoring, callbacks, on_failure, timeout, priority |
| 5 | E-Commerce Inventory Sync | Amazon-scale: 350M products | Pools, Connections, Hooks, rate limiting, resource management |
| 6 | ML Model Training Pipeline | Netflix-scale: 1000s models | KubernetesExecutor, pod_override, GPU scheduling, resources |
| 7 | Customer Data Platform Backfill | CDP: 5 years history, PBs | Catchup, backfill CLI, idempotency, partition-level replay |
| 8 | Event-Driven Order Processing | E-commerce: 1M orders/hour | Deferrable operators, Triggerer, async, event-driven DAGs |
| 9 | Data Quality Validation Pipeline | Any: data trust at scale | Custom operators, BranchOperator, testing, callbacks |
| 10 | Multi-Tenant SaaS Analytics | SaaS: 10K tenants | Dynamic DAG generation, RBAC, security, isolation |

---

## Production Operations (Files 11-14)

| # | Topic | What It Covers |
|---|-------|----------------|
| 11 | Production Deployment | Helm charts, CI/CD, GitSync, blue-green, canary |
| 12 | Monitoring & Alerting | StatsD, Prometheus, Grafana dashboards, PagerDuty |
| 13 | Scaling for Billions | HA scheduler, auto-scaling workers, metadata DB tuning |
| 14 | Disaster Recovery | Multi-region failover, backup/restore, chaos engineering |

---

## Architecture: Airflow at Billions Scale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION AIRFLOW - BILLIONS SCALE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    CONTROL PLANE (EKS/GKE)                       │        │
│  │                                                                  │        │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │        │
│  │  │ Scheduler-1 │  │ Scheduler-2 │  │ Scheduler-3 │  (HA)      │        │
│  │  │ (Active)    │  │ (Active)    │  │ (Active)    │            │        │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │        │
│  │         │                │                │                     │        │
│  │  ┌──────▼────────────────▼────────────────▼──────┐             │        │
│  │  │         DAG Processor Pool (Shared)            │             │        │
│  │  │    20 processes × 3 schedulers = 60 parsers    │             │        │
│  │  └────────────────────────────────────────────────┘             │        │
│  │                                                                  │        │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │        │
│  │  │ Web Server-1 │  │ Web Server-2 │  │ Web Server-3 │         │        │
│  │  │ (behind ALB) │  │ (behind ALB) │  │ (behind ALB) │         │        │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │        │
│  │                                                                  │        │
│  │  ┌──────────────┐  ┌──────────────┐                           │        │
│  │  │ Triggerer-1  │  │ Triggerer-2  │  (Deferrable operators)   │        │
│  │  └──────────────┘  └──────────────┘                           │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    DATA PLANE (Worker Pool)                       │        │
│  │                                                                  │        │
│  │  ┌─────────────────────────────────────────────┐                │        │
│  │  │      CeleryExecutor Workers (Auto-scaled)    │                │        │
│  │  │                                              │                │        │
│  │  │  Queue: default    → 50 workers × 16 slots  │                │        │
│  │  │  Queue: heavy_etl  → 20 workers × 4 slots   │                │        │
│  │  │  Queue: ml_training→ 10 workers × 2 slots   │                │        │
│  │  │  Queue: priority   → 10 workers × 8 slots   │                │        │
│  │  └─────────────────────────────────────────────┘                │        │
│  │                                                                  │        │
│  │  ┌─────────────────────────────────────────────┐                │        │
│  │  │      KubernetesExecutor (On-demand pods)     │                │        │
│  │  │                                              │                │        │
│  │  │  GPU pods    → nvidia.com/gpu nodes          │                │        │
│  │  │  High-mem    → r5.8xlarge nodes              │                │        │
│  │  │  Spark submit→ EMR/Dataproc integration      │                │        │
│  │  └─────────────────────────────────────────────┘                │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    STATE LAYER                                    │        │
│  │                                                                  │        │
│  │  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐ │        │
│  │  │ PostgreSQL RDS │    │ Redis Cluster  │    │ S3 / GCS      │ │        │
│  │  │ (Multi-AZ)     │    │ (ElastiCache)  │    │               │ │        │
│  │  │                │    │                │    │ Remote Logs    │ │        │
│  │  │ Metadata DB    │    │ Celery Broker  │    │ XCom Backend  │ │        │
│  │  │ + PgBouncer    │    │ + Result Store │    │ DAG Storage   │ │        │
│  │  │                │    │                │    │               │ │        │
│  │  │ 8 vCPU, 64GB   │    │ 6 nodes,       │    │               │ │        │
│  │  │ 10K IOPS       │    │ cluster mode   │    │               │ │        │
│  │  └────────────────┘    └────────────────┘    └───────────────┘ │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    OBSERVABILITY                                  │        │
│  │                                                                  │        │
│  │  StatsD → Prometheus → Grafana → PagerDuty/OpsGenie             │        │
│  │  Logs   → FluentBit  → OpenSearch → Kibana                      │        │
│  │  Traces → OpenTelemetry → Jaeger/Tempo                          │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Scale Numbers (Real Production)

| Metric | Target |
|--------|--------|
| DAGs | 2,000+ active |
| Task Instances / day | 500,000+ |
| Data processed / day | 50+ TB |
| Transactions reconciled / day | 2+ Billion |
| Concurrent tasks | 800+ |
| Workers (auto-scaled) | 50-200 |
| Metadata DB connections (pooled) | 500+ |
| P99 scheduling latency | < 5 seconds |
| DAG parse time (p99) | < 30 seconds |
| Availability SLA | 99.95% |

---

## How to Read This Folder

1. **Start with problems 01-10** - Each teaches Airflow concepts through real scenarios
2. **Then read 11-14** - Production operations that apply across all problems
3. **Each file is self-contained** - Read in any order based on your interest
4. **Code is production-ready** - Copy-paste into your project with modifications

---

## Airflow Version & Stack

All examples target:
- **Airflow 2.7+** (with Datasets, Deferrable Operators, TaskFlow API v2)
- **Kubernetes** deployment via official Helm chart
- **CeleryExecutor** (primary) + **KubernetesExecutor** (for heterogeneous workloads)
- **AWS** as primary cloud (easily adaptable to GCP/Azure)
- **PostgreSQL 15** as metadata database
- **Redis 7** as Celery broker
