# Production Issues #61-75: Data Quality & Pipeline Reliability

## Context
At scale: 1000+ data pipelines, 99.99% SLA target, 100TB+ processed daily.
Companies: Airbnb, Netflix, Uber, LinkedIn managing data quality at petabyte scale.

---

## Issue #61: Silent Data Corruption (No Error, Wrong Results)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Pipeline Succeeds but Produces Wrong Data                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Monthly (hardest to detect)                                │
│                                                                         │
│  SCENARIO:                                                              │
│  ETL pipeline joins orders with payments table                         │
│  Upstream team adds a duplicate key in payments (bug)                  │
│  → Join produces 2x rows (Cartesian on duplicate keys)                │
│  → Revenue report shows $20M instead of $10M                          │
│  → CEO presents wrong revenue to board of directors                   │
│  → Discovered 2 weeks later during quarterly audit                    │
│                                                                         │
│  NO ERROR ANYWHERE:                                                     │
│  - Pipeline status: SUCCESS                                            │
│  - Spark job: completed normally                                       │
│  - Row count: increased (looks like growth!)                          │
│  - No exceptions, no failures, no alerts                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Row count assertions (expected vs actual)
from great_expectations import DataContext

context = DataContext()
batch = context.get_batch("revenue_daily")

# Assert row count within expected range
batch.expect_table_row_count_to_be_between(min_value=900000, max_value=1100000)

# Assert no duplicates on primary key
batch.expect_column_values_to_be_unique("order_id")

# Assert sum matches source
batch.expect_column_sum_to_be_between("amount", min_value=9e6, max_value=11e6)

# 2. Cross-system reconciliation
# After every pipeline run:
source_count = spark.sql("SELECT COUNT(*) FROM source.orders WHERE date='2024-01-15'")
target_count = spark.sql("SELECT COUNT(*) FROM warehouse.orders WHERE date='2024-01-15'")
assert abs(source_count - target_count) / source_count < 0.001  # < 0.1% drift

# 3. Join explosion detection
# Monitor: output_rows / input_rows ratio
# Normal join: ratio ≈ 1.0
# Cartesian/duplicate: ratio >> 1.0 → ALERT
join_ratio = output_df.count() / input_df.count()
if join_ratio > 1.5:
    raise DataQualityError(f"Join explosion detected: ratio={join_ratio}")
```

---

## Issue #62: Schema Drift Breaking Downstream Consumers

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Upstream Adds Column → 50 Downstream Pipelines Break         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Weekly (in large organizations)                            │
│                                                                         │
│  SCENARIO:                                                              │
│  Team A adds nullable column "discount_type" to orders table          │
│  → Team B's pipeline: SELECT * → fails (unexpected column)            │
│  → Team C's pipeline: strict schema validation rejects new data       │
│  → Team D's pipeline: Parquet schema mismatch error                   │
│  → 50 downstream pipelines affected across 10 teams                   │
│                                                                         │
│  WORSE VARIANT:                                                         │
│  Column type changed: "price" from INT to DECIMAL                     │
│  → Overflow in downstream INT calculations                            │
│  → Negative prices appearing in reports                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Schema Registry with compatibility checks
# Before schema change is published:
compatibility_mode: BACKWARD  # New schema can read old data
# BACKWARD: new reader, old writer (add optional columns only)
# FORWARD: old reader, new writer (remove optional columns only)
# FULL: both directions compatible

# 2. Data contracts between teams
# contracts/orders-v2.yaml
schema:
  fields:
    - name: order_id
      type: string
      required: true
      breaking_change: never  # Cannot be modified
    - name: amount
      type: decimal(10,2)
      required: true
    - name: discount_type
      type: string
      required: false
      added_version: "2.1"
      
sla:
  freshness: 5m
  completeness: 99.9%
  
owner: team-a@company.com
consumers:
  - team-b (analytics)
  - team-c (billing)

# 3. Schema change alerting
- alert: SchemaChanged
  expr: schema_version{table="orders"} != schema_version_expected{table="orders"}
  annotations:
    summary: "Schema change detected on {{ $labels.table }}"
    impact: "Consumers: team-b, team-c, team-d (from data contract)"
```

