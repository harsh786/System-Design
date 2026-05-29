# Big Data Ecosystem & Data Modeling - Staff Architect Deep Dive

## Part A: Big Data Ecosystem

### 1. HDFS Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        HDFS CLUSTER                               │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   NameNode (Active)                       │    │
│  │  In-memory: File system namespace (tree of files/dirs)    │    │
│  │  FsImage: Periodic snapshot of namespace                  │    │
│  │  EditLog: Append-only log of namespace changes            │    │
│  │  Block mapping: file → list of blocks → DataNode locations│    │
│  │  Memory: ~150 bytes per file/dir/block                    │    │
│  │  1 billion files ≈ 150GB RAM for NameNode                 │    │
│  └──────────────────────────────┬───────────────────────────┘    │
│                                  │                                │
│  ┌──────────────────────────────▼───────────────────────────┐    │
│  │               Standby NameNode (HA)                       │    │
│  │  Reads EditLog from JournalNodes (QJM)                    │    │
│  │  Applies edits to its own FsImage                         │    │
│  │  Takes over on Active failure (via ZKFC)                  │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │
│  │ DataNode 0 │  │ DataNode 1 │  │ DataNode N │                  │
│  │            │  │            │  │            │                  │
│  │ Block A-r1 │  │ Block A-r2 │  │ Block A-r3 │  ← 3 replicas   │
│  │ Block B-r1 │  │ Block C-r1 │  │ Block B-r2 │                  │
│  │ Block D-r1 │  │ Block B-r3 │  │ Block C-r2 │                  │
│  │            │  │            │  │            │                  │
│  │ Heartbeat  │  │ Heartbeat  │  │ Heartbeat  │  → NameNode      │
│  │ Block Rpt  │  │ Block Rpt  │  │ Block Rpt  │  (every 3s/6h)   │
│  └────────────┘  └────────────┘  └────────────┘                  │
│                                                                    │
│  Block size: 128MB (default) or 256MB                             │
│  Replication: 3 (default), rack-aware placement                   │
│  Erasure Coding: 1.5x overhead vs 3x (HDFS 3.x)                 │
└──────────────────────────────────────────────────────────────────┘

Rack Awareness:
  Block replicas placed across racks for fault tolerance
  Replica 1: Local rack, local node
  Replica 2: Different rack
  Replica 3: Same rack as replica 2, different node
```

### 2. YARN Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         YARN                                  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              ResourceManager                          │    │
│  │  ┌──────────────┐  ┌────────────────────────────┐   │    │
│  │  │  Scheduler   │  │  ApplicationManager          │   │    │
│  │  │              │  │                              │   │    │
│  │  │  Fair /      │  │  Accepts app submissions     │   │    │
│  │  │  Capacity /  │  │  Negotiates first container  │   │    │
│  │  │  FIFO        │  │  for ApplicationMaster        │   │    │
│  │  └──────────────┘  └────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────┘    │
│                              │                                │
│  ┌───────────────────────────┼───────────────────────────┐   │
│  ▼                           ▼                           ▼   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ NodeManager 0│ │ NodeManager 1│ │ NodeManager N│        │
│  │              │ │              │ │              │        │
│  │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │        │
│  │ │Container │ │ │ │  App     │ │ │ │Container │ │        │
│  │ │(Spark    │ │ │ │  Master  │ │ │ │(Spark    │ │        │
│  │ │ Executor)│ │ │ │  (Spark  │ │ │ │ Executor)│ │        │
│  │ │          │ │ │ │  Driver) │ │ │ │          │ │        │
│  │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │        │
│  │ ┌──────────┐ │ │ ┌──────────┐ │ │              │        │
│  │ │Container │ │ │ │Container │ │ │              │        │
│  │ │(Flink TM)│ │ │ │(MapReduce│ │ │              │        │
│  │ │          │ │ │ │ Task)    │ │ │              │        │
│  │ └──────────┘ │ │ └──────────┘ │ │              │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                               │
│  Scheduler comparison:                                       │
│  FIFO: Simple queue, no isolation                            │
│  Fair: Equal resources per app/user, preemption              │
│  Capacity: Guaranteed min capacity per queue, hierarchical   │
└──────────────────────────────────────────────────────────────┘
```

### 3. Apache ZooKeeper

