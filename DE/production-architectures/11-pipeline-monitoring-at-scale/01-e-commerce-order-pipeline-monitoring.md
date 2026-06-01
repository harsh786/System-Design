# E-Commerce Order Pipeline Monitoring at Scale

## Problem Statement

At Amazon/Shopify scale, an order processing pipeline handles **billions of orders annually** with peak throughput exceeding **50,000 orders/second** during Black Friday events. The pipeline spans payment processing, inventory management, fulfillment orchestration, and shipping — each stage producing and consuming events that must flow without data loss.

**Every lost or duplicated order directly impacts revenue:**
- A dropped payment event = order never fulfilled = lost sale + customer churn
- A duplicated inventory decrement = phantom stock reduction = overselling
- A delayed shipping event = missed SLA = refund + reputation damage

The monitoring system must itself handle **10 billion events/day** during peak, detecting anomalies within seconds while maintaining low operational overhead during normal periods.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        E-COMMERCE ORDER PIPELINE ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  Web/App │    │  Mobile  │    │   POS    │    │ Partner  │    │  Bulk    │
  │  Orders  │    │  Orders  │    │  Orders  │    │   API    │    │ Imports  │
  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
       │               │               │               │               │
       └───────────────┴───────┬───────┴───────────────┴───────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              KAFKA CLUSTER (Multi-AZ)                                 │
│                                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │   orders    │  │  payments   │  │  inventory  │  │  shipping   │               │
│  │  (128 part) │  │  (64 part)  │  │  (64 part)  │  │  (32 part)  │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         │                │                │                │                        │
│  [TAP-1]●         [TAP-2]●         [TAP-3]●         [TAP-4]●    ← Monitoring Taps  │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         APACHE FLINK CLUSTER (Kubernetes)                             │
│                                                                                       │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐               │
│  │  Order Validation │  │ Payment Matching  │  │ Inventory Update  │               │
│  │  & Deduplication  │  │ & Reconciliation  │  │  & Reservation    │               │
│  └────────┬──────────┘  └────────┬──────────┘  └────────┬──────────┘               │
│           │                      │                      │                           │
│    [TAP-5]●               [TAP-6]●               [TAP-7]●          ← Process Taps   │
│           │                      │                      │                           │
│           └──────────────────────┴──────────────────────┘                           │
│                                  │                                                   │
│                                  ▼                                                   │
│                    ┌──────────────────────────┐                                      │
│                    │  Unified Order State      │                                      │
│                    │  Machine (Flink Stateful) │                                      │
│                    └────────────┬─────────────┘                                      │
│                          [TAP-8]●                                                    │
└─────────────────────────────────┼───────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
          ┌─────────────┐ ┌────────────┐ ┌──────────────┐
          │  Iceberg     │ │ ClickHouse │ │  Downstream  │
          │  Data Lake   │ │  (OLAP)    │ │  Services    │
          │  (S3/HDFS)   │ │            │ │              │
          └──────┬───────┘ └─────┬──────┘ └──────────────┘
                 │               │
          [TAP-9]●        [TAP-10]●
                 │               │
                 ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           MONITORING & OBSERVABILITY LAYER                            │
│                                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Prometheus│  │  Grafana  │  │PagerDuty │  │ RunBooks │  │ Slack    │            │
│  │ + Thanos │  │          │  │          │  │ (Auto)   │  │ Alerts   │            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Monitoring Tap Architecture

Each TAP in the diagram represents a lightweight monitoring sidecar that emits metrics without impacting the data path:

```
┌────────────────────────────────────────────────────────────┐
│                     MONITORING TAP DETAIL                    │
│                                                              │
│   Data Flow          Tap                    Metrics Sink     │
│  ──────────►    ┌──────────┐            ┌──────────────┐   │
│                 │ Counter  │──metrics──► │  Prometheus  │   │
│  ──────────►    │ Sampler  │            │  Remote Write │   │
│                 │ Latency  │──traces──► │  Tempo/Jaeger│   │
│  ──────────►    │ Schema   │            │              │   │
│                 │ Validator│──logs────► │  Loki        │   │
│                 └──────────┘            └──────────────┘   │
│                                                              │
│   Overhead budget: < 0.5% latency, < 2% CPU per tap        │
└────────────────────────────────────────────────────────────┘
```

