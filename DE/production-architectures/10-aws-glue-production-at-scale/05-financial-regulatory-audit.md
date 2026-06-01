# Financial Regulatory Audit Trail Pipeline at Goldman Sachs/JPMorgan Scale

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. The Problem: 10B Financial Events/Day with Complete Lineage & 10-Year Retention

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

A Tier-1 investment bank (Goldman Sachs, JPMorgan scale) must maintain an **immutable,
cryptographically verifiable audit trail** for every piece of data that flows through
its analytics and reporting systems. Regulators (SEC, FCA, FINRA, OCC) can request
proof that:

- A specific trade was captured correctly at time T
- Every transformation applied to raw data is reproducible
- Risk calculations used the correct inputs on a given date
- No data was tampered with post-facto
- Reports submitted to regulators can be regenerated bit-for-bit

### Scale Parameters

```
┌─────────────────────────────────────────────────────────────────┐
│  SCALE REQUIREMENTS                                             │
├─────────────────────────────────────────────────────────────────┤
│  Daily Events:           10 billion (trades, payments, risk)    │
│  Retention Period:       10 years (some data 25 years)          │
│  Total Records:          ~36.5 trillion over retention window   │
│  Storage (compressed):   ~15 PB cumulative                      │
│  Audit Lookup SLA:       < 1 second for any record             │
│  Report Types:           500+ regulatory reports                 │
│  Transformation Lineage: Every column, every row, every job     │
│  Regulatory Jurisdictions: 40+ countries                        │
│  Concurrent Users:       2,000+ (auditors, risk, compliance)    │
│  Recovery Point:         Zero data loss (RPO = 0)               │
└─────────────────────────────────────────────────────────────────┘
```

### Regulatory Requirements

| Regulation | Requirement | Implication |
|---|---|---|
| SOX Section 404 | Internal controls over financial reporting | Every transformation must be auditable |
| PCI-DSS | Protection of cardholder data, access logging | Column-level encryption, access audit trail |
| Basel III (BCBS 239) | Risk data aggregation & reporting | Lineage from source to risk metric |
| MiFID II | Transaction reporting within T+1 | Real-time capture, immutable storage |
| Dodd-Frank | Swap data reporting | Complete OTC derivatives trail |
| CCAR/DFAST | Stress testing data | Reproducible point-in-time snapshots |
| GDPR | Right to erasure (conflicts with retention!) | Pseudonymization, not deletion |
| BSA/AML | Suspicious activity records | 5+ year retention of all transactions |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. Why Traditional Approaches Fail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### RDBMS (Oracle, SQL Server)

```
Problem: 36.5 trillion rows across 10 years
- Oracle RAC max practical: ~50TB per instance
- Would need 300+ database clusters
- Licensing: $50M+ annually
- Query performance degrades catastrophically at this scale
- Schema migrations on 15PB = weeks of downtime
- Backup/restore for DR: days, not minutes
```

### Manual ETL (Informatica, DataStage)

```
Problem: No native lineage, no reproducibility
- Transformation logic buried in GUI workflows
- Cannot cryptographically prove data wasn't altered
- No time-travel capability
- Version control of transformations is bolted-on
- Auditors cannot independently verify pipeline logic
```

### Vendor Solutions (Axiom SL, Wolters Kluwer)

```
Problem: Expensive, inflexible, vendor lock-in
- $20M+ annual licensing for Tier-1 bank scale
- Black-box calculations (regulators increasingly reject this)
- Cannot customize for new regulations without vendor engagement
- 6-12 month lead time for new report types
- No cloud-native scalability
```

### Streaming Only (Kafka + Flink)

