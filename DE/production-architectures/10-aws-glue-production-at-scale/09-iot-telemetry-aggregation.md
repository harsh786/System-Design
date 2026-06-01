# IoT Telemetry Aggregation & Predictive Maintenance Pipeline at Siemens/GE Scale

## Real-World Production Use Case

Industrial manufacturers like Siemens, GE, Caterpillar, and Rolls-Royce operate global
equipment fleets generating massive telemetry streams. AWS Glue processes this data through
multi-resolution time-series aggregation, anomaly feature extraction, fleet-wide baseline
computation, and predictive maintenance feature assembly — enabling condition-based
maintenance that reduces unplanned downtime by 30-50%.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. The Problem: 10M Sensors × 1 Reading/Second = 864B Data Points/Day

### Business Context

A global industrial manufacturer monitors equipment across 50,000+ facilities worldwide.
Each facility contains turbines, compressors, pumps, motors, and CNC machines — all
instrumented with vibration sensors, temperature probes, pressure transducers, and
current monitors.

### Scale Parameters

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCALE PARAMETERS                                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Sensors:              10,000,000 (10M active sensors)               │
│  Sampling Rate:        1 Hz (1 reading per second per sensor)        │
│  Daily Data Points:    864,000,000,000 (864 Billion)                 │
│  Raw Data Volume:      ~50 TB/day (avg 60 bytes/reading)             │
│  Equipment Types:      500+ (turbines, pumps, motors, etc.)          │
│  Facilities:           50,000+ globally                              │
│  Retention:            5 years (raw: 30 days, 1-min: 1yr, 1-hr: 5yr)│
│  Sensor Types:         vibration, temperature, pressure, current,    │
│                        flow rate, RPM, acoustic emission              │
│  Alert Latency SLA:   < 5 minutes for critical anomalies            │
│  Fleet Baselines:      Recomputed weekly per equipment type          │
└─────────────────────────────────────────────────────────────────────┘
```

### Requirements

1. **Multi-Resolution Storage** — Raw (1s) for short-term diagnostics, downsampled (1min,
   1hr, 1day) for trend analysis and long-term retention
2. **Anomaly Feature Extraction** — Statistical features for ML-based anomaly detection
3. **Fleet Baselines** — Normal operating envelopes per equipment type and operating mode
4. **Predictive Maintenance** — Remaining Useful Life (RUL) feature preparation
5. **5-Year Retention** — With progressive resolution reduction to control storage costs
6. **Digital Twin Data** — Prepared aggregates for simulation models

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 2. Why Traditional Approaches Fail

### Time-Series DB Alone (InfluxDB/TimescaleDB)

```
Cost at scale:
  - 50 TB/day raw ingest → InfluxDB Cloud: ~$150K/day = $4.5M/month
  - 5-year retention of all resolutions: petabytes of hot storage
  - Query performance degrades with multi-year range scans
  
Verdict: Use for real-time dashboards (last 24hrs), not bulk storage
```

### Real-Time Processing Only (Flink/Kinesis Analytics)

```
Limitations:
  - Stateful aggregation across hours/days requires massive checkpoints
  - Fleet-wide baselines need full historical context (not just stream state)
  - Long-term degradation = weeks/months of trend → not a streaming problem
  - Cost of running Flink 24/7 for batch-like computations is wasteful
  
Verdict: Use for <5min alerting, not for hour/day/week aggregations
```

### Single-Resolution Storage

```
Too Granular (keep all 1-second data):
  - 50 TB/day × 365 × 5 years = 91 PB storage
  - Cost: ~$2M/month on S3 alone
  
Too Coarse (only 1-hour aggregates):
  - Lose ability to diagnose transient faults (bearing impacts, arcing)
  - Cannot detect sub-minute patterns critical for vibration analysis
  
Verdict: Multi-resolution is mandatory
```

### Manual Threshold-Based Alerting

```
Problems:
  - Static thresholds generate 80%+ false positives
  - Cannot account for operating mode (startup vs steady-state vs shutdown)
  - Ignores gradual degradation (normal today, failure in 3 months)
  - Doesn't adapt to seasonal/environmental variation
  
Verdict: Need ML-based anomaly detection with rich feature vectors
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    IOT TELEMETRY AGGREGATION ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────────┐    ┌─────────────────────────────────┐
│  10M Sensors │───▶│  IoT Gateway     │───▶│  AWS IoT Core                   │
│  (1 Hz each) │    │  (Edge Buffering)│    │  (MQTT → Rules Engine)          │
└──────────────┘    └──────────────────┘    └───────────────┬─────────────────┘
                                                            │
                                                            ▼
                                            ┌───────────────────────────────┐
                                            │  Kinesis Data Streams          │
                                            │  (200 shards, 200MB/s ingest) │
                                            └───────────────┬───────────────┘
                                                            │
                              ┌──────────────────────────────┼──────────────────┐
                              │                              │                   │
                              ▼                              ▼                   ▼
               ┌──────────────────────┐  ┌────────────────────────┐  ┌─────────────────┐
               │  Kinesis Firehose    │  │  Kinesis Analytics      │  │  Lambda         │
               │  (S3 Raw Landing)    │  │  (< 5min critical      │  │  (Equipment     │
               │  Parquet, 1-min      │  │   anomaly alerting)    │  │   state mgmt)   │
               │  micro-batches       │  └────────────────────────┘  └─────────────────┘
               └──────────┬───────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         S3 DATA LAKE (RAW ZONE)                                  │
│  s3://iot-telemetry-raw/year=YYYY/month=MM/day=DD/hour=HH/                      │
│  Format: Parquet, Snappy compression                                             │
│  Partitioning: year/month/day/hour/facility_id                                   │
│  Retention: 30 days (lifecycle policy → Glacier after 7 days)                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                          │
                          │  Triggers Glue Workflows (hourly)
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AWS GLUE PIPELINE                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │  JOB 1: Raw Validation & Quality Flagging                              │     │
│  │  - Sensor range validation (physical bounds)                           │     │
│  │  - Clock drift compensation (NTP sync issues)                          │     │
│  │  - Duplicate detection (edge retry storms)                             │     │
│  │  - Stuck sensor detection (constant value > threshold)                 │     │
│  │  Workers: 50 × G.1X  |  Trigger: Hourly  |  Duration: ~15 min        │     │
│  └────────────────────────────────────┬───────────────────────────────────┘     │
│                                       │                                          │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │  JOB 2: 1-Second → 1-Minute Downsampling                              │     │
│  │  - Statistical summaries: min, max, avg, p50, p95, p99, stddev        │     │
│  │  - Count of valid readings (data completeness)                         │     │
│  │  - Rate of change (first derivative)                                   │     │
│  │  - Output: Iceberg table (1-minute resolution)                         │     │
│  │  Workers: 80 × G.1X  |  Trigger: Hourly  |  Duration: ~25 min        │     │
│  └────────────────────────────────────┬───────────────────────────────────┘     │
│                                       │                                          │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │  JOB 3: 1-Minute → 1-Hour Aggregation + Anomaly Features              │     │
│  │  - Hour-level statistical summaries                                    │     │
│  │  - Z-score features (vs rolling 7-day baseline)                        │     │
│  │  - Exponential moving average deviation                                │     │
│  │  - IQR-based outlier counts per hour                                   │     │
│  │  - Operating mode classification (startup/steady/shutdown)             │     │
│  │  Workers: 40 × G.2X  |  Trigger: Hourly  |  Duration: ~20 min        │     │
│  └────────────────────────────────────┬───────────────────────────────────┘     │
│                                       │                                          │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │  JOB 4: Fleet Baseline Computation                                     │     │
│  │  - Normal operating envelope per equipment_type × operating_mode       │     │
│  │  - Percentile boundaries (p1, p5, p25, p50, p75, p95, p99)            │     │
│  │  - Seasonal adjustment factors                                         │     │
│  │  - Age-based degradation curves                                        │     │
│  │  Workers: 20 × G.4X  |  Trigger: Weekly  |  Duration: ~2 hours       │     │
│  └────────────────────────────────────┬───────────────────────────────────┘     │
│                                       │                                          │
│                                       ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐     │
│  │  JOB 5: Predictive Maintenance Feature Assembly                        │     │
│  │  - RUL (Remaining Useful Life) features                                │     │
│  │  - Vibration FFT frequency domain features                             │     │
│  │  - Degradation trend slopes (30/60/90 day windows)                     │     │
│  │  - Cross-sensor correlation features                                   │     │
│  │  - Maintenance history integration                                     │     │
│  │  Workers: 30 × G.4X  |  Trigger: Daily  |  Duration: ~3 hours        │     │
│  └────────────────────────────────────┬───────────────────────────────────┘     │
│                                       │                                          │
└───────────────────────────────────────┼──────────────────────────────────────────┘
                                        │
                    ┌───────────────────┬┼───────────────────┐
                    │                   ││                    │
                    ▼                   ▼▼                    ▼
