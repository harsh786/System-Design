# Real-World Data Engineering Problems (51-75)
# Complete Architecture + Diagrams + Scalability + Runnable Code

---

## Problem 51: Real-Time Customer 360 Platform

### Business Context
Enterprise needs unified customer view combining data from 20+ systems 
(CRM, support tickets, transactions, web behavior, mobile app, email, social).

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              CUSTOMER 360 PLATFORM                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA SOURCES (20+ Systems)                                                  │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                │
│  │CRM │ │ERP │ │Web │ │App │ │Email│ │Chat│ │Social│ │POS │               │
│  └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └──┬──┘ └─┬──┘              │
│    │       │      │      │      │      │       │       │                    │
│  ┌─▼───────▼──────▼──────▼──────▼──────▼───────▼───────▼────────┐         │
│  │  IDENTITY RESOLUTION ENGINE                                    │         │
│  │                                                                │         │
│  │  CHALLENGE: Same person = different IDs in each system         │         │
│  │  • CRM: customer_123                                           │         │
│  │  • Web: cookie_abc                                             │         │
│  │  • App: device_xyz                                             │         │
│  │  • Email: john@email.com                                       │         │
│  │                                                                │         │
│  │  SOLUTION: Probabilistic + Deterministic matching              │         │
│  │  Deterministic: Same email/phone → same person (100%)          │         │
│  │  Probabilistic: Same name + address + behavior (90%+ conf)     │         │
│  │                                                                │         │
│  │  Output: Unified customer_id (golden record)                   │         │
│  │  Tech: Spark + Graph algorithms (connected components)         │         │
│  └──────────────────────────┬─────────────────────────────────────┘        │
│                              │                                               │
│  ┌───────────────────────────▼────────────────────────────────────┐         │
│  │  UNIFIED PROFILE STORE                                          │         │
│  │                                                                 │         │
│  │  Storage: Cassandra (wide rows per customer)                    │         │
│  │  + Redis (hot profiles, real-time attributes)                   │         │
│  │  + Elasticsearch (profile search)                               │         │
│  │                                                                 │         │
│  │  Profile Schema:                                                │         │
│  │  {                                                              │         │
│  │    "customer_id": "C360-uuid",                                  │         │
│  │    "identifiers": ["email:x", "phone:y", "cookie:z"],           │         │
│  │    "demographics": {"age": 35, "location": "NYC"},              │         │
│  │    "behavioral": {"ltv": 5000, "segment": "high_value"},        │         │
│  │    "real_time": {"last_page": "/cart", "session_active": true},  │        │
│  │    "preferences": {"channels": ["email", "sms"]},               │         │
│  │    "risk_score": 0.12,                                          │         │
│  │    "last_updated": "2024-01-15T10:30:00Z"                       │         │
│  │  }                                                              │         │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  REAL-TIME UPDATES:                                                          │
│  • Flink processes events from all sources                                   │
│  • Updates profile attributes within 5 seconds                               │
│  • Triggers: personalization, next-best-action, churn prediction             │
│                                                                              │
│  SCALABILITY:                                                                │
│  • 100M customer profiles                                                    │
│  • 1B events/day across all sources                                          │
│  • Profile lookup: <5ms (Redis) or <20ms (Cassandra)                         │
│  • Identity resolution batch: Runs hourly (Spark, 500 nodes)                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Each Technology?
```
WHY CASSANDRA for profile store?
→ Wide rows: All customer data in one partition (fast read)
→ Write-optimized: Handle 1B events/day without breaking
→ Horizontal scaling: Add nodes for more customers
→ Multi-DC: Replicate profiles globally for low latency

WHY REDIS for real-time layer?
→ Sub-ms reads for active session data
→ TTL for session expiry (auto-cleanup)
→ Pub/Sub for real-time profile change notifications
→ Trade-off: Memory-bound, only hot profiles

WHY SPARK for identity resolution?
→ Graph algorithms (connected components) at scale
→ Handles 100M+ nodes in identity graph
→ Batch is acceptable (hourly refresh)
→ Alternative: Real-time dedup with Flink (for new matches)
```

---

