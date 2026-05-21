# Top 300 Big Data, Streaming, Lakehouse, and Analytics Interview Question Bank

Purpose: prepare for senior, staff, principal, and architect interviews across big data platforms, streaming systems, lakehouse architecture, real-time analytics, CDC, orchestration, governance, and production operations.

Use this with:

- `11-big-data-lakehouse-analytics.md` for the roadmap and tool selection guide.
- `10-event-driven-kafka-streaming.md` for Kafka and event-driven architecture.
- `44-system-design-concepts-top-300-interview-question-bank.md` for distributed systems primitives.
- `45-database-database-design-top-300-interview-question-bank.md` for database internals and analytical store trade-offs.

How to practice:

1. Answer each problem in 3-5 minutes.
2. Always explain the workload, data volume, latency target, correctness requirement, and failure mode.
3. For every platform choice, compare at least two alternatives.
4. For every pipeline design, cover ingestion, schema, storage, compute, orchestration, quality, lineage, security, observability, backfill, and cost.
5. For every streaming answer, mention event time, watermarks, state, checkpoints, deduplication, ordering, replay, late events, and exactly-once trade-offs.

## Category Map

| Category | Range | What It Trains |
|---|---:|---|
| Big data foundations and architecture | 1-15 | Lake, warehouse, lakehouse, batch, streaming, mesh |
| Kafka fundamentals and data ingestion | 16-30 | Topics, partitions, producers, consumers, offsets |
| Kafka scaling, reliability, and operations | 31-45 | Replication, ISR, rebalances, transactions, retention |
| Kafka Connect, Debezium, CDC, and integration | 46-60 | Source/sink connectors, snapshots, schema changes, DLQs |
| Flink stream processing fundamentals | 61-75 | Event time, state, checkpoints, exactly-once |
| Windows, deduplication, joins, and streaming correctness | 76-90 | Tumbling, sliding, session windows, late data, joins |
| Spark, Beam, and distributed compute | 91-105 | Batch, structured streaming, shuffle, skew, portability |
| S3/object storage, file formats, and table layout | 106-120 | Parquet, ORC, Avro, partitioning, compaction |
| Lakehouse formats: Iceberg, Hudi, Delta | 121-135 | Snapshots, manifests, upserts, time travel, compaction |
| Catalogs, governance, lineage, and data discovery | 136-150 | Hive Metastore, Glue, Nessie, Polaris, DataHub |
| Warehouses and SQL engines: Redshift, Athena, Hive, Trino | 151-165 | MPP, external tables, cost, query optimization |
| Real-time OLAP: Pinot, ClickHouse, Druid, StarRocks | 166-180 | Low-latency analytics, rollups, indexing, ingestion |
| ETL, ELT, dbt, SQLMesh, and data quality | 181-195 | Transform strategy, tests, contracts, semantic layers |
| Orchestration: Airflow, Temporal, Dagster, Prefect, Argo | 196-210 | DAGs, workflows, retries, backfills, stateful orchestration |
| Backfills, reprocessing, replay, and migration | 211-225 | Historical correction, reproducibility, dual-run, validation |
| Analytics data modeling and metrics platforms | 226-240 | Star schema, facts, dimensions, feature stores, metric definitions |
| Performance, scaling, skew, and cost optimization | 241-255 | Shuffle, partition pruning, small files, autoscaling, cost |
| Reliability, observability, and data SRE | 256-270 | SLAs, freshness, lag, incidents, runbooks |
| Security, privacy, compliance, and multi-tenancy | 271-285 | PII, encryption, row/column security, data residency |
| End-to-end big data architecture scenarios | 286-300 | Clickstream, CDC lakehouse, fraud, IoT, dashboards |

## 1. Big Data Foundations and Architecture

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 1 | Explain OLTP, OLAP, HTAP, data lake, warehouse, and lakehouse. | Workload shape, storage layout, query pattern, consistency, cost, and governance. |
| 2 | Design a data platform for product analytics. | Event ingestion, schema, raw/curated zones, BI, privacy, quality, and cost. |
| 3 | Compare batch, streaming, and micro-batch processing. | Latency, throughput, correctness, operations, replay, and cost. |
| 4 | Compare Lambda architecture and Kappa architecture. | Batch correction, stream-only replay, operational complexity, and correctness. |
| 5 | Explain bronze, silver, and gold data layers. | Raw preservation, cleaning, business modeling, ownership, and retention. |
| 6 | What is data mesh and when does it help? | Domain ownership, data products, platform enablement, governance, and risks. |
| 7 | How do you define a data product? | Contract, owner, SLA, quality, documentation, access policy, and consumers. |
| 8 | How do you choose between lakehouse and warehouse-first architecture? | Data openness, BI latency, governance, cost, concurrency, and engine compatibility. |
| 9 | How do you design a canonical event model? | Naming, versioning, required fields, timestamps, identity, schema registry, and ownership. |
| 10 | What is the difference between operational events and analytical events? | Source of truth, business semantics, timing, granularity, and correction strategy. |
| 11 | How do you handle schema evolution across a data platform? | Compatibility rules, registry, table evolution, consumer rollout, and backfill. |
| 12 | How do you design data retention and archival? | Legal needs, business value, partition lifecycle, cold tiers, deletion, and cost. |
| 13 | How do you handle late-arriving data in analytics? | Event time, watermarks, correction windows, recomputation, and user communication. |
| 14 | How do you design data quality gates? | Freshness, completeness, uniqueness, validity, distribution checks, and quarantine. |
| 15 | What makes a big data architecture production-ready? | SLAs, lineage, quality, replay, observability, governance, security, DR, and cost controls. |