---

## Key Monitoring Challenges

### 1. Order Duplication Detection

At 50K orders/sec, Kafka's at-least-once delivery guarantees mean duplicates are inevitable during broker failovers or producer retries.

```
Problem Timeline:
─────────────────────────────────────────────────────────────────
t=0     t=1s    t=2s    t=3s    t=4s    t=5s
│       │       │       │       │       │
▼       ▼       ▼       ▼       ▼       ▼
Order   Kafka   Producer Order   Flink   DUPLICATE
Created Timeout Retry   Reappears Dedup  Detected
                │               Catches  & Counted
                └── Network     It
                    Partition
─────────────────────────────────────────────────────────────────
```

**Monitoring approach:**
- Track dedup rate per partition: sudden spikes indicate infrastructure issues
- Maintain a Bloom filter of recent order IDs with a 24-hour window
- Compare Flink's exactly-once output count vs Kafka input count

### 2. Payment Reconciliation Drift

Orders and payments arrive through separate topics. Drift occurs when one side processes faster than the other.

```
Orders Topic:  ████████████████████████████  → 50,000/sec
Payments Topic: ███████████████████████       → 47,200/sec  ← 5.6% DRIFT!

Expected: ratio stays within 0.1% over any 5-minute window
```

### 3. Inventory Sync Lag

```
                    ┌─── Warehouse A updates ───┐
                    │                            ▼
  Actual Stock ─────┼─── Warehouse B updates ───┼──► Inventory Topic ──► Flink ──► DB
                    │                            │
                    └─── Warehouse C updates ───┘
                                                 │
                              Lag here = overselling risk
                              Threshold: < 5 seconds during peak
```

### 4. End-to-End Order Latency

```
┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│Submit│──►│Kafka │──►│Valid- │──►│Pay-  │──►│Inven-│──►│Ship  │
│Order │   │Ingest│   │ation │   │ment  │   │tory  │   │Label │
└──────┘   └──────┘   └──────┘   └──────┘   └──────┘   └──────┘
   │           │           │           │           │         │
   │◄─ 50ms ─►│◄─ 200ms ─►│◄─ 800ms ─►│◄─ 100ms─►│◄─150ms─►│
   │                                                          │
   │◄──────────────── p99 TARGET: < 5 seconds ──────────────►│
```

### 5. Peak Traffic Burst Handling

```
Normal Day:     ████████░░░░░░░░░░░░  5K orders/sec
Flash Sale:     ████████████████████  50K orders/sec  (10x)
Black Friday:   ████████████████████████████████████  100K+ orders/sec (20x)
                                     ▲
                                     │
                     Monitoring must auto-scale with traffic
                     without becoming a bottleneck itself
```

---

## Metrics to Monitor

### Core Business Metrics

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `orders_processed_total` | Counter | `source`, `status`, `region` | Total orders processed by outcome |
| `orders_failed_total` | Counter | `source`, `failure_reason`, `stage` | Failed orders with failure categorization |
| `payment_reconciliation_drift_count` | Gauge | `direction` (over/under) | Current unreconciled order-payment pairs |
| `inventory_sync_lag_seconds` | Gauge | `warehouse`, `product_category` | Time since last inventory sync per warehouse |
| `order_end_to_end_latency_seconds` | Histogram | `source`, `priority` | Full order lifecycle duration |
| `order_dedup_rate` | Gauge | `partition` | Percentage of duplicate orders detected |

### Infrastructure Metrics

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `kafka_consumer_lag` | Gauge | `topic`, `partition`, `consumer_group` | Messages behind head |
| `kafka_consumer_lag_rate` | Gauge | `topic`, `consumer_group` | Rate of lag change (growing/shrinking) |
| `flink_checkpoint_duration_seconds` | Histogram | `job_name`, `checkpoint_type` | Time to complete checkpoints |
| `flink_checkpoint_size_bytes` | Gauge | `job_name` | State checkpoint size |
| `flink_backpressure_ratio` | Gauge | `job_name`, `operator`, `subtask` | Backpressure percentage |
| `clickhouse_insert_lag_seconds` | Gauge | `table` | Delay from event time to query availability |