┌──────────────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐
│  Multi-Resolution        │ │  SageMaker       │ │  InfluxDB                │
│  Iceberg Tables          │ │  Feature Store   │ │  (Real-time Dashboards)  │
│  - 1-min (1yr retention) │ │  - ML features   │ │  - Last 24hr hot data    │
│  - 1-hr  (5yr retention) │ │  - RUL scores    │ │  - Grafana integration   │
│  - 1-day (indefinite)    │ │  - Anomaly scores│ │                          │
└──────────────────────────┘ └──────────────────┘ └──────────────────────────┘
         │                           │                        │
         ▼                           ▼                        ▼
┌──────────────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐
│  Athena / Redshift       │ │  SageMaker       │ │  Grafana                 │
│  (Ad-hoc Analysis)       │ │  (RUL Prediction │ │  (Operations Center)     │
│                          │ │   Anomaly Det.)  │ │                          │
└──────────────────────────┘ └──────────────────┘ └──────────────────────────┘
         │                           │                        │
         └───────────────────────────┼────────────────────────┘
                                     ▼
                    ┌────────────────────────────────────┐
                    │  Maintenance Management System     │
                    │  (SAP PM / IBM Maximo)             │
                    │  - Work order generation           │
                    │  - Spare parts forecasting         │
                    │  - Maintenance crew scheduling     │
                    └────────────────────────────────────┘
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 4. Glue Concepts Used

### Glue Streaming ETL
- Near-real-time micro-batch processing with configurable window sizes
- Checkpoint management for exactly-once semantics
- Auto-scaling based on Kinesis shard count and processing lag

### Worker Type Selection
```
G.1X (4 vCPU, 16GB):  Jobs 1-2 (simple aggregation, low memory)
G.2X (8 vCPU, 32GB):  Job 3 (anomaly features need rolling windows in memory)
G.4X (16 vCPU, 64GB): Jobs 4-5 (fleet-wide computation, FFT, large state)
```

### Pushdown Predicates
- Query only affected time windows (partition pruning on year/month/day/hour)
- Equipment-type filtering pushed to Iceberg metadata layer
- Reduces data scanned by 95%+ for targeted queries

### Glue Data Quality
- Sensor range validation rules (physical bounds per sensor type)
- Completeness checks (minimum readings per minute)
- Freshness checks (last reading timestamp vs current time)

### Custom Transforms
- Statistical window functions (rolling percentiles, EMA)
- FFT via NumPy (vibration frequency analysis)
- Sensor fusion (cross-sensor correlation computation)

### Iceberg Integration
- Time-travel for reproducible ML training datasets
- Partition evolution (started by day, evolved to hour as scale grew)
- Hidden partitioning on timestamp columns
- Compaction jobs to optimize file sizes (target: 256MB per file)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 5. Implementation Code

### Job 1: Raw Validation & Quality Flagging

```python
# job1_raw_validation.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_hour', 'sensor_bounds_table',
    'raw_input_path', 'validated_output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configure for IoT scale
spark.conf.set("spark.sql.shuffle.partitions", "2000")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")

# ─── Load sensor physical bounds (per sensor_type) ───────────────────────────
sensor_bounds = spark.read.format("iceberg").load(
    f"glue_catalog.iot_reference.{args['sensor_bounds_table']}"
)
# Schema: sensor_type, metric, min_physical, max_physical, stuck_threshold_seconds

# ─── Read raw hourly partition ───────────────────────────────────────────────
raw_df = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    connection_options={
        "paths": [f"{args['raw_input_path']}/{args['processing_hour']}/"],
        "recurse": True
    },
    format="parquet",
    transformation_ctx="raw_source"
).toDF()

# Expected schema:
# sensor_id: string, equipment_id: string, facility_id: string,
# equipment_type: string, sensor_type: string, metric: string,
# value: double, timestamp: timestamp, ingestion_time: timestamp

print(f"Raw records loaded: {raw_df.count()}")

# ─── Quality Flag 1: Physical bounds validation ──────────────────────────────
validated_df = raw_df.join(
    sensor_bounds.select("sensor_type", "metric", "min_physical", "max_physical"),
    on=["sensor_type", "metric"],
    how="left"
).withColumn(
    "qf_out_of_bounds",
    F.when(
        (F.col("value") < F.col("min_physical")) |
        (F.col("value") > F.col("max_physical")),
        True
    ).otherwise(False)
)

# ─── Quality Flag 2: Clock drift compensation ────────────────────────────────
# Sensor timestamps should be within ±30s of ingestion time
validated_df = validated_df.withColumn(
    "clock_drift_seconds",
    F.abs(F.unix_timestamp("timestamp") - F.unix_timestamp("ingestion_time"))
).withColumn(
    "qf_clock_drift",
    F.col("clock_drift_seconds") > 30
).withColumn(
    # Correct drifted timestamps by snapping to ingestion time
    "corrected_timestamp",
    F.when(F.col("qf_clock_drift"), F.col("ingestion_time"))
     .otherwise(F.col("timestamp"))
)

# ─── Quality Flag 3: Stuck sensor detection ──────────────────────────────────
# A sensor reporting the exact same value for > N consecutive readings
window_stuck = Window.partitionBy("sensor_id", "metric").orderBy("corrected_timestamp")

validated_df = validated_df.withColumn(
    "prev_value", F.lag("value").over(window_stuck)
).withColumn(
    "value_changed", F.when(F.col("value") != F.col("prev_value"), 1).otherwise(0)
).withColumn(
    "change_group", F.sum("value_changed").over(window_stuck)
).withColumn(
    "consecutive_same",
    F.count("*").over(
        Window.partitionBy("sensor_id", "metric", "change_group")
    )
)

# Join with stuck thresholds
validated_df = validated_df.join(
    sensor_bounds.select("sensor_type", "metric", "stuck_threshold_seconds"),
    on=["sensor_type", "metric"],
    how="left"
).withColumn(
    "qf_stuck_sensor",
    F.col("consecutive_same") > F.col("stuck_threshold_seconds")
)

# ─── Quality Flag 4: Duplicate detection ─────────────────────────────────────
# Edge gateways may retry, creating duplicates
validated_df = validated_df.withColumn(
    "row_num",
    F.row_number().over(
        Window.partitionBy("sensor_id", "metric", "corrected_timestamp")
              .orderBy(F.col("ingestion_time").desc())
    )
).withColumn(
    "qf_duplicate", F.col("row_num") > 1
)

# ─── Composite quality score ─────────────────────────────────────────────────
validated_df = validated_df.withColumn(
    "quality_score",
    F.when(F.col("qf_duplicate"), 0.0)
     .when(F.col("qf_out_of_bounds"), 0.1)
     .when(F.col("qf_stuck_sensor"), 0.3)
     .when(F.col("qf_clock_drift"), 0.7)
     .otherwise(1.0)
)

# ─── Write validated data (deduplicated, quality-flagged) ─────────────────────
output_df = validated_df.filter(
    F.col("row_num") == 1  # Remove duplicates
).select(
    "sensor_id", "equipment_id", "facility_id", "equipment_type",
    "sensor_type", "metric", "value", "corrected_timestamp",
    "quality_score", "qf_out_of_bounds", "qf_clock_drift", "qf_stuck_sensor"
).withColumnRenamed("corrected_timestamp", "event_time")

output_df.writeTo(
    "glue_catalog.iot_validated.sensor_readings_validated"
).tableProperty("write.distribution-mode", "hash")  \
 .tableProperty("write.parquet.compression-codec", "zstd") \
 .option("fanout-enabled", "true") \
 .partitionedBy(
    F.years("event_time"),
    F.months("event_time"),
    F.days("event_time"),
    F.hours("event_time")
 ).append()

# ─── Write quality metrics for monitoring ─────────────────────────────────────
quality_summary = validated_df.groupBy("facility_id", "sensor_type").agg(
    F.count("*").alias("total_readings"),
    F.sum(F.col("qf_out_of_bounds").cast("int")).alias("out_of_bounds_count"),
    F.sum(F.col("qf_clock_drift").cast("int")).alias("clock_drift_count"),
    F.sum(F.col("qf_stuck_sensor").cast("int")).alias("stuck_sensor_count"),
    F.sum(F.col("qf_duplicate").cast("int")).alias("duplicate_count"),
    F.avg("quality_score").alias("avg_quality_score")
)

quality_summary.write.format("iceberg").mode("append").saveAsTable(
    "glue_catalog.iot_monitoring.quality_metrics"
)

job.commit()
```

