# Interview Questions Set 2: Apache Spark & Batch Processing (Q31-60)

---

## Q31: Explain Spark's lazy evaluation. Why does it matter for optimization?

**Answer:**
Spark builds a DAG of transformations without executing them until an ACTION is called.

**Transformations (lazy):** `map`, `filter`, `join`, `groupBy`, `select`, `withColumn`
**Actions (trigger execution):** `count`, `collect`, `write`, `show`, `take`

**Why it matters:**
1. **Catalyst optimizer** sees the ENTIRE plan before executing → can optimize globally
2. **Predicate pushdown:** Filter pushed into data source (Parquet, JDBC)
3. **Column pruning:** Only read needed columns from columnar storage
4. **Join reordering:** Optimizer picks best join order
5. **Pipelining:** Multiple narrow transforms fused into single stage

```python
# These build a plan but execute NOTHING:
df = spark.read.parquet("s3://data/orders/")
filtered = df.filter(col("amount") > 100)
projected = filtered.select("order_id", "amount", "customer_id")
joined = projected.join(customers, "customer_id")

# THIS triggers execution of entire plan:
joined.write.parquet("s3://output/")

# Catalyst optimizes: push filter+projection into parquet reader
# Read only 3 columns, skip row groups where amount <= 100
```

---

## Q32: What is the difference between narrow and wide transformations? Why does it matter?

**Answer:**

**Narrow transformations:** Each output partition depends on ONE input partition. No shuffle.
- `map`, `filter`, `flatMap`, `union`, `coalesce` (reduce partitions)
- Can be pipelined in same stage

**Wide transformations:** Each output partition depends on MULTIPLE input partitions. Requires shuffle.
- `groupByKey`, `reduceByKey`, `join`, `repartition`, `distinct`, `sort`
- Creates stage boundary. Data must be written to shuffle files and read by next stage.

**Why it matters:**
```
Stage 1 (pipelined, no shuffle):
  read → filter → map → map  [all in one task, one pass]

SHUFFLE BOUNDARY (expensive!)
  - Write shuffle files to disk
  - Network transfer between executors
  - Read shuffle files from disk

Stage 2 (after shuffle):
  groupBy → aggregate → write
```

**Shuffle is the #1 performance killer in Spark:**
- Disk I/O (write + read shuffle files)
- Network I/O (transfer between nodes)
- Memory pressure (sort buffers)
- Serialization/deserialization cost

---

## Q33: Explain data skew in Spark joins. How do you fix it?

**Answer:**

**Problem:** One join key has disproportionately more records than others. One task processes millions of rows while others finish quickly.

**Symptoms:**
- One task takes 10x longer than others
- Executor OOM on skewed partition
- Spark UI shows one task with much more data

**Solutions:**

**1. Salted join (manual):**
```python
# Add random salt to skewed key
SALT_FACTOR = 10
# Explode the smaller table
small_df = small_df.withColumn("salt", explode(array([lit(i) for i in range(SALT_FACTOR)])))
small_df = small_df.withColumn("join_key", concat(col("key"), lit("_"), col("salt")))

# Salt the large table
large_df = large_df.withColumn("join_key", concat(col("key"), lit("_"), (rand() * SALT_FACTOR).cast("int")))

# Join on salted key → skew distributed across SALT_FACTOR partitions
result = large_df.join(small_df, "join_key")
```

**2. AQE Skew Join (Spark 3.0+):**
```properties
spark.sql.adaptive.enabled=true
spark.sql.adaptive.skewJoin.enabled=true
spark.sql.adaptive.skewJoin.skewedPartitionFactor=5
spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=256MB
```
AQE automatically detects skewed partitions at runtime and splits them.

**3. Broadcast join (if one side is small):**
```python
from pyspark.sql.functions import broadcast
result = large_df.join(broadcast(small_df), "key")
# Small table broadcast to all executors → no shuffle for large table
```

**4. Isolate skewed keys:**
```python
skewed_keys = ["key_A", "key_B"]  # Known hot keys
skewed = large_df.filter(col("key").isin(skewed_keys))
non_skewed = large_df.filter(~col("key").isin(skewed_keys))

# Broadcast join for skewed portion
result_skewed = skewed.join(broadcast(small_df.filter(col("key").isin(skewed_keys))), "key")
# Regular join for non-skewed
result_normal = non_skewed.join(small_df, "key")
# Union results
result = result_skewed.union(result_normal)
```

---

## Q34: Explain Spark's Catalyst Optimizer phases.

**Answer:**

```
SQL/DataFrame API
      │
      ▼
┌─────────────────┐
│ 1. PARSING      │  SQL string → Unresolved Logical Plan
│                 │  (AST with unresolved references)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. ANALYSIS     │  Resolve references using Catalog
│                 │  (table names → schemas, column types)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. OPTIMIZATION │  Rule-based + Cost-based optimization
│    (Catalyst)   │  - Predicate pushdown
│                 │  - Column pruning
│                 │  - Constant folding
│                 │  - Join reordering (CBO)
│                 │  - Combine filters
│                 │  - Eliminate subqueries
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. PLANNING     │  Logical Plan → Physical Plan(s)
│                 │  Choose best physical strategy:
│                 │  - BroadcastHashJoin vs SortMergeJoin
│                 │  - HashAggregate vs SortAggregate
│                 │  - Scan with pushed filters
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. CODE GEN     │  Whole-stage codegen (Tungsten)
│                 │  Generate JVM bytecode for entire stage
│                 │  Eliminates virtual function calls
│                 │  CPU cache friendly tight loops
└─────────────────┘
```

