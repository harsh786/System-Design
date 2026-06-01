# Schema & Data Type Issues (#51-60)

> Schema issues are **insidious** — they don't crash jobs immediately but corrupt data silently.
> A type mismatch that goes undetected for 3 months can invalidate millions of downstream reports.

---

## Issue #51: Schema Mismatch Between Glue Catalog and Actual Data

### Severity: P2 | Frequency: Weekly (especially after upstream deploys)

### Symptoms
```
# Columns read as null that should have data
# Numeric columns truncated (decimal → int)
# Job succeeds but output quality degraded
# Data quality checks fail downstream

# Glue Catalog says: column "amount" type = double
# Actual Parquet file: column "amount" type = string ("19.99")
# Result: amount read as NULL (type incompatible, silent fail)
```

### Root Cause
```
Catalog schema drifts from actual file schema when:
1. Upstream producer changes schema without notification
2. Crawler hasn't run after schema change
3. Multiple producers write different schemas to same table
4. Manual catalog edits don't match reality
5. Partition columns have different types across partitions
```

### Fix
```python
# Fix 1: Use DynamicFrame (handles schema inconsistency gracefully)
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db", table_name="events"
)
# DynamicFrame tracks per-record schema - no silent nulls

# Resolve type conflicts explicitly:
dyf = dyf.resolveChoice(
    specs=[
        ("amount", "cast:double"),
        ("user_id", "cast:string"),
        ("timestamp", "cast:timestamp")
    ]
)

# Fix 2: Schema validation at job start
from awsglue.context import GlueContext

def validate_schema(table_name, expected_columns):
    """Fail fast if schema doesn't match expectations."""
    table = glueContext.get_table("db", table_name)
    actual_columns = {col['Name']: col['Type'] for col in table['StorageDescriptor']['Columns']}
    
    for col_name, expected_type in expected_columns.items():
        if col_name not in actual_columns:
            raise Exception(f"Missing column: {col_name}")
        if actual_columns[col_name] != expected_type:
            logger.warning(
                f"Type mismatch: {col_name} expected={expected_type} actual={actual_columns[col_name]}"
            )

expected = {"amount": "double", "user_id": "string", "event_time": "timestamp"}
validate_schema("events", expected)

# Fix 3: Re-crawl before processing
import boto3
glue = boto3.client('glue')
glue.start_crawler(Name='events-crawler')
# Wait for crawler to complete before job processes data
```

---

## Issue #52: Parquet Schema Evolution Breaking Reads

### Severity: P2 | Frequency: On every schema change

### Symptoms
```
# Error: Parquet column cannot be converted
# OR: Column 'new_col' not found in schema (older files don't have it)
# OR: Type mismatch reading historical partitions

# Historical partition (Jan): {user_id: INT, name: STRING}
# New partition (Feb):        {user_id: BIGINT, name: STRING, email: STRING}
# Reading both: fails or returns nulls for email in Jan data
```

### Root Cause
```
Parquet stores schema per-file. When schema evolves:
- Added columns: missing in old files (read as null - OK)
- Removed columns: present in old files (read fails if not in schema)
- Type changes: int→bigint (may work), string→int (fails)
- Column rename: appears as remove + add (data loss!)

Spark mergeSchema=false (default) uses FIRST file's schema → breaks on evolved files
```

### Fix
```python
# Fix 1: Enable schema merging
df = spark.read \
    .option("mergeSchema", "true") \
    .parquet("s3://data/events/")
# Spark reads all file schemas, creates union schema
# Missing columns in old files → null

# Fix 2: Use Glue DynamicFrame (handles per-file schema automatically)
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db", table_name="events"
)
# DynamicFrame maintains per-record type info (no schema merge needed)

# Fix 3: Use Iceberg for safe schema evolution
# Iceberg supports:
# - Add columns (reads null for old data)
# - Drop columns (physically removed on compaction)
# - Rename columns (ID-based, not name-based)
# - Type promotion (int→bigint, float→double)
spark.sql("ALTER TABLE db.events ADD COLUMNS (email STRING)")
# All existing data seamlessly returns null for email

# Fix 4: Handle type evolution explicitly
from pyspark.sql.types import LongType, IntegerType

# Cast columns that may have evolved
df = df.withColumn("user_id", F.col("user_id").cast(LongType()))
# Handles both INT and BIGINT source types
```

---

