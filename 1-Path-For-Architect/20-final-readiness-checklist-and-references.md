# Final Readiness Checklist and References

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 24. Final Architect Interview Readiness Checklist

You are ready when you can do the following without notes:

- Solve medium DSA problems in 25-35 minutes.
- Complete the DSA bank by category and explain each pattern's production use.
- Explain DSA patterns through production use cases.
- Design the top 50 LLD problems with classes, interfaces, relationships, concurrency, state, and tests.
- Design the top 50 HLD systems end to end.
- Explain Java/JVM internals: HashMap, ConcurrentHashMap, locking, thread pools, memory model, and garbage collection.
- Explain database internals: pages, WAL, MVCC, indexes, isolation, replication, sharding, backup, and query plans.
- Compare relational, distributed SQL, document, wide-column, key-value, search, graph, time-series, OLAP, warehouse, lakehouse, and vector databases.
- Explain CAP, PACELC, consistency models, consensus, leader election, split brain, vector clocks, Merkle trees, hinted handoff, and consistent hashing.
- Design microservices with database per service, saga, CQRS, outbox, inbox, CDC, and contract testing.
- Design Kafka topics, partition keys, ordering, replay, DLQ, retry, schema evolution, and idempotent consumers.
- Build batch and streaming pipelines with Kafka, Spark, Flink, Airflow, S3/object storage, Iceberg/Hudi/Delta, and OLAP serving.
- Use architecture styles and create ADRs, C4 diagrams, sequence diagrams, deployment diagrams, and migration plans.
- Define SLIs, SLOs, error budgets, dashboards, alerts, runbooks, and postmortems.
- Deploy to Kubernetes with Helm, GitOps, HPA, probes, RBAC, NetworkPolicy, canary, rollback, and observability.
- Discuss security, IAM, secrets, encryption, threat modeling, supply chain security, and compliance.
- Speak clearly about trade-offs, failure modes, cost, migration, and operations.
- Design AI-native systems with RAG, vector search, LLM gateways, model routing, prompt/version management, evaluation, AI safety, and AI observability.
- Explain prompt injection, insecure output handling, data leakage, excessive agency, unbounded consumption, and safe tool use for LLM/agent systems.
- Build capacity models using QPS, latency budgets, Little's Law, queue depth, saturation, headroom, failover capacity, and unit economics.
- Define layered test strategies covering unit, property, contract, integration, E2E, performance, resilience, security, data quality, and operational recovery.
- Apply domain-specific architecture patterns for fintech, SaaS, marketplace, AdTech, media, healthcare, IoT, and internal platforms.
- Present a portfolio containing requirements, NFRs, C4 diagrams, sequence diagrams, APIs, event contracts, data model, ADRs, threat model, SLO, runbooks, cost model, migration plan, test strategy, and postmortem.
- Answer behavioral architecture questions with clear context, stakes, constraints, options, decision, execution, result, and reflection.
- Explain enterprise architecture through capability maps, operating model, governance, architecture review, technology radar, build-vs-buy, vendor risk, and exit strategy.
- Design client architecture for web/mobile systems with BFF, GraphQL, offline sync, API compatibility, feature rollout, accessibility, and real-user observability.
- Modernize legacy systems using API facades, anti-corruption layers, CDC, file integration, parallel run, reconciliation, and strangler migration.
- Design privacy and data governance controls for classification, consent, deletion, residency, lineage, data contracts, access review, and audit evidence.
- Debug infrastructure-level failures involving Linux processes, file descriptors, TCP, DNS, TLS, page cache, cgroups, containers, and Kubernetes resource limits.
- Define business continuity and disaster recovery strategies with RTO/RPO, backup integrity, regional failover, cyber recovery, DR drills, and crisis communication.
- Choose deployment strategies such as rolling, blue-green, canary, progressive delivery, shadow, dark launch, feature flags, and expand-contract database deployments.
- Scale systems for millions of users with CDN, cache hierarchy, database tuning, sharding, queues, fanout strategy, multi-region, cell architecture, abuse controls, observability, and cost optimization.
- Explain end-to-end microservices scalability from frontend and DNS to load balancers, WAF, API gateway, CORS, rate limiting, BFF, services, thread pools, connection pools, database pools, indexing, partitioning, sharding, caching, outbox, event processing, resilience patterns, security, observability, and deployment safety.
- Compare additional database families and engines: MySQL/InnoDB, Oracle, DynamoDB, Cassandra, HBase, distributed SQL, HTAP, search, graph, time-series, vector, embedded, coordination, and OLAP engines.
- Design lakehouse ecosystems with object storage, file formats, Iceberg/Hudi/Delta, catalogs, governance, CDC, orchestration, stream processing, data quality, lineage, serving engines, and cost controls.
- Design AWS architectures with Route 53, CloudFront, WAF, VPC, subnets, NAT, VPC endpoints, ALB/NLB, API Gateway, EKS, ECS, Fargate, EC2 worker node types, service mesh/service discovery, VPC Lattice, ECS Service Connect, RDS/Aurora, DynamoDB, ElastiCache, KMS, IAM, federation, SQS/SNS/EventBridge/Kinesis, CloudWatch, CloudTrail, Config, DR, and cost governance.