## 2. Kafka Fundamentals and Data Ingestion

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 16 | Explain Kafka topics, partitions, offsets, brokers, producers, and consumers. | Log abstraction, ordering, scalability, durability, and consumer independence. |
| 17 | How do Kafka partitions affect ordering and parallelism? | Ordering per partition, key choice, consumer group parallelism, hot keys, and rebalancing. |
| 18 | How do you choose a Kafka message key? | Ordering, partition distribution, joins, compaction, hot-key risk, and routing. |
| 19 | How do producer acknowledgements affect durability and latency? | `acks=0/1/all`, retries, idempotence, min ISR, and throughput trade-offs. |
| 20 | What is Kafka offset management? | Committed offsets, manual commit, batch processing, retries, and duplicate handling. |
| 21 | How do consumer groups work? | Partition assignment, parallelism, group coordination, rebalancing, and lag. |
| 22 | What is consumer lag and how do you debug it? | Offset gap, processing latency, partition skew, downstream bottleneck, and scaling. |
| 23 | Explain at-most-once, at-least-once, and exactly-once processing with Kafka. | Offset timing, duplicates, transactions, idempotent sinks, and practical limits. |
| 24 | How do you design idempotent Kafka consumers? | Event IDs, dedupe store, business idempotency, sink constraints, and replay safety. |
| 25 | What is log compaction? | Latest value per key, tombstones, changelog topics, state recovery, and retention. |
| 26 | How do Kafka retention policies work? | Time, size, compaction, delete cleanup, replay window, and storage cost. |
| 27 | How do you design Kafka topic naming and ownership? | Domain, environment, versioning, visibility, ACLs, and lifecycle. |
| 28 | How do you choose Kafka serialization format? | Avro, Protobuf, JSON, schema registry, compatibility, size, and language support. |
| 29 | How do you validate events before Kafka ingestion? | Schema validation, required fields, PII checks, DLQ, contracts, and producer feedback. |
| 30 | How do you design high-throughput Kafka producers? | Batching, compression, linger, idempotence, partitioning, retries, and backpressure. |

## 3. Kafka Scaling, Reliability, and Operations

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 31 | How do you size a Kafka cluster? | Throughput, partitions, replication factor, retention, disk, network, CPU, and growth. |
| 32 | How many partitions should a topic have? | Consumer parallelism, throughput, rebalancing overhead, file handles, and future scale. |
| 33 | Explain Kafka replication, ISR, and leader election. | Replicas, in-sync replicas, leader failover, unclean election, and data loss risk. |
| 34 | What is `min.insync.replicas` and why does it matter? | Durability, availability, producer ack behavior, broker failures, and write rejection. |
| 35 | How do you prevent Kafka data loss? | Replication, acks all, min ISR, idempotent producers, monitoring, and safe operations. |
| 36 | How do you prevent duplicate Kafka messages? | Idempotent producer, transactions, consumer idempotency, sink constraints, and retries. |
| 37 | What are Kafka transactions used for? | Atomic writes across partitions, consume-process-produce, exactly-once streams, and cost. |
| 38 | What causes Kafka consumer rebalances? | Membership changes, poll timeout, partition changes, coordinator issues, and deployment. |
| 39 | How do cooperative rebalances improve availability? | Incremental partition movement, less stop-the-world consumption, and compatibility. |
| 40 | How do you monitor Kafka in production? | Broker health, under-replicated partitions, ISR shrink, lag, request latency, disk, and controller. |
| 41 | How do you handle poison messages in Kafka? | Retry topic, DLQ, quarantine, schema checks, manual repair, and replay. |
| 42 | How do you design Kafka disaster recovery? | MirrorMaker/cluster linking, replication lag, failover, offset translation, and runbooks. |
| 43 | How do you secure Kafka? | TLS, SASL, ACLs, quotas, audit, secret rotation, and tenant isolation. |
| 44 | How do you handle hot Kafka partitions? | Better key, salting, sub-key aggregation, split topics, and consumer scaling limits. |
| 45 | Compare Kafka, Redpanda, Pulsar, and NATS JetStream. | Protocol compatibility, storage model, tenancy, geo-replication, latency, and operations. |

## 4. Kafka Connect, Debezium, CDC, and Integration

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 46 | Explain Kafka Connect architecture. | Workers, connectors, tasks, source/sink, converters, offset storage, and scaling. |
| 47 | How do source connectors track progress? | Source offsets, resume position, exactly-once source requirements, snapshots, and failure recovery. |
| 48 | How do sink connectors handle delivery guarantees? | Batching, retries, idempotent writes, DLQ, offset commits, and external system semantics. |
| 49 | How do you scale Kafka Connect connectors? | Task parallelism, partitioning, worker group, connector limits, and rebalance impact. |
| 50 | How do you design a custom Kafka Connect sink connector? | Config, task class, batching, retries, offset handling, idempotency, and observability. |
| 51 | What is Debezium and how does CDC work? | Database logs, snapshots, change events, offsets, schema history, and consistency. |
| 52 | How do Debezium snapshots work? | Initial snapshot, locks or incremental snapshot, chunking, source load, and resume. |
| 53 | How do you handle schema changes in Debezium? | DDL capture, schema history topic, compatibility, consumers, and backfill. |
| 54 | How do you handle deletes in CDC pipelines? | Tombstones, soft deletes, hard deletes, compaction, downstream semantics, and GDPR. |
| 55 | How do you maintain ordering in CDC events? | Database log order, table/topic mapping, transaction metadata, and partition key. |
| 56 | How do you design CDC from multiple databases into a lakehouse? | Connector isolation, topic design, schema registry, raw zone, ordering, and reconciliation. |
| 57 | What are common CDC failure modes? | Source log retention, connector lag, schema drift, snapshot restart, duplicates, and source pressure. |
| 58 | Compare Debezium, AWS DMS, Flink CDC, Airbyte, and Fivetran. | Control, managed operations, latency, transformation, cost, and database support. |
| 59 | How do you protect source databases during CDC? | Replica reads, throttling, snapshot windows, log retention, monitoring, and backpressure. |
| 60 | How do you test CDC correctness? | Row counts, checksums, transaction order, delete handling, replay, and reconciliation jobs. |