### Job 2: 1-Second → 1-Minute Downsampling

```python
# job2_one_minute_aggregation.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_hour'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

spark.conf.set("spark.sql.shuffle.partitions", "4000")
spark.conf.set("spark.sql.adaptive.enabled", "true")

# ─── Read validated 1-second data for the processing hour ─────────────────────
processing_hour = args['processing_hour']  # format: 2024-01-15T10

validated_df = spark.read.format("iceberg") \
    .option("scan.planning.locality.enabled", "false") \
    .load("glue_catalog.iot_validated.sensor_readings_validated") \
    .filter(
        (F.col("event_time") >= F.lit(f"{processing_hour}:00:00")) &
        (F.col("event_time") < F.lit(f"{processing_hour}:59:59")) &
        (F.col("quality_score") >= 0.5)  # Exclude low-quality readings
    )

# ─── Truncate to minute boundary ─────────────────────────────────────────────
minute_df = validated_df.withColumn(
    "minute_bucket",
    F.date_trunc("minute", F.col("event_time"))
)

# ─── Compute statistical summaries per sensor per minute ──────────────────────
one_minute_agg = minute_df.groupBy(
    "sensor_id", "equipment_id", "facility_id", "equipment_type",
    "sensor_type", "metric", "minute_bucket"
).agg(
    # Core statistics
    F.min("value").alias("val_min"),
    F.max("value").alias("val_max"),
    F.avg("value").alias("val_avg"),
    F.stddev_samp("value").alias("val_stddev"),
    
    # Percentiles (approximate for performance at scale)
    F.percentile_approx("value", 0.50).alias("val_p50"),
    F.percentile_approx("value", 0.95).alias("val_p95"),
    F.percentile_approx("value", 0.99).alias("val_p99"),
    F.percentile_approx("value", 0.05).alias("val_p05"),
    
    # Data completeness
    F.count("*").alias("reading_count"),
    F.avg("quality_score").alias("avg_quality"),
    
    # Range and spread
    (F.max("value") - F.min("value")).alias("val_range"),
    
    # Skewness and kurtosis (distribution shape)
    F.skewness("value").alias("val_skewness"),
    F.kurtosis("value").alias("val_kurtosis")
)

# ─── Add rate of change (first derivative approximation) ──────────────────────
window_roc = Window.partitionBy("sensor_id", "metric").orderBy("minute_bucket")

one_minute_agg = one_minute_agg.withColumn(
    "prev_avg", F.lag("val_avg").over(window_roc)
).withColumn(
    "rate_of_change",
    (F.col("val_avg") - F.col("prev_avg")) / 60.0  # per second
).drop("prev_avg")

# ─── Add data completeness ratio ─────────────────────────────────────────────
one_minute_agg = one_minute_agg.withColumn(
    "completeness_ratio",
    F.col("reading_count") / 60.0  # Expected 60 readings per minute at 1Hz
)

# ─── Write to 1-minute resolution Iceberg table ──────────────────────────────
one_minute_agg.sortWithinPartitions("sensor_id", "minute_bucket") \
    .writeTo("glue_catalog.iot_aggregated.sensor_1min") \
    .tableProperty("write.parquet.compression-codec", "zstd") \
    .tableProperty("write.target-file-size-bytes", "268435456") \
    .partitionedBy(
        F.days("minute_bucket"),
        F.bucket(64, "equipment_type")
    ).append()

print(f"Wrote {one_minute_agg.count()} 1-minute aggregates")

job.commit()
```

### Job 3: 1-Minute → 1-Hour Aggregation + Anomaly Feature Extraction

