# Pattern 10: Backpressure Patterns

## The Problem

```
WHAT IS BACKPRESSURE?
═════════════════════
When a downstream system (consumer/sink) is SLOWER than the upstream system 
(producer/source), data accumulates. Without backpressure handling:

  Producer: 100,000 events/sec
  Consumer: 50,000 events/sec
  
  After 1 minute: 3,000,000 events buffered (nowhere to go)
  After 10 minutes: 30,000,000 events → OOM crash or data loss

REAL-WORLD EXAMPLES:
  • Kafka consumer lag growing unboundedly → stale data
  • Flink operator overwhelmed → checkpoint timeouts → job crashes
  • API rate limit hit → requests rejected → data loss
  • Database write throughput saturated → connection pool exhausted
  • S3 multipart upload slow → memory buffers overflow

BACKPRESSURE = Mechanism to SLOW DOWN producers when consumers can't keep up.
```

## Backpressure Strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKPRESSURE STRATEGIES                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STRATEGY 1: BLOCKING (Synchronous Backpressure)                             │
│  ───────────────────────────────────────────────                             │
│  Producer WAITS until consumer is ready.                                     │
│                                                                              │
│  [Producer] ──block──▶ [Buffer FULL] ──wait──▶ [Consumer drains] ──resume──▶│
│                                                                              │
│  Implementation: Bounded queue + blocking put()                              │
│  Example: Java BlockingQueue, Flink network buffers                          │
│  Pro: Simple, no data loss                                                   │
│  Con: Cascading slowdown (entire pipeline slows to slowest operator)         │
│                                                                              │
│  STRATEGY 2: DROPPING (Load Shedding)                                        │
│  ────────────────────────────────────                                        │
│  When buffer is full, DROP oldest or lowest-priority messages.               │
│                                                                              │
│  [Producer] ──write──▶ [Buffer FULL] ──DROP──▶ [newest/oldest discarded]    │
│                                                                              │
│  Implementation: Ring buffer (overwrites oldest)                             │
│  Example: Metrics collection, logging, monitoring data                       │
│  Pro: Producer never blocks, bounded memory                                  │
│  Con: DATA LOSS (acceptable only for non-critical data)                      │
│                                                                              │
│  STRATEGY 3: BUFFERING (Elastic Buffer)                                      │
│  ────────────────────────────────────────                                    │
│  Absorb bursts in a scalable buffer (Kafka, SQS).                           │
│                                                                              │
│  [Producer] ──fast──▶ [Kafka/SQS] ──slow──▶ [Consumer at own pace]         │
│                                                                              │
│  Implementation: Kafka topic as buffer (days of retention)                   │
│  Example: Event-driven architectures, log ingestion                          │
│  Pro: Decouples producer/consumer speeds, handles bursts                     │
│  Con: Eventual consistency, buffer capacity has limits                        │
│                                                                              │
│  STRATEGY 4: RATE LIMITING (Throttling)                                      │
│  ──────────────────────────────────────                                      │
│  Explicitly limit producer throughput.                                        │
│                                                                              │
│  [Producer] ──token_bucket──▶ [Controlled rate] ──▶ [Consumer can keep up]  │
│                                                                              │
│  Implementation: Token bucket, leaky bucket, sliding window                  │
│  Example: API calls, database writes, S3 uploads                             │
│  Pro: Predictable load, protects downstream                                  │
│  Con: Wastes producer capacity during quiet periods                           │
│                                                                              │
│  STRATEGY 5: ADAPTIVE (Dynamic Scaling)                                      │
│  ──────────────────────────────────────                                      │
│  Monitor pressure → auto-scale consumers OR adjust producer rate.            │
│                                                                              │
│  [Monitor lag] → [Lag > threshold] → [Scale consumers UP]                   │
│  [Monitor lag] → [Lag < threshold] → [Scale consumers DOWN]                 │
│                                                                              │
│  Implementation: Kafka consumer group auto-scaling, KEDA                     │
│  Example: Kubernetes + KEDA + Kafka consumer lag metric                      │
│  Pro: Optimal resource usage, handles variable load                          │
│  Con: Scaling latency (minutes), cost                                        │
│                                                                              │
│  STRATEGY 6: SPILLOVER (Overflow to Cheaper Storage)                         │
│  ─────────────────────────────────────────────────                           │
│  When fast path is full, spill to slow-but-cheap path.                      │
│                                                                              │
│  [Producer] ──▶ [Hot Path: Redis/Memory] ─── full ──▶ [Cold Path: S3/Disk] │
│              ──▶ [Hot Path: Redis/Memory] ◀── drain ──  [Cold replay later] │
│                                                                              │
│  Implementation: Tiered storage, overflow queues                             │
│  Example: Real-time scoring with batch fallback                              │
│  Pro: No data loss, bounded hot-path cost                                    │
│  Con: Complexity, eventual consistency for spillover data                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Backpressure in Apache Flink

