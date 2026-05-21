# World-Class Architect Interview Roadmap

This folder is the split, interview-focused version of `../world_class_pro_architect_master_roadmap.md`.
The original source file was not modified.

Use this as a staff/principal/architect preparation system: each file is a separate mastery track with concepts, build targets, interview prompts, and production proof.

## Recommended Order

1. [Execution Plan and Skill Matrix](01-execution-plan-and-skill-matrix.md)
2. [DSA and Algorithms for Architect Interviews](04-dsa-algorithms-production-patterns.md)
3. [Low-Level Design, SOLID, OOP, and Patterns](03-low-level-design-solid-oop.md)
4. [System Design HLD](02-system-design-hld.md)
5. [Java, JVM, and Primary Backend Stack](05-java-jvm-primary-backend-stack.md)
6. [Database Design and Internals](06-database-design-internals.md)
7. [Database Technologies and Selection](07-database-technologies-selection.md)
8. [Distributed Systems](08-distributed-systems.md)
9. [Microservices and Service Architecture](09-microservices-service-architecture.md)
10. [Event-Driven Architecture, Kafka, and Streaming](10-event-driven-kafka-streaming.md)
11. [Big Data, Lakehouse, and Analytics Architecture](11-big-data-lakehouse-analytics.md)
12. [Software Architecture, DDD, C4, and ADRs](12-software-architecture-ddd-c4-adrs.md)
13. [Observability, SRE, and Production Reliability](13-observability-sre-production-reliability.md)
14. [Kubernetes, Deployment, and Cloud Native Operations](14-kubernetes-deployment-cloud-native.md)
15. [Security and Cloud Architecture](15-security-cloud-architecture.md)
16. [Communication Protocols, Networking, and Edge Architecture](16-protocols-networking-edge-architecture.md)
17. [Caching, Scaling, Rate Limiting, and Resilience](17-caching-scaling-rate-limiting-resilience.md)
18. [Capstone Portfolio and Study Plan](18-capstone-portfolio-and-study-plan.md)
19. [Interview Question Bank](19-interview-question-bank.md)
20. [Final Readiness Checklist and References](20-final-readiness-checklist-and-references.md)
21. [Architecture Leadership, Governance, Migration, and Cost](21-architecture-leadership-governance-migration-cost.md)
22. [Interview Execution Playbook](22-interview-execution-playbook.md)
23. [AI-Native, LLM, RAG, and Agent Platform Architecture](23-ai-native-llm-platform-architecture.md)
24. [Performance and Capacity Engineering](24-performance-capacity-engineering.md)
25. [Architecture Review Rubrics](25-architecture-review-rubrics.md)
26. [Domain-Specific Architecture Deep Dives](26-domain-specific-architecture-deep-dives.md)
27. [Testing and Quality Engineering Strategy](27-testing-quality-engineering-strategy.md)
28. [Architecture Portfolio Artifacts](28-architecture-portfolio-artifacts.md)
29. [Behavioral and Architecture Leadership Interview Bank](29-behavioral-leadership-interview-bank.md)

## Architect-Level Outcome Matrix

| Area | Interview Outcome |
| --- | --- |
| DSA | Recognize patterns quickly and explain their production use in caches, queues, schedulers, indexes, search, and streams. |
| LLD and SOLID | Convert messy requirements into maintainable, extensible, concurrent, testable code-level design. |
| HLD System Design | Design scalable, reliable, secure, cost-aware distributed systems with explicit trade-offs. |
| Java/JVM | Explain memory, GC, collections, locking, thread pools, virtual threads, and production debugging. |
| Databases | Model data, choose engines, design indexes, tune queries, shard, replicate, recover, and reason about consistency. |
| Distributed Systems | Explain partitions, clocks, consensus, quorums, replication, leader election, failure detection, and eventual consistency. |
| Microservices | Design boundaries, APIs, data ownership, sagas, outbox, CDC, testing, deployment, and observability. |
| Event-Driven | Design event contracts, topics, partitioning, ordering, retries, DLQs, schema evolution, replay, and stream processing. |
| Big Data | Build batch, streaming, lakehouse, OLAP, governance, lineage, and cost-aware analytics systems. |
| Architecture Practice | Use DDD, C4, ADRs, quality attributes, migration strategies, and architecture review discipline. |
| SRE | Define SLIs/SLOs, instrument telemetry, debug incidents, write runbooks, and manage error budgets. |
| Kubernetes and Cloud | Deploy, scale, secure, observe, troubleshoot, and progressively release workloads. |
| Security | Design identity, authorization, network isolation, encryption, secrets, IAM, threat models, compliance, and auditability. |
| Leadership | Communicate trade-offs, align stakeholders, guide migrations, reduce risk, and make architecture decisions durable. |
| AI-Native Architecture | Design RAG, LLM gateways, vector search, AI evaluation, agent safety, AI security, and AI observability. |
| Performance Engineering | Model capacity, latency, saturation, tail behavior, load tests, profiling, and cost per unit of work. |
| Quality Engineering | Prove correctness, compatibility, resilience, security, performance, and operability through layered testing. |
| Domain Architecture | Adapt core patterns to fintech, SaaS, marketplace, AdTech, media, healthcare, IoT, and internal platforms. |

## Completion Bar

You are interview-ready when you can do all of this without notes:

- Solve common DSA patterns and connect each to a real system component.
- Design one LLD problem with SOLID, patterns, concurrency, persistence, and tests.
- Design one HLD problem with requirements, scale, APIs, data model, architecture, failure modes, security, observability, deployment, cost, and migration.
- Defend two alternatives for every major choice.
- Produce C4 diagrams, ADRs, runbooks, dashboards, and postmortems for the capstone.
- Explain a production incident you would expect in each architecture and how you would detect, mitigate, and prevent it.
- Design AI/RAG/agent systems with safety, evaluation, retrieval quality, permissioning, cost, and observability.
- Build a portfolio with capacity plan, threat model, SLO, runbooks, cost model, migration plan, test strategy, and postmortem.
- Score your own HLD and LLD answers using the architecture review rubrics.