**Key optimization rules:**
- **Predicate pushdown:** `filter` moves before `join`
- **Projection pushdown:** Only read needed columns from source
- **Combine filters:** `filter(A).filter(B)` → `filter(A AND B)`
- **Fold constants:** `1 + 2` → `3` at plan time
- **Eliminate redundancy:** Remove unnecessary projections/sorts

---

## Q35: What is Adaptive Query Execution (AQE)? What problems does it solve?

**Answer:**

**AQE** (Spark 3.0+) re-optimizes the query plan AT RUNTIME using statistics collected during execution.

**Three key features:**

**1. Dynamic Coalescing of Shuffle Partitions:**
```
Problem: spark.sql.shuffle.partitions = 200 (default)
  Some partitions: 1 MB (too small → overhead)
  Some partitions: 1 GB (too large → OOM)

AQE solution: After shuffle, merge small partitions
  200 partitions → coalesced to 50 (based on actual data sizes)
  
Config:
  spark.sql.adaptive.coalescePartitions.enabled=true
  spark.sql.adaptive.advisoryPartitionSizeInBytes=128MB
```

**2. Dynamic Join Strategy Switch:**
```
Problem: At plan time, Spark estimates table B = 500MB → SortMergeJoin
  At runtime, after filters, table B = 8MB → BroadcastHashJoin is better!

AQE solution: After reading actual shuffle data sizes,
  switch from SortMergeJoin to BroadcastHashJoin
  
Config:
  spark.sql.adaptive.localShuffleReader.enabled=true
```

**3. Dynamic Skew Join Optimization:**
```
Problem: Partition 42 has 10GB, others have 100MB

AQE solution: Split skewed partition into sub-partitions
  Partition 42 (10GB) → split into 40 sub-partitions (250MB each)
  Join with corresponding data from other side (replicated)
  
Config:
  spark.sql.adaptive.skewJoin.enabled=true
  spark.sql.adaptive.skewJoin.skewedPartitionFactor=5
```

---

## Q36: Explain Spark's memory management model.

**Answer:**

```
┌──────────────────────────────────────────────────────────────┐
│                 EXECUTOR MEMORY LAYOUT                        │
│                                                               │
│  Total: spark.executor.memory (e.g., 8GB)                    │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ RESERVED (300MB fixed)                                 │  │
│  │ Internal Spark objects                                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ USER MEMORY (40% of remaining = ~3GB)                  │  │
│  │ User data structures, RDD transformations              │  │
│  │ UDF variables, broadcast variables (non-cached)        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ UNIFIED MEMORY (60% of remaining = ~4.6GB)            │  │
│  │                                                        │  │
│  │  ┌──────────────────┐  ┌──────────────────────────┐   │  │
│  │  │  STORAGE (50%)   │  │  EXECUTION (50%)         │   │  │
│  │  │                  │◀▶│                           │   │  │
│  │  │  Cached RDDs     │  │  Shuffle buffers          │   │  │
│  │  │  Broadcast vars  │  │  Join hash tables         │   │  │
│  │  │  Unroll memory   │  │  Sort buffers             │   │  │
│  │  │                  │  │  Aggregation maps          │   │  │
│  │  └──────────────────┘  └──────────────────────────┘   │  │
│  │  DYNAMIC: Execution can evict Storage if needed        │  │
│  │  (but not below spark.memory.storageFraction)         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  OFF-HEAP (optional): spark.memory.offHeap.size              │
│  Avoids GC, used by Tungsten for sort/shuffle buffers        │
│                                                               │
│  OVERHEAD: spark.executor.memoryOverhead (10% or 384MB min)  │
│  Container overhead: non-JVM memory, PySpark, network buffers│
└──────────────────────────────────────────────────────────────┘
```

**OOM troubleshooting:**
- Execution OOM: Reduce `spark.sql.shuffle.partitions` (more, smaller partitions)
- Storage OOM: Reduce cache, use DISK_ONLY storage level
- Container killed (YARN): Increase `spark.executor.memoryOverhead`
- Driver OOM: Avoid `collect()`, increase `spark.driver.memory`

---

## Q37: How do you optimize a Spark job that reads from a data lake with small files?

**Answer:**

**Problem:** 100K small Parquet files (1-5 MB each) → 100K tasks → massive scheduling overhead, slow listing.

**Solutions:**

**1. Combine input splits:**
```python
# Spark 3.x file listing optimization
spark.conf.set("spark.sql.files.maxPartitionBytes", "256MB")  # Combine small files
spark.conf.set("spark.sql.files.openCostInBytes", "4MB")  # Penalty for opening a file

# Result: Multiple small files read by single task
```

**2. Compact at source (periodic maintenance):**
```python
# Iceberg: rewrite_data_files
spark.sql("CALL catalog.system.rewrite_data_files(table => 'db.orders', options => map('target-file-size-bytes', '268435456'))")

# Delta Lake: OPTIMIZE
spark.sql("OPTIMIZE delta.`s3://lake/orders/` ZORDER BY (customer_id)")
```

**3. Pre-listing optimization:**
```python
spark.conf.set("spark.sql.sources.parallelPartitionDiscovery.threshold", "32")
spark.conf.set("spark.sql.hive.metastorePartitionPruning", "true")
# Use partition pruning in WHERE clause to reduce file listing
```

**4. Bin packing with repartition before write:**
```python
df.repartition(100)  # Fewer, larger output files
  .write.mode("overwrite")
  .parquet("s3://lake/orders-compacted/")
```

---

## Q38: Explain Spark's shuffle mechanism in detail.

**Answer:**

```
SHUFFLE (e.g., groupBy, join, repartition):

