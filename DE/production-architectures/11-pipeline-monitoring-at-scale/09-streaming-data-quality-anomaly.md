# Streaming Data Quality Anomaly Detection

## Problem Statement

In streaming pipelines processing billions of events per day, data quality issues must be detected in **seconds**, not hours. Traditional batch-based DQ checks (Great Expectations, dbt tests) run after data lands — by then, corrupted data has already propagated downstream.

Streaming anomalies include:
- **Volume drops**: A source suddenly stops sending events (upstream failure)
- **Volume spikes**: Duplicate replay or bot traffic floods the pipeline
- **Distribution shifts**: A categorical field changes its value distribution (bug in producer)
- **Schema violations**: Events arrive with unexpected types or missing fields
- **Null explosions**: A field that's normally populated becomes 80% null
- **Timestamp anomalies**: Events with future dates or massive clock skew

At scale (1M+ events/sec), you cannot inspect every event. You need statistical methods that profile data inline with minimal overhead and detect anomalies in real-time.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              STREAMING DATA QUALITY ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DATA SOURCES                                                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                                      │
│  │ App     │ │ IoT     │ │ Partner │                                      │
│  │ Events  │ │ Sensors │ │ Feeds   │                                      │
│  └────┬────┘ └────┬────┘ └────┬────┘                                      │
│       │            │           │                                            │
│       ▼            ▼           ▼                                            │
│  ┌──────────────────────────────────────────┐                              │
│  │           KAFKA TOPICS                    │                              │
│  │  (raw events, partitioned by source)      │                              │
│  └──────────────────┬───────────────────────┘                              │
│                     │                                                       │
│           ┌─────────┴─────────┐                                            │
│           │                   │                                            │
│           ▼                   ▼                                            │
│  ┌─────────────────┐  ┌─────────────────┐                                 │
│  │  MAIN PIPELINE  │  │  DQ PROFILER    │  ◀── Taps stream (no impact)    │
│  │  (Flink/Spark)  │  │  (Flink job)    │                                 │
│  │                 │  │                 │                                 │
│  │  Transform      │  │  • Sample events│                                 │
│  │  Enrich         │  │  • Compute stats│                                 │
│  │  Aggregate      │  │  • Detect       │                                 │
│  │  Write to sink  │  │    anomalies    │                                 │
│  └────────┬────────┘  └────────┬────────┘                                 │
│           │                    │                                            │
│           ▼                    ▼                                            │
│  ┌─────────────────┐  ┌─────────────────┐                                 │
│  │  DATA LAKE /    │  │  METRICS STREAM │                                 │
│  │  WAREHOUSE      │  │  (DQ metrics)   │                                 │
│  └─────────────────┘  └────────┬────────┘                                 │
│                                │                                            │
│                                ▼                                            │
│                       ┌─────────────────┐                                  │
│                       │ ANOMALY DETECTOR│                                  │
│                       │                 │                                  │
│                       │ • Z-Score       │                                  │
│                       │ • EWMA          │                                  │
│                       │ • Isolation     │                                  │
│                       │   Forest        │                                  │
│                       │ • Seasonal      │                                  │
│                       │   decomposition │                                  │
│                       └────────┬────────┘                                  │
│                                │                                            │
│                                ▼                                            │
│                       ┌─────────────────┐                                  │
│                       │  ALERT ENGINE   │                                  │
│                       │                 │                                  │
│                       │ • Deduplication │                                  │
│                       │ • Correlation   │                                  │
│                       │ • Routing       │                                  │
│                       │ • Suppression   │                                  │
│                       └────────┬────────┘                                  │
│                                │                                            │
│                    ┌───────────┼───────────┐                               │
│                    ▼           ▼           ▼                               │
│              ┌─────────┐ ┌─────────┐ ┌─────────┐                          │
│              │PagerDuty│ │  Slack  │ │Auto-halt│                          │
│              │         │ │         │ │Pipeline │                          │
│              └─────────┘ └─────────┘ └─────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Statistical Anomaly Detection Methods

### 1. Z-Score Based Detection

Simple but effective for stationary metrics. Flags values more than N standard deviations from the mean.

```
z_score = (observed_value - mean) / std_dev

Alert if |z_score| > 3 (99.7% confidence)
```

**Best for**: Volume metrics with stable baselines (no seasonality)
**Weakness**: Fails with seasonal patterns, slow to adapt

