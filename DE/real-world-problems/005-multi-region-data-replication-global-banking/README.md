# Problem 5: Multi-Region Data Replication (Global Banking)

## Problem 5: Multi-Region Data Replication (Global Banking)

### Business Context
Global bank operating in 15 countries. Regulatory requirement: customer data must reside
in-region. Need consistent view across regions for global risk calculations.

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              MULTI-REGION DATA PLATFORM                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │  REGION: US-EAST │  │  REGION: EU-WEST │  │  REGION: APAC   │            │
│  │                  │  │                  │  │                  │            │
│  │  ┌────────────┐ │  │  ┌────────────┐ │  │  ┌────────────┐ │            │
│  │  │ Local Data │ │  │  │ Local Data │ │  │  │ Local Data │ │            │
│  │  │ (PII stays)│ │  │  │ (GDPR zone)│ │  │  │ (China regs)│ │           │
│  │  └─────┬──────┘ │  │  └─────┬──────┘ │  │  └─────┬──────┘ │            │
│  │        │         │  │        │         │  │        │         │            │
│  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │  │  ┌─────▼──────┐ │            │
│  │  │ Kafka      │ │  │  │ Kafka      │ │  │  │ Kafka      │ │            │
│  │  │ (Local)    │─┼──┼──│ (Mirror)   │─┼──┼──│ (Mirror)   │ │            │
│  │  └────────────┘ │  │  └────────────┘ │  │  └────────────┘ │            │
│  │                  │  │                  │  │                  │            │
│  │  LOCAL PROCESSING│  │  LOCAL PROCESSING│  │  LOCAL PROCESSING│           │
│  │  • Local queries │  │  • Local queries │  │  • Local queries │           │
│  │  • Regional SLAs│  │  • GDPR compliance│ │  • Data residency│           │
│  └─────────┬────────┘  └─────────┬────────┘  └─────────┬────────┘          │
│            │                      │                      │                    │
│  ┌─────────▼──────────────────────▼──────────────────────▼───────────┐      │
│  │  GLOBAL AGGREGATION LAYER (Anonymized/Aggregated Only)             │      │
│  │                                                                    │      │
│  │  • Receives aggregated metrics (no PII crosses borders)            │      │
│  │  • Global risk calculations                                        │      │
│  │  • Cross-region analytics (anonymized)                             │      │
│  │  • Regulatory reporting (aggregated)                               │      │
│  │                                                                    │      │
│  │  CONFLICT RESOLUTION:                                              │      │
│  │  • Last-writer-wins for non-critical                               │      │
│  │  • CRDT (Conflict-free Replicated Data Types) for counters         │      │
│  │  • Saga pattern for cross-region transactions                      │      │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  REPLICATION STRATEGY:                                                       │
│  • MirrorMaker 2 for Kafka cross-region replication                          │
│  • Only non-PII topics replicated (aggregates, reference data)               │
│  • Latency: 50-200ms between regions (acceptable for async)                  │
│  • Bandwidth: 10 Gbps dedicated inter-region links                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions
```
WHY NOT single global database?
→ GDPR: EU data must stay in EU
→ Latency: US user querying EU database = 200ms+ round trip
→ Availability: Regional outage shouldn't affect other regions
→ Compliance: China requires local data residency

WHY Kafka MirrorMaker (not database replication)?
→ Selective: Only replicate what's needed (not PII)
→ Transform: Can anonymize/aggregate during replication
→ Decoupled: Regions operate independently
→ Resumable: Tracks offsets, handles network partitions

WHY CRDT for counters?
→ Concurrent updates from multiple regions
→ No coordination needed (no distributed locks)
→ Eventually consistent (good enough for analytics)
→ Example: Global transaction count = sum(regional_counts)
```

---

## Problems 6-25: Quick Architecture Overview

### Problem 6: Log Analytics Platform (ELK at Scale)
```
SCALE: 10 TB/day of logs from 10,000 microservices
ARCH: Filebeat → Kafka → Flink (enrichment) → Elasticsearch + S3
WHY: ES for search (<3s), S3 for long-term compliance
SCALABILITY: ES 100 nodes, hot-warm-cold node types
```

### Problem 7: Real-Time Bidding (Ad Tech)
```
SCALE: 1M bid requests/sec, 50ms response budget
ARCH: Bid Request → Feature Lookup (Aerospike <1ms) → ML Score → Respond
WHY AEROSPIKE: Sub-ms reads at scale, SSD-optimized
SCALABILITY: 3000 bid servers, geo-distributed
```

### Problem 8: Social Media Feed Generation
```
SCALE: 500M users, 10K new posts/sec
ARCH: Fan-out on write (Kafka) + Fan-out on read (hybrid)
WHY HYBRID: Celebrities fan-out on read (too many followers), others on write
STORAGE: Redis (feed cache) + Cassandra (persistent timeline)
```

### Problem 9: Genomics Data Pipeline
```
SCALE: 1 TB per genome, 1000 genomes/day
ARCH: Raw FASTQ → BWA alignment (HPC) → Variant calling → Delta Lake
WHY SPARK: Embarrassingly parallel (each chromosome independent)
STORAGE: S3 + Hail (genomics-specific format)
```

### Problem 10: Real-Time Inventory Tracking
```
SCALE: 10M SKUs, 1M updates/min (from POS, warehouse, returns)
ARCH: CDC (all stores) → Kafka → Flink (aggregate per SKU) → Redis + Postgres
WHY CDC: Capture every inventory change without app modification
WHY REDIS: <1ms availability check for checkout
CONSISTENCY: Eventual (acceptable: "was available 2 seconds ago")
```

