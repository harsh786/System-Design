# Apache Spark for ML Engineers

## Why Spark?

When your data doesn't fit on a single machine, you need distributed computing. Spark processes terabytes to petabytes across clusters while providing a familiar DataFrame API.

```
┌─────────────────────────────────────────────────────────────┐
│                    SPARK USE CASES IN ML                      │
├─────────────────────────────────────────────────────────────┤
│  • Feature engineering on billions of rows                   │
│  • Distributed model training (MLlib)                        │
│  • Large-scale data preprocessing                            │
│  • ETL for data lakes                                        │
│  • Real-time feature computation (Structured Streaming)      │
│  • A/B test analysis at scale                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Spark Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    SPARK APPLICATION                       │
├──────────────────────────────────────────────────────────┤
│                                                           │
│   ┌──────────────┐         ┌───────────────────┐        │
│   │    DRIVER    │         │  CLUSTER MANAGER  │        │
│   │  (SparkCtx)  │◄───────►│  (YARN/K8s/Mesos)│        │
│   └──────┬───────┘         └───────────────────┘        │
│          │                                               │
│          │ Tasks                                          │
│          ▼                                               │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│   │ EXECUTOR 1 │  │ EXECUTOR 2 │  │ EXECUTOR N │       │
│   │ ┌────────┐ │  │ ┌────────┐ │  │ ┌────────┐ │       │
│   │ │ Task 1 │ │  │ │ Task 3 │ │  │ │ Task 5 │ │       │
│   │ │ Task 2 │ │  │ │ Task 4 │ │  │ │ Task 6 │ │       │
│   │ └────────┘ │  │ └────────┘ │  │ └────────┘ │       │
│   │  [Cache]   │  │  [Cache]   │  │  [Cache]   │       │
│   └────────────┘  └────────────┘  └────────────┘       │
└──────────────────────────────────────────────────────────┘
```

**Key concepts:**
- **Driver**: Orchestrates the application, creates SparkContext
- **Executors**: JVM processes on worker nodes that run tasks
- **Tasks**: Smallest unit of work, one per partition
- **Stages**: Groups of tasks separated by shuffles
- **Jobs**: Triggered by actions (collect, save, count)

---

## RDDs → DataFrames → Datasets

```python
# Evolution of Spark APIs (use DataFrames for 99% of work)

# RDD (low-level, avoid unless necessary)
rdd = sc.parallelize([1, 2, 3, 4, 5])
rdd.map(lambda x: x * 2).filter(lambda x: x > 4).collect()

# DataFrame (preferred for Python/PySpark)
df = spark.read.parquet("s3://bucket/data/")
df.filter(df.age > 25).groupBy("city").agg(F.avg("salary"))

# Dataset (Scala/Java only, type-safe DataFrames)
# case class Person(name: String, age: Int)
# ds: Dataset[Person] = df.as[Person]
```

---

## PySpark DataFrame API

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Initialize
spark = SparkSession.builder \
    .appName("MLFeatureEngineering") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.shuffle.partitions", "200") \
    .getOrCreate()

# Read data
events = spark.read.parquet("s3://datalake/events/")
users = spark.read.parquet("s3://datalake/users/")

# Basic transformations
features = (
    events
    .filter(F.col("event_date") >= F.lit("2024-01-01"))
    .groupBy("user_id")
    .agg(
        F.count("*").alias("total_events"),
        F.countDistinct("session_id").alias("total_sessions"),
        F.sum(F.when(F.col("event_type") == "purchase", 1).otherwise(0)).alias("purchases"),
        F.avg("duration_seconds").alias("avg_duration"),
        F.collect_set("category").alias("categories_viewed"),
    )
)

# Window functions
window_7d = Window.partitionBy("user_id").orderBy("event_date").rangeBetween(-7 * 86400, 0)

events_with_features = events.withColumn(
    "rolling_7d_events", F.count("*").over(window_7d)
)