### 2. Moving Average with Confidence Bands

Uses rolling statistics to account for recent trends:

```
rolling_mean = mean(last N windows)
rolling_std = std(last N windows)

upper_band = rolling_mean + k * rolling_std
lower_band = rolling_mean - k * rolling_std

Anomaly if value > upper_band OR value < lower_band
```

**Best for**: Metrics with gradual trends
**Weakness**: Lags behind sudden legitimate changes

### 3. Exponential Weighted Moving Average (EWMA)

Gives more weight to recent observations, adapts faster:

```
ewma_t = alpha * observed_t + (1 - alpha) * ewma_{t-1}
ewma_var_t = alpha * (observed_t - ewma_t)^2 + (1 - alpha) * ewma_var_{t-1}

Anomaly if |observed - ewma| > k * sqrt(ewma_var)
```

**Alpha**: 0.1 (slow adaptation) to 0.5 (fast adaptation)
**Best for**: Real-time detection with adaptive thresholds

### 4. Isolation Forest (ML-Based)

Unsupervised anomaly detection that isolates anomalies by random partitioning:

```
┌────────────────────────────────────────────────┐
│         ISOLATION FOREST CONCEPT                │
├────────────────────────────────────────────────┤
│                                                │
│  Normal points: Deep in tree (many splits)    │
│  Anomalies: Shallow in tree (few splits)      │
│                                                │
│  Features vector per window:                   │
│   [volume, null_rate, distinct_count,         │
│    avg_event_size, p99_latency, error_rate]   │
│                                                │
│  Score: anomaly_score ∈ [0, 1]                │
│  Alert if score > 0.7                         │
└────────────────────────────────────────────────┘
```

**Best for**: Multi-dimensional anomalies (multiple metrics shift together)
**Weakness**: Requires training on historical "normal" data

### 5. Seasonal Decomposition (Prophet-Based)

For metrics with strong daily/weekly patterns (e.g., user event volume):

```
observed = trend + seasonal + residual

Anomaly if |residual| > k * std(historical_residuals)
```

**Best for**: User-facing metrics with clear time-of-day patterns

---

## What to Monitor in Streaming

### Metric Categories

```
┌─────────────────────────────────────────────────────────────────┐
│              STREAMING DQ METRICS                                 │
├──────────────────┬──────────────────────────────────────────────┤
│  VOLUME          │  events_per_second (per source/topic)        │
│                  │  bytes_per_second                             │
│                  │  events_per_window (1min tumbling)            │
├──────────────────┼──────────────────────────────────────────────┤
│  COMPLETENESS    │  null_rate per field                         │
│                  │  missing_required_fields_rate                 │
│                  │  empty_string_rate                            │
├──────────────────┼──────────────────────────────────────────────┤
│  VALIDITY        │  schema_violation_rate                        │
│                  │  out_of_range_values_rate                     │
│                  │  invalid_enum_rate                            │
├──────────────────┼──────────────────────────────────────────────┤
│  CONSISTENCY     │  duplicate_rate (by event_id)                │
│                  │  ordering_violations                          │
│                  │  referential_integrity_failures               │
├──────────────────┼──────────────────────────────────────────────┤
│  TIMELINESS      │  event_lag (now - event_timestamp)           │
│                  │  inter_arrival_time_p99                       │
│                  │  future_timestamp_rate                        │
├──────────────────┼──────────────────────────────────────────────┤
│  DISTRIBUTION    │  cardinality_per_field (approx)              │
│                  │  value_frequency_shift                        │
│                  │  numeric_distribution (mean, p50, p99)       │
└──────────────────┴──────────────────────────────────────────────┘
```

---

## Real-Time Data Profiling at Scale

### Sampling Strategies

At 1M events/sec, profiling every event is expensive. Strategies:

| Strategy | Overhead | Accuracy | Use Case |
|----------|----------|----------|----------|
| Every Nth (1/100) | ~1% | Good for volume | General profiling |
| Reservoir sampling | ~1% | Statistically representative | Distribution analysis |
| Head sampling (first N per window) | Minimal | Biased | Quick checks |
| Hash-based (deterministic) | ~1% | Reproducible | Debugging |
| Adaptive (more when anomalous) | Variable | High when needed | Intelligent profiling |

### Approximate Algorithms