### Data Quality Metrics

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `schema_validation_failures_total` | Counter | `topic`, `error_type` | Schema validation failures |
| `null_field_rate` | Gauge | `topic`, `field_name` | Percentage of null values in required fields |
| `event_time_skew_seconds` | Histogram | `source` | Difference between event time and ingestion time |
| `late_arriving_events_total` | Counter | `topic`, `window` | Events arriving after watermark |

---

## Alert Rules

### Critical Alerts (Page Immediately)

```yaml
# alert-rules.yaml

groups:
  - name: order_pipeline_critical
    rules:
      # Consumer lag growing uncontrollably
      - alert: KafkaConsumerLagCritical
        expr: |
          kafka_consumer_lag{topic="orders"} > 100000
          and
          rate(kafka_consumer_lag{topic="orders"}[2m]) > 0
        for: 2m
        labels:
          severity: critical
          team: data-platform
        annotations:
          summary: "Kafka consumer lag exceeding 100K and growing"
          description: |
            Consumer group {{ $labels.consumer_group }} on topic {{ $labels.topic }}
            partition {{ $labels.partition }} has lag {{ $value }} and is growing.
            This means order processing is falling behind ingestion rate.
          runbook_url: "https://runbooks.internal/kafka-lag-critical"
          impact: "Orders are being delayed. Customer-facing SLA at risk."

      # Payment reconciliation drift
      - alert: PaymentDriftCritical
        expr: |
          (
            payment_reconciliation_drift_count{direction="orders_without_payment"}
            /
            rate(orders_processed_total[5m]) * 300
          ) > 0.001
        for: 5m
        labels:
          severity: critical
          team: payments
        annotations:
          summary: "Payment drift exceeds 0.1% of order volume"
          description: |
            {{ $value | humanizePercentage }} of orders in the last 5 minutes
            have no matching payment event. Revenue at risk.
          runbook_url: "https://runbooks.internal/payment-drift"

      # Order processing latency
      - alert: OrderLatencyP99Critical
        expr: |
          histogram_quantile(0.99,
            rate(order_end_to_end_latency_seconds_bucket[5m])
          ) > 5
        for: 3m
        labels:
          severity: critical
          team: order-platform
        annotations:
          summary: "Order end-to-end p99 latency exceeds 5 seconds"
          description: |
            p99 latency is {{ $value }}s. Target is 5s.
            Check Flink backpressure and checkpoint durations.

      # Error rate spike
      - alert: OrderErrorRateSpike
        expr: |
          (
            rate(orders_failed_total[5m])
            /
            rate(orders_processed_total[5m])
          ) > 0.01
          and
          rate(orders_processed_total[5m]) > 100
        for: 2m
        labels:
          severity: critical
          team: order-platform
        annotations:
          summary: "Order failure rate exceeds 1%"
          description: |
            Error rate is {{ $value | humanizePercentage }}.
            Top failure reason: check orders_failed_total by failure_reason.
```

### Warning Alerts

```yaml
      # Checkpoint duration growing
      - alert: FlinkCheckpointSlow
        expr: |
          histogram_quantile(0.95,
            rate(flink_checkpoint_duration_seconds_bucket[10m])
          ) > 30
        for: 10m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Flink checkpoints taking > 30s (p95)"
          description: |
            Slow checkpoints indicate growing state size or I/O issues.
            May lead to checkpoint failures and data loss risk.

      # Inventory lag warning
      - alert: InventorySyncLagWarning
        expr: inventory_sync_lag_seconds > 10
        for: 5m
        labels:
          severity: warning
          team: inventory
        annotations:
          summary: "Inventory sync lag > 10s for {{ $labels.warehouse }}"
          description: |
            Warehouse {{ $labels.warehouse }} inventory is {{ $value }}s behind.
            Risk of overselling if lag increases.

      # Late events increasing
      - alert: LateEventsIncreasing
        expr: |
          rate(late_arriving_events_total[10m]) > 
          2 * rate(late_arriving_events_total[1h] offset 1h)
        for: 10m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Late-arriving events rate doubled"
```

---

## Grafana Dashboard Design