## Problem 52: ML Feature Store (Feast/Tecton Pattern)

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              ML FEATURE STORE ARCHITECTURE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FEATURE COMPUTATION                                                         │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  BATCH FEATURES (Spark, daily/hourly)                           │         │
│  │  • user_avg_spend_30d                                           │         │
│  │  • user_purchase_frequency                                      │         │
│  │  • product_popularity_score                                     │         │
│  │  • user_churn_probability                                       │         │
│  │                                                                 │         │
│  │  → Writes to: Offline Store (Delta Lake / BigQuery)              │         │
│  │  → Materializes to: Online Store (Redis / DynamoDB)              │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  STREAMING FEATURES (Flink, real-time)                          │         │
│  │  • user_clicks_last_5min                                        │         │
│  │  • cart_value_current_session                                   │         │
│  │  • items_viewed_this_session                                    │         │
│  │  • time_on_page_current                                         │         │
│  │                                                                 │         │
│  │  → Writes to: Online Store (Redis) directly                     │         │
│  │  → Also logs to: Offline Store (for training consistency)       │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  FEATURE REGISTRY (Metadata)                                                 │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  • Feature definitions (name, type, description)                │         │
│  │  • Data sources and transformations                             │         │
│  │  • Feature freshness SLAs                                       │         │
│  │  • Feature lineage                                              │         │
│  │  • Feature statistics (distribution, drift)                     │         │
│  │  • Access control (who can use which features)                  │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  SERVING                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                                                                 │         │
│  │  ONLINE SERVING (Real-time inference):                          │         │
│  │  ┌─────────────────────────────────────────────────┐           │         │
│  │  │  Model requests features by entity_id            │           │         │
│  │  │  Feature Store returns pre-computed values       │           │         │
│  │  │  Latency: <5ms (Redis lookup)                    │           │         │
│  │  │  Throughput: 100K requests/sec                   │           │         │
│  │  └─────────────────────────────────────────────────┘           │         │
│  │                                                                 │         │
│  │  OFFLINE SERVING (Training):                                    │         │
│  │  ┌─────────────────────────────────────────────────┐           │         │
│  │  │  Point-in-time correct feature retrieval         │           │         │
│  │  │  "What were this user's features on Jan 1?"      │           │         │
│  │  │  Prevents DATA LEAKAGE (future info in training) │           │         │
│  │  │  Reads from: Delta Lake with time-travel         │           │         │
│  │  └─────────────────────────────────────────────────┘           │         │
│  │                                                                 │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  CRITICAL CONCEPT: TRAINING-SERVING SKEW                                     │
│  ═══════════════════════════════════════                                      │
│  Problem: Features computed differently in training vs serving → bad model   │
│  Solution: Same feature definitions used for both (single source of truth)   │
│  Feature Store ensures: EXACT SAME computation, just different time ranges   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problem 53: Event-Time Processing with Watermarks

### Deep Dive: Why Watermarks Matter
```
THE PROBLEM:
════════════
Real-world events arrive OUT OF ORDER and LATE.

Timeline (wall clock):
  T=0: Event A (event_time=0:00) arrives
  T=1: Event C (event_time=0:02) arrives  ← Out of order!
  T=2: Event B (event_time=0:01) arrives  ← Late!
  T=5: Event D (event_time=0:00) arrives  ← VERY late (5 sec delay)

If we compute "count per minute window [0:00-0:01)":
  → When do we close this window and emit result?
  → If we close too early: miss late events (incorrect count)
  → If we close too late: high latency (waiting forever)

WATERMARK = "I believe no more events with event_time < W will arrive"

┌─────────────────────────────────────────────────────────────────┐
│  EVENT STREAM WITH WATERMARKS                                    │
│                                                                  │
│  Events:     A(0:00)  C(0:02)  B(0:01)  E(0:03)  D(0:00)       │
│  Wall clock: ─────────────────────────────────────────────────►  │
│              T=0      T=1      T=2      T=3      T=5            │
│                                                                  │
│  Watermark:  W=-10s   W=0:01   W=0:00   W=0:02   W=0:02        │
│  (max_event_time - allowed_lateness)                             │
│                                                                  │
│  Window [0:00-0:01):                                             │
│    Fires when watermark passes 0:01                              │
│    Events included: A(0:00), B(0:01) ← B arrived late but OK!   │
│    Event D(0:00) at T=5: DROPPED (arrived after watermark passed)│
│                                                                  │
│  TRADE-OFF:                                                      │
│    Large allowed_lateness → more correct, higher latency         │
│    Small allowed_lateness → faster results, may miss events      │
│                                                                  │
│  TYPICAL SETTING:                                                │
│    allowed_lateness = 5 minutes (covers 99.9% of late events)    │
│    Side output for events beyond watermark (to DLQ/late table)   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Runnable Code
```python
"""
Event-Time Processing with Watermarks
=======================================
Demonstrates:
- Out-of-order event handling
- Watermark computation
- Window firing
- Late data handling (side output)

Run: python watermark_processing.py
"""