Stage 1 (Map side):                    Stage 2 (Reduce side):
┌─────────────────────┐                ┌─────────────────────┐
│ Task 0              │                │ Task 0              │
│ Process partition 0 │                │ Fetch data for      │
│ Write shuffle files:│                │ reduce partition 0  │
│   part-0-0.data     │──────────────▶ │ from ALL map tasks  │
│   part-0-1.data     │──┐             │ Sort + Aggregate    │
│   part-0-2.data     │──┼──┐          └─────────────────────┘
└─────────────────────┘  │  │          
                         │  │          ┌─────────────────────┐
┌─────────────────────┐  │  │          │ Task 1              │
│ Task 1              │  │  └────────▶ │ Fetch data for      │
│ Process partition 1 │  │             │ reduce partition 1  │
│ Write shuffle files:│  │             └─────────────────────┘
│   part-1-0.data     │──┘             
│   part-1-1.data     │──────────────▶ ┌─────────────────────┐
│   part-1-2.data     │               │ Task 2              │
└─────────────────────┘  ─────────────▶│ Fetch data for      │
                                       │ reduce partition 2  │
                                       └─────────────────────┘

Sort-based shuffle (default):
  Map side: Sort records by (partition_id, key), write single file
  Index file: byte offset for each partition within data file
  Reduce side: Fetch relevant bytes, external sort if needed
```

**Shuffle configuration:**
```properties
spark.sql.shuffle.partitions=200          # Number of reduce tasks
spark.shuffle.file.buffer=64k             # Buffer for shuffle write
spark.reducer.maxSizeInFlight=96MB        # Max fetch size per reducer
spark.shuffle.io.maxRetries=10            # Retry failed fetches
spark.shuffle.sort.bypassMergeThreshold=200  # Skip sort if few partitions
spark.shuffle.compress=true               # Compress shuffle data
spark.shuffle.spill.compress=true         # Compress spill files
```

---

## Q39: What are the different join strategies in Spark? When is each chosen?

**Answer:**

| Strategy | Condition | Mechanism | Performance |
|----------|-----------|-----------|-------------|
| Broadcast Hash Join | One side < `spark.sql.autoBroadcastJoinThreshold` (10MB) | Small table broadcast to all executors, hash join | Best (no shuffle) |
| Shuffle Hash Join | Both tables small-medium, not sorted | Shuffle both, build hash table on smaller side | Good |
| Sort Merge Join | Large tables, join keys sortable | Shuffle + sort both sides, merge | Default for large |
| Broadcast Nested Loop | One side small, no equi-join condition | Broadcast + nested loop | For non-equi joins |
| Cartesian Product | Cross join, no condition | All pairs | Avoid! |

**Forcing join strategy:**
```python
# Force broadcast (even if table is large)
from pyspark.sql.functions import broadcast
result = big_df.join(broadcast(medium_df), "key")

# Hint in SQL
spark.sql("""
  SELECT /*+ BROADCAST(b) */ a.*, b.name
  FROM orders a JOIN customers b ON a.customer_id = b.id
""")

# Sort Merge Join hint
spark.sql("""
  SELECT /*+ MERGE(a, b) */ ...
""")
```

**AQE dynamic switch:** At runtime, if shuffled data is small enough → switch from SMJ to BHJ.

---

## Q40: How do you handle slowly changing dimensions in Spark + Delta Lake?

**Answer:**

**SCD Type 2 with Delta Lake MERGE:**
```python
from delta.tables import DeltaTable

# Existing dimension table
dim_customers = DeltaTable.forPath(spark, "s3://lake/dim_customers")

# New/updated records from source
updates = spark.read.parquet("s3://staging/customers_daily/")

# MERGE operation for SCD Type 2
(dim_customers.alias("target")
  .merge(
    updates.alias("source"),
    "target.customer_id = source.customer_id AND target.is_current = true"
  )
  # When match AND values changed → expire old row
  .whenMatchedUpdate(
    condition="target.name != source.name OR target.email != source.email",
    set={
      "is_current": "false",
      "valid_to": "source.updated_at"
    }
  )
  # Insert new version of changed rows
  .whenNotMatchedInsert(
    values={
      "customer_id": "source.customer_id",
      "name": "source.name",
      "email": "source.email",
      "valid_from": "source.updated_at",
      "valid_to": "lit('9999-12-31')",
      "is_current": "true"
    }
  )
  .execute()
)

# Also insert new versions for updated records
changed = (updates.alias("s")
  .join(dim_customers.toDF().alias("t"),
    (col("s.customer_id") == col("t.customer_id")) & 
    (col("t.is_current") == False) &
    (col("t.valid_to") == col("s.updated_at")))
)
changed.select(
  col("s.customer_id"), col("s.name"), col("s.email"),
  col("s.updated_at").alias("valid_from"),
  lit("9999-12-31").alias("valid_to"),
  lit(True).alias("is_current")
).write.format("delta").mode("append").save("s3://lake/dim_customers")
```

---

## Q41: Explain Spark's broadcast variable and accumulator. Production use cases?

**Answer:**

**Broadcast variable:** Read-only shared data sent to all executors once.
```python
# Use case: Lookup enrichment (country codes, config, small dimension)
country_map = {"US": "United States", "GB": "United Kingdom", ...}
broadcast_countries = spark.sparkContext.broadcast(country_map)

@udf(StringType())
def get_country_name(code):
    return broadcast_countries.value.get(code, "Unknown")

df = df.withColumn("country_name", get_country_name(col("country_code")))

# Without broadcast: country_map serialized with EVERY task (100 tasks = 100 copies)
# With broadcast: Sent once per executor via BitTorrent-like protocol
```

**Accumulator:** Write-only counter aggregated across tasks.
```python
# Use case: Track data quality metrics during processing
bad_records = spark.sparkContext.accumulator(0)
null_emails = spark.sparkContext.accumulator(0)

def process_record(row):
    if row["email"] is None:
        null_emails.add(1)
    if not is_valid(row):
        bad_records.add(1)
    return transform(row)

