# Category 8: Data Quality & Correctness Issues (Issues 71-80)

> Silent data quality issues are worse than job failures. A failed job is visible; incorrect data that reaches production dashboards erodes trust and causes real business damage.

---

## Issue #71: Silent Data Loss from Failed Tasks (Partial Write)

**Frequency**: Medium  
**Severity**: Critical - missing data, no error  
**Spark Component**: OutputCommitProtocol, TaskCommit

### Symptoms
```
# Job reports SUCCESS but output has fewer records than input
# No error in logs, all stages show "completed"
# Some tasks failed and retried, but data from failed attempt is lost
# Downstream reports show gaps in data
# Reconciliation: source count > sink count
```

### Root Cause
- Task fails after partial write, retry writes to different file
- Speculative execution: one copy succeeds, other's partial write remains
- OutputCommitProtocol race condition with S3
- Append mode: failed batch partially written, retry skips it
- Silently dropped records from corrupt source files (spark.sql.files.ignoreCorruptFiles)

### Solution
```python
# 1. ALWAYS validate record counts
input_count = df_input.count()
df_output = transform(df_input)
df_output.write.parquet("s3://output/")

# Validate
output_count = spark.read.parquet("s3://output/").count()
assert abs(input_count - output_count) < input_count * 0.001, \
    f"Record count mismatch: input={input_count}, output={output_count}"

# 2. Don't silently ignore corrupt files
spark.conf.set("spark.sql.files.ignoreCorruptFiles", "false")  # FAIL on corrupt
spark.conf.set("spark.sql.files.ignoreMissingFiles", "false")  # FAIL on missing

# 3. Use Iceberg/Delta for atomic writes
df.writeTo("catalog.db.table").append()
# Atomic: either ALL records are visible or NONE
# No partial writes possible

# 4. Track records through pipeline with checksums
df_with_checksum = df.withColumn("_record_hash", F.md5(F.concat_ws("|", *df.columns)))
# Compare hash distributions between stages

# 5. Disable speculation for write-heavy stages
spark.conf.set("spark.speculation", "false")

# 6. Implement reconciliation job
# Run daily: compare source counts with sink counts per partition
reconciliation = spark.sql("""
    SELECT s.date, s.source_count, t.target_count,
           s.source_count - t.target_count as diff
    FROM source_counts s JOIN target_counts t ON s.date = t.date
    WHERE ABS(s.source_count - t.target_count) > 0
""")
```

---

## Issue #72: Duplicate Records from Non-Idempotent Writes

**Frequency**: High  
**Severity**: High - financial impact  
**Spark Component**: DataFrameWriter, Retry Logic

### Symptoms
```
# Same record appears 2-3 times in output
# Happens after job retry or stage retry
# Revenue/count metrics inflated by duplicates
# Downstream dedup logic overloaded
```

### Root Cause
- Job failed after writing some data, retried, wrote same data again
- Append mode + retry = duplicates
- No deduplication key or unique constraint in data lake
- Streaming forEachBatch not idempotent
- Two instances of same job running simultaneously

### Solution
```python
# 1. Use MERGE for idempotent upserts (Iceberg/Delta)
df.createOrReplaceTempView("new_data")
spark.sql("""
    MERGE INTO target t
    USING new_data n
    ON t.event_id = n.event_id AND t.event_date = n.event_date
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
# Re-running with same data = no duplicates

# 2. Dynamic partition overwrite (idempotent)
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
df.write.mode("overwrite").partitionBy("date").parquet("s3://output/")
# Rewrites only affected partitions atomically

# 3. Add dedup at write time
df_deduped = df.dropDuplicates(["event_id"])
df_deduped.write.parquet("s3://output/")

# 4. For streaming: idempotent foreachBatch
def write_batch(batch_df, batch_id):
    # Use batch_id for idempotency
    batch_df.write.mode("overwrite") \
        .parquet(f"s3://output/batch_id={batch_id}/")
    # Same batch_id overwrites → no duplicates on retry

# 5. Application-level locking (prevent duplicate runs)
# Use DynamoDB/ZooKeeper lock:
# if not acquire_lock(pipeline_id, execution_date): skip
# process()
# release_lock()

# 6. Post-write deduplication check
result = spark.read.parquet("s3://output/")
dup_count = result.groupBy("event_id").count().filter("count > 1").count()
assert dup_count == 0, f"Found {dup_count} duplicate event_ids!"
```