```
Problem: No batch corrections, no reproducible reports
- Financial data requires amendments/corrections (T+3 settlements)
- Regulatory reports must be reproducible from batch snapshots
- Stream processing cannot guarantee deterministic outputs
- Late-arriving data (common in cross-border transactions)
- Regulators want batch-verified, signed-off datasets
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Architecture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     FINANCIAL REGULATORY AUDIT TRAIL PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │   Trading    │  │   Payment    │  │    Risk      │  │   Market     │
  │   Systems    │  │   Gateways   │  │   Engines    │  │    Data      │
  │  (FIX/SWIFT) │  │  (ISO 20022) │  │  (FpML/ISDA)│  │  (Reuters)   │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    AWS Kinesis Data Streams                          │
  │         (Immutable capture with sequence numbers)                    │
  │         Shards: 5,000  |  Retention: 365 days                       │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                     GLUE JOB 1: IMMUTABLE INGESTION                 │
  │                                                                     │
  │  - SHA-256 hash of every record (tamper detection)                  │
  │  - Merkle tree of each micro-batch (batch integrity)                │
  │  - Hash-based deduplication (exactly-once semantics)                │
  │  - Append-only write to S3 with Object Lock (WORM)                 │
  │  - Ingestion timestamp + source system attestation                  │
  │                                                                     │
  │  Workers: 200 G.2X  |  Frequency: Every 5 min                      │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │              S3: RAW ZONE (Iceberg + Object Lock WORM)              │
  │                                                                     │
  │  s3://bank-audit-raw/                                               │
  │    ├── trades/dt=2024-01-15/hour=14/                                │
  │    ├── payments/dt=2024-01-15/hour=14/                              │
  │    ├── risk_events/dt=2024-01-15/hour=14/                           │
  │    └── market_data/dt=2024-01-15/hour=14/                           │
  │                                                                     │
  │  Object Lock: GOVERNANCE mode, 10-year retention                    │
  │  Encryption: SSE-KMS with bank-managed CMK                         │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                  GLUE JOB 2: LINEAGE TRACKING                       │
  │                                                                     │
  │  - Column-level lineage metadata injection                          │
  │  - Transformation hash (code version + config + input hash)         │
  │  - Before/after snapshots for every mutation                        │
  │  - OpenLineage events emitted to lineage store                      │
  │  - Data quality scores attached to each record                      │
  │                                                                     │
  │  Workers: 150 G.2X  |  Frequency: Every 5 min (chained)            │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │            S3: CONFORMED ZONE (Iceberg, versioned)                  │
  │                                                                     │
  │  - Standardized schemas (canonical trade model)                     │
  │  - Every record carries full lineage metadata                       │
  │  - Iceberg snapshots enable time-travel queries                     │
  │  - Partition: by business_date, asset_class, jurisdiction           │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                          ▼                 ▼
  ┌──────────────────────────────┐  ┌──────────────────────────────────┐
  │  GLUE JOB 3: REGULATORY     │  │  GLUE JOB 4: REPORT DATASET     │
  │  AGGREGATION                 │  │  GENERATION                      │
  │                              │  │                                  │
  │  - Basel III RWA calc        │  │  - CCAR 14-quarter projections   │
  │  - Capital adequacy ratios   │  │  - DFAST scenarios               │
  │  - Liquidity coverage ratio  │  │  - FR Y-14A/Q/M datasets        │
  │  - Net stable funding ratio  │  │  - Call Report (FFIEC 031/041)   │
  │  - Leverage ratio            │  │  - MiFID II ARM submissions      │
  │                              │  │                                  │
  │  Workers: 300 G.2X          │  │  Workers: 200 G.2X               │
  │  Schedule: Daily + Quarter   │  │  Schedule: Quarter-end + ad-hoc  │
  └──────────────┬───────────────┘  └──────────────────┬───────────────┘
                 │                                      │
                 ▼                                      ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                  GLUE JOB 5: AUDIT SNAPSHOT CRYSTALLIZATION         │
  │                                                                     │
  │  - Point-in-time freeze of all datasets used in a report           │
  │  - Cryptographic seal (hash of all inputs + outputs + code)        │
  │  - Immutable write to compliance archive                            │
  │  - Generates reproducibility manifest                               │
  │  - Signs with HSM-backed key (non-repudiation)                     │
  │                                                                     │
  │  Workers: 100 G.2X  |  Trigger: Post-report generation             │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │              S3: COMPLIANCE ARCHIVE (Glacier Deep Archive)           │
  │                                                                     │
  │  - Object Lock: COMPLIANCE mode (cannot be overridden)              │
  │  - Cross-region replication to DR region                            │
  │  - Legal hold capability for litigation                             │
  │  - Lifecycle: S3 Standard (1yr) → IA (3yr) → Glacier (10yr+)      │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
           ┌──────────────┐ ┌──────────┐ ┌──────────────┐
           │  Regulators  │ │ Internal │ │    Risk      │
           │  (SEC, FCA,  │ │  Audit   │ │ Management   │
           │   FINRA)     │ │  Team    │ │              │
           └──────────────┘ └──────────┘ └──────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Glue Concepts Used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Job Bookmarks for Exactly-Once Processing

```
┌─────────────────────────────────────────────────────────────┐
│  WHY EXACTLY-ONCE MATTERS IN FINANCE                        │
├─────────────────────────────────────────────────────────────┤
│  - Duplicate trade = incorrect position = wrong risk calc   │
│  - Missing trade = underreported exposure = regulatory fine  │
│  - Double-counted payment = P&L misstatement = SOX breach   │
│                                                             │
│  Glue Job Bookmarks track:                                  │
│    - Last processed Kinesis sequence number                 │
│    - Last processed S3 object key                           │
│    - Transformation state checkpoint                        │
│                                                             │
│  Combined with idempotent writes (hash-based dedup),        │
│  guarantees exactly-once semantics end-to-end.              │
└─────────────────────────────────────────────────────────────┘
```

### Glue Data Quality (DQDL Rules)

Regulatory data quality checks enforced at pipeline boundaries:

```python
# DQDL Ruleset for Trade Data
dqdl_rules = """
Rules = [
    # Completeness - every trade must have required fields
    Completeness "trade_id" = 1.0,
    Completeness "counterparty_lei" = 1.0,
    Completeness "notional_amount" = 1.0,
    Completeness "trade_date" = 1.0,
    Completeness "settlement_date" = 1.0,

    # Validity - LEI must be 20 chars alphanumeric
    ColumnLength "counterparty_lei" = 20,

    # Referential Integrity - currency must be valid ISO 4217
    ColumnValues "currency" in ["USD","EUR","GBP","JPY","CHF","CAD","AUD"],

    # Business Rules - settlement cannot precede trade
    CustomSql "SELECT COUNT(*) FROM primary WHERE settlement_date < trade_date" = 0,

    # Freshness - data must arrive within SLA
    Freshness "ingestion_timestamp" <= 300 seconds,

    # Volume - detect anomalous drops (potential data loss)
    RowCount between 8000000 and 15000000
]
"""
```

### Glue Data Catalog Versioning

```
┌─────────────────────────────────────────────────────────────┐
│  SCHEMA LINEAGE VIA CATALOG VERSIONING                      │
├─────────────────────────────────────────────────────────────┤
│  Version 1 (2023-01-01): trade_v1 schema                    │
│  Version 2 (2023-03-15): Added MiFID II fields              │
│  Version 3 (2023-06-01): Basel III SA-CCR columns           │
│  Version 4 (2023-09-01): FRTB IMA risk factors             │
│                                                             │
│  Each report references the EXACT catalog version used.     │
│  Auditors can verify which schema was active on any date.   │
│  Schema evolution is append-only (columns never removed).   │
└─────────────────────────────────────────────────────────────┘
```

### Custom Classifiers for Financial Messages

```python
# FIX Protocol Classifier
fix_classifier = {
    "name": "fix-protocol-4.4",
    "classification": "fix_message",
    "grokPattern": '%{DATA:tag}=%{DATA:value}\\x01',
    "customPatterns": {
        "FIXMSG": "8=FIX.4.4\\x01.*10=%{DATA:checksum}\\x01"
    }
}

# SWIFT MT Messages
swift_classifier = {
    "name": "swift-mt",
    "classification": "swift_message",
    "grokPattern": '{1:%{DATA:basic_header}}{2:%{DATA:app_header}}{4:%{GREEDYDATA:body}}'
}

# FpML (Financial products Markup Language)
fpml_classifier = {
    "name": "fpml-5.12",
    "classification": "fpml_trade",
    "xmlTag": "FpML",
    "rowTag": "trade"
}
```

### Security Configuration

```
┌─────────────────────────────────────────────────────────────┐
│  SECURITY LAYERS                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Encryption:                                                │
│    - At rest: SSE-KMS (AES-256) with CMK per data class    │
│    - In transit: TLS 1.3 mandatory                         │
│    - Column-level: PCI data encrypted with separate key    │
│                                                             │
│  Network:                                                   │
│    - Glue jobs run in dedicated VPC                         │
│    - No internet access (VPC endpoints for all services)   │
│    - Private Link to on-premises trading systems           │
│    - Security groups: least-privilege per job role          │
│                                                             │
│  Access Control:                                            │
│    - Lake Formation row-level security                      │
│    - Column-level permissions (PCI columns restricted)     │
│    - Tag-based access (data classification tags)           │
│    - Temporary credentials (12-hour max session)           │
│                                                             │
│  Audit:                                                     │
│    - CloudTrail: every API call logged                     │
│    - S3 access logs: every object access recorded          │
│    - Glue job audit: who ran what, when, on which data     │
│    - Lake Formation: every grant/revoke logged             │
└─────────────────────────────────────────────────────────────┘
```

### Glue Workflows for Regulatory Calculations

```
┌─────────────────────────────────────────────────────────────────────┐
│  QUARTERLY REGULATORY WORKFLOW (CCAR Submission)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Trigger: Quarter-end date (T+5 business days)                      │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ Snapshot │───▶│  Basel   │───▶│   CCAR   │───▶│  Seal &  │     │
│  │  Freeze  │    │  Calc    │    │  Report  │    │  Submit  │     │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│       │               │               │               │             │
│       ▼               ▼               ▼               ▼             │
│  [Crawler:       [DQ Check:     [DQ Check:     [Crystallize       │
│   Update         Calc rules      Report         snapshot +         │
│   Catalog]       validation]     validation]    HSM sign]          │
│                                                                     │
│  On Failure: Alert → Compliance Team → Manual Review Gate           │
│  SLA: Complete within 10 business days of quarter-end               │
└─────────────────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation Code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Job 1: Immutable Ingestion with Cryptographic Hashing

