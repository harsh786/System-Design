# Scaling Monitoring for Billions of Transactions

## Problem Statement

When data pipelines process 1B+ events per day, naive monitoring approaches collapse:

- **Log every event**: 1B log lines/day = ~200TB/year of log storage
- **Metric per record**: Unbounded cardinality kills Prometheus (OOM at ~10M series)
- **Trace every request**: 1B spans × 500 bytes = 500GB/day trace storage

The fundamental tension: you need visibility into every record for debugging, but you can't store telemetry for every record. The solution is **tiered monitoring** with smart sampling, pre-aggregation, and approximate algorithms.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                    Tiered Monitoring for Billion-Scale Pipelines                       │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │  DATA PIPELINE (1B+ events/day)                                                │  │
│  │                                                                                │  │
│  │  Kafka ──▶ Flink ──▶ Transform ──▶ Sink (S3/DWH)                             │  │
│  │    │          │           │              │                                     │  │
│  │    │          │           │              │                                     │  │
│  └────┼──────────┼───────────┼──────────────┼─────────────────────────────────────┘  │
│       │          │           │              │                                        │
│       ▼          ▼           ▼              ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  TIER 1: REAL-TIME (sub-second)                                                 │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐      │ │
│  │  │  In-Memory Counters & Gauges (per operator)                          │      │ │
│  │  │  • events_processed (counter)     • error_count (counter)            │      │ │
│  │  │  • processing_latency (histogram) • backpressure (gauge)             │      │ │
│  │  │  • HyperLogLog(distinct users)    • t-Digest(latency percentiles)    │      │ │
│  │  └──────────────────────────────────────────────────────────────────────┘      │ │
│  │  Cardinality: ~5K series | Latency: <1s | Cost: ~$0/day (in-process)           │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│       │                                                                              │
│       ▼                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  TIER 2: NEAR-REAL-TIME (1-5 min)                                               │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐      │ │
│  │  │  Prometheus Scrape (15s interval)                                    │      │ │
│  │  │  • Pre-aggregated metrics from Tier 1                                │      │ │
│  │  │  • Recording rules for cross-service aggregation                     │      │ │
│  │  │  • Alert evaluation (PromQL)                                         │      │ │
│  │  └──────────────────────────────────────────────────────────────────────┘      │ │
│  │  Cardinality: ~50K series | Latency: 15s-5m | Cost: ~$50/day                  │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│       │                                                                              │
│       ▼                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  TIER 3: BATCH VALIDATION (hourly)                                              │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐      │ │
│  │  │  Spark/SQL Jobs                                                      │      │ │
│  │  │  • Row count reconciliation (source vs destination)                  │      │ │
│  │  │  • Schema drift detection                                            │      │ │
│  │  │  • Statistical distribution checks                                   │      │ │
│  │  │  • Referential integrity validation                                  │      │ │
│  │  └──────────────────────────────────────────────────────────────────────┘      │ │
│  │  Coverage: 100% of data | Latency: 1-2h | Cost: ~$200/day (compute)           │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│       │                                                                              │
│       ▼                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  TIER 4: DEEP ANALYSIS (daily)                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐      │ │
│  │  │  Great Expectations / dbt Tests / Custom ML                          │      │ │
│  │  │  • Full statistical profiling                                        │      │ │
│  │  │  • Anomaly detection (ML-based)                                      │      │ │
│  │  │  • Data drift scoring                                                │      │ │
│  │  │  • Business rule validation (complex joins)                          │      │ │
│  │  └──────────────────────────────────────────────────────────────────────┘      │ │
│  │  Coverage: 100% of data | Latency: 24h | Cost: ~$500/day (heavy compute)      │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## The Cardinality Explosion Problem

### Why High Cardinality Kills Monitoring

```
                    Cardinality Growth Visualization

  Series Count
  (millions)
      │
  10M │                                          ╱ user_id label
      │                                        ╱   (KILLS PROMETHEUS)
      │                                      ╱
   5M │                                    ╱
      │                                  ╱
      │                ╱────────────────── request_id label
   1M │              ╱                      (DON'T DO THIS)
      │            ╱
 500K │──────────╱─────────────────────── PROMETHEUS DANGER ZONE
      │        ╱                            (OOM likely above this)
 100K │──────╱────────────────────────────── bounded labels
      │    ╱                                  (pipeline, status, region)
  10K │──╱
      │╱
      └──────────────────────────────────── Time
```

### Label Best Practices

| Label Type | Example | Cardinality | Verdict |
|-----------|---------|-------------|---------|
| Environment | prod/staging/dev | 3 | SAFE |
| Pipeline name | ingestion, transform | 10-50 | SAFE |
| Status | success/failed/skipped | 3 | SAFE |
| Region | us-east-1, eu-west-1 | 5-10 | SAFE |
| Partition | 0-255 | 256 | CAUTION |
| Customer ID | UUID | Millions | NEVER |
| Request ID | UUID | Billions | NEVER |
| Error message | Free text | Unbounded | NEVER |

### Metric Relabeling Strategies

