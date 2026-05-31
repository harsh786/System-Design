# Problem 76: Real-Time Data Pipeline Monitoring & Alerting

## Problem 76: Real-Time Data Pipeline Monitoring & Alerting

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         DATA PIPELINE OBSERVABILITY PLATFORM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WHAT TO MONITOR:                                                            │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                                                                 │         │
│  │  INFRASTRUCTURE METRICS:                                        │         │
│  │  • Kafka: Consumer lag, broker CPU, disk, replication lag       │         │
│  │  • Flink: Checkpoint duration, backpressure ratio, restarts     │         │
│  │  • Spark: Stage duration, shuffle spill, executor OOM           │         │
│  │  • Storage: S3 request rates, 5xx errors, latency               │         │
│  │                                                                 │         │
│  │  DATA QUALITY METRICS:                                          │         │
│  │  • Freshness: Time since last successful write                  │         │
│  │  • Volume: Row count vs expected (±20% anomaly)                 │         │
│  │  • Schema: Column count/type changes                            │         │
│  │  • Nulls: NULL rate per column trending up?                     │         │
│  │  • Duplicates: Duplicate rate per batch                         │         │
│  │                                                                 │         │
│  │  BUSINESS METRICS:                                              │         │
│  │  • Revenue reconciliation: Pipeline total vs source total       │         │
│  │  • Coverage: % of expected entities present                     │         │
│  │  • Latency: Time from source event to queryable                 │         │
│  │                                                                 │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ALERTING TIERS:                                                             │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                                                                 │         │
│  │  P1 (Page immediately):                                         │         │
│  │  • Pipeline completely stopped (no data flowing)                │         │
│  │  • Data loss detected (gap in sequence)                         │         │
│  │  • Financial reconciliation mismatch > $1000                    │         │
│  │                                                                 │         │
│  │  P2 (Alert within 15 min):                                      │         │
│  │  • Freshness SLA breach (>30 min stale)                         │         │
│  │  • Error rate > 5%                                              │         │
│  │  • Consumer lag growing continuously                            │         │
│  │                                                                 │         │
│  │  P3 (Ticket, fix within 24h):                                   │         │
│  │  • Schema drift detected                                       │         │
│  │  • Gradual quality degradation                                  │         │
│  │  • Cost anomaly (query cost 3x normal)                          │         │
│  │                                                                 │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  TECH STACK:                                                                 │
│  Prometheus (metrics) + Grafana (viz) + PagerDuty (alerting)                 │
│  + OpenTelemetry (tracing) + custom Flink metrics (data quality)             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