import time
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


@dataclass
class Event:
    event_id: str
    event_time: float  # When the event actually occurred
    arrival_time: float  # When it arrived at the system (wall clock)
    value: float
    key: str


@dataclass
class WindowResult:
    window_start: float
    window_end: float
    key: str
    count: int
    sum_value: float
    events: List[str]


class WatermarkTracker:
    """
    Tracks watermarks based on observed event times.
    
    Watermark = max_observed_event_time - allowed_lateness
    
    Meaning: "We believe all events with event_time < watermark 
    have been observed (with high probability)"
    """
    
    def __init__(self, allowed_lateness_sec: float = 5.0):
        self.allowed_lateness = allowed_lateness_sec
        self.max_event_time = 0.0
        self.current_watermark = 0.0
    
    def update(self, event_time: float) -> float:
        """Update watermark based on new event time"""
        if event_time > self.max_event_time:
            self.max_event_time = event_time
            self.current_watermark = self.max_event_time - self.allowed_lateness
        return self.current_watermark
    
    def get_watermark(self) -> float:
        return self.current_watermark


class TumblingWindow:
    """
    Fixed-size, non-overlapping time windows.
    
    Example: 10-second windows
    [0-10), [10-20), [20-30), ...
    
    Window fires (emits result) when watermark passes window_end.
    """
    
    def __init__(self, window_size_sec: float = 10.0):
        self.window_size = window_size_sec
        # Buffered events per window per key
        self.windows: Dict[Tuple[str, float], List[Event]] = defaultdict(list)
        self.fired_windows: set = set()
    
    def get_window_start(self, event_time: float) -> float:
        """Determine which window an event belongs to"""
        return (event_time // self.window_size) * self.window_size
    
    def add_event(self, event: Event, watermark: float) -> Tuple[Optional[WindowResult], bool]:
        """
        Add event to appropriate window.
        Returns: (fired_result_if_any, is_late)
        """
        window_start = self.get_window_start(event.event_time)
        window_end = window_start + self.window_size
        window_key = (event.key, window_start)
        
        # Check if this event is too late (window already fired)
        if window_key in self.fired_windows:
            return None, True  # LATE EVENT - goes to side output
        
        # Add to window buffer
        self.windows[window_key].append(event)
        
        # Check if any windows should fire
        fired_result = self._try_fire(watermark)
        
        return fired_result, False
    
    def _try_fire(self, watermark: float) -> Optional[WindowResult]:
        """Fire windows whose end time is <= watermark"""
        for (key, window_start), events in list(self.windows.items()):
            window_end = window_start + self.window_size
            window_key = (key, window_start)
            
            if window_end <= watermark and window_key not in self.fired_windows:
                # Fire this window!
                result = WindowResult(
                    window_start=window_start,
                    window_end=window_end,
                    key=key,
                    count=len(events),
                    sum_value=sum(e.value for e in events),
                    events=[e.event_id for e in events]
                )
                self.fired_windows.add(window_key)
                del self.windows[window_key]
                return result
        
        return None
    
    def flush_all(self, watermark: float) -> List[WindowResult]:
        """Force-fire all remaining windows"""
        results = []
        for (key, window_start), events in list(self.windows.items()):
            window_end = window_start + self.window_size
            results.append(WindowResult(
                window_start=window_start,
                window_end=window_end,
                key=key,
                count=len(events),
                sum_value=sum(e.value for e in events),
                events=[e.event_id for e in events]
            ))
        self.windows.clear()
        return results


class StreamProcessor:
    """
    Complete stream processor with watermarks and windowing.
    Simulates Flink's event-time processing.
    """
    
    def __init__(self, window_size: float = 10.0, 
                 allowed_lateness: float = 5.0):
        self.watermark_tracker = WatermarkTracker(allowed_lateness)
        self.window = TumblingWindow(window_size)
        self.results: List[WindowResult] = []
        self.late_events: List[Event] = []
        self.processed_count = 0
    
    def process_event(self, event: Event) -> Optional[WindowResult]:
        """Process a single event through the pipeline"""
        self.processed_count += 1
        
        # Update watermark
        watermark = self.watermark_tracker.update(event.event_time)
        
        # Add to window
        result, is_late = self.window.add_event(event, watermark)
        
        if is_late:
            self.late_events.append(event)
        
        if result:
            self.results.append(result)
        
        return result
    
    def finish(self) -> List[WindowResult]:
        """Flush remaining windows at end of stream"""
        remaining = self.window.flush_all(float('inf'))
        self.results.extend(remaining)
        return remaining


def generate_out_of_order_events(count: int = 100) -> List[Event]:
    """
    Generate events that arrive out of order (realistic simulation).
    
    Some events arrive immediately, some are delayed by seconds.
    A few are very late (network issues, mobile app going offline).
    """
    events = []
    base_time = 1000.0  # Starting event time
    
    for i in range(count):
        event_time = base_time + i * 0.5  # Events every 0.5 seconds
        
        # Simulate network delay (arrival delay)
        delay = random.choices(
            [0.1, 0.5, 2.0, 5.0, 15.0],  # Possible delays
            [0.6, 0.2, 0.1, 0.07, 0.03],  # Probabilities
            k=1
        )[0]
        
        arrival_time = event_time + delay
        
        events.append(Event(
            event_id=f"evt_{i:04d}",
            event_time=event_time,
            arrival_time=arrival_time,
            value=random.uniform(1.0, 100.0),
            key=random.choice(['user_A', 'user_B', 'user_C'])
        ))
    
    # Sort by ARRIVAL time (this is how events reach the processor)
    events.sort(key=lambda e: e.arrival_time)
    return events


def run_watermark_demo():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       EVENT-TIME PROCESSING WITH WATERMARKS                     ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  • 100 events generated with realistic delays                    ║
║  • Some arrive out of order, some are very late                  ║
║  • 10-second tumbling windows                                    ║
║  • 5-second allowed lateness (watermark)                         ║
║  • Late events sent to side output (DLQ)                         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Generate events
    events = generate_out_of_order_events(100)
    
    # Process
    processor = StreamProcessor(window_size=10.0, allowed_lateness=5.0)
    
    print("Processing events...")
    print(f"{'Event':<10} {'EventTime':<12} {'Arrival':<12} {'Watermark':<12} {'Action':<20}")
    print("-" * 70)
    
    for i, event in enumerate(events):
        result = processor.process_event(event)
        
        wm = processor.watermark_tracker.get_watermark()
        
        # Print some events for visibility
        if i < 20 or result or event in processor.late_events[-1:]:
            action = ""
            if result:
                action = f"WINDOW FIRED [{result.window_start:.0f}-{result.window_end:.0f})"
            elif event in processor.late_events:
                action = "LATE → side output"
            else:
                action = "buffered"
            
            print(f"{event.event_id:<10} {event.event_time:<12.1f} "
                  f"{event.arrival_time:<12.1f} {wm:<12.1f} {action:<20}")
    
    # Flush remaining
    remaining = processor.finish()
    
    # Summary
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"\n  Events processed: {processor.processed_count}")
    print(f"  Windows fired: {len(processor.results)}")
    print(f"  Late events (dropped): {len(processor.late_events)}")
    print(f"  Late event rate: {len(processor.late_events)/processor.processed_count*100:.1f}%")
    
    print(f"\n  Window Results:")
    for result in sorted(processor.results, key=lambda r: (r.key, r.window_start)):
        print(f"    [{result.window_start:.0f}-{result.window_end:.0f}) "
              f"key={result.key}: count={result.count}, sum={result.sum_value:.1f}")
    
    if processor.late_events:
        print(f"\n  Late Events (would go to DLQ/late-data table):")
        for event in processor.late_events[:5]:
            print(f"    {event.event_id}: event_time={event.event_time:.1f}, "
                  f"arrived={event.arrival_time:.1f}, "
                  f"delay={event.arrival_time - event.event_time:.1f}s")