```yaml
# prometheus-relabeling.yaml
# Applied during scrape to prevent cardinality explosion

scrape_configs:
  - job_name: 'pipeline-metrics'
    metric_relabel_configs:
      # 1. Drop metrics with known high-cardinality labels
      - source_labels: [__name__]
        regex: '.*_by_user_id_.*'
        action: drop

      # 2. Hash high-cardinality values into buckets
      - source_labels: [customer_id]
        regex: '(.+)'
        target_label: customer_bucket
        replacement: ''
        action: replace
      - source_labels: [customer_id]
        modulus: 100  # 100 buckets instead of millions
        target_label: customer_bucket
        action: hashmod

      # 3. Replace unbounded path labels with patterns
      - source_labels: [http_path]
        regex: '/api/v1/users/[a-f0-9-]+'
        target_label: http_path
        replacement: '/api/v1/users/{id}'

      # 4. Drop unused quantile labels from summaries
      - source_labels: [__name__, quantile]
        regex: 'pipeline_.*;(0\.5)'  # Keep only p50, p90, p99
        action: drop

      # 5. Aggregate per-partition metrics to per-topic
      - source_labels: [__name__, partition]
        regex: 'kafka_consumer_lag;.*'
        action: drop  # Use recording rule for aggregated view
```

### Hierarchical Aggregation Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│              Pre-Aggregation at Source                            │
│                                                                 │
│  Level 1: Per-Record (In Operator)                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  counter++ per event                                     │   │
│  │  histogram.observe(latency) per event                    │   │
│  │  hll.add(user_id) per event                             │   │
│  │  bloom.add(record_id) per event                         │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │ Expose as metrics (bounded)       │
│                              ▼                                   │
│  Level 2: Per-Operator (Prometheus Scrape)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  pipeline_events_total{pipeline="X", status="ok"} 10M   │   │
│  │  pipeline_latency_bucket{le="1.0"} 9.5M                 │   │
│  │  pipeline_unique_users_approx 150000                     │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │ Recording rules                   │
│                              ▼                                   │
│  Level 3: Per-Pipeline (Recording Rules)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  pipeline:throughput:rate5m = sum(rate(...))             │   │
│  │  pipeline:error_rate:ratio5m = failed/total             │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │ Federation / Thanos               │
│                              ▼                                   │
│  Level 4: Global (Thanos Query)                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  org:total_events_processed:rate1h                       │   │
│  │  org:pipeline_health:ratio                              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Sampling Strategies

### Head-Based Sampling (Consistent)

```python
"""
head_based_sampling.py
Deterministic sampling based on trace_id - ensures all spans in a trace
are either sampled or not (consistent view).
"""

import hashlib
from typing import Optional

class ConsistentSampler:
    """
    Sample traces consistently using trace_id hash.
    All spans within a trace get the same decision.
    """
    
    def __init__(self, sample_rate: float = 0.01):
        """
        Args:
            sample_rate: Fraction of traces to keep (0.01 = 1%)
        """
        self.sample_rate = sample_rate
        self.threshold = int(sample_rate * (2**32))
    
    def should_sample(self, trace_id: str) -> bool:
        """Deterministic sampling decision based on trace_id."""
        hash_value = int(hashlib.md5(trace_id.encode()).hexdigest()[:8], 16)
        return hash_value < self.threshold
    
    def get_adjusted_count(self) -> float:
        """Return weight for sampled items (for accurate totals)."""
        return 1.0 / self.sample_rate


class StratifiedSampler:
    """
    Different sampling rates per partition/tenant/priority.
    Critical paths get higher sampling rates.
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: Dict mapping category -> sample_rate
                    e.g., {"critical": 1.0, "standard": 0.01, "bulk": 0.001}
        """
        self.samplers = {
            category: ConsistentSampler(rate)
            for category, rate in config.items()
        }
        self.default_sampler = ConsistentSampler(0.01)
    
    def should_sample(self, trace_id: str, category: str) -> bool:
        sampler = self.samplers.get(category, self.default_sampler)
        return sampler.should_sample(trace_id)


# Usage in a Flink operator
class SampledMetricsOperator:
    """Flink operator that emits sampled detailed metrics."""
    
    def __init__(self):
        self.sampler = StratifiedSampler({
            "payment": 1.0,      # Sample 100% of payment traces
            "standard": 0.01,    # Sample 1% of standard events
            "bulk_import": 0.001 # Sample 0.1% of bulk imports
        })
        
        # Always-on aggregate counters (no sampling)
        self.total_counter = 0
        self.error_counter = 0
    
    def process_element(self, event):
        # ALWAYS increment counters (cheap, bounded cardinality)
        self.total_counter += 1
        if event.status == "error":
            self.error_counter += 1
        
        # SELECTIVELY emit detailed trace/log
        if self.sampler.should_sample(event.trace_id, event.priority):
            self.emit_detailed_telemetry(event)
```

### Tail-Based Sampling (Interesting Events)