### Dashboard: Order Pipeline Health (Executive Overview)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ROW 1: Key Business Metrics (Stat Panels)                               │
│                                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Orders  │  │  Revenue │  │  Error   │  │  p99     │  │  Recon   │ │
│  │  /sec    │  │  /min    │  │  Rate    │  │  Latency │  │  Drift   │ │
│  │  48,231  │  │  $2.1M   │  │  0.02%   │  │  3.2s    │  │  0.04%   │ │
│  │  ▲ +12%  │  │  ▲ +8%   │  │  ✓ OK    │  │  ✓ OK    │  │  ✓ OK    │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 2: Time Series (Past 6 hours)                                       │
│                                                                           │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │  Orders Processed vs Failed    │  │  End-to-End Latency (p50/p95/99)│ │
│  │  ████████████████████████████  │  │         ___                    │ │
│  │  ████████████████████████████  │  │  ──────/   \──────── p99      │ │
│  │  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁  │  │  ──────────────────── p50      │ │
│  │  (green=success, red=failed)   │  │                                │ │
│  └────────────────────────────────┘  └────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 3: Infrastructure Health                                            │
│                                                                           │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │  Kafka Consumer Lag (per topic)│  │  Flink Backpressure (heatmap)  │ │
│  │  orders:    ████░░ 45K         │  │  ┌──┬──┬──┬──┬──┬──┬──┬──┐   │ │
│  │  payments:  ██░░░░ 12K         │  │  │▓▓│░░│░░│▓▓│░░│░░│░░│░░│   │ │
│  │  inventory: █░░░░░ 3K          │  │  │░░│░░│░░│░░│░░│░░│░░│░░│   │ │
│  │  shipping:  ░░░░░░ 200         │  │  └──┴──┴──┴──┴──┴──┴──┴──┘   │ │
│  └────────────────────────────────┘  └────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│  ROW 4: Reconciliation & Data Quality                                    │
│                                                                           │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │  Payment Reconciliation Drift  │  │  Schema Validation Failures    │ │
│  │  ──────────────/\──────────    │  │  ▁▁▁▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁    │ │
│  │  Threshold: ─ ─ ─ ─ 0.1% ─ ─ │  │  (spike at 14:32 - schema v3) │ │
│  └────────────────────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Grafana Queries

```sql
-- Orders per second by source
rate(orders_processed_total{status="success"}[1m])

-- Error rate percentage
100 * rate(orders_failed_total[5m]) / rate(orders_processed_total[5m])

-- Consumer lag with growing/shrinking indicator
kafka_consumer_lag{consumer_group="order-processor"}

-- Latency heatmap
sum(rate(order_end_to_end_latency_seconds_bucket[5m])) by (le)

-- Payment drift percentage
payment_reconciliation_drift_count / ignoring(direction)
  group_left sum(rate(orders_processed_total[5m])) * 300
```

---

## Production Code Examples

### 1. Custom Flink Metrics Reporter

```java
/**
 * Custom metrics for the order processing Flink job.
 * Reports business-level metrics alongside infrastructure metrics.
 */
public class OrderPipelineMetrics extends RichFlatMapFunction<Order, ProcessedOrder> {

    // Counters
    private transient Counter ordersProcessed;
    private transient Counter ordersFailed;
    private transient Counter duplicatesDetected;

    // Gauges
    private transient Gauge<Long> currentLag;

    // Histograms
    private transient Histogram processingLatency;

    // State for deduplication
    private transient MapState<String, Long> seenOrderIds;

    @Override
    public void open(Configuration parameters) {
        MetricGroup metrics = getRuntimeContext().getMetricGroup()
            .addGroup("order_pipeline");

        this.ordersProcessed = metrics.counter("orders_processed_total");
        this.ordersFailed = metrics.counter("orders_failed_total");
        this.duplicatesDetected = metrics.counter("duplicates_detected_total");

        this.processingLatency = metrics.histogram("processing_latency_ms",
            new DescriptiveStatisticsHistogram(10000));

        // Lag gauge - reports current consumer offset lag
        AtomicLong lagValue = new AtomicLong(0);
        this.currentLag = metrics.gauge("consumer_lag", lagValue::get);

        // State for dedup with TTL
        StateTtlConfig ttlConfig = StateTtlConfig.newBuilder(Time.hours(24))
            .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .build();

        MapStateDescriptor<String, Long> dedupeDesc =
            new MapStateDescriptor<>("seen-orders", String.class, Long.class);
        dedupeDesc.enableTimeToLive(ttlConfig);
        this.seenOrderIds = getRuntimeContext().getMapState(dedupeDesc);
    }

    @Override
    public void flatMap(Order order, Collector<ProcessedOrder> out) throws Exception {
        long startTime = System.currentTimeMillis();

        try {
            // Deduplication check
            if (seenOrderIds.contains(order.getOrderId())) {
                duplicatesDetected.inc();
                return;  // Skip duplicate
            }
            seenOrderIds.put(order.getOrderId(), System.currentTimeMillis());

            // Process order
            ProcessedOrder result = processOrder(order);
            out.collect(result);
            ordersProcessed.inc();

        } catch (Exception e) {
            ordersFailed.inc();
            // Emit to dead letter queue
            emitToDeadLetter(order, e);
        } finally {
            long duration = System.currentTimeMillis() - startTime;
            processingLatency.update(duration);
        }
    }

    private ProcessedOrder processOrder(Order order) {
        // Business logic: validate, enrich, transform
        return new ProcessedOrder(order, OrderStatus.VALIDATED);
    }
}
```

