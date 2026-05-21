# Interview Execution Playbook

Use this file to turn the roadmap into actual interview performance.

## HLD Interview Flow

| Time | Action |
| --- | --- |
| 0-5 min | Clarify product scope, users, functional requirements, and explicit non-goals. |
| 5-10 min | Define non-functional requirements: scale, latency, availability, durability, consistency, privacy, security, cost. |
| 10-15 min | Estimate traffic, storage, throughput, fanout, partition count, cache size, and regional needs. |
| 15-25 min | Define APIs, data model, core entities, and event contracts. |
| 25-40 min | Draw high-level architecture and explain request/data flow. |
| 40-55 min | Deep dive on the riskiest areas: consistency, partitioning, hot keys, ordering, failover, back-pressure, cache invalidation. |
| 55-65 min | Cover security, observability, deployment, cost, and migration. |
| 65-75 min | Summarize trade-offs and explain what you would build first. |

## LLD Interview Flow

| Time | Action |
| --- | --- |
| 0-5 min | Clarify use cases, actors, constraints, and expected operations. |
| 5-10 min | Identify entities, value objects, services, repositories, and external systems. |
| 10-20 min | Define interfaces and class responsibilities. |
| 20-35 min | Model relationships, state transitions, validation, and invariants. |
| 35-45 min | Handle concurrency, transactions, idempotency, and failure behavior. |
| 45-55 min | Add extensibility points and explain pattern choices. |
| 55-60 min | Define tests and summarize trade-offs. |

## Deep-Dive Prompts to Volunteer

- "Let me discuss the main failure modes and how I would detect them."
- "The hardest part here is consistency around this state transition."
- "This design has one likely hot partition; here are three ways to address it."
- "I would not start with active-active multi-region unless the RTO/RPO requires it."
- "For the first version, I would keep this synchronous and introduce events when the workflow needs decoupling."
- "The rollback plan matters because this changes a persistent contract."

## Common Architect Interview Mistakes

- Jumping into components before requirements.
- Listing technologies without explaining why.
- Ignoring write paths, failure modes, and operational ownership.
- Treating cache as magic instead of discussing invalidation and staleness.
- Saying "Kafka gives exactly once" without explaining constraints.
- Overusing microservices where a modular monolith is the better first step.
- Forgetting schema evolution, replay, DLQs, and idempotent consumers.
- Ignoring cost, rollout, migration, observability, and security.
- Designing for peak scale before clarifying business stage.
- Not summarizing trade-offs at the end.

## One-Page HLD Checklist

- Requirements and non-goals.
- Scale estimates and bottlenecks.
- API contracts and auth model.
- Data model, indexes, retention, and consistency.
- High-level components and data flow.
- Caching and invalidation.
- Partitioning and hot-key handling.
- Replication and disaster recovery.
- Async processing, retries, DLQs, idempotency.
- Security, privacy, compliance, secrets.
- Observability: metrics, logs, traces, alerts, dashboards.
- Deployment, canary, rollback, migration.
- Cost drivers and simplifications.
- Trade-offs and next iteration.

## One-Page LLD Checklist

- Actors and use cases.
- Entities, value objects, aggregates.
- Interfaces and class responsibilities.
- Relationship types and ownership.
- Invariants and validation.
- State machine and transition guards.
- Error model and exceptions.
- Concurrency and idempotency.
- Persistence and transaction boundaries.
- Extensibility and pattern choices.
- Unit, integration, contract, and concurrency tests.

## Mock Interview Drill

For each practice problem:

1. Spend 10 minutes writing requirements and non-goals.
2. Spend 10 minutes doing scale estimates.
3. Spend 20 minutes drawing the design.
4. Spend 15 minutes on one deep dive.
5. Spend 10 minutes on security, observability, deployment, and cost.
6. Spend 5 minutes summarizing trade-offs.
7. Record yourself and review for gaps, rambling, and unsupported claims.

## Final Speaking Standard

Every strong answer should include:

- The decision.
- The reason.
- The alternative rejected.
- The trade-off accepted.
- The failure mode introduced.
- The operational control used to manage that failure mode.

