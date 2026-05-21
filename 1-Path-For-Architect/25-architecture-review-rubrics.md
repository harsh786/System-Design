# Architecture Review Rubrics

Use this file to score your own HLD, LLD, and architect interview answers. A world-class roadmap needs a grading system; otherwise you only collect topics.

## HLD Scoring Rubric

Score each section from 0 to 3.

| Area | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| Requirements | Jumps to design. | Lists generic requirements. | Clarifies functional and non-functional requirements. | Defines goals, non-goals, constraints, and success metrics. |
| Scale | No estimates. | Rough QPS only. | Estimates QPS, storage, bandwidth. | Connects estimates to partitioning, capacity, cost, and failover. |
| APIs | No contracts. | Basic endpoints. | Defines request/response and idempotency. | Covers versioning, pagination, errors, auth, rate limits, and evolution. |
| Data model | Vague data stores. | Basic entities. | Entities, indexes, access patterns. | Ownership, consistency, retention, migration, backup, and privacy. |
| Architecture | Technology list. | Basic boxes. | Clear services and data flow. | Explains boundaries, failure isolation, scaling path, and trade-offs. |
| Deep dive | None. | Random detail. | One key bottleneck explained. | Chooses riskiest area and handles alternatives, failure modes, and operations. |
| Reliability | Ignored. | Mentions replicas. | Covers retries, timeouts, DLQ, failover. | Defines SLO, error budget, graceful degradation, DR, and testing. |
| Security | Ignored. | Mentions auth. | AuthN, AuthZ, encryption. | Threat model, secrets, audit, tenant isolation, compliance, abuse controls. |
| Observability | Ignored. | Mentions logs. | Metrics, logs, traces. | User journey dashboard, dependency health, alerts, runbooks, SLO burn. |
| Deployment | Ignored. | Mentions Kubernetes. | CI/CD, rollout, rollback. | Canary, migration, feature flags, compatibility, operational ownership. |
| Cost | Ignored. | Mentions "expensive". | Names cost drivers. | Unit economics, trade-offs, optimization levers, budget controls. |
| Communication | Disorganized. | Understandable but scattered. | Structured answer. | Drives the interview, summarizes choices, and adapts to feedback. |

Interpretation:

- 0-14: topic memorization.
- 15-25: mid-level system design.
- 26-32: senior-level.
- 33-36: staff/architect-level.

## LLD Scoring Rubric

| Area | Weak | Strong | Architect-Level |
| --- | --- | --- | --- |
| Requirements | Starts with classes. | Clarifies use cases. | Defines invariants, state transitions, and change points. |
| Domain model | Noun extraction only. | Entities and services. | Entities, value objects, aggregates, policies, repositories, events. |
| SOLID | Names principles. | Applies some principles. | Uses SOLID to justify boundaries and future change. |
| Patterns | Pattern dumping. | Appropriate pattern use. | Explains why a pattern is useful and where it would be overkill. |
| Interfaces | Concrete classes only. | Some abstractions. | Stable contracts around policy, persistence, external systems, and time. |
| Concurrency | Ignored. | Mentions locks. | Defines shared state, idempotency, atomicity, lock strategy, and tests. |
| Persistence | Ignored. | Basic repository. | Transaction boundaries, indexes, consistency, migrations, failure behavior. |
| Error handling | Generic exceptions. | Domain errors. | Error taxonomy, retryability, compensation, and user-visible behavior. |
| Extensibility | Adds abstract classes everywhere. | Adds extension points. | Adds extension only where requirements indicate likely change. |
| Testing | Unit tests only. | Unit and integration. | Unit, contract, property, concurrency, mutation, and state-machine tests. |

## "Bad vs Good vs Architect" Examples

### Example: Design a Rate Limiter

Bad answer:

- "Use Redis and token bucket."

Good answer:

- "Use token bucket for burst control, Redis for shared counters, and Lua for atomic updates."

Architect answer:

- "First I need limit dimensions: user, API key, tenant, IP, endpoint, and global. I would use local in-process limiting for cheap protection and Redis-backed distributed limiting for tenant/API quotas. Token bucket handles bursts; sliding-window log is more precise but expensive; fixed window is cheaper but has boundary bursts. I would define fail-open vs fail-closed per endpoint, expose limit headers, add metrics for allowed/blocked/degraded, and test Redis outage behavior."

### Example: Design a Notification System

Bad answer:

- "Use Kafka and workers."

Good answer:

- "Use Kafka topics per channel, workers for email/SMS/push, and retry with DLQ."

Architect answer:

- "I would model notification intent separately from delivery attempts. The system needs preference checks, dedupe, templates, provider routing, priority, rate limits, retry policy, DLQ, and audit. I would separate transactional notifications from marketing traffic, use idempotency keys, track provider responses, expose a delivery state machine, and define SLOs per channel."

### Example: Design a Booking System

Bad answer:

- "Lock the seat and take payment."

Good answer:

- "Use a temporary hold with expiry and confirm after payment."

Architect answer:

- "Inventory correctness is the core invariant. I would use a hold state with TTL, optimistic concurrency or row-level locking for seat allocation, idempotent payment confirmation, and a reconciliation process. The hold expiry must work even if workers fail. The user API returns clear states: available, held, confirmed, expired, payment_failed. I would test concurrent booking attempts and payment webhook retries."

## Architecture Review Checklist

Before calling any design complete, ask:

- What is the business outcome?
- What are explicit non-goals?
- Which quality attribute dominates the design?
- What is the source of truth?
- What is synchronous vs asynchronous and why?
- Where can data be inconsistent?
- What are the hot paths and hot partitions?
- What fails during dependency outage?
- What fails during regional outage?
- What fails during deploy?
- What is the rollback plan?
- What is the migration plan?
- What are the cost drivers?
- What is the security boundary?
- What is the operational owner?
- What dashboard proves health?
- What runbook handles the top incident?

## Principal/Architect Decision Rubric

Architect decisions should be:

- Reversible where possible.
- Explicit where irreversible.
- Measurable through SLOs or business metrics.
- Owned by a team.
- Documented as an ADR if expensive to change.
- Compatible with migration and rollback.
- Clear about cost and operational load.
- Safe under failure.
- Evolvable without breaking clients.

## Mock Interview Self-Review

After every mock answer, write:

| Question | Score |
| --- | --- |
| Did I clarify requirements before designing? | 0-3 |
| Did I quantify scale? | 0-3 |
| Did I choose a data model based on access patterns? | 0-3 |
| Did I discuss consistency and failure modes? | 0-3 |
| Did I explain trade-offs, not just choices? | 0-3 |
| Did I include security, observability, deployment, and cost? | 0-3 |
| Did I speak in a structured, confident way? | 0-3 |

Target: 18+ consistently before serious architect interviews.

## Review Board Simulation

Practice presenting one design as if an architecture board will challenge it.

Expected challenges:

- "Why not start with a modular monolith?"
- "What is the migration path from the current system?"
- "What is the smallest production-safe version?"
- "How does this fail during a regional outage?"
- "Which team owns the on-call burden?"
- "How much will this cost at 10x traffic?"
- "How do you know the system is healthy?"
- "What is your data deletion story?"
- "What happens if Kafka/Redis/Postgres is down?"
- "What decision is hardest to reverse?"