## 5. Flink Stream Processing Fundamentals

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 61 | Explain Flink's streaming-first execution model. | Bounded/unbounded streams, operators, tasks, parallelism, state, and checkpoints. |
| 62 | What is event time and why does it matter? | Source timestamp, late events, watermarks, deterministic windows, and correctness. |
| 63 | Compare event time, processing time, and ingestion time. | Semantics, latency, reproducibility, clock dependence, and use cases. |
| 64 | What are watermarks? | Progress signal, out-of-order tolerance, window closure, lateness, and idle sources. |
| 65 | What is keyed state in Flink? | Key partitioning, state backend, scaling, checkpoints, and state TTL. |
| 66 | What is operator state? | Non-keyed state, source offsets, redistribution, and checkpointing. |
| 67 | Compare RocksDB state backend and heap state. | Scale, latency, memory, disk, checkpoints, and tuning. |
| 68 | How do Flink checkpoints work? | Barrier alignment, state snapshots, source offsets, recovery, and exactly-once. |
| 69 | What are savepoints? | Controlled state snapshot, upgrades, migration, rollback, and operational workflow. |
| 70 | What is Flink exactly-once processing? | Checkpoints, replay, transactional sinks, idempotence, and source/sink support. |
| 71 | How do you choose Flink parallelism? | Throughput, key distribution, source partitions, state size, CPU, and backpressure. |
| 72 | What is Flink backpressure and how do you debug it? | Busy/downstream operators, buffers, checkpoint delays, metrics, and flame graphs. |
| 73 | How do you deploy Flink jobs? | Session cluster, application cluster, per-job cluster, Kubernetes, upgrades, and HA. |
| 74 | How do Flink jobs recover from failure? | Checkpoint restore, restart strategy, source replay, sink transactions, and state compatibility. |
| 75 | Compare Flink, Spark Structured Streaming, Kafka Streams, and Beam. | Latency, state, ecosystem, portability, operations, and fit. |

## 6. Windows, Deduplication, Joins, and Streaming Correctness

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 76 | Explain tumbling windows. | Fixed non-overlapping windows, event time, watermarks, late events, and aggregation. |
| 77 | Explain sliding windows. | Overlapping windows, slide interval, compute amplification, state size, and use cases. |
| 78 | Explain session windows. | Inactivity gap, user behavior, dynamic boundaries, late data, and merging. |
| 79 | What is a global window? | Unbounded grouping, triggers, memory risk, and streaming semantics. |
| 80 | How do you handle late events? | Allowed lateness, side output, corrections, retractions, and business policy. |
| 81 | How do you design streaming deduplication? | Event ID, keyed state, TTL, watermark, exactly-once limits, and replay behavior. |
| 82 | How do you deduplicate without a unique event ID? | Natural key, hash, time window, probabilistic structures, and false positives. |
| 83 | How do stream-stream joins work? | Event-time bounds, state retention, watermarks, late matches, and memory growth. |
| 84 | How do stream-table joins work? | Enrichment, temporal table, changelog, state consistency, and update behavior. |
| 85 | How do you design fraud detection over streams? | Low latency, keyed state, sliding windows, enrichment, alerts, and false positives. |
| 86 | How do you count unique users in streaming? | Exact set, HyperLogLog, windowing, state size, accuracy, and mergeability. |
| 87 | How do you compute rolling metrics? | Sliding windows, incremental aggregation, state TTL, late corrections, and output cadence. |
| 88 | What is a trigger in streaming windows? | Early/on-time/late firing, completeness, latency, and duplicate updates. |
| 89 | How do you handle retractions or corrections in streams? | Changelog mode, upsert sink, downstream semantics, and BI expectations. |
| 90 | How do you test streaming correctness? | Deterministic event-time tests, late data, duplicates, replay, checkpoint recovery, and golden outputs. |

## 7. Spark, Beam, and Distributed Compute

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 91 | Explain Spark architecture. | Driver, executors, tasks, stages, DAG, shuffle, cluster manager, and storage. |
| 92 | Compare RDD, DataFrame, and Dataset. | Abstraction, optimization, type safety, performance, and use cases. |
| 93 | What is Spark shuffle and why is it expensive? | Data movement, partitioning, spill, skew, network, and optimization. |
| 94 | How do you handle data skew in Spark? | Salting, skew join hints, repartitioning, broadcast joins, and pre-aggregation. |
| 95 | What is a broadcast join? | Small table broadcast, memory limits, avoiding shuffle, and correctness. |
| 96 | How do Spark caching and persistence work? | Memory/disk levels, recomputation, eviction, lineage, and misuse. |
| 97 | How do you tune Spark jobs? | Partitions, executor sizing, shuffle, file sizes, serialization, skew, and adaptive execution. |
| 98 | Explain Spark Structured Streaming. | Micro-batch, checkpointing, triggers, output modes, state, and watermarks. |
| 99 | Compare Spark Structured Streaming and Flink. | Latency, state, event time, ecosystem, operations, and batch integration. |
| 100 | What is Apache Beam? | Unified model, portability, runners, windowing, triggers, and trade-offs. |
| 101 | When would you choose Beam over Spark or Flink APIs directly? | Portability, unified semantics, team abstraction, runner lock-in, and feature gaps. |
| 102 | How do distributed compute engines recover failed tasks? | Lineage, retry, checkpoint, speculative execution, idempotent output, and side effects. |
| 103 | How do you prevent duplicate output in Spark jobs? | Atomic commit protocols, output paths, idempotent writes, job IDs, and cleanup. |
| 104 | How do you design Spark on Kubernetes? | Driver/executor pods, resource requests, shuffle storage, autoscaling, and observability. |
| 105 | How do you choose between Spark, Flink, SQL engines, and warehouses for transformations? | Latency, data size, state, SQL complexity, cost, skills, and governance. |