result_rdd = input_rdd.map(process_record)
result_rdd.count()  # Trigger execution

print(f"Bad records: {bad_records.value}")
print(f"Null emails: {null_emails.value}")

# CAVEAT: Accumulators may double-count on task retries!
# Use only in actions, not transformations that might re-execute
```

---

## Q42: How do you tune `spark.sql.shuffle.partitions`?

**Answer:**

**Default:** 200 partitions (almost always wrong)

**Too few partitions:**
- Each partition too large → OOM
- Poor parallelism (fewer tasks than cores)
- Skew more impactful

**Too many partitions:**
- Scheduling overhead (1ms per task × 10K tasks = 10s overhead)
- Small files output
- Shuffle metadata overhead

**Sizing rule:**
```
Target partition size: 100-200 MB
shuffle_partitions = total_shuffle_data_size / target_partition_size

Example: 
  Data after shuffle = 100 GB
  Target partition = 200 MB
  Partitions = 100GB / 200MB = 500
```

**Best approach: Use AQE (Spark 3.0+):**
```properties
spark.sql.adaptive.enabled=true
spark.sql.adaptive.coalescePartitions.enabled=true
spark.sql.adaptive.coalescePartitions.initialPartitionNum=2000  # Start high
spark.sql.adaptive.advisoryPartitionSizeInBytes=128MB  # Target size
# AQE will coalesce small partitions down to target size automatically
```

---

## Q43: Your Spark job fails with "Container killed by YARN for exceeding memory limits". Diagnose.

**Answer:**

**Root cause:** Container uses more memory than allocated (`executor memory + overhead`).

**Memory breakdown:**
```
Container limit = spark.executor.memory + spark.executor.memoryOverhead
Default: 8GB + max(384MB, 10% × 8GB) = 8GB + 800MB = 8.8GB
```

**Common causes:**
1. **PySpark overhead:** Python processes use memoryOverhead, not executor.memory
2. **Large broadcast variables:** Stored off-heap in overhead region
3. **Native library memory:** (e.g., snappy, lz4 decompression buffers)
4. **UDF memory leaks:** Python UDFs accumulating data
5. **Too many tasks per executor:** Each task needs memory for its operation

**Fixes:**
```properties
# Increase overhead (most common fix)
spark.executor.memoryOverhead=2G  # or 20% of executor memory

# For PySpark specifically
spark.executor.pyspark.memory=1G  # Python worker memory

# Reduce parallelism per executor
spark.executor.cores=3  # instead of 5 → fewer concurrent tasks per executor

# Use fewer, larger executors
spark.executor.memory=16G
spark.executor.cores=4
spark.executor.memoryOverhead=4G
```

---

## Q44: Explain Spark Structured Streaming. How does it achieve exactly-once?

**Answer:**

**Model:** Treats streaming as incremental batch processing on an unbounded table.

**Execution modes:**
- **Micro-batch (default):** Process data in small batches (100ms-seconds)
- **Continuous (experimental):** ~1ms latency, at-least-once only

**Exactly-once guarantee (micro-batch):**
```
1. SOURCES (replayable): Kafka offsets tracked in checkpoint
2. STATE: Checkpointed to reliable storage (HDFS/S3)
3. SINKS (idempotent): Write with deterministic output paths/keys

Checkpoint contains:
  - Source offsets (Kafka: topic/partition/offset)
  - State store snapshots
  - Committed batch ID

Recovery: Replay from last checkpointed offsets
  → Reprocess same data → Produce same output (idempotent sink)
  → Exactly-once end-to-end
```

**Idempotent sinks:**
- File sink: batch_id in filename → re-upload = overwrite same file
- Delta Lake: batch_id tracked → duplicate batch is no-op
- Kafka sink: Idempotent producer + transaction per batch
- JDBC: Use MERGE/UPSERT with natural key

```python
query = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "broker:9092")
    .option("subscribe", "orders")
    .load()
    .selectExpr("CAST(value AS STRING)")
    .writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "s3://checkpoints/orders/")
    .trigger(processingTime="10 seconds")
    .start("s3://lake/orders/"))
```

---

## Q45: How do you handle late data in Spark Structured Streaming?

**Answer:**

**Watermark:** Threshold declaring how late data can arrive.

```python
from pyspark.sql.functions import window, col

orders = spark.readStream.format("kafka").load()

windowed_counts = (orders
    .withWatermark("event_time", "10 minutes")  # Allow 10 min late
    .groupBy(
        window(col("event_time"), "5 minutes"),  # 5-min tumbling window
        col("category")
    )
    .agg(sum("amount").alias("total"))
)

# Watermark = max(event_time) - 10 minutes
# Windows older than watermark are "closed" → late data dropped
# State for closed windows cleaned up
```

**Output modes:**
- **Append:** Emit ONLY when window is finalized (after watermark passes). No updates.
- **Update:** Emit updated rows as they change. Rows can appear multiple times.
- **Complete:** Emit entire result table every trigger. Only for non-windowed aggregations.

**Trade-offs:**
- Larger watermark → more late data captured, more state to maintain
- Smaller watermark → less state, faster cleanup, but drops more late arrivals
- No watermark → state grows unbounded (OOM eventually)

---

## Q46: Compare `repartition()` vs `coalesce()`. When to use each?

**Answer:**

| Aspect | `repartition(n)` | `coalesce(n)` |
|--------|-------------------|---------------|
| Direction | Increase OR decrease | Only decrease |
| Shuffle | Always (full shuffle) | No shuffle (merge partitions) |
| Balance | Evenly distributed | May be uneven |
| Use case | Increase parallelism, even distribution | Reduce output files |
| Cost | Expensive (network + disk) | Cheap (in-memory merge) |

```python
# GOOD: Reduce output files before write (no shuffle)
df.coalesce(10).write.parquet("s3://output/")