if __name__ == '__main__':
    run_watermark_demo()
```

---

## Problem 54: Data Pipeline Backpressure Handling

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         BACKPRESSURE HANDLING PATTERNS                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WHAT IS BACKPRESSURE?                                                       │
│  Producer is faster than consumer → buffers fill → system crashes            │
│                                                                              │
│  Example: Kafka produces 100K/sec, Flink processes 80K/sec                   │
│  Without backpressure: OOM in Flink → crash → data loss                      │
│  With backpressure: Flink signals "slow down" → system stable                │
│                                                                              │
│  STRATEGIES:                                                                 │
│                                                                              │
│  1. RATE LIMITING (at source)                                                │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Producer → Rate Limiter (token bucket) → Kafka      │                    │
│  │  If tokens exhausted → block/drop/queue               │                   │
│  │  Simple but loses data or adds latency                │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                              │
│  2. BUFFERING (absorb bursts)                                                │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Kafka itself IS the buffer!                          │                    │
│  │  Fast producer → Kafka (days of retention) → slow consumer                │
│  │  Consumer processes at its own pace                    │                   │
│  │  Works if: consumer catches up during off-peak         │                   │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                              │
│  3. DYNAMIC SCALING (match capacity to load)                                 │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Monitor consumer lag → if lag > threshold → scale up │                   │
│  │  Kubernetes HPA on consumer pod count                 │                    │
│  │  + Kafka partition increase for parallelism           │                    │
│  │  Delay: 2-5 minutes to spin up new pods               │                   │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                              │
│  4. FLINK INTERNAL BACKPRESSURE                                              │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Flink propagates backpressure through the DAG:       │                    │
│  │                                                       │                    │
│  │  Source → Map → Window → Sink                         │                    │
│  │                     ↑ SLOW (complex aggregation)       │                   │
│  │                                                       │                    │
│  │  Window full → Map blocked → Source pauses reading    │                    │
│  │  Result: Kafka consumer lag grows (acceptable!)        │                   │
│  │  System stays stable, no OOM                          │                    │
│  │                                                       │                    │
│  │  HOW IT WORKS:                                        │                    │
│  │  • Credit-based flow control between operators        │                    │
│  │  • Downstream grants credits to upstream              │                    │
│  │  • No credits = upstream blocks                       │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                              │
│  5. LOAD SHEDDING (last resort)                                              │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  When all else fails: intentionally drop low-priority │                    │
│  │  Priority levels:                                     │                    │
│  │  P1: Financial transactions → NEVER drop              │                    │
│  │  P2: User events → buffer, retry                      │                    │
│  │  P3: Telemetry → drop oldest, sample                  │                    │
│  │                                                       │                    │
│  │  Implementation: Priority queue + TTL                  │                   │
│  │  Dropped events → DLQ for later processing            │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problems 55-75: Architecture Summaries

### Problem 55: Change Data Capture for Microservices
```
PATTERN: Outbox Pattern + Debezium
Each service writes events to outbox table → CDC captures → Kafka distributes
WHY: Ensures DB write + event publish are atomic (same transaction)
SCALE: 500 microservices, each publishing domain events
```

### Problem 56: Real-Time Alerting System
```
ARCH: Metrics → Kafka → Flink (CEP rules) → Alert Router → PagerDuty/Slack
CEP: Complex Event Processing (detect patterns across events)
EXAMPLES: "3 failures in 5 minutes from same service" → P1 alert
DEDUP: Suppress duplicate alerts (5-minute silence after first alert)
```

### Problem 57: Data Lake Governance (Unity Catalog Pattern)
```
ARCH: Central Catalog + RBAC + Column-level security + Audit logs
FEATURES: Table discovery, lineage visualization, PII tagging
ACCESS: Role-based (analyst → read gold, engineer → write silver)
AUDIT: Every query logged (who accessed what, when)
```

### Problem 58: Streaming ETL with Schema Registry
```
ARCH: Producer → Schema Registry → Kafka → Consumer (validates schema)
FORMAT: Avro (schema embedded) or Protobuf (external definition)
EVOLUTION: Backward compatible changes only (add field OK, remove NO)
VALIDATION: Kafka rejects messages that don't match registered schema
```

### Problem 59: Real-Time Dashboard Backend
```
ARCH: Events → Kafka → Flink (pre-aggregate) → Druid/Pinot → Dashboard
WHY PRE-AGGREGATE: 100K events/sec can't be queried raw in real-time
REFRESH: Dashboard polls every 5 seconds, gets pre-computed metrics
CACHE: Redis between Druid and dashboard for sub-10ms response
```

### Problem 60: Data Warehouse Cost Management
```
METRICS: Cost per query, cost per pipeline, cost per GB stored
STRATEGIES:
  • Auto-suspend idle warehouses (Snowflake)
  • Materialized views (pre-compute expensive joins)
  • Query result caching (same query = cached result)
  • Storage tiering (hot → archive)
