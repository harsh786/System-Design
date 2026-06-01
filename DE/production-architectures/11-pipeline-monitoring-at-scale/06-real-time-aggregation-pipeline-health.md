# Real-Time Aggregation Pipeline Health Monitoring

## Problem Statement

Real-time dashboards and alerting systems depend on correctly aggregated metrics. Late data, out-of-order events, and exactly-once failures produce incorrect aggregations that drive wrong business decisions. At 1M events/sec, even 0.01% errors mean 100 wrong aggregations per second—potentially triggering false alerts, hiding real incidents, or misrepresenting revenue figures.

The fundamental challenges of real-time aggregation:
- **Time is not linear**: Events arrive out of order due to network delays, mobile offline periods, and distributed system clock skew
- **Exactly-once is fragile**: A single checkpoint failure can cause duplicates or data loss
- **Windows are approximate**: You never truly know when all events for a time window have arrived
- **State grows unboundedly**: Without careful management, stateful operators consume all available memory

A streaming aggregation that silently drops 0.1% of events will show metrics that are consistently slightly wrong—just enough to be dangerous but not enough to be obviously broken.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│           REAL-TIME AGGREGATION PIPELINE WITH MONITORING                          │
└─────────────────────────────────────────────────────────────────────────────────┘

 ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
 │  Mobile  │  │   Web    │  │   IoT    │  │  Backend │
 │  Events  │  │  Events  │  │ Sensors  │  │  Events  │
 └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
      │              │              │              │
      │   Event Time │    Clock     │   Network    │
      │   Skew: ±30s │   Skew: ±5s │   Delay: 2m  │
      ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KAFKA (Event Bus)                                     │
│                                                                              │
│  Topic: raw_events (partitions=128, retention=7d)                           │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  MONITOR: Produce rate, partition lag, message size, ordering     │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    APACHE FLINK (Stream Processing)                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Flink Job Graph                                    │    │
│  │                                                                      │    │
│  │  KafkaSource ──► Deserialize ──► Watermark ──► KeyBy ──► Window     │    │
│  │       │              │             │              │          │        │    │
│  │       │              │             │              │          ▼        │    │
│  │       │              │             │              │      Aggregate    │    │
│  │       │              │             │              │          │        │    │
│  │       │              │             │              │          ▼        │    │
│  │       │              │             │              │     Sink(s)      │    │
│  │       │              │             │              │      │    │      │    │
│  │       │              │             │              │      ▼    ▼      │    │
│  │       │              │             │              │   Druid  Kafka   │    │
│  │       │              │             │              │          (out)   │    │
│  └───────┼──────────────┼─────────────┼──────────────┼──────────────────┘    │
│          │              │             │              │                        │
│  ┌───────┴──────────────┴─────────────┴──────────────┴──────────────────┐    │
│  │  MONITOR TAPS:                                                        │    │
│  │  • Consumer lag          • Deserialization errors                     │    │
│  │  • Watermark progression • Backpressure (busy time)                  │    │
│  │  • Late events count     • Checkpoint duration/size                  │    │
│  │  • State size            • Output rate                               │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                          ▼                 ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│     DRUID / CLICKHOUSE      │  │    KAFKA (Output Topics)     │
│     (OLAP Queries)          │  │    (Downstream Consumers)    │
│                             │  │                              │
│  Real-time dashboards       │  │  Alerting systems            │
│  Ad-hoc analytics           │  │  ML feature pipelines        │
│                             │  │  Billing aggregation          │
│  ┌───────────────────────┐  │  │                              │
│  │ MONITOR: Query latency,│  │  │  ┌────────────────────────┐ │
│  │ segment count, ingestion│  │  │  │ MONITOR: Consumer lag, │ │
│  │ lag                    │  │  │  │ duplicate detection     │ │
│  └───────────────────────┘  │  │  └────────────────────────┘ │
└─────────────────────────────┘  └─────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    BATCH VALIDATION LAYER                                     │
│                                                                              │
│  Hourly batch job recomputes aggregations and compares with streaming       │
│  output. Discrepancies indicate exactly-once violations or late data issues.│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Streaming Output vs Batch Recomputation:                            │    │
│  │    Window [10:00-10:05]: Streaming=1,234,567 | Batch=1,234,589       │    │
│  │    Difference: 22 events (0.0018%) ← Within SLA                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Watermark and Late Data Flow

```
Event Time ────────────────────────────────────────────────────────►

  Events arriving:
  
  Processing Time
       │
  T+0  │  ●(10:01) ●(10:02) ●(10:03)          Normal events
  T+1  │  ●(10:04) ●(10:05)                    Normal events
  T+2  │  ●(10:06) ●(10:07) ●(10:01)           ← LATE! (10:01 arrives at T+2)
  T+3  │  ●(10:08)          ●(09:58)           ← VERY LATE! (09:58 arrives at T+3)
       │
       │  Watermark ═══════════════►
       │  (max_event_time - allowed_lateness)
       │
       │  Window [10:00-10:05] closes when watermark passes 10:05
       │  
       │  Events before watermark: PROCESSED normally
       │  Events after watermark:  LATE → side output → batch correction
       ▼
```

---

## Critical Monitoring Points

### 1. Watermark Progression

The watermark represents the system's confidence that no more events with timestamp ≤ watermark will arrive. If watermarks stop advancing, windows never close and state grows unboundedly.