```python
"""
tail_based_sampling.py
Keep traces that exhibit interesting behavior (errors, slow, etc.)
Requires buffering complete traces before decision.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Set
import threading

@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str
    operation: str
    duration_ms: float
    status_code: int
    attributes: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass 
class TraceBuffer:
    spans: List[Span] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    
    @property
    def duration_ms(self) -> float:
        if not self.spans:
            return 0
        return max(s.duration_ms for s in self.spans)
    
    @property
    def has_error(self) -> bool:
        return any(s.status_code >= 400 for s in self.spans)
    
    @property
    def span_count(self) -> int:
        return len(self.spans)


class TailBasedSampler:
    """
    Buffer traces and make sampling decision after seeing all spans.
    Keeps 100% of interesting traces, 1% of boring ones.
    """
    
    def __init__(
        self,
        decision_wait_seconds: float = 10.0,
        max_traces_buffered: int = 100_000,
        latency_threshold_ms: float = 5000,
        base_sample_rate: float = 0.01,
    ):
        self.decision_wait = decision_wait_seconds
        self.max_traces = max_traces_buffered
        self.latency_threshold = latency_threshold_ms
        self.base_sample_rate = base_sample_rate
        
        self.traces: Dict[str, TraceBuffer] = {}
        self.lock = threading.Lock()
        
        # Start background decision thread
        self._start_decision_loop()
    
    def add_span(self, span: Span):
        """Add a span to the trace buffer."""
        with self.lock:
            if span.trace_id not in self.traces:
                if len(self.traces) >= self.max_traces:
                    self._evict_oldest()
                self.traces[span.trace_id] = TraceBuffer()
            self.traces[span.trace_id].spans.append(span)
    
    def _should_keep(self, trace: TraceBuffer) -> bool:
        """Decision policies for keeping a trace."""
        # Policy 1: Always keep errors
        if trace.has_error:
            return True
        
        # Policy 2: Always keep slow traces
        if trace.duration_ms > self.latency_threshold:
            return True
        
        # Policy 3: Keep traces with many spans (complex operations)
        if trace.span_count > 50:
            return True
        
        # Policy 4: Keep traces from critical pipelines
        critical_ops = {"payment-processing", "fraud-detection", "compliance"}
        if any(s.operation in critical_ops for s in trace.spans):
            return True
        
        # Policy 5: Probabilistic sampling for everything else
        import hashlib
        trace_id = trace.spans[0].trace_id
        hash_val = int(hashlib.md5(trace_id.encode()).hexdigest()[:8], 16)
        return hash_val < int(self.base_sample_rate * (2**32))
    
    def _make_decisions(self):
        """Process buffered traces that have waited long enough."""
        now = time.time()
        decisions = []
        
        with self.lock:
            expired = [
                tid for tid, buf in self.traces.items()
                if now - buf.first_seen > self.decision_wait
            ]
            
            for trace_id in expired:
                trace = self.traces.pop(trace_id)
                keep = self._should_keep(trace)
                decisions.append((trace_id, trace, keep))
        
        # Export kept traces
        for trace_id, trace, keep in decisions:
            if keep:
                self._export_trace(trace)
    
    def _export_trace(self, trace: TraceBuffer):
        """Send trace to backend (Tempo/Jaeger)."""
        # Implementation: batch export via OTLP
        pass
    
    def _evict_oldest(self):
        """Evict oldest trace when buffer is full."""
        oldest_id = min(self.traces, key=lambda k: self.traces[k].first_seen)
        del self.traces[oldest_id]
    
    def _start_decision_loop(self):
        """Background thread for making sampling decisions."""
        def loop():
            while True:
                self._make_decisions()
                time.sleep(1.0)
        
        t = threading.Thread(target=loop, daemon=True)
        t.start()
```

### Adaptive Sampling