### 2. Kafka Consumer Lag Monitor

```python
#!/usr/bin/env python3
"""
Kafka consumer lag monitoring service.
Exposes Prometheus metrics for consumer group lag across all topics.
Supports alerting on lag growth rate, not just absolute values.
"""

import time
import logging
from dataclasses import dataclass
from typing import Dict, List
from confluent_kafka.admin import AdminClient, ConsumerGroupTopicPartitions
from prometheus_client import Gauge, Counter, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Prometheus metrics
CONSUMER_LAG = Gauge(
    'kafka_consumer_lag',
    'Consumer group lag per partition',
    ['topic', 'partition', 'consumer_group']
)
CONSUMER_LAG_RATE = Gauge(
    'kafka_consumer_lag_rate',
    'Rate of lag change per second (positive=growing)',
    ['topic', 'consumer_group']
)
LAG_CHECK_DURATION = Histogram(
    'kafka_lag_check_duration_seconds',
    'Time to compute lag for all groups'
)
LAG_CHECK_ERRORS = Counter(
    'kafka_lag_check_errors_total',
    'Errors encountered during lag checks',
    ['error_type']
)


@dataclass
class LagSnapshot:
    timestamp: float
    total_lag: int
    per_partition: Dict[int, int]


class KafkaLagMonitor:
    def __init__(self, bootstrap_servers: str, consumer_groups: List[str],
                 check_interval_seconds: int = 10):
        self.admin = AdminClient({'bootstrap.servers': bootstrap_servers})
        self.consumer_groups = consumer_groups
        self.check_interval = check_interval_seconds
        self.lag_history: Dict[str, List[LagSnapshot]] = {}

    def get_consumer_lag(self, group: str) -> Dict[str, Dict[int, int]]:
        """Get lag per topic-partition for a consumer group."""
        try:
            # Get committed offsets
            committed = self.admin.list_consumer_group_offsets(
                [ConsumerGroupTopicPartitions(group)]
            )

            lag_by_topic = {}
            for topic_partition, offset_info in committed.items():
                topic = topic_partition.topic
                partition = topic_partition.partition
                committed_offset = offset_info.offset

                # Get high watermark (latest offset)
                hw = self._get_high_watermark(topic, partition)
                lag = max(0, hw - committed_offset)

                if topic not in lag_by_topic:
                    lag_by_topic[topic] = {}
                lag_by_topic[topic][partition] = lag

            return lag_by_topic

        except Exception as e:
            LAG_CHECK_ERRORS.labels(error_type=type(e).__name__).inc()
            logger.error(f"Error getting lag for group {group}: {e}")
            return {}

    def compute_lag_rate(self, group: str, topic: str, current_lag: int) -> float:
        """Compute the rate of lag change over the last minute."""
        key = f"{group}:{topic}"
        now = time.time()

        if key not in self.lag_history:
            self.lag_history[key] = []

        self.lag_history[key].append(LagSnapshot(
            timestamp=now, total_lag=current_lag, per_partition={}
        ))

        # Keep only last 5 minutes of history
        cutoff = now - 300
        self.lag_history[key] = [
            s for s in self.lag_history[key] if s.timestamp > cutoff
        ]

        # Compute rate over last minute
        one_min_ago = [s for s in self.lag_history[key] if s.timestamp < now - 60]
        if not one_min_ago:
            return 0.0

        oldest = one_min_ago[-1]
        time_diff = now - oldest.timestamp
        lag_diff = current_lag - oldest.total_lag
        return lag_diff / time_diff if time_diff > 0 else 0.0

    @LAG_CHECK_DURATION.time()
    def check_all_groups(self):
        """Run a single lag check across all consumer groups."""
        for group in self.consumer_groups:
            lag_by_topic = self.get_consumer_lag(group)

            for topic, partitions in lag_by_topic.items():
                total_lag = 0
                for partition, lag in partitions.items():
                    CONSUMER_LAG.labels(
                        topic=topic, partition=str(partition),
                        consumer_group=group
                    ).set(lag)
                    total_lag += lag

                # Compute and report lag rate
                rate = self.compute_lag_rate(group, topic, total_lag)
                CONSUMER_LAG_RATE.labels(
                    topic=topic, consumer_group=group
                ).set(rate)

    def run(self):
        """Main monitoring loop."""
        start_http_server(8080)
        logger.info(f"Lag monitor started. Checking every {self.check_interval}s")

        while True:
            self.check_all_groups()
            time.sleep(self.check_interval)


if __name__ == '__main__':
    monitor = KafkaLagMonitor(
        bootstrap_servers='kafka-broker-1:9092,kafka-broker-2:9092',
        consumer_groups=[
            'order-processor',
            'payment-reconciler',
            'inventory-updater',
            'shipping-dispatcher'
        ],
        check_interval_seconds=10
    )
    monitor.run()
```

