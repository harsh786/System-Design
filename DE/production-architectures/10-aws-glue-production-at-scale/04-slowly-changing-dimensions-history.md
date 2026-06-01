# Slowly Changing Dimensions & History Tracking at Walmart/Target Scale

## The Problem: 500M Customer Dimension Records with Full Change History

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

Retail enterprises like Walmart and Target need **accurate historical reporting** across every
dimension. When a customer moves from Texas to California, every past order must still attribute
to Texas, while future orders attribute to California. When a product changes category or price
tier, historical revenue must reflect the original classification.

**If you just UPDATE in place, you lose the ability to answer:**
- "What was this customer's tier when they made that $5000 purchase last March?"
- "How much revenue came from the Electronics category before we reclassified 10K products?"
- "Which store region generated the most revenue in Q2 — using Q2's region boundaries?"

### Scale Parameters

```
┌─────────────────────────────────────────────────────────────┐
│  DIMENSION SCALE                                            │
├─────────────────────────────────────────────────────────────┤
│  Customers:           500 million active profiles           │
│  Products:            100 million SKUs                      │
│  Stores/Locations:    12,000 physical + 50K fulfillment     │
│  Suppliers/Vendors:   200,000 active relationships          │
│                                                             │
│  CHANGE VELOCITY                                            │
├─────────────────────────────────────────────────────────────┤
│  Customer changes:    1.5 million/day (address, email, tier)│
│  Product changes:     400K/day (price, description, cat.)   │
│  Store changes:       5K/day (hours, manager, attributes)   │
│  Supplier changes:    50K/day (contact, terms, status)      │
│  Total:               ~2 million dimension changes/day      │
│                                                             │
│  HISTORY REQUIREMENTS                                       │
├─────────────────────────────────────────────────────────────┤
│  Retention:           7 years (regulatory) + 10 years (BI)  │
│  History rows:        ~8 billion (avg 16 versions/customer) │
│  Point-in-time query: Any date in last 10 years, < 30s     │
│  SCD Types needed:    Type 1, 2, 3, 6 simultaneously       │
└─────────────────────────────────────────────────────────────┘
```

### Why History Matters

| Use Case | Requirement | Business Impact |
|----------|-------------|-----------------|
| Revenue attribution | Customer tier at time of purchase | $200M loyalty program accuracy |
| Regulatory compliance | GDPR/CCPA audit trail | Legal obligation, fines up to 4% revenue |
| Marketing analysis | Customer journey across segments | $50M campaign targeting accuracy |
| Product analytics | Category at time of sale | Merchandising decisions |
| Store performance | Region/district at time of transaction | Executive compensation |
| Supplier negotiations | Terms at time of PO | Contract dispute resolution |

---

## Why Traditional Approaches Fail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Approach 1: UPDATE in Place

```
Problem: Customer moves from TX → CA
Before: customer_id=123, state='TX'
After:  customer_id=123, state='CA'

Result: ALL historical queries now show CA — WRONG
        "Q1 revenue by state" now attributes past TX orders to CA
```

**Verdict:** Unacceptable for any analytical workload.

### Approach 2: Append-Only in Hive/S3

```
Day 1: customer_123, state=TX, load_date=2024-01-01
Day 2: customer_123, state=CA, load_date=2024-01-02

Problems:
- No MERGE capability — cannot close previous record
- Reading "current" requires window function on every query
- 500M customers × 365 days × 7 years = 1.2 TRILLION rows
- Partition explosion: partition by load_date = 2,555 partitions minimum
- Query "as-of 2023-06-15" requires scanning all partitions up to that date
```

**Verdict:** Works for small scale, collapses at 500M+ dimensions.

### Approach 3: Traditional Data Warehouse SCD (Kimball)

```
Teradata/Redshift approach:
- Surrogate key assignment via sequence
- ROW_NUMBER() to find current record
- MERGE statement to close/open records

Problems at scale:
- Redshift MERGE on 8B rows = 4+ hour runtime
- Surrogate key sequences = bottleneck
- Vacuum/analyze on 8B row table = overnight job
- Cost: $500K+/year for sufficient Redshift capacity
```

**Verdict:** Cost-prohibitive at retail scale. Walmart's dimension tables alone would require dedicated clusters.

### Approach 4: Manual Timestamp Tracking

```python
# Developer writes custom logic:
if new_record != existing_record:
    existing_record.end_date = now()
    existing_record.is_current = False
    new_record.start_date = now()
    new_record.end_date = '9999-12-31'
    new_record.is_current = True

Problems:
- Race conditions with concurrent updates
- Out-of-order events create gaps/overlaps
- No transaction guarantees in S3
- Every developer implements differently
- No validation of date continuity
```

**Verdict:** Error-prone, inconsistent, unmaintainable.

---

## SCD Types Explained

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────┬──────────────────┬─────────────────────────────────────────────────┐
│ Type    │ Strategy         │ Example                                         │
├─────────┼──────────────────┼─────────────────────────────────────────────────┤
│ Type 1  │ Overwrite        │ Fix typo in name: "Jonh" → "John"              │
│         │                  │ No history needed, just correct it               │
├─────────┼──────────────────┼─────────────────────────────────────────────────┤
│ Type 2  │ Add new row      │ Customer moves TX → CA                          │
│         │ with dates       │ Row 1: TX, eff 2020-01-01 to 2024-03-15        │
│         │                  │ Row 2: CA, eff 2024-03-15 to 9999-12-31        │
├─────────┼──────────────────┼─────────────────────────────────────────────────┤
│ Type 3  │ Previous value   │ customer.current_tier = 'Gold'                  │
│         │ column           │ customer.previous_tier = 'Silver'               │
│         │                  │ Only tracks ONE previous value                   │
├─────────┼──────────────────┼─────────────────────────────────────────────────┤
│ Type 4  │ Mini-dimension   │ Separate history table for rapidly changing     │
│         │                  │ attributes (e.g., customer_age_band)            │
├─────────┼──────────────────┼─────────────────────────────────────────────────┤
│ Type 6  │ Hybrid 1+2+3    │ Full row history (Type 2) PLUS current value    │
│         │                  │ on every row (Type 1) PLUS previous (Type 3)    │
│         │                  │ Most flexible, most storage                      │
└─────────┴──────────────────┴─────────────────────────────────────────────────┘
```

### Type 2 Diagram — The Core of This Architecture

```
Customer 123 moves from TX → CA on 2024-03-15:

