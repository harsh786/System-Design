# Pattern 02: Kappa Architecture

## Overview

Kappa Architecture simplifies Lambda by using a single stream processing engine for
BOTH real-time AND historical reprocessing. The immutable log (Kafka) IS the source of truth.

**Proposed by**: Jay Kreps (co-creator of Kafka, CEO of Confluent)
**Used at**: Uber, Netflix, Airbnb, Spotify, Stripe

---

## Why Kappa Over Lambda?

```
THE CORE INSIGHT:
═══════════════
If your stream processor can reprocess historical data 
by replaying the log, you DON'T need a separate batch layer.

Lambda Pain Points that Kappa Solves:
1. TWO codebases (batch + stream) = 2x bugs, 2x maintenance
2. Results diverge between batch and speed layers
3. Complex merge logic in serving layer
4. Batch delay means stale corrections

Kappa Promise:
- ONE codebase, ONE processing path
- Replay log for reprocessing (like a "batch" job)
- Simpler operations, fewer moving parts
```

---

## Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KAPPA ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                    DATA SOURCES                                   │        │
│  │  [Web Events] [Mobile App] [IoT] [Databases via CDC] [APIs]      │        │
│  └──────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────┐       │
│  │         IMMUTABLE LOG (Source of Truth)                            │       │
│  │         Apache Kafka with Long Retention                           │       │
│  │                                                                    │       │
│  │  WHY KAFKA AS SOURCE OF TRUTH:                                     │       │
│  │  • Immutable: Events never modified once written                   │       │
│  │  • Replayable: Any consumer can re-read from beginning             │       │
│  │  • Ordered: Within partition, total order guaranteed                │       │
│  │  • Durable: Replicated across brokers                              │       │
│  │  • Retention: Days → Years (tiered storage)                        │       │
│  │                                                                    │       │
│  │  Retention Strategy:                                               │       │
│  │  ┌────────┐  ┌──────────┐  ┌──────────────┐                      │       │
│  │  │ Hot    │→ │ Warm     │→ │ Cold (S3/GCS)│                       │       │
│  │  │ 7 days │  │ 30 days  │  │ 1-7 years    │                      │       │
│  │  │ SSD    │  │ HDD      │  │ Object Store │                      │       │
│  │  └────────┘  └──────────┘  └──────────────┘                      │       │
│  └───────────────────────────────┬──────────────────────────────────┘       │
│                                   │                                          │
│  ┌────────────────────────────────▼─────────────────────────────────┐       │
│  │         STREAM PROCESSING ENGINE (Single Path)                     │       │
│  │         Apache Flink / Kafka Streams / Spark Structured Streaming  │       │
│  │                                                                    │       │
│  │  ┌─────────────────────────────────────────────────────┐          │       │
│  │  │  REAL-TIME MODE (Normal Operation)                   │          │       │
│  │  │  • Consumes from latest offset                       │          │       │
│  │  │  • Processes events as they arrive                   │          │       │
│  │  │  • Updates materialized views continuously           │          │       │
│  │  │  • Latency: milliseconds                             │          │       │
│  │  └─────────────────────────────────────────────────────┘          │       │
│  │                                                                    │       │
│  │  ┌─────────────────────────────────────────────────────┐          │       │
│  │  │  REPROCESSING MODE (When logic changes)              │          │       │
│  │  │  • Deploy new version of processor (v2)              │          │       │
│  │  │  • v2 reads from BEGINNING of log                    │          │       │
│  │  │  • Builds new output (parallel to v1)                │          │       │
│  │  │  • Once v2 catches up → swap (atomic cutover)        │          │       │
│  │  │  • Retire v1                                         │          │       │
│  │  └─────────────────────────────────────────────────────┘          │       │
│  └────────────────────────────────┬─────────────────────────────────┘       │
│                                    │                                         │
│  ┌─────────────────────────────────▼────────────────────────────────┐       │
│  │         SERVING / MATERIALIZED VIEWS                               │       │
│  │                                                                    │       │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐          │       │
│  │  │ Redis   │ │ Elastic  │ │ Pinot   │ │ PostgreSQL   │           │       │
│  │  │ (K/V)   │ │ (Search) │ │ (OLAP)  │ │ (Relational) │           │       │
│  │  └─────────┘ └──────────┘ └─────────┘ └──────────────┘          │       │
│  │                                                                    │       │
│  │  Each is a "materialized view" of the stream                       │       │
│  │  Consumers can rebuild any view by replaying                       │       │
│  └────────────────────────────────────────────────────────────────── │       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Reprocessing Strategy (The Key Innovation)