```python
"""
adaptive_sampling.py
Dynamically adjust sampling rate based on system state.
Increase sampling during anomalies, decrease during calm periods.
"""

import time
from dataclasses import dataclass
from collections import deque
import math

@dataclass
class AdaptiveSamplerConfig:
    min_rate: float = 0.001     # Never go below 0.1%
    max_rate: float = 1.0       # Can go up to 100%
    target_rate: float = 0.01   # Default 1%
    anomaly_multiplier: float = 10.0  # 10x during anomalies
    cooldown_seconds: float = 300.0   # 5min cooldown after anomaly
    budget_per_minute: int = 10000    # Max traces/min regardless

class AdaptiveSampler:
    """
    Adjusts sampling rate based on:
    1. Error rate (more errors → sample more)
    2. Latency anomalies (spikes → sample more)  
    3. Budget constraints (cap total traces/min)
    """
    
    def __init__(self, config: AdaptiveSamplerConfig = None):
        self.config = config or AdaptiveSamplerConfig()
        self.current_rate = self.config.target_rate
        
        # Sliding windows for anomaly detection
        self.error_rates = deque(maxlen=60)  # 1min of 1s buckets
        self.latencies = deque(maxlen=60)
        self.traces_this_minute = 0
        self.minute_start = time.time()
        
        # Anomaly state
        self.in_anomaly = False
        self.anomaly_end_time = 0
    
    def record_event(self, is_error: bool, latency_ms: float):
        """Record an event for rate adjustment."""
        self.error_rates.append(1 if is_error else 0)
        self.latencies.append(latency_ms)
        self._maybe_adjust()
    
    def should_sample(self, trace_id: str) -> bool:
        """Get sampling decision with current adaptive rate."""
        # Budget check
        now = time.time()
        if now - self.minute_start > 60:
            self.traces_this_minute = 0
            self.minute_start = now
        
        if self.traces_this_minute >= self.config.budget_per_minute:
            return False
        
        # Hash-based decision with current rate
        import hashlib
        hash_val = int(hashlib.md5(trace_id.encode()).hexdigest()[:8], 16)
        sampled = hash_val < int(self.current_rate * (2**32))
        
        if sampled:
            self.traces_this_minute += 1
        
        return sampled
    
    def _maybe_adjust(self):
        """Adjust sampling rate based on observed patterns."""
        if len(self.error_rates) < 10:
            return
        
        # Detect error rate anomaly
        error_rate = sum(self.error_rates) / len(self.error_rates)
        
        # Detect latency anomaly (> 3 standard deviations)
        if len(self.latencies) > 10:
            mean_lat = sum(self.latencies) / len(self.latencies)
            variance = sum((x - mean_lat) ** 2 for x in self.latencies) / len(self.latencies)
            std_lat = math.sqrt(variance)
            latest_lat = self.latencies[-1]
            latency_anomaly = (latest_lat - mean_lat) > 3 * std_lat if std_lat > 0 else False
        else:
            latency_anomaly = False
        
        # Adjust rate
        if error_rate > 0.05 or latency_anomaly:
            # Anomaly detected - increase sampling
            self.current_rate = min(
                self.config.target_rate * self.config.anomaly_multiplier,
                self.config.max_rate
            )
            self.in_anomaly = True
            self.anomaly_end_time = time.time() + self.config.cooldown_seconds
        elif self.in_anomaly and time.time() > self.anomaly_end_time:
            # Cooldown expired - return to normal
            self.current_rate = self.config.target_rate
            self.in_anomaly = False
        
        # Never go below minimum
        self.current_rate = max(self.current_rate, self.config.min_rate)
```

---

## Approximate Algorithms for Scale

### HyperLogLog for Distinct Counts

```python
"""
hyperloglog_metrics.py
Use HyperLogLog for cardinality estimation without storing every value.
Error rate: ~1.04 / sqrt(m) where m = number of registers.
With 16384 registers: ~0.81% error.
"""

import hashlib
import struct
from prometheus_client import Gauge

class HyperLogLogMetric:
    """
    Prometheus-compatible metric that uses HyperLogLog internally.
    Tracks approximate distinct count without high cardinality.
    """
    
    def __init__(self, name: str, description: str, precision: int = 14):
        """
        Args:
            precision: Number of bits for register addressing (14 = 16384 registers)
        """
        self.precision = precision
        self.num_registers = 1 << precision
        self.registers = bytearray(self.num_registers)
        
        # Expose as Prometheus gauge
        self.gauge = Gauge(
            name,
            description,
            ['pipeline']
        )
    
    def add(self, value: str, pipeline: str = "default"):
        """Add a value to the HLL sketch."""
        hash_val = self._hash(value)
        
        # First `precision` bits determine register index
        index = hash_val >> (64 - self.precision)
        
        # Remaining bits: count leading zeros + 1
        remaining = hash_val << self.precision | (1 << (self.precision - 1))
        run_length = self._count_leading_zeros(remaining) + 1
        
        # Update register with max
        self.registers[index] = max(self.registers[index], run_length)
        
        # Update Prometheus metric periodically
        self.gauge.labels(pipeline=pipeline).set(self.estimate())
    
    def estimate(self) -> float:
        """Estimate cardinality using harmonic mean."""
        alpha = self._get_alpha()
        raw_estimate = alpha * self.num_registers ** 2 / sum(
            2.0 ** (-r) for r in self.registers
        )
        
        # Small range correction
        if raw_estimate <= 2.5 * self.num_registers:
            zeros = self.registers.count(0)
            if zeros > 0:
                return self.num_registers * math.log(self.num_registers / zeros)
        
        return raw_estimate
    
    def _hash(self, value: str) -> int:
        h = hashlib.md5(value.encode()).digest()
        return struct.unpack('<Q', h[:8])[0]
    
    def _count_leading_zeros(self, value: int) -> int:
        if value == 0:
            return 64
        count = 0
        for i in range(63, -1, -1):
            if value & (1 << i):
                break
            count += 1
        return count
    
    def _get_alpha(self) -> float:
        if self.num_registers >= 128:
            return 0.7213 / (1 + 1.079 / self.num_registers)
        return {16: 0.673, 32: 0.697, 64: 0.709}[self.num_registers]


# Usage in pipeline
import math

unique_users = HyperLogLogMetric(
    "pipeline_unique_users_approx",
    "Approximate number of unique users processed"
)

# In event processing loop:
# unique_users.add(event.user_id, pipeline="ingestion")
# Exposes: pipeline_unique_users_approx{pipeline="ingestion"} 1523847
```

### Count-Min Sketch for Frequency Estimation