```
Architecture (Raft-like ZAB protocol):
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Leader     │  │  Follower 1  │  │  Follower 2  │
│              │  │              │  │              │
│  All writes  │──│  Replicate   │──│  Replicate   │
│  go here     │  │  from leader │  │  from leader │
│              │  │              │  │              │
│  Reads from  │  │  Reads from  │  │  Reads from  │
│  any node    │  │  any node    │  │  any node    │
└──────────────┘  └──────────────┘  └──────────────┘

Quorum: Majority must agree (2 of 3, 3 of 5)
Ensemble size: Always odd (3, 5, 7)

Data model (ZNode tree):
/
├── /kafka
│   ├── /brokers
│   │   ├── /ids/0        (ephemeral) → broker 0 alive
│   │   └── /ids/1        (ephemeral) → broker 1 alive
│   ├── /controller       (ephemeral) → current controller
│   └── /topics/orders/partitions/0/state → leader, ISR
├── /hbase
│   └── /master           (ephemeral) → active HMaster
└── /flink
    └── /leader            → current JobManager leader

Key patterns:
1. Leader Election: Create ephemeral sequential node, lowest wins
2. Distributed Lock: Create ephemeral node, if success → lock acquired
3. Service Discovery: Ephemeral nodes represent live services
4. Configuration: Persistent nodes with watches for changes
5. Barrier: All participants create nodes, proceed when count reached
```

### 4. Apache HBase

```
Architecture:
┌──────────────────────────────────────────────────────────────┐
│                       HBASE                                    │
│                                                               │
│  ┌──────────────┐    ┌──────────────────────────────────┐    │
│  │   HMaster    │    │        ZooKeeper                  │    │
│  │              │    │  - Region assignment               │    │
│  │  Region      │    │  - Master election                 │    │
│  │  assignment  │    │  - META table location             │    │
│  │  Load balance│    └──────────────────────────────────┘    │
│  │  Schema ops  │                                            │
│  └──────────────┘                                            │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │RegionServer 0│  │RegionServer 1│  │RegionServer N│       │
│  │              │  │              │  │              │       │
│  │  Region A    │  │  Region C    │  │  Region E    │       │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │       │
│  │  │MemStore│  │  │  │MemStore│  │  │  │MemStore│  │       │
│  │  │ (write │  │  │  │        │  │  │  │        │  │       │
│  │  │ buffer)│  │  │  └────────┘  │  │  └────────┘  │       │
│  │  └────────┘  │  │  ┌────────┐  │  │  ┌────────┐  │       │
│  │  ┌────────┐  │  │  │ HFiles │  │  │  │ HFiles │  │       │
│  │  │ HFiles │  │  │  │(sorted │  │  │  │        │  │       │
│  │  │(SST on │  │  │  │ on disk│  │  │  │        │  │       │
│  │  │ HDFS)  │  │  │  │        │  │  │  │        │  │       │
│  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │       │
│  │              │  │              │  │              │       │
│  │  WAL (Write-│  │  WAL         │  │  WAL         │       │
│  │  Ahead Log) │  │              │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘

Write path: Client → WAL → MemStore → (flush) → HFile (HDFS)
Read path: Client → Block Cache → MemStore → HFiles (merge)

Row key design (CRITICAL for performance):
  GOOD: user_123|2024-01-15|order_456 (prefix for range scans)
  BAD:  2024-01-15|user_123 (time prefix → hot region)
  
  Anti-pattern: Monotonic keys (timestamps) → single region hot spot
  Solution: Salt prefix (hash % N), reverse timestamp, composite keys
```

### 5. Cloud-Native Data Stack Comparison

```
┌──────────────────┬─────────────────┬──────────────────┬─────────────────┐
│ Function         │ AWS             │ GCP              │ Azure           │
├──────────────────┼─────────────────┼──────────────────┼─────────────────┤
│ Object Storage   │ S3              │ GCS              │ ADLS Gen2       │
│ Data Warehouse   │ Redshift        │ BigQuery         │ Synapse         │
│ ETL/Processing   │ Glue, EMR      │ Dataproc,        │ HDInsight,      │
│                  │                 │ Dataflow         │ Databricks      │
│ Streaming        │ Kinesis, MSK   │ Pub/Sub,         │ Event Hubs      │
│                  │                 │ Dataflow         │                 │
│ Orchestration    │ Step Functions, │ Cloud Composer   │ Data Factory    │
│                  │ MWAA           │ (Airflow)        │                 │
│ Catalog          │ Glue Catalog   │ Data Catalog     │ Purview         │
│ Serverless Query │ Athena         │ BigQuery         │ Synapse SL      │
│ ML Platform      │ SageMaker      │ Vertex AI        │ Azure ML        │
│ Real-time OLAP   │ Timestream     │ BigQuery BI      │ ADX             │
│ Message Queue    │ SQS/SNS       │ Pub/Sub          │ Service Bus     │
│ NoSQL            │ DynamoDB       │ Bigtable,        │ Cosmos DB       │
│                  │                 │ Firestore        │                 │
│ Search           │ OpenSearch     │ N/A              │ Cognitive Search│
│ Cache            │ ElastiCache    │ Memorystore      │ Azure Cache     │
│ Data Lake Format │ Iceberg (Athena│ BigLake          │ Delta (Databr.) │
│                  │ 3)             │ (Iceberg)        │                 │
└──────────────────┴─────────────────┴──────────────────┴─────────────────┘
```

