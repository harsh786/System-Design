# Real-World Data Engineering Problems (100 Problems)

## Index

Each problem has its own directory with a dedicated README containing:
- Business context and requirements
- Architecture diagram (ASCII)
- Technology choices with WHY justification
- Scalability analysis
- Runnable Python code (for deep-dive problems)

---

### Problems 1-25: Foundations & Core Patterns

| # | Problem | Key Technologies |
|---|---------|-----------------|
| 001 | [Real-Time Fraud Detection](./001-real-time-fraud-detection-pipeline/) | Kafka, Flink, Redis, XGBoost |
| 002 | [Real-Time Recommendation Engine](./002-real-time-recommendation-engine-netflix-spotify-sc/) | Kafka, Flink, Milvus, Redis |
| 003 | [IoT Sensor Data Pipeline](./003-iot-sensor-data-pipeline-manufacturing/) | MQTT, Kafka, Flink, TimescaleDB |
| 004 | [E-Commerce Search & Analytics](./004-e-commerce-search-analytics-amazon-scale/) | Elasticsearch, Kafka, Druid |
| 005 | [Multi-Region Data Replication](./005-multi-region-data-replication-global-banking/) | Kafka MirrorMaker, CRDTs |
| 006 | [Log Analytics Platform](./006-log-analytics-platform-elk-at-scale/) | ELK Stack, Kafka |
| 007 | [Real-Time Bidding (AdTech)](./007-real-time-bidding-ad-tech/) | Low-latency streaming |
| 008 | [Social Media Feed Generation](./008-social-media-feed-generation/) | Fan-out, Redis, Kafka |
| 009 | [Genomics Data Pipeline](./009-genomics-data-pipeline/) | Spark, distributed storage |
| 010 | [Real-Time Inventory Tracking](./010-real-time-inventory-tracking/) | CDC, Flink, Redis |
| 011 | [Click Stream Analytics](./011-click-stream-analytics/) | Kafka, Flink, Druid |
| 012 | [Data Quality Pipeline](./012-data-quality-pipeline/) | Great Expectations, dbt |
| 013 | [Feature Store for ML](./013-feature-store-for-ml/) | Feast, Redis, Spark |
| 014 | [CDC-Based Data Warehouse Sync](./014-cdc-based-data-warehouse-sync/) | Debezium, Kafka Connect |
| 015 | [Streaming ETL for Financial Reporting](./015-streaming-etl-for-financial-reporting/) | Flink, Iceberg |
| 016 | [Real-Time Geospatial Pipeline](./016-real-time-geospatial-pipeline/) | H3, PostGIS, Kafka |
| 017 | [Data Mesh Implementation](./017-data-mesh-implementation/) | Domain ownership, self-serve |
| 018 | [Real-Time Pricing Engine](./018-real-time-pricing-engine/) | Flink, Redis, ML models |
| 019 | [Data Lake Migration (Hadoop → Lakehouse)](./019-data-lake-migration-hadoop-to-lakehouse/) | Iceberg, Spark |
| 020 | [Streaming Joins (Order+Payment+Shipment)](./020-streaming-joins-order-payment-shipment/) | Flink temporal joins |
| 021 | [Real-Time A/B Testing Analytics](./021-real-time-a-b-testing-analytics/) | Flink, statistical engines |
| 022 | [Data Governance & Lineage Platform](./022-data-governance-lineage-platform/) | DataHub, OpenLineage |
| 023 | [Multi-Tenant Data Platform (SaaS)](./023-multi-tenant-data-platform-saas/) | Tenant isolation, Iceberg |
| 024 | [Slowly Changing Dimensions (SCD Type 2)](./024-slowly-changing-dimensions-scd-type-2/) | Delta Lake MERGE |
| 025 | [Dead Letter Queue & Data Recovery](./025-dead-letter-queue-data-recovery/) | DLQ, retry patterns |

---

### Problems 26-50: Distributed Systems & Patterns