```
┌────────────────────────────────────────────────────────────────┐
│            APPROXIMATE ALGORITHMS FOR STREAMING                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  HyperLogLog (Cardinality):                                    │
│    • Counts distinct values with ~2% error                     │
│    • Memory: 12KB per counter                                  │
│    • Use: Track distinct user_ids, ip_addresses per window     │
│                                                                │
│  t-Digest (Percentiles):                                       │
│    • Accurate percentile estimation (p50, p95, p99)           │
│    • Memory: ~10KB per digest                                  │
│    • Use: Track event_size, latency distributions              │
│                                                                │
│  Count-Min Sketch (Frequency):                                 │
│    • Approximate frequency counts for values                   │
│    • Memory: configurable (width × depth × 4 bytes)           │
│    • Use: Detect sudden frequency changes in categorical fields│
│                                                                │
│  Bloom Filter (Membership):                                    │
│    • Test if value was seen before (false positives ok)        │
│    • Memory: ~1.2 bytes per element at 1% FP rate             │
│    • Use: Duplicate detection                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Production Code Examples

### 1. Flink-Based Inline Data Quality Profiler

```python
"""
Apache Flink streaming data quality profiler.
Computes per-window statistics without impacting the main pipeline.
"""

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import ProcessWindowFunction, AggregateFunction
from pyflink.datastream.window import TumblingEventTimeWindows
from pyflink.common.time import Time
from pyflink.common.watermark_strategy import WatermarkStrategy
from dataclasses import dataclass, field
from typing import Dict, List
import json
import time


@dataclass
class WindowProfile:
    """Statistics for a single time window."""
    window_start: int = 0
    window_end: int = 0
    source: str = ""
    event_count: int = 0
    bytes_total: int = 0
    null_counts: Dict[str, int] = field(default_factory=dict)
    field_count: int = 0
    distinct_estimates: Dict[str, int] = field(default_factory=dict)
    min_timestamp: int = 0
    max_timestamp: int = 0
    schema_violations: int = 0
    duplicate_count: int = 0


class ProfileAggregator(AggregateFunction):
    """Aggregates event statistics within a window."""

    def create_accumulator(self):
        return {
            'count': 0,
            'bytes': 0,
            'null_counts': {},
            'schema_violations': 0,
            'timestamps': [],
            'seen_ids': set(),
            'duplicates': 0
        }

    def add(self, event, accumulator):
        accumulator['count'] += 1
        accumulator['bytes'] += len(json.dumps(event))

        # Track nulls per field
        for field_name, value in event.items():
            if value is None or value == '':
                accumulator['null_counts'][field_name] = \
                    accumulator['null_counts'].get(field_name, 0) + 1

        # Track duplicates (by event_id if present)
        event_id = event.get('event_id')
        if event_id:
            if event_id in accumulator['seen_ids']:
                accumulator['duplicates'] += 1
            else:
                accumulator['seen_ids'].add(event_id)

        # Track timestamps
        ts = event.get('timestamp')
        if ts:
            accumulator['timestamps'].append(ts)

        return accumulator

    def get_result(self, accumulator):
        return accumulator

    def merge(self, a, b):
        a['count'] += b['count']
        a['bytes'] += b['bytes']
        a['duplicates'] += b['duplicates']
        for k, v in b['null_counts'].items():
            a['null_counts'][k] = a['null_counts'].get(k, 0) + v
        a['timestamps'].extend(b['timestamps'])
        return a