```
HEALTHY watermark progression:
  Time  │  Watermark
  ──────┼────────────
  00:01 │  09:59:30
  00:02 │  10:00:30   (+60s in 60s ✓)
  00:03 │  10:01:30   (+60s in 60s ✓)
  00:04 │  10:02:30   (+60s in 60s ✓)

UNHEALTHY watermark progression:
  Time  │  Watermark
  ──────┼────────────
  00:01 │  09:59:30
  00:02 │  09:59:30   (STALLED ⚠️)
  00:03 │  09:59:30   (STALLED ⚠️⚠️)
  00:04 │  09:59:35   (+5s in 180s ❌ CRITICAL)
```

### 2. Late Data Rate

Track events arriving after their window has closed, bucketed by lateness:

| Lateness Bucket | Acceptable Rate | Action |
|----------------|----------------|--------|
| < 1 min | < 5% | Normal side output |
| 1-5 min | < 1% | Warning |
| 5 min - 1 hr | < 0.1% | Batch correction triggered |
| > 1 hr | < 0.001% | Investigate source system |

### 3. Window Completeness

Did we see all expected events for a given window? Compare event count per window against expected baseline.

### 4. Exactly-Once Verification

Checkpoint barriers must flow through all operators. If a barrier is delayed, it indicates backpressure or operator issues.

### 5. Aggregation Accuracy

Periodically recompute aggregations in batch and compare against streaming output. Acceptable discrepancy depends on SLA.

### 6. Output Consistency

The same window must not produce multiple conflicting results (can happen during failover/recovery).

---

## Flink-Specific Monitoring Deep Dive

### Key Metrics

```
┌─────────────────────────────────────────────────────────────────┐
│              FLINK MONITORING METRICS HIERARCHY                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  JOB LEVEL                                                       │
│  ├── numRestarts: total restarts (should be low)                │
│  ├── uptime: milliseconds since last restart                    │
│  ├── lastCheckpointDuration: time to complete checkpoint        │
│  ├── lastCheckpointSize: bytes persisted in checkpoint          │
│  └── numberOfFailedCheckpoints: (should be 0)                   │
│                                                                  │
│  TASK LEVEL                                                      │
│  ├── numRecordsIn / numRecordsOut: throughput                   │
│  ├── numRecordsInPerSecond / numRecordsOutPerSecond             │
│  ├── currentInputWatermark: watermark at this operator          │
│  ├── busyTimeMsPerSecond: backpressure indicator (>800 = bad)   │
│  ├── backPressuredTimeMsPerSecond: direct backpressure time     │
│  └── numBuffersInLocalPerSecond: network buffer usage           │
│                                                                  │
│  OPERATOR LEVEL                                                  │
│  ├── numLateRecordsDropped: events past allowed lateness        │
│  ├── currentOutputWatermark: watermark emitted by operator      │
│  ├── windowSize: number of elements in current window state     │
│  └── stateSizeBytes: RocksDB state backend size                 │
│                                                                  │
│  CHECKPOINT LEVEL                                                │
│  ├── checkpointAlignmentTime: barrier alignment (skew indicator)│
│  ├── syncDurationMs: synchronous snapshot time                  │
│  ├── asyncDurationMs: asynchronous snapshot time                │
│  └── checkpointedDataSize: actual data written                  │
│                                                                  │
│  KAFKA SOURCE                                                    │
│  ├── KafkaConsumer.records-lag-max: max partition lag           │
│  ├── KafkaConsumer.records-consumed-rate: consumption rate       │
│  └── committedOffsets vs currentOffsets: pending messages        │
│                                                                  │
│  JVM / TASKMANAGER                                               │
│  ├── heap.used / heap.max: memory pressure                      │
│  ├── gc.time / gc.count: garbage collection overhead            │
│  ├── threads.count: thread pool saturation                      │
│  └── cpu.load: task manager CPU utilization                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Backpressure Detection

```
Backpressure propagation through Flink pipeline:

  Source ──► Map ──► KeyBy ──► Window ──► Sink
    ✓         ✓       ✓         ⚠️ SLOW    ✓

When Window operator is slow:
  - Window operator: busyTime=950ms/s (saturated)
  - KeyBy operator:  backPressuredTime=800ms/s (blocked by Window)
  - Map operator:    backPressuredTime=750ms/s (blocked by KeyBy)
  - Source:          backPressuredTime=700ms/s (reading Kafka slower)

Result: Kafka consumer lag increases → watermarks stall → windows delayed

Detection rule:
  IF busyTimeMsPerSecond > 800 for any operator for > 2 minutes
  THEN alert: "Backpressure detected at operator {{ operator_name }}"
```

### State Size Monitoring

```
State growth pattern - HEALTHY:
  ┌────────────────────────────────────────┐
  │     State Size (GB)                     │
  │  4 ┤    ╭─╮    ╭─╮    ╭─╮             │
  │  3 ┤   ╱   ╲  ╱   ╲  ╱   ╲            │  Windows fill and empty
  │  2 ┤  ╱     ╲╱     ╲╱     ╲           │  predictably
  │  1 ┤─╱                      ╲──        │
  │  0 ┤────────────────────────────────    │
  │    └──┬──┬──┬──┬──┬──┬──┬──┬──┬──     │
  │       00 03 06 09 12 15 18 21 24       │
  └────────────────────────────────────────┘