## Issue #53: DynamicFrame resolveChoice Explosion (Too Many Types Per Column)

### Severity: P2 | Frequency: Common with JSON sources

### Symptoms
```
# DynamicFrame schema shows:
# "price": choice {int, long, double, string, null}
# Each record may have different type for same field

# resolveChoice with "make_struct" creates deeply nested output
# resolveChoice with "cast:double" fails for non-numeric strings
```

### Root Cause
```
Semi-structured data (JSON) has no enforced schema:
- {"price": 10}       → int
- {"price": 10.99}    → double
- {"price": "10.99"}  → string
- {"price": null}     → null
- {"price": "N/A"}    → string (can't cast to numeric!)

DynamicFrame tracks ALL observed types → resolveChoice needed.
```

### Fix
```python
# Fix 1: Explicit casting with error handling
dyf = glueContext.create_dynamic_frame.from_catalog(database="db", table_name="raw")

# Cast to target type, invalid values become null
dyf_resolved = dyf.resolveChoice(specs=[
    ("price", "cast:double"),  # "N/A" → null, "10.99" → 10.99, 10 → 10.0
    ("quantity", "cast:int"),
    ("timestamp", "cast:timestamp")
])

# Check for resolution failures (values that became null)
null_count = dyf_resolved.toDF().filter(F.col("price").isNull()).count()
if null_count > threshold:
    alert(f"Schema resolution: {null_count} null prices (possible data issue)")

# Fix 2: Use make_struct for complex cases then flatten
dyf_struct = dyf.resolveChoice(specs=[("price", "make_struct")])
# Now price is a struct with all type variants
# Flatten with custom logic:
df = dyf_struct.toDF()
df = df.withColumn("price_clean",
    F.coalesce(
        F.col("price.double"),
        F.col("price.int").cast("double"),
        F.col("price.string").cast("double"),
        F.lit(0.0)  # Default for truly invalid values
    )
)

# Fix 3: Pre-process JSON to enforce types before Glue reads
# Use Lambda trigger on S3 to validate/coerce JSON schema on landing
# Write validated JSON to "clean" prefix
# Glue reads from clean prefix (consistent types)

# Fix 4: Use Spark's schema-on-read with explicit schema
from pyspark.sql.types import StructType, StructField, DoubleType, StringType

explicit_schema = StructType([
    StructField("user_id", StringType(), True),
    StructField("price", DoubleType(), True),  # Forces type
    StructField("quantity", IntegerType(), True)
])

df = spark.read.schema(explicit_schema).json("s3://data/raw/")
# Non-conforming values → null (with badRecordsPath option for debugging)
```

---

## Issue #54: Timestamp Timezone Handling Inconsistencies

### Severity: P2 | Frequency: Constant (every system has timezone bugs)

### Symptoms
```
# Same event shows different times in different queries:
# Source (MySQL):   2024-01-15 10:00:00 (stored as UTC)
# Glue read:       2024-01-15 05:00:00 (interpreted as local time, converted to UTC)
# Athena query:    2024-01-15 10:00:00 (shows UTC)
# Redshift:        2024-01-15 02:00:00 (shows PST)

# Result: duplicate events, missed events, wrong aggregation windows
```

### Root Cause
```
The unholy trinity of timestamp confusion:
1. JDBC reads: Java interprets timestamps in JVM timezone (often UTC or server-local)
2. Spark SESSION_LOCAL_TIMEZONE affects timestamp interpretation
3. Parquet stores as INT96 (no timezone) or TIMESTAMP_MILLIS (UTC assumed)
4. Iceberg: stores as UTC microseconds (correct but source may be wrong)
5. Glue Catalog: timestamp type has no timezone annotation
```

### Fix
```python
# RULE: ALL timestamps internally stored as UTC. Convert at display layer only.

# Fix 1: Force UTC in Spark session
spark.conf.set("spark.sql.session.timeZone", "UTC")

# Fix 2: JDBC timestamp handling
jdbc_options = {
    "url": "jdbc:mysql://host:3306/db?serverTimezone=UTC&useLegacyDatetimeCode=false",
    "sessionInitStatement": "SET time_zone = '+00:00'"  # Force UTC on connection
}

# Fix 3: Explicit timezone conversion in code
from pyspark.sql.functions import from_utc_timestamp, to_utc_timestamp

# Convert local time to UTC (when source stores in local time)
df = df.withColumn("event_time_utc", to_utc_timestamp("event_time", "America/New_York"))

# Convert UTC to local for display (at output layer only)
df = df.withColumn("event_time_local", from_utc_timestamp("event_time_utc", "America/New_York"))

# Fix 4: Parquet timestamp settings
spark.conf.set("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")  # Not INT96
spark.conf.set("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "CORRECTED")
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")

# Fix 5: Iceberg timestamp handling
spark.conf.set("spark.sql.iceberg.handle-timestamp-without-timezone", "true")
# Iceberg STRICTLY requires timezone-aware timestamps
# This setting allows timestampNTZ (no timezone) columns
```