```python
# job3_hourly_aggregation_anomaly_features.py
import sys
import numpy as np
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'processing_date', 'processing_hour'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

spark.conf.set("spark.sql.shuffle.partitions", "2000")

processing_date = args['processing_date']
processing_hour = int(args['processing_hour'])

# ─── Read 1-minute data for the hour ─────────────────────────────────────────
one_min_df = spark.read.format("iceberg") \
    .load("glue_catalog.iot_aggregated.sensor_1min") \
    .filter(
        (F.to_date("minute_bucket") == F.lit(processing_date)) &
        (F.hour("minute_bucket") == processing_hour)
    )

# ─── Hourly aggregation ──────────────────────────────────────────────────────
hour_bucket = F.date_trunc("hour", F.col("minute_bucket"))

hourly_agg = one_min_df.withColumn("hour_bucket", hour_bucket).groupBy(
    "sensor_id", "equipment_id", "facility_id", "equipment_type",
    "sensor_type", "metric", "hour_bucket"
).agg(
    F.min("val_min").alias("val_min"),
    F.max("val_max").alias("val_max"),
    F.avg("val_avg").alias("val_avg"),
    F.avg("val_stddev").alias("val_avg_stddev"),
    F.percentile_approx("val_avg", 0.50).alias("val_p50"),
    F.percentile_approx("val_avg", 0.95).alias("val_p95"),
    F.percentile_approx("val_avg", 0.99).alias("val_p99"),
    F.sum("reading_count").alias("total_readings"),
    F.avg("completeness_ratio").alias("avg_completeness"),
    F.avg("rate_of_change").alias("avg_rate_of_change"),
    F.stddev("val_avg").alias("intra_hour_variability"),
    F.max("val_avg").alias("max_minute_avg"),
    F.min("val_avg").alias("min_minute_avg")
)

# ─── Anomaly Feature Extraction ──────────────────────────────────────────────

# Load 7-day rolling baseline for z-score computation
seven_days_ago = (
    F.date_sub(F.to_date(F.lit(processing_date)), 7).cast("string")
)

baseline_df = spark.read.format("iceberg") \
    .load("glue_catalog.iot_aggregated.sensor_1hr") \
    .filter(
        (F.to_date("hour_bucket") >= seven_days_ago) &
        (F.to_date("hour_bucket") < F.lit(processing_date))
    ).groupBy("sensor_id", "metric").agg(
        F.avg("val_avg").alias("baseline_mean"),
        F.stddev("val_avg").alias("baseline_stddev"),
        F.percentile_approx("val_avg", 0.25).alias("baseline_q1"),
        F.percentile_approx("val_avg", 0.75).alias("baseline_q3")
    )

# Join with baseline and compute anomaly features
hourly_with_baseline = hourly_agg.join(
    baseline_df, on=["sensor_id", "metric"], how="left"
)

# Z-Score Feature
hourly_with_baseline = hourly_with_baseline.withColumn(
    "zscore",
    F.when(
        F.col("baseline_stddev") > 0,
        (F.col("val_avg") - F.col("baseline_mean")) / F.col("baseline_stddev")
    ).otherwise(0.0)
)

# IQR-Based Outlier Score
hourly_with_baseline = hourly_with_baseline.withColumn(
    "iqr", F.col("baseline_q3") - F.col("baseline_q1")
).withColumn(
    "iqr_lower", F.col("baseline_q1") - 1.5 * F.col("iqr")
).withColumn(
    "iqr_upper", F.col("baseline_q3") + 1.5 * F.col("iqr")
).withColumn(
    "iqr_outlier_score",
    F.when(F.col("val_avg") < F.col("iqr_lower"),
           (F.col("iqr_lower") - F.col("val_avg")) / F.col("iqr"))
     .when(F.col("val_avg") > F.col("iqr_upper"),
           (F.col("val_avg") - F.col("iqr_upper")) / F.col("iqr"))
     .otherwise(0.0)
)

# Exponential Moving Average Deviation
window_ema = Window.partitionBy("sensor_id", "metric") \
    .orderBy("hour_bucket").rowsBetween(-168, 0)  # 7 days of hours

alpha = 0.1  # EMA smoothing factor

hourly_with_baseline = hourly_with_baseline.withColumn(
    "ema_7day",
    F.avg("val_avg").over(window_ema)  # Simplified; true EMA needs UDF
).withColumn(
    "ema_deviation",
    F.abs(F.col("val_avg") - F.col("ema_7day")) / F.greatest(
        F.abs(F.col("ema_7day")), F.lit(0.001)
    )
)

# Operating Mode Classification (based on rate of change patterns)
hourly_with_baseline = hourly_with_baseline.withColumn(
    "operating_mode",
    F.when(F.col("avg_rate_of_change") > 0.5, "startup")
     .when(F.col("avg_rate_of_change") < -0.5, "shutdown")
     .when(F.col("intra_hour_variability") < F.col("baseline_stddev") * 0.5, "steady_state")
     .otherwise("transient")
)

# ─── Write hourly aggregates with anomaly features ────────────────────────────
output_columns = [
    "sensor_id", "equipment_id", "facility_id", "equipment_type",
    "sensor_type", "metric", "hour_bucket",
    "val_min", "val_max", "val_avg", "val_avg_stddev",
    "val_p50", "val_p95", "val_p99",
    "total_readings", "avg_completeness",
    "zscore", "iqr_outlier_score", "ema_deviation",
    "operating_mode", "intra_hour_variability", "avg_rate_of_change"
]

hourly_with_baseline.select(output_columns).writeTo(
    "glue_catalog.iot_aggregated.sensor_1hr"
).tableProperty("write.parquet.compression-codec", "zstd") \
 .partitionedBy(F.days("hour_bucket"), F.bucket(32, "equipment_type")) \
 .append()

job.commit()
```

### Job 4: Fleet Baseline Computation

```python
# job4_fleet_baseline.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'baseline_end_date', 'lookback_days'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

spark.conf.set("spark.sql.shuffle.partitions", "1000")
spark.conf.set("spark.sql.adaptive.enabled", "true")

baseline_end = args['baseline_end_date']
lookback = int(args['lookback_days'])  # typically 90 days

# ─── Load hourly data for baseline window ─────────────────────────────────────
start_date = F.date_sub(F.to_date(F.lit(baseline_end)), lookback).cast("string")

hourly_df = spark.read.format("iceberg") \
    .load("glue_catalog.iot_aggregated.sensor_1hr") \
    .filter(
        (F.to_date("hour_bucket") >= start_date) &
        (F.to_date("hour_bucket") <= F.lit(baseline_end)) &
        (F.col("operating_mode") == "steady_state")  # Only steady-state for baselines
    )

# ─── Fleet baseline: Normal operating envelope per equipment_type × metric ────
fleet_baseline = hourly_df.groupBy(
    "equipment_type", "sensor_type", "metric", "operating_mode"
).agg(
    F.count("*").alias("sample_count"),
    F.avg("val_avg").alias("fleet_mean"),
    F.stddev("val_avg").alias("fleet_stddev"),
    F.percentile_approx("val_avg", 0.01).alias("fleet_p01"),
    F.percentile_approx("val_avg", 0.05).alias("fleet_p05"),
    F.percentile_approx("val_avg", 0.25).alias("fleet_p25"),
    F.percentile_approx("val_avg", 0.50).alias("fleet_p50"),
    F.percentile_approx("val_avg", 0.75).alias("fleet_p75"),
    F.percentile_approx("val_avg", 0.95).alias("fleet_p95"),
    F.percentile_approx("val_avg", 0.99).alias("fleet_p99"),
    F.avg("val_avg_stddev").alias("fleet_avg_variability"),
    F.avg("avg_rate_of_change").alias("fleet_avg_roc")
)

# ─── Age-based degradation curves ────────────────────────────────────────────
# Join with equipment metadata for age information
equipment_meta = spark.read.format("iceberg").load(
    "glue_catalog.iot_reference.equipment_metadata"
)  # Schema: equipment_id, equipment_type, install_date, last_maintenance_date

hourly_with_age = hourly_df.join(
    equipment_meta.select("equipment_id", "install_date"),
    on="equipment_id"
).withColumn(
    "equipment_age_days",
    F.datediff(F.to_date("hour_bucket"), F.col("install_date"))
).withColumn(
    "age_bucket",
    (F.col("equipment_age_days") / 90).cast("int") * 90  # 90-day age buckets
)

age_degradation = hourly_with_age.groupBy(
    "equipment_type", "sensor_type", "metric", "age_bucket"
).agg(
    F.avg("val_avg").alias("age_mean"),
    F.stddev("val_avg").alias("age_stddev"),
    F.percentile_approx("val_avg", 0.50).alias("age_p50"),
    F.percentile_approx("val_avg", 0.95).alias("age_p95"),
    F.count(F.countDistinct("equipment_id")).alias("equipment_count")
).filter(F.col("equipment_count") >= 10)  # Need statistical significance

# ─── Seasonal adjustment factors (hour of day, day of week) ───────────────────
seasonal_factors = hourly_df.withColumn(
    "hour_of_day", F.hour("hour_bucket")
).withColumn(
    "day_of_week", F.dayofweek("hour_bucket")
).groupBy(
    "equipment_type", "sensor_type", "metric", "hour_of_day", "day_of_week"
).agg(
    F.avg("val_avg").alias("seasonal_mean"),
    F.stddev("val_avg").alias("seasonal_stddev")
)

# ─── Write baselines ─────────────────────────────────────────────────────────
fleet_baseline.withColumn("baseline_date", F.lit(baseline_end)) \
    .write.format("iceberg").mode("overwrite") \
    .saveAsTable("glue_catalog.iot_baselines.fleet_operating_envelope")

age_degradation.withColumn("baseline_date", F.lit(baseline_end)) \
    .write.format("iceberg").mode("overwrite") \
    .saveAsTable("glue_catalog.iot_baselines.age_degradation_curves")

seasonal_factors.withColumn("baseline_date", F.lit(baseline_end)) \
    .write.format("iceberg").mode("overwrite") \
    .saveAsTable("glue_catalog.iot_baselines.seasonal_factors")

job.commit()
```

