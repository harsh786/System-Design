# Big Data, Lakehouse, and Analytics Architecture

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---


## Big Data Foundation

- OLTP vs OLAP.
- Data lake vs warehouse vs lakehouse.
- Data mesh.
- Batch vs streaming.
- ETL vs ELT.
- Lambda vs Kappa architecture.
- CDC.
- Data quality.
- Data lineage.
- Data governance.
- PII and compliance.

## Frameworks

### Kafka

- Event ingestion.
- Replayable logs.
- Stream source for analytics.

### Redpanda

- Kafka-compatible streaming platform.
- Useful when teams want Kafka protocol compatibility with a different operational model.
- Know compatibility, partitioning, consumer groups, and operational trade-offs.

### Apache Pulsar

- Pub/sub and streaming with separated compute and storage.
- Topics, partitions, subscriptions, tenants, namespaces.
- Useful for multi-tenant messaging and geo-replication discussions.

### NATS JetStream

- Lightweight messaging and streaming.
- Useful for low-latency service messaging and simpler operational footprints.

### Spark

- Batch processing.
- Spark SQL.
- DataFrames.
- Structured Streaming.
- Shuffle optimization.
- Skew handling.
- Broadcast joins.
- Caching and persistence.

### Flink

- Stateful stream processing.
- Event time.
- Watermarks.
- Checkpoints.
- Savepoints.
- Exactly-once processing.
- Low-latency streaming.

### Apache Beam

- Unified batch and streaming programming model.
- Portable pipelines across runners such as Flink, Spark, and cloud runners.
- Useful for interviews about portability vs runner-specific optimization.

### Kafka Streams

- JVM library for stream processing directly on Kafka.
- Good for service-owned stream processing.
- Compare with Flink for stateful, large-scale, operationally centralized stream processing.

### Airflow

- DAG orchestration.
- Scheduling.
- Retries.
- Backfills.
- SLA monitoring.

### Dagster

- Asset-oriented orchestration.
- Strong for data assets, lineage, testing, and local development.

### Prefect

- Python-first workflow orchestration.
- Dynamic workflows and operational simplicity.

### Argo Workflows

- Kubernetes-native workflow orchestration.
- Useful when batch/data jobs run as containers on Kubernetes.

### dbt

- SQL transformations.
- Data tests.
- Documentation.
- Lineage.

### SQLMesh

- SQL transformation framework with environment-aware planning.
- Useful for safe data model changes and impact analysis.

### Great Expectations / Soda / Deequ

- Data quality testing.
- Validate freshness, completeness, uniqueness, ranges, nulls, and distribution drift.

### Trino/Presto

- Federated SQL.
- Interactive analytics.
- Querying data lakes.

### Athena / BigQuery External Tables / Snowflake External Tables

- Managed query access over object-storage data.
- Important for cost, governance, and managed-vs-open architecture discussions.

### Lakehouse Formats

- Apache Iceberg.
- Delta Lake.
- Apache Hudi.

### Lakehouse Catalogs and Governance

- Hive Metastore.
- AWS Glue Data Catalog.
- Iceberg REST Catalog.
- Project Nessie.
- Unity Catalog.
- Apache Polaris.
- Apache Gravitino.
- Apache Ranger.
- AWS Lake Formation.

Architect focus:

- Catalog is the control plane for table discovery, permissions, and metadata.
- Choose catalog strategy based on engine compatibility, governance, multi-cloud needs, and operational maturity.
- Avoid catalog fragmentation where different engines see different truth.

### OLAP Serving

- ClickHouse.
- Apache Pinot.
- Apache Druid.
- StarRocks.
- Apache Doris.
- DuckDB for embedded/local analytics.

### Data Warehouses

- Redshift.
- Snowflake.
- BigQuery.
- Databricks SQL.
- Synapse/Fabric-style enterprise analytics platforms where Microsoft ecosystem matters.

### CDC and Ingestion Frameworks