## 8. S3/Object Storage, File Formats, and Table Layout

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 106 | Why is S3 commonly used as a data lake storage layer? | Durability, scale, cost, separation of storage/compute, lifecycle, and object semantics. |
| 107 | What object storage semantics matter for data lakes? | Object immutability pattern, listing, consistency, rename cost, multipart upload, and eventual operations. |
| 108 | Compare Parquet, ORC, Avro, JSON, CSV, and Protobuf. | Columnar vs row, schema, compression, splittability, compatibility, and use cases. |
| 109 | Why is Parquet popular for analytics? | Column pruning, predicate pushdown, compression, nested data, and engine support. |
| 110 | How do you choose compression codec? | ZSTD, Snappy, Gzip, CPU, compression ratio, splittability, and query cost. |
| 111 | How do you design S3 prefixes and paths? | Zone, domain, table, partition, version, environment, and access pattern. |
| 112 | How do partitions differ from folders in object storage? | Metadata concept, pruning, file layout, query planning, and catalog registration. |
| 113 | How do you choose partition columns for lake tables? | Query predicates, cardinality, skew, evolution, small files, and pruning. |
| 114 | What is the small-file problem? | Metadata overhead, planning latency, object store requests, inefficient scans, and compaction. |
| 115 | How do you design compaction? | File size target, clustering, scheduling, isolation, cost, and concurrent reads/writes. |
| 116 | What is bucketing or clustering in data lakes? | Co-location, join optimization, sort order, data skipping, and maintenance. |
| 117 | How do you handle raw immutable data? | Append-only storage, provenance, schema capture, replay, retention, and access control. |
| 118 | How do you design lifecycle policies for lake data? | Hot/warm/cold tiers, expiration, archival, legal hold, and restore latency. |
| 119 | How do you encrypt data lake storage? | KMS, bucket policies, per-tenant keys, access logs, and key rotation. |
| 120 | How do you monitor object-storage data lake cost? | Storage class, request count, scan bytes, compaction cost, egress, and orphan files. |

## 9. Lakehouse Formats: Iceberg, Hudi, and Delta

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 121 | What problem do lakehouse table formats solve? | ACID metadata, snapshots, schema evolution, partition evolution, time travel, and multi-engine reads. |
| 122 | Explain Apache Iceberg snapshots and metadata. | Snapshot pointer, manifests, manifest lists, data/delete files, planning, and rollback. |
| 123 | What is Iceberg hidden partitioning? | Logical transforms, query pruning, avoiding user-visible partition columns, and evolution. |
| 124 | What is Iceberg partition evolution? | Changing layout safely, old/new files coexisting, planning, and migration. |
| 125 | How does Iceberg handle schema evolution? | Add/drop/rename/reorder, field IDs, compatibility, and reader behavior. |
| 126 | What are Iceberg position deletes and equality deletes? | Row-level deletes, merge-on-read cost, compaction, and engine support. |
| 127 | Explain Apache Hudi copy-on-write vs merge-on-read. | Read/write trade-off, compaction, latency, file groups, and query engines. |
| 128 | What are Hudi upserts and incremental pulls? | Record keys, precombine field, timeline, indexes, CDC-like consumption, and compaction. |
| 129 | Compare Iceberg, Hudi, and Delta Lake. | Metadata model, upserts, streaming, engine support, governance, operations, and ecosystem. |
| 130 | How do lakehouse formats implement time travel? | Snapshots/timeline/log, retention, rollback, reproducibility, and storage cleanup. |
| 131 | What is vacuum or snapshot expiration risk? | Time travel loss, active readers, streaming jobs, orphan cleanup, and retention policy. |
| 132 | How do you handle concurrent writers to lakehouse tables? | Optimistic commits, conflict detection, retries, isolation, and catalog consistency. |
| 133 | How do you design lakehouse tables for CDC upserts? | Primary key, merge strategy, deletes, compaction, clustering, and freshness. |
| 134 | How do you migrate Hive tables to Iceberg or Hudi? | Metadata import, rewrite, validation, dual reads, compatibility, and rollback. |
| 135 | How do you operate lakehouse maintenance jobs? | Compaction, clustering, manifest rewrite, vacuum, metrics, scheduling, and cost. |

## 10. Catalogs, Governance, Lineage, and Data Discovery

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 136 | What is a data catalog? | Table discovery, schemas, ownership, metadata, permissions, lineage, and search. |
| 137 | Compare Hive Metastore, AWS Glue Catalog, Iceberg REST Catalog, Nessie, Polaris, and Gravitino. | Engine support, governance, branching, multi-cloud, maturity, and operations. |
| 138 | What is the role of Hive Metastore? | Table metadata, partitions, schemas, compatibility, scaling limits, and migration. |
| 139 | How does AWS Glue Data Catalog fit with Athena and lakehouse tables? | Metadata, crawlers, permissions, integrations, schema updates, and governance. |
| 140 | What is catalog fragmentation? | Multiple sources of metadata truth, inconsistent permissions, stale schemas, and operational risk. |
| 141 | How do you design data lineage? | Column/table/job lineage, OpenLineage, producer/consumer mapping, impact analysis, and trust. |
| 142 | How do you design data discovery? | Search, tags, ownership, docs, sample queries, freshness, and access workflow. |
| 143 | How do you track data ownership? | Domain owner, steward, SLA, on-call, contract, escalation, and lifecycle. |
| 144 | What is data classification? | PII, PHI, PCI, sensitivity tags, access policy, masking, and retention. |
| 145 | How do you enforce lake permissions? | IAM, Lake Formation/Ranger, table/column/row policies, audit, and cross-engine consistency. |
| 146 | What is metadata scalability? | Partition count, table count, manifest count, cache, API limits, and planning latency. |
| 147 | How do you design schema registry governance? | Compatibility modes, ownership, approval, evolution, and consumer visibility. |
| 148 | How do you manage data contracts? | Producer schema, semantic expectations, quality tests, versioning, and breaking-change workflow. |
| 149 | How do you audit data access? | Query logs, table access, row/column policies, identity mapping, and anomaly detection. |
| 150 | How do you measure trust in a dataset? | Freshness, quality score, owner, lineage, usage, incident history, and SLA compliance. |