---

## Issue #63: Null Value Flood Corrupting Aggregations

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: NULL Values Make AVG/SUM Calculations Wrong                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: After upstream system changes                              │
│                                                                         │
│  SCENARIO:                                                              │
│  Upstream API changes: field "revenue" → returns null instead of 0    │
│  for free-tier customers (bug in upstream deploy)                      │
│                                                                         │
│  Before: AVG(revenue) = (100+200+0+300+0)/5 = 120                    │
│  After: AVG(revenue) = (100+200+NULL+300+NULL)/3 = 200               │
│  → Average revenue inflated by 67% (NULLs excluded from AVG)         │
│  → Business team: "Revenue per user jumped 67%! Amazing!"            │
│  → Actually: data quality bug, not growth                             │
│                                                                         │
│  SUM case:                                                              │
│  Before: SUM(revenue) = 600                                            │
│  After: SUM(revenue) = 600 (NULLs treated as 0 in SUM)              │
│  → But COUNT drops from 5 to 3                                        │
│  → Inconsistent metrics depending on aggregation function             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. NULL rate monitoring per column
null_rate_check = spark.sql("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN revenue IS NULL THEN 1 ELSE 0 END) as null_count,
        SUM(CASE WHEN revenue IS NULL THEN 1 ELSE 0 END) / COUNT(*) as null_rate
    FROM orders
    WHERE date = current_date()
""")

# Alert if null_rate exceeds historical baseline + 2 std dev
if null_rate > historical_avg + 2 * historical_std:
    alert("Null rate anomaly", column="revenue", rate=null_rate)

# 2. Great Expectations check
batch.expect_column_values_to_not_be_null("revenue", mostly=0.99)
# At least 99% non-null (allows some but catches floods)

# 3. Explicit NULL handling in all aggregations
# NEVER use AVG() without understanding NULL behavior
SELECT 
    AVG(COALESCE(revenue, 0)) as avg_revenue_with_zeros,
    AVG(revenue) as avg_revenue_nulls_excluded,  -- Different!
    COUNT(*) as total_rows,
    COUNT(revenue) as non_null_rows
FROM orders
```

---

## Issue #64: Timezone Bug Causing Double-Counted / Missing Data

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: DST Change Causes 1 Hour of Data to Duplicate/Disappear      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: 2x per year (DST transitions) + timezone conversions      │
│                                                                         │
│  SCENARIO (Spring Forward):                                             │
│  Pipeline partitions by date in local time                             │
│  2:00 AM → 3:00 AM (1 hour "disappears")                             │
│  → Events from 2:00-2:59 AM local don't fit any partition             │
│  → Lost to a dead letter queue or wrong partition                     │
│                                                                         │
│  SCENARIO (Fall Back):                                                  │
│  1:00 AM → 1:00 AM (1 hour "repeats")                                │
│  → Events from the second 1:00 AM assigned to same partition          │
│  → Duplicate processing if pipeline reprocesses that hour             │
│                                                                         │
│  SCENARIO (Cross-timezone):                                             │
│  Server in UTC, data partitioned by PST date                          │
│  → Records at 23:00 UTC on Jan 15 = 15:00 PST Jan 15                │
│  → Records at 08:00 UTC on Jan 16 = 00:00 PST Jan 16                │
│  → Pipeline running at 00:00 UTC: which date partition to process?   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# RULE: ALWAYS store and process in UTC. Convert only at display layer.

# 1. Partition by UTC date always
spark.sql("""
    INSERT INTO warehouse.events
    PARTITION (dt = date_format(event_time_utc, 'yyyy-MM-dd'))
    SELECT * FROM staging.events
""")
# Never: PARTITION (dt = date_format(convert_timezone(event_time, 'America/New_York'), 'yyyy-MM-dd'))

# 2. DST-aware monitoring
# Alert if hourly event count deviates > 20% from previous week same DOW
- alert: HourlyVolumeAnomaly
  expr: |
    abs(events_per_hour - events_per_hour offset 7d) 
    / events_per_hour offset 7d > 0.2

# 3. Use epoch timestamps internally
# Store as epoch_ms (timezone-agnostic)
# Convert to user timezone only at API/UI layer
# This eliminates ALL timezone bugs in data layer
```

---

## Issue #65: Data Pipeline Idempotency Failure (Reprocessing Creates Duplicates)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Retry/Reprocess Creates Duplicate Records                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Every pipeline retry (daily)                               │
│                                                                         │
│  SCENARIO:                                                              │
│  Spark job fails at 80% completion → operator reruns                  │
│  → First 80% of data written again (duplicates)                       │
│  → No deduplication logic → double counting in reports                │
│                                                                         │
│  SCALE IMPACT:                                                          │
│  1000 pipelines × 10% daily failure rate × 2 retries average         │
│  = 200 potential duplicate-producing runs per day                     │
│                                                                         │
│  VARIANTS:                                                              │
│  - Kafka consumer rebalance → reprocess committed messages            │
│  - Airflow task retry → re-execute write to sink                      │
│  - Exactly-once broken → duplicates in output                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Idempotent writes with MERGE/UPSERT
spark.sql("""
    MERGE INTO target.orders t
    USING staging.orders s
    ON t.order_id = s.order_id AND t.event_time = s.event_time
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
# Re-running this is safe: duplicates are handled by MERGE

# 2. Write-audit-publish pattern
# Step 1: Write to staging (overwrite partition)
# Step 2: Audit (count, checksum, quality)
# Step 3: Publish (atomic swap staging → production)
# Rerun: overwrites staging, doesn't affect production until audit passes

# 3. Deduplication in streaming
# Kafka: enable.idempotence=true + transactional.id
# Flink: exactly-once checkpointing
# Post-processing: DISTINCT on business key + event_time

# 4. Monitor duplicate rate
duplicate_rate = spark.sql("""
    SELECT 
        COUNT(*) - COUNT(DISTINCT order_id) as duplicates,
        COUNT(*) as total
    FROM target.orders
    WHERE date = current_date()
""")
assert duplicate_rate["duplicates"] == 0, f"Duplicates found: {duplicate_rate}"
```

---

## Issue #66: Backfill Job Consuming All Cluster Resources

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Historical Reprocessing Starves Production Pipelines          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Monthly (backfills for bug fixes, new features)            │
│                                                                         │
│  SCENARIO:                                                              │
│  Bug discovered in transformation logic → need to backfill 90 days    │
│  Engineer submits backfill job: 90 days × 10TB/day = 900TB to process │
│  → Job takes all available Spark executors (200/200)                  │
│  → Daily production pipelines queued, waiting for resources            │
│  → SLA breach: daily reports 4 hours late                             │
│  → Downstream ML training delayed → model staleness                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Resource pools with priority
# Production pool: guaranteed 150 executors, priority HIGH
# Backfill pool: max 50 executors, priority LOW, preemptible
spark:
  scheduler:
    mode: FAIR
    pools:
      - name: production
        weight: 3
        minShare: 150
      - name: backfill
        weight: 1
        minShare: 0  # Can be fully preempted

# 2. Throttled backfill (process N days per batch)
def run_backfill(start_date, end_date, batch_size=7):
    """Process backfill in weekly batches with delay between."""
    current = start_date
    while current < end_date:
        batch_end = min(current + timedelta(days=batch_size), end_date)
        process_batch(current, batch_end)
        current = batch_end
        time.sleep(300)  # 5 min gap between batches
        # Check if production pipelines are healthy
        if production_sla_breached():
            pause_backfill()
            wait_for_production_recovery()

# 3. Monitoring: backfill impact on production
- alert: BackfillImpactingProduction
  expr: |
    airflow_pool_used_slots{pool="production"} 
    / airflow_pool_total_slots{pool="production"} > 0.9
    AND airflow_pool_used_slots{pool="backfill"} > 0
```

---

## Issue #67: Late-Arriving Data Missing from Published Reports

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Events Arriving After Partition Closure Not Captured          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Daily (mobile apps, IoT, partner integrations)             │
│                                                                         │
│  SCENARIO:                                                              │
│  Daily pipeline runs at 2 AM, processes yesterday's data               │
│  Mobile app events: some arrive with 6-24 hour delay                  │
│  (phone offline, batch sync, poor connectivity)                        │
│                                                                         │
│  Pipeline closes yesterday's partition at 2 AM                         │
│  Events arriving at 3 AM for yesterday → WHERE DO THEY GO?            │
│  Option A: Lost (pipeline already ran)                                 │
│  Option B: Counted in today's partition (wrong day!)                   │
│  Option C: Manual reprocessing (expensive, delays)                    │
│                                                                         │
│  IMPACT:                                                                │
│  5-10% of mobile events arrive late                                   │
│  → Daily active users under-reported by 5-10%                         │
│  → Revenue attribution incorrect                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Multi-pass processing
# Pass 1: T+2h (95% of data) → "preliminary" report
# Pass 2: T+24h (99.5% of data) → "final" report
# Pass 3: T+72h (99.99% of data) → "revised" report (if material change)

# Airflow DAG
@dag(schedule_interval="0 2 * * *")  # 2 AM daily
def daily_report_pipeline():
    # First pass: preliminary (most data available)
    preliminary = process_day(
        date="{{ ds }}", 
        output_table="reports.preliminary"
    )
    
    # Correction pass: runs 24h later for late data
    @task(trigger_rule="none_failed", 
          execution_timeout=timedelta(hours=1))
    def correction_pass():
        late_events = get_late_events(date="{{ ds }}", since_last_run=True)
        if late_events.count() > threshold:
            reprocess_and_update(date="{{ ds }}")
            notify("Report revised: late data incorporated")

# 2. Iceberg table: MERGE late data into existing partitions
spark.sql("""
    MERGE INTO reports.daily_metrics t
    USING late_events s
    ON t.event_date = s.event_date AND t.user_id = s.user_id
    WHEN MATCHED THEN UPDATE SET 
        event_count = t.event_count + s.event_count
    WHEN NOT MATCHED THEN INSERT *
""")

# 3. Monitor late arrival rate
- alert: HighLateArrivalRate
  expr: |
    late_events_count{delay_bucket=">24h"} / total_events_count > 0.05
  annotations:
    summary: "More than 5% of events arriving >24h late"
```

---

## Issue #68: Pipeline Dependency Failure Cascade (DAG Domino Effect)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: One Failed Pipeline Blocks 50 Downstream Pipelines            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Weekly                                                     │
│                                                                         │
│  SCENARIO:                                                              │
│  Pipeline dependency tree:                                              │
│  raw_events → cleaned_events → user_sessions → analytics_daily        │
│                              → fraud_features → fraud_model_training   │
│                              → recommendation_features → rec_model     │
│                                                                         │
│  raw_events pipeline fails (source API timeout)                        │
│  → ALL 6 downstream pipelines blocked                                  │
│  → DAG shows 50 tasks in "upstream_failed" state                      │
│  → One 5-minute API timeout → 6 hours of delayed reports              │
│                                                                         │
│  CASCADING TIME AMPLIFICATION:                                          │
│  Root failure: 5 minutes to resolve                                    │
│  But: all downstream scheduled after → +1 hour to clear queue         │
│  Total impact: 6 hours of delayed analytics                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Graceful degradation (process with partial data)
@task(trigger_rule="all_done")  # Run even if upstream failed
def analytics_with_fallback(**context):
    if upstream_succeeded():
        process_full_data()
    else:
        # Use last known good data + flag as partial
        process_with_stale_data(flag="PARTIAL")
        alert_data_staleness()

# 2. Independent retry with exponential backoff
default_args = {
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
}

# 3. Priority-based downstream execution
# When root recovers: run critical paths first
# fraud_features → PRIORITY 1 (business critical)
# recommendation_features → PRIORITY 2 (can wait)
# analytics_daily → PRIORITY 3 (informational)

# 4. Circuit breaker on dependencies
# If upstream fails 3x in a row → skip and use cached
# Don't keep retrying a dead upstream
@task
def fetch_with_circuit_breaker(source_table):
    if circuit_breaker.is_open(source_table):
        return get_cached_version(source_table)
    try:
        data = fetch_fresh(source_table)
        circuit_breaker.record_success(source_table)
        return data
    except Exception:
        circuit_breaker.record_failure(source_table)
        return get_cached_version(source_table)
```

---

## Issue #69: Data Freshness SLA Breach Not Detected Until Customer Complains

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Dashboard Data is 6 Hours Stale, Nobody Notices               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Weekly (especially for non-critical pipelines)             │
│                                                                         │
│  SCENARIO:                                                              │
│  Pipeline SLA: data available by 8 AM daily                           │
│  Pipeline hung at 3 AM (deadlocked Spark task)                        │
│  Airflow shows "running" (not failed, so no failure alert)            │
│  → 8 AM: Dashboard shows yesterday's data (stale)                    │
│  → Business team uses stale data for decisions until 10 AM            │
│  → 10 AM: Product manager notices data is old, files ticket           │
│  → 2 hours of decisions made on stale data                           │
│                                                                         │
│  KEY INSIGHT:                                                           │
│  "Running" ≠ "Healthy". Long-running task is often hung.              │
│  No failure = no alert, but SLA still breached.                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. SLA monitoring independent of pipeline status
- alert: DataFreshnessSLABreach
  expr: |
    time() - data_last_updated_timestamp{table="analytics_daily"} > 21600  # 6 hours
  for: 0m
  labels:
    severity: critical
  annotations:
    summary: "Table {{ $labels.table }} data is {{ $value | humanizeDuration }} old"

# 2. Expected completion time alert
- alert: PipelineOverdue
  expr: |
    time() > on(dag_id) group_left 
      airflow_dag_expected_completion_time
    AND airflow_dag_state == "running"
  annotations:
    summary: "Pipeline {{ $labels.dag_id }} still running past expected completion"

# 3. Stuck task detection
- alert: AirflowTaskStuck
  expr: |
    airflow_task_duration_seconds{state="running"} 
    > 3 * avg_over_time(airflow_task_duration_seconds{state="success"}[7d])
  annotations:
    summary: "Task running 3x longer than historical average - likely hung"

# 4. End-user freshness indicator
# Add "Last Updated: 2 hours ago" badge on every dashboard
# Visual indicator: Green (<1h), Yellow (1-4h), Red (>4h)
```

---

## Issue #70: Partition Skew Causing Pipeline Timeout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: One Partition Has 100x Data → Causes Timeout                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: During anomalous events (viral content, bot attacks)       │
│                                                                         │
│  SCENARIO:                                                              │
│  Pipeline partitions user_events by user_id hash % 100                │
│  Normal: each partition ≈ 1GB                                          │
│  Viral event: one celebrity user generates 100GB of events             │
│  → That partition takes 100x longer to process                        │
│  → Pipeline timeout at 2 hours → fails                                │
│  → Other 99 partitions completed in 5 minutes, waiting for one        │
│                                                                         │
│  VARIANTS:                                                              │
│  - Date partition: one day has 10x data (Black Friday)                │
│  - Key skew in joins: null keys create monster partition               │
│  - Geographic: US partition 50x larger than others                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Skew detection before processing
partition_sizes = spark.sql("""
    SELECT partition_key, COUNT(*) as cnt, 
           SUM(size_bytes) as bytes
    FROM raw_events
    GROUP BY partition_key
""")

max_size = partition_sizes.agg({"bytes": "max"}).collect()[0][0]
avg_size = partition_sizes.agg({"bytes": "avg"}).collect()[0][0]
skew_ratio = max_size / avg_size

if skew_ratio > 10:
    alert(f"Partition skew detected: {skew_ratio}x")
    # Use salting or adaptive partitioning

# 2. Spark AQE (Adaptive Query Execution)
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")

# 3. Salting for known hot keys
# Add random salt to hot keys to spread across partitions
df = df.withColumn("salt", 
    when(col("user_id").isin(hot_users), 
         concat(col("user_id"), lit("_"), (rand() * 10).cast("int")))
    .otherwise(col("user_id"))
)

# 4. Monitor per-partition processing time
- alert: PartitionSkew
  expr: |
    max(task_duration_seconds) by (job) 
    / avg(task_duration_seconds) by (job) > 10
```

---

## Issue #71: CDC Event Ordering Violation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Out-of-Order CDC Events Produce Incorrect State               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: During Kafka partition rebalancing or multi-source CDC     │
│                                                                         │
│  SCENARIO:                                                              │
│  Order lifecycle: CREATED → PAID → SHIPPED → DELIVERED                │
│  CDC events arrive out of order:                                       │
│  [PAID, CREATED, DELIVERED, SHIPPED]                                   │
│                                                                         │
│  If pipeline applies events in arrival order:                          │
│  State after PAID: status=PAID (correct at that point)                │
│  State after CREATED: status=CREATED (WRONG! Goes backward)           │
│  → Final state shows SHIPPED instead of DELIVERED                     │
│                                                                         │
│  CAUSES:                                                                │
│  - Kafka partition reassignment during consumer group rebalance       │
│  - Multiple source databases with different transaction timestamps    │
│  - Network delays between source and Kafka                            │
│  - Debezium connector restart replaying from snapshot                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. Event ordering by source timestamp (not arrival time)
# Always include source_timestamp in CDC events
# Apply events sorted by source_timestamp

def apply_cdc_events(events):
    # Sort by source transaction timestamp, not Kafka offset
    sorted_events = sorted(events, key=lambda e: e.source_ts)
    for event in sorted_events:
        apply_event(event)

# 2. Last-writer-wins with timestamp comparison
spark.sql("""
    MERGE INTO target.orders t
    USING cdc_events s
    ON t.order_id = s.order_id
    WHEN MATCHED AND s.source_ts > t.last_updated_ts THEN
        UPDATE SET status = s.status, last_updated_ts = s.source_ts
    WHEN NOT MATCHED THEN
        INSERT (order_id, status, last_updated_ts) 
        VALUES (s.order_id, s.status, s.source_ts)
""")
# Only apply event if it's newer than current state

# 3. Monitor out-of-order events
out_of_order_count = events.filter(
    col("kafka_timestamp") - col("source_timestamp") > timedelta(minutes=5)
).count()

if out_of_order_count > threshold:
    alert(f"Out-of-order events detected: {out_of_order_count}")
```

---

## Issue #72: Resource Contention Between Monitoring and Production

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Data Quality Checks Consuming Production Cluster Resources    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Daily during quality validation windows                    │
│                                                                         │
│  SCENARIO:                                                              │
│  Great Expectations validation runs on production Spark cluster        │
│  → Full table scan for uniqueness check (SELECT COUNT(DISTINCT ...))  │
│  → 500GB shuffle → eats 80% of cluster memory                        │
│  → Production ETL jobs queued behind validation                       │
│  → ETL SLA breached because monitoring consumed resources             │
│  → THE MONITORING CAUSES THE SLA BREACH IT'S SUPPOSED TO DETECT      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Sample-based validation (don't scan full table)
# Instead of COUNT(DISTINCT col) on 1B rows:
# Sample 1% → validate → extrapolate
validation_config:
  sampling:
    enabled: true
    strategy: stratified  # Sample from each partition
    rate: 0.01  # 1%
    min_sample_size: 100000

# 2. Dedicated monitoring cluster/queue
# Separate resource pool for validation jobs
spark.conf.set("spark.scheduler.pool", "monitoring")
# Pool has capped resources, can't starve production

# 3. Lightweight statistical checks (no full scan)
# Use pre-computed statistics (Iceberg table stats)
# Column stats available without scanning:
# - min/max values
# - null count
# - distinct count (approximate via HLL)

# 4. Schedule validation after production SLA met
# Production ETL: 2 AM - 6 AM (SLA: done by 6 AM)
# Validation: 6 AM - 7 AM (only after production complete)
# If validation fails: alert but don't block downstream
```

---

## Issue #73: Metric Semantic Change Without Documentation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Metric Definition Changed, Dashboards Now Wrong               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium, but high business impact)                       │
│  Frequency: Quarterly (definition changes during refactoring)          │
│                                                                         │
│  SCENARIO:                                                              │
│  "Active Users" metric defined as: users with login in last 30 days   │
│  Team refactors: changes to "users with ANY event in last 30 days"   │
│  → Active users jumps 40% overnight (more events than logins)         │
│  → No code error, no pipeline failure, no alert                       │
│  → Executive report: "DAU grew 40% month-over-month!"                 │
│  → Actually: definition change, not real growth                       │
│  → Discovered during board meeting Q&A → embarrassment               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Metric registry with versioned definitions
# metrics/active_users.yaml
metric:
  name: active_users_daily
  version: "2.0"
  definition: "Count of users with any event in last 30 days"
  previous_version: "1.0"
  previous_definition: "Count of users with login event in last 30 days"
  changed_date: "2024-01-15"
  change_reason: "Include app events, not just logins (JIRA-4567)"
  owner: growth-team
  consumers:
    - executive-dashboard
    - investor-reporting
    - product-analytics

# 2. Metric change detection
- alert: MetricDefinitionChange
  expr: |
    abs(
      avg_over_time(active_users_daily[1d]) 
      - avg_over_time(active_users_daily[1d] offset 1d)
    ) / avg_over_time(active_users_daily[1d] offset 1d) > 0.2
  annotations:
    summary: "Active users changed by >20% day-over-day. Verify no definition change."

# 3. Semantic versioning for metrics
# v1.x → backward compatible (additive filters)
# v2.x → breaking change (different definition)
# When v2 deployed: old and new run in parallel for 2 weeks
# Compare outputs, document difference, migrate consumers
```

---

## Issue #74: Incomplete Data Lineage (Can't Trace Data Origin)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Can't Answer "Where Did This Wrong Number Come From?"         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium, P0 during compliance audits)                    │
│  Frequency: Every data quality investigation                           │
│                                                                         │
│  SCENARIO:                                                              │
│  CFO: "Revenue dashboard shows $10M but finance says $9.5M.           │
│  Where does the $500K difference come from?"                          │
│                                                                         │
│  Investigation:                                                         │
│  Dashboard → Metric table → 5 upstream transformations →              │
│  3 source systems → ???                                                │
│  Which transformation added the $500K? Which source is wrong?         │
│  No lineage → manually trace through code → 2 days of investigation  │
│                                                                         │
│  COMPLIANCE:                                                            │
│  Auditor: "Prove this financial number traces to source systems"      │
│  Team: "We... can't. The pipeline is too complex."                   │
│  Auditor: "Finding."                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```python
# 1. OpenLineage integration across all tools
# Spark: automatic lineage capture
spark.conf.set("spark.openlineage.transport.type", "kafka")
spark.conf.set("spark.openlineage.transport.topicName", "openlineage.events")
spark.conf.set("spark.openlineage.namespace", "production")

# Airflow: OpenLineage provider
# pip install apache-airflow-providers-openlineage
# Automatically emits lineage for all operators

# dbt: built-in lineage via manifest.json + OpenLineage integration

# 2. Column-level lineage tracking
# Track: target_column = f(source_columns)
# revenue_total = SUM(orders.amount) + SUM(refunds.amount * -1)
# → Can trace exactly which source columns affect revenue_total

# 3. Lineage-aware impact analysis
# Before any change, query lineage graph:
# "If I modify table X, what downstream dashboards are affected?"
affected = lineage_api.get_downstream_consumers("raw.payments")
# Returns: [transformation_1, metric_table, dashboard_revenue, ...]

# 4. Monitor lineage completeness
- alert: LineageGap
  expr: |
    openlineage_events_emitted{job_type="spark"} == 0 
    AND airflow_task_completed{task_type="spark"} > 0
  annotations:
    summary: "Spark jobs completing without emitting lineage events"
```

---

## Issue #75: Cost Anomaly in Data Pipeline (Unexpected $100K Bill)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Monthly Cloud Bill Spikes 5x Due to Pipeline Bug              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High - Financial)                                       │
│  Frequency: Quarterly                                                   │
│                                                                         │
│  SCENARIO:                                                              │
│  Pipeline bug: infinite retry loop on failed partition                 │
│  → Spark job restarts 200 times/day (each spin-up = 500 executors)   │
│  → EMR cost: $0.50/executor/hour × 500 × 24h × 200 retries          │
│  → $1.2M extra cost in one week before detected                      │
│                                                                         │
│  OTHER VARIANTS:                                                        │
│  - Cartesian join (output 1TB instead of 1GB) → S3 costs spike       │
│  - Full table scan instead of partition pruning → 100x compute        │
│  - Uncompressed Parquet → 5x storage costs                            │
│  - Cross-region data transfer → network costs spike                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Real-time cost monitoring per pipeline
- alert: PipelineCostAnomaly
  expr: |
    pipeline_cost_dollars_last_hour > 
    3 * avg_over_time(pipeline_cost_dollars_last_hour[7d:1h])
  for: 30m
  annotations:
    summary: "Pipeline {{ $labels.pipeline }} cost 3x higher than baseline"
    estimated_daily: "{{ $value | multiply 24 | humanize }} dollars"

# 2. Resource guardrails
# Max executor count per job
spark.conf.set("spark.dynamicAllocation.maxExecutors", "100")
# Max retry count
default_args = {'retries': 3}  # Not unlimited!
# Max runtime
execution_timeout = timedelta(hours=4)  # Kill if exceeds

# 3. Cost attribution per team
# Tag all resources with team/pipeline
# Weekly cost report per team
# Alert team if their monthly budget tracking > 120%

# 4. Pre-commit cost estimation
# Before deploying pipeline change:
# Estimate: new_query_plan.estimated_bytes_scanned
# Compare: vs current query plan
# If 5x more → require approval
```

---

## Summary: Data Quality & Pipeline Reliability Issues

| # | Issue | Severity | Detection Difficulty |
|---|-------|----------|---------------------|
| 61 | Silent data corruption | P0 | Very Hard (no errors) |
| 62 | Schema drift cascade | P1 | Medium (errors downstream) |
| 63 | NULL flood corrupting aggregations | P1 | Hard (no errors, wrong results) |
| 64 | Timezone/DST bugs | P1 | Hard (periodic, subtle) |
| 65 | Idempotency failure (duplicates) | P1 | Medium (count checks) |
| 66 | Backfill starving production | P1 | Easy (SLA breach visible) |
| 67 | Late-arriving data missed | P1 | Medium (needs freshness tracking) |
| 68 | DAG dependency cascade | P1 | Easy (Airflow shows) |
| 69 | Freshness SLA breach undetected | P1 | Medium (need external monitor) |
| 70 | Partition skew timeout | P1 | Easy (task duration anomaly) |
| 71 | CDC ordering violation | P1 | Hard (state looks wrong later) |
| 72 | Monitoring consuming prod resources | P1 | Medium (resource contention) |
| 73 | Metric semantic change | P2 | Very Hard (no technical error) |
| 74 | Incomplete lineage | P2 | Hard (discovered during incidents) |
| 75 | Cost anomaly from pipeline bug | P1 | Medium (billing delay) |