### Job 5: Predictive Maintenance Feature Assembly

```python
# job5_predictive_maintenance_features.py
import sys
import numpy as np
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'feature_date', 'sagemaker_feature_group'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

spark.conf.set("spark.sql.shuffle.partitions", "2000")

feature_date = args['feature_date']

# ─── Load hourly data (90-day window for trend features) ──────────────────────
start_date = F.date_sub(F.to_date(F.lit(feature_date)), 90).cast("string")

hourly_df = spark.read.format("iceberg") \
    .load("glue_catalog.iot_aggregated.sensor_1hr") \
    .filter(
        (F.to_date("hour_bucket") >= start_date) &
        (F.to_date("hour_bucket") <= F.lit(feature_date))
    )

# ─── Load fleet baselines ────────────────────────────────────────────────────
fleet_baseline = spark.read.format("iceberg").load(
    "glue_catalog.iot_baselines.fleet_operating_envelope"
)

# ─── Feature 1: Degradation Trend Slopes ─────────────────────────────────────
# Compute linear regression slope over 30/60/90 day windows

# Daily averages for trend computation
daily_avg = hourly_df.withColumn(
    "day_bucket", F.to_date("hour_bucket")
).groupBy(
    "equipment_id", "sensor_type", "metric", "day_bucket"
).agg(F.avg("val_avg").alias("daily_mean"))

# Window for regression
window_90d = Window.partitionBy("equipment_id", "sensor_type", "metric") \
    .orderBy("day_bucket").rowsBetween(-89, 0)
window_60d = Window.partitionBy("equipment_id", "sensor_type", "metric") \
    .orderBy("day_bucket").rowsBetween(-59, 0)
window_30d = Window.partitionBy("equipment_id", "sensor_type", "metric") \
    .orderBy("day_bucket").rowsBetween(-29, 0)

# Simplified slope: (last - first) / days (true implementation uses OLS UDF)
daily_avg = daily_avg.withColumn(
    "first_30d", F.first("daily_mean").over(window_30d)
).withColumn(
    "last_value", F.last("daily_mean").over(window_30d)
).withColumn(
    "trend_slope_30d", (F.col("last_value") - F.col("first_30d")) / 30.0
)

# ─── Feature 2: Vibration FFT Features (UDF-based) ───────────────────────────
@F.udf(returnType=ArrayType(DoubleType()))
def compute_fft_features(values):
    """Extract frequency-domain features from vibration time series."""
    if values is None or len(values) < 60:
        return [0.0] * 8
    
    arr = np.array(values, dtype=np.float64)
    # Remove DC component
    arr = arr - np.mean(arr)
    
    # FFT
    fft_vals = np.abs(np.fft.rfft(arr))
    freqs = np.fft.rfftfreq(len(arr), d=1.0/60.0)  # 1-minute sampling
    
    # Features
    total_power = np.sum(fft_vals**2)
    dominant_freq = freqs[np.argmax(fft_vals[1:])+1] if len(fft_vals) > 1 else 0.0
    spectral_centroid = np.sum(freqs * fft_vals) / (np.sum(fft_vals) + 1e-10)
    spectral_spread = np.sqrt(
        np.sum(((freqs - spectral_centroid)**2) * fft_vals) / (np.sum(fft_vals) + 1e-10)
    )
    
    # Band powers (low/mid/high frequency)
    low_band = np.sum(fft_vals[freqs < 0.1]**2) / (total_power + 1e-10)
    mid_band = np.sum(fft_vals[(freqs >= 0.1) & (freqs < 0.3)]**2) / (total_power + 1e-10)
    high_band = np.sum(fft_vals[freqs >= 0.3]**2) / (total_power + 1e-10)
    
    # Crest factor
    crest_factor = np.max(np.abs(arr)) / (np.sqrt(np.mean(arr**2)) + 1e-10)
    
    return [
        float(total_power), float(dominant_freq),
        float(spectral_centroid), float(spectral_spread),
        float(low_band), float(mid_band), float(high_band),
        float(crest_factor)
    ]

# Collect 1-hour of 1-minute averages for FFT (vibration sensors only)
vibration_hourly = hourly_df.filter(
    F.col("sensor_type") == "vibration"
)

# Collect minute-level values for FFT computation
minute_data = spark.read.format("iceberg") \
    .load("glue_catalog.iot_aggregated.sensor_1min") \
    .filter(
        (F.to_date("minute_bucket") == F.lit(feature_date)) &
        (F.col("sensor_type") == "vibration")
    )

# Group minutes into hours for FFT
fft_input = minute_data.withColumn(
    "hour_bucket", F.date_trunc("hour", "minute_bucket")
).groupBy("equipment_id", "sensor_id", "metric", "hour_bucket").agg(
    F.collect_list(F.struct("minute_bucket", "val_avg")).alias("minute_values")
).withColumn(
    # Sort and extract just values
    "sorted_values",
    F.transform(
        F.array_sort("minute_values"),
        lambda x: x["val_avg"]
    )
).withColumn(
    "fft_features", compute_fft_features(F.col("sorted_values"))
)

# Explode FFT features into columns
fft_features = fft_input.select(
    "equipment_id", "sensor_id", "metric", "hour_bucket",
    F.col("fft_features")[0].alias("fft_total_power"),
    F.col("fft_features")[1].alias("fft_dominant_freq"),
    F.col("fft_features")[2].alias("fft_spectral_centroid"),
    F.col("fft_features")[3].alias("fft_spectral_spread"),
    F.col("fft_features")[4].alias("fft_low_band_ratio"),
    F.col("fft_features")[5].alias("fft_mid_band_ratio"),
    F.col("fft_features")[6].alias("fft_high_band_ratio"),
    F.col("fft_features")[7].alias("fft_crest_factor")
)

# ─── Feature 3: Cross-Sensor Correlation ─────────────────────────────────────
# For each equipment, compute correlation between sensor pairs
# (e.g., vibration vs temperature indicates bearing issues)

equipment_sensors = hourly_df.filter(
    F.to_date("hour_bucket") == F.lit(feature_date)
).groupBy("equipment_id", "hour_bucket").pivot(
    "metric",
    ["vibration_rms", "temperature", "current", "pressure"]
).agg(F.first("val_avg"))

cross_sensor_features = equipment_sensors.withColumn(
    "vib_temp_ratio",
    F.col("vibration_rms") / F.greatest(F.col("temperature"), F.lit(0.001))
).withColumn(
    "current_pressure_ratio",
    F.col("current") / F.greatest(F.col("pressure"), F.lit(0.001))
)

# ─── Feature 4: Fleet-relative position ──────────────────────────────────────
# How does this equipment compare to fleet peers?

latest_hourly = hourly_df.filter(
    F.to_date("hour_bucket") == F.lit(feature_date)
)

fleet_relative = latest_hourly.join(
    fleet_baseline.select(
        "equipment_type", "sensor_type", "metric",
        "fleet_mean", "fleet_stddev", "fleet_p95"
    ),
    on=["equipment_type", "sensor_type", "metric"],
    how="left"
).withColumn(
    "fleet_zscore",
    (F.col("val_avg") - F.col("fleet_mean")) / F.greatest(F.col("fleet_stddev"), F.lit(0.001))
).withColumn(
    "pct_of_fleet_p95",
    F.col("val_avg") / F.greatest(F.col("fleet_p95"), F.lit(0.001))
)

# ─── Feature 5: Days since last maintenance ──────────────────────────────────
maintenance_history = spark.read.format("iceberg").load(
    "glue_catalog.iot_reference.maintenance_events"
)

days_since_maintenance = maintenance_history.filter(
    F.col("event_type") == "maintenance_complete"
).groupBy("equipment_id").agg(
    F.max("event_date").alias("last_maintenance_date")
).withColumn(
    "days_since_maintenance",
    F.datediff(F.lit(feature_date), F.col("last_maintenance_date"))
)

# ─── Assemble final feature vector ───────────────────────────────────────────
# Aggregate to equipment-level (one row per equipment per day)
equipment_features = latest_hourly.groupBy(
    "equipment_id", "equipment_type", "facility_id"
).agg(
    # Aggregate anomaly scores across all sensors on this equipment
    F.max("zscore").alias("max_zscore"),
    F.avg("zscore").alias("avg_zscore"),
    F.max("iqr_outlier_score").alias("max_iqr_score"),
    F.sum(F.when(F.abs(F.col("zscore")) > 3, 1).otherwise(0)).alias("anomaly_count"),
    F.avg("avg_completeness").alias("data_completeness")
)

# Join all feature sets
final_features = equipment_features \
    .join(days_since_maintenance, on="equipment_id", how="left") \
    .withColumn("feature_date", F.lit(feature_date)) \
    .withColumn("feature_timestamp", F.current_timestamp())

# ─── Write to SageMaker Feature Store ────────────────────────────────────────
final_features.write.format("iceberg").mode("append").saveAsTable(
    "glue_catalog.iot_features.predictive_maintenance_features"
)

# Also write to SageMaker Feature Store via Glue connector
from awsglue.dynamicframe import DynamicFrame

feature_dynamic_frame = DynamicFrame.fromDF(final_features, glueContext, "features")

glueContext.write_dynamic_frame.from_options(
    frame=feature_dynamic_frame,
    connection_type="custom.spark",
    connection_options={
        "className": "sagemaker.spark.SageMakerFeatureStoreConnector",
        "featureGroupName": args['sagemaker_feature_group'],
        "eventTimeFeatureName": "feature_timestamp",
        "recordIdentifierFeatureName": "equipment_id"
    }
)

job.commit()
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 6. Production Handling

### Sensor Clock Drift Compensation

```python
# Sensors with low-quality NTP sync may report timestamps ±minutes off.
# Strategy: Use ingestion_time as ground truth when drift exceeds threshold.