# Join
training_data = (
    users
    .join(features, on="user_id", how="left")
    .fillna(0, subset=["total_events", "purchases"])
    .withColumn("conversion_rate", F.col("purchases") / F.col("total_events"))
)

# Write
training_data.write \
    .mode("overwrite") \
    .partitionBy("signup_month") \
    .parquet("s3://datalake/ml/training_data/")
```

---

## Transformations vs Actions

```
┌────────────────────────────────────────────────────────┐
│  TRANSFORMATIONS (Lazy)     │  ACTIONS (Trigger exec)  │
├─────────────────────────────┼──────────────────────────┤
│  filter(), select()         │  count(), collect()      │
│  groupBy(), join()          │  show(), take()          │
│  withColumn(), drop()       │  write(), save()         │
│  union(), distinct()        │  foreach()               │
│  repartition()              │  toPandas()              │
└─────────────────────────────┴──────────────────────────┘

Nothing executes until an ACTION is called!
This enables Spark's query optimizer (Catalyst) to optimize the entire plan.
```

---

## Partitioning and Shuffling

```python
# Check partitions
df.rdd.getNumPartitions()  # Default: 200 for shuffles

# Repartition (causes shuffle - expensive)
df_repartitioned = df.repartition(100, "user_id")

# Coalesce (reduce partitions without full shuffle)
df_smaller = df.coalesce(10)

# Partition on write (critical for query performance)
df.write.partitionBy("date", "country").parquet("s3://output/")
```

### When Shuffles Happen
- `groupBy().agg()`
- `join()` (unless broadcast)
- `distinct()`
- `repartition()`
- `orderBy()` (global sort)

**Rule: Minimize shuffles. They are the #1 performance killer.**

---

## Spark MLlib

```python
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler, StringIndexer
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator

# Feature assembly
assembler = VectorAssembler(
    inputCols=["total_events", "purchases", "avg_duration", "days_since_signup"],
    outputCol="features_raw"
)

scaler = StandardScaler(inputCol="features_raw", outputCol="features")

# Model
gbt = GBTClassifier(
    labelCol="churned",
    featuresCol="features",
    maxDepth=5,
    maxIter=100
)

# Pipeline
pipeline = Pipeline(stages=[assembler, scaler, gbt])

# Train/test split
train, test = training_data.randomSplit([0.8, 0.2], seed=42)

# Fit
model = pipeline.fit(train)

# Evaluate
predictions = model.transform(test)
evaluator = BinaryClassificationEvaluator(labelCol="churned", metricName="areaUnderROC")
auc = evaluator.evaluate(predictions)
print(f"AUC: {auc:.4f}")
```

---

## Spark Structured Streaming

```python
# Read from Kafka
stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "broker:9092")
    .option("subscribe", "user_events")
    .load()
)

# Parse and process
from pyspark.sql.types import StructType, StringType, TimestampType

schema = StructType() \
    .add("user_id", StringType()) \
    .add("event_type", StringType()) \
    .add("timestamp", TimestampType())

events = (
    stream
    .select(F.from_json(F.col("value").cast("string"), schema).alias("data"))
    .select("data.*")
    .withWatermark("timestamp", "10 minutes")
    .groupBy(
        F.window("timestamp", "5 minutes"),
        "user_id"
    )
    .agg(F.count("*").alias("event_count"))
)

# Write to Delta Lake
query = (
    events.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "s3://checkpoints/events/")
    .start("s3://datalake/streaming_features/")
)
```

---

## Performance Tuning

### 1. Broadcast Joins (Small table < 10MB)
```python
from pyspark.sql.functions import broadcast

# Force broadcast for small dimension table
result = large_df.join(broadcast(small_df), on="key")
```

### 2. Caching
```python
# Cache frequently accessed DataFrame
df.cache()  # or df.persist(StorageLevel.MEMORY_AND_DISK)
df.count()  # Trigger materialization

# Unpersist when done
df.unpersist()
```

### 3. Adaptive Query Execution (AQE)
```python
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
```

### 4. Avoid Common Pitfalls
```python
# ❌ Collecting large data to driver
all_data = df.collect()  # OOM risk!