State growth pattern - UNHEALTHY (leak):
  ┌────────────────────────────────────────┐
  │     State Size (GB)                     │
  │ 40 ┤                           ╱       │
  │ 30 ┤                      ╱╱╱╱         │  Unbounded growth!
  │ 20 ┤                ╱╱╱╱╱              │  State never cleaned
  │ 10 ┤          ╱╱╱╱╱                    │
  │  0 ┤───╱╱╱╱╱                           │
  │    └──┬──┬──┬──┬──┬──┬──┬──┬──┬──     │
  │       00 03 06 09 12 15 18 21 24       │
  └────────────────────────────────────────┘
  ⚠️ Will OOM within 48 hours at this rate
```

---

## Late Data Monitoring Pattern

### Lateness Bucketing

```python
"""
late_data_monitor.py
Monitors late event rates bucketed by lateness severity.
Emits metrics for alerting and triggers batch corrections.
"""
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics
LATE_EVENTS_TOTAL = Counter(
    "flink_late_events_total",
    "Total late events by lateness bucket",
    ["job_name", "operator", "lateness_bucket"]
)

LATE_EVENTS_RATIO = Gauge(
    "flink_late_events_ratio",
    "Ratio of late events to total events",
    ["job_name", "operator"]
)

LATENESS_SECONDS = Histogram(
    "flink_event_lateness_seconds",
    "Distribution of event lateness in seconds",
    ["job_name"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 3600, 86400]
)

AFFECTED_WINDOWS = Counter(
    "flink_late_data_affected_windows_total",
    "Windows that received late data after closure",
    ["job_name", "correction_status"]
)


@dataclass
class LateEvent:
    event_time: datetime
    processing_time: datetime
    window_end: datetime
    key: str
    lateness_seconds: float


class LateDataMonitor:
    """
    Monitors late data patterns and triggers batch corrections
    when late events would materially affect aggregation results.
    """
    
    LATENESS_BUCKETS = [
        ("under_1min", 0, 60),
        ("1min_to_5min", 60, 300),
        ("5min_to_1hr", 300, 3600),
        ("over_1hr", 3600, float("inf")),
    ]
    
    # Thresholds for triggering batch correction
    CORRECTION_THRESHOLD_COUNT = 100    # Correct if >100 late events for a window
    CORRECTION_THRESHOLD_RATIO = 0.01   # Correct if >1% of window events are late
    
    def __init__(self, job_name: str):
        self.job_name = job_name
        self.late_events_buffer: List[LateEvent] = []
        self.total_events_count = 0
        self.late_events_count = 0
    
    def record_late_event(self, event: LateEvent):
        """Record a late event and update metrics."""
        self.late_events_count += 1
        self.late_events_buffer.append(event)
        
        # Update Prometheus metrics
        LATENESS_SECONDS.labels(job_name=self.job_name).observe(
            event.lateness_seconds
        )
        
        # Bucket the lateness
        for bucket_name, min_sec, max_sec in self.LATENESS_BUCKETS:
            if min_sec <= event.lateness_seconds < max_sec:
                LATE_EVENTS_TOTAL.labels(
                    job_name=self.job_name,
                    operator="window_aggregate",
                    lateness_bucket=bucket_name,
                ).inc()
                break
        
        # Update ratio
        if self.total_events_count > 0:
            LATE_EVENTS_RATIO.labels(
                job_name=self.job_name,
                operator="window_aggregate",
            ).set(self.late_events_count / self.total_events_count)
    
    def record_on_time_event(self):
        """Record an on-time event (for ratio calculation)."""
        self.total_events_count += 1
    
    def check_correction_needed(self, window_key: str, window_end: datetime) -> bool:
        """
        Check if a batch correction is needed for a specific window.
        Returns True if late events exceed correction threshold.
        """
        window_late_events = [
            e for e in self.late_events_buffer
            if e.window_end == window_end and e.key == window_key
        ]
        
        if len(window_late_events) > self.CORRECTION_THRESHOLD_COUNT:
            AFFECTED_WINDOWS.labels(
                job_name=self.job_name,
                correction_status="triggered"
            ).inc()
            logger.warning(
                f"Batch correction triggered for window {window_key}:{window_end} "
                f"({len(window_late_events)} late events)"
            )
            return True
        
        return False
    
    def get_impact_assessment(self) -> Dict:
        """Assess the impact of late data on aggregation accuracy."""
        if not self.late_events_buffer:
            return {"impact": "none", "affected_windows": 0}
        
        # Group by window
        windows_affected = set()
        for event in self.late_events_buffer:
            windows_affected.add((event.key, event.window_end))
        
        # Calculate severity
        late_ratio = self.late_events_count / max(self.total_events_count, 1)
        
        severity = "low"
        if late_ratio > 0.01:
            severity = "medium"
        if late_ratio > 0.05:
            severity = "high"
        if late_ratio > 0.1:
            severity = "critical"
        
        return {
            "impact": severity,
            "affected_windows": len(windows_affected),
            "total_late_events": self.late_events_count,
            "late_ratio": late_ratio,
            "max_lateness_seconds": max(
                e.lateness_seconds for e in self.late_events_buffer
            ),
            "correction_candidates": sum(
                1 for w in windows_affected
                if self.check_correction_needed(w[0], w[1])
            ),
        }