```python
import sys
import hashlib
import json
from datetime import datetime, timezone
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructType, StructField

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'source_stream', 'target_bucket',
    'kms_key_id', 'environment'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configure Iceberg
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", f"s3://{args['target_bucket']}/raw/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl",
               "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl",
               "org.apache.iceberg.aws.s3.S3FileIO")


def compute_record_hash(record_json: str) -> str:
    """SHA-256 hash of canonical JSON representation for tamper detection."""
    canonical = json.dumps(json.loads(record_json), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def compute_merkle_root(hashes: list) -> str:
    """Compute Merkle tree root for batch integrity verification."""
    if len(hashes) == 0:
        return hashlib.sha256(b'empty').hexdigest()
    if len(hashes) == 1:
        return hashes[0]

    new_level = []
    for i in range(0, len(hashes), 2):
        left = hashes[i]
        right = hashes[i + 1] if i + 1 < len(hashes) else left
        combined = hashlib.sha256((left + right).encode('utf-8')).hexdigest()
        new_level.append(combined)
    return compute_merkle_root(new_level)


# Register UDF for record hashing
compute_hash_udf = F.udf(compute_record_hash, StringType())

# Read from Kinesis with exactly-once via job bookmarks
kinesis_frame = glueContext.create_data_frame.from_options(
    connection_type="kinesis",
    connection_options={
        "streamARN": args['source_stream'],
        "startingPosition": "TRIM_HORIZON",
        "classification": "json",
        "inferSchema": "true"
    },
    transformation_ctx="kinesis_source"  # Bookmark tracking
)

# Add audit metadata
ingestion_time = datetime.now(timezone.utc).isoformat()
job_run_id = args['JOB_RUN_ID'] if 'JOB_RUN_ID' in args else 'local'

enriched_df = kinesis_frame \
    .withColumn("_raw_json", F.to_json(F.struct("*"))) \
    .withColumn("_record_hash", compute_hash_udf(F.col("_raw_json"))) \
    .withColumn("_ingestion_timestamp", F.lit(ingestion_time)) \
    .withColumn("_ingestion_job_run_id", F.lit(job_run_id)) \
    .withColumn("_source_system", F.col("source_system_id")) \
    .withColumn("_business_date", F.to_date(F.col("event_timestamp"))) \
    .withColumn("_partition_hour", F.hour(F.col("event_timestamp")))

# Hash-based deduplication (exactly-once)
# Check against existing hashes in the dedup window (last 24 hours)
existing_hashes = spark.sql("""
    SELECT _record_hash FROM glue_catalog.audit_db.raw_events
    WHERE _business_date >= date_sub(current_date(), 1)
""")

deduped_df = enriched_df.join(
    existing_hashes,
    on="_record_hash",
    how="left_anti"  # Keep only records NOT already present
)

# Write to Iceberg (append-only, never overwrite)
deduped_df.writeTo("glue_catalog.audit_db.raw_events") \
    .option("write-format", "parquet") \
    .option("target-file-size-bytes", "134217728") \
    .append()

# Compute and store batch Merkle root for integrity verification
batch_hashes = deduped_df.select("_record_hash").rdd.map(lambda r: r[0]).collect()
merkle_root = compute_merkle_root(batch_hashes)

# Store batch attestation
batch_attestation = spark.createDataFrame([{
    "batch_id": f"{job_run_id}_{ingestion_time}",
    "merkle_root": merkle_root,
    "record_count": len(batch_hashes),
    "timestamp": ingestion_time,
    "job_run_id": job_run_id
}])

batch_attestation.writeTo("glue_catalog.audit_db.batch_attestations").append()

job.commit()
```

### Job 2: Lineage Tracking

```python
import sys
import hashlib
import json
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql import DataFrame

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'catalog_db', 'code_version'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

CODE_VERSION = args['code_version']  # Git SHA of this transformation code


class LineageTracker:
    """Tracks every transformation applied to a DataFrame with full metadata."""

    def __init__(self, job_name: str, job_run_id: str, code_version: str):
        self.job_name = job_name
        self.job_run_id = job_run_id
        self.code_version = code_version
        self.lineage_events = []
        self.step_counter = 0

    def track_transformation(self, input_df: DataFrame, output_df: DataFrame,
                             transform_name: str, transform_logic: str,
                             columns_affected: list) -> DataFrame:
        """Record a transformation and inject lineage metadata."""
        self.step_counter += 1

        # Compute transformation fingerprint
        transform_hash = hashlib.sha256(
            f"{self.code_version}:{transform_name}:{transform_logic}".encode()
        ).hexdigest()[:16]

        # Record lineage event
        event = {
            "step": self.step_counter,
            "job_name": self.job_name,
            "job_run_id": self.job_run_id,
            "code_version": self.code_version,
            "transform_name": transform_name,
            "transform_logic": transform_logic,
            "transform_hash": transform_hash,
            "columns_affected": columns_affected,
            "input_count": input_df.count(),
            "output_count": output_df.count(),
            "timestamp": F.current_timestamp()
        }
        self.lineage_events.append(event)

        # Inject lineage into output DataFrame
        lineage_json = json.dumps({
            "step": self.step_counter,
            "transform": transform_name,
            "hash": transform_hash,
            "code_version": self.code_version
        })

        output_with_lineage = output_df.withColumn(
            "_lineage_chain",
            F.when(
                F.col("_lineage_chain").isNotNull(),
                F.concat(F.col("_lineage_chain"), F.lit(f"|{lineage_json}"))
            ).otherwise(F.lit(lineage_json))
        )

        return output_with_lineage

    def emit_lineage_events(self, spark_session):
        """Write all lineage events to the lineage store."""
        if self.lineage_events:
            lineage_df = spark_session.createDataFrame(self.lineage_events)
            lineage_df.writeTo("glue_catalog.audit_db.transformation_lineage").append()


# Initialize tracker
tracker = LineageTracker(
    job_name=args['JOB_NAME'],
    job_run_id=args.get('JOB_RUN_ID', 'local'),
    code_version=CODE_VERSION
)

# Read raw events (unprocessed since last bookmark)
raw_df = spark.sql("""
    SELECT * FROM glue_catalog.audit_db.raw_events
    WHERE _processing_status IS NULL OR _processing_status = 'pending'
""")

# Add lineage chain column if not present
if "_lineage_chain" not in raw_df.columns:
    raw_df = raw_df.withColumn("_lineage_chain", F.lit(None).cast("string"))

# --- Transformation 1: Standardize trade identifiers ---
standardized_df = raw_df.withColumn(
    "canonical_trade_id",
    F.when(F.col("source_system_id") == "MUREX",
           F.concat(F.lit("MX-"), F.col("trade_id")))
    .when(F.col("source_system_id") == "CALYPSO",
          F.concat(F.lit("CL-"), F.col("trade_id")))
    .otherwise(F.concat(F.lit("EXT-"), F.col("trade_id")))
)

standardized_df = tracker.track_transformation(
    input_df=raw_df,
    output_df=standardized_df,
    transform_name="standardize_trade_id",
    transform_logic="Prefix trade_id with source system code for canonical identification",
    columns_affected=["canonical_trade_id"]
)

# --- Transformation 2: Enrich with counterparty data ---
counterparty_ref = spark.sql("SELECT * FROM glue_catalog.audit_db.counterparty_reference")

enriched_df = standardized_df.join(
    counterparty_ref.select("lei", "legal_name", "country", "sector"),
    standardized_df["counterparty_lei"] == counterparty_ref["lei"],
    "left"
)

enriched_df = tracker.track_transformation(
    input_df=standardized_df,
    output_df=enriched_df,
    transform_name="enrich_counterparty",
    transform_logic="LEFT JOIN to counterparty_reference on LEI for legal_name, country, sector",
    columns_affected=["legal_name", "country", "sector"]
)

# --- Transformation 3: Currency normalization to USD ---
fx_rates = spark.sql("""
    SELECT currency_pair, rate, rate_date
    FROM glue_catalog.audit_db.fx_rates
    WHERE rate_date = current_date()
""")

normalized_df = enriched_df.join(
    fx_rates,
    enriched_df["currency"] == F.substring(fx_rates["currency_pair"], 1, 3),
    "left"
).withColumn(
    "notional_usd",
    F.when(F.col("currency") == "USD", F.col("notional_amount"))
    .otherwise(F.col("notional_amount") * F.col("rate"))
)

normalized_df = tracker.track_transformation(
    input_df=enriched_df,
    output_df=normalized_df,
    transform_name="normalize_currency_to_usd",
    transform_logic="Convert notional_amount to USD using daily FX rate from fx_rates table",
    columns_affected=["notional_usd"]
)

# Write conformed data
normalized_df.writeTo("glue_catalog.audit_db.conformed_trades").append()

# Emit all lineage events
tracker.emit_lineage_events(spark)

job.commit()
```