SAVINGS: Typical 40-60% reduction with proper optimization
```

### Problem 61: Streaming Deduplication with Bloom Filters
```
CHALLENGE: Deduplicate 1 billion events/day (remembering all IDs = expensive)
BLOOM FILTER: Probabilistic. "Definitely not seen" or "probably seen"
FALSE POSITIVE RATE: 0.1% (1 in 1000 duplicates pass through)
MEMORY: 1 billion items at 0.1% FPR = ~1.2 GB (vs 30GB+ for hash set)
ROTATION: Time-windowed bloom filters (1 per hour, discard after 24h)
```

### Problem 62: Incremental Materialized Views
```
PATTERN: Instead of recomputing entire view, apply DELTA
EXAMPLE: SUM(revenue) → new row arrives → just add to existing sum
WHY: Full recomputation of 1TB table takes hours; increment takes seconds
FLINK SQL: Continuous queries ARE incremental materialized views
LIMITATION: Not all aggregations are incrementally computable (e.g., MEDIAN)
```

### Problem 63: Data Pipeline Testing Framework
```
LAYERS:
  • Unit tests: Single transformation logic (pytest)
  • Integration tests: End-to-end with test data (testcontainers)
  • Data quality tests: Great Expectations / dbt tests
  • Performance tests: Benchmark with production-scale data
  • Contract tests: Schema compatibility between producer/consumer