---

## Issue #73: Type Coercion Causing Silent Data Corruption

**Frequency**: Medium  
**Severity**: Critical - wrong values, no error  
**Spark Component**: Cast, TypeCoercion (Catalyst Rule)

### Symptoms
```
# Column expected INT but source has BIGINT → silent overflow
# String "123.45" cast to INT → becomes 123 (truncated, no warning)
# Timestamp precision lost: microseconds → milliseconds
# Null values appearing where data should exist (failed cast → null)
```

### Root Cause
- Spark silently casts incompatible types (returns null on failure)
- Schema inference guesses wrong type (e.g., "123" as INT, later "123.45" fails)
- Parquet schema evolution: INT → BIGINT → doesn't auto-widen
- ANSI mode off by default (permits silent overflow and null casts)

### Solution
```python
# 1. Enable ANSI mode (fail on bad casts instead of returning null)
spark.conf.set("spark.sql.ansi.enabled", "true")
# Now: CAST('abc' AS INT) → throws error instead of returning null
# Now: INT overflow → throws error instead of wrapping

# 2. Use explicit schema (never rely on inference for production)
from pyspark.sql.types import StructType, StructField, StringType, LongType, DecimalType

schema = StructType([
    StructField("event_id", StringType(), nullable=False),
    StructField("amount", DecimalType(18, 2), nullable=False),  # Exact decimal!
    StructField("timestamp", LongType(), nullable=False),
])
df = spark.read.schema(schema).json("s3://input/")

# 3. Validate after cast
df_casted = df.withColumn("amount_int", F.col("amount").cast("int"))
# Check for unexpected nulls (failed casts):
null_count = df_casted.filter(F.col("amount_int").isNull() & F.col("amount").isNotNull()).count()
assert null_count == 0, f"{null_count} records had cast failures!"

# 4. Use DECIMAL for financial data (never FLOAT/DOUBLE)
# FLOAT: 0.1 + 0.2 = 0.30000000000000004
# DECIMAL(18,2): 0.1 + 0.2 = 0.30 (exact)
df = df.withColumn("revenue", F.col("revenue").cast("decimal(18,2)"))

# 5. Timestamp handling
# Always be explicit about timezone:
df = df.withColumn("ts", F.to_timestamp("ts_string", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"))
spark.conf.set("spark.sql.session.timeZone", "UTC")  # Explicit timezone

# 6. Schema enforcement at boundaries
# Read with enforced schema → fail if data doesn't conform
# Iceberg: schema enforcement built-in (rejects incompatible writes)
```

---

## Issue #74: Null Handling Inconsistencies

**Frequency**: Very High  
**Severity**: Medium - incorrect aggregations  
**Spark Component**: NullPropagation, NullIntolerant expressions

### Symptoms
```
# COUNT(*) vs COUNT(col) give different numbers (nulls!)
# JOIN missing matches because null != null
# Aggregations wrong: SUM includes nulls? Excludes nulls?
# Filter col = 'X' doesn't include rows where col IS NULL
```

### Root Cause
- SQL null semantics: null != null, null comparisons return null (not false)
- JOIN: null keys never match (null != null)
- COUNT(col) excludes nulls; COUNT(*) counts all rows
- Filter `col > 5` excludes nulls; need explicit `OR col IS NULL`