## 11. Warehouses and SQL Engines: Redshift, Athena, Hive, and Trino

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 151 | Compare Redshift, Athena, Trino, Hive, Snowflake, BigQuery, and Databricks SQL. | Storage model, compute model, concurrency, cost, governance, latency, and operations. |
| 152 | How does MPP query execution work? | Distributed planning, scan, shuffle, join, aggregation, data distribution, and spilling. |
| 153 | How do you tune Redshift tables? | Distribution style, sort keys, compression, vacuum/analyze, workload management, and concurrency. |
| 154 | What is Redshift Spectrum? | External S3 queries, Glue catalog, file format, partition pruning, cost, and performance. |
| 155 | How do you optimize Athena queries? | Partition pruning, Parquet/ORC, compression, file size, projection, and scanned bytes. |
| 156 | What is Athena partition projection? | Avoid catalog partition explosion, computed partition metadata, path templates, and limitations. |
| 157 | What role does Hive play in modern data platforms? | SQL engine legacy, Metastore, table layout, batch jobs, and migration. |
| 158 | How do Hive partitions and bucketing work? | Directory layout, pruning, join optimization, skew, and maintenance. |
| 159 | When would you choose Trino or Presto? | Federated SQL, interactive analytics, multi-source joins, lakehouse querying, and cluster tuning. |
| 160 | What is predicate pushdown? | Filtering at storage/source, reduced IO, connector support, and query plan inspection. |
| 161 | What is column pruning? | Reading only needed columns, columnar formats, scan reduction, and schema design. |
| 162 | How do you debug slow SQL analytics queries? | Explain plan, scan bytes, skew, joins, partitions, spills, concurrency, and stats. |
| 163 | How do workload management queues work? | Concurrency control, priorities, memory, admission, isolation, and SLA tiers. |
| 164 | How do materialized views help analytics? | Precomputation, freshness, refresh cost, query rewrite, and invalidation. |
| 165 | How do you control SQL analytics cost? | Scan reduction, caching, result reuse, workload limits, table layout, and user education. |

## 12. Real-Time OLAP: Pinot, ClickHouse, Druid, and StarRocks

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 166 | When do you need a real-time OLAP serving store? | Low-latency dashboards, high concurrency, fresh data, aggregations, and user-facing analytics. |
| 167 | Compare Apache Pinot, ClickHouse, Druid, StarRocks, and Apache Doris. | Ingestion, query latency, indexes, rollups, joins, operations, and ecosystem. |
| 168 | How does Pinot serve real-time analytics? | Real-time/offline tables, segments, brokers, servers, controllers, and Kafka ingestion. |
| 169 | How does ClickHouse achieve high analytical performance? | Columnar storage, vectorized execution, sparse indexes, merges, compression, and distributed tables. |
| 170 | How do Druid segments and rollups work? | Time chunks, immutable segments, ingestion, rollup, indexing, and query serving. |
| 171 | How do you design real-time ingestion into OLAP stores? | Kafka source, schema, partitioning, segment size, late data, and exactly-once expectations. |
| 172 | How do you design indexes for Pinot or ClickHouse? | Inverted, range, text, bloom, sorted keys, skip indexes, and query pattern. |
| 173 | What is pre-aggregation or rollup? | Lower storage/query cost, lost granularity, dimension choice, and correction strategy. |
| 174 | How do you handle high-cardinality dimensions? | Dictionary size, index strategy, memory, query shape, and approximate aggregation. |
| 175 | How do you design a user-facing analytics dashboard? | Freshness, concurrency, pre-aggregation, caching, authorization, and p99 latency. |
| 176 | How do you handle late or corrected events in real-time OLAP? | Upserts, mutable segments, reingestion, correction tables, and user semantics. |
| 177 | How do you scale query concurrency in OLAP stores? | Brokers/coordinators, replicas, resource groups, query limits, cache, and workload isolation. |
| 178 | How do you monitor Pinot or ClickHouse? | Ingestion lag, segment health, query latency, memory, merges, disk, and error rates. |
| 179 | How do you choose between OLAP store and warehouse for dashboards? | Latency, concurrency, freshness, data model, cost, and operational complexity. |
| 180 | How do you migrate dashboards from warehouse to real-time OLAP? | Query analysis, model redesign, dual-run, validation, freshness, and rollback. |

## 13. ETL, ELT, dbt, SQLMesh, and Data Quality

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 181 | Compare ETL and ELT. | Transformation location, raw preservation, governance, cost, flexibility, and tooling. |
| 182 | How do you design an ELT pipeline? | Raw ingestion, staging, transformations, tests, lineage, deployment, and rollback. |
| 183 | What is dbt used for? | SQL models, tests, documentation, lineage, environments, and analytics engineering workflow. |
| 184 | What is SQLMesh and when is it useful? | Environment-aware planning, impact analysis, backfills, model versions, and safe rollout. |
| 185 | How do you design data quality tests? | Not-null, uniqueness, referential integrity, freshness, ranges, distributions, and anomaly detection. |
| 186 | How do you handle bad data in pipelines? | Quarantine, DLQ, rejection, correction workflow, alerts, and reprocessing. |
| 187 | What is schema drift? | Producer changes, ingestion breakage, loose formats, detection, compatibility, and contracts. |
| 188 | How do you design data validation at ingestion vs transformation? | Fast rejection, raw preservation, business rules, layered quality, and cost. |
| 189 | What is a data contract? | Schema, semantics, ownership, SLA, quality, versioning, and breaking-change policy. |
| 190 | How do you deploy transformation changes safely? | Dev/prod environments, CI tests, sample validation, backfill planning, and rollback. |
| 191 | How do you handle slowly changing dimensions? | Type 1/2/3, effective dates, surrogate keys, history, and query complexity. |
| 192 | How do you design incremental transformations? | Watermarks, change capture, idempotency, late data, merge, and state tracking. |
| 193 | How do you make data transformations idempotent? | Deterministic output, overwrite partitions, merge keys, run IDs, and cleanup. |
| 194 | What is semantic layer architecture? | Metric definitions, dimensions, governance, BI consistency, and performance. |
| 195 | How do you prevent metric drift across teams? | Central definitions, ownership, tests, documentation, review, and lineage. |