```python
"""
count_min_sketch.py
Estimate frequency of events without storing per-event counters.
Useful for: "How many events did customer X send?" without a metric per customer.
"""

import hashlib
import array
from typing import Tuple

class CountMinSketch:
    """
    Probabilistic frequency counter.
    Space: O(width * depth) = O(1/epsilon * ln(1/delta))
    Error: actual_count <= estimated_count <= actual_count + epsilon * N
    """
    
    def __init__(self, width: int = 10000, depth: int = 7):
        """
        Args:
            width: Number of counters per row (affects accuracy)
            depth: Number of hash functions (affects confidence)
        """
        self.width = width
        self.depth = depth
        self.table = [array.array('L', [0] * width) for _ in range(depth)]
        self.total_count = 0
    
    def add(self, item: str, count: int = 1):
        """Increment count for an item."""
        self.total_count += count
        for i in range(self.depth):
            index = self._hash(item, i)
            self.table[i][index] += count
    
    def estimate(self, item: str) -> int:
        """Get estimated count (always >= actual, may overcount)."""
        return min(
            self.table[i][self._hash(item, i)]
            for i in range(self.depth)
        )
    
    def _hash(self, item: str, seed: int) -> int:
        h = hashlib.md5(f"{seed}:{item}".encode()).hexdigest()
        return int(h[:8], 16) % self.width
    
    def top_k_detection(self, item: str, threshold_fraction: float = 0.001) -> bool:
        """Check if item is a heavy hitter (> threshold of total)."""
        return self.estimate(item) > threshold_fraction * self.total_count


# Integration with monitoring
class FrequencyMonitor:
    """Monitor event frequencies without per-entity metrics."""
    
    def __init__(self):
        self.customer_events = CountMinSketch(width=50000, depth=7)
        self.error_by_type = CountMinSketch(width=1000, depth=5)
        
        # Only expose top-level aggregates as Prometheus metrics
        from prometheus_client import Counter, Gauge
        self.total_events = Counter('pipeline_events_total', 'Total events', ['pipeline'])
        self.heavy_hitters = Gauge('pipeline_heavy_hitter_customers', 'Count of heavy hitters')
        self.heavy_hitter_count = 0
    
    def record_event(self, customer_id: str, pipeline: str):
        """Record an event, detect heavy hitters."""
        self.customer_events.add(customer_id)
        self.total_events.labels(pipeline=pipeline).inc()
        
        # Detect if customer becomes a heavy hitter (>0.1% of traffic)
        if self.customer_events.top_k_detection(customer_id, 0.001):
            # Log alert for investigation (not a metric - would explode cardinality)
            if not hasattr(self, f'_alerted_{customer_id}'):
                setattr(self, f'_alerted_{customer_id}', True)
                self.heavy_hitter_count += 1
                self.heavy_hitters.set(self.heavy_hitter_count)
                print(f"HEAVY HITTER DETECTED: {customer_id}")
```

### t-Digest for Percentile Approximation

```python
"""
tdigest_metrics.py
Efficient percentile estimation for streaming data.
Much more memory-efficient than storing all values or using histograms
with many buckets.
"""

from dataclasses import dataclass, field
from typing import List
import bisect
import math

@dataclass
class Centroid:
    mean: float
    count: int

class TDigest:
    """
    Streaming percentile approximation.
    Maintains ~O(delta * log(n)) centroids regardless of data volume.
    Accuracy is highest at extreme percentiles (p1, p99) where it matters most.
    """
    
    def __init__(self, compression: float = 100):
        self.compression = compression
        self.centroids: List[Centroid] = []
        self.total_count = 0
        self.min_val = float('inf')
        self.max_val = float('-inf')
        self._buffer: List[float] = []
        self._buffer_size = 500
    
    def add(self, value: float):
        """Add a value to the digest."""
        self._buffer.append(value)
        self.min_val = min(self.min_val, value)
        self.max_val = max(self.max_val, value)
        
        if len(self._buffer) >= self._buffer_size:
            self._flush_buffer()
    
    def percentile(self, q: float) -> float:
        """
        Get the value at percentile q (0-100).
        Accuracy is best at extremes (p1, p99, p99.9).
        """
        self._flush_buffer()
        
        if not self.centroids:
            return 0.0
        
        if q <= 0:
            return self.min_val
        if q >= 100:
            return self.max_val
        
        target = (q / 100.0) * self.total_count
        cumulative = 0.0
        
        for i, centroid in enumerate(self.centroids):
            if cumulative + centroid.count > target:
                # Interpolate within centroid
                if i == 0:
                    return self.min_val + (centroid.mean - self.min_val) * (target / centroid.count)
                
                prev = self.centroids[i - 1]
                inner = target - cumulative
                frac = inner / centroid.count
                return prev.mean + (centroid.mean - prev.mean) * frac
            
            cumulative += centroid.count
        
        return self.max_val
    
    def _flush_buffer(self):
        """Merge buffer into centroids."""
        if not self._buffer:
            return
        
        self._buffer.sort()
        for value in self._buffer:
            self._add_centroid(Centroid(mean=value, count=1))
            self.total_count += 1
        self._buffer = []
        self._compress()
    
    def _add_centroid(self, new: Centroid):
        """Add a centroid maintaining sorted order."""
        idx = bisect.bisect_left(
            [c.mean for c in self.centroids], new.mean
        )
        self.centroids.insert(idx, new)
    
    def _compress(self):
        """Merge nearby centroids to maintain compression bound."""
        if len(self.centroids) <= self.compression:
            return
        
        new_centroids = []
        i = 0
        while i < len(self.centroids):
            current = self.centroids[i]
            
            # Try to merge with next centroid
            if i + 1 < len(self.centroids):
                next_c = self.centroids[i + 1]
                merged_count = current.count + next_c.count
                
                # Size limit based on quantile position
                q = sum(c.count for c in new_centroids) / self.total_count
                max_size = 4 * self.total_count * q * (1 - q) / self.compression
                
                if merged_count <= max(1, max_size):
                    # Merge
                    merged_mean = (
                        current.mean * current.count + next_c.mean * next_c.count
                    ) / merged_count
                    new_centroids.append(Centroid(mean=merged_mean, count=merged_count))
                    i += 2
                    continue
            
            new_centroids.append(current)
            i += 1
        
        self.centroids = new_centroids


# Usage: Pipeline latency monitoring at scale
class LatencyMonitor:
    """Track latency percentiles for 1B+ events without memory explosion."""
    
    def __init__(self):
        self.digests = {}  # Per-pipeline t-Digest
    
    def record(self, pipeline: str, latency_ms: float):
        if pipeline not in self.digests:
            self.digests[pipeline] = TDigest(compression=200)
        self.digests[pipeline].add(latency_ms)
    
    def get_percentiles(self, pipeline: str) -> dict:
        if pipeline not in self.digests:
            return {}
        d = self.digests[pipeline]
        return {
            "p50": d.percentile(50),
            "p90": d.percentile(90),
            "p95": d.percentile(95),
            "p99": d.percentile(99),
            "p99.9": d.percentile(99.9),
        }
```