---

# 25. Official Documentation References for Continued Study

Use official/reference documentation whenever possible:

- Kubernetes concepts: https://kubernetes.io/docs/concepts/
- OpenTelemetry concepts: https://opentelemetry.io/docs/concepts/
- DORA metrics: https://dora.dev/guides/dora-metrics/
- PostgreSQL concurrency control: https://www.postgresql.org/docs/current/mvcc.html
- PostgreSQL transaction isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- Apache Kafka documentation: https://kafka.apache.org/documentation/
- Apache Spark documentation: https://spark.apache.org/docs/latest/
- Apache Flink documentation: https://nightlies.apache.org/flink/flink-docs-stable/
- Apache Iceberg documentation: https://iceberg.apache.org/docs/latest/
- Apache Hudi documentation: https://hudi.apache.org/docs/
- AWS S3 user guide: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html
- LeetCode problemset: https://leetcode.com/problemset/
- Microsoft SQL Server documentation: https://learn.microsoft.com/en-us/sql/sql-server/
- MongoDB manual: https://www.mongodb.com/docs/manual/
- Redis documentation: https://redis.io/docs/latest/
- RocksDB wiki: https://github.com/facebook/rocksdb/wiki
- Apache Pinot docs: https://docs.pinot.apache.org/
- ClickHouse docs: https://clickhouse.com/docs
- Amazon Redshift developer guide: https://docs.aws.amazon.com/redshift/latest/dg/welcome.html
- Aerospike documentation: https://aerospike.com/docs/
- AWS Well-Architected Framework: https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html
- Azure Well-Architected Framework: https://learn.microsoft.com/en-us/azure/well-architected/
- Google Cloud Well-Architected Framework: https://docs.cloud.google.com/architecture/framework
- Google SRE Book: https://sre.google/sre-book/table-of-contents/
- FinOps Framework: https://www.finops.org/framework/
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- CNCF Cloud Native Landscape: https://landscape.cncf.io/
- Web.dev performance guidance: https://web.dev/learn/performance/
- OWASP Application Security Verification Standard: https://owasp.org/www-project-application-security-verification-standard/
- AWS Route 53 API Reference: https://docs.aws.amazon.com/Route53/latest/APIReference/Welcome.html
- Apache Airflow documentation: https://airflow.apache.org/docs/
- Apache Beam documentation: https://beam.apache.org/documentation/
- Debezium documentation: https://debezium.io/documentation/
- Trino documentation: https://trino.io/docs/current/
- Apache Druid documentation: https://druid.apache.org/docs/latest/
- DuckDB documentation: https://duckdb.org/docs/
- DataHub documentation: https://datahubproject.io/docs/
- OpenMetadata documentation: https://docs.open-metadata.org/
- Great Expectations documentation: https://docs.greatexpectations.io/
- AWS EKS User Guide: https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html
- AWS ECS Developer Guide: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html
- Elastic Load Balancing User Guide: https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/what-is-load-balancing.html
- AWS IAM User Guide: https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html
- AWS KMS Developer Guide: https://docs.aws.amazon.com/kms/latest/developerguide/overview.html

---

# 26. Final Rule

Do not prepare like someone who memorizes tool names. Prepare like someone who can own a production platform.

For every design, always cover:

```text
Requirements -> Scale -> APIs -> Data -> Architecture -> Failure -> Consistency -> Security -> Observability -> Deployment -> Cost -> Trade-offs -> Migration
```

That is the architect-level interview standard.
