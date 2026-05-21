# Observability, SRE, and Production Reliability

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 14. Observability, SRE, and Production Reliability Roadmap

## Observability Pillars

- Logs.
- Metrics.
- Traces.
- Profiles.
- Events.

## OpenTelemetry

Learn:

- Traces.
- Spans.
- Metrics.
- Logs.
- Context propagation.
- Instrumentation libraries.
- Collector.
- Exporters.

## Metrics Frameworks

### RED Metrics

- Rate.
- Errors.
- Duration.

### USE Metrics

- Utilization.
- Saturation.
- Errors.

### Golden Signals

- Latency.
- Traffic.
- Errors.
- Saturation.

## SRE Concepts

- SLI.
- SLO.
- SLA.
- Error budget.
- Burn-rate alert.
- Incident response.
- Postmortem.
- Runbook.
- Toil.
- Capacity planning.
- Load testing.
- Chaos engineering.

## Production Dashboards

Create dashboards for:

- API latency p50/p90/p95/p99.
- Error rate.
- Request rate.
- Saturation.
- Database slow queries.
- Connection pool usage.
- Kafka consumer lag.
- Redis hit ratio.
- Kubernetes pod restarts.
- Deployment health.
- SLO burn rate.

---


## 16.8 Observability & Monitoring Deep Dive

### Prometheus Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Exporters  │────▶│  Prometheus  │────▶│   Grafana   │
│  (Targets)  │     │   Server     │     │ Dashboards  │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐
                    │ Alertmanager │
                    └──────────────┘
```

**Core Components:**
| Component | Role | Key Config |
|-----------|------|------------|
| Prometheus Server | Scrapes & stores metrics (TSDB) | `scrape_interval`, `evaluation_interval` |
| Alertmanager | Routes & deduplicates alerts | `group_by`, `inhibit_rules`, `routes` |
| Pushgateway | For short-lived batch jobs | Push metrics before job exits |
| Exporters | Expose metrics in Prometheus format | node_exporter, blackbox_exporter |
| Service Discovery | Auto-find scrape targets | Kubernetes SD, Consul SD, DNS SD |

**PromQL Essentials:**
```promql
# Request rate per second (5-minute window)
rate(http_requests_total{job="api"}[5m])

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# Predict disk full in 4 hours
predict_linear(node_filesystem_free_bytes[1h], 4*3600) < 0
```

**Scaling Prometheus:**
| Approach | Use Case | Trade-off |
|----------|----------|-----------|
| Federation | Aggregate from multiple Prometheus instances | Loses granularity at higher levels |
| Thanos | Long-term storage + global view | Adds complexity (sidecar, store, compactor) |
| Cortex/Mimir | Multi-tenant, horizontally scalable | Heavy infrastructure requirement |
| VictoriaMetrics | Drop-in replacement, better compression | Smaller community than Thanos |
| Remote Write | Stream to external long-term store | Network bandwidth cost |

### VictoriaMetrics

**Architecture Advantages over Prometheus:**
- 10x better compression (less storage cost)
- Handles billions of time series
- MetricsQL (superset of PromQL with extensions)
- Supports multiple protocols: Prometheus, Graphite, InfluxDB, OpenTSDB
- Cluster mode with separate vminsert, vmselect, vmstorage

**Cluster Architecture:**
```
┌────────────┐     ┌────────────┐     ┌─────────────┐
│  vminsert  │────▶│ vmstorage  │◀────│  vmselect   │
│ (ingestion)│     │  (data)    │     │  (queries)  │
└────────────┘     └────────────┘     └─────────────┘
```

### Distributed Tracing

**OpenTelemetry Architecture:**
```
┌─────────────────────────────────────────────┐
│              Application                      │
│  ┌───────┐  ┌────────┐  ┌───────────────┐  │
│  │Traces │  │Metrics │  │    Logs       │  │
│  └───┬───┘  └───┬────┘  └──────┬────────┘  │
└──────┼──────────┼───────────────┼───────────┘
       └──────────┼───────────────┘
                  ▼
       ┌─────────────────────┐
       │  OTel Collector     │
       │  (Agent/Gateway)    │
       └─────────┬───────────┘
                 ▼
    ┌────────┬────────┬─────────┐
    │ Jaeger │ Zipkin │ Tempo   │
    └────────┴────────┴─────────┘
```

**Trace Propagation Context:**
| Header Format | Standard | Example |
|---------------|----------|---------|
| W3C TraceContext | `traceparent` | `00-{trace-id}-{span-id}-{flags}` |
| B3 (Zipkin) | `X-B3-TraceId` | Single or multi-header |
| Jaeger | `uber-trace-id` | `{trace-id}:{span-id}:{parent-id}:{flags}` |
| AWS X-Ray | `X-Amzn-Trace-Id` | `Root={trace-id};Parent={span-id}` |

**Sampling Strategies:**
| Strategy | Description | When to Use |
|----------|-------------|-------------|
| Always On | Trace every request | Dev/staging only |
| Probabilistic | Sample X% of requests | General production use |
| Rate Limiting | Max N traces/sec | High-traffic services |
| Tail-based | Decide after span completes (keep errors) | Need error traces without overhead |
| Parent-based | Follow parent's decision | Consistent across service boundaries |

### Observability Interview Questions

1. How would you design an alerting pipeline that avoids alert fatigue while ensuring critical issues are caught?
2. Explain the difference between black-box and white-box monitoring. When would you use each?
3. How does Prometheus handle high cardinality, and what strategies prevent cardinality explosion?
4. Design a distributed tracing system for a microservices architecture with 200+ services.
5. Compare push-based vs pull-based metrics collection. What are the failure modes of each?
6. How would you implement SLO-based alerting with error budgets?
7. Explain how Thanos achieves global query view across multiple Prometheus instances.
8. What's the difference between logging, metrics, and traces? When is each most appropriate?
9. How would you debug a latency spike that only affects p99 but not p50?
10. Design a log aggregation pipeline that handles 1TB/day with search latency under 2 seconds.

---


## 20.7 Observability, SRE, and Incident Depth

### Observability Must Cover

- Metrics: RED, USE, golden signals, business KPIs.
- Logs: structured JSON, trace IDs, sampling, PII redaction.
- Traces: spans, propagation, async boundaries, messaging spans.
- Profiles: CPU, allocation, lock contention, heap, wall-clock profiling.
- Events: deploy markers, config changes, feature flag flips.
- Dashboards: user journey, service health, dependency health, saturation, data freshness.
- Alerts: symptom-based, SLO burn rate, actionable owner, runbook link.

### Reliability Must Cover

- SLI, SLO, SLA distinction.
- Error budget policy and release gating.
- Graceful degradation and partial availability.
- Incident command, communication, and postmortem.
- Capacity tests, load tests, soak tests, chaos tests, failover drills.
- Backup and restore tests.
- Dependency risk register.
- Toil reduction and automation.