BEFORE (1 row):
┌────────────┬──────┬────────────┬────────────┬─────────┐
│ surrogate  │ state│ eff_start  │ eff_end    │ current │
├────────────┼──────┼────────────┼────────────┼─────────┤
│ sk_abc_001 │ TX   │ 2020-01-01 │ 9999-12-31 │ true    │
└────────────┴──────┴────────────┴────────────┴─────────┘

AFTER (2 rows):
┌────────────┬──────┬────────────┬────────────┬─────────┐
│ surrogate  │ state│ eff_start  │ eff_end    │ current │
├────────────┼──────┼────────────┼────────────┼─────────┤
│ sk_abc_001 │ TX   │ 2020-01-01 │ 2024-03-15 │ false   │  ← CLOSED
│ sk_abc_002 │ CA   │ 2024-03-15 │ 9999-12-31 │ true    │  ← NEW
└────────────┴──────┴────────────┴────────────┴─────────┘

Point-in-time query for 2023-06-15:
  WHERE eff_start <= '2023-06-15' AND eff_end > '2023-06-15'
  Result: TX ✓
```

### Type 6 Diagram — Used for Key Attributes

```
Customer 123, tier changes Silver → Gold → Platinum:

┌────────────┬──────────┬──────────────┬───────────────┬─────────┬──────────────────┐
│ surrogate  │ curr_tier│ prev_tier    │ hist_tier     │ eff_dt  │ current          │
├────────────┼──────────┼──────────────┼───────────────┼─────────┼──────────────────┤
│ sk_001     │ Platinum │ Gold         │ Silver        │ 2022-01 │ false            │
│ sk_002     │ Platinum │ Gold         │ Gold          │ 2023-06 │ false            │
│ sk_003     │ Platinum │ Gold         │ Platinum      │ 2024-01 │ true             │
└────────────┴──────────┴──────────────┴───────────────┴─────────┴──────────────────┘

Benefits: curr_tier on EVERY row enables simple joins without window functions
          hist_tier shows what tier was at that point in time
          prev_tier enables "just upgraded from" analysis
```

---

## Architecture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                        SCD HISTORY TRACKING ARCHITECTURE                              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  Customer   │  │  Product    │  │   Store     │  │  Supplier   │               │
│  │  Service    │  │  Catalog    │  │   Master    │  │  Portal     │               │
│  │  (MySQL)    │  │  (Postgres) │  │   (API)     │  │  (Oracle)   │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         │ CDC             │ Batch          │ API Poll        │ CDC                  │
│         ▼                 ▼                ▼                 ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │                    AWS DMS / MSK (Kafka)                            │            │
│  │         CDC streams with before/after images                        │            │
│  └─────────────────────────────────┬───────────────────────────────────┘            │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │  JOB 1: CDC INGESTION                                              │            │
│  │  - Consume from Kafka/DMS                                           │            │
│  │  - Deduplicate by event_id                                          │            │
│  │  - Write to S3 landing (partitioned by source_date)                 │            │
│  │  - Track offsets via Job Bookmarks                                  │            │
│  └─────────────────────────────────┬───────────────────────────────────┘            │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐           │
│  │  S3 LANDING ZONE                                                     │           │
│  │  s3://lake/landing/dimensions/{source}/{yyyy}/{mm}/{dd}/             │           │
│  └─────────────────────────────────┬────────────────────────────────────┘           │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │  JOB 2: CHANGE DETECTION                                           │            │
│  │  - Read today's landing data                                        │            │
│  │  - Read current dimension snapshot from Iceberg                     │            │
│  │  - Hash comparison (MD5 of tracked columns)                         │            │
│  │  - Classify: NEW | CHANGED | UNCHANGED | DELETED                    │            │
│  │  - Output: change_set with old/new values                           │            │
│  └─────────────────────────────────┬───────────────────────────────────┘            │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │  JOB 3: SCD MERGE                                                  │            │
│  │  - Type 1: Direct overwrite for correction columns                  │            │
│  │  - Type 2: Close existing → Insert new for tracked columns          │            │
│  │  - Type 6: Update curr_* on ALL historical rows                     │            │
│  │  - Iceberg MERGE INTO for atomic operations                         │            │
│  │  - Generate surrogate keys (deterministic hash)                     │            │
│  └─────────────────────────────────┬───────────────────────────────────┘            │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │  JOB 4: SNAPSHOT GENERATION                                         │            │
│  │  - Nightly: Generate "as-of" snapshot for common query dates        │            │
│  │  - Monthly: Full materialized snapshot for month-end                 │            │
│  │  - On-demand: Point-in-time views for ad-hoc analysis               │            │
│  └─────────────────────────────────┬───────────────────────────────────┘            │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐            │
│  │  JOB 5: HISTORY COMPACTION & OPTIMIZATION                           │            │
│  │  - Iceberg table maintenance (compact small files)                  │            │
│  │  - Expire old snapshots (keep 30 days for time travel)              │            │
│  │  - Rewrite data files for optimal partition layout                   │            │
│  │  - Sort within partitions by business_key for merge perf            │            │
│  └─────────────────────────────────┬───────────────────────────────────┘            │
│                                    │                                                 │
│                                    ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐           │
│  │  ICEBERG TABLES (S3)                                                 │           │
│  │  ┌────────────────┐ ┌────────────────┐ ┌────────────────────┐       │           │
│  │  │ dim_customer   │ │ dim_product    │ │ dim_store           │       │           │
│  │  │ (SCD Type 2+6) │ │ (SCD Type 2)  │ │ (SCD Type 2)       │       │           │
│  │  │ 8B rows        │ │ 2B rows        │ │ 500K rows          │       │           │
│  │  └────────────────┘ └────────────────┘ └────────────────────┘       │           │
│  └──────────────────────────────────────────────────────────────────────┘           │
│                                    │                                                 │
│              ┌─────────────────────┼──────────────────────┐                         │
│              ▼                     ▼                      ▼                          │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐                 │
│  │  BI / Reporting   │ │  ML Features      │ │  Compliance/Audit │                 │
│  │  (Athena/Redshift)│ │  (Point-in-time)  │ │  (Full lineage)   │                 │
│  └───────────────────┘ └───────────────────┘ └───────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Glue Concepts Used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 1. MERGE Operations via Iceberg Connector

Glue 4.0+ supports Apache Iceberg natively. The MERGE INTO statement enables atomic
close-and-insert operations essential for SCD Type 2:

```
MERGE INTO dim_customer target
USING staged_changes source
ON target.customer_id = source.customer_id AND target.is_current = true
WHEN MATCHED AND source.change_type = 'UPDATE' THEN
  UPDATE SET eff_end = source.change_date, is_current = false