### 3. Reconciliation Job (Spark SQL)

```python
"""
Daily reconciliation job comparing source (Kafka) vs target (Iceberg/ClickHouse) counts.
Runs every hour and at end-of-day for full reconciliation.
Detects: missing records, duplicates, count mismatches, and data freshness issues.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from datetime import datetime, timedelta
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import logging

logger = logging.getLogger(__name__)


class OrderReconciliation:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.registry = CollectorRegistry()
        self.drift_gauge = Gauge(
            'reconciliation_drift_count',
            'Number of unreconciled records',
            ['direction', 'table', 'hour'],
            registry=self.registry
        )
        self.freshness_gauge = Gauge(
            'reconciliation_freshness_seconds',
            'Seconds since newest record in target',
            ['table'],
            registry=self.registry
        )

    def run_hourly_reconciliation(self, hour: datetime):
        """Compare Kafka committed offsets vs records landed in Iceberg."""

        hour_start = hour.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        logger.info(f"Reconciling hour: {hour_start} to {hour_end}")

        # Source count: Kafka offset-based (tracked by Flink)
        source_counts = self.spark.sql(f"""
            SELECT
                topic,
                SUM(end_offset - start_offset) as source_count
            FROM kafka_offset_tracking.offsets_committed
            WHERE commit_time >= '{hour_start}'
              AND commit_time < '{hour_end}'
            GROUP BY topic
        """)

        # Target count: Iceberg table
        target_counts = self.spark.sql(f"""
            SELECT
                'orders' as topic,
                COUNT(*) as target_count,
                MAX(event_time) as max_event_time,
                COUNT(*) - COUNT(DISTINCT order_id) as duplicate_count
            FROM iceberg.orders.orders_processed
            WHERE event_time >= '{hour_start}'
              AND event_time < '{hour_end}'
        """)

        # Join and compute drift
        reconciled = source_counts.join(
            target_counts, on='topic', how='full_outer'
        ).withColumn(
            'drift', F.col('source_count') - F.col('target_count')
        ).withColumn(
            'drift_pct', F.abs(F.col('drift')) / F.col('source_count') * 100
        )

        # Report metrics
        results = reconciled.collect()
        for row in results:
            topic = row['topic']
            drift = row['drift'] or 0
            duplicates = row['duplicate_count'] or 0

            direction = 'missing_in_target' if drift > 0 else 'extra_in_target'
            self.drift_gauge.labels(
                direction=direction,
                table=topic,
                hour=hour_start.isoformat()
            ).set(abs(drift))

            # Log alerts for significant drift
            drift_pct = row['drift_pct'] or 0
            if drift_pct > 0.1:
                logger.error(
                    f"RECONCILIATION ALERT: {topic} drift={drift} "
                    f"({drift_pct:.3f}%) for hour {hour_start}"
                )

            if duplicates > 0:
                logger.warning(
                    f"Duplicates detected in {topic}: {duplicates} "
                    f"for hour {hour_start}"
                )

        # Push metrics
        push_to_gateway(
            'prometheus-pushgateway:9091',
            job='order_reconciliation',
            registry=self.registry
        )

        # Write reconciliation results to audit table
        reconciled.withColumn(
            'reconciliation_time', F.current_timestamp()
        ).write.mode('append').saveAsTable(
            'iceberg.monitoring.reconciliation_results'
        )

        return reconciled

    def run_data_freshness_check(self):
        """Check how fresh data is in each target system."""

        tables = [
            ('iceberg.orders.orders_processed', 'event_time'),
            ('iceberg.orders.payments_processed', 'payment_time'),
            ('iceberg.orders.inventory_updates', 'update_time'),
        ]

        for table, time_col in tables:
            result = self.spark.sql(f"""
                SELECT
                    UNIX_TIMESTAMP(CURRENT_TIMESTAMP())
                    - UNIX_TIMESTAMP(MAX({time_col})) as staleness_seconds
                FROM {table}
            """).collect()[0]

            staleness = result['staleness_seconds']
            self.freshness_gauge.labels(table=table).set(staleness)

            if staleness > 300:  # 5 minutes
                logger.warning(f"Data freshness alert: {table} is {staleness}s stale")


if __name__ == '__main__':
    spark = SparkSession.builder \
        .appName("OrderReconciliation") \
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
        .getOrCreate()

    recon = OrderReconciliation(spark)
    recon.run_hourly_reconciliation(datetime.utcnow())
    recon.run_data_freshness_check()
```