## 14. Orchestration: Airflow, Temporal, Dagster, Prefect, and Argo

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 196 | What problem does orchestration solve? | Dependencies, scheduling, retries, backfills, visibility, state, and operations. |
| 197 | Explain Airflow DAGs, tasks, operators, sensors, and executors. | Scheduling model, metadata DB, workers, retries, pools, and observability. |
| 198 | How do you design Airflow DAGs for reliability? | Idempotent tasks, retries, timeouts, SLAs, pools, task isolation, and alerting. |
| 199 | How do you handle Airflow backfills? | Catchup, data intervals, partitioned outputs, idempotency, resource limits, and validation. |
| 200 | What are Airflow sensors and deferrable operators? | Waiting, worker slot usage, event-based triggers, scaling, and latency. |
| 201 | When would you choose Temporal over Airflow? | Long-running durable workflows, activities, retries, signals, state, and business process orchestration. |
| 202 | How do Temporal workflows differ from normal code? | Deterministic workflow code, activity side effects, replay, timers, and versioning. |
| 203 | How do you handle retries in Temporal? | Activity retry policy, workflow-level decisions, idempotency, and compensation. |
| 204 | When would you choose Dagster? | Asset-oriented orchestration, lineage, partitions, type checks, local development, and data assets. |
| 205 | When would you choose Prefect? | Pythonic workflows, dynamic tasks, operational simplicity, and cloud-managed options. |
| 206 | When would you choose Argo Workflows? | Kubernetes-native jobs, containerized tasks, DAG/steps, artifacts, and platform integration. |
| 207 | How do you design workflow cancellation? | State cleanup, idempotent activities, compensation, partial output handling, and user visibility. |
| 208 | How do you avoid duplicate side effects in orchestrated workflows? | Idempotency keys, external state checks, transactional writes, retries, and run IDs. |
| 209 | How do you monitor orchestration systems? | Failed tasks, duration, queue time, retries, SLA misses, scheduler health, and worker capacity. |
| 210 | Compare Airflow, Temporal, Dagster, Prefect, and Argo. | Batch scheduling, durable workflows, assets, dynamic Python flows, Kubernetes jobs, and fit. |

## 15. Backfills, Reprocessing, Replay, and Migration

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 211 | What is a backfill and why is it risky? | Historical recomputation, resource impact, correctness, idempotency, and downstream effects. |
| 212 | How do you design safe backfills? | Partitioning, throttling, validation, isolation, checkpointing, rollback, and communication. |
| 213 | How do you replay Kafka data into a new pipeline? | Consumer group, offsets, retention, side effects, idempotent sink, and rate control. |
| 214 | How do you reprocess data after a bug? | Identify affected range, freeze writes if needed, recompute, validate, publish, and audit. |
| 215 | How do you dual-run old and new pipelines? | Parallel outputs, comparison, cutover, monitoring, rollback, and cost. |
| 216 | How do you validate migration correctness? | Row counts, checksums, aggregates, sampling, business metrics, and reconciliation. |
| 217 | How do you backfill lakehouse tables with concurrent readers? | Snapshot isolation, new table then swap, partition overwrite, validation, and rollback. |
| 218 | How do you backfill streaming state? | Bootstrap from history, savepoint, state migration, changelog replay, and downtime planning. |
| 219 | How do you handle source data corrections? | Correction events, CDC updates, merge, retractions, versioned facts, and communication. |
| 220 | How do you make replay safe for external systems? | Side-effect suppression, idempotency, dry-run mode, sandbox sink, and dedupe. |
| 221 | How do you handle Kafka retention limits during replay? | Tiered storage, archival raw data, S3 landing, backup topics, and replay strategy. |
| 222 | How do you migrate from Hive tables to lakehouse formats? | Inventory, convert/import, rewrite, engine validation, permissions, and phased cutover. |
| 223 | How do you migrate from batch to streaming? | Parallel stream path, correctness comparison, late data policy, state, and operational readiness. |
| 224 | How do you migrate from warehouse-only to lakehouse-plus-serving architecture? | Workload split, catalog, governance, replication, BI compatibility, and cost. |
| 225 | How do you document backfill runbooks? | Preconditions, commands, resource limits, validation queries, rollback, and owner escalation. |

