# Data Engineering System Design Patterns - Master Reference
## For Staff/Principal/Architect Level Engineers

---

## Table of Contents
1. [Pattern Categories](#pattern-categories)
2. [Architectural Patterns](#architectural-patterns)
3. [Data Modeling Patterns](#data-modeling-patterns)
4. [Processing Patterns](#processing-patterns)
5. [Integration Patterns](#integration-patterns)
6. [Reliability Patterns](#reliability-patterns)
7. [Storage Patterns](#storage-patterns)
8. [Governance Patterns](#governance-patterns)
9. [Decision Matrix](#decision-matrix)
10. [Pattern Composition](#pattern-composition)
11. [Anti-Patterns](#anti-patterns)

---

## Why Patterns Matter in Data Engineering

Data engineering at scale is fundamentally different from application development:
- **Volume**: Petabytes of data flowing daily
- **Velocity**: Millions of events per second
- **Variety**: Structured, semi-structured, unstructured
- **Veracity**: Data quality degrades over time
- **Value**: Business decisions depend on data freshness

Patterns provide **proven solutions** to recurring problems. A Staff Architect must know:
- WHEN to apply which pattern
- WHY one pattern over another
- HOW patterns compose together
- WHAT are the failure modes

---

## Pattern Categories

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA ENGINEERING PATTERNS                         │
├─────────────────┬──────────────────┬────────────────────────────────┤
│  ARCHITECTURAL  │   PROCESSING     │      INTEGRATION               │
│                 │                  │                                │
│  • Lambda       │  • Batch         │  • CDC (Change Data Capture)   │
│  • Kappa        │  • Stream        │  • Event Sourcing              │
│  • Delta        │  • Micro-batch   │  • CQRS                       │
│  • Medallion    │  • Exactly-once  │  • ETL / ELT                  │
│  • Data Mesh    │  • Watermarks    │  • Pub/Sub                    │
│  • Data Fabric  │  • Windowing     │  • Request-Reply              │
│                 │  • MapReduce     │  • Saga Pattern               │
├─────────────────┼──────────────────┼────────────────────────────────┤
│  DATA MODELING  │   RELIABILITY    │      STORAGE                   │
│                 │                  │                                │
│  • Star Schema  │  • Idempotency   │  • Partitioning               │
│  • Snowflake    │  • Dead Letter Q │  • Compaction                  │
│  • Data Vault   │  • Backpressure  │  • Schema Evolution            │
│  • SCD Types    │  • Circuit Break │  • Time-Travel                 │
│  • Wide Table   │  • Checkpointing │  • Hot/Warm/Cold               │
│  • Activity     │  • Retry + DLQ   │  • Columnar Storage            │
│    Schema       │  • Deduplication │  • Object Storage              │
├─────────────────┼──────────────────┼────────────────────────────────┤
│  GOVERNANCE     │   SCALABILITY    │      OPTIMIZATION              │
│                 │                  │                                │
│  • Data Lineage │  • Sharding      │  • Predicate Pushdown          │
│  • Data Contract│  • Replication   │  • Partition Pruning           │
│  • Data Catalog │  • Federation    │  • Materialized Views          │
│  • Data Quality │  • Auto-scaling  │  • Denormalization             │
│  • Access Ctrl  │  • Multi-tenant  │  • Caching Layers              │
│  • PII Handling │  • Geo-distribute│  • Bloom Filters               │
└─────────────────┴──────────────────┴────────────────────────────────┘
```

---

## Architectural Patterns Overview

### 1. Lambda Architecture
```
                    ┌─────────────────────────────────────┐
                    │         DATA SOURCES                  │
                    │  (Logs, Events, DBs, APIs, IoT)      │
                    └──────────────┬───────────────────────┘
                                   │
                    ┌──────────────▼───────────────────────┐
                    │      INGESTION LAYER (Kafka)          │
                    └──────┬───────────────────┬───────────┘
                           │                   │
              ┌────────────▼────────┐  ┌───────▼──────────────┐
              │   BATCH LAYER       │  │  SPEED LAYER          │
              │   (Spark/Hadoop)    │  │  (Flink/Storm)        │
              │                     │  │                       │
              │  • Master Dataset   │  │  • Real-time views    │
              │  • Batch Views      │  │  • Approximate        │
              │  • Complete but slow│  │  • Fast but may lose  │
              └────────────┬────────┘  └───────┬──────────────┘
                           │                   │
              ┌────────────▼───────────────────▼──────────────┐
              │            SERVING LAYER                        │
              │   (Druid/Pinot/Cassandra/ElasticSearch)         │
              │                                                │
              │   Merge: batch_view UNION speed_view            │
              └────────────────────────────────────────────────┘
```

**When**: Need both real-time AND historically accurate results
**Why**: Batch gives correctness; Speed gives freshness
**Trade-off**: Operational complexity of maintaining two codepaths
**Scale**: LinkedIn (30PB+), Twitter (500TB/day)

### 2. Kappa Architecture
```
              ┌─────────────────────────────────────┐
              │         DATA SOURCES                  │
              └──────────────┬───────────────────────┘
                             │
              ┌──────────────▼───────────────────────┐
              │   IMMUTABLE LOG (Kafka with retention)│
              │   • Infinite retention OR             │
              │   • Tiered storage                    │
              └──────────────┬───────────────────────┘
                             │
              ┌──────────────▼───────────────────────┐
              │   STREAM PROCESSING (Flink/KStreams)  │
              │   • Single code path                  │
              │   • Reprocess by replaying log        │
              │   • Versioned processors              │
              └──────────────┬───────────────────────┘
                             │
              ┌──────────────▼───────────────────────┐
              │   SERVING LAYER                       │
              │   (Real-time materialized views)      │
              └──────────────────────────────────────┘
```

**When**: Stream processing is sufficient for all use cases
**Why**: Single codebase, simpler ops, lower latency
**Trade-off**: Expensive reprocessing for large historical windows
**Scale**: Uber (trillions of events), Netflix (real-time recommendations)

### 3. Delta/Lakehouse Architecture
```
              ┌──────────────────────────────────────────────────┐
              │              DATA SOURCES                          │
              │   (DBs, APIs, Files, Streams, IoT)                │
              └──────────────────────┬───────────────────────────┘
                                     │
              ┌──────────────────────▼───────────────────────────┐
              │         UNIFIED STORAGE (Object Store)             │
              │         Delta Lake / Iceberg / Hudi                │
              │                                                    │
              │   ┌──────────┐  ┌──────────┐  ┌──────────┐       │
              │   │  BRONZE   │  │  SILVER   │  │  GOLD     │      │
              │   │  (Raw)    │→ │ (Cleaned) │→ │ (Curated) │      │
              │   └──────────┘  └──────────┘  └──────────┘       │
              │                                                    │
              │   Features: ACID, Time-travel, Schema Evolution    │
              └──────────────────────┬───────────────────────────┘
                                     │
              ┌──────────────────────▼───────────────────────────┐
              │         COMPUTE ENGINES                            │
              │   Spark | Flink | Presto | Trino | DuckDB          │
              └──────────────────────┬───────────────────────────┘
                                     │
              ┌──────────────────────▼───────────────────────────┐
              │         CONSUMPTION                                │
              │   BI Tools | ML Models | APIs | Notebooks          │
              └──────────────────────────────────────────────────┘
```

**When**: Need warehouse reliability with lake flexibility
**Why**: ACID on object storage, unified batch+streaming
**Trade-off**: Additional metadata management overhead
**Scale**: Databricks (exabyte-scale), Apple, Comcast

### 4. Medallion Architecture (Bronze/Silver/Gold)
```
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │   BRONZE     │     │   SILVER     │     │    GOLD      │
  │              │     │              │     │              │
  │ • Raw ingest │────▶│ • Cleaned    │────▶│ • Business   │
  │ • Append-only│     │ • Conformed  │     │   aggregates │
  │ • Schema on  │     │ • Deduplicated│    │ • Star schema│
  │   read       │     │ • Validated  │     │ • ML features│
  │ • Full       │     │ • Standardized│    │ • KPIs       │
  │   fidelity   │     │   types      │     │              │
  └─────────────┘     └─────────────┘     └─────────────┘
       │                     │                     │
  Retention:            Retention:            Retention:
  7-90 days            1-5 years             Forever
  Format: JSON/        Format: Parquet       Format: Parquet
  Avro/Raw             Partitioned           Optimized
```

### 5. Data Mesh
```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    DATA MESH TOPOLOGY                             │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
  │  │  DOMAIN A     │  │  DOMAIN B     │  │  DOMAIN C     │         │
  │  │  (Orders)     │  │  (Customers)  │  │  (Inventory)  │         │
  │  │               │  │               │  │               │         │
  │  │ • Own pipeline│  │ • Own pipeline│  │ • Own pipeline│         │
  │  │ • Own storage │  │ • Own storage │  │ • Own storage │         │
  │  │ • Own SLAs    │  │ • Own SLAs    │  │ • Own SLAs    │         │
  │  │ • Data product│  │ • Data product│  │ • Data product│         │
  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
  │         │                  │                  │                   │
  │  ┌──────▼──────────────────▼──────────────────▼───────┐         │
  │  │         SELF-SERVE DATA PLATFORM                    │         │
  │  │  (Infra as platform: compute, storage, catalog)     │         │
  │  └─────────────────────────┬──────────────────────────┘         │
  │                            │                                     │
  │  ┌─────────────────────────▼──────────────────────────┐         │
  │  │      FEDERATED GOVERNANCE                           │         │
  │  │  (Standards, interoperability, security policies)   │         │
  │  └────────────────────────────────────────────────────┘         │
  └─────────────────────────────────────────────────────────────────┘
```

**Four Principles**: Domain ownership, Data as product, Self-serve platform, Federated governance

### 6. Data Fabric
```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    DATA FABRIC                                    │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  ┌──────────────────────────────────────────────────────┐       │
  │  │         KNOWLEDGE GRAPH + ACTIVE METADATA             │       │
  │  │   (Auto-discovers, catalogs, recommends, governs)     │       │
  │  └──────────────────────────┬───────────────────────────┘       │
  │                             │                                    │
  │  ┌──────────┐  ┌──────────┐│  ┌──────────┐  ┌──────────┐      │
  │  │  On-Prem  │  │  Cloud A  ││  │  Cloud B  │  │  SaaS     │     │
  │  │  (Oracle)  │  │  (S3)    ││  │  (GCS)    │  │  (Salesforce)│  │
  │  └──────────┘  └──────────┘│  └──────────┘  └──────────┘      │
  │                             │                                    │
  │  ┌──────────────────────────▼───────────────────────────┐       │
  │  │    UNIFIED ACCESS LAYER (Virtual + Physical)          │       │
  │  │    • Data Virtualization                              │       │
  │  │    • Semantic Layer                                   │       │
  │  │    • Policy Engine (ABAC/RBAC)                        │       │
  │  └──────────────────────────────────────────────────────┘       │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Decision Matrix

| Pattern | Latency Need | Data Volume | Team Size | Complexity | Best For |
|---------|-------------|-------------|-----------|------------|----------|
| Lambda | Mixed | Very High | Large | Very High | Enterprises with both real-time + batch |
| Kappa | Low | High | Medium | Medium | Event-driven systems |
| Delta/Lakehouse | Mixed | Very High | Any | Medium | Unified analytics |
| Medallion | Any | High | Any | Low | Data quality progression |
| Data Mesh | Any | Very High | Very Large | High | Large orgs, many domains |
| Data Fabric | Any | Very High | Medium | Very High | Multi-cloud, heterogeneous |
| Star Schema | High query perf | Medium | Small | Low | BI/Reporting |
| Data Vault | Audit/History | High | Large | High | Regulated industries |
| CDC | Low | Any | Small | Medium | DB synchronization |
| Event Sourcing | Medium | High | Medium | High | Audit trails, replay |

---

## Pattern Composition (How Patterns Work Together)

```
┌─────────────────────────────────────────────────────────────────────┐
│                 COMMON PATTERN COMPOSITIONS                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. MODERN LAKEHOUSE STACK:                                          │
│     Medallion + Delta Lake + CDC + Schema Evolution + Data Quality   │
│                                                                      │
│  2. REAL-TIME ANALYTICS:                                             │
│     Kappa + Exactly-Once + Watermarks + Materialized Views           │
│                                                                      │
│  3. ENTERPRISE DATA PLATFORM:                                        │
│     Data Mesh + Data Contracts + Medallion + Federated Governance    │
│                                                                      │
│  4. EVENT-DRIVEN MICROSERVICES:                                      │
│     Event Sourcing + CQRS + Saga + Dead Letter Queue + Idempotency  │
│                                                                      │
│  5. ML FEATURE PLATFORM:                                             │
│     Kappa + Feature Store + Backfill + Point-in-time Joins           │
│                                                                      │
│  6. REGULATED DATA WAREHOUSE:                                        │
│     Data Vault + SCD Type 2 + Data Lineage + Access Control          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Anti-Patterns

| Anti-Pattern | Problem | Solution |
|-------------|---------|----------|
| Golden Source Myth | Single DB for everything | Domain-oriented storage |
| Schema-on-Pray | No schema validation | Schema registry + contracts |
| Reprocessing Hell | Can't replay/fix data | Immutable raw layer + idempotent transforms |
| Monolith Pipeline | Single DAG does everything | Decompose by domain/SLA |
| Late-Binding Horror | Types resolved at query time | Early validation, late enrichment |
| Copy-Paste ETL | Duplicate logic everywhere | Shared transformation libraries |
| Big Ball of SQL | 5000-line SQL transforms | Modular CTEs, dbt models |
| Alert Fatigue | Too many low-quality alerts | Tiered alerting, anomaly detection |
| Partition Explosion | Too many small files | Compaction, partition strategies |
| Premature Optimization | Optimizing before measuring | Profile first, optimize bottlenecks |

---

## File Index

### Patterns (Deep Dives)
| # | Pattern | File |
|---|---------|------|
| 01 | Lambda Architecture | `01-lambda-architecture/` |
| 02 | Kappa Architecture | `02-kappa-architecture/` |
| 03 | Delta/Lakehouse Architecture | `03-delta-architecture/` |
| 04 | Medallion Architecture | `04-medallion-architecture/` |
| 05 | Event Sourcing + CQRS | `05-event-sourcing-cqrs/` |
| 06 | Change Data Capture | `06-cdc-patterns/` |
| 07 | Data Vault Modeling | `07-data-vault-modeling/` |
| 08 | Slowly Changing Dimensions | `08-slowly-changing-dimensions/` |
| 09 | Exactly-Once Semantics | `09-exactly-once-semantics/` |
| 10 | Backpressure Patterns | `10-backpressure-patterns/` |
| 11 | Dead Letter Queue | `11-dead-letter-queue/` |
| 12 | Schema Evolution | `12-schema-evolution/` |
| 13 | Data Partitioning | `13-data-partitioning/` |
| 14 | Idempotency Patterns | `14-idempotency-patterns/` |
| 15 | Data Mesh | `15-data-mesh/` |
| 16 | Data Fabric | `16-data-fabric/` |
| 17 | Streaming Joins | `17-streaming-joins/` |
| 18 | Watermarks & Late Data | `18-watermarks-late-data/` |
| 19 | Compaction Strategies | `19-compaction-strategies/` |
| 20 | Data Lineage & Governance | `20-data-lineage-governance/` |

### Real-World Problems (100 Problems with Solutions)
| Range | File |
|-------|------|
| Problems 1-25 | `../real-world-problems/01-to-25/` |
| Problems 26-50 | `../real-world-problems/26-to-50/` |
| Problems 51-75 | `../real-world-problems/51-to-75/` |
| Problems 76-100 | `../real-world-problems/76-to-100/` |

### End-to-End Architectures
| # | Architecture | File |
|---|-------------|------|
| 01 | Streaming Platform | `../architectures/01-streaming-platform/` |
| 02 | Batch Lakehouse | `../architectures/02-batch-lakehouse/` |
| 03 | Real-time Analytics | `../architectures/03-real-time-analytics/` |
| 04 | ML Feature Store | `../architectures/04-ml-feature-store/` |
| 05 | Data Platform | `../architectures/05-data-platform/` |
| 06 | Event-Driven Microservices | `../architectures/06-event-driven-microservices/` |

