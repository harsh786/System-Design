# Pattern 01: Lambda Architecture

## Overview

Lambda Architecture is a data-processing architecture designed to handle massive quantities
of data by combining batch and real-time stream processing methods.

**Invented by**: Nathan Marz (creator of Apache Storm)
**Used at**: LinkedIn, Twitter, Netflix, Yahoo, Spotify

---

## Why Lambda Architecture?

### The Problem It Solves
```
CHALLENGE: How do you get BOTH:
  1. Complete, accurate results (requires seeing ALL data) 
  2. Low-latency results (requires processing data immediately)

REALITY: No single system can do both optimally.
  - Batch: Accurate but slow (hours of latency)
  - Stream: Fast but may miss/duplicate data

SOLUTION: Run BOTH in parallel, merge results.
```

### When to Use
- You need sub-second query latency AND historical accuracy
- Data volume exceeds what streaming alone can reprocess
- Business requires both real-time dashboards AND auditable reports
- You have engineering capacity for dual-path maintenance

### When NOT to Use
- Stream processing alone meets accuracy requirements (use Kappa)
- Data volume is manageable for full stream reprocessing
- Team is too small for dual-system maintenance
- Latency requirements are relaxed (>minutes)

---

## Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LAMBDA ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    DATA SOURCES                                   │        │
│  │  [Web Logs] [Click Events] [IoT Sensors] [DB Changes] [APIs]     │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────┐       │
│  │              INGESTION LAYER                                       │       │
│  │              Apache Kafka (Distributed Commit Log)                 │       │
│  │                                                                    │       │
│  │  WHY KAFKA:                                                        │       │
│  │  • Durable: Data persisted to disk, replicated                     │       │
│  │  • Replayable: Consumers can re-read from any offset               │       │
│  │  • High throughput: Millions of msgs/sec                           │       │
│  │  • Decouples: Sources don't need to know about consumers           │       │
│  │  • Partitioned: Enables parallel processing                        │       │
│  └────────────┬──────────────────────────────┬──────────────────────┘       │
│               │                              │                               │
│    ┌──────────▼──────────────┐    ┌──────────▼──────────────┐               │
│    │    BATCH LAYER           │    │    SPEED LAYER           │               │
│    │                          │    │                          │               │
│    │  Technology: Spark       │    │  Technology: Flink        │              │
│    │                          │    │                          │               │
│    │  WHY SPARK:              │    │  WHY FLINK:              │               │
│    │  • Handles PB scale      │    │  • True event-time       │              │
│    │  • Fault tolerant        │    │  • Exactly-once          │               │
│    │  • Rich SQL support      │    │  • Millisecond latency   │              │
│    │  • Mature ecosystem      │    │  • Stateful processing   │               │
│    │                          │    │                          │               │
│    │  PROCESS:                │    │  PROCESS:                │               │
│    │  1. Read ALL raw data    │    │  1. Consume from Kafka   │               │
│    │  2. Compute batch views  │    │  2. Process immediately  │               │
│    │  3. Store in serving DB  │    │  3. Update real-time view│               │
│    │  4. Run every N hours    │    │  4. Continuous           │               │
│    │                          │    │                          │               │
│    │  OUTPUT:                 │    │  OUTPUT:                 │               │
│    │  • Complete & accurate   │    │  • Approximate/recent    │              │
│    │  • High latency (hours)  │    │  • Low latency (ms)      │              │
│    └──────────┬───────────────┘    └──────────┬───────────────┘              │
│               │                               │                              │
│    ┌──────────▼───────────────────────────────▼───────────────┐              │
│    │              SERVING LAYER                                 │              │
│    │                                                           │              │
│    │  Batch Views: Apache Druid / ClickHouse / Cassandra       │              │
│    │  Speed Views: Redis / Elasticsearch / Apache Pinot        │              │
│    │                                                           │              │
│    │  MERGE STRATEGY:                                          │              │
│    │  result = batch_view(t <= last_batch) ∪ speed_view(t > last_batch)     │
│    │                                                           │              │
│    │  WHY DRUID/PINOT:                                         │              │
│    │  • Sub-second OLAP queries on huge datasets               │              │
│    │  • Column-oriented for fast aggregation                   │              │
│    │  • Real-time ingestion support                            │              │
│    │  • Horizontal scaling                                     │              │
│    └───────────────────────────────────────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Scalability Analysis