TOOLS: pytest + testcontainers + Great Expectations + dbt test
```

### Problem 64: Real-Time ETL for Compliance (GDPR/CCPA)
```
REQUIREMENTS: Delete user data within 30 days of request
CHALLENGE: Data spread across 50+ tables, 3 storage systems
ARCH: Deletion request → Kafka → Flink (find all user data) → Execute deletes
PATTERN: Crypto-shredding (encrypt per-user key, delete key = data gone)
ADVANTAGE: Don't need to find every copy; just destroy the encryption key
```

### Problem 65: Hybrid Transactional/Analytical Processing (HTAP)
```
ARCH: TiDB / CockroachDB / AlloyDB (single system, both OLTP + OLAP)
WHY: No ETL delay between operational and analytical
HOW: Row store (OLTP) + Column store (OLAP) with real-time replication
TRADE-OFF: Jack of all trades; dedicated systems still win for extreme scale
USE CASE: SMB/mid-market where operational simplicity > absolute performance
```

### Problem 66: Streaming Aggregation with Retraction
```
PROBLEM: User updates profile → aggregation count changes
APPROACH: Retraction stream (emit -1 for old value, +1 for new value)
EXAMPLE: User moves from "NY" to "CA"
  → Emit: (NY, -1), (CA, +1) → count_by_state stays correct