WHEN NOT MATCHED THEN
  INSERT (...)
```

### 2. Job Bookmarks

Track CDC consumption position. Each run picks up only new change events since last
successful completion. Critical for exactly-once processing of dimension changes.

### 3. DynamicFrame Schema Evolution

When source systems add new columns (e.g., customer adds `preferred_language`), Glue's
DynamicFrame handles schema evolution without breaking the pipeline. The new column is
added to the Iceberg table via schema evolution.

### 4. Pushdown Predicates

```python
# Only read partitions with changes — not the entire 8B row table
dyf = glue_context.create_dynamic_frame.from_catalog(
    database="dimensions",
    table_name="dim_customer",
    push_down_predicate="(is_current = true)"
)
```

### 5. Custom Transforms for SCD Logic

Glue's `Map` and `Filter` transforms implement the SCD classification logic —
determining which records are Type 1 corrections vs Type 2 tracked changes.

### 6. Glue Data Quality

```python
# Validate SCD integrity
ruleset = """
    Rules = [
        ColumnValues "eff_start" <= "eff_end",
        ColumnValues "is_current" in ["true", "false"],
        Uniqueness "surrogate_key" > 0.9999,
        CustomSql "SELECT COUNT(*) FROM dim_customer
                   WHERE is_current = true
                   GROUP BY customer_id HAVING COUNT(*) > 1" = 0
    ]
"""
```

---

## Implementation Code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Job 1: CDC Ingestion

```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'kafka_bootstrap', 'topic_prefix', 'landing_path'
])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# ─────────────────────────────────────────────────────────────
# Read CDC events from Kafka (DMS replication to MSK)
# ─────────────────────────────────────────────────────────────
cdc_df = spark.read \
    .format("kafka") \
    .option("kafka.bootstrap.servers", args['kafka_bootstrap']) \
    .option("subscribePattern", f"{args['topic_prefix']}.*") \
    .option("startingOffsets", "earliest") \
    .option("endingOffsets", "latest") \
    .load()

# Parse CDC envelope (Debezium format)
from pyspark.sql.types import StructType, StructField, StringType, LongType

parsed_df = cdc_df.select(
    F.from_json(F.col("value").cast("string"), cdc_schema).alias("data"),
    F.col("topic"),
    F.col("partition"),
    F.col("offset"),
    F.col("timestamp").alias("kafka_timestamp")
).select(
    "data.op",                          # c=create, u=update, d=delete
    "data.before",                      # before-image
    "data.after",                       # after-image
    "data.source.ts_ms",               # source timestamp
    "data.source.table",               # source table name
    "topic", "partition", "offset", "kafka_timestamp"
)

# Deduplicate by event_id (handle Kafka redeliveries)
deduped_df = parsed_df.dropDuplicates(["topic", "partition", "offset"])

# Classify by source dimension
source_date = F.current_date().cast("string")

deduped_df.write \
    .mode("append") \
    .partitionBy("table", "source_date") \
    .parquet(f"{args['landing_path']}/dimensions/")

job.commit()
```

### Job 2: Change Detection

```python
import hashlib
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'landing_path', 'iceberg_catalog', 'process_date'
])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# Configure Iceberg
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", "s3://lake/iceberg/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl",
               "org.apache.iceberg.aws.glue.GlueCatalog")

# ─────────────────────────────────────────────────────────────
# Configuration: Which columns are tracked for which SCD type
# ─────────────────────────────────────────────────────────────
SCD_CONFIG = {
    "dim_customer": {
        "business_key": ["customer_id"],
        "type1_columns": ["first_name", "last_name"],        # Corrections only
        "type2_columns": ["address", "city", "state", "zip",
                          "email", "phone", "tier"],           # Full history
        "type6_columns": ["tier"],                             # Also track current on all rows
        "ignore_columns": ["last_login", "session_count"],    # Don't trigger SCD
    },
    "dim_product": {
        "business_key": ["product_id"],
        "type1_columns": ["description_typo_fix"],
        "type2_columns": ["price", "category", "subcategory",
                          "brand", "supplier_id"],
        "type6_columns": ["category"],
        "ignore_columns": ["view_count", "last_viewed"],
    }
}

# ─────────────────────────────────────────────────────────────
# Read today's changes from landing zone
# ─────────────────────────────────────────────────────────────
process_date = args['process_date']
landing_df = spark.read.parquet(
    f"{args['landing_path']}/dimensions/table=customer/source_date={process_date}/"
)

# Take latest change per business key (if multiple changes in one day)
window_latest = Window.partitionBy("customer_id").orderBy(F.col("ts_ms").desc())
latest_changes = landing_df \
    .withColumn("rn", F.row_number().over(window_latest)) \
    .filter(F.col("rn") == 1) \
    .drop("rn")