---

## Issue #55: Decimal Precision Loss During Type Conversion

### Severity: P2 | Frequency: Common in financial data

### Symptoms
```
# Input: amount = 19999.99 (decimal(10,2))
# After processing: amount = 20000.0 (double)
# $0.01 lost per transaction × 100M transactions = $1M discrepancy!

# OR: amount = 123456789.12 → 123456789.0 (double has only 15-17 significant digits)
```

### Root Cause
```
Implicit type promotion in Spark:
- decimal(10,2) + decimal(10,2) = decimal(11,2) → may exceed max precision
- decimal joined with double → everything becomes double (lossy!)
- Aggregation of decimal → intermediate as double → precision loss

Double (float64) has only ~15 significant digits:
123456789.12 stored as double → 123456789.11999999... (rounding error)
```

### Fix
```python
# RULE: NEVER use double/float for financial data. ALWAYS decimal.

# Fix 1: Force decimal type throughout pipeline
from pyspark.sql.types import DecimalType

df = df.withColumn("amount", F.col("amount").cast(DecimalType(18, 2)))
# 18 digits total, 2 after decimal point

# Fix 2: Prevent implicit promotion to double
# BAD: Mixing decimal and double
df.withColumn("total", F.col("amount") * F.lit(1.1))  # 1.1 is double!
# GOOD: Keep as decimal
df.withColumn("total", F.col("amount") * F.lit(Decimal("1.1")).cast(DecimalType(3,1)))

# Fix 3: Use appropriate precision for aggregations
# SUM of 1B transactions × max $99,999.99:
# Worst case sum: 1,000,000,000 × 99,999.99 = ~10^14
# Need DecimalType(38, 2) for safety (38 = max in Spark)
agg_df = df.groupBy("merchant").agg(
    F.sum(F.col("amount").cast(DecimalType(38, 2))).alias("total_amount")
)

# Fix 4: Validate precision after computation
df_check = result_df.filter(
    F.col("amount") != F.col("amount").cast(DecimalType(18, 2))
)
if df_check.count() > 0:
    raise Exception("Precision loss detected in financial data!")

# Fix 5: Parquet stores decimal natively (no loss)
# Ensure output is written as decimal, not converted to double:
df.write.parquet("s3://output/")  # Schema preserved including decimal type
```

---

## Issue #56: Nested JSON Flattening Failures (Deeply Nested Arrays)

### Severity: P3 | Frequency: Common with event data

### Symptoms
```
# Input: Complex nested JSON (5+ levels deep)
# Explode arrays → Cartesian explosion (1 record → 1000 records)
# Null nested fields → NullPointerException
# Schema inference creates unreadable struct<array<struct<...>>>
```

### Root Cause
```json
{
  "order": {
    "items": [
      {
        "product": { "categories": ["A", "B"] },
        "variants": [
          { "size": "L", "colors": ["red", "blue"] }
        ]
      }
    ]
  }
}
// Exploding items × variants × colors:
// 1 order → 2 items × 2 variants × 2 colors = 8 rows
// At scale: 1M orders → 8M+ rows (unexpected explosion)
```

### Fix
```python
# Fix 1: Selective explode (don't explode everything)
# Only explode the level you need:
df = spark.read.json("s3://data/orders/")
df_items = df.select(
    "order.order_id",
    F.explode("order.items").alias("item")
)
# Don't also explode variants unless needed!

# Fix 2: Extract specific fields without exploding
df_flat = df.select(
    F.col("order.order_id").alias("order_id"),
    F.size("order.items").alias("num_items"),
    F.col("order.items")[0]["product"]["categories"][0].alias("primary_category"),
    F.aggregate("order.items", F.lit(0.0), 
        lambda acc, x: acc + x["price"]).alias("total_price")
)
# No explosion - one output row per input row

# Fix 3: Use DynamicFrame Relationalize for complex nesting
dyf = glueContext.create_dynamic_frame.from_catalog(database="db", table_name="raw")
dfc = dyf.relationalize("root", "s3://temp/relationalize/")
# Creates separate tables for each nested level
# root: main table
# root_order.items: items table with foreign key back to root
# root_order.items.variants: variants table with FK to items

# Fix 4: Guard against explosion
df_items = df.select(F.explode("items").alias("item"))
item_count = df_items.count()
input_count = df.count()
if item_count > input_count * 100:  # More than 100x expansion
    raise Exception(f"Explosion detected: {input_count} → {item_count} rows")
```