| # | Problem | Key Technologies |
|---|---------|-----------------|
| 026 | [Event-Driven Microservices Data Platform](./026-event-driven-microservices-data-platform/) | Saga, Outbox, Kafka |
| 027 | [Real-Time Data Quality Monitoring](./027-real-time-data-quality-monitoring/) | Circuit breaker, Grafana |
| 028 | [Streaming Data Warehouse (Materialized Views)](./028-streaming-data-warehouse-real-time-materialized-vi/) | Flink SQL, Pinot |
| 029 | [LSM-Tree Pipeline for Time-Series](./029-log-structured-merge-tree-pipeline-lsm-tree-for-ti/) | RocksDB, compaction |
| 030 | [Exactly-Once Processing Across Systems](./030-exactly-once-processing-across-systems/) | 2PC, idempotent sinks |
| 031 | [Data Catalog & Discovery Platform](./031-data-catalog-discovery-platform/) | DataHub, Graph DB |
| 032 | [Reverse ETL](./032-reverse-etl-warehouse-operational-systems/) | Census, Hightouch |
| 033 | [Real-Time Anomaly Detection on Metrics](./033-real-time-anomaly-detection-on-metrics/) | Z-score, Flink |
| 034 | [Data Versioning & Reproducibility](./034-data-versioning-reproducibility-ml/) | DVC, Delta time-travel |
| 035 | [Cross-Database Federated Queries](./035-cross-database-federated-queries/) | Trino, pushdown |
| 036 | [Streaming CDC to Data Warehouse](./036-streaming-cdc-to-data-warehouse-snowflake-bq/) | Debezium, Snowpipe |
| 037 | [Time-Series Forecasting Pipeline](./037-time-series-forecasting-pipeline/) | Prophet, DeepAR |
| 038 | [Data Contracts Between Teams](./038-data-contracts-between-teams/) | Schema Registry, CI/CD |
| 039 | [Backfill & Reprocessing Framework](./039-backfill-reprocessing-framework/) | Idempotent jobs |
| 040 | [Real-Time User Session Analysis](./040-real-time-user-session-analysis/) | Flink session windows |
| 041 | [Data Pipeline Orchestration](./041-data-pipeline-orchestration-beyond-airflow/) | Dagster, Prefect |
| 042 | [Schema Registry & Evolution](./042-schema-registry-evolution-management/) | Confluent SR |
| 043 | [Data Lakehouse Performance Tuning](./043-data-lakehouse-performance-tuning/) | Z-ORDER, compaction |
| 044 | [Streaming Deduplication at Scale](./044-streaming-deduplication-at-scale/) | Bloom filter, TTL |
| 045 | [Multi-Cloud Data Platform](./045-multi-cloud-data-platform/) | Iceberg, federation |
| 046 | [PII Detection & Tokenization](./046-pii-detection-tokenization-pipeline/) | NER, FPE |
| 047 | [Cost Optimization for Data Platform](./047-cost-optimization-for-data-platform/) | Tiering, right-sizing |
| 048 | [Streaming Graph Analytics](./048-streaming-graph-analytics/) | Neo4j, Flink |
| 049 | [Data Warehouse Automation](./049-data-warehouse-automation-auto-modeling/) | Auto-modeling, dbt |
| 050 | [Disaster Recovery for Data Pipelines](./050-disaster-recovery-for-data-pipelines/) | Multi-AZ, failover |

---

### Problems 51-75: Advanced Streaming & ML

| # | Problem | Key Technologies |
|---|---------|-----------------|
| 051 | [Real-Time Customer 360 Platform](./051-real-time-customer-360-platform/) | Identity resolution, Cassandra |
| 052 | [ML Feature Store (Feast/Tecton)](./052-ml-feature-store-feast-tecton-pattern/) | Feast, Redis, point-in-time |
| 053 | [Event-Time Processing with Watermarks](./053-event-time-processing-with-watermarks/) | Watermarks, late data |
| 054 | [Data Pipeline Backpressure Handling](./054-data-pipeline-backpressure-handling/) | Credit-based flow control |
| 055 | [CDC for Microservices](./055-change-data-capture-for-microservices/) | Outbox, Debezium |
| 056 | [Real-Time Alerting System](./056-real-time-alerting-system/) | CEP, Flink |
| 057 | [Data Lake Governance](./057-data-lake-governance-unity-catalog-pattern/) | Unity Catalog, RBAC |
| 058 | [Streaming ETL with Schema Registry](./058-streaming-etl-with-schema-registry/) | Avro, Protobuf |
| 059 | [Real-Time Dashboard Backend](./059-real-time-dashboard-backend/) | Druid/Pinot, pre-aggregate |
| 060 | [Data Warehouse Cost Management](./060-data-warehouse-cost-management/) | Auto-suspend, caching |
| 061 | [Streaming Deduplication with Bloom Filters](./061-streaming-deduplication-with-bloom-filters/) | Probabilistic dedup |
| 062 | [Incremental Materialized Views](./062-incremental-materialized-views/) | Delta processing |
| 063 | [Data Pipeline Testing Framework](./063-data-pipeline-testing-framework/) | pytest, testcontainers |
| 064 | [Real-Time ETL for GDPR/CCPA](./064-real-time-etl-for-compliance-gdpr-ccpa/) | Crypto-shredding |
| 065 | [Hybrid Transactional/Analytical (HTAP)](./065-hybrid-transactional-analytical-processing-htap/) | TiDB, AlloyDB |
| 066 | [Streaming Aggregation with Retraction](./066-streaming-aggregation-with-retraction/) | Retraction streams |
| 067 | [Data Observability Platform](./067-data-observability-platform/) | Monte Carlo, elementary |
| 068 | [Partition Management at Scale](./068-partition-management-at-scale/) | Iceberg manifests |
| 069 | [Stream-Table Duality](./069-stream-table-duality/) | Log compaction, KTable |
| 070 | [Data Pipeline Idempotency](./070-data-pipeline-idempotency-framework/) | Dedup, upsert |
| 071 | [Multi-Hop Streaming Pipeline](./071-multi-hop-streaming-pipeline/) | Bronze→Silver→Gold stream |
| 072 | [Data Mesh Self-Serve Platform](./072-data-mesh-self-serve-platform/) | Templates, GitOps |
| 073 | [Streaming ML Pipeline](./073-streaming-machine-learning-pipeline/) | Online learning, A/B |
| 074 | [Cross-Region Event Streaming](./074-cross-region-event-streaming/) | MirrorMaker 2 |
| 075 | [Cost-Effective Historical Archival](./075-cost-effective-historical-data-archival/) | S3 lifecycle, Glacier |

