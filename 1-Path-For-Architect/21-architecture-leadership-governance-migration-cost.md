# Architecture Leadership, Governance, Migration, and Cost

This file adds architect interview areas that are often missing from pure technical roadmaps.

## Architect-Level Outcomes

| Area | Outcome |
| --- | --- |
| Stakeholder alignment | Convert vague business goals into scoped, measurable architecture decisions. |
| Architecture governance | Keep systems consistent through lightweight standards, reviews, ADRs, and paved roads. |
| Migration strategy | Move from legacy to target architecture with low risk, measurable checkpoints, and rollback paths. |
| Platform thinking | Build reusable capabilities that reduce product-team cognitive load. |
| Cost and FinOps | Estimate, observe, allocate, and reduce spend without harming reliability. |
| Risk management | Identify technical, security, operational, delivery, and organizational risks early. |
| Communication | Explain trade-offs clearly to engineers, leaders, security, product, and operations. |

## Stakeholder and Requirement Mastery

- Separate business goals, user goals, system goals, and engineering constraints.
- Translate goals into quality attributes: availability, latency, durability, freshness, correctness, security, privacy, cost, operability, maintainability.
- Ask for hard boundaries: launch date, data volume, compliance scope, regions, budget, team skills, operational maturity.
- Define explicit non-goals to prevent architecture sprawl.
- Name the decision owner and escalation path for unresolved trade-offs.

## Architecture Governance

- Define a small set of platform standards: service template, logging schema, tracing propagation, metrics, health checks, auth, secrets, CI/CD, IaC, deployment strategy.
- Use ADRs for decisions that are expensive to reverse.
- Use architecture reviews for risk discovery, not ceremony.
- Create paved roads: approved libraries, golden paths, reference services, reusable Terraform/Kubernetes modules, runbook templates.
- Track exceptions with expiry dates and owners.

## Migration Patterns

| Pattern | Use When | Interview Talking Point |
| --- | --- | --- |
| Strangler fig | Replacing a monolith incrementally. | Route traffic feature by feature, keep rollback. |
| Parallel run | Correctness must be proven before cutover. | Compare outputs, reconcile differences, define tolerance. |
| Expand-contract | Database/API schema must evolve without downtime. | Add new fields first, migrate readers, then remove old fields. |
| Dual write with repair | Temporary synchronization is unavoidable. | Add reconciliation jobs and idempotency. |
| CDC replication | Legacy DB is source of truth during migration. | Watch lag, schema changes, ordering, and replay. |
| Shadow traffic | Validate new service behavior safely. | Do not affect user-visible state. |
| Canary cutover | Reduce blast radius. | Use metrics and rollback thresholds. |

## Cost and FinOps

- Estimate cost by traffic, storage, retention, replication factor, egress, managed-service pricing, observability volume, and support plan.
- Use unit economics: cost per request, order, user, GB ingested, event processed, query, or model inference.
- Tag resources by service, team, environment, cost center, and data classification.
- Control waste: autoscaling, rightsizing, reserved capacity, lifecycle policies, compaction, query optimization, log sampling.
- Include cost in design trade-offs: multi-region active-active, exactly-once processing, high retention, synchronous replication, and large indexes all have cost consequences.

## Platform and Team Topology

- Prefer platform capabilities that product teams can consume through self-service APIs, templates, and documentation.
- Reduce cognitive load: standardize infrastructure, observability, deployment, secrets, and incident workflows.
- Match service boundaries to team ownership where possible.
- Avoid shared databases across teams; use contracts and events instead.
- Define ownership for APIs, schemas, dashboards, SLOs, runbooks, and data products.

## Risk Register Template

| Risk | Impact | Likelihood | Signal | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| Hot partition | High write latency and dropped traffic. | Medium | Partition skew dashboard. | Better key, adaptive sharding, queue buffering. | Storage owner |
| Vendor outage | User-facing dependency failure. | Medium | Synthetic checks and provider status. | Fallback provider, circuit breaker, degraded mode. | Platform owner |
| Schema break | Consumer failures after deploy. | Medium | Contract test failure, DLQ spike. | Schema registry, compatibility rules, canary. | Event owner |

## Behavioral Stories to Prepare

- A time you changed an architecture decision after new evidence.
- A time you reduced system risk without blocking delivery.
- A time you led a migration while keeping production stable.
- A time you handled disagreement between teams.
- A time you improved operability after an incident.
- A time you balanced cost against reliability.
- A time you chose a boring technology over a trendy one.

## Interview Signals

Strong architects sound like this:

- "The design changes depending on the consistency requirement, so I will make that explicit first."
- "This option is cheaper operationally, but the migration risk is higher."
- "I would make this an ADR because reversing it later affects data ownership and client contracts."
- "The initial version can be simpler, but I want the interfaces to preserve the future migration path."
- "The dashboard should show symptoms first, then dependencies, then saturation."