```

### Side Output and Batch Correction

```python
"""
batch_correction_job.py
Recomputes aggregations for windows affected by significant late data.
Compares with streaming output and publishes corrections.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime, timedelta
from typing import List, Dict


class BatchCorrectionJob:
    """
    Recomputes windowed aggregations for time ranges where
    late data exceeded acceptable thresholds.
    """
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
    
    def correct_windows(
        self,
        source_table: str,
        streaming_output_table: str,
        correction_output_table: str,
        affected_windows: List[Dict],
        window_duration_minutes: int = 5,
    ):
        """
        Recompute aggregations for affected windows and publish corrections.
        
        Args:
            source_table: Raw events table (complete, including late data)
            streaming_output_table: Streaming aggregation results
            correction_output_table: Where to write corrections
            affected_windows: List of {key, window_start, window_end}
            window_duration_minutes: Window size
        """
        
        for window_info in affected_windows:
            key = window_info["key"]
            window_start = window_info["window_start"]
            window_end = window_info["window_end"]
            
            # Recompute from source (includes ALL events, even late ones)
            batch_result = self.spark.sql(f"""
                SELECT
                    '{key}' as aggregation_key,
                    TIMESTAMP '{window_start}' as window_start,
                    TIMESTAMP '{window_end}' as window_end,
                    COUNT(*) as event_count,
                    SUM(value) as total_value,
                    AVG(value) as avg_value,
                    MAX(value) as max_value,
                    MIN(value) as min_value,
                    APPROX_PERCENTILE(value, 0.99) as p99_value
                FROM {source_table}
                WHERE event_time >= TIMESTAMP '{window_start}'
                  AND event_time < TIMESTAMP '{window_end}'
                  AND key = '{key}'
            """)
            
            # Get streaming result for same window
            streaming_result = self.spark.sql(f"""
                SELECT *
                FROM {streaming_output_table}
                WHERE window_start = TIMESTAMP '{window_start}'
                  AND window_end = TIMESTAMP '{window_end}'
                  AND aggregation_key = '{key}'
            """)
            
            batch_row = batch_result.first()
            streaming_row = streaming_result.first()
            
            if batch_row and streaming_row:
                # Calculate discrepancy
                count_diff = batch_row["event_count"] - streaming_row["event_count"]
                value_diff = batch_row["total_value"] - streaming_row["total_value"]
                
                if count_diff != 0 or abs(value_diff) > 0.01:
                    # Write correction
                    correction_df = self.spark.createDataFrame([{
                        "aggregation_key": key,
                        "window_start": window_start,
                        "window_end": window_end,
                        "streaming_count": streaming_row["event_count"],
                        "corrected_count": batch_row["event_count"],
                        "streaming_total": streaming_row["total_value"],
                        "corrected_total": batch_row["total_value"],
                        "count_difference": count_diff,
                        "value_difference": value_diff,
                        "correction_time": datetime.utcnow().isoformat(),
                        "correction_reason": "late_data_threshold_exceeded",
                    }])
                    
                    correction_df.writeTo(correction_output_table).append()
```

---

## Exactly-Once Verification

### End-to-End Verification Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│              EXACTLY-ONCE VERIFICATION LAYERS                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: SOURCE → FLINK                                        │
│  ─────────────────────────────                                  │
│  • Kafka consumer committed offsets match processed offsets     │
│  • No gaps in offset sequence per partition                     │
│  • Verify: last_committed_offset == last_processed_offset      │
│                                                                  │
│  Layer 2: FLINK INTERNAL                                        │
│  ────────────────────────                                       │
│  • Checkpoint barriers complete without timeout                 │
│  • All operators participate in every checkpoint                │
│  • State consistent across checkpoint/restore                   │
│  • Verify: checkpoint_count == expected (no skips)              │
│                                                                  │
│  Layer 3: FLINK → SINK                                          │
│  ──────────────────────                                         │
│  • Kafka producer transactions committed atomically             │
│  • Druid ingestion uses deterministic segment IDs               │
│  • Idempotent writes verified (no duplicates in output)         │
│  • Verify: output_record_count == expected for each window      │
│                                                                  │
│  Layer 4: END-TO-END                                            │
│  ────────────────────                                           │
│  • Source event count == output aggregation input count         │
│  • Batch recomputation matches streaming output (within SLA)    │
│  • No duplicate windows in output                               │
│  • Verify: streaming_result ≈ batch_result (within tolerance)   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Duplicate Detection in Output

```python
"""
duplicate_detector.py
Detects duplicate records in streaming output sinks.
Duplicates indicate exactly-once guarantee violation.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from prometheus_client import Counter, Gauge
import logging

logger = logging.getLogger(__name__)

DUPLICATES_DETECTED = Counter(
    "streaming_output_duplicates_total",
    "Total duplicate records detected in output",
    ["sink", "table"]
)

DUPLICATE_RATE = Gauge(
    "streaming_output_duplicate_rate",
    "Current duplicate rate in output sink",
    ["sink", "table"]
)