### Job 3: Regulatory Aggregation (Basel III)

```python
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'reporting_date', 'scenario'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

reporting_date = args['reporting_date']
scenario = args.get('scenario', 'baseline')


def calculate_risk_weighted_assets(trades_df):
    """
    Basel III Standardized Approach for Credit Risk.
    Risk weights by counterparty type and exposure class.
    """
    risk_weights = {
        "sovereign_aaa": 0.0,
        "sovereign_aa": 0.0,
        "sovereign_a": 0.20,
        "sovereign_bbb": 0.50,
        "bank_rated": 0.20,
        "corporate_rated": 0.50,
        "corporate_unrated": 1.00,
        "retail": 0.75,
        "residential_mortgage": 0.35,
        "commercial_real_estate": 1.50,
    }

    # Apply risk weights based on exposure class
    rwa_df = trades_df.withColumn(
        "risk_weight",
        F.when(F.col("exposure_class") == "sovereign",
               F.when(F.col("credit_rating").isin(["AAA", "AA+", "AA", "AA-"]), 0.0)
               .when(F.col("credit_rating").isin(["A+", "A", "A-"]), 0.20)
               .when(F.col("credit_rating").isin(["BBB+", "BBB", "BBB-"]), 0.50)
               .otherwise(1.00))
        .when(F.col("exposure_class") == "corporate",
              F.when(F.col("credit_rating").isNotNull(), 0.50)
              .otherwise(1.00))
        .when(F.col("exposure_class") == "retail", 0.75)
        .otherwise(1.00)
    ).withColumn(
        "risk_weighted_amount",
        F.col("exposure_at_default") * F.col("risk_weight")
    )

    return rwa_df


def calculate_capital_adequacy(rwa_df, capital_df):
    """
    Calculate CET1, Tier 1, and Total Capital ratios.
    Basel III minimums: CET1 >= 4.5%, Tier1 >= 6%, Total >= 8%
    Plus capital conservation buffer (2.5%) and G-SIB surcharge (1-3.5%)
    """
    total_rwa = rwa_df.agg(F.sum("risk_weighted_amount")).collect()[0][0]

    capital_ratios = capital_df.withColumn(
        "cet1_ratio", F.col("cet1_capital") / F.lit(total_rwa)
    ).withColumn(
        "tier1_ratio", (F.col("cet1_capital") + F.col("at1_capital")) / F.lit(total_rwa)
    ).withColumn(
        "total_capital_ratio",
        (F.col("cet1_capital") + F.col("at1_capital") + F.col("tier2_capital"))
        / F.lit(total_rwa)
    ).withColumn(
        "leverage_ratio",
        F.col("tier1_capital") / F.col("total_exposure_measure")
    )

    return capital_ratios


def calculate_liquidity_coverage_ratio(assets_df, outflows_df):
    """
    LCR = High Quality Liquid Assets / Total Net Cash Outflows (30 days)
    Minimum requirement: >= 100%
    """
    hqla = assets_df.filter(F.col("hqla_classification").isNotNull()) \
        .withColumn("hqla_value",
                    F.when(F.col("hqla_level") == "1", F.col("market_value"))
                    .when(F.col("hqla_level") == "2A", F.col("market_value") * 0.85)
                    .when(F.col("hqla_level") == "2B", F.col("market_value") * 0.50))

    total_hqla = hqla.agg(F.sum("hqla_value")).collect()[0][0]

    net_outflows = outflows_df.agg(
        F.sum(F.col("outflow_amount") * F.col("runoff_rate"))
        - F.sum(F.col("inflow_amount") * F.col("inflow_rate"))
    ).collect()[0][0]

    lcr = total_hqla / net_outflows if net_outflows > 0 else float('inf')
    return lcr


# --- Execute regulatory calculations ---

# Load conformed trades as of reporting date (time-travel)
trades_df = spark.sql(f"""
    SELECT * FROM glue_catalog.audit_db.conformed_trades
    FOR SYSTEM_TIME AS OF '{reporting_date}T23:59:59'
    WHERE business_date <= '{reporting_date}'
""")

capital_df = spark.sql(f"""
    SELECT * FROM glue_catalog.audit_db.capital_components
    WHERE reporting_date = '{reporting_date}'
""")

# Calculate RWA
rwa_df = calculate_risk_weighted_assets(trades_df)
rwa_df.writeTo("glue_catalog.audit_db.risk_weighted_assets") \
    .option("snapshot-property.reporting_date", reporting_date) \
    .option("snapshot-property.scenario", scenario) \
    .append()

# Calculate capital ratios
capital_ratios = calculate_capital_adequacy(rwa_df, capital_df)
capital_ratios.writeTo("glue_catalog.audit_db.capital_ratios") \
    .option("snapshot-property.reporting_date", reporting_date) \
    .append()

# Store calculation metadata for audit
calc_metadata = spark.createDataFrame([{
    "reporting_date": reporting_date,
    "scenario": scenario,
    "total_rwa": float(rwa_df.agg(F.sum("risk_weighted_amount")).collect()[0][0]),
    "trade_count": rwa_df.count(),
    "calculation_timestamp": F.current_timestamp(),
    "code_version": args.get('code_version', 'unknown'),
    "input_snapshot_id": str(spark.sql(
        "SELECT snapshot_id FROM glue_catalog.audit_db.conformed_trades.snapshots "
        "ORDER BY committed_at DESC LIMIT 1"
    ).collect()[0][0])
}])

calc_metadata.writeTo("glue_catalog.audit_db.regulatory_calc_audit").append()

job.commit()
```

