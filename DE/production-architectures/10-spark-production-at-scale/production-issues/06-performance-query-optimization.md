# Category 6: Performance & Query Optimization Issues (Issues 51-60)

> Query optimization issues are often invisible - jobs "work" but take 10-100x longer than necessary. Catalyst optimizer decisions silently make or break performance.

---

## Issue #51: Catalyst Choosing Wrong Join Strategy

**Frequency**: High  
**Severity**: High - 10-100x performance difference  
**Spark Component**: JoinSelection, Catalyst Optimizer

### Symptoms
```
# Small table (50MB) being sort-merge joined instead of broadcast
# OR large table (10GB) being broadcast → driver OOM
# Query plan shows unexpected join type
# Same query was fast yesterday, slow today (data grew past threshold)
```

### Root Cause
- Stale table statistics (data grew but stats not updated)
- Filter pushdown changes effective table size (optimizer can't predict)
- CBO disabled or missing column statistics
- Threshold settings too conservative or aggressive

### Solution
```python
# 1. Collect table and column statistics regularly
spark.sql("ANALYZE TABLE fact_orders COMPUTE STATISTICS")
spark.sql("ANALYZE TABLE fact_orders COMPUTE STATISTICS FOR ALL COLUMNS")
spark.sql("ANALYZE TABLE dim_products COMPUTE STATISTICS")

# 2. Enable Cost-Based Optimizer
spark.conf.set("spark.sql.cbo.enabled", "true")
spark.conf.set("spark.sql.cbo.joinReorder.enabled", "true")
spark.conf.set("spark.sql.cbo.planStats.enabled", "true")

# 3. Use join hints when you know better than optimizer
# Force broadcast (you know dim table is small):
result = fact.join(broadcast(dim), "product_id")

# Force sort-merge (both tables are large):
result = df1.join(df2.hint("merge"), "key")

# Force shuffle hash (medium table, good for highly filtered):
result = df1.join(df2.hint("shuffle_hash"), "key")

# 4. Let AQE correct at runtime
spark.conf.set("spark.sql.adaptive.enabled", "true")
# AQE converts SortMergeJoin to BroadcastHashJoin at runtime
# if shuffle stage reveals one side is actually small

# 5. Inspect the plan BEFORE execution
result.explain(mode="cost")  # Shows estimated costs
result.explain(mode="formatted")  # Shows chosen strategies

# 6. For CI/CD: assert expected join strategies
physical_plan = result._jdf.queryExecution().executedPlan().toString()
assert "BroadcastHashJoin" in physical_plan or "BroadcastNestedLoopJoin" in physical_plan
```

---

## Issue #52: Unnecessary Cartesian Product / Cross Join

**Frequency**: Medium  
**Severity**: Critical - exponential data explosion  
**Spark Component**: CartesianProductExec, BroadcastNestedLoopJoinExec

### Symptoms
```
org.apache.spark.sql.AnalysisException: 
  Detected implicit cartesian product for INNER join between logical plans.
# OR job running forever: 1M × 1M = 1 TRILLION rows processing
# OR unexpected massive data output (10TB from 1GB inputs)
```

### Root Cause
- Missing join condition (implicit cross join)
- Non-equi join without proper optimization
- Complex WHERE instead of JOIN ON
- Theta joins (inequality conditions only)
- DataFrame API: `.join(df2)` without condition

### Solution
```python
# 1. Always specify join condition explicitly
# BAD (cartesian!):
result = df1.join(df2)  # No condition = cross join!

# GOOD:
result = df1.join(df2, "key")
result = df1.join(df2, df1.key == df2.key)

# 2. Enable cross join detection (fails fast)
spark.conf.set("spark.sql.crossJoin.enabled", "false")  # Default: fails on cartesian

# 3. For legitimate cross joins, be explicit and limit
result = df1.crossJoin(df2)  # Explicit intent
# But first: ensure both sides are SMALL
assert df1.count() * df2.count() < 100_000_000, "Cross join too large!"

# 4. Replace cross join with broadcast + filter
# Instead of: SELECT * FROM a CROSS JOIN b WHERE a.x BETWEEN b.lo AND b.hi
# Use: broadcast smaller side with range condition
result = df_large.join(
    broadcast(df_ranges),
    (F.col("value").between(F.col("range_low"), F.col("range_high")))
)

# 5. For inequality joins: use range bucketing
# Instead of cross join + filter on ranges,
# bucket both sides into ranges and equi-join on bucket
df1_bucketed = df1.withColumn("bucket", F.floor(F.col("value") / 1000))
df2_bucketed = df2.withColumn("bucket", F.floor(F.col("value") / 1000))
# Join on bucket first (equi-join), then filter within bucket
```

---

## Issue #53: Whole-Stage Codegen Disabled (CPU Bottleneck)

**Frequency**: Low-Medium  
**Severity**: Medium - 2-10x slower CPU utilization  
**Spark Component**: WholeStageCodegenExec, Tungsten

### Symptoms
```
# From plan: no * prefix on operators (codegen not applied)
# Expected: *(1) Filter, *(1) Project
# Actual: Filter, Project (no asterisk = no codegen)
# CPU utilization much higher than expected for simple operations
# Single-threaded interpretation instead of compiled code
```

### Root Cause
- Codegen disabled due to too many fields (> 100 columns in expression)
- Complex UDFs break codegen chain
- Expression exceeds codegen height limit
- Fallback to interpreted mode silently

### Solution
```python
# 1. Ensure codegen is enabled
spark.conf.set("spark.sql.codegen.wholeStage", "true")  # Default true
spark.conf.set("spark.sql.codegen.fallback", "true")     # Fallback if codegen fails

# 2. Increase codegen limits for wide tables
spark.conf.set("spark.sql.codegen.maxFields", "200")  # Default 100
spark.conf.set("spark.sql.codegen.hugeMethodLimit", "65536")

# 3. Check codegen status in plan
df.explain(mode="codegen")  # Shows generated Java code
# OR look for asterisk prefix: *(1) indicates codegen active

# 4. Avoid patterns that break codegen
# BAD: UDF in the middle of codegen pipeline
df.select(F.col("a") + 1, my_udf(F.col("b")), F.col("c") * 2)
# The UDF breaks the codegen chain for the whole stage

# GOOD: Separate UDF stage
df_no_udf = df.select(F.col("a") + 1, F.col("c") * 2)  # Codegen applies
df_final = df_no_udf.withColumn("b_result", my_udf(F.col("b")))

# 5. For very wide tables (500+ columns):
# Select only needed columns before operations
df.select(needed_cols).filter(...).groupBy(...)  # Codegen works on fewer fields
```

---

## Issue #54: UDF Performance Bottleneck

**Frequency**: Very High  
**Severity**: Medium-High - 10-100x slower than built-in functions  
**Spark Component**: PythonUDFRunner, BatchEvalPythonExec

### Symptoms
```
# PySpark UDF stage takes 10x longer than equivalent SQL/built-in function
# Tasks show high "Python worker time"
# CPU mostly idle on executors (waiting for Python)
# Serialization/deserialization overhead visible in metrics
```

### Root Cause
- Row-at-a-time Python UDF: data serialized to Python per row
- JVM ↔ Python serialization overhead (Pickle/Arrow)
- Python GIL limiting parallelism within UDF
- UDF prevents Catalyst optimization (opaque function)
- No predicate pushdown, no column pruning through UDF

### Solution
```python
# Priority 1: Replace UDF with built-in functions (BEST)
# BAD (10x slower):
@udf(StringType())
def extract_domain(email):
    return email.split("@")[1] if "@" in email else None

# GOOD (native, vectorized, 10-100x faster):
df.withColumn("domain", F.split(F.col("email"), "@")[1])

# Priority 2: Use Pandas UDF (vectorized) if built-in not possible
@F.pandas_udf("string")
def extract_domain_vec(emails: pd.Series) -> pd.Series:
    return emails.str.split("@").str[1]
# 10-50x faster than row-at-a-time UDF (Arrow batching)

# Priority 3: Use mapInPandas for complex logic
def process_partition(iterator):
    for batch in iterator:
        # Operate on pandas DataFrame (vectorized)
        batch["domain"] = batch["email"].str.split("@").str[1]
        yield batch

result = df.mapInPandas(process_partition, schema=df.schema)

# Priority 4: If must use row UDF, at least make it Scala
# Scala UDFs run in JVM (no serialization overhead)
# Register from Scala JAR:
# spark.udf.register("fast_udf", ...)

# Common UDF replacements:
# String operations → F.regexp_extract, F.split, F.substring, F.concat
# Date operations → F.date_add, F.datediff, F.date_format
# Conditionals → F.when().otherwise(), F.coalesce
# JSON → F.from_json, F.get_json_object, F.json_tuple
# Array → F.array_contains, F.explode, F.transform
# Math → F.abs, F.ceil, F.floor, F.pow, F.log
```

---

## Issue #55: Repeated Computation (Missing Cache/Persist)

**Frequency**: High  
**Severity**: Medium - redundant work, 2-5x slower  
**Spark Component**: DAGScheduler, InMemoryRelation

### Symptoms
```
# Same large DataFrame recomputed 3 times in job
# Spark UI: identical stages appearing multiple times
# Reading same source table 3 times from S3
# Linear pipeline but taking 3x expected time
```

### Root Cause
- Spark is lazy: each action triggers full recomputation from source
- Same DataFrame used in multiple branches without caching
- No persistence between actions on shared intermediate result
- Developer unaware of lazy evaluation model

### Solution
```python
# PROBLEM: df_enriched computed 3 times!
df_enriched = df.join(dim1, "key1").join(dim2, "key2").filter(...)
report_a = df_enriched.groupBy("cat1").count()  # Computes df_enriched
report_b = df_enriched.groupBy("cat2").sum()    # Computes AGAIN
report_c = df_enriched.filter(...).count()      # Computes AGAIN!

# SOLUTION: Cache the shared intermediate
df_enriched = df.join(dim1, "key1").join(dim2, "key2").filter(...)
df_enriched.cache()  # OR .persist(StorageLevel.MEMORY_AND_DISK)
df_enriched.count()  # Trigger materialization

report_a = df_enriched.groupBy("cat1").count()   # Uses cache
report_b = df_enriched.groupBy("cat2").sum()     # Uses cache
report_c = df_enriched.filter(...).count()       # Uses cache

# ALWAYS unpersist when done
df_enriched.unpersist()

# Choose storage level based on size:
from pyspark import StorageLevel

# Fits in memory: fastest
df.persist(StorageLevel.MEMORY_ONLY)

# Might not fit: spill to disk (avoids recomputation)
df.persist(StorageLevel.MEMORY_AND_DISK)

# Memory pressure: store serialized (2x less memory, slightly slower)
df.persist(StorageLevel.MEMORY_AND_DISK_SER)

# Very large + reused moderately: disk only
df.persist(StorageLevel.DISK_ONLY)

# ANTI-PATTERN: Don't cache everything!
# Only cache if: (reuse_count - 1) * recompute_cost > cache_cost
# Don't cache: small DataFrames, one-time-use DataFrames, streaming
```

---

## Issue #56: Suboptimal Join Order in Multi-Table Queries

**Frequency**: Medium  
**Severity**: Medium-High - order of magnitude slower  
**Spark Component**: CBO JoinReorder, ReorderJoin

### Symptoms
```
# Query joins 5 tables: A(1B), B(100M), C(10M), D(1K), E(500)
# Spark joins in code order: A⋈B⋈C⋈D⋈E
# Optimal would be: (A⋈D)⋈(B⋈E)⋈C  (broadcast small tables first)
# Result: intermediate results explode in size
```

### Root Cause
- Without CBO, Spark joins in the order written in code
- Missing statistics prevents cost estimation
- Star schema queries not optimized for dimension broadcast
- Left-deep join tree instead of bushy tree

### Solution
```python
# 1. Enable join reordering
spark.conf.set("spark.sql.cbo.enabled", "true")
spark.conf.set("spark.sql.cbo.joinReorder.enabled", "true")
spark.conf.set("spark.sql.cbo.joinReorder.dp.star.filter", "true")
spark.conf.set("spark.sql.cbo.joinReorder.dp.threshold", "12")  # Max tables to reorder

# 2. Collect statistics for all join tables
for table in ["fact_orders", "dim_products", "dim_customers", "dim_dates", "dim_stores"]:
    spark.sql(f"ANALYZE TABLE {table} COMPUTE STATISTICS FOR ALL COLUMNS")

# 3. Manual ordering (when you know the data)
# Start with most selective joins (reduce data earliest)
result = (
    fact_orders
    .join(broadcast(dim_dates.filter("year = 2024")), "date_key")  # Filter early
    .join(broadcast(dim_stores.filter("region = 'US'")), "store_key")  # Broadcast small
    .join(dim_customers, "customer_key")  # Larger dim, sort-merge
    .join(dim_products, "product_key")  # Larger dim, sort-merge
)

# 4. Force join ordering with DataFrame API
# The order you write determines execution order (without CBO)
# Always: small/filtered → large
# Always: broadcast small dims first to reduce fact table size

# 5. Use AQE for runtime optimization
spark.conf.set("spark.sql.adaptive.enabled", "true")
# AQE will convert to broadcast after seeing actual shuffle sizes
```

---

## Issue #57: Catalyst Rule Explosion (Optimizer Timeout)

**Frequency**: Low-Medium  
**Severity**: High - query planning takes minutes  
**Spark Component**: Catalyst Optimizer, Rule Batches

### Symptoms
```
# Query takes 5 minutes to plan before any execution starts
# WARN Optimizer: Plan exceeds max iterations (100)
# Very complex query (50+ columns, 10+ joins, nested subqueries)
# Plan generation allocates GBs of memory
# Analyzer/Optimizer batch taking unusually long
```

### Root Cause
- Exponential rule application on complex plans
- Many correlated subqueries creating combinatorial explosion
- Deeply nested CASE WHEN expressions
- View upon view upon view creating massive logical plans
- Too many optimizer rules enabled

### Solution
```python
# 1. Increase optimizer iteration limits
spark.conf.set("spark.sql.optimizer.maxIterations", "200")  # Default 100

# 2. Simplify query structure
# BAD: deeply nested subqueries
result = spark.sql("""
    SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM ...)))
""")

# GOOD: Break into intermediate tables/CTEs
spark.sql("CREATE TEMP VIEW step1 AS SELECT ...")
spark.sql("CREATE TEMP VIEW step2 AS SELECT ... FROM step1")
result = spark.sql("SELECT ... FROM step2")

# 3. Materialize intermediate results for complex pipelines
intermediate = complex_query_part1.persist()
intermediate.count()  # Force materialization
final = intermediate.join(...)  # Simpler plan for optimizer

# 4. Disable specific expensive rules if not needed
spark.conf.set("spark.sql.optimizer.excludedRules",
    "org.apache.spark.sql.catalyst.optimizer.PushDownPredicates,"
    "org.apache.spark.sql.catalyst.optimizer.ColumnPruning")
# CAUTION: Only disable rules you're sure aren't needed

# 5. Reduce view nesting depth
# Instead of 5 levels of views, flatten into 1-2 levels
# Each view level multiplies optimizer work

# 6. Monitor planning time
import time
start = time.time()
result.explain()  # Force planning
planning_ms = (time.time() - start) * 1000
assert planning_ms < 30000, f"Planning took {planning_ms}ms - too complex!"
```

---

## Issue #58: Window Functions Causing Full Data Shuffle

**Frequency**: High  
**Severity**: Medium - unexpected shuffle  
**Spark Component**: WindowExec, WindowFunctionFrame

### Symptoms
```
# Window function triggers full shuffle even for simple row_number()
# PARTITION BY high-cardinality column → huge shuffle
# Multiple window functions with different PARTITION BY → multiple shuffles
# Window followed by filter doesn't push filter before window
```

### Root Cause
- Each PARTITION BY clause requires data co-located by that key
- Multiple window functions with different partition keys = multiple shuffles
- Window over entire dataset (no PARTITION BY) = single partition = single task!
- Catalyst can't push filters through windows

### Solution
```python
# 1. Combine window functions with same PARTITION BY
# BAD (2 shuffles - different partition keys):
w1 = Window.partitionBy("user_id").orderBy("ts")
w2 = Window.partitionBy("merchant_id").orderBy("ts")
df.withColumn("user_rank", F.row_number().over(w1)) \
  .withColumn("merchant_rank", F.row_number().over(w2))

# GOOD (1 shuffle - same partition key):
w = Window.partitionBy("user_id").orderBy("ts")
df.withColumn("rank", F.row_number().over(w)) \
  .withColumn("running_total", F.sum("amount").over(w))

# 2. Filter BEFORE window function (reduce data before shuffle)
# BAD:
result = df.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
# Processes ALL rows through window, then filters

# BETTER: Pre-filter when possible
df_filtered = df.filter(F.col("status") == "active")  # Reduce data first
result = df_filtered.withColumn("rn", F.row_number().over(w)).filter("rn = 1")

# 3. For top-N per group, consider alternatives to window:
# Instead of row_number + filter:
# Use groupBy + struct trick (faster for top-1):
result = df.groupBy("user_id").agg(
    F.max(F.struct("ts", "amount", "merchant")).alias("latest")
).select("user_id", "latest.*")

# 4. NEVER use window without PARTITION BY on large data
# BAD (all data to single partition!):
w_no_partition = Window.orderBy("ts")
df.withColumn("global_rank", F.row_number().over(w_no_partition))  # 1 task for 1B rows!

# GOOD: Add artificial partition to parallelize
df.withColumn("bucket", F.floor(F.col("ts").cast("long") / 3600)) \
  .withColumn("rank_in_bucket", F.row_number().over(
      Window.partitionBy("bucket").orderBy("ts")))
```

---

## Issue #59: Explain Plan Not Matching Actual Execution (AQE Changing Plans)

**Frequency**: Medium  
**Severity**: Low-Medium (confusion more than bug)  
**Spark Component**: AdaptiveSparkPlanExec, AQE

### Symptoms
```
# explain() shows SortMergeJoin but actual execution used BroadcastHashJoin
# explain() shows 2000 partitions but actual uses 500 (AQE coalesced)
# Performance tuning based on explain() doesn't match reality
# Spark UI shows different plan than .explain()
```

### Root Cause
- AQE re-plans at runtime based on actual statistics from shuffle stages
- `explain()` shows the INITIAL plan (before AQE)
- Runtime plan visible in Spark UI SQL tab (after AQE)
- AQE can: coalesce partitions, change join strategy, handle skew

### Solution
```python
# 1. Use explain with AQE mode
df.explain(mode="formatted")  # Shows initial plan
# For actual plan: check Spark UI → SQL tab → query details

# 2. Understand what AQE can change at runtime:
# - SortMergeJoin → BroadcastHashJoin (if runtime size < threshold)
# - 2000 partitions → 500 partitions (coalesce small partitions)
# - Skewed partition → split into multiple tasks

# 3. Force a specific plan (bypass AQE decisions):
# If AQE makes wrong choice:
spark.conf.set("spark.sql.adaptive.forceApply", "false")  # Disable AQE for debugging
# OR use hints to force specific behavior:
df1.join(df2.hint("broadcast"), "key")  # AQE won't override explicit hints

# 4. Log actual runtime plan
# After execution:
print(result._jdf.queryExecution().executedPlan().toString())
# This shows the final plan INCLUDING AQE changes

# 5. Trust Spark UI over .explain() for actual performance analysis
# Spark UI → SQL → click on query → shows actual runtime plan with metrics
# Each operator shows: rows output, time, data size
```

---

## Issue #60: Inefficient Data Serialization Between Stages

**Frequency**: Medium  
**Severity**: Medium - CPU overhead, GC pressure  
**Spark Component**: SerializerManager, KryoSerializer, JavaSerializer

### Symptoms
```
# High CPU usage during serialization/deserialization
# "Serialization time" significant in task metrics
# Task GC time high due to object creation during deser
# Using Java serialization (very slow, large payloads)
```

### Root Cause
- Default Java serialization is 10x slower than Kryo
- Custom objects not registered with Kryo
- UDFs returning complex objects requiring expensive serialization
- Large closure serialization (accidentally capturing driver objects)

### Solution
```python
# 1. Use Kryo serialization (2-10x faster)
spark.conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
spark.conf.set("spark.kryoserializer.buffer.max", "1024m")
spark.conf.set("spark.kryoserializer.buffer", "64k")

# 2. Register custom classes with Kryo
spark.conf.set("spark.kryo.registrator", "com.mycompany.MyKryoRegistrator")
# OR
spark.conf.set("spark.kryo.classesToRegister", 
    "com.mycompany.MyClass,com.mycompany.MyOtherClass")
spark.conf.set("spark.kryo.registrationRequired", "false")  # Warn but don't fail

# 3. Avoid closure serialization issues
# BAD (captures entire class in closure):
class Processor:
    def __init__(self):
        self.large_model = load_model()  # 2GB object in closure!
    def process(self, df):
        return df.filter(lambda row: self.large_model.predict(row))

# GOOD (use broadcast variable):
model_broadcast = spark.sparkContext.broadcast(load_model())
def predict(row):
    return model_broadcast.value.predict(row)

# 4. Use DataFrame API (avoids serialization entirely for SQL operations)
# DataFrame operations use Tungsten binary format (no Java serialization)
# Only RDD operations and UDFs trigger Java/Kryo serialization

# 5. For inter-stage data: use Arrow format
spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
spark.conf.set("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")

# 6. Monitor serialization overhead
# Spark UI → Tasks → "Result Serialization Time" and "Task Deserialization Time"
# If > 10% of task time → serialization is bottleneck
```

---

## Summary: Performance & Query Optimization Decision Tree

```
Query performance issue
├── Wrong execution plan chosen
│   ├── Wrong join strategy → Issue #51 (CBO, hints, AQE)
│   ├── Cartesian product → Issue #52 (missing join condition)
│   ├── Bad join order → Issue #56 (CBO join reorder)
│   └── Plan doesn't match execution → Issue #59 (AQE runtime changes)
├── CPU bottleneck
│   ├── No codegen (interpreted) → Issue #53 (enable, reduce fields)
│   ├── Slow UDFs → Issue #54 (replace with built-in, vectorize)
│   └── Serialization overhead → Issue #60 (Kryo, Arrow)
├── Redundant work
│   ├── Recomputing same DataFrame → Issue #55 (cache/persist)
│   └── Unnecessary shuffle from window → Issue #58 (combine windows)
└── Planning overhead
    └── Complex query planning slow → Issue #57 (simplify, materialize)
```