### Solution
```python
# 1. Understand null behavior in joins
# INNER JOIN: null keys NEVER match → rows silently dropped!
# To join on nullable keys, coalesce first:
df_left = df_left.withColumn("key", F.coalesce(F.col("key"), F.lit("__NULL__")))
df_right = df_right.withColumn("key", F.coalesce(F.col("key"), F.lit("__NULL__")))
result = df_left.join(df_right, "key", "inner")

# 2. Null-safe equality operator (<=>)
# Standard: NULL = NULL → NULL (evaluates to false in WHERE)
# Null-safe: NULL <=> NULL → TRUE
result = df1.join(df2, df1.key.eqNullSafe(df2.key))

# 3. Explicit null handling in aggregations
df.agg(
    F.count("*").alias("total_rows"),                    # Includes nulls
    F.count("amount").alias("non_null_amounts"),         # Excludes nulls
    F.sum("amount").alias("total_amount"),               # Excludes nulls
    F.count(F.when(F.col("amount").isNull(), 1)).alias("null_count")  # Count nulls
)

# 4. Filter with null awareness
# BAD: misses null values
df.filter(F.col("status") != "inactive")  # Excludes nulls!

# GOOD: explicitly handle nulls
df.filter((F.col("status") != "inactive") | F.col("status").isNull())
# OR
df.filter(~F.coalesce(F.col("status") == "inactive", F.lit(False)))

# 5. Fill nulls with defaults at source
df = df.fillna({
    "status": "unknown",
    "amount": 0,
    "country": "N/A"
})

# 6. Data quality check: monitor null ratios
null_report = df.select([
    (F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)) / F.count("*") * 100)
    .alias(f"{c}_null_pct")
    for c in df.columns
])
# Alert if null_pct exceeds expected threshold
```

---

## Issue #75: Timezone Handling Errors

**Frequency**: High  
**Severity**: High - wrong event attribution, SLA miscalculation  
**Spark Component**: DateTimeUtils, TimestampType

### Symptoms
```
# Events at 23:00 UTC showing up in wrong day's partition
# Aggregations by day give different results in dev (UTC) vs prod (US/Pacific)
# Daylight saving time transitions cause duplicate or missing hours
# Two systems disagree on which "day" an event belongs to
```

### Root Cause
- Spark's TimestampType stores as UTC internally
- Session timezone affects display and operations differently
- Source data has inconsistent timezone information
- DST transitions create non-existent or ambiguous times
- Partition by "date" without specifying whose timezone

### Solution
```python
# 1. ALWAYS set explicit session timezone
spark.conf.set("spark.sql.session.timeZone", "UTC")
# All timestamp operations now consistently use UTC
# Convert for business logic:
df = df.withColumn("event_date_pacific", 
    F.to_date(F.from_utc_timestamp("event_ts", "US/Pacific")))

# 2. Store timestamps in UTC, convert on read for business logic
df = df.withColumn("event_ts_utc", F.to_utc_timestamp("event_ts_local", "US/Eastern"))

# 3. Partition by UTC date (consistent regardless of timezone)
df = df.withColumn("partition_date", F.to_date(F.col("event_ts_utc")))
df.write.partitionBy("partition_date").parquet("s3://output/")

# 4. Handle DST explicitly
# 2AM doesn't exist on spring-forward day; 1AM exists twice on fall-back
# Use UTC to avoid entirely!

# 5. Validate timezone consistency
sample = df.select("event_ts").head(100)
# Check: are timestamps reasonable (not year 2053, not 1970)?
# Check: do timestamps have timezone info or are they ambiguous?

# 6. For legacy systems sending local time without timezone:
# Always document and enforce: "this field is US/Eastern" or "this field is UTC"
df = df.withColumn("event_ts_utc", 
    F.to_utc_timestamp(F.col("local_ts"), F.col("timezone_column")))
```

---

## Issue #76: Schema Evolution Breaking Downstream Consumers

**Frequency**: Medium-High  
**Severity**: High - downstream pipeline failures  
**Spark Component**: SchemaEvolution, Iceberg/Delta SchemaUpdate

### Symptoms
```
# Upstream team adds column → downstream job fails with unexpected schema
# Column renamed → downstream NULL values (old column name returns null)
# Type widened (INT→BIGINT) → downstream with strict schema rejects
# Column reordered → positional CSV readers break
```