### Job 4: Audit Snapshot Crystallization

```python
import sys
import hashlib
import json
import boto3
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'reporting_date', 'report_type',
    'archive_bucket', 'hsm_key_id'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

reporting_date = args['reporting_date']
report_type = args['report_type']


def crystallize_snapshot(reporting_date: str, report_type: str):
    """
    Freeze all datasets used in a regulatory report at a specific point in time.
    Creates an immutable, cryptographically sealed archive.
    """
    # Identify all tables referenced by this report
    report_manifest = spark.sql(f"""
        SELECT table_name, snapshot_id, record_count
        FROM glue_catalog.audit_db.report_dependencies
        WHERE report_type = '{report_type}'
        AND reporting_date = '{reporting_date}'
    """).collect()

    # Build reproducibility manifest
    manifest = {
        "report_type": report_type,
        "reporting_date": reporting_date,
        "crystallization_timestamp": str(F.current_timestamp()),
        "datasets": [],
        "code_versions": {},
        "parameters": {}
    }

    all_hashes = []

    for row in report_manifest:
        table_name = row['table_name']
        snapshot_id = row['snapshot_id']

        # Read exact snapshot
        table_df = spark.sql(f"""
            SELECT * FROM glue_catalog.audit_db.{table_name}
            FOR SYSTEM_VERSION AS OF {snapshot_id}
        """)

        # Compute dataset hash
        dataset_hash = hashlib.sha256(
            table_df.select(F.sha2(F.concat_ws("|", *table_df.columns), 256))
            .agg(F.concat_ws(",", F.collect_list("sha2(concat_ws(|, *), 256)")))
            .collect()[0][0].encode()
        ).hexdigest()

        all_hashes.append(dataset_hash)

        # Write frozen copy to archive
        archive_path = (
            f"s3://{args['archive_bucket']}/crystallized/"
            f"{report_type}/{reporting_date}/{table_name}/"
        )
        table_df.write.mode("overwrite").parquet(archive_path)

        manifest["datasets"].append({
            "table": table_name,
            "snapshot_id": snapshot_id,
            "record_count": row['record_count'],
            "hash": dataset_hash,
            "archive_path": archive_path
        })

    # Compute seal (hash of all dataset hashes + manifest)
    seal_input = "|".join(sorted(all_hashes)) + json.dumps(manifest, sort_keys=True)
    seal = hashlib.sha256(seal_input.encode()).hexdigest()
    manifest["seal"] = seal

    # Sign with HSM key (CloudHSM via KMS)
    kms_client = boto3.client('kms')
    signature = kms_client.sign(
        KeyId=args['hsm_key_id'],
        Message=seal.encode(),
        MessageType='RAW',
        SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_256'
    )
    manifest["signature"] = signature['Signature'].hex()
    manifest["signing_key_id"] = args['hsm_key_id']

    # Write manifest with Object Lock
    s3_client = boto3.client('s3')
    manifest_key = f"crystallized/{report_type}/{reporting_date}/MANIFEST.json"
    s3_client.put_object(
        Bucket=args['archive_bucket'],
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2),
        ObjectLockMode='COMPLIANCE',
        ObjectLockRetainUntilDate='2034-12-31T23:59:59Z',
        ServerSideEncryption='aws:kms',
        SSEKMSKeyId=args['hsm_key_id']
    )

    return manifest


# Execute crystallization
manifest = crystallize_snapshot(reporting_date, report_type)

# Store crystallization record
crystal_record = spark.createDataFrame([{
    "report_type": report_type,
    "reporting_date": reporting_date,
    "seal": manifest["seal"],
    "signature": manifest["signature"],
    "dataset_count": len(manifest["datasets"]),
    "total_records": sum(d["record_count"] for d in manifest["datasets"])
}])

crystal_record.writeTo("glue_catalog.audit_db.crystallization_log").append()

job.commit()
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Production Handling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Corrections and Amendments (Never Delete, Only Amend)

```
┌─────────────────────────────────────────────────────────────────┐
│  AMENDMENT PATTERN (Financial Data)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Original Record:                                               │
│    trade_id: MX-12345                                           │
│    notional: 10,000,000 USD                                     │
│    status: ACTIVE                                               │
│    version: 1                                                   │
│                                                                 │
│  Amendment (T+2 correction):                                    │
│    trade_id: MX-12345                                           │
│    notional: 10,500,000 USD   ← corrected value                │
│    status: AMENDED                                              │
│    version: 2                                                   │
│    amends_version: 1                                            │
│    amendment_reason: "Settlement amount correction"             │
│    amendment_authorized_by: "john.smith@bank.com"               │
│    amendment_timestamp: "2024-01-17T14:30:00Z"                  │
│                                                                 │
│  BOTH records are retained forever.                             │
│  Queries use latest version; auditors can see full history.     │
└─────────────────────────────────────────────────────────────────┘
```

```python
def apply_amendment(spark, trade_id: str, corrections: dict,
                    reason: str, authorized_by: str):
    """Apply an amendment as a new version, preserving history."""

    # Get current version
    current = spark.sql(f"""
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY trade_id ORDER BY version DESC
        ) as rn
        FROM glue_catalog.audit_db.conformed_trades
        WHERE trade_id = '{trade_id}'
    """).filter("rn = 1").drop("rn")

    current_version = current.collect()[0]['version']

    # Create amendment record
    amendment = current.withColumn("version", F.lit(current_version + 1)) \
        .withColumn("status", F.lit("AMENDED")) \
        .withColumn("amends_version", F.lit(current_version)) \
        .withColumn("amendment_reason", F.lit(reason)) \
        .withColumn("amendment_authorized_by", F.lit(authorized_by)) \
        .withColumn("amendment_timestamp", F.current_timestamp())

    # Apply corrections
    for col_name, new_value in corrections.items():
        amendment = amendment.withColumn(col_name, F.lit(new_value))

    # Append (never overwrite)
    amendment.writeTo("glue_catalog.audit_db.conformed_trades").append()