# GOOD: Repartition by key for downstream joins (shuffle, but needed)
df.repartition(100, "customer_id").write.parquet("s3://output/")

# BAD: coalesce(1) on huge dataset → single task for all data → OOM
# Use repartition(1) if you must have 1 file (triggers shuffle, distributed)

# BAD: repartition() just to reduce files → use coalesce instead (cheaper)
```

**With AQE:** Less need for manual repartition. AQE coalesces small partitions automatically.

---

## Q47: What is predicate pushdown and how does it work with Parquet?

**Answer:**

**Predicate pushdown:** Filter condition pushed into the data source, so only matching data is read.

**Parquet pushdown levels:**

**1. Row group level (column statistics):**
```
Parquet file structure:
  Row Group 0: min(amount)=10, max(amount)=500
  Row Group 1: min(amount)=501, max(amount)=2000
  Row Group 2: min(amount)=50, max(amount)=300

Query: WHERE amount > 1000
  → Skip Row Group 0 (max=500 < 1000) ✓
  → Read Row Group 1 (contains values > 1000) 
  → Skip Row Group 2 (max=300 < 1000) ✓
  → Only 1 of 3 row groups read!
```

**2. Page level (Parquet 2.0 page index):**
- Statistics per data page (finer granularity within row group)

**3. Partition pruning:**
```python
# Data partitioned by date
df = spark.read.parquet("s3://lake/orders/")
# Query with partition filter
result = df.filter(col("order_date") == "2024-01-15")
# Only reads s3://lake/orders/order_date=2024-01-15/ directory
```

**4. Column pruning:**
```python
# Only 3 of 50 columns read from Parquet (columnar = skip other columns)
df.select("order_id", "amount", "status").filter(...)
```

---

## Q48: How do you implement incremental processing in Spark batch jobs?

**Answer:**

**Pattern 1: Partition-based incremental (most common):**
```python
# Only process today's partition
today = datetime.now().strftime("%Y-%m-%d")
new_data = spark.read.parquet(f"s3://raw/orders/date={today}/")

# Process and append to target
result = transform(new_data)
result.write.mode("append").partitionBy("date").parquet("s3://lake/orders/")
```

**Pattern 2: High watermark (max timestamp):**
```python
# Read last processed timestamp from state store
last_processed = spark.read.json("s3://state/orders_watermark.json")
max_ts = last_processed.select("max_timestamp").first()[0]

# Read only new records
new_records = (spark.read.parquet("s3://raw/orders/")
    .filter(col("updated_at") > max_ts))

# Process
result = transform(new_records)
result.write.mode("append").save("s3://lake/orders/")

# Update watermark
new_max = new_records.agg(max("updated_at")).first()[0]
spark.createDataFrame([{"max_timestamp": new_max}]).write.mode("overwrite").json("s3://state/orders_watermark.json")
```

**Pattern 3: Delta Lake MERGE (upsert):**
```python
from delta.tables import DeltaTable

target = DeltaTable.forPath(spark, "s3://lake/orders/")
new_data = spark.read.parquet(f"s3://raw/orders/date={today}/")

(target.alias("t")
    .merge(new_data.alias("s"), "t.order_id = s.order_id")
    .whenMatchedUpdateAll()
    .whenNotMatchedInsertAll()
    .execute())
```

---

## Q49: Your Spark job takes 3 hours. How do you systematically optimize it?

**Answer:**

**Step 1: Profile with Spark UI**
```
Check:
1. Stage timeline: Which stages are slowest?
2. Task distribution: Skewed tasks (one task 10x others)?
3. Shuffle read/write sizes: How much data shuffled?
4. GC time: >10% of task time = memory pressure
5. Spill (disk): Insufficient memory for operations
```

**Step 2: Identify bottleneck type**

| Symptom | Bottleneck | Fix |
|---------|-----------|-----|
| One task 10x slower | Data skew | Salted join, AQE |
| All tasks slow, high GC | Memory pressure | More memory, fewer tasks/executor |
| Large shuffle write | Too many shuffles | Reduce joins, pre-partition |
| Long listing time | Small files | Compact, use Delta/Iceberg |
| Wait time between stages | Scheduling overhead | Fewer partitions, bigger tasks |

**Step 3: Apply optimizations (priority order):**
```properties
# 1. Enable AQE (free wins)
spark.sql.adaptive.enabled=true

# 2. Right-size partitions
spark.sql.shuffle.partitions=auto  # or calculated value

# 3. Broadcast small tables
spark.sql.autoBroadcastJoinThreshold=100MB  # up from 10MB

# 4. Avoid unnecessary shuffles
# Use bucket joins (pre-shuffled tables)
df.write.bucketBy(100, "customer_id").saveAsTable("orders_bucketed")

# 5. Cache strategically
intermediate_df.cache()  # Only if reused multiple times

# 6. Use columnar formats with statistics (Parquet + Z-order)

# 7. Reduce serialization
spark.serializer=org.apache.spark.serializer.KryoSerializer
```

---

## Q50: Explain bucketing in Spark. How does it eliminate shuffle?

**Answer:**

**Bucketing:** Pre-partition data into fixed buckets by hash of column(s) at write time.

```python
# Write bucketed table
(orders_df
    .write
    .bucketBy(100, "customer_id")  # 100 buckets, hashed by customer_id
    .sortBy("order_date")           # Sorted within each bucket
    .saveAsTable("orders_bucketed"))

# Write matching bucketed table
(customers_df
    .write
    .bucketBy(100, "customer_id")  # SAME bucket count and column
    .saveAsTable("customers_bucketed"))

