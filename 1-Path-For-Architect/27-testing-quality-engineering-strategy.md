# Testing and Quality Engineering Strategy

Architect-level quality is not "write unit tests". It is a layered strategy that proves correctness, compatibility, resilience, security, performance, and operability.

## Architect-Level Outcome

You should be able to define what must be tested, where to test it, which failures are acceptable, and what evidence proves production readiness.

## Testing Pyramid for Architects

| Layer | Purpose | Examples |
| --- | --- | --- |
| Unit | Fast validation of pure logic. | pricing, validators, state transitions. |
| Property-based | Validate invariants over many inputs. | ledger balances, scheduler constraints. |
| Contract | Preserve API/event compatibility. | consumer-driven contracts, schema compatibility. |
| Integration | Validate real dependencies. | DB transactions, Redis scripts, Kafka producers. |
| End-to-end | Validate critical user journeys. | signup, checkout, booking, payout. |
| Performance | Validate SLO under load. | load, stress, spike, soak. |
| Resilience | Validate failure handling. | dependency outage, network latency, failover. |
| Security | Validate abuse controls. | authz, injection, secrets, tenant isolation. |
| Data quality | Validate pipelines and analytics correctness. | freshness, completeness, uniqueness, drift. |
| Operational | Validate runbooks and recovery. | backup/restore, rollback, incident drill. |

## Quality Strategy Template

For every architecture, define:

```text
Critical invariants -> Test layers -> Test data -> Environments -> Gates -> Observability -> Failure drills -> Ownership
```

## Invariant-Driven Testing

Start with invariants:

- A ledger must balance.
- A booking cannot confirm an unavailable seat.
- A payment webhook must be idempotent.
- A tenant cannot read another tenant's data.
- A message can be processed more than once without duplicate side effects.
- A schema change cannot break existing consumers.
- A backup can be restored within RTO.

Then map each invariant to tests.

| Invariant | Test Type |
| --- | --- |
| Balance never negative unless credit line exists. | Unit, property, integration. |
| Events remain backward compatible. | Schema and contract test. |
| Duplicate command has one side effect. | Integration and concurrency test. |
| Tenant isolation holds in API and background jobs. | Security and integration test. |
| Service recovers after dependency outage. | Fault injection and chaos test. |

## Contract Testing

### API Contracts

- OpenAPI or protobuf definitions.
- Backward-compatible request and response evolution.
- Required vs optional fields.
- Error code stability.
- Pagination and filtering behavior.
- Auth and authorization expectations.

### Event Contracts

- Schema registry.
- Compatibility mode.
- Version field.
- Required defaults for new fields.
- Unknown-field handling.
- Consumer compatibility tests.
- Replay tests.

### Consumer-Driven Contracts

Use when independent teams own producers and consumers.

Workflow:

1. Consumer defines expectations.
2. Provider verifies expectations in CI.
3. Breaking change is blocked before deployment.
4. Contract ownership and expiry are explicit.

## Data Quality Testing

For data platforms:

- Freshness: data arrives within expected delay.
- Completeness: expected partitions and row counts exist.
- Validity: values match allowed ranges and formats.
- Uniqueness: no duplicate primary/business keys.
- Referential integrity: foreign relationships make sense.
- Distribution drift: metrics change beyond threshold.
- Reconciliation: aggregate totals match source of truth.
- Lineage: output can be traced to input.

## Resilience Testing

### Failure Injection Matrix

| Failure | Expected Behavior |
| --- | --- |
| DB slow queries | Timeouts, degraded mode, alert. |
| Redis unavailable | Local fallback or fail policy. |
| Kafka unavailable | Producer back-pressure, buffering, alert. |
| Downstream 500s | Circuit breaker opens, retries bounded. |
| Network latency | Caller timeout and retry budget preserved. |
| Pod restart | No data loss, idempotent recovery. |
| Region outage | Failover plan meets RTO/RPO. |
| Clock skew | Time-sensitive workflows remain safe. |

### Chaos Testing Rules

- Start in staging.
- Define hypothesis before experiment.
- Limit blast radius.
- Add abort conditions.
- Run during controlled windows first.
- Observe user-facing symptoms, not only infrastructure metrics.
- Convert findings into runbooks and fixes.

## Performance Testing Gates

Before production:

- Baseline p50/p95/p99 latency.
- Peak throughput.
- Error rate under expected load.
- Saturation point.
- Resource usage per request.
- Database query plans under realistic data volume.
- Queue lag under burst traffic.
- Cache hit ratio after warmup.
- Cost per unit of work.
- Soak test for leaks and slow degradation.

## Security Testing

Minimum architect checklist:

- AuthN and AuthZ tests.
- Tenant isolation tests.
- Input validation and injection tests.
- Secrets scanning.
- Dependency scanning.
- Container image scanning.
- IaC policy checks.
- API abuse and rate-limit tests.
- Audit log verification.
- Data deletion and retention tests.

For AI systems, add:

- Prompt injection tests.
- Poisoned retrieved-document tests.
- Sensitive data exfiltration tests.
- Unsafe tool-call tests.
- Unbounded consumption tests.

## Deployment Quality Gates

| Gate | Purpose |
| --- | --- |
| Static checks | Formatting, lint, security scan, policy check. |
| Unit tests | Logic correctness. |
| Contract tests | Compatibility. |
| Integration tests | Dependency behavior. |
| Migration tests | Schema/data migration safety. |
| Canary | Real traffic with limited blast radius. |
| SLO monitor | Confirm no burn-rate spike. |
| Rollback drill | Confirm recovery path works. |

## Test Environment Strategy

| Environment | Purpose |
| --- | --- |
| Local | Fast developer feedback. |
| CI ephemeral | Isolated test execution. |
| Shared integration | Realistic dependencies. |
| Staging | Release validation with production-like config. |
| Performance | Load and soak testing. |
| Production canary | Final validation with controlled traffic. |

Rules:

- Do not rely only on staging; production behavior includes real traffic, data shape, and dependency conditions.
- Do not run destructive tests in shared environments without isolation.
- Use synthetic tenants/accounts for repeatable E2E tests.
- Keep test data compliant and non-sensitive.

## Interview Questions

1. How do you test an event-driven payment workflow?
2. How do you prove a schema migration is safe?
3. How do you test tenant isolation?
4. What is the difference between contract testing and integration testing?
5. How do you test exactly-once-like behavior on top of at-least-once delivery?
6. How do you design a chaos experiment safely?
7. How do you test a backup/restore process?
8. How do you validate data quality in a lakehouse pipeline?
9. How do you test a RAG system?
10. What gates should block production deployment?

## Capstone Deliverable

For the commerce platform, produce:

- Test strategy document.
- Critical invariant list.
- API contract tests.
- Event schema compatibility tests.
- Concurrent booking/payment/idempotency tests.
- Load test report.
- Chaos experiment report.
- Backup/restore evidence.
- Security test checklist.
- Release gate policy.