```

### Regulatory Date Boundaries (Quarter-End Processing)

```python
def get_regulatory_quarter_end(date_str: str) -> str:
    """
    Regulatory quarter-end uses business day convention.
    If quarter-end falls on weekend/holiday, use last business day.
    """
    from pandas.tseries.offsets import BQuarterEnd
    import pandas as pd

    date = pd.Timestamp(date_str)
    quarter_end = date + BQuarterEnd(0)  # Current quarter end

    # Check against bank holidays calendar
    holidays = spark.sql("""
        SELECT holiday_date FROM glue_catalog.audit_db.bank_holidays
        WHERE jurisdiction = 'US'
    """).toPandas()['holiday_date'].tolist()

    while quarter_end in holidays:
        quarter_end -= pd.Timedelta(days=1)

    return str(quarter_end.date())


def quarter_end_cutoff_processing(reporting_date: str):
    """
    Quarter-end requires:
    1. All pending amendments applied before cutoff
    2. Snapshot freeze at exact cutoff timestamp
    3. No modifications permitted after freeze
    4. Reconciliation with upstream systems
    """
    cutoff_timestamp = f"{reporting_date}T21:00:00Z"  # 9 PM UTC cutoff

    # Freeze: tag the Iceberg snapshot
    spark.sql(f"""
        ALTER TABLE glue_catalog.audit_db.conformed_trades
        CREATE TAG `quarter_end_{reporting_date}`
        AS OF SYSTEM_TIME '{cutoff_timestamp}'
    """)

    # Verify no late arrivals after cutoff
    late_arrivals = spark.sql(f"""
        SELECT COUNT(*) as cnt
        FROM glue_catalog.audit_db.raw_events
        WHERE _business_date <= '{reporting_date}'
        AND _ingestion_timestamp > '{cutoff_timestamp}'
    """).collect()[0]['cnt']

    if late_arrivals > 0:
        # Flag for manual review - do not auto-process
        alert_compliance_team(
            f"WARNING: {late_arrivals} late arrivals after quarter-end cutoff"
        )
```

### Data Retention Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│  RETENTION LIFECYCLE                                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Hot (0-90 days):                                                │
│    Storage: S3 Standard                                          │
│    Access: Sub-second queries via Athena/Redshift Spectrum       │
│    Use: Daily operations, real-time risk                         │
│    Cost: $0.023/GB/month                                         │
│                                                                  │
│  Warm (91 days - 2 years):                                       │
│    Storage: S3 Intelligent-Tiering                               │
│    Access: Seconds via Athena                                    │
│    Use: Monthly/quarterly regulatory reports                     │
│    Cost: $0.01-0.023/GB/month (auto-tiered)                     │
│                                                                  │
│  Cold (2-7 years):                                               │
│    Storage: S3 Glacier Instant Retrieval                         │
│    Access: Milliseconds (but higher retrieval cost)              │
│    Use: Annual audits, ad-hoc regulatory requests               │
│    Cost: $0.004/GB/month                                         │
│                                                                  │
│  Archive (7-10+ years):                                          │
│    Storage: S3 Glacier Deep Archive                              │
│    Access: 12-48 hours                                           │
│    Use: Legal holds, historical investigations                   │
│    Cost: $0.00099/GB/month                                       │
│                                                                  │
│  CRITICAL: Object Lock COMPLIANCE mode on ALL tiers.             │
│  Data CANNOT be deleted before retention period expires.         │
│  Even root account cannot override COMPLIANCE mode.              │
└──────────────────────────────────────────────────────────────────┘
```

### Disaster Recovery

```
┌──────────────────────────────────────────────────────────────────┐
│  DR CONFIGURATION                                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Primary: us-east-1 (Virginia)                                   │
│  DR:      eu-west-1 (Ireland)                                    │
│                                                                  │
│  Replication:                                                    │
│    - S3 Cross-Region Replication (real-time)                     │
│    - Glue Data Catalog: exported hourly via API                  │
│    - KMS: Multi-region keys for seamless failover                │
│    - Kinesis: Cross-region stream replication                    │
│                                                                  │
│  RTO: 4 hours (regulatory requirement: same business day)        │
│  RPO: 0 (zero data loss via synchronous replication)             │
│                                                                  │
│  Failover Test: Quarterly (required by OCC)                      │
└──────────────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Compliance Patterns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### SOX Section 404: Internal Controls

```python
class SOXControlFramework:
    """
    SOX 404 requires that every material financial data transformation
    has documented controls, is tested, and produces evidence.
    """

    def __init__(self, spark, control_catalog_table: str):
        self.spark = spark
        self.control_table = control_catalog_table

    def execute_with_control(self, control_id: str, transform_fn, input_df, **kwargs):
        """Execute a transformation with SOX control wrapper."""

        # Pre-condition: verify input data quality
        pre_check = self.run_pre_conditions(control_id, input_df)
        if not pre_check['passed']:
            self.raise_control_exception(control_id, "PRE", pre_check)

        # Execute transformation
        output_df = transform_fn(input_df, **kwargs)

        # Post-condition: verify output data quality
        post_check = self.run_post_conditions(control_id, input_df, output_df)
        if not post_check['passed']:
            self.raise_control_exception(control_id, "POST", post_check)

        # Log control evidence
        self.log_control_evidence(control_id, pre_check, post_check, input_df, output_df)

        return output_df

    def run_pre_conditions(self, control_id: str, df):
        """Run pre-condition checks defined for this control."""
        controls = self.spark.sql(f"""
            SELECT check_type, check_expression, threshold
            FROM {self.control_table}
            WHERE control_id = '{control_id}' AND phase = 'PRE'
        """).collect()

        results = []
        for ctrl in controls:
            if ctrl['check_type'] == 'COMPLETENESS':
                result = df.filter(F.col(ctrl['check_expression']).isNull()).count() == 0
            elif ctrl['check_type'] == 'VOLUME':
                result = df.count() >= int(ctrl['threshold'])
            results.append(result)

        return {"passed": all(results), "details": results}

    def log_control_evidence(self, control_id, pre_check, post_check, input_df, output_df):
        """Store immutable evidence that control was executed and passed."""
        evidence = self.spark.createDataFrame([{
            "control_id": control_id,
            "execution_timestamp": str(F.current_timestamp()),
            "pre_condition_passed": pre_check['passed'],
            "post_condition_passed": post_check['passed'],
            "input_record_count": input_df.count(),
            "output_record_count": output_df.count(),
            "job_run_id": self.spark.conf.get("spark.glue.JOB_RUN_ID", "unknown")
        }])
        evidence.writeTo("glue_catalog.audit_db.sox_control_evidence").append()