### Horizontal Scaling at Each Layer

| Layer | Scale Mechanism | Limit | Real-World Numbers |
|-------|----------------|-------|-------------------|
| Ingestion (Kafka) | Add partitions + brokers | 200K partitions/cluster | LinkedIn: 7 trillion msgs/day |
| Batch (Spark) | Add executor nodes | 10,000+ nodes | Alibaba: 100PB/day |
| Speed (Flink) | Add TaskManagers | 1000s of parallel tasks | Alibaba: 4 billion events/sec |
| Serving (Druid) | Add historical nodes | Linear with nodes | Airbnb: 1.5M queries/day |

### Data Flow Scalability
```
Throughput Calculation:
─────────────────────
Kafka: 100 partitions × 50MB/s per partition = 5 GB/s ingestion
Spark Batch: 1000 executors × 100MB/s = 100 GB/s processing
Flink Speed: 500 TaskManagers × 200K events/s = 100M events/s
Serving: 50 nodes × 10K queries/s = 500K queries/s

Bottleneck Analysis:
───────────────────
1. Kafka → Storage I/O (SSD helps)
2. Spark → Shuffle (network bandwidth)
3. Flink → State size (RocksDB + checkpoints)
4. Serving → Memory (for caching hot data)
```

### Fault Tolerance
```
┌─────────────────────────────────────────────────────────┐
│                FAULT TOLERANCE MATRIX                     │
├──────────────┬──────────────────────────────────────────┤
│ Component    │ Recovery Mechanism                         │
├──────────────┼──────────────────────────────────────────┤
│ Kafka Broker │ ISR replication (min.insync.replicas=2)   │
│ Spark Job    │ RDD lineage re-computation                │
│ Flink Job    │ Checkpoint restore from last barrier      │
│ Serving Node │ Replication factor + load balancer        │
│ Entire Zone  │ Multi-AZ deployment + failover            │
└──────────────┴──────────────────────────────────────────┘
```

---

## Runnable Example: Real-Time + Batch Analytics

### Complete Python Implementation

