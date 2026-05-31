# Pattern 18: Watermarks & Late Data Handling

## The Fundamental Problem

```
WHY IS TIME HARD IN STREAMING?
══════════════════════════════

In batch processing: All data is present. You know the "end" of the dataset.
In streaming: Data arrives CONTINUOUSLY and OUT OF ORDER.

SCENARIO: Window aggregation "orders per minute"
  
  Timeline (wall clock):
  10:00:00  Event arrives: order_time=10:00:00  ← on time
  10:00:03  Event arrives: order_time=09:59:58  ← LATE (2 sec late)
  10:00:05  Event arrives: order_time=09:58:30  ← VERY LATE (1.5 min late)
  10:00:10  Event arrives: order_time=09:45:00  ← EXTREMELY LATE (15 min late!)
  
QUESTION: When can you close the "09:59-10:00" window?
  
  If you close immediately at 10:00 → miss late events → WRONG COUNT
  If you wait forever → never produce results → INFINITE LATENCY
  
WATERMARK = "I believe all events with timestamp ≤ W have arrived."
  When watermark passes window end → close window → emit result
  
  Watermark is a TRADE-OFF between:
    • Correctness (wait longer → catch more late events)
    • Latency (wait shorter → produce results faster)
```

## Watermark Strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WATERMARK STRATEGIES                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STRATEGY 1: FIXED DELAY                                                     │
│  ────────────────────────                                                    │
│  Watermark = max(event_time) - fixed_delay                                   │
│                                                                              │
│  Example: delay = 10 seconds                                                 │
│    Events seen: 10:00:05, 10:00:03, 10:00:08                                │
│    Max event_time = 10:00:08                                                 │
│    Watermark = 10:00:08 - 10s = 09:59:58                                    │
│    → Any window ending ≤ 09:59:58 can be closed                             │
│                                                                              │
│  Pro: Simple, predictable                                                    │
│  Con: Fixed delay regardless of actual lateness                              │
│  Use: When event lateness is relatively uniform                              │
│                                                                              │
│  Flink: .assignTimestampsAndWatermarks(                                      │
│           WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(10))) │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  STRATEGY 2: PERCENTILE-BASED (Heuristic)                                   │
│  ──────────────────────────────────────────                                  │
│  Set delay to cover 99th percentile of lateness.                             │
│                                                                              │
│  Observe: Most events arrive within 5 sec, 99th pctl = 30 sec               │
│  Set watermark delay = 30 sec                                                │
│  Accept: 1% of events will be "late" (after watermark)                       │
│                                                                              │
│  Pro: Balances correctness and latency based on data                         │
│  Con: Requires profiling actual lateness distribution                        │
│  Use: Production systems where some loss is acceptable                       │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  STRATEGY 3: PROCESSING TIME (No watermark)                                  │
│  ──────────────────────────────────────────                                  │
│  Ignore event time. Use wall clock.                                          │
│                                                                              │
│  Window: "all events that ARRIVED between 10:00 and 10:01"                   │
│  Not: "all events that HAPPENED between 10:00 and 10:01"                     │
│                                                                              │
│  Pro: Simplest, no late data problem at all                                  │
│  Con: Results depend on system speed, not business time                      │
│  Use: Monitoring (alert on recent events) not analytics                      │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  STRATEGY 4: PER-SOURCE WATERMARK                                            │
│  ─────────────────────────────────                                           │
│  Each source/partition has its own watermark.                                │
│  Global watermark = MIN(all source watermarks)                               │
│                                                                              │
│  Source A watermark: 10:00:08 (healthy, recent data)                         │
│  Source B watermark: 09:55:00 (slow partition, lagging)                      │
│  Global watermark: MIN = 09:55:00 (held back by B!)                         │
│                                                                              │
│  Problem: One slow source holds back entire pipeline                         │
│  Solution: Idle source detection (advance watermark if no events)            │
│                                                                              │
│  Flink: .withIdleness(Duration.ofMinutes(1))                                │
│    → If source sends nothing for 1 min, exclude from global watermark        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Handling Late Data