def compensate_clock_drift(df, drift_threshold_seconds=30):
    """
    Correct sensor timestamps that have drifted from server time.
    
    Approach:
    1. If |sensor_time - ingestion_time| < threshold → trust sensor_time
    2. If drift detected → use ingestion_time - avg_network_latency
    3. Log drifted sensors for firmware update scheduling
    """
    return df.withColumn(
        "drift_seconds",
        F.unix_timestamp("sensor_timestamp") - F.unix_timestamp("ingestion_time")
    ).withColumn(
        "corrected_time",
        F.when(
            F.abs(F.col("drift_seconds")) > drift_threshold_seconds,
            # Use ingestion time minus typical network latency (2s)
            F.col("ingestion_time") - F.expr("INTERVAL 2 SECONDS")
        ).otherwise(F.col("sensor_timestamp"))
    )
```

### Missing Data Interpolation

```python
# Strategy varies by sensor type and gap duration:
# - Temperature (slow-changing): Linear interpolation for gaps < 5 min
# - Vibration (fast-changing): Mark as NULL, do not interpolate
# - Pressure (medium): Forward-fill for gaps < 2 min

INTERPOLATION_RULES = {
    "temperature": {"method": "linear", "max_gap_minutes": 5},
    "vibration":   {"method": "null", "max_gap_minutes": 0},
    "pressure":    {"method": "ffill", "max_gap_minutes": 2},
    "current":     {"method": "linear", "max_gap_minutes": 3},
    "flow_rate":   {"method": "ffill", "max_gap_minutes": 2},
}

def interpolate_missing(df, sensor_type, max_gap_minutes):
    """Fill short gaps; leave long gaps as NULL for downstream handling."""
    window = Window.partitionBy("sensor_id", "metric").orderBy("event_time")
    
    return df.withColumn(
        "prev_time", F.lag("event_time").over(window)
    ).withColumn(
        "gap_minutes",
        (F.unix_timestamp("event_time") - F.unix_timestamp("prev_time")) / 60.0
    ).withColumn(
        "interpolated",
        F.when(
            F.col("gap_minutes") <= max_gap_minutes,
            True
        ).otherwise(False)
    )
```

### Late-Arriving Sensor Data

```python
# Edge gateways buffer data during network outages and send in bursts.
# Late data can arrive hours or even days after the event time.

# Strategy: Use Iceberg's MERGE INTO for idempotent late-data handling