---

## Pre-Aggregation at the Flink Level

```java
/**
 * FlinkMetricsAggregator.java
 * Pre-aggregate monitoring metrics within Flink operators
 * to avoid pushing per-record metrics to Prometheus.
 */

import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.metrics.Counter;
import org.apache.flink.metrics.Histogram;
import org.apache.flink.metrics.MetricGroup;
import org.apache.flink.dropwizard.metrics.DropwizardHistogramWrapper;
import com.codahale.metrics.SlidingTimeWindowArrayReservoir;
import java.util.concurrent.TimeUnit;

public class MonitoredTransformOperator<IN, OUT> extends RichMapFunction<IN, OUT> {
    
    // Bounded-cardinality counters
    private transient Counter eventsProcessed;
    private transient Counter eventsSuccess;
    private transient Counter eventsFailed;
    private transient Counter bytesProcessed;
    
    // Histogram (pre-aggregated, fixed buckets)
    private transient Histogram processingLatency;
    
    // Approximate distinct count (no label explosion)
    private transient HyperLogLogPlusCounter distinctUsers;
    
    private final String pipelineName;
    private final TransformFunction<IN, OUT> transformFn;
    
    public MonitoredTransformOperator(String pipelineName, TransformFunction<IN, OUT> fn) {
        this.pipelineName = pipelineName;
        this.transformFn = fn;
    }
    
    @Override
    public void open(Configuration parameters) throws Exception {
        MetricGroup metrics = getRuntimeContext()
            .getMetricGroup()
            .addGroup("pipeline", pipelineName);
        
        // Register counters (bounded: one per pipeline × status)
        eventsProcessed = metrics.counter("events_processed_total");
        eventsSuccess = metrics.addGroup("status", "success").counter("events_total");
        eventsFailed = metrics.addGroup("status", "failed").counter("events_total");
        bytesProcessed = metrics.counter("bytes_processed_total");
        
        // Register histogram with time-windowed reservoir
        // This gives us percentiles without storing every value
        com.codahale.metrics.Histogram dropwizardHistogram = 
            new com.codahale.metrics.Histogram(
                new SlidingTimeWindowArrayReservoir(60, TimeUnit.SECONDS)
            );
        processingLatency = metrics.histogram(
            "processing_duration_ms",
            new DropwizardHistogramWrapper(dropwizardHistogram)
        );
        
        // HLL for distinct count - exposed as gauge
        distinctUsers = new HyperLogLogPlusCounter(14); // ~0.8% error
        metrics.gauge("distinct_users_approx", () -> distinctUsers.estimate());
    }
    
    @Override
    public OUT map(IN value) throws Exception {
        long startTime = System.nanoTime();
        
        try {
            OUT result = transformFn.apply(value);
            
            // Record success metrics
            eventsProcessed.inc();
            eventsSuccess.inc();
            bytesProcessed.inc(getSize(value));
            
            // Record latency
            long durationMs = (System.nanoTime() - startTime) / 1_000_000;
            processingLatency.update(durationMs);
            
            // Track distinct users (approximate, no cardinality explosion)
            String userId = extractUserId(value);
            if (userId != null) {
                distinctUsers.add(userId);
            }
            
            return result;
            
        } catch (Exception e) {
            eventsFailed.inc();
            eventsProcessed.inc();
            
            // Only log sampled errors (not every one)
            if (shouldSampleError(value)) {
                logDetailedError(value, e);
            }
            
            throw e;
        }
    }
    
    private boolean shouldSampleError(IN value) {
        // Sample 10% of errors for detailed logging
        return Math.abs(value.hashCode()) % 10 == 0;
    }
}
```