---

## Scaling Considerations

### How Monitoring Scales During Black Friday

```
┌─────────────────────────────────────────────────────────────────────┐
│              MONITORING SCALING ARCHITECTURE                          │
│                                                                       │
│  Normal (5K/sec)          Peak (100K/sec)                            │
│  ┌──────────────┐         ┌──────────────────────────────┐          │
│  │ 2 Prometheus │         │ 8 Prometheus (sharded)       │          │
│  │ 1 Thanos     │   ──►   │ 3 Thanos (query + store)    │          │
│  │ 1 Grafana    │         │ 2 Grafana (read replicas)    │          │
│  └──────────────┘         │ 4 ClickHouse nodes           │          │
│                            └──────────────────────────────┘          │
│                                                                       │
│  Strategies:                                                          │
│  1. Prometheus federation with Thanos for long-term storage          │
│  2. Recording rules to pre-aggregate high-cardinality metrics        │
│  3. Adaptive sampling: 100% at normal, 10% sampling during peak     │
│  4. Separate monitoring cluster from production cluster              │
│  5. Circuit breaker: monitoring degrades gracefully under load       │
└─────────────────────────────────────────────────────────────────────┘
```

### Prometheus Recording Rules for Efficiency

```yaml
# recording-rules.yaml
# Pre-aggregate high-cardinality metrics to reduce query load

groups:
  - name: order_pipeline_aggregations
    interval: 15s
    rules:
      # Pre-compute per-topic lag (avoids partition-level cardinality)
      - record: kafka_consumer_lag:sum_by_topic
        expr: sum(kafka_consumer_lag) by (topic, consumer_group)

      # Pre-compute order rates by source
      - record: orders_processed:rate5m
        expr: sum(rate(orders_processed_total[5m])) by (source, status)

      # Pre-compute latency percentiles
      - record: order_latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(order_end_to_end_latency_seconds_bucket[5m])) by (le)
          )

      # Pre-compute error rate
      - record: order_error_rate:ratio_5m
        expr: |
          sum(rate(orders_failed_total[5m]))
          /
          sum(rate(orders_processed_total[5m]))
```

### Adaptive Sampling Strategy