class AnomalyDetectorFunction(ProcessWindowFunction):
    """Detects anomalies by comparing current window to historical baselines."""

    def __init__(self):
        self.history: List[Dict] = []
        self.max_history = 60  # Keep 60 windows of history (1 hour at 1min windows)

    def process(self, key, context, elements):
        profile = elements[0]  # Aggregated result

        # Build current metrics
        current = {
            'count': profile['count'],
            'bytes': profile['bytes'],
            'null_rate': sum(profile['null_counts'].values()) / max(profile['count'] * len(profile['null_counts']), 1),
            'duplicate_rate': profile['duplicates'] / max(profile['count'], 1),
        }

        anomalies = []

        if len(self.history) >= 10:
            # Z-score detection on volume
            hist_counts = [h['count'] for h in self.history]
            mean_count = sum(hist_counts) / len(hist_counts)
            std_count = (sum((x - mean_count)**2 for x in hist_counts) / len(hist_counts)) ** 0.5

            if std_count > 0:
                z_score = (current['count'] - mean_count) / std_count
                if abs(z_score) > 3:
                    anomalies.append({
                        'type': 'volume_anomaly',
                        'z_score': z_score,
                        'expected': mean_count,
                        'actual': current['count'],
                        'direction': 'spike' if z_score > 0 else 'drop'
                    })

            # Null rate spike detection
            hist_null_rates = [h.get('null_rate', 0) for h in self.history]
            mean_null = sum(hist_null_rates) / len(hist_null_rates)
            if current['null_rate'] > mean_null * 3 and current['null_rate'] > 0.05:
                anomalies.append({
                    'type': 'null_rate_spike',
                    'expected_rate': mean_null,
                    'actual_rate': current['null_rate']
                })

        # Store in history
        self.history.append(current)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        # Emit anomalies
        if anomalies:
            yield {
                'source': key,
                'window_start': context.window().start,
                'window_end': context.window().end,
                'anomalies': anomalies,
                'metrics': current
            }


def build_profiler_job():
    """Build and submit the Flink profiling job."""
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(4)

    # Configure Kafka source
    # In production: use FlinkKafkaConsumer with proper deserialization
    source = env.from_source(
        # KafkaSource configuration here
        source_name="raw-events"
    )

    # Profile with 1-minute tumbling windows
    profiles = (
        source
        .key_by(lambda event: event.get('source', 'unknown'))
        .window(TumblingEventTimeWindows.of(Time.minutes(1)))
        .aggregate(
            ProfileAggregator(),
            AnomalyDetectorFunction()
        )
    )

    # Sink anomalies to alert topic
    profiles.add_sink(
        # KafkaSink to 'dq-anomalies' topic
    )

    env.execute("streaming-dq-profiler")
```

### 2. Z-Score Anomaly Detector for Volume Monitoring

```python
#!/usr/bin/env python3
"""
Z-Score based volume anomaly detector.
Monitors event counts per source/topic and alerts on significant deviations.
"""

import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from prometheus_client import start_http_server, Gauge, Counter


VOLUME_ZSCORE = Gauge(
    'dq_volume_zscore',
    'Z-score of current volume vs historical baseline',
    ['source', 'topic']
)

ANOMALY_DETECTED = Counter(
    'dq_anomaly_detected_total',
    'Number of anomalies detected',
    ['source', 'type', 'direction']
)


@dataclass
class RollingStats:
    """Maintains rolling statistics efficiently."""
    window_size: int = 60  # Number of periods to track
    values: deque = field(default_factory=lambda: deque(maxlen=60))
    _sum: float = 0
    _sum_sq: float = 0

    def add(self, value: float):
        if len(self.values) == self.values.maxlen:
            old = self.values[0]
            self._sum -= old
            self._sum_sq -= old * old
        self.values.append(value)
        self._sum += value
        self._sum_sq += value * value

    @property
    def mean(self) -> float:
        n = len(self.values)
        return self._sum / n if n > 0 else 0

    @property
    def std(self) -> float:
        n = len(self.values)
        if n < 2:
            return 0
        variance = (self._sum_sq / n) - (self.mean ** 2)
        return math.sqrt(max(variance, 0))

    @property
    def count(self) -> int:
        return len(self.values)

    def z_score(self, value: float) -> Optional[float]:
        if self.count < 10 or self.std == 0:
            return None
        return (value - self.mean) / self.std


class VolumeAnomalyDetector:
    """Detects volume anomalies using rolling Z-score."""

    def __init__(self, sensitivity: float = 3.0, min_absolute_change: int = 100):
        self.sensitivity = sensitivity
        self.min_absolute_change = min_absolute_change
        self.stats: Dict[str, RollingStats] = {}

    def observe(self, source: str, count: int) -> Optional[Dict]:
        """
        Observe a new count for a source.
        Returns anomaly dict if detected, None otherwise.
        """
        if source not in self.stats:
            self.stats[source] = RollingStats(window_size=60)

        stats = self.stats[source]
        z = stats.z_score(count)

        # Record the observation
        stats.add(count)

        # Update Prometheus
        if z is not None:
            VOLUME_ZSCORE.labels(source=source, topic=source).set(z)

        # Check for anomaly
        if z is not None and abs(z) > self.sensitivity:
            # Also check absolute change (avoid alerting on tiny variations)
            abs_change = abs(count - stats.mean)
            if abs_change >= self.min_absolute_change:
                direction = 'spike' if z > 0 else 'drop'
                anomaly = {
                    'source': source,
                    'type': 'volume',
                    'direction': direction,
                    'z_score': round(z, 2),
                    'observed': count,
                    'expected_mean': round(stats.mean, 1),
                    'expected_std': round(stats.std, 1),
                    'severity': 'critical' if abs(z) > 5 else 'warning',
                    'timestamp': time.time()
                }
                ANOMALY_DETECTED.labels(
                    source=source, type='volume', direction=direction
                ).inc()
                return anomaly

        return None