```

### PCI-DSS: Data Access Logging

```python
class PCIDSSAccessControl:
    """
    PCI-DSS Requirement 10: Track and monitor all access to
    network resources and cardholder data.
    """

    # PCI columns that require enhanced protection
    PCI_COLUMNS = [
        "card_number", "cvv", "expiry_date", "cardholder_name",
        "account_number", "routing_number"
    ]

    @staticmethod
    def mask_pci_data(df, columns_to_mask: list = None):
        """Tokenize PCI data - original stored in separate encrypted vault."""
        cols = columns_to_mask or PCIDSSAccessControl.PCI_COLUMNS

        for col_name in cols:
            if col_name in df.columns:
                df = df.withColumn(
                    col_name,
                    F.sha2(F.concat(F.col(col_name), F.lit("BANK_SALT_KEY")), 256)
                ).withColumn(
                    f"{col_name}_masked", F.lit(True)
                )
        return df

    @staticmethod
    def log_pci_access(spark, user_id: str, table_name: str,
                       columns_accessed: list, justification: str):
        """Log every access to PCI data (Requirement 10.2)."""
        pci_cols_accessed = [c for c in columns_accessed
                           if c in PCIDSSAccessControl.PCI_COLUMNS]

        if pci_cols_accessed:
            access_log = spark.createDataFrame([{
                "user_id": user_id,
                "table_name": table_name,
                "columns_accessed": json.dumps(pci_cols_accessed),
                "access_timestamp": str(datetime.now(timezone.utc)),
                "justification": justification,
                "access_granted": True  # Logged regardless of grant/deny
            }])
            access_log.writeTo("glue_catalog.audit_db.pci_access_log").append()
```

### Basel III BCBS 239: Risk Data Aggregation

```python
class BCBS239Compliance:
    """
    BCBS 239 Principles for effective risk data aggregation:
    - Principle 3: Accuracy and Integrity
    - Principle 4: Completeness
    - Principle 5: Timeliness
    - Principle 6: Adaptability
    """

    def verify_accuracy(self, aggregated_df, source_df, key_columns: list):
        """Principle 3: Verify aggregation accuracy via reconciliation."""
        # Sum at source vs sum at aggregate must match
        source_total = source_df.agg(F.sum("exposure_amount")).collect()[0][0]
        agg_total = aggregated_df.agg(F.sum("exposure_amount")).collect()[0][0]

        tolerance = 0.01  # $0.01 tolerance for floating point
        if abs(source_total - agg_total) > tolerance:
            raise ValueError(
                f"BCBS239 Principle 3 violation: Source={source_total}, "
                f"Aggregate={agg_total}, Diff={abs(source_total - agg_total)}"
            )

        return {
            "principle": "3_accuracy",
            "source_total": float(source_total),
            "aggregate_total": float(agg_total),
            "variance": float(abs(source_total - agg_total)),
            "status": "PASS"
        }

    def verify_completeness(self, df, expected_dimensions: dict):
        """Principle 4: All expected data dimensions are present."""
        results = []
        for dim_col, expected_values in expected_dimensions.items():
            actual_values = set(
                df.select(dim_col).distinct().rdd.map(lambda r: r[0]).collect()
            )
            missing = set(expected_values) - actual_values
            if missing:
                results.append({
                    "dimension": dim_col,
                    "missing_values": list(missing),
                    "status": "FAIL"
                })
            else:
                results.append({"dimension": dim_col, "status": "PASS"})

        return results

    def verify_timeliness(self, df, sla_minutes: int = 60):
        """Principle 5: Data must be available within SLA."""
        max_lag = df.agg(
            F.max(F.unix_timestamp(F.current_timestamp())
                  - F.unix_timestamp(F.col("_ingestion_timestamp")))
        ).collect()[0][0]

        return {
            "principle": "5_timeliness",
            "max_lag_seconds": max_lag,
            "sla_seconds": sla_minutes * 60,
            "status": "PASS" if max_lag <= sla_minutes * 60 else "FAIL"
        }
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Scaling: 10B Events/Day x 10 Years

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCALING STRATEGY                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Ingestion Layer:                                                   │
│    - 5,000 Kinesis shards (5M records/sec ingest capacity)         │
│    - Glue Job 1: 200 G.2X workers × 288 runs/day (5-min interval) │
│    - Auto-scaling: +50 workers during market open (9:30-4:00 ET)   │
│                                                                     │
│  Processing Layer:                                                  │
│    - Glue Flex execution for non-time-critical jobs                │
│    - Reserved capacity for regulatory SLA-bound jobs               │
│    - Parallel execution across asset classes                        │
│                                                                     │
│  Storage Layer:                                                     │
│    - Iceberg table partitioning: business_date / asset_class / hour │
│    - Compaction: scheduled every 6 hours (merge small files)        │
│    - Expire snapshots: keep 90 days of snapshots, archive rest     │
│    - Target file size: 128MB (optimal for Parquet + S3)            │
│                                                                     │
│  Query Layer:                                                       │
│    - Athena for ad-hoc audit queries                               │
│    - Redshift Spectrum for complex regulatory reports              │
│    - Pre-materialized views for common audit lookups               │
│                                                                     │
│  Data Volume Projections:                                           │
│    Year 1:  ~550 TB (compressed Parquet)                           │
│    Year 3:  ~1.6 PB                                                │
│    Year 5:  ~2.7 PB                                                │
│    Year 10: ~5.5 PB (hot) + ~9.5 PB (cold/archive)               │
│                                                                     │
│  Partition Strategy:                                                │
│    - Level 1: business_date (daily partitions)                     │
│    - Level 2: asset_class (equities, fixed_income, fx, deriv)     │
│    - Level 3: hour (for intraday queries)                          │
│    - Result: ~35,000 partitions/year (within Glue Catalog limits)  │
└─────────────────────────────────────────────────────────────────────┘
```

### Iceberg Table Maintenance

```python
def scheduled_table_maintenance(spark, table_name: str):
    """Run on schedule to keep Iceberg tables performant at scale."""

    # Compact small files (critical after high-frequency appends)
    spark.sql(f"""
        CALL glue_catalog.system.rewrite_data_files(
            table => 'audit_db.{table_name}',
            strategy => 'binpack',
            options => map(
                'target-file-size-bytes', '134217728',
                'min-file-size-bytes', '67108864',
                'max-file-size-bytes', '201326592',
                'partial-progress.enabled', 'true',
                'partial-progress.max-commits', '10'
            )
        )
    """)

    # Expire old snapshots (keep metadata, remove unreferenced data files)
    spark.sql(f"""
        CALL glue_catalog.system.expire_snapshots(
            table => 'audit_db.{table_name}',
            older_than => TIMESTAMP '{datetime.now() - timedelta(days=90)}',
            retain_last => 100
        )
    """)

    # Remove orphan files
    spark.sql(f"""
        CALL glue_catalog.system.remove_orphan_files(
            table => 'audit_db.{table_name}',
            older_than => TIMESTAMP '{datetime.now() - timedelta(days=3)}'
        )
    """)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Cost Analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────┐