# Join WITHOUT shuffle!
result = spark.table("orders_bucketed").join(
    spark.table("customers_bucketed"), "customer_id")
# Both tables already co-partitioned → no shuffle needed!
```

**Requirements for shuffle-free join:**
- Same bucket count
- Same bucket column(s)
- Same bucketing hash function
- Both registered in Hive metastore

**When to use:**
- Large tables joined repeatedly on same key
- ETL pipelines with predictable join patterns
- Replaces repartitioning at query time

---

## Q51: What is the difference between `cache()`, `persist()`, and `checkpoint()`?

**Answer:**

| Feature | `cache()` | `persist(level)` | `checkpoint()` |
|---------|-----------|-------------------|----------------|
| Storage | MEMORY_AND_DISK | Configurable | Reliable storage (HDFS/S3) |
| Lineage | Preserved | Preserved | TRUNCATED |
| Recompute on loss | Yes (from lineage) | Yes | No (reads from checkpoint) |
| Use case | Reuse intermediate | Control storage | Break long lineages |

```python
# cache = persist(StorageLevel.MEMORY_AND_DISK)
df.cache()

# persist with explicit level
from pyspark import StorageLevel
df.persist(StorageLevel.MEMORY_ONLY)         # Fast, but lost if evicted
df.persist(StorageLevel.MEMORY_AND_DISK)     # Spill to disk if needed
df.persist(StorageLevel.DISK_ONLY)           # Only disk (save memory)
df.persist(StorageLevel.MEMORY_ONLY_SER)     # Serialized (less memory, CPU cost)

# checkpoint: Breaks lineage (critical for iterative algorithms)
spark.sparkContext.setCheckpointDir("s3://checkpoints/")
df.checkpoint()  # Materializes to S3, forgets how df was computed
# Use when: lineage is 100+ stages (e.g., ML training loops)
# Prevents stack overflow in lineage graph traversal
```

---

## Q52: How does Spark handle failures? Explain task-level and stage-level retries.

**Answer:**

**Task failure:**
```
Task fails (exception, OOM, node crash)
  → Spark retries on SAME or DIFFERENT executor
  → spark.task.maxFailures = 4 (default)
  → If all retries fail → stage fails

Speculative execution (for stragglers):
  spark.speculation = true
  spark.speculation.quantile = 0.9  # Launch speculative if slower than 90%
  First to finish wins, other killed
```

**Stage failure:**
```
Stage fails (all task retries exhausted for one task)
  → spark.stage.maxConsecutiveAttempts = 4
  → Retry entire stage (re-read shuffle outputs from previous stage)
  → If shuffle files lost (executor died): recompute missing partitions
```

**Shuffle file loss:**
```
Executor storing shuffle files crashes:
  → Reduce tasks cannot fetch shuffle data
  → Spark re-runs map tasks to regenerate lost shuffle files
  → Then reduce tasks retry

External Shuffle Service (ESS):
  spark.shuffle.service.enabled=true
  → Shuffle files survive executor death
  → Reduces recomputation on executor loss
```

**Driver failure:**
- Without checkpoint: Job completely lost
- With checkpoint (streaming): Restart from last checkpoint
- Cluster mode: YARN/K8s can restart driver container

---

## Q53: Explain Delta Lake's transaction log. How does it provide ACID on object storage?

**Answer:**

```
Delta table on S3:
s3://lake/orders/
├── _delta_log/                  # Transaction log
│   ├── 00000000000000000000.json   # Version 0 (initial write)
│   ├── 00000000000000000001.json   # Version 1 (append)
│   ├── 00000000000000000002.json   # Version 2 (update)
│   ├── ...
│   └── 00000000000000000010.checkpoint.parquet  # Checkpoint (every 10)
├── part-00000-xxx.parquet       # Data files
├── part-00001-xxx.parquet
└── part-00002-xxx.parquet
```

**Transaction log entry (JSON):**
```json
// Version 1: Append new data
{"add": {"path": "part-00003-abc.parquet", "size": 1048576, "partitionValues": {"date": "2024-01-15"}, "stats": "{\"numRecords\":10000,\"minValues\":{\"amount\":1.5},\"maxValues\":{\"amount\":9999.0}}"}}

// Version 2: Update (delete old file + add new)
{"remove": {"path": "part-00001-xxx.parquet", "deletionTimestamp": 1706000000}}
{"add": {"path": "part-00004-def.parquet", "size": 1048000, "stats": "..."}}
```

**ACID mechanism:**
- **Atomicity:** Write new log entry atomically (S3 PUT is atomic for single object)
- **Consistency:** Read log to construct consistent snapshot
- **Isolation:** Optimistic concurrency. Conflicting writes → one wins (first writer), other retries.
- **Durability:** Data files + log on S3 (11 9's durability)

**Conflict resolution:**
```
Writer A: reads version 5, writes version 6 (modifies file X)
Writer B: reads version 5, tries to write version 6 (modifies file Y)
  → B fails (version 6 already exists)
  → B re-reads log, checks if conflict (does A's change affect B's files?)
  → If no conflict: B retries as version 7 (successful)
  → If conflict: B throws ConcurrentModificationException
```

---

## Q54: How do you handle data partitioning strategy in a data lake?

**Answer:**

**Partitioning trade-offs:**
```
Too few partitions (e.g., year only):
  → Full scan within partition (large files)
  → Poor query performance for filtered queries

Too many partitions (e.g., year/month/day/hour/minute):
  → Small files problem (millions of tiny files)
  → Slow file listing
  → High metadata overhead
```

**Choosing partition columns:**
```python
# Rule 1: Partition by columns used in WHERE clauses
# Rule 2: Each partition should have 100MB - 1GB of data
# Rule 3: Limit cardinality (< 10K partitions total)