```
FLINK'S CREDIT-BASED FLOW CONTROL:
══════════════════════════════════

Every Flink operator has NETWORK BUFFERS (bounded memory pools).

  [Source] ──buffers──▶ [Map] ──buffers──▶ [Window] ──buffers──▶ [Sink]
                                                │
                                         SLOW (complex aggregation)
                                                │
                                    Buffers fill up ← backpressure propagates
                                                │
                     [Map] buffers full ← ← ← ←┘
                           │
           [Source] blocked ← ← ← 
           (stops reading from Kafka)
           
  RESULT: Kafka consumer lag increases (Kafka is the elastic buffer)
          Pipeline runs at speed of SLOWEST operator
          No data loss, no OOM

MONITORING:
  - Backpressure indicator in Flink Web UI (0.0 to 1.0)
  - > 0.5 = significant backpressure (operator is bottleneck)
  - Identify bottleneck: operator with HIGH backpressure + HIGH busy time

FIXING FLINK BACKPRESSURE:
  1. Scale up parallelism of slow operator
  2. Optimize slow operator (reduce computation)
  3. Add async I/O for external calls (don't block operator thread)
  4. Increase network buffer memory (handle bursts, not sustained overload)
  5. Use side outputs for slow paths (don't block main pipeline)
```

## Backpressure in Kafka

```
KAFKA CONSUMER LAG AS BACKPRESSURE SIGNAL:
═════════════════════════════════════════

Kafka doesn't have ACTIVE backpressure (producers are never blocked).
Instead: topic retention = elastic buffer, consumer lag = pressure metric.

  Producer rate: 100,000 msg/sec
  Consumer rate: 80,000 msg/sec
  
  Lag growth: 20,000 msg/sec × 60 sec = 1.2M messages per minute
  Retention: 7 days = buffer of 7 × 86400 × 20,000 = 12 BILLION messages
  
  WHEN TO WORRY:
  - Lag > 1 hour: Dashboard data is stale
  - Lag > retention: DATA LOSS (messages expire before consumption)
  - Lag growing: Consumer will never catch up without intervention

RESPONSE STRATEGIES:
  
  1. Auto-scale consumers (KEDA on Kubernetes):
     IF consumer_lag > 1M messages for 5 min:
       Scale consumer group from 3 → 6 pods
       (Requires partition count ≥ 6, otherwise can't parallelize)
       
  2. Increase partitions (one-time, can't decrease):
     kafka-topics --alter --partitions 12 --topic orders
     → More partitions = more consumer parallelism
     → WARNING: Repartitioning loses ordering guarantees
     
  3. Reduce processing time per message:
     - Batch writes to DB (100 rows/commit instead of 1)
     - Cache lookups instead of DB queries per message
     - Async I/O for external calls
     - Simpler transformations (push complex logic to later stage)
     
  4. Backpressure to producer (extreme):
     Quota mechanism: Set produce byte-rate limit per client
     kafka-configs --alter --entity-type clients --entity-name producer-1 \
       --add-config 'producer_byte_rate=10485760'  # 10 MB/s limit
```