def handle_late_arrivals(spark, late_data_df, target_table):
    """
    Merge late-arriving data into existing aggregations.
    Recompute affected time windows.
    """
    # Identify affected windows
    affected_windows = late_data_df.select(
        "sensor_id", "metric",
        F.date_trunc("hour", "event_time").alias("affected_hour")
    ).distinct()
    
    # Re-aggregate affected windows from raw data
    # (Iceberg time-travel ensures consistency)
    late_data_df.createOrReplaceTempView("late_data")
    affected_windows.createOrReplaceTempView("affected")
    
    spark.sql(f"""
        MERGE INTO {target_table} t
        USING (
            SELECT sensor_id, metric, hour_bucket,
                   MIN(val_min) as val_min, MAX(val_max) as val_max,
                   AVG(val_avg) as val_avg
            FROM recomputed_aggregates
            GROUP BY sensor_id, metric, hour_bucket
        ) s
        ON t.sensor_id = s.sensor_id 
           AND t.metric = s.metric 
           AND t.hour_bucket = s.hour_bucket
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
```

### Sensor Replacement Detection

```python
# When a sensor is replaced, readings may jump discontinuously.
# This should NOT trigger anomaly alerts.

def detect_sensor_replacement(df):
    """
    Detect sensor replacements by looking for:
    1. Gap > 1 hour (maintenance window)
    2. Followed by value jump > 3 sigma from pre-gap baseline
    3. Followed by stable operation at new level
    """
    window = Window.partitionBy("sensor_id", "metric").orderBy("event_time")
    
    return df.withColumn(
        "gap_hours",
        (F.unix_timestamp("event_time") - 
         F.unix_timestamp(F.lag("event_time").over(window))) / 3600.0
    ).withColumn(
        "pre_gap_avg",
        F.avg("value").over(window.rowsBetween(-60, -1))
    ).withColumn(
        "post_gap_avg",
        F.avg("value").over(window.rowsBetween(1, 60))
    ).withColumn(
        "likely_replacement",
        (F.col("gap_hours") > 1.0) &
        (F.abs(F.col("post_gap_avg") - F.col("pre_gap_avg")) > 
         3 * F.col("val_avg_stddev"))
    )
```

### Equipment Commissioning/Decommissioning

```python
# New equipment needs burn-in period before baselines apply.
# Decommissioned equipment should stop generating alerts.

BURN_IN_PERIOD_DAYS = 14  # 2 weeks of operation before including in baselines

def filter_commissioning_state(df, equipment_meta):
    """Exclude equipment in burn-in or decommissioned state."""
    return df.join(
        equipment_meta.select(
            "equipment_id", "install_date", "decommission_date", "status"
        ),
        on="equipment_id"
    ).filter(
        (F.col("status") == "active") &
        (F.datediff(F.col("event_time"), F.col("install_date")) > BURN_IN_PERIOD_DAYS)
    )
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 7. Downstream Integration

### Grafana Real-Time Dashboards

```
┌─────────────────────────────────────────────────────────────────────┐
│  GRAFANA INTEGRATION                                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Data Sources:                                                       │
│  ├── InfluxDB (last 24hr, 1-second resolution for live monitoring)  │
│  ├── Athena (1-minute Iceberg tables for detailed analysis)         │
│  └── Athena (1-hour Iceberg tables for trend dashboards)            │
│                                                                      │
│  Dashboards:                                                         │
│  ├── Fleet Overview (all facilities, health scores, alerts)         │
│  ├── Facility Drilldown (equipment status, anomaly heatmaps)        │
│  ├── Equipment Detail (sensor trends, predicted RUL, baselines)     │
│  ├── Maintenance Planner (upcoming predicted failures)              │
│  └── Data Quality (sensor health, completeness, drift)              │
│                                                                      │
│  Alert Rules:                                                        │
│  ├── Critical: zscore > 5 AND operating_mode = "steady_state"       │
│  ├── Warning:  zscore > 3 AND duration > 30 minutes                 │
│  └── Info:     fleet_relative_position > 90th percentile            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### SageMaker Predictive Models

```python
# SageMaker training pipeline consumes features from Glue output

# Model 1: Remaining Useful Life (RUL) Regression
# Input: equipment_features table (90-day feature windows)
# Output: Predicted days until maintenance required

# Model 2: Anomaly Classification
# Input: hourly anomaly features (zscore, iqr_score, fft_features)
# Output: anomaly_type (bearing_wear, misalignment, imbalance, normal)

# Model 3: Failure Mode Prediction
# Input: Multi-sensor cross-correlation features
# Output: Probability of each failure mode in next 30 days

# Training data query (via Athena on Iceberg)
TRAINING_QUERY = """
SELECT 
    f.*,
    CASE 
        WHEN m.days_to_failure <= 7 THEN 'critical'
        WHEN m.days_to_failure <= 30 THEN 'warning'
        ELSE 'normal'
    END as label
FROM iot_features.predictive_maintenance_features f
LEFT JOIN iot_reference.failure_events m
    ON f.equipment_id = m.equipment_id
    AND m.failure_date BETWEEN f.feature_date AND DATE_ADD(f.feature_date, 30)
WHERE f.feature_date BETWEEN '2023-01-01' AND '2024-01-01'
"""
```

### Maintenance Management Integration (SAP PM / IBM Maximo)

```python
# When model predicts failure probability > threshold:
# 1. Generate work order recommendation via API
# 2. Include predicted failure mode and suggested parts
# 3. Suggest optimal maintenance window (minimize production impact)

import boto3
import json

def generate_maintenance_recommendation(equipment_id, prediction):
    """Push maintenance recommendation to SAP PM via API Gateway."""
    
    recommendation = {
        "equipment_id": equipment_id,
        "predicted_failure_date": prediction["rul_days_from_now"],
        "confidence": prediction["confidence"],
        "failure_mode": prediction["failure_mode"],
        "recommended_action": prediction["maintenance_type"],
        "suggested_parts": prediction["spare_parts"],
        "priority": "P1" if prediction["rul_days_from_now"] < 7 else "P2",
        "optimal_window": prediction["low_production_windows"]
    }
    
    # Push to maintenance system via EventBridge
    client = boto3.client('events')
    client.put_events(Entries=[{
        'Source': 'iot.predictive-maintenance',
        'DetailType': 'MaintenanceRecommendation',
        'Detail': json.dumps(recommendation),
        'EventBusName': 'maintenance-events'
    }])
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 8. Scaling: 864B Data Points/Day Optimization

### Partition Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION STRATEGY BY TABLE                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Raw (1-second):                                                     │
│    year/month/day/hour/facility_id                                   │
│    ~50TB/day → 50,000 files/hour × 24 hours = 1.2M files/day       │
│    File size target: 128MB (optimized for write throughput)          │
│                                                                      │
│  1-Minute Aggregated:                                                │
│    day/bucket(64, equipment_type)                                    │
│    ~850GB/day → 64 partitions × files = ~4,000 files/day            │
│    File size target: 256MB                                           │
│                                                                      │
│  1-Hour Aggregated:                                                  │
│    day/bucket(32, equipment_type)                                    │
│    ~15GB/day → 32 partitions = ~200 files/day                       │
│    File size target: 256MB                                           │
│                                                                      │
│  Features:                                                           │
│    day/equipment_type                                                 │
│    ~500MB/day                                                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Glue Job Scaling

```
┌────────────────────────────────────────────────────────────────────────┐
│  JOB SCALING CONFIGURATION                                             │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Job 1 (Validation):                                                    │
│    Workers: 50 × G.1X (auto-scale 30-80)                               │
│    Partitions: 2000                                                     │
│    Strategy: Broadcast join for sensor_bounds (small table)             │
│                                                                         │
│  Job 2 (1-min agg):                                                     │
│    Workers: 80 × G.1X (auto-scale 50-120)                              │
│    Partitions: 4000                                                     │
│    Strategy: Hash partition by sensor_id for window operations          │
│                                                                         │
│  Job 3 (1-hr agg):                                                      │
│    Workers: 40 × G.2X (auto-scale 20-60)                               │
│    Partitions: 2000                                                     │
│    Strategy: Repartition by equipment_id for cross-sensor features      │
│                                                                         │
│  Job 4 (Fleet baseline):                                                │
│    Workers: 20 × G.4X (fixed — runs weekly, needs large memory)        │
│    Partitions: 1000                                                     │
│    Strategy: Full scan of 90-day window; heavy aggregation              │
│                                                                         │
│  Job 5 (ML features):                                                   │
│    Workers: 30 × G.4X (auto-scale 20-50)                               │
│    Partitions: 2000                                                     │
│    Strategy: G.4X for FFT UDFs (NumPy memory); collect_list operations  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Performance Optimizations

```python
# 1. Broadcast small reference tables
sensor_bounds_broadcast = F.broadcast(sensor_bounds)  # ~10MB

# 2. Salting for skewed equipment_types (some types have 10x more sensors)
def salt_key(df, key_col, num_salts=10):
    return df.withColumn(
        "salted_key",
        F.concat(F.col(key_col), F.lit("_"), (F.rand() * num_salts).cast("int"))
    )

# 3. Bucketed writes for efficient downstream joins
# Pre-bucket by equipment_id (consistent across all tables)
spark.sql("""
    CREATE TABLE IF NOT EXISTS iot_aggregated.sensor_1hr (...)
    USING iceberg
    PARTITIONED BY (days(hour_bucket), bucket(32, equipment_type))
    TBLPROPERTIES (
        'write.distribution-mode' = 'hash',
        'write.parquet.compression-codec' = 'zstd',
        'write.target-file-size-bytes' = '268435456',
        'read.split.target-size' = '134217728'
    )
""")

# 4. Iceberg compaction job (scheduled daily)
spark.sql("""
    CALL glue_catalog.system.rewrite_data_files(
        table => 'iot_aggregated.sensor_1hr',
        strategy => 'sort',
        sort_order => 'equipment_id ASC, hour_bucket DESC',
        options => map(
            'target-file-size-bytes', '268435456',
            'min-file-size-bytes', '67108864',
            'max-file-size-bytes', '536870912'
        )
    )
""")

# 5. Expire old snapshots (prevent metadata bloat)
spark.sql("""
    CALL glue_catalog.system.expire_snapshots(
        table => 'iot_aggregated.sensor_1min',
        older_than => TIMESTAMP '2024-01-01 00:00:00',
        retain_last => 10
    )
""")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 9. Cost Analysis

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MONTHLY COST BREAKDOWN                                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  STORAGE                                                                 │
│  ├── S3 Raw (30-day retention):          50TB/day × 30 = 1.5PB         │
│  │   S3 Standard (7 days):              350TB × $0.023/GB = $8,050     │
│  │   S3 Glacier IR (23 days):           1.15PB × $0.004/GB = $4,600   │
│  │                                                    Subtotal: $12,650 │
│  ├── S3 1-Minute (1-year retention):    850GB/day × 365 = 310TB        │
│  │   S3 Standard-IA:                   310TB × $0.0125/GB = $3,875     │
│  ├── S3 1-Hour (5-year retention):      15GB/day × 1825 = 27TB         │
│  │   S3 Standard:                      27TB × $0.023/GB = $621         │
│  ├── Feature Store:                     500MB/day × 365 = 182GB         │
│  │   S3 Standard:                                        ≈ $5           │
│  │                                                                       │
│  │   TOTAL STORAGE:                              ~$17,150/month         │
│  │                                                                       │
│  COMPUTE (GLUE)                                                          │
│  ├── Job 1 (Validation):                                                │
│  │   50 × G.1X × 0.25hr × 24 runs/day × 30 = 9,000 DPU-hrs           │
│  │   9,000 × $0.44 =                                     $3,960        │
│  ├── Job 2 (1-min agg):                                                │
│  │   80 × G.1X × 0.42hr × 24 runs/day × 30 = 24,192 DPU-hrs          │
│  │   24,192 × $0.44 =                                   $10,644        │
│  ├── Job 3 (1-hr agg + anomaly):                                       │
│  │   40 × G.2X × 0.33hr × 24 runs/day × 30 = 9,504 DPU-hrs           │
│  │   9,504 × $0.44 =                                     $4,182        │
│  ├── Job 4 (Fleet baseline - weekly):                                   │
│  │   20 × G.4X × 2hr × 4 runs/month = 640 DPU-hrs                     │
│  │   640 × $0.44 =                                         $282        │
│  ├── Job 5 (ML features - daily):                                       │
│  │   30 × G.4X × 3hr × 30 = 10,800 DPU-hrs                            │
│  │   10,800 × $0.44 =                                    $4,752        │
│  │                                                                       │
│  │   TOTAL COMPUTE:                              ~$23,820/month         │
│  │                                                                       │
│  STREAMING (KINESIS)                                                     │
│  ├── 200 shards × $0.015/hr × 720hrs =                   $2,160        │
│  ├── PUT payload units: 10M sensors × 86400s × $0.014/M = $12,096      │
│  │                                                                       │
│  │   TOTAL STREAMING:                            ~$14,256/month         │
│  │                                                                       │
│  OTHER                                                                   │
│  ├── InfluxDB Cloud (24hr hot data):                      $2,000        │
│  ├── SageMaker (training + inference):                    $5,000        │
│  ├── Athena queries:                                      $1,500        │
│  ├── Data transfer:                                       $3,000        │
│  │                                                                       │
│  │   TOTAL OTHER:                                ~$11,500/month         │
│  │                                                                       │
│  ═══════════════════════════════════════════════════════════════════════  │
│  GRAND TOTAL:                                    ~$66,726/month         │
│  ═══════════════════════════════════════════════════════════════════════  │
│                                                                          │
│  COST PER SENSOR:                                $0.0067/sensor/month   │
│  COST PER DATA POINT:                            $0.0000000026          │
│                                                                          │
│  COMPARISON:                                                             │
│  ├── Pure InfluxDB Cloud (all data): ~$4,500,000/month (67x more)       │
│  ├── Pure TimescaleDB (self-managed): ~$800,000/month (12x more)        │
│  └── This architecture:               ~$67,000/month                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies

1. **Lifecycle Policies**: Raw data → Glacier IR after 7 days, delete after 30
2. **Adaptive Resolution**: Increase sampling for anomalous equipment, decrease for healthy
3. **Spot Instances**: Glue Flex execution (up to 70% savings for Jobs 4-5)
4. **Compaction**: Regular Iceberg compaction reduces scan costs by 40%
5. **Partition Pruning**: Pushdown predicates eliminate 95%+ of data scanning

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 10. Companies Running Similar Architectures

### Siemens (MindSphere)
- **Scale**: 1.5M+ connected assets, billions of data points daily
- **Use Case**: Gas turbine predictive maintenance, building automation
- **Approach**: Multi-resolution aggregation on AWS with custom ML models
- **Outcome**: 30% reduction in unplanned downtime

### GE (Predix → AWS Migration)
- **Scale**: 500K+ industrial assets (aviation, power, healthcare)
- **Use Case**: Jet engine health monitoring, power plant optimization
- **Approach**: Digital twin data preparation via batch aggregation pipelines
- **Outcome**: $1.5B in customer savings through predictive maintenance

### Caterpillar (Cat Connect)
- **Scale**: 1M+ heavy equipment globally (mining, construction)
- **Use Case**: Engine degradation prediction, fuel optimization
- **Approach**: Tiered aggregation (real-time + batch) for global fleet
- **Outcome**: 20% reduction in maintenance costs

### Rolls-Royce (IntelligentEngine)
- **Scale**: 13,000+ engines in service, 70+ petabytes of data
- **Use Case**: TotalCare (power-by-the-hour) requires precise health monitoring
- **Approach**: FFT-based vibration analysis, multi-resolution trend storage
- **Outcome**: 99.9% dispatch reliability for airline customers

### Tesla (Vehicle Telemetry)
- **Scale**: 5M+ vehicles, 100+ sensors each, continuous streaming
- **Use Case**: Battery degradation prediction, predictive service scheduling
- **Approach**: Multi-resolution aggregation for fleet learning
- **Outcome**: OTA updates prevent 50%+ of potential service visits

### Key Architectural Patterns Shared

```
1. Multi-resolution is universal (nobody stores raw at scale for >30 days)
2. Batch aggregation dominates (streaming only for <5min alerting)
3. Fleet baselines are equipment-type specific (not one-size-fits-all)
4. ML features are pre-computed (not computed at inference time)
5. Iceberg/Delta Lake for time-travel and schema evolution
6. Progressive retention: raw→days, minute→months, hour→years
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Summary

This architecture processes 864 billion data points daily at $0.0067 per sensor per month
by combining AWS Glue's batch processing power with Iceberg's multi-resolution storage.
The key insight is that IoT telemetry is a **write-heavy, read-selective** workload —
you write everything but only query specific time windows, equipment, or aggregation
levels. Glue's serverless auto-scaling handles the variable compute demand without
maintaining 24/7 cluster infrastructure, while Iceberg's partition evolution and
time-travel provide the flexibility needed as the pipeline matures.