### 6. Message Queue vs Event Streaming Comparison

```
┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Feature      │ Kafka    │ Pulsar   │ RabbitMQ │ SQS      │ Kinesis  │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Model        │ Log      │ Log      │ Queue    │ Queue    │ Log      │
│ Ordering     │ Partition│ Partition│ Queue    │ FIFO*    │ Shard    │
│ Retention    │ Time/size│ Time/size│ Until ack│ 14 days  │ 7 days   │
│ Replay       │ Yes      │ Yes      │ No       │ No       │ Yes      │
│ Throughput   │ Very High│ High     │ Medium   │ Medium   │ High     │
│ Latency      │ Low      │ Low      │ Very Low │ Medium   │ Medium   │
│ Multi-tenant │ Topics   │ Tenants  │ Vhosts   │ Queues   │ Streams  │
│ Tiered store │ Yes(3.0) │ Yes      │ No       │ N/A      │ No       │
│ Exactly-once │ Yes      │ Yes      │ No       │ FIFO*    │ No       │
│ Protocol     │ Binary   │ Binary   │ AMQP     │ HTTP     │ HTTP     │
│ Managed      │ MSK,     │ StreamNtv│ CloudAMQP│ Native   │ Native   │
│              │ Confluent│          │ Amazon MQ│          │          │
│ Best for     │ Event    │ Multi-   │ Task     │ Simple   │ AWS      │
│              │ streaming│ tenant   │ queue    │ decouple │ streaming│
└──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## Part B: Data Modeling and Warehousing

### 1. Dimensional Modeling

```
STAR SCHEMA:
              ┌──────────────┐
              │ dim_customer │
              │              │
              │ customer_id  │
              │ name         │
              │ email        │
              │ tier         │
              │ region       │
              └──────┬───────┘
                     │
┌──────────────┐  ┌──▼──────────────┐  ┌──────────────┐
│ dim_product  │  │  fct_orders      │  │  dim_date    │
│              │  │                  │  │              │
│ product_id   │──│ order_id (PK)   │──│ date_key     │
│ name         │  │ customer_id (FK)│  │ full_date    │
│ category     │  │ product_id (FK) │  │ year         │
│ brand        │  │ date_key (FK)   │  │ quarter      │
│ price        │  │ store_id (FK)   │  │ month        │
└──────────────┘  │                  │  │ week         │
                  │ quantity         │  │ day_of_week  │
┌──────────────┐  │ amount           │  │ is_holiday   │
│ dim_store    │  │ discount         │  └──────────────┘
│              │──│ tax              │
│ store_id     │  │ total            │
│ store_name   │  └──────────────────┘
│ city         │
│ state        │
└──────────────┘
```

### 2. Fact Table Types

```
TRANSACTION FACT:
  One row per event (most common)
  Example: fct_orders - one row per order line
  Grain: Individual transaction
  Additivity: All measures are additive

PERIODIC SNAPSHOT:
  One row per entity per time period
  Example: fct_account_daily - balance per account per day
  Grain: Entity + time period
  Additivity: Some measures non-additive (balance)

ACCUMULATING SNAPSHOT:
  One row per entity lifecycle (updated as events occur)
  Example: fct_order_lifecycle
  
  order_id | placed_date | shipped_date | delivered_date | returned_date
  1001     | 2024-01-01  | 2024-01-03   | 2024-01-05     | NULL
  
  Row UPDATED when order progresses through stages
  Grain: Entity lifecycle (one row per order)

FACTLESS FACT:
  Records events without measures
  Example: fct_student_attendance
  
  student_id | date_key | class_id
  (no numeric measures - the row itself IS the fact)
  
  Use: Coverage analysis, eligibility tracking
```

### 3. SCD Types (Slowly Changing Dimensions)

```
TYPE 0: Retain Original
  Never update. Keep original value forever.
  Use: Birth date, original sign-up date

TYPE 1: Overwrite
  Update in place. No history.
  Before: customer_id=1, tier=Silver
  After:  customer_id=1, tier=Gold  (Silver is LOST)
  Use: Corrections, non-important attributes

