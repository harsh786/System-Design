# Problem 27: Real-Time Data Quality Monitoring

## Problem 27: Real-Time Data Quality Monitoring

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         DATA QUALITY MONITORING ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA PIPELINES (100+ DAGs in Airflow)                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                          │
│  │  ETL 1  │ │  ETL 2  │ │  ETL 3  │ │  ETL N  │                          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                          │
│       │           │           │           │                                 │
│  ┌────▼───────────▼───────────▼───────────▼────┐                           │
│  │  DATA QUALITY CHECKS (at each stage)         │                           │
│  │                                              │                            │
│  │  ┌─────────────────────────────────────────┐│                            │
│  │  │ CHECK TYPES:                             ││                            │
│  │  │ • Schema: columns exist, types match     ││                            │
│  │  │ • Freshness: data arrived on time        ││                            │
│  │  │ • Volume: row count within ±20% of norm  ││                            │
│  │  │ • Completeness: NULL rate < threshold    ││                            │
│  │  │ • Uniqueness: no duplicate PKs           ││                            │
│  │  │ • Range: values within expected bounds   ││                            │
│  │  │ • Referential: FK relationships hold     ││                            │
│  │  │ • Custom: business-specific rules        ││                            │
│  │  └─────────────────────────────────────────┘│                            │
│  └────────────────────┬────────────────────────┘                            │
│                       │                                                      │
│  ┌────────────────────▼────────────────────────┐                            │
│  │  CIRCUIT BREAKER                             │                            │
│  │                                              │                            │
│  │  If critical check fails:                    │                            │
│  │  → HALT downstream pipeline                  │                            │
│  │  → Alert on-call engineer (PagerDuty)        │                            │
│  │  → Record in quality events (Kafka)          │                            │
│  │  → Dashboard shows red (Grafana)             │                            │
│  │                                              │                            │
│  │  If non-critical check fails:                │                            │
│  │  → Log warning                               │                            │
│  │  → Continue pipeline                         │                            │
│  │  → Track trend (degradation detection)       │                            │
│  └────────────────────┬────────────────────────┘                            │
│                       │                                                      │
│  ┌────────────────────▼────────────────────────┐                            │
│  │  QUALITY METADATA STORE                      │                            │
│  │                                              │                            │
│  │  • Historical check results (time-series)    │                            │
│  │  • SLA tracking per dataset                  │                            │
│  │  • Anomaly detection on quality metrics      │                            │
│  │  • Data contract compliance                  │                            │
│  │                                              │                            │
│  │  Store: TimescaleDB (time-series optimized)  │                            │
│  │  Viz: Grafana dashboards                     │                            │
│  └──────────────────────────────────────────────┘                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