```
WHAT HAPPENS TO DATA THAT ARRIVES AFTER THE WATERMARK?
═════════════════════════════════════════════════════

Three options:

1. DROP (Default in most systems)
   Late event arrives → window already closed → event is DISCARDED
   Flink: Default behavior after watermark passes
   Use when: Approximation is OK (monitoring, non-critical metrics)

2. ALLOWED LATENESS (Window stays open longer)
   Window result emitted at watermark, but window stays "open"
   Late events update the result (re-emit corrected value)
   
   Flink:
   .window(TumblingEventTimeWindows.of(Time.minutes(1)))
   .allowedLateness(Time.minutes(5))
   
   Timeline:
     Watermark passes 10:01 → emit preliminary count for [10:00-10:01]
     Event arrives at 10:03 with event_time 10:00:30 → WITHIN allowed lateness
       → Window reopened → updated count emitted
     Event arrives at 10:07 with event_time 10:00:30 → BEYOND allowed lateness
       → DROPPED (or sent to side output)

3. SIDE OUTPUT (Dead Letter for Late Events)
   Late events routed to a separate stream for later processing
   
   Flink:
   OutputTag<Event> lateTag = new OutputTag<>("late-events");
   
   .window(...)
   .allowedLateness(Time.minutes(5))
   .sideOutputLateData(lateTag)
   
   → Collect late events → batch-correct the window results later
   → Common pattern: Streaming gives fast (approximate) results,
     batch job corrects with late data overnight
```