class EWMAAnomalyDetector:
    """Exponentially Weighted Moving Average anomaly detector."""

    def __init__(self, alpha: float = 0.2, sensitivity: float = 3.0):
        self.alpha = alpha
        self.sensitivity = sensitivity
        self.ewma: Dict[str, float] = {}
        self.ewma_var: Dict[str, float] = {}

    def observe(self, source: str, value: float) -> Optional[Dict]:
        if source not in self.ewma:
            self.ewma[source] = value
            self.ewma_var[source] = 0
            return None

        # Update EWMA
        prev_ewma = self.ewma[source]
        self.ewma[source] = self.alpha * value + (1 - self.alpha) * prev_ewma

        # Update variance
        diff = value - prev_ewma
        self.ewma_var[source] = (
            self.alpha * (diff ** 2) + (1 - self.alpha) * self.ewma_var[source]
        )

        # Detect anomaly
        std = math.sqrt(self.ewma_var[source])
        if std > 0:
            deviation = abs(value - prev_ewma) / std
            if deviation > self.sensitivity:
                return {
                    'source': source,
                    'type': 'ewma_deviation',
                    'deviation_sigmas': round(deviation, 2),
                    'observed': value,
                    'expected': round(prev_ewma, 2),
                    'ewma_std': round(std, 2),
                    'timestamp': time.time()
                }

        return None


# Integration with Kafka consumer
def main():
    """Main loop: consume DQ metrics from Kafka and detect anomalies."""
    from confluent_kafka import Consumer

    detector = VolumeAnomalyDetector(sensitivity=3.0)
    ewma_detector = EWMAAnomalyDetector(alpha=0.15)

    consumer = Consumer({
        'bootstrap.servers': 'kafka:9092',
        'group.id': 'dq-anomaly-detector',
        'auto.offset.reset': 'latest'
    })
    consumer.subscribe(['dq-metrics'])

    start_http_server(9093)
    print("Volume anomaly detector running on :9093")

    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            continue

        metric = json.loads(msg.value())
        source = metric['source']
        count = metric['event_count']

        # Run both detectors
        anomaly_z = detector.observe(source, count)
        anomaly_ewma = ewma_detector.observe(source, float(count))

        for anomaly in [anomaly_z, anomaly_ewma]:
            if anomaly:
                print(f"ANOMALY: {json.dumps(anomaly)}")
                # In production: publish to alert topic or call webhook


if __name__ == "__main__":
    import json
    main()
```

### 3. Great Expectations Streaming Integration

```python
#!/usr/bin/env python3
"""
Integration of Great Expectations with streaming pipelines.
Validates micro-batches as they arrive.
"""

import great_expectations as gx
from great_expectations.core.batch import RuntimeBatchRequest
import pandas as pd
from typing import Dict, List
import json