```python
"""
Lambda Architecture Implementation
===================================
Simulates a complete Lambda Architecture for e-commerce analytics:
- Speed Layer: Real-time revenue tracking
- Batch Layer: Accurate daily aggregations  
- Serving Layer: Merged view for queries

Run: pip install kafka-python pyspark redis flask
"""

import json
import time
import threading
import random
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple
import hashlib

# ============================================================================
# SIMULATED KAFKA (In-memory message broker for demo)
# ============================================================================

class SimulatedKafka:
    """
    Simulates Kafka's behavior:
    - Partitioned topics
    - Consumer groups with offset tracking
    - Message retention
    - Replay capability
    """
    
    def __init__(self, num_partitions: int = 4):
        self.partitions: Dict[int, List[dict]] = {
            i: [] for i in range(num_partitions)
        }
        self.num_partitions = num_partitions
        self.consumer_offsets: Dict[str, Dict[int, int]] = {}
        self._lock = threading.Lock()
    
    def produce(self, topic: str, key: str, value: dict):
        """Produce message to a partition based on key hash"""
        partition = hash(key) % self.num_partitions
        with self._lock:
            message = {
                'key': key,
                'value': value,
                'timestamp': time.time(),
                'offset': len(self.partitions[partition])
            }
            self.partitions[partition].append(message)
        return partition, message['offset']
    
    def consume(self, consumer_group: str, partition: int, 
                from_offset: int = None) -> List[dict]:
        """Consume messages from a partition"""
        with self._lock:
            if consumer_group not in self.consumer_offsets:
                self.consumer_offsets[consumer_group] = {
                    i: 0 for i in range(self.num_partitions)
                }
            
            if from_offset is not None:
                offset = from_offset
            else:
                offset = self.consumer_offsets[consumer_group][partition]
            
            messages = self.partitions[partition][offset:]
            self.consumer_offsets[consumer_group][partition] = (
                offset + len(messages)
            )
            return messages
    
    def get_all_messages(self) -> List[dict]:
        """Get all messages across all partitions (for batch layer)"""
        all_msgs = []
        for partition_msgs in self.partitions.values():
            all_msgs.extend(partition_msgs)
        return sorted(all_msgs, key=lambda x: x['timestamp'])


# ============================================================================
# SPEED LAYER (Real-time processing)
# ============================================================================

class SpeedLayer:
    """
    Processes events in real-time as they arrive.
    
    WHY THIS DESIGN:
    - Maintains in-memory counters for instant updates
    - Trades accuracy for speed (may double-count on failures)
    - Only responsible for data AFTER the last batch run
    - Gets "replaced" by batch results once batch catches up
    
    SCALABILITY:
    - Partition-parallel processing (each partition = 1 thread)
    - State stored in Redis for fast access + persistence
    - Horizontal scale by adding more consumer instances
    """
    
    def __init__(self):
        # Real-time aggregations (simulating Redis)
        self.real_time_revenue: Dict[str, float] = defaultdict(float)
        self.real_time_orders: Dict[str, int] = defaultdict(int)
        self.real_time_users: Dict[str, set] = defaultdict(set)
        self.last_processed_time: float = 0
        self._lock = threading.Lock()
    
    def process_event(self, event: dict):
        """
        Process a single event in real-time.
        
        Design Decisions:
        - Use atomic increments (simulated with locks)
        - Key by time window (minute-granularity)
        - No complex joins (speed over accuracy)
        """
        with self._lock:
            timestamp = event['timestamp']
            window_key = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d-%H:%M')
            
            if event['type'] == 'purchase':
                self.real_time_revenue[window_key] += event['amount']
                self.real_time_orders[window_key] += 1
                self.real_time_users[window_key].add(event['user_id'])
            
            self.last_processed_time = max(self.last_processed_time, timestamp)
    
    def get_speed_view(self, after_timestamp: float) -> dict:
        """
        Return real-time view for data AFTER the given timestamp.
        This is the data that batch hasn't processed yet.
        """
        result = {'revenue': 0, 'orders': 0, 'unique_users': set()}
        
        with self._lock:
            for window_key, revenue in self.real_time_revenue.items():
                # Parse window key back to timestamp for comparison
                window_time = datetime.strptime(window_key, '%Y-%m-%d-%H:%M')
                if window_time.timestamp() > after_timestamp:
                    result['revenue'] += revenue
                    result['orders'] += self.real_time_orders.get(window_key, 0)
                    result['unique_users'].update(
                        self.real_time_users.get(window_key, set())
                    )
        
        result['unique_users'] = len(result['unique_users'])
        return result
    
    def clear_before(self, timestamp: float):
        """
        Clear speed layer data that batch has now covered.
        Called after each successful batch run.
        """
        with self._lock:
            keys_to_remove = []
            for window_key in self.real_time_revenue:
                window_time = datetime.strptime(window_key, '%Y-%m-%d-%H:%M')
                if window_time.timestamp() <= timestamp:
                    keys_to_remove.append(window_key)
            
            for key in keys_to_remove:
                del self.real_time_revenue[key]
                del self.real_time_orders[key]
                del self.real_time_users[key]


# ============================================================================
# BATCH LAYER (Complete, accurate processing)
# ============================================================================

class BatchLayer:
    """
    Processes ALL data periodically for accurate results.
    
    WHY THIS DESIGN:
    - Recomputes from raw data (immutable master dataset)
    - Handles late arrivals, duplicates, corrections
    - Complex transformations (joins, sessionization, ML)
    - Results are AUTHORITATIVE (replace speed layer)
    
    SCALABILITY:
    - MapReduce paradigm (embarrassingly parallel)
    - Partition by time for independent processing
    - Can run on Spark cluster with 1000s of nodes
    - Reprocessing: Just re-run with same immutable input
    """
    
    def __init__(self):
        self.batch_views: Dict[str, dict] = {}
        self.last_batch_timestamp: float = 0
        self.batch_run_count: int = 0
    
    def run_batch(self, all_messages: List[dict]) -> dict:
        """
        Run batch computation over ALL data.
        
        In production this would be a Spark job:
        - Read all data from data lake (S3/HDFS)
        - Deduplicate by event_id
        - Join with dimension tables
        - Compute accurate aggregations
        - Write to serving layer
        """
        self.batch_run_count += 1
        print(f"\n{'='*60}")
        print(f"  BATCH RUN #{self.batch_run_count} - Processing {len(all_messages)} events")
        print(f"{'='*60}")
        
        # Step 1: Deduplicate (by event_id)
        seen_ids = set()
        deduped_events = []
        for msg in all_messages:
            event = msg['value']
            event_id = event.get('event_id', '')
            if event_id not in seen_ids:
                seen_ids.add(event_id)
                deduped_events.append(event)
        
        print(f"  Deduplication: {len(all_messages)} → {len(deduped_events)} events")
        
        # Step 2: Compute aggregations (simulating Spark transformations)
        daily_revenue: Dict[str, float] = defaultdict(float)
        daily_orders: Dict[str, int] = defaultdict(int)
        daily_users: Dict[str, set] = defaultdict(set)
        category_revenue: Dict[str, float] = defaultdict(float)
        hourly_distribution: Dict[int, int] = defaultdict(int)
        
        for event in deduped_events:
            if event['type'] == 'purchase':
                day_key = datetime.fromtimestamp(
                    event['timestamp']
                ).strftime('%Y-%m-%d')
                hour = datetime.fromtimestamp(event['timestamp']).hour
                
                daily_revenue[day_key] += event['amount']
                daily_orders[day_key] += 1
                daily_users[day_key].add(event['user_id'])
                category_revenue[event.get('category', 'unknown')] += event['amount']
                hourly_distribution[hour] += 1
        
        # Step 3: Build batch views
        batch_result = {
            'total_revenue': sum(daily_revenue.values()),
            'total_orders': sum(daily_orders.values()),
            'total_unique_users': len(set().union(*daily_users.values())) if daily_users else 0,
            'daily_revenue': dict(daily_revenue),
            'daily_orders': dict(daily_orders),
            'category_revenue': dict(category_revenue),
            'hourly_distribution': dict(hourly_distribution),
            'avg_order_value': (
                sum(daily_revenue.values()) / max(sum(daily_orders.values()), 1)
            ),
            'batch_timestamp': time.time(),
            'events_processed': len(deduped_events)
        }
        
        self.batch_views = batch_result
        self.last_batch_timestamp = time.time()
        
        print(f"  Results: Revenue=${batch_result['total_revenue']:.2f}, "
              f"Orders={batch_result['total_orders']}, "
              f"Users={batch_result['total_unique_users']}")
        print(f"  Batch view updated at: {datetime.now().strftime('%H:%M:%S')}")
        
        return batch_result
    
    def get_batch_view(self) -> dict:
        return self.batch_views


# ============================================================================
# SERVING LAYER (Merge batch + speed views)
# ============================================================================

class ServingLayer:
    """
    Merges batch and speed layer results for queries.
    
    WHY THIS DESIGN:
    - Provides single query interface to consumers
    - Handles the merge logic transparently
    - Caches frequently accessed views
    - Routes queries to appropriate layer
    
    MERGE STRATEGY:
    result = batch_view(data up to T) + speed_view(data after T)
    where T = timestamp of last successful batch run
    
    SCALABILITY:
    - Read replicas for query load
    - Cache layer (Redis) for hot queries
    - CDN for static dashboards
    """
    
    def __init__(self, batch_layer: BatchLayer, speed_layer: SpeedLayer):
        self.batch_layer = batch_layer
        self.speed_layer = speed_layer
    
    def query(self, metric: str = 'all') -> dict:
        """
        Query the merged view.
        
        The key insight: 
        - Batch view is ACCURATE for data up to last_batch_timestamp
        - Speed view fills the GAP between last batch and now
        - Together they give accurate + fresh results
        """
        batch_view = self.batch_layer.get_batch_view()
        speed_view = self.speed_layer.get_speed_view(
            self.batch_layer.last_batch_timestamp
        )
        
        merged = {
            'total_revenue': (
                batch_view.get('total_revenue', 0) + speed_view['revenue']
            ),
            'total_orders': (
                batch_view.get('total_orders', 0) + speed_view['orders']
            ),
            'total_unique_users': (
                batch_view.get('total_unique_users', 0) + speed_view['unique_users']
            ),
            'batch_coverage_until': datetime.fromtimestamp(
                self.batch_layer.last_batch_timestamp
            ).strftime('%H:%M:%S') if self.batch_layer.last_batch_timestamp else 'N/A',
            'speed_layer_events': speed_view['orders'],
            'freshness_lag_seconds': (
                time.time() - self.speed_layer.last_processed_time
                if self.speed_layer.last_processed_time else 0
            ),
            'query_timestamp': datetime.now().strftime('%H:%M:%S'),
        }
        
        return merged


# ============================================================================
# DATA GENERATOR (Simulates real-world events)
# ============================================================================

class EventGenerator:
    """Generates realistic e-commerce events"""
    
    CATEGORIES = ['electronics', 'clothing', 'food', 'books', 'sports']
    
    def __init__(self):
        self.event_counter = 0
    
    def generate_event(self) -> dict:
        self.event_counter += 1
        user_id = f"user_{random.randint(1, 1000)}"
        
        return {
            'event_id': hashlib.md5(
                f"{self.event_counter}{time.time()}".encode()
            ).hexdigest()[:12],
            'type': 'purchase',
            'user_id': user_id,
            'amount': round(random.uniform(5.0, 500.0), 2),
            'category': random.choice(self.CATEGORIES),
            'timestamp': time.time(),
            'product_id': f"prod_{random.randint(1, 5000)}",
        }


# ============================================================================
# ORCHESTRATOR (Runs the Lambda Architecture)
# ============================================================================

def run_lambda_architecture():
    """
    Main execution - demonstrates Lambda Architecture in action.
    
    Timeline:
    1. Start producing events continuously
    2. Speed layer processes in real-time
    3. Batch layer runs every N seconds (simulating hourly batch)
    4. Serving layer merges both views
    5. Queries show merged, fresh, accurate results
    """
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           LAMBDA ARCHITECTURE - LIVE DEMONSTRATION              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  This demo simulates:                                           ║
║  • Continuous event production (e-commerce purchases)            ║
║  • Speed Layer: Real-time aggregation (instant)                  ║
║  • Batch Layer: Complete recomputation (every 10 seconds)        ║
║  • Serving Layer: Merged view for queries                        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize components
    kafka = SimulatedKafka(num_partitions=4)
    speed_layer = SpeedLayer()
    batch_layer = BatchLayer()
    serving_layer = ServingLayer(batch_layer, speed_layer)
    generator = EventGenerator()
    
    # Flags for coordination
    running = True
    
    # --- Producer Thread ---
    def producer():
        """Produces events at ~100 events/second"""
        while running:
            event = generator.generate_event()
            kafka.produce('purchases', event['user_id'], event)
            # Also send to speed layer immediately
            speed_layer.process_event(event)
            time.sleep(0.01)  # 100 events/sec
    
    # --- Batch Thread ---
    def batch_scheduler():
        """Runs batch every 10 seconds (simulating hourly in production)"""
        time.sleep(5)  # Initial delay
        while running:
            all_messages = kafka.get_all_messages()
            batch_layer.run_batch(all_messages)
            # Clear speed layer data that batch now covers
            speed_layer.clear_before(batch_layer.last_batch_timestamp)
            time.sleep(10)  # Run every 10 seconds
    
    # Start threads
    producer_thread = threading.Thread(target=producer, daemon=True)
    batch_thread = threading.Thread(target=batch_scheduler, daemon=True)
    
    producer_thread.start()
    batch_thread.start()
    
    # --- Query Loop (Main Thread) ---
    print("\nQuerying merged view every 3 seconds...\n")
    
    for i in range(10):  # Run for 30 seconds
        time.sleep(3)
        result = serving_layer.query()
        
        print(f"\n┌─── Query #{i+1} at {result['query_timestamp']} ───┐")
        print(f"│ Total Revenue:    ${result['total_revenue']:,.2f}")
        print(f"│ Total Orders:     {result['total_orders']:,}")
        print(f"│ Unique Users:     {result['total_unique_users']:,}")
        print(f"│ Batch Coverage:   until {result['batch_coverage_until']}")
        print(f"│ Speed Layer Adds: {result['speed_layer_events']} orders")
        print(f"│ Freshness Lag:    {result['freshness_lag_seconds']:.3f}s")
        print(f"└{'─' * 40}┘")
    
    running = False
    time.sleep(1)
    
    # Final Summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Total events generated: {generator.event_counter}")
    print(f"Batch runs completed: {batch_layer.batch_run_count}")
    final = serving_layer.query()
    print(f"Final revenue: ${final['total_revenue']:,.2f}")
    print(f"Final orders: {final['total_orders']:,}")


if __name__ == '__main__':
    run_lambda_architecture()
```