TYPE 2: Add New Row (MOST COMMON)
  New row with version tracking.
  customer_id | name  | tier   | valid_from | valid_to   | is_current
  1           | Alice | Silver | 2023-01-01 | 2024-06-15 | false
  1           | Alice | Gold   | 2024-06-15 | 9999-12-31 | true
  
  Use: Track full history (regulatory, analytics)

TYPE 3: Add New Column
  Keep previous and current values.
  customer_id | name  | current_tier | previous_tier
  1           | Alice | Gold         | Silver
  
  Use: Only care about previous value (not full history)

TYPE 4: Mini-Dimension
  Rapidly changing attributes split to separate table.
  dim_customer: customer_id, name, email (stable)
  dim_customer_profile: profile_id, tier, credit_score (volatile)
  fct_orders: customer_id, profile_id, ...
  
  Use: Frequently changing attributes (avoid bloating main dim)

TYPE 6: Hybrid (1+2+3)
  Combines Type 1, 2, and 3.
  customer_id | name | current_tier | historical_tier | valid_from | valid_to
  1           | Alice| Gold         | Silver          | 2023-01-01 | 2024-06-15
  1           | Alice| Gold         | Gold            | 2024-06-15 | 9999-12-31
  
  current_tier updated in ALL rows (Type 1)
  New row added (Type 2)
  Previous value kept (Type 3)
```

### 4. Data Vault 2.0

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA VAULT 2.0                                │
│                                                                  │
│  HUB (Business Key):          LINK (Relationship):              │
│  ┌──────────────────┐         ┌──────────────────────┐          │
│  │ hub_customer     │         │ link_order            │          │
│  │                  │         │                       │          │
│  │ hub_customer_hk  │◀────────│ link_order_hk         │          │
│  │ customer_bk      │         │ hub_customer_hk (FK) │          │
│  │ load_date        │         │ hub_product_hk (FK)  │          │
│  │ record_source    │         │ load_date             │          │
│  └──────────────────┘         │ record_source         │          │
│                                └──────────────────────┘          │
│                                                                  │
│  SATELLITE (Descriptive):                                       │
│  ┌──────────────────────┐                                       │
│  │ sat_customer_details  │                                       │
│  │                       │                                       │
│  │ hub_customer_hk (FK) │                                       │
│  │ load_date (PK)       │  ← Versioned (new row per change)    │
│  │ name                 │                                       │
│  │ email                │                                       │
│  │ tier                 │                                       │
│  │ hash_diff            │  ← Hash of all descriptive columns   │
│  │ record_source        │                                       │
│  └──────────────────────┘                                       │
│                                                                  │
│  Benefits:                                                      │
│  - Parallel loading (hubs, links, sats loaded independently)    │
│  - Full audit trail (load_date, record_source on everything)    │
│  - Resilient to source changes (additive-only)                  │
│  - Scales to enterprise (1000s of sources)                      │
│                                                                  │
│  Challenges:                                                    │
│  - Complex for end users → need Business Vault / marts on top   │
│  - More joins required for queries                              │
│  - Requires tooling/automation for loading patterns             │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Kimball vs Inmon

```
┌──────────────────┬─────────────────────┬─────────────────────┐
│                  │ KIMBALL             │ INMON               │
│                  │ (Bottom-Up)         │ (Top-Down)          │
├──────────────────┼─────────────────────┼─────────────────────┤
│ Approach         │ Build dimensional   │ Build normalized    │
│                  │ marts first         │ EDW first           │
│ Data model       │ Star schema (3NF    │ 3NF enterprise      │
│                  │ avoided)            │ model               │
│ Time to value    │ Fast (mart by mart) │ Slow (EDW first)    │
│ Integration      │ Conformed dimensions│ Centralized EDW     │
│ Complexity       │ Lower per mart      │ Higher upfront      │
│ Flexibility      │ Business-driven     │ IT-driven           │
│ Redundancy       │ Some (across marts) │ Minimal             │
│ ETL complexity   │ Moderate            │ High                │
│ Best for         │ Analytics/BI focus  │ Enterprise-wide     │
│                  │ Iterative delivery  │ Single source of    │
│                  │                     │ truth               │
│ Modern equiv.    │ dbt + Star schema   │ Data Vault + marts  │
└──────────────────┴─────────────────────┴─────────────────────┘
```

### 6. Data Mesh

```
┌──────────────────────────────────────────────────────────────────┐
│                      DATA MESH                                    │
│                                                                    │
│  PILLAR 1: Domain-Oriented Ownership                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ Orders   │  │ Customer │  │ Inventory│                       │
│  │ Domain   │  │ Domain   │  │ Domain   │                       │
│  │          │  │          │  │          │                       │
│  │ Own data │  │ Own data │  │ Own data │                       │
│  │ Own pipe │  │ Own pipe │  │ Own pipe │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
│                                                                    │
│  PILLAR 2: Data as a Product                                      │
│  Each domain publishes data products with:                        │
│  - Discoverable (registered in catalog)                           │
│  - Addressable (standard URIs)                                    │
│  - Trustworthy (quality guarantees, SLAs)                        │
│  - Self-describing (schema, documentation)                       │
│  - Interoperable (standard formats)                              │
│  - Secure (access control, encryption)                           │
│                                                                    │
│  PILLAR 3: Self-Serve Data Platform                               │
│  Platform team provides:                                          │
│  - Data infrastructure as a service                               │
│  - Pipeline templates and blueprints                              │
│  - Data quality frameworks                                        │
│  - Catalog and discovery tools                                    │
│  - Access management                                              │
│                                                                    │
│  PILLAR 4: Federated Computational Governance                     │
│  - Global standards (naming, formats, quality)                    │
│  - Local autonomy (domain-specific decisions)                     │
│  - Automated policy enforcement                                  │
│  - Cross-domain interoperability standards                        │
└──────────────────────────────────────────────────────────────────┘
```

### 7. Modern Data Stack

```
┌──────────────────────────────────────────────────────────────────┐
│                    MODERN DATA STACK                               │
│                                                                    │
│  INGESTION:                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Fivetran │  │ Airbyte  │  │ Stitch   │  │ Meltano  │        │
│  │ (SaaS)   │  │ (OSS)    │  │ (SaaS)   │  │ (OSS)    │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └──────────────┼──────────────┼──────────────┘              │
│                      ▼                                            │
│  STORAGE:     ┌──────────────────────────────────┐               │
│               │ Cloud DW / Lakehouse              │               │
│               │ Snowflake | BigQuery | Databricks │               │
│               └──────────────┬───────────────────┘               │
│                              ▼                                    │
│  TRANSFORM:   ┌──────────────────────────────────┐               │
│               │ dbt (SQL transformations)         │               │
│               │ Models → Tests → Documentation    │               │
│               └──────────────┬───────────────────┘               │
│                              ▼                                    │
│  BI:          ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│               │ Looker   │  │ Tableau  │  │ Metabase │          │
│               │          │  │          │  │ (OSS)    │          │
│               └──────────┘  └──────────┘  └──────────┘          │
│                                                                    │
│  ORCHESTRATION: Airflow / Dagster / Prefect                       │
│  CATALOG: DataHub / Atlan / dbt Docs                             │
│  QUALITY: Great Expectations / dbt tests / Monte Carlo            │
│  OBSERVABILITY: Monte Carlo / Bigeye / Metaplane                 │
└──────────────────────────────────────────────────────────────────┘
```

### 8. Metrics Layer / Semantic Layer

```
Problem:
  Same metric defined differently across tools:
  - BI tool A: revenue = SUM(amount) WHERE status != 'cancelled'
  - BI tool B: revenue = SUM(amount) WHERE status = 'completed'
  - Analyst SQL: revenue = SUM(amount - tax - discount)
  
  Result: "Which revenue number is correct?" → Trust crisis

