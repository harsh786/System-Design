# Problem 53: Event-Time Processing with Watermarks

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