---

## Production Considerations

### 1. Exactly-Once in Batch + Speed
```
BATCH LAYER:
- Reads from immutable source (S3/HDFS)
- Deduplicates by event_id
- Idempotent writes (overwrite partitions)
- Result: Exactly-once guaranteed

SPEED LAYER:
- Kafka consumer with enable.auto.commit=false
- Manual offset commit after processing
- Flink checkpointing for exactly-once
- Result: At-least-once (acceptable for speed layer)

MERGE:
- Batch results are authoritative
- Speed layer only serves gap between last batch and now
- Any duplicates in speed layer get corrected on next batch
```

### 2. Late-Arriving Data
```
Problem: Event occurred at T=100, arrives at T=200
         Batch at T=150 missed it

Solution:
1. Batch reprocesses overlapping windows
   - Current batch covers [T-48h, T] not just [last_batch, T]
   - Late data within 48h gets picked up

2. Speed layer watermark
   - Allow 5-minute late window
   - Events arriving > 5min late → dead letter queue
   - Next batch will pick them up

3. Reconciliation job
   - Runs daily, compares batch vs speed
   - Flags discrepancies for investigation
```

### 3. Schema Evolution
```
Strategy: Schema Registry (Confluent/AWS Glue)

1. Add field → OK (backward compatible)
2. Remove field → Deprecate first, remove after 2 batch cycles
3. Rename field → Add new + deprecate old
4. Type change → NEVER (create new field)

Both layers must handle schema versions:
- Batch: Read all versions, transform to latest
- Speed: Deserialize with schema registry, handle missing fields
```

