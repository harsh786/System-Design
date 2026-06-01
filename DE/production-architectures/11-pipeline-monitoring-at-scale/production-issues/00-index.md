# Top 100 Production Issues in Observability at Large Scale

## Overview

These are real production issues encountered at companies processing **billions of events/day**
across their observability infrastructure (metrics, logs, traces, alerts). Each issue includes
the problem, root cause, impact, detection method, and resolution pattern.

---

## File Organization

| File | Category | Issues | Scale Context |
|------|----------|--------|---------------|
| `01-metric-collection-storage.md` | Metric Collection & TSDB | #1-15 | 10M+ active time series |
| `02-log-pipeline-issues.md` | Log Ingestion & Processing | #16-30 | 10TB+ logs/day |
| `03-distributed-tracing-issues.md` | Tracing & APM | #31-45 | 1B+ spans/day |
| `04-alerting-oncall-issues.md` | Alerting & Incident Response | #46-60 | 10K+ alert rules |
| `05-data-quality-reliability.md` | Data Quality & Pipeline Reliability | #61-75 | 99.99% SLA target |
| `06-scaling-performance-issues.md` | Scaling & Performance | #76-90 | 100K+ monitored services |
| `07-organizational-operational.md` | Org & Operational Challenges | #91-100 | 500+ engineering teams |

---

## Severity Classification

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SEVERITY CLASSIFICATION                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  P0 - CRITICAL    │ Complete observability blindness                    │
│                   │ Cannot detect production incidents                  │
│                   │ Data loss in monitoring pipeline                    │
│                                                                         │
│  P1 - HIGH        │ Partial observability gap                          │
│                   │ Delayed incident detection (>5 min)                │
│                   │ Incorrect alerts firing/not firing                  │
│                                                                         │
│  P2 - MEDIUM      │ Degraded monitoring quality                        │
│                   │ Increased toil for on-call engineers               │
│                   │ Dashboard inaccuracies                             │
│                                                                         │
│  P3 - LOW         │ Cosmetic/minor issues                              │
│                   │ Performance degradation in queries                  │
│                   │ Cost inefficiencies                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Common Patterns Across All Issues

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    ROOT CAUSE PATTERNS                                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  1. CARDINALITY EXPLOSION (30% of issues)                                          │
│     └── Unbounded labels, tenant growth, deployment churn                          │
│                                                                                     │
│  2. RESOURCE EXHAUSTION (25% of issues)                                            │
│     └── Memory, disk, CPU, network bandwidth exceeded                              │
│                                                                                     │
│  3. CONFIGURATION DRIFT (20% of issues)                                            │
│     └── Misconfigs, version skew, inconsistent rollouts                            │
│                                                                                     │
│  4. UPSTREAM DEPENDENCY FAILURES (15% of issues)                                   │
│     └── Service discovery, DNS, storage backends                                    │
│                                                                                     │
│  5. DESIGN LIMITATIONS (10% of issues)                                             │
│     └── Single points of failure, lack of backpressure                             │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technologies Referenced

- **Metrics**: Prometheus, Thanos, Cortex, Mimir, Victoria Metrics, DataDog, InfluxDB
- **Logs**: Loki, Elasticsearch, OpenSearch, Splunk, ClickHouse, Fluentd, Vector
- **Traces**: Jaeger, Tempo, Zipkin, AWS X-Ray, OpenTelemetry Collector
- **Alerting**: Alertmanager, PagerDuty, OpsGenie, Grafana Alerting
- **Infrastructure**: Kubernetes, Kafka, S3/GCS, etcd, Consul