class StreamingDQValidator:
    """Validates streaming micro-batches using Great Expectations."""

    def __init__(self, context_path: str, suite_name: str):
        self.context = gx.get_context(context_root_dir=context_path)
        self.suite_name = suite_name
        self.violation_counts: Dict[str, int] = {}

    def validate_batch(self, events: List[Dict]) -> Dict:
        """
        Validate a micro-batch of events.
        Returns validation result with pass/fail per expectation.
        """
        df = pd.DataFrame(events)

        batch_request = RuntimeBatchRequest(
            datasource_name="streaming_source",
            data_connector_name="runtime_connector",
            data_asset_name="micro_batch",
            runtime_parameters={"batch_data": df},
            batch_identifiers={"batch_id": "streaming"}
        )

        result = self.context.run_checkpoint(
            checkpoint_name="streaming_checkpoint",
            batch_request=batch_request,
            expectation_suite_name=self.suite_name
        )

        # Extract failures
        validation_result = result.list_validation_results()[0]
        failures = []

        for exp_result in validation_result.results:
            if not exp_result.success:
                failures.append({
                    'expectation': exp_result.expectation_config.expectation_type,
                    'column': exp_result.expectation_config.kwargs.get('column'),
                    'observed_value': exp_result.result.get('observed_value'),
                    'details': exp_result.result
                })

        return {
            'success': validation_result.success,
            'statistics': validation_result.statistics,
            'failures': failures,
            'batch_size': len(events)
        }

    def create_streaming_suite(self):
        """Create expectations suite for streaming data."""
        suite = self.context.add_expectation_suite(self.suite_name)

        # Volume expectations
        suite.add_expectation(
            gx.expectations.ExpectTableRowCountToBeBetween(min_value=100, max_value=100000)
        )

        # Completeness expectations
        for col in ['event_id', 'user_id', 'timestamp', 'event_type']:
            suite.add_expectation(
                gx.expectations.ExpectColumnValuesToNotBeNull(column=col, mostly=0.99)
            )

        # Validity expectations
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToBeDatetimeParseable(column='timestamp')
        )
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToBeInSet(
                column='event_type',
                value_set=['click', 'view', 'purchase', 'signup', 'logout']
            )
        )

        # Distribution expectations
        suite.add_expectation(
            gx.expectations.ExpectColumnMeanToBeBetween(
                column='event_value', min_value=0, max_value=10000
            )
        )

        self.context.save_expectation_suite(suite)
```

### 4. Kafka Streams Data Quality Monitor

```python
#!/usr/bin/env python3
"""
Kafka Streams-style DQ monitor using Faust (Python stream processing).
Lightweight alternative to Flink for DQ profiling.
"""

import faust
from datetime import timedelta
from typing import Dict
import json


app = faust.App(
    'streaming-dq-monitor',
    broker='kafka://localhost:9092',
    store='rocksdb://',
)

# Input topic
raw_events = app.topic('raw-events', value_type=bytes)

# Output topics
dq_metrics_topic = app.topic('dq-metrics', value_type=bytes)
dq_anomalies_topic = app.topic('dq-anomalies', value_type=bytes)


class WindowStats(faust.Record):
    source: str
    window_start: float
    event_count: int = 0
    total_bytes: int = 0
    null_counts: Dict[str, int] = {}
    schema_violations: int = 0
    duplicate_count: int = 0


# Tumbling window table (1 minute)
window_stats = app.Table(
    'dq-window-stats',
    default=lambda: WindowStats(source='', window_start=0),
).tumbling(timedelta(minutes=1), expires=timedelta(hours=1))


@app.agent(raw_events)
async def profile_events(stream):
    """Profile events in 1-minute windows."""
    async for event_bytes in stream:
        try:
            event = json.loads(event_bytes)
            source = event.get('source', 'unknown')

            # Update window stats
            stats = window_stats[source]
            stats.event_count += 1
            stats.total_bytes += len(event_bytes)

            # Check for nulls in required fields
            for field in ['event_id', 'user_id', 'timestamp']:
                if not event.get(field):
                    stats.null_counts[field] = stats.null_counts.get(field, 0) + 1

            # Schema validation (basic)
            if not isinstance(event.get('timestamp'), (int, float)):
                stats.schema_violations += 1

            window_stats[source] = stats

        except json.JSONDecodeError:
            # Malformed event
            stats = window_stats['__malformed__']
            stats.schema_violations += 1
            window_stats['__malformed__'] = stats


@app.timer(interval=60.0)
async def emit_metrics():
    """Emit aggregated DQ metrics every minute."""
    for source, stats in window_stats.items():
        if stats.event_count > 0:
            metric = {
                'source': source,
                'event_count': stats.event_count,
                'total_bytes': stats.total_bytes,
                'avg_event_size': stats.total_bytes / stats.event_count,
                'null_rates': {
                    k: v / stats.event_count
                    for k, v in stats.null_counts.items()
                },
                'schema_violation_rate': stats.schema_violations / stats.event_count,
                'timestamp': stats.window_start
            }
            await dq_metrics_topic.send(value=json.dumps(metric).encode())