# ─────────────────────────────────────────────────────────────
# Read current dimension state from Iceberg
# ─────────────────────────────────────────────────────────────
current_dim = spark.read \
    .format("iceberg") \
    .load("glue_catalog.dimensions.dim_customer") \
    .filter(F.col("is_current") == True)

# ─────────────────────────────────────────────────────────────
# Hash comparison for change detection
# ─────────────────────────────────────────────────────────────
config = SCD_CONFIG["dim_customer"]
tracked_cols = config["type2_columns"] + config["type1_columns"]

def generate_row_hash(df, columns, prefix=""):
    """Generate MD5 hash of tracked columns for comparison."""
    hash_expr = F.md5(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("__NULL__"))
                                            for c in columns]))
    return df.withColumn(f"{prefix}row_hash", hash_expr)

latest_with_hash = generate_row_hash(latest_changes, tracked_cols, "new_")
current_with_hash = generate_row_hash(current_dim, tracked_cols, "cur_")

# ─────────────────────────────────────────────────────────────
# Classify changes
# ─────────────────────────────────────────────────────────────
joined = latest_with_hash.alias("new").join(
    current_with_hash.alias("cur"),
    on=[F.col("new.customer_id") == F.col("cur.customer_id")],
    how="left"
)

classified = joined.withColumn(
    "change_type",
    F.when(F.col("cur.customer_id").isNull(), F.lit("NEW"))
     .when(F.col("new_row_hash") != F.col("cur_row_hash"), F.lit("CHANGED"))
     .otherwise(F.lit("UNCHANGED"))
).filter(F.col("change_type") != "UNCHANGED")

# Determine which SCD type applies per column
type2_hash = F.md5(F.concat_ws("||", *[F.coalesce(F.col(f"new.{c}").cast("string"), F.lit("__NULL__"))
                                         for c in config["type2_columns"]]))
cur_type2_hash = F.md5(F.concat_ws("||", *[F.coalesce(F.col(f"cur.{c}").cast("string"), F.lit("__NULL__"))
                                             for c in config["type2_columns"]]))

classified = classified.withColumn(
    "requires_type2",
    F.when(type2_hash != cur_type2_hash, F.lit(True)).otherwise(F.lit(False))
)

# Write change set for Job 3
classified.write \
    .mode("overwrite") \
    .parquet(f"s3://lake/staging/change_sets/dim_customer/{process_date}/")

print(f"Change detection complete: {classified.count()} changes identified")
print(f"  NEW: {classified.filter(F.col('change_type')=='NEW').count()}")
print(f"  CHANGED (Type 2): {classified.filter(F.col('requires_type2')==True).count()}")
print(f"  CHANGED (Type 1 only): {classified.filter((F.col('change_type')=='CHANGED') & (F.col('requires_type2')==False)).count()}")

job.commit()
```

### Job 3: SCD Type 2 Merge (Core Logic)

```python
import sys
import hashlib
from datetime import datetime
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'process_date', 'iceberg_catalog'
])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# Iceberg configuration
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", "s3://lake/iceberg/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl",
               "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.extensions",
               "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")

process_date = args['process_date']
HIGH_DATE = "9999-12-31"

# ─────────────────────────────────────────────────────────────
# Surrogate Key Generation (Deterministic)
# ─────────────────────────────────────────────────────────────
@F.udf(StringType())
def generate_surrogate_key(business_key, effective_start):
    """
    Deterministic surrogate key = hash(business_key + effective_start).
    This ensures idempotent reruns produce the same key.
    """
    raw = f"{business_key}|{effective_start}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

# ─────────────────────────────────────────────────────────────
# Read change set from Job 2
# ─────────────────────────────────────────────────────────────
change_set = spark.read.parquet(
    f"s3://lake/staging/change_sets/dim_customer/{process_date}/"
)

type2_changes = change_set.filter(
    (F.col("change_type") == "CHANGED") & (F.col("requires_type2") == True)
    | (F.col("change_type") == "NEW")
)

type1_only_changes = change_set.filter(
    (F.col("change_type") == "CHANGED") & (F.col("requires_type2") == False)
)

# ─────────────────────────────────────────────────────────────
# SCD TYPE 1: Direct overwrite (corrections)
# ─────────────────────────────────────────────────────────────
if type1_only_changes.count() > 0:
    type1_only_changes.createOrReplaceTempView("type1_changes")

    spark.sql(f"""
        MERGE INTO glue_catalog.dimensions.dim_customer target
        USING type1_changes source
        ON target.customer_id = source.customer_id AND target.is_current = true
        WHEN MATCHED THEN UPDATE SET
            target.first_name = source.first_name,
            target.last_name = source.last_name,
            target.updated_at = current_timestamp()
    """)
    print(f"Type 1 updates applied: {type1_only_changes.count()}")