```
SCENARIO: You need to fix a bug in your processing logic

LAMBDA APPROACH:
  1. Fix batch job code
  2. Re-run batch (hours to complete)
  3. Fix speed layer code separately
  4. Hope they produce same results

KAPPA APPROACH:
  ┌─────────────────────────────────────────────────────────────┐
  │                                                              │
  │   Time ───────────────────────────────────────────────►      │
  │                                                              │
  │   v1 (buggy):  ████████████████████████████                  │
  │                 reading from latest, serving queries          │
  │                                                              │
  │   v2 (fixed):       ░░░░░░░░░░░░░░░░░░████████              │
  │                     reading from beginning,                  │
  │                     building new output                       │
  │                                                              │
  │   Cutover point:                        ↑                    │
  │                              v2 caught up to v1              │
  │                              Swap routing to v2              │
  │                              Shut down v1                    │
  │                                                              │
  └─────────────────────────────────────────────────────────────┘
```

---

## Scalability Deep Dive

### Kafka Scalability (The Foundation)
```
┌────────────────────────────────────────────────────────────────┐
│  KAFKA CLUSTER SIZING FOR KAPPA                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Throughput Target: 1 million events/sec                        │
│                                                                 │
│  Calculation:                                                   │
│  ─────────────                                                  │
│  Avg event size: 1 KB                                           │
│  Required bandwidth: 1M × 1KB = 1 GB/s write                   │
│  Replication factor: 3                                          │
│  Total write load: 3 GB/s across cluster                        │
│                                                                 │
│  Per broker capacity: 200 MB/s (SSD, 10Gbps network)            │
│  Brokers needed: 3 GB/s ÷ 200 MB/s = 15 brokers minimum        │
│  With headroom (60% util): 25 brokers                           │
│                                                                 │
│  Partitions:                                                    │
│  Target parallelism: 100 Flink tasks                            │
│  Partitions per topic: 100 (1:1 with tasks)                     │
│  Max partitions/broker: 4000                                    │
│  Total: 100 partitions × topics = well within limits            │
│                                                                 │
│  Retention (Tiered Storage):                                    │
│  Hot (SSD): 7 days × 1GB/s × 86400 = 604 TB                    │
│  Warm (S3): 365 days = 31 PB                                    │
│  Cost: $0.023/GB/month for S3 = ~$700K/year for 1yr retention   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Flink Scalability (The Processor)
```
┌────────────────────────────────────────────────────────────────┐
│  FLINK CLUSTER SIZING                                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Processing 1M events/sec with stateful operations:             │
│                                                                 │
│  TaskManagers: 50 (each 8 cores, 32GB RAM)                      │
│  Parallelism: 200 tasks                                         │
│  State backend: RocksDB (spills to disk)                        │
│  State size: ~500 GB (windowed aggregations)                    │
│  Checkpoint interval: 60 seconds                                │
│  Checkpoint storage: S3 (for recovery)                          │
│                                                                 │
│  Reprocessing scenario:                                         │
│  - 30 days of data = 30 × 86400 × 1M = 2.6 trillion events    │
│  - Reprocess rate: 5M events/sec (batch-optimized)              │
│  - Time to reprocess: 2.6T ÷ 5M = ~6 days                     │
│  - Solution: Spin up 5x cluster temporarily = 1.2 days         │
│                                                                 │
│  Cost optimization:                                             │
│  - Normal: 50 TaskManagers (on-demand)                          │
│  - Reprocessing: 250 TaskManagers (spot instances, 70% savings) │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Runnable Example: Complete Kappa Architecture