### Root Cause
- No schema contract between producers and consumers
- Schema changes deployed without notification
- No backward/forward compatibility enforcement
- Consumers use positional access instead of column names

### Solution
```python
# 1. Use Iceberg schema evolution (safe by default)
# Iceberg tracks columns by ID, not position or name
spark.sql("ALTER TABLE catalog.db.events ADD COLUMNS (new_col STRING)")
# Old readers: new_col = NULL (safe)
# New readers: see new_col (safe)

# 2. Schema compatibility rules:
# BACKWARD compatible (safe): add nullable column, widen type
# BREAKING (unsafe): remove column, rename column, narrow type
# ALWAYS: add columns as NULLABLE

# 3. Schema validation at read time
expected_schema = StructType([...])
df = spark.read.parquet("s3://input/")
assert df.schema == expected_schema, \
    f"Schema mismatch!\nExpected: {expected_schema}\nActual: {df.schema}"

# 4. Use schema registry for streaming
# Confluent Schema Registry with BACKWARD compatibility mode
# Rejects incompatible schema changes at write time

# 5. Data contract testing in CI/CD
# test_schema_contract.py:
def test_output_schema():
    """Ensures output schema matches published contract."""
    contract = load_contract("contracts/events_v2.json")
    output_schema = run_pipeline_with_sample_data()
    assert schemas_compatible(contract, output_schema)

# 6. Graceful handling of unknown columns
# Read with expected schema (ignores extra columns):
df = spark.read.schema(expected_schema).parquet("s3://input/")
# Unknown columns silently dropped → no failure
```

---

## Issue #77: Decimal Precision Loss in Financial Calculations

**Frequency**: Medium  
**Severity**: Critical - financial discrepancies  
**Spark Component**: DecimalType, DecimalPrecision catalyst rule

### Symptoms
```
# SUM of amounts doesn't match expected total
# 0.1 + 0.2 != 0.3 (floating point)
# Large sums overflow DECIMAL precision
# Revenue reports off by cents/dollars after aggregation
# Decimal rounding inconsistent between Spark and source system
```

### Root Cause
- Using DOUBLE/FLOAT for monetary values (binary floating point imprecision)
- DECIMAL precision overflow during multiplication: DECIMAL(10,2) × DECIMAL(10,2) = DECIMAL(21,4)
- Spark truncates decimal if result exceeds max precision (38)
- Different rounding modes between systems

### Solution
```python
# 1. ALWAYS use DECIMAL for money (never FLOAT/DOUBLE)
df = df.withColumn("amount", F.col("amount").cast("decimal(18,2)"))
# DECIMAL(18,2) = up to 9,999,999,999,999,999.99

# 2. Be careful with arithmetic precision expansion
# DECIMAL(18,2) * DECIMAL(18,2) = DECIMAL(37,4) - close to max!
# DECIMAL(18,2) + DECIMAL(18,2) = DECIMAL(19,2) - safe
# Plan your precision requirements:
price = F.col("price").cast("decimal(10,2)")   # Up to 99,999,999.99
quantity = F.col("qty").cast("decimal(6,0)")    # Up to 999,999
# total = price * quantity → DECIMAL(17,2) - safe!

# 3. Control rounding explicitly
df = df.withColumn("rounded", F.round(F.col("amount"), 2))
# Spark uses HALF_UP rounding by default

# 4. Validate aggregation results
total = df.agg(F.sum("amount").cast("decimal(28,2)")).first()[0]
# Check against source system total
assert abs(total - expected_total) < 0.01, f"Discrepancy: {total} vs {expected_total}"

# 5. Avoid implicit widening
# BAD:
df.withColumn("calc", F.col("decimal_col") + 0.1)  # 0.1 is DOUBLE!
# GOOD:
df.withColumn("calc", F.col("decimal_col") + F.lit(0.1).cast("decimal(2,1)"))

# 6. For very large sums (trillions): use higher precision
# DECIMAL(38,2) is max in Spark → supports up to 10^36 (plenty)
df.agg(F.sum(F.col("amount").cast("decimal(38,2)")))
```

---