# ─────────────────────────────────────────────────────────────
# SCD TYPE 2: Close existing + Insert new
# ─────────────────────────────────────────────────────────────
if type2_changes.count() > 0:
    # Prepare new rows with surrogate keys and effective dates
    new_rows = type2_changes.select(
        generate_surrogate_key(
            F.col("customer_id").cast("string"),
            F.lit(process_date)
        ).alias("surrogate_key"),
        F.col("customer_id"),
        F.col("new.first_name").alias("first_name"),
        F.col("new.last_name").alias("last_name"),
        F.col("new.address").alias("address"),
        F.col("new.city").alias("city"),
        F.col("new.state").alias("state"),
        F.col("new.zip").alias("zip"),
        F.col("new.email").alias("email"),
        F.col("new.phone").alias("phone"),
        F.col("new.tier").alias("tier"),
        F.lit(process_date).cast("date").alias("eff_start"),
        F.lit(HIGH_DATE).cast("date").alias("eff_end"),
        F.lit(True).alias("is_current"),
        # Type 6 columns
        F.col("new.tier").alias("current_tier"),      # Current value on new row
        F.col("cur.tier").alias("previous_tier"),     # Previous value
        F.current_timestamp().alias("created_at"),
        F.current_timestamp().alias("updated_at"),
        F.lit(process_date).alias("partition_date")
    )

    new_rows.createOrReplaceTempView("new_dimension_rows")

    # Step 1: Close existing current records
    spark.sql(f"""
        MERGE INTO glue_catalog.dimensions.dim_customer target
        USING new_dimension_rows source
        ON target.customer_id = source.customer_id AND target.is_current = true
        WHEN MATCHED THEN UPDATE SET
            target.eff_end = '{process_date}',
            target.is_current = false,
            target.updated_at = current_timestamp()
    """)

    # Step 2: Insert new current records
    spark.sql("""
        INSERT INTO glue_catalog.dimensions.dim_customer
        SELECT * FROM new_dimension_rows
    """)

    # Step 3: Type 6 — Update current_tier on ALL historical rows for these customers
    type6_customers = type2_changes.filter(
        F.col("new.tier") != F.col("cur.tier")
    ).select("customer_id", F.col("new.tier").alias("new_current_tier"))

    if type6_customers.count() > 0:
        type6_customers.createOrReplaceTempView("type6_updates")

        spark.sql("""
            MERGE INTO glue_catalog.dimensions.dim_customer target
            USING type6_updates source
            ON target.customer_id = source.customer_id
            WHEN MATCHED THEN UPDATE SET
                target.current_tier = source.new_current_tier,
                target.updated_at = current_timestamp()
        """)

    print(f"Type 2 inserts: {type2_changes.count()}")
    print(f"Type 6 backfills: {type6_customers.count() if type6_customers.count() > 0 else 0}")

# ─────────────────────────────────────────────────────────────
# Handle DELETES (soft delete — mark end date, don't remove)
# ─────────────────────────────────────────────────────────────
deletes = change_set.filter(F.col("change_type") == "DELETED")
if deletes.count() > 0:
    deletes.createOrReplaceTempView("deleted_records")
    spark.sql(f"""
        MERGE INTO glue_catalog.dimensions.dim_customer target
        USING deleted_records source
        ON target.customer_id = source.customer_id AND target.is_current = true
        WHEN MATCHED THEN UPDATE SET
            target.eff_end = '{process_date}',
            target.is_current = false,
            target.is_deleted = true,
            target.updated_at = current_timestamp()
    """)

job.commit()
```

### Job 4: Snapshot Generation

```python
# ─────────────────────────────────────────────────────────────
# Generate point-in-time snapshots for common query patterns
# ─────────────────────────────────────────────────────────────

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'snapshot_date', 'snapshot_type'])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

snapshot_date = args['snapshot_date']
snapshot_type = args['snapshot_type']  # 'daily', 'monthly', 'quarter_end'

# ─────────────────────────────────────────────────────────────
# Point-in-time snapshot: Who was current on snapshot_date?
# ─────────────────────────────────────────────────────────────
pit_snapshot = spark.sql(f"""
    SELECT
        customer_id,
        surrogate_key,
        first_name,
        last_name,
        address,
        city,
        state,
        zip,
        email,
        phone,
        tier,
        eff_start,
        eff_end,
        '{snapshot_date}' as snapshot_date
    FROM glue_catalog.dimensions.dim_customer
    WHERE eff_start <= '{snapshot_date}'
      AND eff_end > '{snapshot_date}'
""")

# Write as materialized snapshot (much faster for repeated queries)
pit_snapshot.writeTo(
    f"glue_catalog.dimensions.dim_customer_snapshot"
).partitionedBy("snapshot_date").append()

# Monthly snapshots: Generate for month-end
if snapshot_type == 'monthly':
    # Also generate aggregate metrics per snapshot
    snapshot_metrics = pit_snapshot.groupBy("state", "tier").agg(
        F.count("*").alias("customer_count"),
        F.countDistinct("zip").alias("unique_zips")
    ).withColumn("snapshot_date", F.lit(snapshot_date))

    snapshot_metrics.writeTo(
        "glue_catalog.dimensions.dim_customer_snapshot_metrics"
    ).partitionedBy("snapshot_date").append()

print(f"Snapshot generated for {snapshot_date}: {pit_snapshot.count()} customers")
job.commit()
```

### Job 5: History Compaction & Optimization

```python
# ─────────────────────────────────────────────────────────────
# Iceberg table maintenance for SCD tables
# ─────────────────────────────────────────────────────────────

args = getResolvedOptions(sys.argv, ['JOB_NAME'])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# ─────────────────────────────────────────────────────────────
# 1. Compact small files (daily MERGE creates many small files)
# ─────────────────────────────────────────────────────────────
spark.sql("""
    CALL glue_catalog.system.rewrite_data_files(
        table => 'dimensions.dim_customer',
        strategy => 'sort',
        sort_order => 'customer_id ASC, eff_start ASC',
        options => map(
            'target-file-size-bytes', '536870912',
            'min-file-size-bytes', '67108864',
            'max-file-size-bytes', '1073741824',
            'partial-progress.enabled', 'true',
            'partial-progress.max-commits', '10'
        )
    )
""")

# ─────────────────────────────────────────────────────────────
# 2. Expire old Iceberg snapshots (keep 30 days for time travel)
# ─────────────────────────────────────────────────────────────
spark.sql("""
    CALL glue_catalog.system.expire_snapshots(
        table => 'dimensions.dim_customer',
        older_than => TIMESTAMP '2024-01-01 00:00:00',
        retain_last => 30,
        stream_results => true
    )
""")

# ─────────────────────────────────────────────────────────────
# 3. Remove orphan files
# ─────────────────────────────────────────────────────────────
spark.sql("""
    CALL glue_catalog.system.remove_orphan_files(
        table => 'dimensions.dim_customer',
        older_than => TIMESTAMP '2024-01-01 00:00:00'
    )
""")

# ─────────────────────────────────────────────────────────────
# 4. Rewrite manifests for faster query planning
# ─────────────────────────────────────────────────────────────
spark.sql("""
    CALL glue_catalog.system.rewrite_manifests(
        table => 'dimensions.dim_customer'
    )
""")