```python
"""
Kappa Architecture Implementation
==================================
Single stream processing path for:
- Real-time processing (normal mode)
- Historical reprocessing (replay mode)
- Versioned processors with atomic cutover

Run: python kappa_architecture.py
"""

import time
import json
import threading
import random
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import hashlib


# ============================================================================
# IMMUTABLE LOG (Simulated Kafka with Tiered Storage)
# ============================================================================

class RetentionTier(Enum):
    HOT = "hot"       # In-memory, fast access
    WARM = "warm"     # On-disk, slower
    COLD = "cold"     # Object store, slowest

@dataclass
class LogSegment:
    """Represents a Kafka log segment"""
    messages: List[dict] = field(default_factory=list)
    start_offset: int = 0
    end_offset: int = 0
    tier: RetentionTier = RetentionTier.HOT
    created_at: float = field(default_factory=time.time)


class ImmutableLog:
    """
    Immutable append-only log with tiered storage.
    
    This is the SINGLE SOURCE OF TRUTH in Kappa Architecture.
    
    Key Properties:
    1. Append-only: Events are never modified
    2. Ordered: Total order within each partition
    3. Replayable: Any consumer can read from any offset
    4. Retained: Long-term storage for full replay
    """
    
    def __init__(self, num_partitions: int = 8, 
                 hot_retention_sec: int = 30,
                 warm_retention_sec: int = 120):
        self.num_partitions = num_partitions
        self.partitions: Dict[int, List[dict]] = {
            i: [] for i in range(num_partitions)
        }
        self.hot_retention = hot_retention_sec
        self.warm_retention = warm_retention_sec
        self._lock = threading.Lock()
        self.total_messages = 0
    
    def append(self, key: str, value: dict) -> tuple:
        """Append event to log (immutable write)"""
        partition = hash(key) % self.num_partitions
        
        with self._lock:
            offset = len(self.partitions[partition])
            record = {
                'offset': offset,
                'key': key,
                'value': value,
                'timestamp': time.time(),
                'partition': partition
            }
            self.partitions[partition].append(record)
            self.total_messages += 1
            return partition, offset
    
    def read(self, partition: int, from_offset: int = 0, 
             max_records: int = 1000) -> List[dict]:
        """Read from any offset (enables replay)"""
        with self._lock:
            return self.partitions[partition][from_offset:from_offset + max_records]
    
    def read_all(self, from_offset: int = 0) -> List[dict]:
        """Read all messages across partitions (for reprocessing)"""
        all_msgs = []
        with self._lock:
            for partition_msgs in self.partitions.values():
                all_msgs.extend(partition_msgs[from_offset:])
        return sorted(all_msgs, key=lambda x: x['timestamp'])
    
    def get_latest_offsets(self) -> Dict[int, int]:
        """Get latest offset for each partition"""
        with self._lock:
            return {p: len(msgs) for p, msgs in self.partitions.items()}


# ============================================================================
# STREAM PROCESSOR (Versioned, Stateful)
# ============================================================================

@dataclass
class ProcessorState:
    """Encapsulates processor state for checkpointing"""
    counters: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    sets: Dict[str, set] = field(default_factory=lambda: defaultdict(set))
    windows: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(float))
    )
    offsets: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    events_processed: int = 0


class StreamProcessor:
    """
    Versioned stream processor supporting real-time and replay modes.
    
    KEY CONCEPT: Same code handles both real-time AND reprocessing.
    The only difference is WHERE you start reading from.
    
    - Real-time: Read from latest offset (normal operation)
    - Replay: Read from beginning (reprocessing for bug fix/new logic)
    
    VERSION MANAGEMENT:
    - Each processor version has unique ID
    - Multiple versions can run simultaneously
    - Atomic cutover when new version catches up
    """
    
    def __init__(self, version: str, 
                 process_fn: Callable,
                 log: ImmutableLog):
        self.version = version
        self.process_fn = process_fn
        self.log = log
        self.state = ProcessorState()
        self.running = False
        self.mode = "real-time"  # or "replay"
        self.caught_up = False
        self._lock = threading.Lock()
    
    def start_realtime(self):
        """Start processing from latest (normal operation)"""
        self.mode = "real-time"
        self.running = True
        latest_offsets = self.log.get_latest_offsets()
        self.state.offsets = dict(latest_offsets)
        self.caught_up = True
        print(f"  [Processor v{self.version}] Started REAL-TIME from latest offsets")
    
    def start_replay(self):
        """Start processing from beginning (reprocessing)"""
        self.mode = "replay"
        self.running = True
        self.state = ProcessorState()  # Fresh state
        self.caught_up = False
        print(f"  [Processor v{self.version}] Started REPLAY from offset 0")
    
    def process_batch(self) -> int:
        """Process available messages (called in a loop)"""
        total_processed = 0
        
        for partition in range(self.log.num_partitions):
            current_offset = self.state.offsets.get(partition, 0)
            messages = self.log.read(partition, current_offset, max_records=100)
            
            for msg in messages:
                self.process_fn(msg['value'], self.state)
                self.state.events_processed += 1
                total_processed += 1
            
            if messages:
                self.state.offsets[partition] = current_offset + len(messages)
        
        # Check if replay has caught up
        if self.mode == "replay" and not self.caught_up:
            latest = self.log.get_latest_offsets()
            if all(self.state.offsets.get(p, 0) >= latest[p] 
                   for p in range(self.log.num_partitions)):
                self.caught_up = True
                print(f"  [Processor v{self.version}] CAUGHT UP! Ready for cutover.")
        
        return total_processed
    
    def get_view(self) -> dict:
        """Get current materialized view from processor state"""
        with self._lock:
            return {
                'version': self.version,
                'mode': self.mode,
                'caught_up': self.caught_up,
                'events_processed': self.state.events_processed,
                'revenue': dict(self.state.counters),
                'unique_users': {k: len(v) for k, v in self.state.sets.items()},
            }
    
    def checkpoint(self) -> dict:
        """Save state for recovery (simulates Flink checkpointing)"""
        return {
            'version': self.version,
            'offsets': dict(self.state.offsets),
            'events_processed': self.state.events_processed,
            'timestamp': time.time()
        }


# ============================================================================
# PROCESSING LOGIC (Versioned)
# ============================================================================

def process_v1(event: dict, state: ProcessorState):
    """
    Version 1: Basic revenue aggregation
    (The "buggy" version - doesn't handle refunds)
    """
    if event.get('type') == 'purchase':
        day = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d')
        state.counters[f"revenue_{day}"] += event['amount']
        state.counters["total_revenue"] += event['amount']
        state.counters[f"orders_{day}"] += 1
        state.counters["total_orders"] += 1
        state.sets[f"users_{day}"].add(event['user_id'])


def process_v2(event: dict, state: ProcessorState):
    """
    Version 2: Fixed - handles refunds correctly
    (Deployed as new version, replays from beginning)
    """
    if event.get('type') == 'purchase':
        day = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d')
        state.counters[f"revenue_{day}"] += event['amount']
        state.counters["total_revenue"] += event['amount']
        state.counters[f"orders_{day}"] += 1
        state.counters["total_orders"] += 1
        state.sets[f"users_{day}"].add(event['user_id'])
    
    elif event.get('type') == 'refund':
        # v2 FIX: Properly subtract refunds
        day = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d')
        state.counters[f"revenue_{day}"] -= event['amount']
        state.counters["total_revenue"] -= event['amount']
        state.counters[f"refunds_{day}"] += 1
        state.counters["total_refunds"] += 1


# ============================================================================
# SERVING LAYER (Materialized Views)
# ============================================================================

class ServingLayer:
    """
    Routes queries to the active processor version.
    
    During reprocessing:
    - Queries still go to v1 (active)
    - v2 builds its view in background
    - Once v2 catches up → atomic switch
    
    This ensures ZERO DOWNTIME during reprocessing.
    """
    
    def __init__(self):
        self.active_processor: Optional[StreamProcessor] = None
        self.pending_processor: Optional[StreamProcessor] = None
    
    def set_active(self, processor: StreamProcessor):
        self.active_processor = processor
    
    def set_pending(self, processor: StreamProcessor):
        self.pending_processor = processor
    
    def try_cutover(self) -> bool:
        """Attempt atomic cutover from active to pending"""
        if self.pending_processor and self.pending_processor.caught_up:
            old_version = self.active_processor.version if self.active_processor else "none"
            self.active_processor = self.pending_processor
            self.pending_processor = None
            print(f"\n  *** CUTOVER: v{old_version} → v{self.active_processor.version} ***\n")
            return True
        return False
    
    def query(self) -> dict:
        """Query active materialized view"""
        if self.active_processor:
            view = self.active_processor.get_view()
            view['serving_status'] = 'active'
            if self.pending_processor:
                view['pending_version'] = self.pending_processor.version
                view['pending_progress'] = self.pending_processor.state.events_processed
            return view
        return {'error': 'no active processor'}


# ============================================================================
# ORCHESTRATOR
# ============================================================================

def run_kappa_architecture():
    """
    Demonstrates Kappa Architecture with:
    1. Normal real-time processing (v1)
    2. Bug discovered → deploy v2 with replay
    3. v2 catches up → atomic cutover
    4. v1 retired
    """
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           KAPPA ARCHITECTURE - LIVE DEMONSTRATION               ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Phase 1: Normal operation with processor v1                     ║
║  Phase 2: Bug found! Deploy v2 with replay from beginning        ║
║  Phase 3: v2 catches up, atomic cutover                          ║
║  Phase 4: v1 retired, v2 serves all queries                      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize
    log = ImmutableLog(num_partitions=4)
    serving = ServingLayer()
    
    # Phase 1: Start v1 processor
    print("=" * 60)
    print("PHASE 1: Normal Operation with Processor v1")
    print("=" * 60)
    
    processor_v1 = StreamProcessor("1.0", process_v1, log)
    processor_v1.start_realtime()
    serving.set_active(processor_v1)
    
    # Produce events (mix of purchases and refunds)
    print("\n  Producing 1000 events (purchases + refunds)...")
    for i in range(1000):
        event_type = 'purchase' if random.random() > 0.1 else 'refund'
        event = {
            'event_id': f"evt_{i}",
            'type': event_type,
            'user_id': f"user_{random.randint(1, 200)}",
            'amount': round(random.uniform(10, 200), 2),
            'category': random.choice(['electronics', 'food', 'books']),
            'timestamp': time.time() - random.uniform(0, 3600),
        }
        log.append(event['user_id'], event)
    
    # Process all events with v1
    processor_v1.process_batch()
    
    view_v1 = serving.query()
    print(f"\n  v1 Results:")
    print(f"    Events processed: {view_v1['events_processed']}")
    print(f"    Total Revenue: ${view_v1['revenue'].get('total_revenue', 0):,.2f}")
    print(f"    Total Orders: {view_v1['revenue'].get('total_orders', 0):,.0f}")
    print(f"    NOTE: v1 ignores refunds! Revenue is OVERSTATED.")
    
    # Phase 2: Bug discovered, deploy v2
    print(f"\n{'=' * 60}")
    print("PHASE 2: Bug Found! Deploying v2 with Replay")
    print("=" * 60)
    print("\n  Bug: v1 doesn't subtract refunds from revenue!")
    print("  Fix: v2 properly handles refund events")
    print("  Strategy: Deploy v2, replay from beginning, cutover when caught up")
    
    processor_v2 = StreamProcessor("2.0", process_v2, log)
    processor_v2.start_replay()  # Start from offset 0
    serving.set_pending(processor_v2)
    
    # Meanwhile, more events arrive (v1 still serving)
    print("\n  Meanwhile, 200 more events arriving (v1 still serving)...")
    for i in range(1000, 1200):
        event_type = 'purchase' if random.random() > 0.15 else 'refund'
        event = {
            'event_id': f"evt_{i}",
            'type': event_type,
            'user_id': f"user_{random.randint(1, 200)}",
            'amount': round(random.uniform(10, 200), 2),
            'category': random.choice(['electronics', 'food', 'books']),
            'timestamp': time.time(),
        }
        log.append(event['user_id'], event)
    
    # v1 processes new events
    processor_v1.process_batch()
    
    # v2 replaying historical data
    print("\n  v2 replaying historical data...")
    replay_rounds = 0
    while not processor_v2.caught_up:
        processed = processor_v2.process_batch()
        replay_rounds += 1
        if replay_rounds % 5 == 0:
            print(f"    Replay round {replay_rounds}: "
                  f"{processor_v2.state.events_processed} events processed")
    
    # Phase 3: Cutover
    print(f"\n{'=' * 60}")
    print("PHASE 3: Atomic Cutover")
    print("=" * 60)
    
    serving.try_cutover()
    
    view_v2 = serving.query()
    print(f"\n  v2 Results (CORRECTED):")
    print(f"    Events processed: {view_v2['events_processed']}")
    print(f"    Total Revenue: ${view_v2['revenue'].get('total_revenue', 0):,.2f}")
    print(f"    Total Orders: {view_v2['revenue'].get('total_orders', 0):,.0f}")
    print(f"    Total Refunds: {view_v2['revenue'].get('total_refunds', 0):,.0f}")
    
    # Compare
    print(f"\n{'=' * 60}")
    print("COMPARISON: v1 vs v2")
    print("=" * 60)
    v1_rev = view_v1['revenue'].get('total_revenue', 0)
    v2_rev = view_v2['revenue'].get('total_revenue', 0)
    print(f"  v1 Revenue (buggy, no refunds): ${v1_rev:,.2f}")
    print(f"  v2 Revenue (correct, with refunds): ${v2_rev:,.2f}")
    print(f"  Difference (refund impact): ${v1_rev - v2_rev:,.2f}")
    print(f"\n  KEY INSIGHT: Kappa let us fix the bug by replaying")
    print(f"  the SAME log with CORRECTED logic. Zero data loss.")
    print(f"  Zero downtime (v1 served queries during replay).")


if __name__ == '__main__':
    run_kappa_architecture()
```