```python
class AdaptiveMetricsSampler:
    """
    During extreme peak load, reduce monitoring overhead by sampling.
    Maintains statistical accuracy while reducing metric volume.
    """

    def __init__(self):
        self.base_sample_rate = 1.0  # 100% at normal
        self.current_rate = 1.0
        self.throughput_thresholds = [
            (10_000, 1.0),    # Below 10K/sec: sample everything
            (50_000, 0.5),    # 10K-50K/sec: 50% sampling
            (100_000, 0.1),   # 50K-100K/sec: 10% sampling
            (500_000, 0.01),  # Above 100K/sec: 1% sampling
        ]

    def should_sample(self, current_throughput: int) -> bool:
        for threshold, rate in reversed(self.throughput_thresholds):
            if current_throughput >= threshold:
                self.current_rate = rate
                break

        return random.random() < self.current_rate

    def get_scaling_factor(self) -> float:
        """Multiply counts by this to get estimated true count."""
        return 1.0 / self.current_rate
```

---

## Runbook Template

### Incident: Kafka Consumer Lag > 100K (Growing)

```markdown
## Runbook: Kafka Consumer Lag Critical

### Severity: P1 (Critical)
### SLA: Acknowledge within 5 minutes, resolve within 30 minutes

### Symptoms
- Alert: KafkaConsumerLagCritical firing
- Consumer lag growing consistently
- Order processing delays reported

### Diagnostic Steps

1. **Identify scope**
   ```bash
   # Check which consumer groups are affected
   kafka-consumer-groups.sh --bootstrap-server $BROKERS \
     --describe --all-groups | grep -v "^$" | sort -k5 -rn | head -20
   ```

2. **Check Flink job health**
   ```bash
   # Is the Flink job running?
   curl -s http://flink-jobmanager:8081/jobs | jq '.jobs[] | select(.status != "RUNNING")'
   
   # Check for backpressure
   curl -s http://flink-jobmanager:8081/jobs/$JOB_ID/vertices/$VERTEX_ID/backpressure
   ```

3. **Check for checkpoint failures**
   ```bash
   curl -s http://flink-jobmanager:8081/jobs/$JOB_ID/checkpoints | \
     jq '.history[] | select(.status == "FAILED") | {id, trigger_timestamp, failure_message}'
   ```

4. **Check Kafka broker health**
   ```bash
   # Under-replicated partitions (ISR shrinkage)
   kafka-topics.sh --bootstrap-server $BROKERS --describe \
     --under-replicated-partitions
   ```

### Resolution Actions

| Root Cause | Action |
|---|---|
| Flink job crashed | Restart from latest checkpoint: `flink run -s $SAVEPOINT_PATH` |
| Flink backpressure | Scale up parallelism: `flink modify $JOB_ID -p $NEW_PARALLELISM` |
| Checkpoint failures | Check state backend (S3/HDFS). Clear corrupted state if needed. |
| Kafka broker overload | Add partitions + rebalance consumers |
| Downstream slow (ClickHouse) | Enable async sink / increase buffer |

### Escalation
- If not resolved in 15 min → Page on-call lead
- If not resolved in 30 min → Page engineering manager
- If customer-facing impact → Incident commander activates
```

---

## Technology Stack Summary

| Component | Technology | Purpose |
|---|---|---|
| Event Streaming | Apache Kafka (MSK) | Order event transport |
| Stream Processing | Apache Flink | Stateful order processing |
| Data Lake | Apache Iceberg on S3 | Historical storage |
| OLAP Analytics | ClickHouse | Real-time analytics queries |
| Metrics | Prometheus + Thanos | Time-series metrics |
| Dashboards | Grafana | Visualization |
| Alerting | PagerDuty + Grafana Alerting | Incident management |
| Reconciliation | Apache Spark | Batch accuracy checks |
| Tracing | Jaeger/Tempo | Distributed tracing |
| Log Aggregation | Loki | Centralized logs |

---

## Key Takeaways

1. **Monitor at every boundary** — every Kafka topic, every Flink operator, every sink
2. **Reconciliation is non-negotiable** — hourly count comparisons catch silent data loss
3. **Lag rate matters more than absolute lag** — a stable 50K lag is fine; a growing 10K lag is not
4. **Pre-aggregate with recording rules** — save query costs and enable faster dashboards
5. **Monitoring must scale independently** — never let observability become a bottleneck
6. **Runbooks save MTTR** — every alert links to a runbook with exact diagnostic steps
7. **Adaptive sampling** — maintain visibility without drowning in metrics during peaks