class OutputDuplicateDetector:
    """
    Periodically scans output sinks for duplicate records.
    Duplicates indicate checkpoint/transaction failures.
    """
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
    
    def check_druid_duplicates(
        self,
        table: str,
        time_range_hours: int = 1,
        dedup_columns: list = None,
    ) -> Dict:
        """
        Check for duplicate aggregation results in Druid/ClickHouse.
        
        A window should produce exactly ONE result per key.
        Multiple results for same (key, window) = exactly-once violation.
        """
        if dedup_columns is None:
            dedup_columns = ["aggregation_key", "window_start", "window_end"]
        
        dedup_cols_str = ", ".join(dedup_columns)
        
        duplicates_df = self.spark.sql(f"""
            SELECT 
                {dedup_cols_str},
                COUNT(*) as occurrence_count,
                MIN(ingestion_time) as first_seen,
                MAX(ingestion_time) as last_seen
            FROM {table}
            WHERE ingestion_time > NOW() - INTERVAL '{time_range_hours}' HOUR
            GROUP BY {dedup_cols_str}
            HAVING COUNT(*) > 1
            ORDER BY occurrence_count DESC
        """)
        
        duplicate_count = duplicates_df.count()
        
        total_records = self.spark.sql(f"""
            SELECT COUNT(*) as cnt
            FROM {table}
            WHERE ingestion_time > NOW() - INTERVAL '{time_range_hours}' HOUR
        """).first()["cnt"]
        
        rate = duplicate_count / max(total_records, 1)
        
        # Update metrics
        DUPLICATES_DETECTED.labels(sink="druid", table=table).inc(duplicate_count)
        DUPLICATE_RATE.labels(sink="druid", table=table).set(rate)
        
        if duplicate_count > 0:
            logger.error(
                f"EXACTLY-ONCE VIOLATION: {duplicate_count} duplicate windows "
                f"detected in {table} (rate: {rate:.6f})"
            )
            
            # Get sample duplicates for debugging
            samples = duplicates_df.limit(10).collect()
            for row in samples:
                logger.error(
                    f"  Duplicate: key={row['aggregation_key']}, "
                    f"window={row['window_start']}-{row['window_end']}, "
                    f"count={row['occurrence_count']}"
                )
        
        return {
            "table": table,
            "time_range_hours": time_range_hours,
            "total_records": total_records,
            "duplicate_windows": duplicate_count,
            "duplicate_rate": rate,
            "exactly_once_intact": duplicate_count == 0,
        }
    
    def check_kafka_output_duplicates(
        self,
        topic: str,
        key_extractor: callable,
        time_range_hours: int = 1,
    ) -> Dict:
        """
        Check for duplicate messages in Kafka output topic.
        Uses Kafka transaction IDs to detect redelivery.
        """
        output_df = self.spark.read.format("kafka") \
            .option("kafka.bootstrap.servers", "kafka:9092") \
            .option("subscribe", topic) \
            .option("startingOffsets", "latest") \
            .load() \
            .filter(
                F.col("timestamp") > F.current_timestamp() - F.expr(f"INTERVAL {time_range_hours} HOURS")
            )
        
        # Check for duplicate keys (same window result sent twice)
        duplicates = output_df \
            .withColumn("msg_key", F.col("key").cast("string")) \
            .groupBy("msg_key") \
            .agg(
                F.count("*").alias("msg_count"),
                F.min("timestamp").alias("first_ts"),
                F.max("timestamp").alias("last_ts"),
            ) \
            .filter(F.col("msg_count") > 1)
        
        return {
            "topic": topic,
            "duplicate_keys": duplicates.count(),
            "total_messages": output_df.count(),
        }
```

---

## Production Code Examples

### Custom Flink MetricReporter for Prometheus

```java
/**
 * FlinkPrometheusReporter.java
 * Custom metric reporter that exposes Flink metrics to Prometheus
 * with labels for job, operator, and subtask.
 */
package com.company.flink.metrics;

import org.apache.flink.metrics.*;
import org.apache.flink.metrics.reporter.MetricReporter;
import org.apache.flink.metrics.reporter.Scheduled;
import io.prometheus.client.CollectorRegistry;
import io.prometheus.client.exporter.HTTPServer;

import java.util.HashMap;
import java.util.Map;

public class FlinkPrometheusReporter implements MetricReporter, Scheduled {
    
    private final Map<String, io.prometheus.client.Gauge> gauges = new HashMap<>();
    private final Map<String, io.prometheus.client.Counter> counters = new HashMap<>();
    private HTTPServer httpServer;
    
    @Override
    public void open(MetricConfig config) {
        int port = config.getInteger("port", 9249);
        try {
            httpServer = new HTTPServer(port);
        } catch (Exception e) {
            throw new RuntimeException("Failed to start Prometheus HTTP server", e);
        }
    }
    
    @Override
    public void notifyOfAddedMetric(Metric metric, String metricName, MetricGroup group) {
        String fullName = sanitizeMetricName(group.getMetricIdentifier(metricName));
        Map<String, String> labels = extractLabels(group);
        
        if (metric instanceof Gauge) {
            io.prometheus.client.Gauge promGauge = io.prometheus.client.Gauge.build()
                .name(fullName)
                .help(fullName)
                .labelNames(labels.keySet().toArray(new String[0]))
                .register();
            gauges.put(fullName, promGauge);
        } else if (metric instanceof Counter) {
            io.prometheus.client.Counter promCounter = io.prometheus.client.Counter.build()
                .name(fullName)
                .help(fullName)
                .labelNames(labels.keySet().toArray(new String[0]))
                .register();
            counters.put(fullName, promCounter);
        }
    }
    
    @Override
    public void report() {
        // Metrics are automatically scraped by Prometheus via HTTP server
        // This method can be used for additional push-based reporting
    }
    
