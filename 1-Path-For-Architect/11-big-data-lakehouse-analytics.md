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

### Airflow

- DAG orchestration.
- Scheduling.
- Retries.
- Backfills.
- SLA monitoring.

### dbt

- SQL transformations.
- Data tests.
- Documentation.
- Lineage.

### Trino/Presto

- Federated SQL.
- Interactive analytics.
- Querying data lakes.

### Lakehouse Formats

- Apache Iceberg.
- Delta Lake.
- Apache Hudi.

### OLAP Serving

- ClickHouse.
- Apache Pinot.
- Apache Druid.

### Data Warehouses

- Redshift.
- Snowflake.
- BigQuery.

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