## Runnable Implementation

```python
"""
Backpressure Patterns - Simulation
==================================
Demonstrates:
- Blocking backpressure (bounded queue)
- Drop-based backpressure (ring buffer)
- Rate limiting (token bucket)
- Adaptive scaling
- Monitoring and alerting
"""

import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional, List, Callable
import random


# ============================================================================
# STRATEGY 1: BLOCKING BACKPRESSURE (Bounded Queue)
# ============================================================================

class BoundedQueue:
    """Thread-safe bounded queue that blocks producers when full."""
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.queue = deque()
        self.lock = threading.Lock()
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
        self.stats = {"produced": 0, "consumed": 0, "blocked_time_ms": 0}
    
    def put(self, item, timeout: float = 1.0) -> bool:
        """Blocking put. Returns False if timed out."""
        start = time.time()
        with self.not_full:
            while len(self.queue) >= self.capacity:
                if not self.not_full.wait(timeout):
                    self.stats["blocked_time_ms"] += int((time.time() - start) * 1000)
                    return False  # Timed out
            self.queue.append(item)
            self.stats["produced"] += 1
            self.stats["blocked_time_ms"] += int((time.time() - start) * 1000)
            self.not_empty.notify()
            return True
    
    def get(self, timeout: float = 1.0) -> Optional[any]:
        """Blocking get. Returns None if timed out."""
        with self.not_empty:
            while len(self.queue) == 0:
                if not self.not_empty.wait(timeout):
                    return None
            item = self.queue.popleft()
            self.stats["consumed"] += 1
            self.not_full.notify()
            return item
    
    @property
    def fill_ratio(self) -> float:
        return len(self.queue) / self.capacity


# ============================================================================
# STRATEGY 2: DROP-BASED BACKPRESSURE (Ring Buffer)
# ============================================================================

class RingBuffer:
    """Fixed-size ring buffer that overwrites oldest when full."""
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.write_pos = 0
        self.read_pos = 0
        self.count = 0
        self.stats = {"produced": 0, "consumed": 0, "dropped": 0}
    
    def put(self, item):
        """Always succeeds. Drops oldest if full."""
        if self.count == self.capacity:
            # Overwrite oldest (data loss!)
            self.read_pos = (self.read_pos + 1) % self.capacity
            self.count -= 1
            self.stats["dropped"] += 1
        
        self.buffer[self.write_pos] = item
        self.write_pos = (self.write_pos + 1) % self.capacity
        self.count += 1
        self.stats["produced"] += 1
    
    def get(self) -> Optional[any]:
        """Returns None if empty."""
        if self.count == 0:
            return None
        item = self.buffer[self.read_pos]
        self.read_pos = (self.read_pos + 1) % self.capacity
        self.count -= 1
        self.stats["consumed"] += 1
        return item
    
    @property
    def drop_rate(self) -> float:
        if self.stats["produced"] == 0:
            return 0.0
        return self.stats["dropped"] / self.stats["produced"]


# ============================================================================
# STRATEGY 3: TOKEN BUCKET RATE LIMITER
# ============================================================================

class TokenBucket:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(self, rate: float, burst: int):
        """
        rate: tokens added per second
        burst: maximum tokens (bucket size)
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst  # Start full
        self.last_refill = time.time()
        self.stats = {"allowed": 0, "throttled": 0}
    
    def _refill(self):
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.rate
        self.tokens = min(self.burst, self.tokens + new_tokens)
        self.last_refill = now
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns False if rate limited."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            self.stats["allowed"] += 1
            return True
        else:
            self.stats["throttled"] += 1
            return False
    
    @property
    def throttle_rate(self) -> float:
        total = self.stats["allowed"] + self.stats["throttled"]
        if total == 0:
            return 0.0
        return self.stats["throttled"] / total


# ============================================================================
# STRATEGY 4: ADAPTIVE BACKPRESSURE (Auto-Scaling Simulation)
# ============================================================================

class AdaptiveConsumer:
    """Simulates auto-scaling based on lag."""
    
    def __init__(self, base_rate: int, max_instances: int):
        self.base_rate = base_rate  # Per instance
        self.max_instances = max_instances
        self.current_instances = 1
        self.lag = 0
        self.stats = {"scale_ups": 0, "scale_downs": 0, "max_lag": 0}
        
        # Scaling thresholds
        self.scale_up_lag = 1000  # Scale up if lag exceeds this
        self.scale_down_lag = 100  # Scale down if lag below this
    
    @property
    def current_rate(self) -> int:
        return self.base_rate * self.current_instances
    
    def process_tick(self, incoming_count: int):
        """Simulate one time period."""
        # Add incoming to lag
        self.lag += incoming_count
        
        # Consume at current capacity
        consumed = min(self.lag, self.current_rate)
        self.lag -= consumed
        
        # Track max lag
        self.stats["max_lag"] = max(self.stats["max_lag"], self.lag)
        
        # Auto-scale decision
        if self.lag > self.scale_up_lag and self.current_instances < self.max_instances:
            self.current_instances += 1
            self.stats["scale_ups"] += 1
        elif self.lag < self.scale_down_lag and self.current_instances > 1:
            self.current_instances -= 1
            self.stats["scale_downs"] += 1
        
        return consumed


# ============================================================================
# DEMONSTRATION
# ============================================================================

def simulate_backpressure():
    """Compare all backpressure strategies under the same workload."""
    print("=" * 70)
    print("BACKPRESSURE PATTERNS - STRATEGY COMPARISON")
    print("=" * 70)
    
    # Workload: Producer at 1000/sec, Consumer at 600/sec (overloaded)
    DURATION_TICKS = 50
    PRODUCER_RATE = 1000  # events per tick
    CONSUMER_RATE = 600   # events per tick (slower!)
    
    print(f"\n  Scenario: Producer={PRODUCER_RATE}/tick, Consumer={CONSUMER_RATE}/tick")
    print(f"  Duration: {DURATION_TICKS} ticks")
    print(f"  Overload: {(PRODUCER_RATE - CONSUMER_RATE) * DURATION_TICKS:,} excess events")
    
    # ─── STRATEGY 1: BLOCKING ───
    print("\n╔══ STRATEGY 1: BLOCKING (Bounded Queue, capacity=5000) ══╗")
    
    queue = BoundedQueue(capacity=5000)
    produced_blocking = 0
    consumed_blocking = 0
    
    for tick in range(DURATION_TICKS):
        # Produce (may block)
        for _ in range(PRODUCER_RATE):
            if queue.put(f"event-{tick}", timeout=0.001):  # Non-blocking for sim
                produced_blocking += 1
        # Consume
        for _ in range(CONSUMER_RATE):
            if queue.get(timeout=0.001):
                consumed_blocking += 1
    
    # Drain remaining
    while queue.get(timeout=0.001):
        consumed_blocking += 1
    
    print(f"  Produced: {produced_blocking:,}")
    print(f"  Consumed: {consumed_blocking:,}")
    print(f"  Data loss: 0 (blocked producer when full)")
    print(f"  Effective producer rate: {produced_blocking/DURATION_TICKS:.0f}/tick "
          f"(throttled from {PRODUCER_RATE})")
    
    # ─── STRATEGY 2: DROPPING ───
    print("\n╔══ STRATEGY 2: DROPPING (Ring Buffer, capacity=5000) ══╗")
    
    ring = RingBuffer(capacity=5000)
    consumed_dropping = 0
    
    for tick in range(DURATION_TICKS):
        # Produce (always succeeds, may drop old)
        for _ in range(PRODUCER_RATE):
            ring.put(f"event-{tick}")
        # Consume
        for _ in range(CONSUMER_RATE):
            if ring.get():
                consumed_dropping += 1
    
    # Drain remaining
    while ring.get():
        consumed_dropping += 1
    
    total_produced = PRODUCER_RATE * DURATION_TICKS
    print(f"  Produced: {total_produced:,} (never blocked)")
    print(f"  Consumed: {consumed_dropping:,}")
    print(f"  Dropped: {ring.stats['dropped']:,} ({ring.drop_rate*100:.1f}%)")
    print(f"  ⚠ DATA LOSS: {ring.stats['dropped']:,} events permanently lost")
    
    # ─── STRATEGY 3: RATE LIMITING ───
    print("\n╔══ STRATEGY 3: RATE LIMITING (Token Bucket, rate=600/tick) ══╗")
    
    limiter = TokenBucket(rate=CONSUMER_RATE, burst=CONSUMER_RATE * 2)
    produced_limited = 0
    
    for tick in range(DURATION_TICKS):
        limiter.tokens = min(limiter.burst, limiter.tokens + limiter.rate)  # Refill
        for _ in range(PRODUCER_RATE):
            if limiter.try_acquire():
                produced_limited += 1
    
    print(f"  Attempted: {PRODUCER_RATE * DURATION_TICKS:,}")
    print(f"  Allowed: {limiter.stats['allowed']:,}")
    print(f"  Throttled: {limiter.stats['throttled']:,} ({limiter.throttle_rate*100:.1f}%)")
    print(f"  Effective rate: {limiter.stats['allowed']/DURATION_TICKS:.0f}/tick")
    print(f"  ⚠ Throttled events need retry or queue (not lost yet)")
    
    # ─── STRATEGY 4: ADAPTIVE SCALING ───
    print("\n╔══ STRATEGY 4: ADAPTIVE (Auto-scale, base=300/instance, max=5) ══╗")
    
    adaptive = AdaptiveConsumer(base_rate=300, max_instances=5)
    total_consumed_adaptive = 0
    
    for tick in range(DURATION_TICKS):
        consumed = adaptive.process_tick(PRODUCER_RATE)
        total_consumed_adaptive += consumed
    
    print(f"  Produced: {PRODUCER_RATE * DURATION_TICKS:,}")
    print(f"  Consumed: {total_consumed_adaptive:,}")
    print(f"  Final instances: {adaptive.current_instances}")
    print(f"  Max lag: {adaptive.stats['max_lag']:,}")
    print(f"  Remaining lag: {adaptive.lag:,}")
    print(f"  Scale-ups: {adaptive.stats['scale_ups']}, Scale-downs: {adaptive.stats['scale_downs']}")
    print(f"  Final rate: {adaptive.current_rate}/tick ({adaptive.current_instances} × 300)")
    
    # ─── COMPARISON TABLE ───
    print("\n╔══ COMPARISON ══╗")
    print(f"""
  ┌─────────────────┬──────────────┬──────────────┬──────────────┬───────────┐
  │ Strategy        │ Data Loss    │ Latency      │ Throughput   │ Complexity│
  ├─────────────────┼──────────────┼──────────────┼──────────────┼───────────┤
  │ Blocking        │ None         │ HIGH (waits) │ Limited      │ Low       │
  │ Dropping        │ {ring.stats['dropped']:,} events │ None         │ Full       │ Low       │
  │ Rate Limiting   │ None*        │ Medium       │ Controlled   │ Medium    │
  │ Adaptive        │ None         │ Variable     │ Scales up    │ High      │
  └─────────────────┴──────────────┴──────────────┴──────────────┴───────────┘
  * Rate-limited events must be retried (buffered elsewhere)
    """)
    
    print("╔══ WHEN TO USE EACH ══╗")
    print("""
  BLOCKING:   Financial transactions (CANNOT lose data, latency OK)
  DROPPING:   Metrics/logs (some loss acceptable, must not slow producer)
  RATE LIMIT: API calls to external service (protect downstream)
  ADAPTIVE:   Streaming pipelines (handle variable load, minimize cost)
  SPILLOVER:  Real-time + batch hybrid (hot path + cold overflow)
    """)


if __name__ == "__main__":
    simulate_backpressure()
```