print("Compaction and maintenance complete")
job.commit()
```

### Handling Out-of-Order Changes

```python
# ─────────────────────────────────────────────────────────────
# Late-arriving dimension change handling
#
# Scenario: We receive a change dated 2024-01-15 on 2024-02-01.
# The record has already been superseded by a 2024-01-20 change.
# We must INSERT the late record in the correct historical position.
# ─────────────────────────────────────────────────────────────

def handle_late_arriving_change(spark, customer_id, change_date, new_values):
    """
    Insert a late-arriving change into the correct position in history.
    
    Timeline example:
    Existing:  [2024-01-01 → 2024-01-20] [2024-01-20 → 9999-12-31]
    Late:      Change happened on 2024-01-15
    Result:    [2024-01-01 → 2024-01-15] [2024-01-15 → 2024-01-20] [2024-01-20 → 9999-12-31]
    """
    
    # Find the record that was active on the change_date
    affected_record = spark.sql(f"""
        SELECT * FROM glue_catalog.dimensions.dim_customer
        WHERE customer_id = '{customer_id}'
          AND eff_start <= '{change_date}'
          AND eff_end > '{change_date}'
    """)
    
    if affected_record.count() == 0:
        raise ValueError(f"No active record found for {customer_id} on {change_date}")
    
    existing = affected_record.first()
    
    # Step 1: Shrink the existing record's end date
    spark.sql(f"""
        UPDATE glue_catalog.dimensions.dim_customer
        SET eff_end = '{change_date}', updated_at = current_timestamp()
        WHERE surrogate_key = '{existing.surrogate_key}'
    """)
    
    # Step 2: Insert the late-arriving record
    # Its end date = the original record's end date (not 9999-12-31!)
    new_surrogate = hashlib.sha256(
        f"{customer_id}|{change_date}".encode()
    ).hexdigest()[:16]
    
    spark.sql(f"""
        INSERT INTO glue_catalog.dimensions.dim_customer
        VALUES (
            '{new_surrogate}',
            '{customer_id}',
            '{new_values["first_name"]}',
            '{new_values["last_name"]}',
            '{new_values["state"]}',
            -- ... other columns ...
            '{change_date}',            -- eff_start
            '{existing.eff_end}',       -- eff_end = original end, NOT 9999-12-31
            {existing.is_current},      -- preserve current flag from original
            current_timestamp(),
            current_timestamp()
        )
    """)
    
    print(f"Late-arriving change inserted for {customer_id} at {change_date}")
```

### Bridge Tables for Multi-Valued Dimensions

```python
# ─────────────────────────────────────────────────────────────
# Customer can belong to multiple segments simultaneously
# Bridge table tracks segment membership history
# ─────────────────────────────────────────────────────────────

def build_customer_segment_bridge(spark, process_date):
    """
    A customer may be in: ['High-Value', 'Early-Adopter', 'West-Coast']
    Each membership has its own SCD Type 2 history.
    """
    
    # Read segment assignments from source
    segment_changes = spark.read.parquet(
        f"s3://lake/landing/customer_segments/{process_date}/"
    )
    
    # SCD Type 2 on the bridge table
    spark.sql(f"""
        MERGE INTO glue_catalog.dimensions.bridge_customer_segment target
        USING segment_changes source
        ON target.customer_id = source.customer_id
           AND target.segment_id = source.segment_id
           AND target.is_current = true
        WHEN MATCHED AND source.action = 'REMOVE' THEN
            UPDATE SET
                target.eff_end = '{process_date}',
                target.is_current = false
        WHEN NOT MATCHED AND source.action = 'ADD' THEN
            INSERT (customer_id, segment_id, eff_start, eff_end, is_current)
            VALUES (source.customer_id, source.segment_id,
                    '{process_date}', '9999-12-31', true)
    """)
```

---

## Production Handling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Late-Arriving Changes Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│  LATE-ARRIVING CHANGE DECISION TREE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Change arrives with event_date < current process_date           │
│                                                                  │
│  Q1: Is event_date within the "restatement window" (7 days)?    │
│      YES → Process normally with correct effective date          │
│      NO  → Route to manual review queue                          │
│                                                                  │
│  Q2: Does inserting this change create a gap?                    │
│      YES → Reject, log error, alert data steward                │
│      NO  → Insert in correct chronological position              │
│                                                                  │
│  Q3: Has a downstream fact table already used the wrong dim?     │
│      YES → Trigger fact table restatement job                    │
│      NO  → Insert silently, no downstream impact                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Collision Handling

```python
# Surrogate key collision detection and resolution
def validate_surrogate_keys(spark):
    """Check for duplicate surrogate keys (should never happen with deterministic hashing)."""
    
    collisions = spark.sql("""
        SELECT surrogate_key, COUNT(*) as cnt
        FROM glue_catalog.dimensions.dim_customer
        GROUP BY surrogate_key
        HAVING COUNT(*) > 1
    """)
    
    if collisions.count() > 0:
        # Alert and resolve: append sequence number to hash
        print(f"CRITICAL: {collisions.count()} surrogate key collisions detected!")
        # Resolution: regenerate with additional entropy
        # hash(business_key + eff_start + version_number)
```

### Partition Strategy for Historical Tables

```
┌───────────────────────────────────────────────────────────────┐
│  PARTITION STRATEGY                                            │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  Primary partition: is_current (boolean)                       │
│    - 99% of queries hit current=true (500M rows)              │
│    - Historical queries scan current=false (7.5B rows)        │
│                                                                │
│  Secondary partition: eff_start_year (for historical)          │
│    - Enables time-bounded scans                                │
│    - ~1B rows per year in historical partition                 │
│                                                                │
│  Sort order within files: customer_id, eff_start              │
│    - Enables efficient MERGE (sorted merge join)              │
│    - Point-in-time queries benefit from clustering            │
│                                                                │
│  Iceberg hidden partitioning:                                  │
│    PARTITIONED BY (is_current, years(eff_start))              │
│    No partition columns in data — automatic routing           │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