---

## Real-World Production Examples

### LinkedIn (Original Lambda)
- **Scale**: 7 trillion messages/day through Kafka
- **Batch**: Hadoop jobs compute people-you-may-know, feed ranking
- **Speed**: Samza processes real-time signals (views, likes)
- **Serving**: Voldemort (K/V store) serves merged results
- **Lesson**: Eventually migrated towards Kappa for simpler pipelines

### Netflix
- **Scale**: 500 billion events/day
- **Batch**: Spark jobs for recommendation model training
- **Speed**: Flink for real-time viewing signals
- **Serving**: Cassandra + EVCache for serving
- **Lesson**: Lambda works when batch = ML training, speed = feature updates

### Twitter
- **Scale**: 500 million tweets/day, 400K tweets/sec peaks
- **Batch**: Scalding (Scala on Hadoop) for engagement analytics
- **Speed**: Heron (successor to Storm) for trending topics
- **Serving**: Manhattan (distributed DB) serves results
- **Lesson**: Speed layer must handle spikes (breaking news = 10x traffic)

---

## Comparison: Lambda vs Alternatives

| Aspect | Lambda | Kappa | Delta Lakehouse |
|--------|--------|-------|-----------------|
| Accuracy | Highest | High | High |
| Latency | Mixed | Low | Medium |
| Complexity | Very High | Medium | Medium |
| Code Duplication | Yes (2 paths) | No | No |
| Reprocessing | Natural (batch) | Expensive | Medium |
| Storage Cost | High (2x) | Medium | Low |
| Team Size Needed | Large | Medium | Small |
| Best For | Critical accuracy + speed | Pure streaming | Unified analytics |