    private Map<String, String> extractLabels(MetricGroup group) {
        Map<String, String> labels = new HashMap<>();
        labels.put("job_name", group.getAllVariables().getOrDefault("<job_name>", "unknown"));
        labels.put("operator_name", group.getAllVariables().getOrDefault("<operator_name>", "unknown"));
        labels.put("subtask_index", group.getAllVariables().getOrDefault("<subtask_index>", "0"));
        labels.put("task_name", group.getAllVariables().getOrDefault("<task_name>", "unknown"));
        return labels;
    }
    
    private String sanitizeMetricName(String name) {
        return name.replaceAll("[^a-zA-Z0-9_]", "_").toLowerCase();
    }
    
    @Override
    public void close() {
        if (httpServer != null) {
            httpServer.stop();
        }
    }
}
```

### Aggregation Accuracy Validator

```python
"""
accuracy_validator.py
Compares streaming aggregation output against batch recomputation
to verify correctness within acceptable tolerance.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class AccuracyResult:
    window_start: str
    window_end: str
    aggregation_key: str
    streaming_value: float
    batch_value: float
    absolute_error: float
    relative_error: float
    within_tolerance: bool


class AggregationAccuracyValidator:
    """
    Validates streaming aggregation accuracy by comparing against
    batch recomputation (source of truth).
    
    Runs hourly to catch:
    - Exactly-once violations (duplicates/missing)
    - Late data impact
    - Aggregation logic bugs
    """
    
    # Acceptable relative error (streaming vs batch)
    TOLERANCE_RELATIVE = 0.001  # 0.1%
    TOLERANCE_ABSOLUTE = 1.0    # 1 unit
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
    
    def validate_window_range(
        self,
        streaming_table: str,
        source_events_table: str,
        start_time: str,
        end_time: str,
        window_duration_minutes: int = 5,
        aggregation_key_col: str = "aggregation_key",
        value_col: str = "total_value",
    ) -> List[AccuracyResult]:
        """
        Compare streaming output against batch-computed ground truth
        for a range of windows.
        """
        
        # Get streaming results
        streaming_df = self.spark.sql(f"""
            SELECT 
                window_start,
                window_end,
                {aggregation_key_col},
                {value_col} as streaming_value,
                event_count as streaming_count
            FROM {streaming_table}
            WHERE window_start >= TIMESTAMP '{start_time}'
              AND window_end <= TIMESTAMP '{end_time}'
        """)
        
        # Recompute from source events (ground truth)
        batch_df = self.spark.sql(f"""
            SELECT
                window(event_time, '{window_duration_minutes} minutes').start as window_start,
                window(event_time, '{window_duration_minutes} minutes').end as window_end,
                {aggregation_key_col},
                SUM(value) as batch_value,
                COUNT(*) as batch_count
            FROM {source_events_table}
            WHERE event_time >= TIMESTAMP '{start_time}'
              AND event_time < TIMESTAMP '{end_time}'
            GROUP BY 
                window(event_time, '{window_duration_minutes} minutes'),
                {aggregation_key_col}
        """)
        
        # Join and compare
        comparison_df = streaming_df.join(
            batch_df,
            on=["window_start", "window_end", aggregation_key_col],
            how="full_outer"
        ).withColumn(
            "absolute_error",
            F.abs(F.coalesce(F.col("streaming_value"), F.lit(0)) - 
                  F.coalesce(F.col("batch_value"), F.lit(0)))
        ).withColumn(
            "relative_error",
            F.when(F.col("batch_value") != 0,
                   F.col("absolute_error") / F.abs(F.col("batch_value")))
            .otherwise(F.when(F.col("streaming_value") != 0, F.lit(1.0)).otherwise(F.lit(0.0)))
        ).withColumn(
            "within_tolerance",
            (F.col("relative_error") <= self.TOLERANCE_RELATIVE) |
            (F.col("absolute_error") <= self.TOLERANCE_ABSOLUTE)
        )
        
        # Find violations
        violations = comparison_df.filter(~F.col("within_tolerance"))
        violation_count = violations.count()
        total_windows = comparison_df.count()
        
        if violation_count > 0:
            logger.error(
                f"ACCURACY VIOLATION: {violation_count}/{total_windows} windows "
                f"exceed tolerance ({start_time} to {end_time})"
            )
            
            # Log worst offenders
            worst = violations.orderBy(F.col("relative_error").desc()).limit(5).collect()
            for row in worst:
                logger.error(
                    f"  Window {row['window_start']}-{row['window_end']} "
                    f"key={row[aggregation_key_col]}: "
                    f"streaming={row['streaming_value']}, batch={row['batch_value']}, "
                    f"error={row['relative_error']:.4%}"
                )
        else:
            logger.info(
                f"Accuracy validation PASSED: {total_windows} windows within tolerance"
            )
        
        # Persist comparison results
        comparison_df.writeTo("monitoring.aggregation_accuracy_checks").append()
        
        return comparison_df.collect()
```

### Watermark Lag Alert Rule

```yaml
# streaming_alerts.yml
groups:
  - name: flink_streaming_health
    rules:
      # Watermark stalled (not advancing)
      - alert: WatermarkStalled
        expr: |
          rate(flink_taskmanager_job_task_operator_currentInputWatermark[5m]) == 0
          AND flink_taskmanager_job_task_operator_currentInputWatermark > 0
        for: 3m
        labels:
          severity: critical
          team: streaming-platform
        annotations:
          summary: "Watermark stalled for operator {{ $labels.operator_name }}"
          description: |
            Watermark has not advanced in 3 minutes.
            Current watermark: {{ $value }}
            This means windows are not closing and state is growing unboundedly.
            Possible causes:
            - Source partition with no data (idle partition)
            - Backpressure preventing event processing
            - Source system outage
          runbook_url: "https://wiki.internal/runbooks/watermark-stall"

      # Watermark lag too high
      - alert: WatermarkLagHigh
        expr: |
          (time() * 1000) - flink_taskmanager_job_task_operator_currentInputWatermark
          > 300000
        for: 2m
        labels:
          severity: warning
          team: streaming-platform
        annotations:
          summary: "Watermark lag >5 minutes for {{ $labels.operator_name }}"
          description: "Aggregation results are delayed by >5 minutes from real-time."

      # Checkpoint duration increasing
      - alert: CheckpointDurationHigh
        expr: flink_jobmanager_job_lastCheckpointDuration > 60000
        for: 5m
        labels:
          severity: warning
          team: streaming-platform
        annotations:
          summary: "Checkpoint taking >60s for job {{ $labels.job_name }}"
          description: |
            Long checkpoints indicate large state or slow state backend.
            Duration: {{ $value }}ms
            Risk: If checkpoint exceeds timeout, job will restart.

      # Checkpoint failures
      - alert: CheckpointFailing
        expr: increase(flink_jobmanager_job_numberOfFailedCheckpoints[10m]) > 0
        for: 0m
        labels:
          severity: critical
          team: streaming-platform
        annotations:
          summary: "Checkpoint failures detected for {{ $labels.job_name }}"
          description: |
            Failed checkpoints mean exactly-once guarantees are at risk.
            If the job restarts, it will reprocess from last successful checkpoint.
            This WILL cause duplicate outputs if sink is not idempotent.

      # Backpressure
      - alert: BackpressureDetected
        expr: flink_taskmanager_job_task_busyTimeMsPerSecond > 900
        for: 3m
        labels:
          severity: warning
          team: streaming-platform
        annotations:
          summary: "Backpressure at {{ $labels.task_name }} ({{ $value }}ms/s busy)"
          description: |
            Operator is saturated (>90% busy).
            Upstream operators will be blocked.
            Consider: scaling parallelism, optimizing operator logic, or 
            reducing input rate.

      # State size growth
      - alert: StateSizeGrowthAnomaly
        expr: |
          predict_linear(flink_taskmanager_job_task_operator_state_size_bytes[1h], 3600*24)
          > flink_taskmanager_job_task_operator_state_size_bytes * 10
        for: 30m
        labels:
          severity: warning
          team: streaming-platform
        annotations:
          summary: "State growing rapidly for {{ $labels.operator_name }}"
          description: |
            State predicted to grow 10x within 24 hours.
            Current size: {{ $value }} bytes
            Possible state leak - windows or timers not being cleaned up.

      # Late events spike
      - alert: LateEventsSpike
        expr: |
          rate(flink_late_events_total{lateness_bucket="over_1hr"}[5m]) > 10
        for: 5m
        labels:
          severity: warning
          team: streaming-platform
        annotations:
          summary: "Spike in very late events (>1hr lateness)"
          description: |
            {{ $value }} events/sec arriving >1 hour late.
            These events are dropped from streaming aggregation.
            Batch correction may be needed.

      # Exactly-once violation
      - alert: ExactlyOnceViolation
        expr: streaming_output_duplicates_total > 0
        for: 0m
        labels:
          severity: critical
          team: streaming-platform
        annotations:
          summary: "Duplicate outputs detected - exactly-once violated"
          description: |
            Sink: {{ $labels.sink }}
            Table: {{ $labels.table }}
            Duplicates: {{ $value }}
            Downstream systems may have incorrect aggregations.

      # Aggregation accuracy breach
      - alert: AggregationAccuracyBreach
        expr: |
          streaming_accuracy_violation_windows / streaming_accuracy_total_windows > 0.01
        for: 10m
        labels:
          severity: critical
          team: streaming-platform
        annotations:
          summary: ">1% of windows exceed accuracy tolerance"
          description: |
            Streaming aggregations diverge significantly from batch truth.
            Violation rate: {{ $value | humanizePercentage }}
            Action: Review checkpoint health, late data rates, and 
            exactly-once guarantees.
```

### State Size Growth Predictor

```python
"""
state_size_predictor.py
Predicts when Flink state will exceed capacity based on growth trends.
Enables proactive scaling before OOM.
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from prometheus_client import Gauge
import logging