### Iceberg Table DDL

```sql
CREATE TABLE glue_catalog.dimensions.dim_customer (
    surrogate_key       STRING,
    customer_id         STRING,
    first_name          STRING,
    last_name           STRING,
    address             STRING,
    city                STRING,
    state               STRING,
    zip                 STRING,
    email               STRING,
    phone               STRING,
    tier                STRING,
    -- Type 6 columns
    current_tier        STRING,
    previous_tier       STRING,
    -- SCD metadata
    eff_start           DATE,
    eff_end             DATE,
    is_current          BOOLEAN,
    is_deleted          BOOLEAN,
    -- Audit
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP,
    source_system       STRING,
    change_hash         STRING
)
USING iceberg
PARTITIONED BY (is_current, years(eff_start))
TBLPROPERTIES (
    'write.merge.mode' = 'merge-on-read',
    'write.update.mode' = 'merge-on-read',
    'write.delete.mode' = 'merge-on-read',
    'read.split.target-size' = '268435456',
    'write.target-file-size-bytes' = '536870912',
    'write.distribution-mode' = 'hash',
    'write.sort-order' = 'customer_id ASC, eff_start ASC'
);
```

### Validation Rules

```python
def validate_scd_integrity(spark, table_name):
    """
    Validate no gaps and no overlaps in effective date ranges.
    Run after every SCD merge job.
    """
    
    # Rule 1: No overlaps — for any customer_id, date ranges must not overlap
    overlaps = spark.sql(f"""
        SELECT a.customer_id, a.surrogate_key, b.surrogate_key,
               a.eff_start, a.eff_end, b.eff_start, b.eff_end
        FROM glue_catalog.dimensions.{table_name} a
        JOIN glue_catalog.dimensions.{table_name} b
          ON a.customer_id = b.customer_id
          AND a.surrogate_key != b.surrogate_key
          AND a.eff_start < b.eff_end
          AND a.eff_end > b.eff_start
    """)
    
    # Rule 2: Exactly one current record per business key
    multi_current = spark.sql(f"""
        SELECT customer_id, COUNT(*) as current_count
        FROM glue_catalog.dimensions.{table_name}
        WHERE is_current = true AND is_deleted = false
        GROUP BY customer_id
        HAVING COUNT(*) > 1
    """)
    
    # Rule 3: No gaps — consecutive records must have matching start/end
    gaps = spark.sql(f"""
        WITH ordered AS (
            SELECT customer_id, eff_start, eff_end,
                   LEAD(eff_start) OVER (
                       PARTITION BY customer_id ORDER BY eff_start
                   ) as next_start
            FROM glue_catalog.dimensions.{table_name}
            WHERE is_deleted = false
        )
        SELECT * FROM ordered
        WHERE next_start IS NOT NULL AND eff_end != next_start
    """)
    
    # Rule 4: Current record must have eff_end = 9999-12-31
    bad_current = spark.sql(f"""
        SELECT customer_id, eff_end
        FROM glue_catalog.dimensions.{table_name}
        WHERE is_current = true AND eff_end != DATE '9999-12-31'
    """)
    
    results = {
        "overlaps": overlaps.count(),
        "multi_current": multi_current.count(),
        "gaps": gaps.count(),
        "bad_current_end_date": bad_current.count()
    }
    
    for check, count in results.items():
        if count > 0:
            print(f"VALIDATION FAILED: {check} = {count} violations")
            # Push metric to CloudWatch
            # Trigger SNS alert
    
    return all(v == 0 for v in results.values())
```

---

## Query Patterns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Pattern 1: Current State (Most Common — 90% of Queries)

```sql
-- Fast: Partition pruning on is_current=true scans only 500M rows, not 8B
SELECT customer_id, first_name, last_name, state, tier
FROM dim_customer
WHERE is_current = true
  AND state = 'CA';
```

### Pattern 2: Point-in-Time (As-Of Query)

```sql
-- "What was this customer's tier when they made purchase X?"
SELECT c.customer_id, c.tier, c.state
FROM dim_customer c
JOIN fact_orders o ON c.customer_id = o.customer_id
WHERE o.order_id = 'ORD-12345'
  AND c.eff_start <= o.order_date
  AND c.eff_end > o.order_date;
```

### Pattern 3: Historical Aggregation with Correct Attribution

```sql
-- "Q2 2023 revenue by customer tier, using tier AT TIME of each order"
SELECT c.tier AS tier_at_purchase,
       SUM(o.amount) AS revenue,
       COUNT(DISTINCT o.customer_id) AS customers
FROM fact_orders o
JOIN dim_customer c
  ON o.customer_id = c.customer_id
  AND c.eff_start <= o.order_date
  AND c.eff_end > o.order_date
WHERE o.order_date BETWEEN '2023-04-01' AND '2023-06-30'
GROUP BY c.tier;
```

### Pattern 4: Change History for a Specific Customer

```sql
-- "Show me all changes to customer 123"
SELECT surrogate_key, state, tier, email, eff_start, eff_end, is_current
FROM dim_customer
WHERE customer_id = '123'
ORDER BY eff_start;
```

### Pattern 5: ML Feature Engineering (Point-in-Time Correct)

```sql
-- Features as of 30 days before each order (no data leakage)
SELECT o.order_id,
       c.tier AS tier_30d_before,
       c.state AS state_30d_before,
       DATEDIFF(o.order_date, c.eff_start) AS days_in_current_state
FROM fact_orders o
JOIN dim_customer c
  ON o.customer_id = c.customer_id
  AND c.eff_start <= DATE_SUB(o.order_date, 30)
  AND c.eff_end > DATE_SUB(o.order_date, 30);
```

### Pattern 6: Type 6 Advantage — No Join Needed for Current Tier