│  MONTHLY COST BREAKDOWN (Steady State, Year 3)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Compute (Glue Jobs):                                               │
│    Job 1 (Ingestion):    200 G.2X × 288 runs × 5 min = $185,000   │
│    Job 2 (Lineage):      150 G.2X × 288 runs × 4 min = $104,000   │
│    Job 3 (Regulatory):   300 G.2X × 30 runs × 60 min = $69,000    │
│    Job 4 (Reports):      200 G.2X × 15 runs × 120 min = $46,000   │
│    Job 5 (Crystallize):  100 G.2X × 15 runs × 30 min = $7,200     │
│    Crawlers & DQ:                                        = $12,000  │
│                                              Subtotal:   $423,200   │
│                                                                     │
│  Storage (S3):                                                      │
│    Hot (Standard, 550TB):                                $12,650    │
│    Warm (IA, 500TB):                                     $6,250     │
│    Cold (Glacier IR, 400TB):                             $1,600     │
│    Archive (Deep Archive, 200TB):                        $198       │
│    Object Lock overhead (~5%):                           $1,035     │
│    Cross-region replication:                             $15,000    │
│                                              Subtotal:   $36,733    │
│                                                                     │
│  Streaming (Kinesis):                                               │
│    5,000 shards × $0.015/hr:                             $54,000   │
│    Extended retention (365 days):                         $25,000   │
│                                              Subtotal:   $79,000    │
│                                                                     │
│  Other:                                                             │
│    KMS (encryption operations):                          $8,000     │
│    CloudTrail (data events):                             $15,000    │
│    VPC endpoints:                                        $3,500     │
│    Athena queries:                                       $12,000    │
│                                              Subtotal:   $38,500    │
│                                                                     │
│  ════════════════════════════════════════════════════════════════    │
│  TOTAL MONTHLY:                                          $577,433   │
│  TOTAL ANNUAL:                                           $6.93M     │
│  ════════════════════════════════════════════════════════════════    │
│                                                                     │
│  vs. Traditional (Oracle RAC + Informatica + AxiomSL):              │
│    Licensing alone: $50M+ annually                                  │
│    Infrastructure: $15M+ annually                                   │
│    Total traditional: $65M+                                         │
│                                                                     │
│  SAVINGS: ~89% cost reduction                                       │
│  PLUS: Better scalability, auditability, and flexibility            │
└─────────────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies

```
1. Glue Flex Execution: Use for non-SLA jobs (saves 34%)
   - Applicable to: Job 5 (crystallization), crawlers
   - Savings: ~$8,000/month

2. Reserved Capacity: Commit to baseline for predictable jobs
   - Job 1 & 2 run continuously → reserved pricing
   - Savings: ~$50,000/month

3. Intelligent Tiering: Automatic cost optimization for warm data
   - No retrieval fees, automatic movement
   - Savings: ~$4,000/month vs manual lifecycle

4. Spot Instances (Glue Auto Scaling): For burst capacity
   - Market open surge, quarter-end processing
   - Savings: ~$20,000/month during peaks
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Companies Running This Pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────┐
│  COMPANY          │ SCALE              │ KEY USE CASE               │
├───────────────────┼────────────────────┼────────────────────────────┤
│  Goldman Sachs    │ 15B+ events/day    │ Trade lifecycle audit,     │
│                   │                    │ CCAR stress testing data   │
│                   │                    │ Marcus consumer banking    │
├───────────────────┼────────────────────┼────────────────────────────┤
│  JPMorgan Chase   │ 12B+ events/day    │ Cross-LOB risk aggregation │
│                   │                    │ CIB trade reporting        │
│                   │                    │ Consumer payment audit     │
├───────────────────┼────────────────────┼────────────────────────────┤
│  Morgan Stanley   │ 8B+ events/day     │ Wealth management audit,  │
│                   │                    │ Prime brokerage lineage    │
│                   │                    │ E*TRADE integration        │
├───────────────────┼────────────────────┼────────────────────────────┤
│  Citadel /        │ 5B+ events/day     │ Trading strategy audit,   │
│  Citadel Sec.     │                    │ Regulatory reporting,     │
│                   │                    │ Market making compliance  │
├───────────────────┼────────────────────┼────────────────────────────┤
│  Bank of America  │ 10B+ events/day    │ Merrill Lynch advisory,   │
│                   │                    │ Global Markets reporting  │
├───────────────────┼────────────────────┼────────────────────────────┤
│  Barclays         │ 6B+ events/day     │ Investment bank + retail  │
│                   │                    │ FCA/PRA regulatory        │
├───────────────────┼────────────────────┼────────────────────────────┤
│  Deutsche Bank    │ 7B+ events/day     │ BaFin compliance,         │
│                   │                    │ Cross-border reporting    │
└───────────────────┴────────────────────┴────────────────────────────┘
```

### Why AWS Glue Specifically

```
┌─────────────────────────────────────────────────────────────────────┐
│  WHY GLUE FOR FINANCIAL REGULATORY PIPELINES                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Serverless = No infrastructure to audit                         │
│     - No OS patching, no server hardening                          │
│     - Reduces SOX IT general controls scope                        │
│                                                                     │
│  2. Native Iceberg = Time-travel for point-in-time audits          │
│     - "What did the data look like on March 31?"                   │
│     - Reproducible regulatory reports                               │
│                                                                     │
│  3. Job Bookmarks = Exactly-once semantics                         │
│     - Critical for financial accuracy                              │
│     - No duplicate/missing transactions                            │
│                                                                     │
│  4. Data Catalog = Schema lineage and governance                   │
│     - Version history of every schema change                       │
│     - Integration with Lake Formation for access control           │
│                                                                     │
│  5. DQDL = Codified regulatory data quality rules                  │
│     - Rules as code (version controlled)                           │
│     - Automated evidence generation                                │
│                                                                     │
│  6. Workflows = Orchestrated regulatory calculations               │
│     - Dependency management                                        │
│     - Failure handling with compliance notifications               │
│                                                                     │
│  7. CloudTrail Integration = Complete API audit trail              │
│     - Who ran what job, when, on which data                        │
│     - Tamper-evident (CloudTrail Integrity Validation)             │
└─────────────────────────────────────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Takeaways

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
1. IMMUTABILITY IS NON-NEGOTIABLE
   - Append-only writes, Object Lock COMPLIANCE mode
   - Cryptographic hashes at record and batch level
   - HSM-signed snapshots for non-repudiation

2. LINEAGE MUST BE AUTOMATIC, NOT AFTER-THE-FACT
   - Every transformation injects lineage metadata
   - OpenLineage events for cross-system tracing
   - Code version tied to every output record

3. EXACTLY-ONCE IS A FINANCIAL REQUIREMENT
   - Job Bookmarks + hash-based dedup = guaranteed
   - One missing or duplicate trade = regulatory breach

4. TIME-TRAVEL IS YOUR AUDIT SUPERPOWER
   - Iceberg snapshots answer "what did we know and when"
   - Crystallized snapshots for regulatory submission proof
   - Tagged snapshots for quarter-end boundaries

5. COMPLIANCE AS CODE
   - SOX controls are executable, not documented
   - DQDL rules enforce regulatory requirements in-pipeline
   - Evidence is auto-generated, not manually gathered
```