logger = logging.getLogger(__name__)

STATE_OOM_PREDICTION_HOURS = Gauge(
    "flink_state_oom_prediction_hours",
    "Predicted hours until state exceeds memory limit",
    ["job_name", "operator"]
)


class StateSizePredictor:
    """
    Analyzes state size trends and predicts when operator state
    will exceed configured limits. Enables proactive scaling.
    """
    
    def __init__(self, max_state_bytes: int):
        """
        Args:
            max_state_bytes: Maximum state size before OOM (typically 80% of TM heap)
        """
        self.max_state_bytes = max_state_bytes
        self.history: Dict[str, list] = {}  # operator -> [(timestamp, size)]
    
    def record_state_size(self, operator: str, size_bytes: int):
        """Record a state size observation."""
        if operator not in self.history:
            self.history[operator] = []
        
        self.history[operator].append((datetime.utcnow(), size_bytes))
        
        # Keep last 24 hours of history
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.history[operator] = [
            (ts, sz) for ts, sz in self.history[operator] if ts > cutoff
        ]
    
    def predict_oom(self, operator: str) -> Optional[Tuple[float, str]]:
        """
        Predict hours until OOM for an operator.
        
        Returns:
            Tuple of (hours_until_oom, trend_description) or None if insufficient data
        """
        if operator not in self.history or len(self.history[operator]) < 10:
            return None
        
        observations = self.history[operator]
        
        # Convert to numpy for linear regression
        base_time = observations[0][0]
        x = np.array([(ts - base_time).total_seconds() / 3600 for ts, _ in observations])
        y = np.array([sz for _, sz in observations])
        
        # Linear regression
        n = len(x)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / \
                (n * np.sum(x ** 2) - np.sum(x) ** 2)
        intercept = (np.sum(y) - slope * np.sum(x)) / n
        
        current_size = y[-1]
        current_hour = x[-1]
        
        if slope <= 0:
            # State is shrinking or stable
            STATE_OOM_PREDICTION_HOURS.labels(
                job_name="aggregation_job", operator=operator
            ).set(float("inf"))
            return None
        
        # Hours until max_state_bytes
        hours_until_oom = (self.max_state_bytes - current_size) / slope
        
        STATE_OOM_PREDICTION_HOURS.labels(
            job_name="aggregation_job", operator=operator
        ).set(hours_until_oom)
        
        trend = (
            f"Growing at {slope/1024/1024:.1f} MB/hour. "
            f"Current: {current_size/1024/1024:.0f} MB / "
            f"{self.max_state_bytes/1024/1024:.0f} MB max. "
            f"OOM in {hours_until_oom:.1f} hours."
        )
        
        if hours_until_oom < 6:
            logger.critical(f"STATE OOM IMMINENT for {operator}: {trend}")
        elif hours_until_oom < 24:
            logger.warning(f"State growth warning for {operator}: {trend}")
        
        return (hours_until_oom, trend)
    
    def recommend_action(self, operator: str) -> str:
        """Recommend scaling action based on state growth prediction."""
        prediction = self.predict_oom(operator)
        
        if prediction is None:
            return "No action needed - state is stable or shrinking"
        
        hours_until_oom, _ = prediction
        
        if hours_until_oom < 2:
            return (
                "IMMEDIATE: Increase TaskManager memory or parallelism. "
                "Consider enabling incremental checkpointing to reduce checkpoint size."
            )
        elif hours_until_oom < 12:
            return (
                "SOON: Schedule scaling during next maintenance window. "
                "Investigate if state TTL can be reduced."
            )
        elif hours_until_oom < 48:
            return (
                "PLAN: Add to next sprint - optimize state usage or plan "
                "capacity increase. Check for state leaks (missing timers/cleanup)."
            )
        else:
            return "MONITOR: Growth is sustainable for now. Review weekly."