## Issue #78: Non-Deterministic Results (Different Runs Give Different Answers)

**Frequency**: Medium  
**Severity**: High - can't reproduce/validate  
**Spark Component**: Various (partitioning, ordering, floating point)

### Symptoms
```
# Same query on same data gives different results each run
# Row order changes between runs (breaks row_number without ORDER BY)
# Floating point aggregation order-dependent
# Test assertions fail intermittently
# "First" record changes between runs
```

### Root Cause
- No ORDER BY but relying on row order (undefined in distributed system)
- `row_number()` without deterministic tie-breaking
- Floating point SUM depends on order of addition (non-associative)
- `rand()` or `monotonically_increasing_id()` used without seed
- Hash partitioning distributes differently with different partition counts

### Solution
```python
# 1. Always use deterministic ordering for row_number/rank
# BAD (non-deterministic when ties exist):
w = Window.partitionBy("user_id").orderBy("timestamp")
df.withColumn("rn", F.row_number().over(w))  # Ties broken randomly!

# GOOD (deterministic tie-breaking):
w = Window.partitionBy("user_id").orderBy("timestamp", "event_id")
df.withColumn("rn", F.row_number().over(w))  # event_id breaks ties

# 2. For reproducible random: use seed
df.withColumn("random", F.rand(seed=42))
df.sample(0.1, seed=42)

# 3. For floating point aggregation: use DECIMAL or Kahan summation
# SUM(DOUBLE) depends on addition order → use DECIMAL
df.agg(F.sum(F.col("amount").cast("decimal(18,2)")))

# 4. Never rely on DataFrame row order
# BAD:
first_row = df.first()  # Which row? Undefined!

# GOOD:
first_row = df.orderBy("timestamp").first()  # Deterministic

# 5. For reproducible test results: fix partition count
spark.conf.set("spark.sql.shuffle.partitions", "100")  # Fixed, not dynamic

# 6. Use deterministic IDs
# BAD: monotonically_increasing_id() → different values each run
# GOOD: hash-based ID
df.withColumn("id", F.md5(F.concat_ws("|", "col1", "col2", "col3")))
```

---

## Issue #79: Data Quality Regression After Pipeline Change

**Frequency**: High  
**Severity**: High - broken data in production  
**Spark Component**: Application logic (not Spark-specific)

### Symptoms
```
# Pipeline change deployed → downstream dashboard shows impossible values
# Nulls suddenly appear where data was always present
# Record counts drop 50% after a "minor refactor"
# Aggregation results change (new logic incorrect for edge cases)
# Found 2 weeks later (no alerting on data quality)
```

### Root Cause
- Code change introduced logic error (edge case not handled)
- Filter condition changed (excluded data unintentionally)
- Join type changed (INNER → LEFT or vice versa → row count changes)
- Column computation modified without updating downstream expectations

### Solution
```python
# 1. Great Expectations / data quality checks in pipeline
from great_expectations.dataset import SparkDFDataset

ge_df = SparkDFDataset(df)
results = ge_df.expect_column_values_to_not_be_null("event_id")
results = ge_df.expect_column_values_to_be_between("amount", min_value=0, max_value=1000000)
results = ge_df.expect_table_row_count_to_be_between(min_value=1000000)
assert results.success, f"Data quality check failed: {results}"

# 2. Automated regression checks
def check_regression(new_df, reference_table):
    """Compare new output against known-good reference."""
    old_df = spark.read.table(reference_table)
    
    checks = {
        "row_count_change": abs(new_df.count() - old_df.count()) / old_df.count(),
        "null_increase": (
            new_df.select([F.sum(F.col(c).isNull().cast("int")).alias(c) for c in new_df.columns])
        ),
        "avg_change": (
            new_df.agg(F.avg("amount")).first()[0] / old_df.agg(F.avg("amount")).first()[0]
        )
    }
    
    assert checks["row_count_change"] < 0.05, "Row count changed > 5%!"
    assert 0.9 < checks["avg_change"] < 1.1, "Average amount changed > 10%!"

# 3. Shadow mode: run old and new in parallel
# Week 1: Run new pipeline, compare output with old pipeline's output
# Only switch after validation passes for N days

# 4. Unit tests for transformations
def test_amount_calculation():
    """Test edge cases in amount calculation."""
    test_data = spark.createDataFrame([
        (1, 0.0, "USD"),    # Zero amount
        (2, -5.0, "USD"),   # Negative (refund)
        (3, None, "USD"),   # Null amount
        (4, 999999.99, "USD"),  # Large amount
    ], ["id", "amount", "currency"])
    
    result = calculate_amounts(test_data)
    assert result.filter("id = 3").first()["computed_amount"] is None
    assert result.filter("id = 2").first()["computed_amount"] == -5.0

# 5. Deploy data quality SLAs
# Freshness: data arrives within SLA
# Completeness: null ratios within bounds
# Accuracy: aggregations match reconciliation
# Consistency: counts match across systems
```