# ✅ Process distributed, collect only summaries
summary = df.groupBy("category").count().collect()

# ❌ Python UDFs (slow, serialization overhead)
@udf(returnType=StringType())
def slow_function(x):
    return x.upper()

# ✅ Use built-in functions or Pandas UDFs
df.withColumn("upper_name", F.upper(F.col("name")))

# ✅ Pandas UDF for complex logic (vectorized)
@F.pandas_udf(FloatType())
def fast_prediction(features: pd.Series) -> pd.Series:
    return model.predict(features)
```

### 5. Partition Strategy
```
┌──────────────────────────────────────────────────────────┐
│  Rule of Thumb for Partition Size:                        │
│  • Target: 128MB - 256MB per partition                   │
│  • Too few partitions → OOM, poor parallelism            │
│  • Too many partitions → scheduler overhead              │
│  • Formula: num_partitions = data_size / 128MB           │
└──────────────────────────────────────────────────────────┘
```

---

## Delta Lake Integration

```python
# Write as Delta table
df.write.format("delta").mode("overwrite").save("s3://lake/features/")

# Time travel
spark.read.format("delta").option("versionAsOf", 5).load("s3://lake/features/")

# MERGE (upsert) - critical for feature stores
from delta.tables import DeltaTable

delta_table = DeltaTable.forPath(spark, "s3://lake/features/")
delta_table.alias("target").merge(
    new_data.alias("source"),
    "target.user_id = source.user_id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

# Optimize and Z-order
spark.sql("OPTIMIZE delta.`s3://lake/features/` ZORDER BY (user_id)")
```

---

## Spark on Kubernetes

```yaml
# spark-app.yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: feature-engineering
spec:
  type: Python
  mode: cluster
  image: spark-ml:latest
  mainApplicationFile: s3://code/feature_pipeline.py
  sparkVersion: "3.5.0"
  driver:
    cores: 2
    memory: "4g"
  executor:
    cores: 4
    instances: 10
    memory: "8g"
  dynamicAllocation:
    enabled: true
    minExecutors: 5
    maxExecutors: 50
```

---

## Interview Questions

1. **What's the difference between transformations and actions?**
   - Transformations are lazy (build a plan); actions trigger execution.

2. **How does Spark handle data skew?**
   - Salting keys, AQE skew join, broadcast small side, custom partitioning.

3. **When would you use repartition vs coalesce?**
   - Repartition: increase/redistribute partitions (full shuffle). Coalesce: only reduce (no shuffle).

4. **Explain the Catalyst optimizer.**
   - Parses → Analyzes → Optimizes (rule + cost-based) → Physical plan generation.

5. **What's the difference between cache and persist?**
   - cache() = persist(MEMORY_AND_DISK). persist() allows choosing storage level.

6. **How do you handle late data in Structured Streaming?**
   - Watermarks define how late data can arrive; data beyond watermark is dropped.

7. **Why avoid Python UDFs? What's the alternative?**
   - Serialization overhead (JVM↔Python). Use built-in functions or Pandas UDFs (vectorized).

8. **What is a shuffle and why is it expensive?**
   - Data redistribution across executors via network. Involves disk I/O, serialization, network transfer.

9. **Explain narrow vs wide dependencies.**
   - Narrow: each parent partition maps to one child (map, filter). Wide: multiple children need same parent (groupBy, join) → shuffle.

10. **How does Delta Lake improve Spark workflows?**
    - ACID transactions, time travel, schema enforcement, MERGE/upsert, optimize+zorder.

---

## Cost Optimization

| Strategy | Savings |
|----------|---------|
| Spot/preemptible instances for executors | 60-80% |
| Right-size executor memory | 20-40% |
| Partition pruning (read less data) | Huge |
| Columnar formats (Parquet/ORC) | 50-90% I/O |
| Z-ordering for selective queries | 50-80% scan |
| Dynamic allocation | Variable |
| Cache intermediate results | Avoid recomputation |