```

---

## Technologies

| Category | Tool | Purpose |
|----------|------|---------|
| Stream Processing | Apache Flink | Windowed aggregation, exactly-once, state management |
| Event Bus | Apache Kafka | Event transport, exactly-once source/sink |
| OLAP Storage | Apache Druid | Real-time analytics, sub-second queries |
| OLAP Storage | ClickHouse | High-performance analytical queries |
| OLAP Storage | Apache Pinot | Real-time OLAP for user-facing analytics |
| Monitoring | Prometheus | Metrics collection and alerting |
| Visualization | Grafana | Dashboards for streaming health |
| Batch Validation | Apache Spark | Recomputation for accuracy verification |

---

## Operational Playbook

### Daily Health Check

```
┌─────────────────────────────────────────────────────────────────┐
│              DAILY STREAMING HEALTH CHECK                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Checkpoint Health                                            │
│     □ Last checkpoint < 30s ago                                 │
│     □ Checkpoint duration < 60s                                 │
│     □ No failed checkpoints in 24h                              │
│                                                                  │
│  2. Watermark Health                                            │
│     □ Watermark advancing steadily                              │
│     □ Watermark lag < 30s                                       │
│     □ No idle partitions                                        │
│                                                                  │
│  3. Throughput                                                   │
│     □ Input rate within expected range                          │
│     □ Output rate matches input rate (±late data)               │
│     □ No sustained backpressure                                 │
│                                                                  │
│  4. State                                                       │
│     □ State size within bounds                                  │
│     □ No unexpected growth trend                                │
│     □ RocksDB compaction healthy                                │
│                                                                  │
│  5. Accuracy                                                    │
│     □ Batch validation passed (last hour)                       │
│     □ No duplicates detected in output                         │
│     □ Late event rate < 1%                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Common Failure Modes and Responses

| Symptom | Root Cause | Response |
|---------|-----------|----------|
| Watermark stalled | Idle Kafka partition | Configure idle timeout or send heartbeat events |
| Checkpoint timeout | State too large | Increase checkpoint timeout, enable incremental checkpoints |
| Backpressure at sink | Druid ingestion slow | Scale Druid ingestion, buffer with intermediate Kafka topic |
| Duplicates in output | Checkpoint restore + non-idempotent sink | Make sink idempotent (upsert mode) |
| State OOM | Unbounded window or missing TTL | Add state TTL, check timer cleanup logic |
| Late data spike | Source system buffered events | Increase allowed lateness, monitor source health |
| Accuracy drift | Subtle logic bug in streaming vs batch | Compare operator-by-operator against batch |