if __name__ == '__main__':
    app.main()
```

---

## Alert Fatigue Prevention

### The Problem

Without careful design, streaming DQ monitoring generates thousands of alerts per day, causing operators to ignore them entirely.

```
┌─────────────────────────────────────────────────────────────────┐
│             ALERT FATIGUE PREVENTION STRATEGIES                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DEDUPLICATION                                               │
│     Same anomaly firing every minute? Suppress after first.     │
│     Only re-alert if severity escalates.                        │
│                                                                 │
│  2. SEVERITY-BASED ROUTING                                      │
│     Critical (volume drop >90%): Page on-call                  │
│     Warning (null rate doubled): Slack notification            │
│     Info (minor distribution shift): Dashboard only            │
│                                                                 │
│  3. CORRELATION-BASED SUPPRESSION                               │
│     If upstream source is known-down, suppress all downstream  │
│     alerts related to that source.                             │
│                                                                 │
│  4. ADAPTIVE THRESHOLDS                                         │
│     During known high-traffic periods (Black Friday),           │
│     automatically widen thresholds.                            │
│     After deployment, temporarily increase sensitivity.        │
│                                                                 │
│  5. ALERT GROUPING                                              │
│     10 tables from same source all drop volume?                │
│     Group into single alert: "Source X offline"                │
│                                                                 │
│  6. COOLDOWN PERIODS                                            │
│     After resolving, don't re-fire for same issue             │
│     within 15 minutes (prevents flapping).                    │
│                                                                 │
│  7. BUSINESS HOURS AWARENESS                                    │
│     Non-critical alerts only during business hours.           │
│     Critical alerts always page.                              │
└─────────────────────────────────────────────────────────────────┘
```

### Alert Deduplication Implementation

```python
class AlertDeduplicator:
    """Deduplicates and groups streaming DQ alerts."""

    def __init__(self, cooldown_seconds: int = 900):
        self.active_alerts: Dict[str, Dict] = {}
        self.cooldown_seconds = cooldown_seconds

    def should_fire(self, alert_key: str, severity: str, details: Dict) -> bool:
        """Determine if this alert should fire or be suppressed."""
        now = time.time()

        if alert_key in self.active_alerts:
            existing = self.active_alerts[alert_key]

            # Already firing — suppress unless severity escalated
            if severity_rank(severity) > severity_rank(existing['severity']):
                # Escalation — fire
                self.active_alerts[alert_key]['severity'] = severity
                return True

            # Check cooldown
            if now - existing['last_fired'] < self.cooldown_seconds:
                return False  # Suppress

        # New alert or cooldown expired
        self.active_alerts[alert_key] = {
            'severity': severity,
            'first_seen': now,
            'last_fired': now,
            'fire_count': self.active_alerts.get(alert_key, {}).get('fire_count', 0) + 1
        }
        return True

    def resolve(self, alert_key: str):
        """Mark an alert as resolved."""
        if alert_key in self.active_alerts:
            del self.active_alerts[alert_key]


def severity_rank(s: str) -> int:
    return {'info': 0, 'warning': 1, 'critical': 2}.get(s, 0)
```

---

## Technologies Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Stream processing | Apache Flink, Kafka Streams, Faust | Inline profiling |
| Statistical detection | Custom Python, scikit-learn | Anomaly algorithms |
| Approximate counting | HyperLogLog, t-digest, CMS | Scalable profiling |
| DQ frameworks | Great Expectations, Soda Core, Deequ | Validation rules |
| Metrics | Prometheus + Grafana | Visualization |
| Alerting | PagerDuty, Slack, custom routing | Notification |
| ML-based | Isolation Forest, Prophet | Advanced detection |

---

## Key Takeaways

1. **Profile inline, detect asynchronously** — Don't add latency to the main pipeline
2. **Use approximate algorithms** — Exact counts are impossible at streaming scale
3. **Layer detection methods** — Simple Z-score catches most issues; ML catches the rest
4. **Adaptive thresholds** — Static thresholds generate noise; learn what's normal
5. **Alert fatigue is the enemy** — Deduplicate, correlate, and group aggressively
6. **Start simple** — Volume monitoring alone catches 60% of streaming DQ issues
7. **Sampling is acceptable** — 1% sample gives 99% of the insight at 1% of the cost