## 16. Analytics Data Modeling and Metrics Platforms

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 226 | Explain facts, dimensions, measures, and grains. | Star schema, event grain, aggregation correctness, and BI usability. |
| 227 | How do you choose the grain of a fact table? | Business process, uniqueness, query needs, storage, and future aggregations. |
| 228 | How do you model user activity events? | Actor, action, object, timestamp, context, session, device, and schema evolution. |
| 229 | How do you model sessions? | Timeout gap, cross-device behavior, late events, attribution, and recomputation. |
| 230 | How do you design a metrics store? | Definitions, dimensions, rollups, freshness, query API, permissions, and lineage. |
| 231 | How do you design a feature store? | Offline/online consistency, point-in-time joins, freshness, training-serving skew, and monitoring. |
| 232 | What is point-in-time correctness? | Avoid future leakage, event timestamps, feature snapshots, and ML training validity. |
| 233 | How do you design attribution models? | Touchpoints, windows, identity stitching, late events, and business semantics. |
| 234 | How do you model slowly changing dimensions in analytics? | Type 2 history, effective dates, surrogate keys, and query patterns. |
| 235 | How do you design a customer 360 table? | Identity resolution, source precedence, freshness, privacy, and conflict resolution. |
| 236 | How do you design metrics for experimentation? | Assignment, exposure, guardrails, delayed metrics, variance, and data quality. |
| 237 | How do you avoid double counting in analytics? | Unique keys, deduplication, grain clarity, joins, and idempotent ingestion. |
| 238 | How do you model nested or semi-structured data? | Flattening, nested columns, schema-on-read, query cost, and evolution. |
| 239 | How do you design aggregated tables? | Rollup grain, refresh cadence, partitioning, invalidation, and drill-down. |
| 240 | How do you design a semantic metrics layer? | Central metric definitions, dimensions, governance, API, BI integration, and tests. |

## 17. Performance, Scaling, Skew, and Cost Optimization

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 241 | How do you diagnose a slow data pipeline? | Stage timing, shuffle, skew, IO, source/sink bottlenecks, retries, and cluster resources. |
| 242 | What is data skew and how do you fix it? | Hot keys, salting, repartitioning, custom partitioner, broadcast, and pre-aggregation. |
| 243 | How do you optimize joins at scale? | Broadcast, sort-merge, shuffle hash, bucketing, partitioning, and join order. |
| 244 | How do you optimize file sizes? | Target size, compaction, writer batching, partition cardinality, and scan efficiency. |
| 245 | How do you optimize partition pruning? | Query predicates, partition transforms, metadata, hidden partitioning, and stats. |
| 246 | How do you reduce scanned bytes? | Columnar formats, column pruning, compression, partitioning, materialized views, and filters. |
| 247 | How do you reduce shuffle cost? | Partitioning, map-side aggregation, broadcast, bucketing, and query rewrite. |
| 248 | How do you tune streaming latency vs throughput? | Batch size, checkpoint interval, state backend, parallelism, sink latency, and backpressure. |
| 249 | How do checkpoints affect performance? | State size, interval, alignment, storage, incremental checkpoints, and recovery time. |
| 250 | How do you design autoscaling for data systems? | Queue lag, CPU, memory, checkpoint duration, workload windows, and cost guardrails. |
| 251 | How do you control cloud data costs? | Storage tiers, scan bytes, compute scheduling, spot/preemptible, compaction, and query limits. |
| 252 | How do you optimize Redshift or warehouse cost? | Workload management, materialized views, distribution/sort keys, concurrency, and reserved capacity. |
| 253 | How do you optimize real-time OLAP cost? | Rollups, retention, segment sizing, replicas, indexes, and query limits. |
| 254 | How do you optimize Kafka cost? | Retention, compression, partitions, replication factor, tiered storage, and producer batching. |
| 255 | How do you design cost attribution for data platforms? | Tags, per-tenant usage, query logs, pipeline ownership, chargeback, and budgets. |

## 18. Reliability, Observability, and Data SRE

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 256 | What are data SLAs and SLOs? | Freshness, completeness, accuracy, availability, latency, and ownership. |
| 257 | How do you monitor data freshness? | Expected arrival, watermark, partition completeness, dashboards, and alerts. |
| 258 | How do you monitor data completeness? | Counts, source comparison, missing partitions, checksums, and anomaly detection. |
| 259 | How do you monitor streaming pipelines? | Lag, throughput, watermarks, checkpoint health, backpressure, DLQ, and error rate. |
| 260 | How do you monitor batch pipelines? | Duration, retries, failed partitions, SLA misses, output validation, and resource usage. |
| 261 | What is a data incident? | Incorrect, late, missing, duplicated, exposed, or inaccessible data and user impact. |
| 262 | How do you run a data incident response? | Triage, blast radius, stop bad writes, rollback, repair, communicate, and postmortem. |
| 263 | How do you design data pipeline runbooks? | Symptoms, dashboards, commands, rollback, replay, owners, and escalation. |
| 264 | How do you alert on Kafka Connect failures? | Connector/task status, lag, DLQ rate, retries, source offsets, and worker health. |
| 265 | How do you alert on Flink failures? | Restarts, checkpoint failures, backpressure, lag, watermark stalls, and state growth. |
| 266 | How do you detect silent data corruption? | Invariants, checksums, reconciliation, distribution drift, canaries, and audit queries. |
| 267 | How do you design lineage-based impact analysis? | Upstream/downstream graph, column lineage, owner mapping, and incident blast radius. |
| 268 | What is data observability? | Freshness, volume, schema, distribution, lineage, quality, and operational signals. |
| 269 | How do you verify disaster recovery for data platforms? | Restore tests, replay drills, catalog backup, checkpoint restore, and RPO/RTO evidence. |
| 270 | How do you write a strong data postmortem? | Timeline, impact, root causes, detection gap, repair, prevention, owners, and deadlines. |