```sql
-- Because current_tier is on EVERY row, simple filter works:
SELECT tier AS tier_at_time, current_tier, COUNT(*)
FROM dim_customer
WHERE eff_start >= '2023-01-01'
GROUP BY tier, current_tier;
-- Shows: how many customers WERE Silver but are NOW Gold, etc.
```

---

## Scaling to 500M Records with Daily Changes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Performance Characteristics

```
┌──────────────────────────────────────────────────────────────────────┐
│  SCALING METRICS                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Job 1 (CDC Ingestion):                                              │
│    Workers: 10 G.2X      Duration: 5 min      Records: 2M/run       │
│                                                                       │
│  Job 2 (Change Detection):                                           │
│    Workers: 50 G.2X      Duration: 15 min     Compare: 2M vs 500M   │
│    Key: Pushdown predicate is_current=true avoids 7.5B history rows  │
│                                                                       │
│  Job 3 (SCD Merge):                                                  │
│    Workers: 100 G.2X     Duration: 25 min     Merges: 1.5M Type 2   │
│    Key: merge-on-read mode — writes delta files, not full rewrite    │
│    Key: Sort order matches merge key — sorted merge join, not hash   │
│                                                                       │
│  Job 4 (Snapshots):                                                  │
│    Workers: 30 G.2X      Duration: 10 min     Output: 500M rows     │
│    Key: Only runs on demand or monthly (not every day)               │
│                                                                       │
│  Job 5 (Compaction):                                                 │
│    Workers: 50 G.2X      Duration: 45 min     Rewrites: ~5GB/run    │
│    Key: Runs weekly, partial-progress allows incremental compaction  │
│                                                                       │
│  DAILY COST:                                                         │
│    Total DPU-hours: ~180   Cost: ~$130/day   Monthly: ~$4,000        │
│    Storage: 8B rows × 500B avg = 4TB Parquet (S3: $92/month)        │
│                                                                       │
│  vs REDSHIFT EQUIVALENT:                                             │
│    ra3.4xlarge × 12 nodes = $47,000/month                            │
│    SAVINGS: 90%+                                                      │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Scaling Techniques

| Technique | Purpose | Impact |
|-----------|---------|--------|
| Merge-on-read (Iceberg) | Avoids rewriting entire table on each MERGE | 10x faster writes |
| Hidden partitioning (is_current) | Current-state queries scan 6% of data | 15x faster reads |
| Sort order (customer_id, eff_start) | Sorted merge join in Job 3 | 3x faster merge |
| Deterministic surrogate keys | Enables idempotent reruns | Zero duplicates |
| Partial-progress compaction | Don't block on full table rewrite | Continuous operation |
| Snapshot pre-materialization | Month-end reports in seconds | 100x faster BI |

### Auto-Scaling Configuration

```python
# Glue job configuration for the SCD merge job
job_config = {
    "WorkerType": "G.2X",
    "NumberOfWorkers": 100,
    "GlueVersion": "4.0",
    "DefaultArguments": {
        "--enable-auto-scaling": "true",
        "--conf": "spark.sql.shuffle.partitions=2000",
        "--conf": "spark.sql.adaptive.enabled=true",
        "--conf": "spark.sql.adaptive.coalescePartitions.enabled=true",
        "--conf": "spark.sql.iceberg.handle-timestamp-without-timezone=true",
        "--datalake-formats": "iceberg",
        "--enable-metrics": "true",
        "--enable-continuous-cloudwatch-log": "true",
    }
}
```

---

## Companies Using This Pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Company | Scale | Key Dimensions | SCD Types Used |
|---------|-------|----------------|----------------|
| **Walmart** | 500M customers, 100M products | Customer, Product, Store, Supplier | Type 2 + 6 for customer tier |
| **Target** | 100M loyalty members | Guest profiles, Product, Store | Type 2 for all; Type 6 for Circle status |
| **Costco** | 130M cardholders | Member, Product, Warehouse | Type 2 with 5yr retention |
| **Home Depot** | 40M Pro customers | Customer, Product, Store, Project | Type 2 + bridge tables for project membership |

### Walmart Specifics
- 4,700 US stores + Sam's Club + ecommerce
- Customer tier changes drive $200M in differential pricing
- Must track tier at time of purchase for loyalty point accuracy
- SCD on supplier terms enables contract dispute resolution
- Regulatory: 7-year history for tax compliance across state lines

### Target Specifics
- Target Circle loyalty program: tier changes trigger different coupon eligibility
- Product category reclassification: affects vendor negotiations
- Store district reassignment: changes executive compensation calculations
- Point-in-time inventory valuation: SEC reporting requirement

### Implementation Notes
- All companies use Iceberg or Delta Lake as the table format
- Glue preferred for batch SCD processing (cost-effective at scale)
- Real-time dimension updates (< 5 min) handled by streaming layer; Glue handles the bulk Type 2 merge
- Hybrid approach: streaming updates to "current" table, Glue nightly for full SCD history maintenance

---

## Summary

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌──────────────────────────────────────────────────────────────────┐
│  KEY TAKEAWAYS                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. Iceberg merge-on-read makes SCD Type 2 feasible on S3        │
│     - No full-table rewrites on each merge                        │
│     - Atomic close + insert operations                            │
│                                                                   │
│  2. Deterministic surrogate keys enable idempotent processing    │
│     - hash(business_key + effective_date) = same key every time  │
│     - Safe to rerun without duplicates                            │
│                                                                   │
│  3. Hidden partitioning (is_current) is the #1 performance win   │
│     - 90% of queries only need current state                     │
│     - Separates 500M current from 7.5B historical                │
│                                                                   │
│  4. Type 6 eliminates expensive self-joins                       │
│     - current_tier on every row = instant "upgrade from" queries │
│     - Worth the extra storage for high-value attributes           │
│                                                                   │
│  5. Validation after every run prevents silent corruption        │
│     - No gaps, no overlaps, exactly one current per key          │
│     - Catches late-arriving change issues immediately             │
│                                                                   │
│  6. Cost: ~$4K/month for 8B rows vs $47K for equivalent DW      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```
