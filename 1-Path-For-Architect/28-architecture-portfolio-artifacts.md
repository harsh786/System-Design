# Architecture Portfolio Artifacts

A world-class roadmap should produce proof. Interviewers trust candidates who can show structured thinking, operational realism, and decision quality.

## Portfolio Outcome

Build a portfolio folder for the capstone where each artifact proves one architect skill.

```text
portfolio/
  01-business-requirements.md
  02-non-functional-requirements.md
  03-capacity-plan.md
  04-c4-context.md
  05-c4-container.md
  06-sequence-diagrams.md
  07-api-contracts.md
  08-event-contracts.md
  09-data-model.md
  10-adr-log.md
  11-threat-model.md
  12-slo-document.md
  13-runbooks.md
  14-cost-model.md
  15-migration-plan.md
  16-test-strategy.md
  17-postmortem.md
```

## 1. Business Requirements

Include:

- Problem statement.
- Target users.
- User journeys.
- Success metrics.
- Non-goals.
- Constraints.
- Stakeholders.
- Rollout scope.

Template:

```markdown
# Business Requirements

## Problem
...

## Users
...

## Goals
...

## Non-Goals
...

## Success Metrics
...

## Constraints
...
```

## 2. Non-Functional Requirements

Cover:

- Availability.
- Latency.
- Throughput.
- Durability.
- Consistency.
- Security.
- Privacy.
- Compliance.
- Operability.
- Cost.
- Data retention.
- Disaster recovery.

Use exact targets:

```text
Checkout API p95 latency <= 300 ms under 2,000 QPS.
Order creation durability: no acknowledged order is lost.
RPO <= 5 minutes, RTO <= 30 minutes for regional failover.
```

## 3. Capacity Plan

Include:

- DAU/MAU.
- Peak QPS.
- Read/write split.
- Storage/day.
- Retention.
- Partition count.
- Cache working set.
- Queue throughput.
- Failover headroom.
- Cost estimate.

## 4. C4 Context Diagram

Show:

- Users.
- External systems.
- System boundary.
- Trust boundaries.
- High-level dependencies.

Keep it readable. The goal is shared understanding, not artistic detail.

## 5. C4 Container Diagram

Show:

- Services.
- Databases.
- Caches.
- Queues.
- Search indexes.
- Analytics stores.
- External providers.
- Sync and async flows.

Include ownership and criticality where useful.

## 6. Sequence Diagrams

Required flows:

- Happy path.
- Retry path.
- Failure path.
- Compensation path.
- Rollback path.

For commerce capstone:

- Checkout.
- Inventory reservation.
- Payment authorization.
- Order confirmation.
- Payment failure.
- Refund.
- Shipment update.

## 7. API Contracts

Include:

- Endpoint or RPC name.
- Request schema.
- Response schema.
- Error model.
- Auth requirements.
- Idempotency behavior.
- Pagination/filtering.
- Versioning.
- Rate limits.

## 8. Event Contracts

Include:

- Event name.
- Producer.
- Consumers.
- Schema.
- Version.
- Partition key.
- Ordering guarantee.
- Retention.
- Compatibility mode.
- Replay behavior.
- PII classification.

## 9. Data Model

Include:

- Conceptual model.
- Logical schema.
- Physical schema.
- Indexes.
- Partitioning.
- Ownership.
- Retention.
- Backup/restore.
- Migration strategy.

## 10. ADR Log

ADR template:

```markdown
# ADR-N: Title

## Status
Accepted

## Context
...

## Decision
...

## Alternatives Considered
...

## Consequences
...

## Reversal Plan
...
```

Must-have ADRs:

- Monolith vs microservices.
- Database choice.
- Event platform choice.
- Consistency model.
- Deployment strategy.
- Multi-region strategy.
- Auth model.
- Observability standard.

## 11. Threat Model

Use STRIDE:

| Threat | Example |
| --- | --- |
| Spoofing | Stolen token, fake service identity. |
| Tampering | Modified event payload. |
| Repudiation | User denies payment action. |
| Information disclosure | Tenant data leak. |
| Denial of service | API abuse or queue flood. |
| Elevation of privilege | Broken admin authorization. |

Include:

- Assets.
- Actors.
- Trust boundaries.
- Abuse cases.
- Controls.
- Residual risk.

## 12. SLO Document

Include:

- User journeys.
- SLIs.
- SLO targets.
- Error budget.
- Alert policy.
- Dashboard.
- Escalation.
- Review cadence.

Example:

```text
SLI: successful checkout requests / total checkout requests.
SLO: 99.9% monthly successful checkout excluding client validation errors.
Alert: 2% error budget burn in 1 hour or 5% burn in 6 hours.
```

## 13. Runbooks

Each runbook should include:

- Symptom.
- Impact.
- Dashboard link.
- Diagnosis steps.
- Mitigation.
- Rollback.
- Escalation.
- Post-incident follow-up.

Required runbooks:

- Database latency spike.
- Kafka lag spike.
- Redis outage.
- Payment provider outage.
- Error budget burn.
- Bad deployment.
- Regional failover.

## 14. Cost Model

Include:

- Unit economics.
- Main cost drivers.
- Baseline monthly estimate.
- 10x growth estimate.
- Optimization levers.
- Budget alerts.
- Ownership tags.

Example units:

- Cost per order.
- Cost per 1,000 API requests.
- Cost per GB stored/month.
- Cost per million events.
- Cost per tenant.

## 15. Migration Plan

Include:

- Current state.
- Target state.
- Steps.
- Expand-contract changes.
- Backfill.
- Dual-run or shadow mode.
- Cutover.
- Rollback.
- Validation.
- Owner and timeline.

## 16. Test Strategy

Include:

- Critical invariants.
- Test layers.
- Contract tests.
- Load tests.
- Chaos tests.
- Security tests.
- Data quality tests.
- Release gates.

## 17. Postmortem

Write one simulated incident:

- Summary.
- Timeline.
- User impact.
- Root cause.
- Detection gap.
- Mitigation.
- What went well.
- What went poorly.
- Action items.
- Prevention.

## Portfolio Review Checklist

- Can someone understand the system without you speaking?
- Are trade-offs explicit?
- Are diagrams consistent with APIs and data model?
- Are SLOs connected to dashboards and alerts?
- Are failure modes connected to runbooks?
- Are ADRs specific and reversible where possible?
- Does the cost model connect to architecture choices?
- Does the migration plan avoid big-bang cutover?
- Does the threat model include tenant and data boundaries?