## Production Architecture: Lambda with Watermarks

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SPEED + CORRECTNESS: Handling Late Data in Production                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  REAL-TIME PATH (Speed Layer)                                    │        │
│  │                                                                  │        │
│  │  Kafka → Flink (watermark = 30 sec) → Dashboard                 │        │
│  │                                                                  │        │
│  │  • Fast: Results in < 1 minute                                   │        │
│  │  • Approximate: May miss events > 30 sec late                    │        │
│  │  • Metric labeled: "preliminary" in dashboard                    │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  CORRECTION PATH (Batch Layer)                                   │        │
│  │                                                                  │        │
│  │  Schedule: Every 2 hours                                         │        │
│  │  Logic: Re-aggregate last 4 hours from raw events in lake        │        │
│  │  Output: Overwrite streaming results with "final" numbers        │        │
│  │                                                                  │        │
│  │  • Slow: 2-4 hour delay                                          │        │
│  │  • Complete: Includes ALL late events (they're in the lake now)  │        │
│  │  • Metric labeled: "final" in dashboard                          │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  USER EXPERIENCE:                                                            │
│  10:05 - Dashboard shows: "10:00-10:01: 1,234 orders (preliminary)"         │
│  12:00 - Dashboard shows: "10:00-10:01: 1,247 orders (final)"              │
│  Difference: 13 late events (1%) corrected by batch                         │
│                                                                              │
│  WHY BOTH?                                                                   │
│  • Business wants FAST metrics (don't wait hours)                            │
│  • Finance needs CORRECT numbers (can't be 1% off for reporting)            │
│  • Solution: Show both, clearly labeled                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Runnable Implementation

```python
"""
Watermarks & Late Data Handling - Complete Simulation
=====================================================
Demonstrates:
- Event-time vs processing-time windowing
- Watermark generation (fixed delay)
- Late event handling (drop, allow, side output)
- Window triggering based on watermark advancement
- Correction path for late data
"""

import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


@dataclass
class Event:
    """An event with both event-time and arrival-time."""
    event_id: str
    event_time: datetime        # When it HAPPENED (set by producer)
    arrival_time: datetime      # When it ARRIVED at processor
    value: float
    source: str = "default"
    
    @property
    def lateness(self) -> timedelta:
        """How late this event arrived relative to its event time."""
        return self.arrival_time - self.event_time


@dataclass
class WindowResult:
    """Result of a time window aggregation."""
    window_start: datetime
    window_end: datetime
    count: int
    total: float
    is_final: bool = False
    corrections: int = 0  # Number of late updates


class WatermarkGenerator:
    """Generates watermarks based on observed event times."""
    
    def __init__(self, max_delay: timedelta):
        self.max_delay = max_delay
        self.max_event_time: Optional[datetime] = None
        self.watermark: Optional[datetime] = None
    
    def observe(self, event_time: datetime) -> datetime:
        """Update watermark based on new event time."""
        if self.max_event_time is None or event_time > self.max_event_time:
            self.max_event_time = event_time
        
        self.watermark = self.max_event_time - self.max_delay
        return self.watermark
    
    def current(self) -> Optional[datetime]:
        return self.watermark


class StreamingWindowProcessor:
    """
    Event-time windowed processor with watermark-based triggering.
    Simulates Flink/Spark windowed aggregation.
    """
    
    def __init__(self, window_size: timedelta, watermark_delay: timedelta,
                 allowed_lateness: timedelta = timedelta(0)):
        self.window_size = window_size
        self.watermark_gen = WatermarkGenerator(watermark_delay)
        self.allowed_lateness = allowed_lateness
        
        # Active windows: window_start → WindowResult
        self.windows: Dict[datetime, WindowResult] = {}
        # Emitted (closed) windows
        self.emitted: List[WindowResult] = []
        # Late events (beyond allowed lateness)
        self.late_events: List[Event] = []
        # Stats
        self.stats = {
            "on_time": 0,
            "late_within_allowed": 0,
            "late_dropped": 0,
            "windows_emitted": 0,
            "windows_updated": 0,
        }
    
    def _get_window_start(self, event_time: datetime) -> datetime:
        """Determine which window this event belongs to."""
        # Tumbling window alignment
        epoch = datetime(2024, 1, 1)
        elapsed = (event_time - epoch).total_seconds()
        window_seconds = self.window_size.total_seconds()
        window_num = int(elapsed // window_seconds)
        return epoch + timedelta(seconds=window_num * window_seconds)
    
    def process(self, event: Event) -> Optional[WindowResult]:
        """Process a single event. Returns WindowResult if a window was emitted."""
        # Update watermark
        watermark = self.watermark_gen.observe(event.event_time)
        
        # Determine target window
        window_start = self._get_window_start(event.event_time)
        window_end = window_start + self.window_size
        
        # Check if event is late
        if watermark and event.event_time < watermark:
            # Event is LATE (arrived after watermark passed its event time)
            
            # Check if within allowed lateness
            lateness_deadline = window_end + self.allowed_lateness
            if watermark <= lateness_deadline:
                # Within allowed lateness → update existing window
                self._add_to_window(window_start, window_end, event)
                self.stats["late_within_allowed"] += 1
                # Re-emit updated result
                if window_start in self.windows:
                    self.windows[window_start].corrections += 1
                    return self.windows[window_start]
            else:
                # Beyond allowed lateness → DROP (side output)
                self.late_events.append(event)
                self.stats["late_dropped"] += 1
                return None
        else:
            # On-time event
            self._add_to_window(window_start, window_end, event)
            self.stats["on_time"] += 1
        
        # Check if any windows should be triggered (watermark passed end)
        emitted = self._try_emit_windows(watermark)
        return emitted
    
    def _add_to_window(self, window_start: datetime, window_end: datetime, event: Event):
        """Add event to appropriate window."""
        if window_start not in self.windows:
            self.windows[window_start] = WindowResult(
                window_start=window_start,
                window_end=window_end,
                count=0,
                total=0.0
            )
        self.windows[window_start].count += 1
        self.windows[window_start].total += event.value
    
    def _try_emit_windows(self, watermark: Optional[datetime]) -> Optional[WindowResult]:
        """Emit windows whose end time is past the watermark."""
        if watermark is None:
            return None
        
        emitted = None
        to_emit = []
        
        for window_start, result in self.windows.items():
            if result.window_end <= watermark and not result.is_final:
                result.is_final = True
                to_emit.append(result)
        
        for result in to_emit:
            self.emitted.append(result)
            self.stats["windows_emitted"] += 1
            emitted = result  # Return last emitted
        
        return emitted
    
    def flush(self) -> List[WindowResult]:
        """Force-emit all remaining windows (end of stream)."""
        remaining = []
        for window_start, result in self.windows.items():
            if not result.is_final:
                result.is_final = True
                self.emitted.append(result)
                remaining.append(result)
                self.stats["windows_emitted"] += 1
        return remaining


# ============================================================================
# EVENT GENERATOR (Simulates real-world out-of-order delivery)
# ============================================================================

def generate_events(
    start_time: datetime, 
    duration_minutes: int,
    events_per_minute: int,
    late_event_probability: float = 0.1,
    max_lateness_seconds: int = 120
) -> List[Event]:
    """Generate events with realistic out-of-order arrival."""
    events = []
    event_id = 0
    
    for minute in range(duration_minutes):
        for i in range(events_per_minute):
            event_id += 1
            
            # Event time: roughly within this minute
            event_time = start_time + timedelta(
                minutes=minute,
                seconds=random.uniform(0, 60)
            )
            
            # Arrival time: usually close to event time, sometimes very late
            if random.random() < late_event_probability:
                # Late event: arrives 5-120 seconds after event time
                delay = random.uniform(5, max_lateness_seconds)
            else:
                # On-time: arrives 0.1-3 seconds after event time
                delay = random.uniform(0.1, 3.0)
            
            arrival_time = event_time + timedelta(seconds=delay)
            
            events.append(Event(
                event_id=f"E-{event_id:06d}",
                event_time=event_time,
                arrival_time=arrival_time,
                value=random.uniform(10, 100),
                source=f"source-{random.randint(1, 3)}"
            ))
    
    # Sort by arrival time (this is how the processor would see them)
    events.sort(key=lambda e: e.arrival_time)
    return events


# ============================================================================
# DEMONSTRATION
# ============================================================================

def run_watermark_demo():
    """Compare different watermark strategies on the same dataset."""
    print("=" * 70)
    print("WATERMARKS & LATE DATA HANDLING")
    print("=" * 70)
    
    # Generate events
    start = datetime(2024, 1, 15, 10, 0, 0)
    events = generate_events(
        start_time=start,
        duration_minutes=10,
        events_per_minute=100,
        late_event_probability=0.15,
        max_lateness_seconds=90
    )
    
    print(f"\n  Generated {len(events)} events over 10 minutes")
    print(f"  Late event probability: 15%")
    print(f"  Max lateness: 90 seconds")
    
    # Analyze lateness distribution
    latenesses = [(e.arrival_time - e.event_time).total_seconds() for e in events]
    latenesses.sort()
    p50 = latenesses[len(latenesses)//2]
    p90 = latenesses[int(len(latenesses)*0.9)]
    p99 = latenesses[int(len(latenesses)*0.99)]
    
    print(f"\n  Lateness distribution:")
    print(f"    P50: {p50:.1f}s")
    print(f"    P90: {p90:.1f}s")
    print(f"    P99: {p99:.1f}s")
    print(f"    Max: {max(latenesses):.1f}s")
    
    # ─── STRATEGY A: Tight watermark (5 sec) ───
    print("\n╔══ STRATEGY A: Tight Watermark (5 sec delay) ══╗")
    print("  Fast results, but misses most late events")
    
    processor_a = StreamingWindowProcessor(
        window_size=timedelta(minutes=1),
        watermark_delay=timedelta(seconds=5),
        allowed_lateness=timedelta(seconds=0)  # No grace period
    )
    
    for event in events:
        processor_a.process(event)
    processor_a.flush()
    
    print(f"  On-time: {processor_a.stats['on_time']}")
    print(f"  Late (dropped): {processor_a.stats['late_dropped']}")
    print(f"  Windows emitted: {processor_a.stats['windows_emitted']}")
    drop_rate_a = processor_a.stats['late_dropped'] / len(events) * 100
    print(f"  DROP RATE: {drop_rate_a:.1f}%")
    
    # ─── STRATEGY B: Conservative watermark (30 sec) ───
    print("\n╔══ STRATEGY B: Conservative Watermark (30 sec delay) ══╗")
    print("  Slower results, catches most late events")
    
    processor_b = StreamingWindowProcessor(
        window_size=timedelta(minutes=1),
        watermark_delay=timedelta(seconds=30),
        allowed_lateness=timedelta(seconds=0)
    )
    
    for event in events:
        processor_b.process(event)
    processor_b.flush()
    
    print(f"  On-time: {processor_b.stats['on_time']}")
    print(f"  Late (dropped): {processor_b.stats['late_dropped']}")
    print(f"  Windows emitted: {processor_b.stats['windows_emitted']}")
    drop_rate_b = processor_b.stats['late_dropped'] / len(events) * 100
    print(f"  DROP RATE: {drop_rate_b:.1f}%")
    
    # ─── STRATEGY C: Watermark + Allowed Lateness ───
    print("\n╔══ STRATEGY C: Watermark (10 sec) + Allowed Lateness (60 sec) ══╗")
    print("  Fast preliminary results, accepts corrections for 60 sec")
    
    processor_c = StreamingWindowProcessor(
        window_size=timedelta(minutes=1),
        watermark_delay=timedelta(seconds=10),
        allowed_lateness=timedelta(seconds=60)
    )
    
    for event in events:
        processor_c.process(event)
    processor_c.flush()
    
    print(f"  On-time: {processor_c.stats['on_time']}")
    print(f"  Late (within grace): {processor_c.stats['late_within_allowed']}")
    print(f"  Late (dropped): {processor_c.stats['late_dropped']}")
    print(f"  Window corrections: {processor_c.stats['windows_updated'] if 'windows_updated' in processor_c.stats else sum(w.corrections for w in processor_c.emitted)}")
    drop_rate_c = processor_c.stats['late_dropped'] / len(events) * 100
    print(f"  DROP RATE: {drop_rate_c:.1f}%")
    print(f"  Late events saved: {processor_c.stats['late_within_allowed']}")
    
    # ─── COMPARISON ───
    print("\n╔══ STRATEGY COMPARISON ══╗")
    print(f"""
  ┌───────────────────┬──────────┬──────────────┬──────────────────────────┐
  │ Strategy          │ Latency  │ Drop Rate    │ Best For                  │
  ├───────────────────┼──────────┼──────────────┼──────────────────────────┤
  │ A: Tight (5s)     │ ~5 sec   │ {drop_rate_a:5.1f}%      │ Monitoring (speed > accuracy)│
  │ B: Conservative   │ ~30 sec  │ {drop_rate_b:5.1f}%      │ Analytics (accuracy matters) │
  │ C: Grace period   │ ~10 sec* │ {drop_rate_c:5.1f}%      │ Best of both worlds         │
  └───────────────────┴──────────┴──────────────┴──────────────────────────┘
  * C gives preliminary result at 10s, corrected result within 60s
    """)
    
    # ─── SIDE OUTPUT (Late Events for Batch Correction) ───
    print("╔══ SIDE OUTPUT: LATE EVENTS FOR BATCH CORRECTION ══╗")
    print(f"\n  Strategy C captured {len(processor_c.late_events)} events in side output")
    if processor_c.late_events:
        print(f"  These can be processed by a batch job to correct final numbers:")
        for evt in processor_c.late_events[:5]:
            print(f"    {evt.event_id}: event_time={evt.event_time.strftime('%H:%M:%S')}, "
                  f"arrived={evt.arrival_time.strftime('%H:%M:%S')}, "
                  f"lateness={evt.lateness.total_seconds():.0f}s")
        if len(processor_c.late_events) > 5:
            print(f"    ... and {len(processor_c.late_events) - 5} more")
    
    # ─── RECOMMENDATION ───
    print("\n╔══ PRODUCTION RECOMMENDATION ══╗")
    print(f"""
  1. Profile your data lateness distribution FIRST
     (Run: SELECT PERCENTILE(arrival_time - event_time, 0.99) FROM events)
     
  2. Set watermark = P95-P99 of lateness
     (Catches 95-99% of events, drops only extreme outliers)
     
  3. Add allowed lateness = 2-5x watermark delay
     (Safety net for events that are late but still valuable)
     
  4. Route dropped events to side output → batch correction
     (Nothing is truly lost, just delayed)
     
  5. Monitor watermark lag:
     Alert if watermark < processing_time - 5 minutes
     (Means events are arriving very late → investigate source)
    """)
    
    print("=" * 70)


if __name__ == "__main__":
    random.seed(42)
    run_watermark_demo()
```