## 19. Security, Privacy, Compliance, and Multi-Tenancy

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 271 | How do you secure a data lake? | IAM, bucket policies, encryption, catalog permissions, network controls, and audit logs. |
| 272 | How do you handle PII in streaming pipelines? | Classification, minimization, masking, tokenization, encryption, and deletion propagation. |
| 273 | How do you implement row-level and column-level security? | Policy engine, catalog integration, query engine enforcement, masking, and tests. |
| 274 | How do you design tenant isolation in analytics platforms? | Storage, catalog, compute, quotas, encryption keys, and audit separation. |
| 275 | How do you handle GDPR/CCPA deletion in lakehouse tables? | Identity mapping, delete files/merge, compaction, backups, audit, and downstream propagation. |
| 276 | How do you prevent data leakage through derived tables? | Lineage, classification propagation, policy inheritance, masking, and review. |
| 277 | How do you secure Kafka? | TLS, SASL, ACLs, topic naming, quotas, audit, and secret rotation. |
| 278 | How do you secure Kafka Connect and connectors? | Secret management, connector permissions, network egress, plugin vetting, and DLQ access. |
| 279 | How do you secure Airflow or orchestration systems? | RBAC, connection secrets, DAG review, task isolation, audit, and least privilege. |
| 280 | How do you design data residency controls? | Regional storage, processing boundaries, routing, replication rules, and compliance evidence. |
| 281 | How do you classify and tag sensitive data automatically? | Scanners, schema rules, ML detection, manual review, and false positive handling. |
| 282 | How do you design audit trails for analytics access? | Query logs, identity, table/column access, exports, retention, and anomaly detection. |
| 283 | How do you prevent analysts from running destructive or expensive queries? | Permissions, query limits, workgroups, sandbox, approvals, and guardrails. |
| 284 | How do you handle secrets in data pipelines? | Secret stores, rotation, scoped credentials, no logs, and environment separation. |
| 285 | How do you design compliance-ready data governance? | Policies, ownership, classification, lineage, access reviews, retention, and evidence. |

## 20. End-to-End Big Data Architecture Scenarios

| # | Problem Statement | Deep-Dive Focus |
|---:|---|---|
| 286 | Design a clickstream analytics platform. | Kafka, schema registry, S3 raw zone, Flink/Spark, Iceberg/Hudi, Athena/Trino, Pinot/ClickHouse, quality, and cost. |
| 287 | Design CDC from PostgreSQL to S3 lakehouse and real-time dashboard. | Debezium, Kafka Connect, schema evolution, deletes, Iceberg/Hudi merge, ClickHouse/Pinot serving, and reconciliation. |
| 288 | Design real-time fraud detection. | Kafka, Flink, sliding windows, state, feature enrichment, alerts, exactly-once, and false positives. |
| 289 | Design IoT telemetry ingestion and analytics. | High cardinality, partitioning, Kafka/MQTT, Flink, time-series rollups, lake storage, and late data. |
| 290 | Design log analytics like Datadog or Splunk. | Ingestion agents, Kafka, parsing, indexing, storage tiers, search, retention, and multi-tenancy. |
| 291 | Design a metrics pipeline for millions of services. | Aggregation, cardinality control, rollups, remote write, retention, alerts, and query scale. |
| 292 | Design a recommendation feature pipeline. | Offline features, streaming features, point-in-time correctness, feature store, freshness, and monitoring. |
| 293 | Design a marketing attribution pipeline. | Identity stitching, event ordering, attribution windows, late events, deduplication, and BI model. |
| 294 | Design an enterprise data lake migration from Hive to Iceberg. | Inventory, conversion, catalog, permissions, dual-run, validation, maintenance jobs, and rollback. |
| 295 | Design a near-real-time executive dashboard. | Ingestion, stream aggregation, OLAP serving, cache, row-level security, freshness SLA, and drill-down. |
| 296 | Design a data quality platform. | Rule engine, profiling, tests, anomaly detection, lineage, alerting, quarantine, and ownership. |
| 297 | Design a data catalog and governance platform. | Metadata ingestion, lineage, ownership, access workflow, classification, search, and audit. |
| 298 | Design a backfill platform for all historical data. | Job planning, partitioning, throttling, checkpoints, validation, isolation, and cost controls. |
| 299 | Design a multi-tenant lakehouse platform. | Tenant isolation, quotas, catalogs, compute pools, encryption, cost attribution, and noisy-neighbor control. |
| 300 | Design a world-class data platform for a large enterprise. | Domains, ingestion, lakehouse, warehouse, real-time OLAP, orchestration, governance, observability, security, DR, and cost. |

## Interview Answer Framework

For every big data answer, use this structure:

1. Workload: batch, streaming, CDC, interactive SQL, dashboard, ML, or governance.
2. Volume: events/sec, TB/day, retention, concurrency, and freshness SLA.
3. Ingestion: Kafka, CDC, files, APIs, logs, or managed connectors.
4. Storage: object store, lakehouse table format, warehouse, real-time OLAP, or feature store.
5. Compute: Flink, Spark, Beam, SQL engine, dbt, or warehouse-native transforms.
6. Correctness: ordering, deduplication, late data, schema evolution, idempotency, replay, and reconciliation.
7. Operations: orchestration, observability, data quality, lineage, security, DR, and cost.

## High-Frequency Deep-Dive Chains

- Kafka -> partitions -> consumer groups -> offsets -> lag -> rebalancing -> exactly-once -> DLQ.
- Kafka Connect -> source offsets -> Debezium snapshot -> schema history -> deletes -> sink idempotency.
- Flink -> event time -> watermarks -> tumbling/sliding/session windows -> state TTL -> checkpoints -> savepoints.
- S3 -> Parquet -> partitioning -> small files -> compaction -> Iceberg/Hudi -> catalog -> Athena/Trino.
- Iceberg -> snapshots -> manifests -> hidden partitioning -> partition evolution -> time travel -> vacuum.
- Hudi -> upserts -> copy-on-write vs merge-on-read -> indexing -> compaction -> incremental pull.
- Redshift/Athena/Trino -> query plan -> scan bytes -> partition pruning -> joins -> workload management.
- Pinot/ClickHouse -> Kafka ingestion -> segment/part layout -> indexing -> rollups -> dashboard p99 latency.
- Airflow -> DAG schedule -> retries -> backfill -> idempotent tasks -> SLA -> incident runbook.
- Temporal -> durable workflow -> activity retries -> deterministic replay -> compensation -> long-running process.
