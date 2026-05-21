# Capstone Portfolio and Study Plan

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 17. Master Capstone Project

## Project: Production-Grade Event-Driven Commerce Platform

### Services

- API Gateway.
- Auth Service.
- User Service.
- Catalog Service.
- Cart Service.
- Inventory Service.
- Order Service.
- Payment Service.
- Shipment Service.
- Notification Service.
- Search Service.
- Recommendation Service.
- Analytics Service.
- Admin Service.

### Databases and Platforms

- PostgreSQL for transactional services.
- SQL Server optional for enterprise comparison.
- MongoDB for document catalog or content modeling.
- ScyllaDB for high-scale activity/event lookup experiments.
- Aerospike or Redis for low-latency profile/session/cache experiments.
- RocksDB for embedded state store experiments.
- Kafka for events.
- Redis for caching and rate limiting.
- Elasticsearch/OpenSearch for search.
- ClickHouse or Pinot for real-time analytics.
- Redshift/Snowflake/BigQuery-style warehouse for BI.
- Object storage + Iceberg/Delta/Hudi for lakehouse.

### Patterns to Implement

- Database per service.
- Transactional outbox.
- Inbox deduplication.
- Saga.
- CQRS read models.
- Event-carried state transfer.
- Idempotency keys.
- Retry with backoff and jitter.
- Circuit breaker.
- Bulkhead.
- Rate limiting.
- Cache-aside.
- DLQ.
- Schema registry.
- API gateway.
- BFF.
- Service discovery.
- Load balancing.
- CDN.
- OpenTelemetry tracing.
- Prometheus/Grafana dashboards.
- Kubernetes deployment.
- GitOps.
- Canary releases.
- Expand-contract migrations.

### Required Documents

- Business requirements.
- Non-functional requirements.
- Capacity plan.
- C4 context diagram.
- C4 container diagram.
- Service boundaries document.
- API contracts.
- Event contracts.
- Database schema.
- Sharding/partitioning plan.
- Caching plan.
- Failure-mode analysis.
- Security threat model.
- SLO document.
- Runbook.
- ADRs.
- Deployment diagram.
- Migration plan.
- Postmortem from simulated incident.

---

# 18. Weekly Aggressive Study Plan

## Daily 5-Hour Plan

| Time | Activity |
| --- | --- |
| 60 minutes | DSA pattern practice. |
| 60 minutes | Deep concept study. |
| 90 minutes | HLD or LLD design practice. |
| 60 minutes | Capstone coding/deployment/observability work. |
| 30 minutes | Notes, diagrams, and ADRs. |
| 20 minutes | Speak one concept aloud as interview practice. |

## Weekly Deliverables

- 5 DSA problems.
- 1 LLD design.
- 1 system design.
- 1 database deep dive.
- 1 distributed-systems concept lab.
- 1 microservice/event-driven implementation.
- 1 Kubernetes/deployment improvement.
- 1 observability dashboard or alert.
- 1 ADR.
- 1 mock interview recording.
- 1 capacity or cost model update.
- 1 test strategy improvement: contract, load, chaos, security, data quality, or recovery.
- 1 domain-specific architecture drill.
- 1 portfolio artifact update.
- 1 behavioral leadership story.

---