---

### Problems 76-100: Enterprise & Platform Engineering

| # | Problem | Key Technologies |
|---|---------|-----------------|
| 076 | [Real-Time Pipeline Monitoring](./076-real-time-data-pipeline-monitoring-alerting/) | Prometheus, Grafana |
| 077 | [Data Contract Platform](./077-building-a-data-contract-platform/) | Contract registry, validation |
| 078 | [Streaming CDC to Analytics](./078-streaming-cdc-to-analytics-complete-pipeline/) | Debezium→Kafka→Flink→Iceberg |
| 079 | [Real-Time Supply Chain Optimization](./079-real-time-supply-chain-optimization/) | Demand forecasting |
| 080 | [Autonomous Vehicles Data Platform](./080-data-platform-for-autonomous-vehicles/) | 1TB/hour per car |
| 081 | [Financial Market Data Pipeline](./081-financial-market-data-pipeline/) | FPGA, <10μs latency |
| 082 | [Healthcare Data Interoperability (FHIR)](./082-healthcare-data-interoperability-fhir-pipeline/) | HL7/FHIR, HIPAA |
| 083 | [Content Moderation Pipeline](./083-content-moderation-pipeline-social-media/) | ML models, 500M posts/day |
| 084 | [Energy Grid Real-Time Balancing](./084-energy-grid-real-time-balancing/) | Smart meters, grid control |
| 085 | [Telecom Network Analytics](./085-telecom-network-analytics/) | 10B CDRs/day |
| 086 | [Streaming Graph Updates](./086-streaming-graph-updates-knowledge-graph/) | Neo4j, batch writes |
| 087 | [Multi-Model Data Store](./087-multi-model-data-store-pattern/) | Polyglot persistence |
| 088 | [Lakehouse for Regulatory Reporting](./088-data-lakehouse-for-regulatory-reporting/) | Immutable, 7-year retention |
| 089 | [Streaming Sessionization](./089-streaming-sessionization/) | Session windows, gap-based |
| 090 | [Data Pipeline as Code](./090-data-pipeline-as-code-infrastructure/) | Terraform, GitOps |
| 091 | [Streaming Enrichment (Multi-Source)](./091-streaming-enrichment-from-multiple-sources/) | Temporal joins |
| 092 | [Data Warehouse Migration](./092-data-warehouse-migration-on-prem-to-cloud/) | Dual-write, cutover |
| 093 | [Real-Time Personalization Engine](./093-real-time-personalization-engine/) | User profiles, Redis |
| 094 | [Streaming Data Warehouse](./094-streaming-data-warehouse-materialize-risingwave/) | Materialize, RisingWave |
| 095 | [Chaos Engineering for Data Pipelines](./095-chaos-engineering-for-data-pipelines/) | Resilience testing |
| 096 | [Zero-Copy Data Sharing](./096-zero-copy-data-sharing-across-organizations/) | Delta Sharing |
| 097 | [Time-Series Anomaly Detection](./097-time-series-anomaly-detection-at-scale/) | Isolation Forest, STL |
| 098 | [Data Product Marketplace](./098-data-product-marketplace/) | Catalog, self-serve |
| 099 | [Unified Batch+Stream (Apache Beam)](./099-unified-batch-stream-processing-apache-beam/) | Write once, run anywhere |
| 100 | [Complete Data Platform from Scratch](./100-building-a-complete-data-platform-from-scratch/) | Full 6-layer architecture |

---

## Deep-Dive Problems (with full runnable code)

These problems include complete Python implementations you can run locally:

- **001** - Fraud Detection: Feature store + Rule engine + ML scoring + Decision engine
- **026** - Event-Driven Saga: Orchestrator + compensation + multi-service
- **051** - Customer 360: Identity resolution + unified profile store
- **052** - ML Feature Store: Batch + streaming features + point-in-time
- **053** - Watermarks: Out-of-order events + window triggering + late data
- **077** - Data Contracts: Schema validation + quality SLAs + compatibility