### Problem 11: Click-Stream Analytics
```
SCALE: 100K clicks/sec, session analysis
ARCH: JS SDK → API → Kafka → Flink (sessionization) → Druid + Delta Lake
WHY FLINK: Session windows with gap detection
WHY DRUID: Sub-second slicing by dimension (page, device, campaign)
```

### Problem 12: Data Quality Pipeline
```
SCALE: 500 tables, 10K quality checks/day
ARCH: dbt tests + Great Expectations + custom Flink checks
Pattern: Circuit breaker (halt pipeline if quality drops below threshold)
ALERTING: Tiered (P1: data loss, P2: freshness, P3: coverage)
```

### Problem 13: Feature Store for ML
```
SCALE: 10,000 features, 100ms serving SLA, 50K requests/sec
ARCH: Offline (Spark → Iceberg) + Online (Flink → Redis)
WHY DUAL STORE: Training needs historical, serving needs real-time
POINT-IN-TIME: Prevent data leakage in training
```

### Problem 14: CDC-Based Data Warehouse Sync
```
SCALE: 200 source tables, 5-minute freshness SLA
ARCH: Debezium → Kafka → Flink → Iceberg (lakehouse)
WHY NOT full-load: 200 tables × full scan = DB overload
MERGE strategy: Upsert by PK, soft-delete tracking
```

### Problem 15: Streaming ETL for Financial Reporting
```
SCALE: 10M transactions/day, reconciliation across 50 systems
ARCH: Kafka → Flink (joins, enrichment) → Gold tables → Reporting DB
EXACTLY-ONCE: Required (financial data, no duplicates allowed)
AUDIT: Every transformation logged with lineage
```

### Problem 16: Real-Time Geospatial Pipeline
```
SCALE: 10M location updates/min (ride-sharing)
ARCH: GPS → Kafka → Flink (geofencing, ETA) → Redis (live positions)
WHY REDIS GEO: O(log n) radius queries, sorted sets
PARTITIONING: By geographic grid (H3 hexagonal)
```

### Problem 17: Data Mesh Implementation
```
SCALE: Large enterprise, 50 domains, 5000 tables
ARCH: Per-domain pipelines + shared platform (compute, catalog, governance)
DATA PRODUCTS: Each domain publishes validated, documented, SLA-backed datasets
GOVERNANCE: Federated (standards agreed, enforcement local)
```

### Problem 18: Real-Time Pricing Engine
```
SCALE: 50K price updates/sec (stock market data)
ARCH: Exchange Feed → UDP multicast → FPGA parsing → Kafka → Flink → Redis
WHY FPGA: <10 microsecond parsing (software too slow)
WHY UDP: Lower latency than TCP for market data
```

### Problem 19: Data Lake Migration (Hadoop to Lakehouse)
```
SCALE: 5 PB on HDFS → S3 + Iceberg
STRATEGY: Dual-write during migration, validate, cutover
WHY ICEBERG: Open format, multi-engine, partition evolution
TIMELINE: 12-18 months (large enterprises)
```

### Problem 20: Streaming Joins (Order + Payment + Shipment)
```
SCALE: 3 streams, 50K events/sec each, join within 1-hour window
ARCH: Kafka → Flink (temporal join with watermarks) → Enriched events
WHY FLINK: Best-in-class streaming join support
CHALLENGE: Late data, out-of-order events, state management
```

### Problem 21: Real-Time A/B Testing Analytics
```
SCALE: 100 concurrent experiments, 10M users, statistical significance
ARCH: Event → Kafka → Flink (metric computation) → Druid (dashboard)
STATISTICS: Sequential testing, always-valid confidence intervals
WHY REAL-TIME: Detect harmful experiments immediately (guardrail metrics)
```

### Problem 22: Data Governance & Lineage Platform
```
SCALE: Track lineage across 10K datasets, 5K pipelines
ARCH: OpenLineage events → Kafka → Marquez/DataHub → Graph DB
WHY GRAPH DB: Lineage is naturally a DAG (Neo4j/Neptune)
FEATURES: Impact analysis, compliance reporting, data discovery
```

### Problem 23: Multi-Tenant Data Platform (SaaS)
```
SCALE: 10K tenants, shared infrastructure, isolation guarantees
ARCH: Tenant-partitioned Kafka → Per-tenant compute limits → Shared storage
ISOLATION: Compute quotas, storage quotas, network isolation
NOISY NEIGHBOR: Rate limiting, priority queues, dedicated pools for enterprise
```

### Problem 24: Slowly Changing Dimensions (SCD Type 2)
```
SCALE: 100M customer records, 500K updates/day
ARCH: CDC → Flink → Iceberg (with versioned rows)
WHY SCD2: Full history (customer address changed → keep both)
IMPLEMENTATION: Surrogate keys, effective_from/to dates
```

### Problem 25: Dead Letter Queue & Data Recovery
```
SCALE: 1% error rate on 1M events/day = 10K failures to handle
ARCH: Main pipeline → DLQ (separate topic) → Retry logic → Alert
RETRY STRATEGY: Exponential backoff, max 3 retries, then manual queue
ROOT CAUSE: Schema errors (40%), downstream timeout (30%), data quality (30%)
```