---

## Issue #57: Partition Column Type Mismatch Across Partitions

### Severity: P2 | Frequency: Common with heterogeneous producers

### Symptoms
```
# Table has partitions: date=2024-01-15 (string), date=20240116 (string, different format)
# OR: id=123 (integer partition), id=abc (string partition in same table)
# Glue Crawler marks table as "inconsistent"
# Reads fail or return unexpected nulls
```

### Fix
```python
# Fix 1: Standardize partition values in landing zone
# Use Lambda on S3 PUT to rename paths to canonical format:
# s3://bucket/data/date=20240115/ → s3://bucket/data/date=2024-01-15/

# Fix 2: Use Glue Crawler custom classifier
# Define classifier that enforces partition type:
{
    "Name": "date-partition-classifier",
    "GrokPattern": "%{YEAR:year}-%{MONTHNUM:month}-%{MONTHDAY:day}",
    "CustomPatterns": ""
}

# Fix 3: Cast partition columns after read
df = spark.read.table("db.events")
df = df.withColumn("date", 
    F.when(F.length("date") == 8,
        F.to_date("date", "yyyyMMdd"))
    .otherwise(F.to_date("date", "yyyy-MM-dd"))
)

# Fix 4: Use Iceberg (partition spec is table-level, not file-level)
# All data written with consistent partition transform
spark.sql("""
    CREATE TABLE db.events (
        event_id STRING, event_time TIMESTAMP, data STRING
    ) USING iceberg
    PARTITIONED BY (days(event_time))
""")
# Partition type always consistent (derived from column)
```

---

## Issue #58: Binary/Complex Types Not Supported in Target

### Severity: P3 | Frequency: When migrating between systems

### Symptoms
```
# Error: "Unsupported type: binary" when writing to Redshift
# OR: "Cannot convert struct<...> to Redshift type"
# OR: Athena can't query map<string,string> columns

# Source has complex types that target system can't handle:
# - binary (images, serialized objects)
# - map<K,V> (key-value pairs)
# - array<struct<...>> (nested arrays)
# - struct<struct<...>> (deeply nested objects)
```

### Fix
```python
# Fix 1: Serialize complex types to string for compatibility
df = df.withColumn("metadata_json", F.to_json("metadata_map"))
df = df.drop("metadata_map")  # Drop original map column

# Fix 2: Flatten structs to scalar columns
df = df.select(
    "*",
    F.col("address.street").alias("address_street"),
    F.col("address.city").alias("address_city"),
    F.col("address.zip").alias("address_zip")
).drop("address")

# Fix 3: Convert arrays to delimited strings
df = df.withColumn("tags_csv", F.array_join("tags", ","))
df = df.drop("tags")

# Fix 4: Base64 encode binary for text-based targets
import base64
from pyspark.sql.functions import udf

@udf(StringType())
def binary_to_base64(data):
    return base64.b64encode(data).decode('utf-8') if data else None

df = df.withColumn("image_b64", binary_to_base64("image_binary"))
```

---

## Issue #59: Glue Crawler Incorrectly Infers Schema

### Severity: P2 | Frequency: On every crawler run with diverse data

### Symptoms
```
# Crawler infers:
# - "id" as bigint (but some values are UUIDs → should be string)
# - "timestamp" as string (ISO format not recognized)
# - "price" as bigint (first file has "100", not "100.50")
# - Two separate tables created for same logical table (schema too different)
```