---

## Tiered Alert System

```yaml
# tiered-alerts.yaml
# Different alert speeds for different signals

apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: tiered-pipeline-alerts
  namespace: monitoring
spec:
  groups:
    # TIER 1: Immediate (seconds) - From real-time counters
    - name: pipeline.immediate
      interval: 15s
      rules:
        - alert: PipelineCompletelyDown
          expr: rate(pipeline_events_processed_total[2m]) == 0
          for: 2m
          labels:
            severity: critical
            tier: immediate
            response_time: "5m"

        - alert: PipelineErrorSpike
          expr: |
            rate(pipeline_events_processed_total{status="failed"}[1m]) 
            > 10 * avg_over_time(
              rate(pipeline_events_processed_total{status="failed"}[1m])[1h:1m]
            )
          for: 1m
          labels:
            severity: critical
            tier: immediate

    # TIER 2: Near-real-time (minutes) - From Prometheus metrics
    - name: pipeline.near_realtime
      interval: 1m
      rules:
        - alert: PipelineSLOBreach
          expr: pipeline:error_rate:ratio5m > 0.01
          for: 5m
          labels:
            severity: warning
            tier: near_realtime
            response_time: "30m"

        - alert: PipelineLatencyDegraded
          expr: pipeline:latency_seconds:p99_5m > 30
          for: 10m
          labels:
            severity: warning
            tier: near_realtime

    # TIER 3: Hourly batch - Results pushed from Spark validation jobs
    - name: pipeline.batch_hourly
      interval: 5m
      rules:
        - alert: DataReconciliationMismatch
          expr: |
            pipeline_batch_reconciliation_difference_ratio > 0.001
          for: 0m  # Fire immediately when batch job reports
          labels:
            severity: warning
            tier: batch
            response_time: "4h"

        - alert: SchemaValidationFailure
          expr: pipeline_schema_validation_failures_total > 0
          for: 0m
          labels:
            severity: warning
            tier: batch

    # TIER 4: Daily - From Great Expectations / deep analysis
    - name: pipeline.daily_analysis
      interval: 5m
      rules:
        - alert: DataDriftDetected
          expr: pipeline_data_drift_score > 0.3
          for: 0m
          labels:
            severity: info
            tier: daily
            response_time: "next_business_day"

        - alert: StatisticalAnomalyDetected
          expr: pipeline_anomaly_score > 3.0
          for: 0m
          labels:
            severity: info
            tier: daily
```

---

## Cost Management

### Monitoring Cost Calculator