# GOOD: Daily partitioned, ~500MB per partition
df.write.partitionBy("date").parquet("s3://lake/orders/")

# BAD: User ID partition (millions of values → millions of folders)
df.write.partitionBy("user_id").parquet(...)  # DON'T DO THIS

# GOOD for high-cardinality: Use Z-ORDER / bucketing instead
spark.sql("OPTIMIZE orders ZORDER BY (customer_id)")
```

**Multi-level partitioning:**
```
s3://lake/events/
├── year=2024/
│   ├── month=01/
│   │   ├── day=15/
│   │   │   ├── part-00000.parquet  (target: 256MB each)
│   │   │   └── part-00001.parquet
```

**Z-Ordering (data clustering within partitions):**
- Collocate related data (by customer_id) within files
- Improves predicate pushdown (min/max statistics per file more useful)
- Available in Delta Lake, Iceberg (sort orders)

---

## Q55: Explain the difference between `groupByKey` and `reduceByKey` in Spark RDD API.

**Answer:**

**`groupByKey`** — Shuffles ALL data, groups by key, returns iterator of values:
```python
rdd.groupByKey()
# (A, [1,2,3,4,5])  ← All values for A sent to one reducer (lots of data!)
# Then: map(lambda (k,vs): (k, sum(vs)))  ← Reduce locally
```

**`reduceByKey`** — Combines values MAP-SIDE first, then shuffles reduced values:
```python
rdd.reduceByKey(lambda a, b: a + b)
# Map side: A→(1+2)=3, A→(3+4+5)=12  ← partial aggregation BEFORE shuffle
# Shuffle: (A, 3), (A, 12)             ← Much less data transferred!
# Reduce: (A, 15)
```

**Performance impact:**
```
Data: 1 billion records, 1000 unique keys
groupByKey: Shuffles 1 billion records (all of them)
reduceByKey: Shuffles ~1000 records (one partial sum per key per partition)
```

**Rule:** NEVER use `groupByKey` for aggregation. Use `reduceByKey`, `aggregateByKey`, or `combineByKey`.

**DataFrame equivalent (always optimized):**
```python
df.groupBy("key").agg(sum("value"))
# Catalyst automatically does partial aggregation (map-side combine)
```

---

## Q56: How do you write a Spark application that processes both batch and streaming?

**Answer:**

**Lambda architecture with unified code:**
```python
def transform(df):
    """Same transformation logic for batch and streaming"""
    return (df
        .filter(col("amount") > 0)
        .withColumn("tax", col("amount") * 0.1)
        .withColumn("total", col("amount") + col("tax"))
        .groupBy("category")
        .agg(sum("total").alias("revenue")))

# BATCH mode:
batch_df = spark.read.parquet("s3://lake/orders/date=2024-01-15/")
batch_result = transform(batch_df)
batch_result.write.mode("overwrite").parquet("s3://output/daily/")

# STREAMING mode:
stream_df = (spark.readStream
    .format("kafka")
    .option("subscribe", "orders")
    .load()
    .select(from_json(col("value").cast("string"), schema).alias("data"))
    .select("data.*"))

stream_result = transform(stream_df)
(stream_result.writeStream
    .format("delta")
    .outputMode("complete")
    .option("checkpointLocation", "s3://checkpoints/orders/")
    .start("s3://lake/orders_streaming/"))
```

**Unified with Delta Lake (Kappa architecture):**
- Stream writes to Delta table
- Batch reads from same Delta table (time travel for point-in-time)
- No separate batch/stream pipelines

---

## Q57: What are the common causes of Spark OOM errors? How do you fix each?

**Answer:**

| Error | Cause | Fix |
|-------|-------|-----|
| `java.lang.OutOfMemoryError: Java heap space` | Executor heap exhausted | Increase `spark.executor.memory`, reduce data per task |
| `Container killed by YARN for exceeding memory limits` | Off-heap/Python exceeds overhead | Increase `spark.executor.memoryOverhead` |
| Driver OOM | `collect()`, large broadcast, many small tasks | Increase `spark.driver.memory`, avoid `collect()` |
| `GC overhead limit exceeded` | Too much GC, not freeing memory | Fewer objects, more memory, use DataFrame (not RDD) |
| `Unable to acquire X bytes of memory` | Execution memory exhausted (sort/join) | More shuffle partitions, less data per task |

**Systematic approach:**
```python
# 1. Increase partitions (smaller data per task)
spark.conf.set("spark.sql.shuffle.partitions", "500")

# 2. Reduce executor cores (fewer concurrent tasks competing for memory)
# --executor-cores 2 instead of 5

# 3. Use disk for large operations
spark.conf.set("spark.sql.join.preferSortMergeJoin", "true")  # Sort-merge spills to disk

# 4. Avoid collecting large datasets
# BAD: df.collect()
# GOOD: df.write.parquet("s3://output/")

# 5. Use serialized storage for cached data
df.persist(StorageLevel.MEMORY_AND_DISK_SER)
```

---

## Q58: Explain Spark on Kubernetes vs YARN. When would you choose each?

**Answer:**

| Aspect | Spark on YARN | Spark on Kubernetes |
|--------|---------------|---------------------|
| Cluster | Dedicated Hadoop cluster | Shared K8s cluster |
| Resource isolation | Queue-based | Pod resource limits + namespaces |
| Container overhead | Low (JVM only) | Higher (pod startup) |
| Multi-tenancy | Queue configs | Namespace/quota |
| Auto-scaling | Limited (nodemanager scale) | HPA/Cluster Autoscaler |
| Docker support | Limited | Native (custom images) |
| Cost model | Fixed cluster | Pay per pod-second |
| Ecosystem | HDFS co-located (data locality) | S3/GCS (no locality) |
| Maturity | Very mature | Mature (GA since Spark 3.1) |
| Dynamic allocation | Supported | Supported (shuffle service harder) |

**Choose YARN when:**
- Existing Hadoop infrastructure
- Need data locality (HDFS reads)
- Mature multi-tenant policies required
- Running alongside Hive, HBase, etc.

**Choose Kubernetes when:**
- Cloud-native, no Hadoop dependency
- Need auto-scaling (scale to zero)
- Custom container images (ML dependencies)
- Multi-language workloads on same cluster
- Cost optimization (spot instances + autoscaler)

---

## Q59: How do you implement data quality checks within a Spark batch pipeline?

**Answer:**

```python
from pyspark.sql.functions import col, count, when, lit, sum as spark_sum