### Fix
```python
# Fix 1: Use custom classifiers with Grok patterns
# Create classifier that forces specific types:
glue.create_classifier(
    GrokClassifier={
        'Classification': 'custom_events',
        'Name': 'event-classifier',
        'GrokPattern': '%{UUID:id} %{TIMESTAMP_ISO8601:event_time} %{NUMBER:amount}'
    }
)

# Fix 2: Define table schema manually (skip crawler for known schemas)
glue.create_table(
    DatabaseName='db',
    TableInput={
        'Name': 'events',
        'StorageDescriptor': {
            'Columns': [
                {'Name': 'id', 'Type': 'string'},
                {'Name': 'event_time', 'Type': 'timestamp'},
                {'Name': 'amount', 'Type': 'decimal(18,2)'}
            ],
            'Location': 's3://bucket/events/',
            'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
            'SerdeInfo': {'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'}
        },
        'PartitionKeys': [{'Name': 'date', 'Type': 'string'}]
    }
)

# Fix 3: Configure crawler to use existing schema as template
# Crawler configuration:
# "SchemaChangePolicy": {
#     "UpdateBehavior": "LOG",      # Don't auto-update schema
#     "DeleteBehavior": "LOG"       # Don't auto-delete columns
# }
# Crawler logs schema drift but doesn't change table definition

# Fix 4: Use Schema Registry for producer enforcement
# Producers register schema BEFORE writing data
# Crawler validates against registered schema
```

---

## Issue #60: Character Encoding Issues (UTF-8/Latin-1 Mismatch)

### Severity: P3 | Frequency: Common with international data

### Symptoms
```
# Customer names showing as: "JosÃ© GarcÃ­a" instead of "José García"
# OR: UnicodeDecodeError when processing CSV files
# OR: Special characters lost/corrupted after processing
# OR: File read returns garbled text for non-ASCII content
```

### Fix
```python
# Fix 1: Specify encoding on read
df = spark.read \
    .option("encoding", "UTF-8") \
    .option("charset", "UTF-8") \
    .csv("s3://data/international/")

# For Latin-1 (ISO-8859-1) sources:
df = spark.read \
    .option("encoding", "ISO-8859-1") \
    .csv("s3://data/legacy_system/")
# Then convert to UTF-8 for storage

# Fix 2: Force UTF-8 on write (always)
df.write \
    .option("encoding", "UTF-8") \
    .csv("s3://output/")
# Parquet/ORC always use UTF-8 (no option needed)

# Fix 3: Detect and handle encoding in job
import chardet

def detect_encoding(file_path):
    """Detect file encoding by sampling."""
    import boto3
    s3 = boto3.client('s3')
    # Read first 10KB for detection
    obj = s3.get_object(Bucket=bucket, Key=key, Range='bytes=0-10240')
    raw = obj['Body'].read()
    result = chardet.detect(raw)
    return result['encoding']  # e.g., 'utf-8', 'iso-8859-1', 'windows-1252'

# Fix 4: Sanitize strings after read
from pyspark.sql.functions import regexp_replace

# Remove non-UTF8 characters that slipped through
df = df.withColumn("name",
    regexp_replace("name", "[^\x00-\x7F\xC0-\xFF]", "")
)

# Fix 5: Use DynamicFrame for automatic encoding handling
# Glue DynamicFrame handles encoding better than raw Spark for CSV
dyf = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    format="csv",
    connection_options={"paths": ["s3://data/"]},
    format_options={"withHeader": True, "encoding": "UTF-8"}
)
```

---

## Schema Issue Prevention Checklist

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCHEMA MANAGEMENT BEST PRACTICES                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Prevention:                                                         │
│  ✓ Register schemas BEFORE producing data (Schema Registry)         │
│  ✓ Use backward-compatible evolution only (add columns, not remove) │
│  ✓ Store schema version with data (Avro/Protobuf include schema)    │
│  ✓ Test schema changes against ALL downstream consumers             │
│  ✓ Use Iceberg for safe schema evolution                            │
│  ✓ Always use DecimalType for money (never double/float)            │
│  ✓ Always store timestamps in UTC                                    │
│  ✓ Always write in UTF-8 encoding                                    │
│                                                                      │
│  Detection:                                                          │
│  ✓ Glue Data Quality rules for type validation                      │
│  ✓ Compare schema hash before/after each job run                    │
│  ✓ Alert on crawler schema change detection                         │
│  ✓ Monitor null rates per column (spike = schema issue)             │
│                                                                      │
│  Recovery:                                                           │
│  ✓ Keep raw data immutable (can always reprocess)                   │
│  ✓ Schema version catalog (know which version wrote each partition) │
│  ✓ Backfill procedure for schema corrections                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