---

## Production Deployment Patterns

### Blue-Green Reprocessing
```
┌─────────────────────────────────────────────────────────────┐
│  BLUE-GREEN DEPLOYMENT FOR KAPPA REPROCESSING               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  BLUE (Active - v1):                                         │
│  ┌─────────────────────────────────────┐                    │
│  │ Kafka ──→ Flink Job v1 ──→ Pinot A  │ ◄── Queries       │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  GREEN (Reprocessing - v2):                                  │
│  ┌─────────────────────────────────────┐                    │
│  │ Kafka ──→ Flink Job v2 ──→ Pinot B  │    (building)      │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  Load Balancer:  [BLUE=100%] [GREEN=0%]                      │
│                                                              │
│  After cutover:  [BLUE=0%]   [GREEN=100%]                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### State Management for Large-Scale Kappa
```
WHY RocksDB + Incremental Checkpoints:
──────────────────────────────────────

Problem: State can grow to TBs (user sessions, aggregation windows)
Solution: RocksDB as state backend

┌─────────────────────────────────────────────────────────────┐
│  Flink TaskManager                                           │
│  ┌─────────────────────────────────────────┐                │
│  │  Operator State                          │                │
│  │  ┌──────────────────────────────┐       │                │
│  │  │  RocksDB (embedded)          │       │                │
│  │  │  • LSM-tree structure        │       │                │
│  │  │  • Spills to local SSD       │       │                │
│  │  │  • Handles TB-scale state    │       │                │
│  │  └──────────────┬───────────────┘       │                │
│  │                 │ Checkpoint             │                │
│  │                 ▼                        │                │
│  │  ┌──────────────────────────────┐       │                │
│  │  │  S3 (Checkpoint Storage)     │       │                │
│  │  │  • Incremental (only deltas) │       │                │
│  │  │  • Enables fast recovery     │       │                │
│  │  │  • ~60s checkpoint interval  │       │                │
│  │  └──────────────────────────────┘       │                │
│  └─────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘

Recovery Time Calculation:
- State size: 500 GB
- S3 read throughput: 5 GB/s
- Download time: 100 seconds
- Replay uncommitted: ~60s of events
- Total recovery: ~3 minutes
```

---

## When Kappa Fails (Know the Limits)

| Scenario | Problem with Kappa | Alternative |
|----------|-------------------|-------------|
| 7-year reprocessing | Log too large, takes days | Lambda + cold batch |
| Complex ML training | Stream processor not ideal for training | Lambda (batch for ML) |
| Ad-hoc queries | Can't "query the stream" arbitrarily | Lakehouse (Delta/Iceberg) |
| Very late data (days) | Watermarks already advanced | Lambda with late-data handling |
| Cross-domain joins | Hard in streaming (unbounded state) | Batch + materialized views |

---

## Uber's Kappa at Scale

```
UBER'S REAL-TIME ANALYTICS (Kappa-based):
─────────────────────────────────────────

Scale:
- 1 trillion events/day
- 100+ PB data
- P99 latency < 1 second

Stack:
- Kafka: Ingestion (trillions of msgs)
- Apache Flink: Stream processing
- Apache Pinot: Real-time OLAP serving
- Apache Hudi: Table format for replay

Key Decisions:
1. WHY Flink over Spark Streaming?
   → True event-time processing
   → Lower latency (ms vs seconds)
   → Better exactly-once guarantees

2. WHY Pinot for serving?
   → Sub-second queries on real-time data
   → Handles both real-time segments + offline segments
   → Star-tree index for pre-aggregation

3. WHY Hudi for storage?
   → Upserts (riders/drivers update frequently)
   → Incremental queries (only read changes)
   → Enables replay without Kafka's full retention cost
```