def run_quality_checks(df, table_name):
    """Run data quality checks, fail pipeline if critical checks fail."""
    
    checks = []
    total_rows = df.count()
    
    # Check 1: Null rate on critical columns
    for column in ["order_id", "customer_id", "amount"]:
        null_count = df.filter(col(column).isNull()).count()
        null_rate = null_count / total_rows
        checks.append({
            "check": f"null_rate_{column}",
            "value": null_rate,
            "threshold": 0.001,  # < 0.1% nulls allowed
            "passed": null_rate < 0.001
        })
    
    # Check 2: Uniqueness of primary key
    distinct_keys = df.select("order_id").distinct().count()
    dup_rate = 1 - (distinct_keys / total_rows)
    checks.append({
        "check": "uniqueness_order_id",
        "value": dup_rate,
        "threshold": 0.0,
        "passed": dup_rate == 0.0
    })
    
    # Check 3: Value range
    out_of_range = df.filter((col("amount") <= 0) | (col("amount") > 1000000)).count()
    checks.append({
        "check": "amount_range",
        "value": out_of_range,
        "threshold": 0,
        "passed": out_of_range == 0
    })
    
    # Check 4: Volume (compare to yesterday ±50%)
    yesterday_count = get_yesterday_count(table_name)
    volume_ratio = total_rows / yesterday_count if yesterday_count > 0 else 1
    checks.append({
        "check": "volume_stability",
        "value": volume_ratio,
        "threshold": 0.5,  # No less than 50% of yesterday
        "passed": 0.5 <= volume_ratio <= 2.0
    })
    
    # Evaluate results
    failed = [c for c in checks if not c["passed"]]
    
    # Log all results to monitoring table
    spark.createDataFrame(checks).write.mode("append").saveAsTable("data_quality_log")
    
    if failed:
        critical = [c for c in failed if c["check"].startswith("null_rate") or c["check"] == "uniqueness"]
        if critical:
            raise DataQualityException(f"CRITICAL quality failure: {critical}")
        else:
            alert_slack(f"WARNING: Non-critical quality issues: {failed}")
    
    return df  # Pass through if all critical checks pass
```

---

## Q60: Design a cost-efficient Spark architecture for processing 10 TB daily on cloud.

**Answer:**

```
Architecture:
┌─────────────────────────────────────────────────────────────┐
│               COST-OPTIMIZED SPARK ON CLOUD                  │
│                                                               │
│  ┌───────────────────────────────────────────────────┐       │
│  │ Orchestrator: Airflow (trigger Spark jobs)        │       │
│  └───────────────────────┬───────────────────────────┘       │
│                          │                                    │
│  ┌───────────────────────▼───────────────────────────┐       │
│  │ Spark on K8s (or EMR Serverless / Dataproc)       │       │
│  │                                                    │       │
│  │ Driver: On-demand instance (reliable)              │       │
│  │ Executors: 80% Spot/Preemptible + 20% On-demand   │       │
│  │                                                    │       │
│  │ Auto-scaling: Start with 50 executors              │       │
│  │ Scale up to 200 for peak, down to 0 when idle     │       │
│  │                                                    │       │
│  │ Instance type: Memory-optimized (r5.2xlarge)       │       │
│  │ Executor: 28GB mem, 4 cores each                   │       │
│  └───────────────────────┬───────────────────────────┘       │
│                          │                                    │
│  ┌───────────────────────▼───────────────────────────┐       │
│  │ Storage: S3/GCS (separate from compute!)          │       │
│  │                                                    │       │
│  │ Format: Delta Lake / Iceberg (Parquet + metadata) │       │
│  │ Compression: ZSTD (best ratio)                     │       │
│  │ Partitioning: date (daily granularity)             │       │
│  │ Z-Order: by most queried columns                   │       │
│  │                                                    │       │
│  │ Tiering: Hot (last 30 days) / Cold (S3 IA/Glacier)│       │
│  └───────────────────────────────────────────────────┘       │
│                                                               │
│  Cost optimization levers:                                   │
│  1. Spot instances: 60-70% cost savings                      │
│  2. Auto-scaling: Pay only during processing                 │
│  3. Serverless (EMR Serverless / Dataproc): Scale to zero    │
│  4. ZSTD compression: 50% storage reduction                  │
│  5. Columnar + pushdown: Read only needed data               │
│  6. Delta OPTIMIZE: Fewer files = fewer API calls            │
│  7. Graviton/ARM instances: 20% cheaper, same performance    │
│  8. Reserved capacity for baseline: 30-40% savings           │
│                                                               │
│  Estimated cost for 10 TB/day:                               │
│  Compute: ~50 r5.2xlarge × 2 hours × $0.15/hr = ~$15/run   │
│  (With spot: ~$5/run)                                        │
│  Storage: 10TB × $0.023/GB/month = ~$230/month              │
│  Total: ~$400-600/month for daily 10TB processing            │
└─────────────────────────────────────────────────────────────┘
```