- Kafka Connect.
- Debezium.
- Flink CDC.
- AWS DMS.
- Apache NiFi.
- Airbyte.
- Fivetran.
- Fluent Bit / Fluentd / Logstash for logs.

Architect focus:

- Snapshot plus ongoing CDC.
- Schema evolution.
- Ordering.
- Exactly-once vs at-least-once.
- Backfill and replay.
- Source load.
- Delete handling.
- PII filtering.

### Data Lake Storage and File Formats

- Object storage: S3, GCS, ADLS, MinIO.
- File formats: Parquet, ORC, Avro, JSON, CSV, Protobuf.
- Compression: ZSTD, Snappy, Gzip.
- Table layout: partitioning, bucketing, clustering, sort order.
- Small-file mitigation: compaction, batching, clustering.

### Data Catalog, Lineage, and Discovery

- DataHub.
- OpenMetadata.
- Apache Atlas.
- Amundsen.
- OpenLineage.
- Marquez.

Architect focus:

- Ownership.
- Lineage.
- Documentation.
- Search/discovery.
- PII tagging.
- Freshness and quality metadata.
- Access workflow.

### Data Versioning and Reproducibility

- LakeFS.
- Iceberg snapshots/time travel.
- Delta time travel.
- Hudi timeline.
- Reproducible backfills.
- Rollback after bad data loads.

### Feature Store and ML Data

- Feast.
- Tecton-style managed feature platforms.
- Online/offline feature consistency.
- Point-in-time correctness.
- Feature freshness.
- Training-serving skew.

## Big Data Capstone

Build a clickstream analytics platform:

1. Ingest events through Kafka.
2. Validate schemas.
3. Store raw events in object storage.
4. Process batch with Spark.
5. Process streaming with Flink or Spark Structured Streaming.
6. Store curated tables in Iceberg/Delta/Hudi.
7. Query with Trino.
8. Serve real-time dashboard from ClickHouse/Pinot.
9. Add data quality checks.
10. Add lineage, monitoring, and cost controls.

## Missing Big Data and Lakehouse Architect Checklist

### Storage Layer

- Object storage layout: raw, bronze, silver, gold.
- File format choice: Parquet/ORC for analytics, Avro/Protobuf for event interchange.
- Compression and block size.
- Partitioning and sort order.
- Small-file strategy.
- Lifecycle and retention.
- Encryption and access policies.

### Table Format Layer

- Iceberg snapshots, manifests, metadata files.
- Iceberg hidden partitioning and partition evolution.
- Hudi copy-on-write vs merge-on-read.
- Delta transaction log and optimize/vacuum concepts.
- Schema evolution.
- Time travel.
- Rollback.
- Compaction and clustering.

Context7 check: Apache Iceberg docs emphasize schema evolution without rewriting existing data files, hidden partitioning, partition layout evolution, snapshots/time travel, rollback, and manifests for planning and fast appends.

### Catalog and Governance Layer

- Catalog choice: Hive Metastore, Glue, REST Catalog, Nessie, Unity Catalog, Polaris, Gravitino.
- Authorization: Ranger, Lake Formation, Unity Catalog-style controls.
- Data discovery: DataHub, OpenMetadata, Atlas, Amundsen.
- Lineage: OpenLineage/Marquez.
- Data contracts and ownership.
- PII classification and audit.

### Processing Layer

- Batch: Spark, Flink batch, Beam, dbt, SQLMesh.
- Streaming: Flink, Kafka Streams, Spark Structured Streaming, Beam.
- Orchestration: Airflow, Dagster, Prefect, Argo Workflows.
- CDC: Debezium, Kafka Connect, Flink CDC, DMS.
- Ingestion: NiFi, Airbyte, Fivetran.

### Serving Layer

- Interactive SQL: Trino, Presto, Athena, Spark SQL.
- Warehouse: Snowflake, BigQuery, Redshift, Databricks SQL.
- Real-time OLAP: ClickHouse, Pinot, Druid, StarRocks, Doris.
- Embedded analytics: DuckDB.
- Search serving: OpenSearch/Elasticsearch when text search is required.
- Feature serving: online feature store for ML use cases.