---

## Issue #80: Character Encoding Issues (UTF-8 / Latin-1 Mix)

**Frequency**: Medium  
**Severity**: Medium - garbled data, failed parsing  
**Spark Component**: CSVParser, TextInputFormat

### Symptoms
```
# Garbled characters: "JosÃ©" instead of "José"
# MalformedInputException for certain rows
# CSV parsing fails on rows with special characters
# Byte order marks (BOM) appearing as garbage characters
# Different results on different cluster nodes (locale settings)
```

### Root Cause
- Source file is Latin-1/ISO-8859-1 but Spark assumes UTF-8
- Mixed encodings within same dataset
- BOM (Byte Order Mark) at file beginning
- Legacy systems producing Windows-1252 encoded data
- No encoding specified at read time

### Solution
```python
# 1. Specify encoding explicitly at read
df = spark.read \
    .option("encoding", "UTF-8") \  # Or: "ISO-8859-1", "Windows-1252"
    .option("charset", "UTF-8") \
    .csv("s3://input/data.csv")

# 2. Handle BOM (Byte Order Mark)
df = spark.read \
    .option("encoding", "UTF-8-BOM") \  # Handles BOM
    .csv("s3://input/data.csv")

# 3. For mixed encoding: read as binary and detect
from pyspark.sql.functions import decode

df_binary = spark.read.format("binaryFile").load("s3://input/")
# Then detect and convert per file

# 4. Sanitize text columns
df = df.withColumn("name", F.regexp_replace("name", "[^\x20-\x7E\xC0-\xFF]", ""))

# 5. Set JVM default encoding
spark.conf.set("spark.executor.extraJavaOptions", "-Dfile.encoding=UTF-8")
spark.conf.set("spark.driver.extraJavaOptions", "-Dfile.encoding=UTF-8")

# 6. Validate encoding in data quality checks
# Check for common encoding issues:
garbled = df.filter(F.col("name").rlike("Ã[€-¿]"))  # Double-encoded UTF-8 pattern
assert garbled.count() == 0, "Found garbled encoding!"
```

---

## Summary: Data Quality & Correctness Decision Tree

```
Data quality issue
├── Missing data?
│   ├── Fewer rows than expected → Issue #71 (silent data loss)
│   ├── Null where value expected → Issue #74 (null handling)
│   └── After pipeline change → Issue #79 (regression)
├── Duplicate data?
│   └── Same records appearing multiple times → Issue #72 (idempotent writes)
├── Wrong values?
│   ├── Type coercion silently changing values → Issue #73 (ANSI mode, DECIMAL)
│   ├── Financial amounts off by cents → Issue #77 (precision)
│   ├── Wrong timezone attribution → Issue #75 (UTC storage)
│   ├── Garbled characters → Issue #80 (encoding)
│   └── Different results each run → Issue #78 (determinism)
├── Schema problems?
│   └── Downstream broken by upstream change → Issue #76 (contracts, evolution)
└── Prevention
    ├── Great Expectations / data quality frameworks
    ├── Schema contracts between teams
    ├── Automated reconciliation (source count = sink count)
    └── Shadow mode for pipeline changes
```