```python
"""
monitoring_cost_calculator.py
Calculate and project monitoring infrastructure costs.
"""

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class MonitoringCosts:
    """Cost model for monitoring infrastructure."""
    
    # Metrics (Prometheus/Mimir/Thanos)
    metric_series_count: int = 500_000
    scrape_interval_seconds: int = 15
    metrics_retention_days: int = 365
    
    # Logs (Loki/ELK)
    log_lines_per_day: int = 10_000_000_000  # 10B
    avg_log_line_bytes: int = 200
    log_retention_days: int = 30
    log_sampling_rate: float = 0.1  # Keep 10%
    
    # Traces (Tempo/Jaeger)
    spans_per_day: int = 1_000_000_000  # 1B
    avg_span_bytes: int = 500
    trace_sampling_rate: float = 0.01  # Keep 1%
    trace_retention_days: int = 7
    
    # Infrastructure costs (AWS pricing approximation)
    s3_per_gb_month: float = 0.023
    s3_ia_per_gb_month: float = 0.0125
    compute_per_vcpu_hour: float = 0.05
    memory_per_gb_hour: float = 0.007
    
    def metrics_storage_cost_monthly(self) -> float:
        """Calculate monthly metrics storage cost."""
        samples_per_day = self.metric_series_count * (86400 / self.scrape_interval_seconds)
        bytes_per_day = samples_per_day * 2  # ~2 bytes per sample compressed
        gb_per_day = bytes_per_day / (1024**3)
        
        # Tiered: first 15 days on SSD, rest on S3
        hot_gb = gb_per_day * 15
        warm_gb = gb_per_day * min(self.metrics_retention_days - 15, 75)
        cold_gb = gb_per_day * max(self.metrics_retention_days - 90, 0)
        
        hot_cost = hot_gb * 0.10  # gp3 EBS ~$0.08/GB-month
        warm_cost = warm_gb * self.s3_per_gb_month
        cold_cost = cold_gb * self.s3_ia_per_gb_month
        
        return hot_cost + warm_cost + cold_cost
    
    def logs_storage_cost_monthly(self) -> float:
        """Calculate monthly log storage cost."""
        raw_gb_per_day = (
            self.log_lines_per_day * self.avg_log_line_bytes * self.log_sampling_rate
        ) / (1024**3)
        
        # Loki compression ratio ~15x
        compressed_gb_per_day = raw_gb_per_day / 15
        total_gb = compressed_gb_per_day * self.log_retention_days
        
        return total_gb * self.s3_per_gb_month
    
    def traces_storage_cost_monthly(self) -> float:
        """Calculate monthly trace storage cost."""
        sampled_spans = self.spans_per_day * self.trace_sampling_rate
        raw_gb_per_day = (sampled_spans * self.avg_span_bytes) / (1024**3)
        
        # Tempo compression ~5x
        compressed_gb_per_day = raw_gb_per_day / 5
        total_gb = compressed_gb_per_day * self.trace_retention_days
        
        return total_gb * self.s3_per_gb_month
    
    def compute_cost_monthly(self) -> float:
        """Calculate compute costs for monitoring stack."""
        components = {
            "prometheus_shards": {"vcpu": 16, "memory_gb": 64},
            "thanos_query": {"vcpu": 6, "memory_gb": 12},
            "thanos_store": {"vcpu": 4, "memory_gb": 16},
            "thanos_compact": {"vcpu": 4, "memory_gb": 8},
            "loki_ingester": {"vcpu": 8, "memory_gb": 32},
            "loki_querier": {"vcpu": 4, "memory_gb": 8},
            "tempo_ingester": {"vcpu": 4, "memory_gb": 16},
            "otel_collector": {"vcpu": 8, "memory_gb": 16},
            "grafana": {"vcpu": 3, "memory_gb": 6},
            "alertmanager": {"vcpu": 1, "memory_gb": 2},
        }
        
        total_cost = 0
        hours_per_month = 730
        
        for component, resources in components.items():
            cpu_cost = resources["vcpu"] * self.compute_per_vcpu_hour * hours_per_month
            mem_cost = resources["memory_gb"] * self.memory_per_gb_hour * hours_per_month
            total_cost += cpu_cost + mem_cost
        
        return total_cost
    
    def total_monthly_cost(self) -> Dict[str, float]:
        """Complete cost breakdown."""
        return {
            "metrics_storage": self.metrics_storage_cost_monthly(),
            "logs_storage": self.logs_storage_cost_monthly(),
            "traces_storage": self.traces_storage_cost_monthly(),
            "compute": self.compute_cost_monthly(),
            "total": (
                self.metrics_storage_cost_monthly() +
                self.logs_storage_cost_monthly() +
                self.traces_storage_cost_monthly() +
                self.compute_cost_monthly()
            )
        }
    
    def optimization_recommendations(self) -> List[Dict]:
        """Suggest cost optimizations."""
        recommendations = []
        
        costs = self.total_monthly_cost()
        
        if self.log_sampling_rate > 0.05:
            savings = costs["logs_storage"] * 0.5
            recommendations.append({
                "action": "Reduce log sampling to 5%",
                "monthly_savings": savings,
                "risk": "Less log coverage for debugging"
            })
        
        if self.metric_series_count > 200_000:
            recommendations.append({
                "action": "Audit and drop unused metrics (target: 200K series)",
                "monthly_savings": costs["metrics_storage"] * 0.4,
                "risk": "May lose visibility into edge cases"
            })
        
        if self.trace_sampling_rate > 0.005:
            recommendations.append({
                "action": "Use tail-based sampling at 0.5% + 100% errors",
                "monthly_savings": costs["traces_storage"] * 0.5,
                "risk": "Fewer normal traces available"
            })
        
        return recommendations


# Run cost analysis
if __name__ == "__main__":
    costs = MonitoringCosts()
    breakdown = costs.total_monthly_cost()
    
    print("=" * 60)
    print("MONITORING INFRASTRUCTURE COST ESTIMATE (Monthly)")
    print("=" * 60)
    for category, cost in breakdown.items():
        print(f"  {category:20s}: ${cost:,.2f}")
    print("=" * 60)
    
    print("\nOPTIMIZATION RECOMMENDATIONS:")
    for rec in costs.optimization_recommendations():
        print(f"  • {rec['action']}")
        print(f"    Savings: ${rec['monthly_savings']:,.2f}/mo | Risk: {rec['risk']}")
```

---

## Summary

Monitoring at billion-event scale requires fundamentally different approaches:

| Approach | Naive (Doesn't Scale) | Production (Scales) |
|----------|----------------------|---------------------|
| Counting | Metric per customer | Pre-aggregated counters + CMS for drill-down |
| Percentiles | Store all values | t-Digest / DDSketch streaming approximation |
| Distinct counts | Set of all IDs | HyperLogLog (~1% error, fixed memory) |
| Tracing | Trace every event | Tail-based sampling (errors + slow + 1%) |
| Logging | Log every event | Structured + sampled + tiered retention |
| Alerting | Real-time everything | Tiered: immediate/hourly/daily by criticality |

Key principles:
1. **Aggregate at source** - Don't push per-record data to monitoring systems
2. **Sample intelligently** - Keep 100% of interesting, 1% of boring
3. **Approximate where possible** - HLL, CMS, t-Digest give 99%+ accuracy at 0.01% cost
4. **Tier by urgency** - Not everything needs sub-second detection
5. **Budget explicitly** - Know your cost per series, per GB, per trace