IMPLEMENTATION: Flink handles retractions natively in SQL mode
```

### Problem 67: Data Observability Platform
```
PILLARS: Freshness, Volume, Schema, Distribution, Lineage
DETECTION: Anomaly detection on each pillar (ML-based)
ARCH: Monitors → Time-series DB → Anomaly models → Alerts
TOOLS: Monte Carlo, Datadog, elementary (open-source)
RESULT: Detect data issues before business users notice
```

### Problem 68: Partition Management at Scale
```
PROBLEM: 10,000 Hive partitions → listing takes minutes
SOLUTION: 
  • Iceberg manifest files (no directory listing needed)
  • Partition pruning via metadata (min/max statistics)
  • Dynamic partitioning (auto-create partitions)
  • Partition compaction (merge small partitions)
BEST PRACTICE: Partition by day (not hour) unless hourly queries are common
```

### Problem 69: Stream-Table Duality
```
CONCEPT: A stream and a table are two views of the same data
TABLE → STREAM: CDC captures changes as a stream
STREAM → TABLE: Aggregate stream into latest state (materialized view)
KAFKA LOG COMPACTION: Turns topic into a table (keeps latest value per key)
APPLICATION: Kafka Streams KTable, Flink dynamic tables
```

### Problem 70: Data Pipeline Idempotency Framework
```
PATTERN: Same input processed multiple times → same output
IMPLEMENTATION:
  1. Dedup by event_id at ingestion (Bloom filter + DB check)
  2. Overwrite partitions (not append) for batch
  3. Upsert by natural key for incremental
  4. Idempotent aggregations (SUM is NOT idempotent, MAX is)
WHY CRITICAL: Retries are inevitable (network, crashes, restarts)
```

### Problem 71: Multi-Hop Streaming Pipeline
```
ARCH: Source → Bronze stream → Silver stream → Gold stream → Serving
EACH HOP: Kafka topic → Flink job → next Kafka topic
ADVANTAGE: Each stage independently scalable, restartable
DISADVANTAGE: More Kafka topics, more operational overhead
TOTAL LATENCY: Sum of all hops (typically 5-30 seconds end-to-end)
```

### Problem 72: Data Mesh Self-Serve Platform
```
COMPONENTS:
  • Infrastructure templates (Terraform modules for pipelines)
  • Data product builder (UI for domain teams)
  • Quality automation (auto-apply standard checks)
  • Discovery (catalog with search)
  • Access management (request + approve flow)
GOAL: Domain team deploys new data product in <1 day (not months)
```

### Problem 73: Streaming Machine Learning Pipeline
```
ARCH: Events → Feature computation (Flink) → Online inference → Decision
ONLINE LEARNING: Model updates with each new data point
A/B TESTING: Route traffic to model versions, measure conversion
MONITORING: Feature drift detection, prediction quality degradation
RETRAINING TRIGGER: Automated when quality drops below threshold
```

### Problem 74: Cross-Region Event Streaming
```
ARCH: Local Kafka → MirrorMaker 2 → Remote Kafka (active-active)
CHALLENGE: Exactly-once across regions (CAP theorem: pick 2 of 3)
SOLUTION: Eventual consistency + conflict resolution (LWW / vector clocks)
LATENCY: 50-200ms inter-region (acceptable for async replication)
USE CASE: Multi-region active-active for disaster recovery
```

### Problem 75: Cost-Effective Historical Data Archival
```
TIERING:
  Hot (0-7 days): SSD storage, instant queries ($0.10/GB)
  Warm (7-90 days): HDD/S3 Standard, seconds to query ($0.023/GB)
  Cold (90d-1yr): S3 IA, minutes to access ($0.0125/GB)
  Archive (1yr+): Glacier Deep Archive, hours to restore ($0.00099/GB)

AUTOMATION:
  • S3 Lifecycle policies move data automatically
  • Delta Lake OPTIMIZE compacts before archival
  • Metadata stays in catalog (queryable even if archived)
  • Restore-on-demand for investigations
```