Solution: Single source of metric definitions

┌──────────────────────────────────────────────────────────────┐
│                    SEMANTIC LAYER                              │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │              Metric Definitions                     │      │
│  │                                                     │      │
│  │  revenue:                                           │      │
│  │    type: derived                                    │      │
│  │    sql: SUM(amount) WHERE status = 'completed'      │      │
│  │    time_grains: [day, week, month, quarter, year]   │      │
│  │    dimensions: [region, product, channel]            │      │
│  │                                                     │      │
│  │  active_users:                                      │      │
│  │    type: derived                                    │      │
│  │    sql: COUNT(DISTINCT user_id) WHERE ...            │      │
│  │    window: 30 days rolling                          │      │
│  └────────────────────────────────────────────────────┘      │
│                        │                                      │
│       ┌────────────────┼────────────────┐                    │
│       ▼                ▼                ▼                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐            │
│  │ Looker   │   │ Tableau  │   │ Python/SQL   │            │
│  │          │   │          │   │ Notebooks    │            │
│  └──────────┘   └──────────┘   └──────────────┘            │
│                                                               │
│  ALL tools query same metric definitions                     │
│  Single source of truth for business metrics                 │
│                                                               │
│  Tools: dbt Semantic Layer (MetricFlow), Cube.js, Headless BI│
└──────────────────────────────────────────────────────────────┘
```