### Quality and Operations

- Data quality checks: dbt tests, Great Expectations, Soda, Deequ.
- Freshness SLOs.
- Backfill strategy.
- Late-arriving data handling.
- Duplicate handling.
- Reconciliation with source systems.
- Cost controls: partition pruning, compaction, query limits, warehouse sizing.
- Observability: pipeline duration, failure rate, data freshness, row counts, null rate, schema drift, cost per job/query.

## Lakehouse Technology Selection Matrix

| Need | Strong Candidates | Watch Out |
| --- | --- | --- |
| Open table format with multi-engine analytics | Iceberg | Catalog compatibility and maintenance jobs. |
| Upserts and incremental ingestion | Hudi, Delta, Iceberg with merge support | Compaction and file layout complexity. |
| Databricks-heavy platform | Delta Lake, Unity Catalog | Platform coupling and interoperability requirements. |
| AWS-native lake governance | Glue, Lake Formation, Athena, Iceberg/Hudi/Delta | Permissions model complexity. |
| Multi-cloud open governance | Iceberg REST Catalog, Polaris, Gravitino, DataHub/OpenMetadata | Operational maturity. |
| Streaming-first processing | Flink, Kafka Streams, Spark Structured Streaming | State management and checkpointing. |
| Batch-heavy transformations | Spark, dbt, SQLMesh, Airflow/Dagster | Backfill and dependency management. |
| Real-time dashboard serving | Pinot, ClickHouse, Druid, StarRocks, Doris | Ingestion model and query concurrency. |
| Local analytics | DuckDB | Not a shared production warehouse by itself. |
| CDC ingestion | Debezium, Kafka Connect, Flink CDC, DMS | Deletes, schema changes, ordering, source load. |

---


### Flink Architect Depth

- Stateful stream processing and keyed state.
- Event time vs processing time.
- Watermarks and late events.
- Windows: tumbling, sliding, session, global.
- Checkpoints, savepoints, restart strategies.
- State backends and RocksDB state.
- Exactly-once sinks and two-phase commit concepts.
- Backpressure, operator parallelism, rescaling.
- Use cases: fraud detection, sessionization, real-time enrichment, CDC joins.

### Object Storage and Lakehouse

- Object storage is not a POSIX file system; design around object immutability, listing cost, prefix strategy, and eventual operational limits.
- S3/GCS/ADLS patterns: raw, bronze, silver, gold zones; lifecycle policies; versioning; encryption; access policies.
- File formats: Parquet, ORC, Avro, JSON; choose columnar for analytics and row/event formats for ingestion.
- Table formats: Iceberg, Hudi, Delta Lake.
- Iceberg concepts: snapshots, manifests, partition evolution, schema evolution, time travel, hidden partitioning, catalog integration.
- Hudi concepts: copy-on-write, merge-on-read, upserts, indexing, incremental pull, compaction.
- Delta concepts: transaction log, schema enforcement, time travel, optimize/vacuum concepts.
- Catalogs: Hive Metastore, AWS Glue, REST catalog.
- Query engines: Spark, Flink, Trino, Athena, Presto.
- Maintenance: compaction, clustering, small-file cleanup, snapshot expiration, metadata pruning.
- Governance: lineage, quality checks, PII tagging, access control, audit logs.

### Data Platform Interview Drill

Design a clickstream lakehouse:

1. Collect events through SDK/API gateway.
2. Validate schema and publish to Kafka.
3. Use Kafka Connect or Flink to land raw events in S3.
4. Write curated Iceberg/Hudi tables with partitioning based on query patterns.
5. Run stream enrichment in Flink with checkpoints and DLQ handling.
6. Run batch transforms with Spark/dbt.
7. Query through Trino/Athena and serve real-time dashboards through Pinot/ClickHouse.
8. Add lineage, data quality tests, RBAC, encryption, lifecycle, cost monitoring, and replay plan.

