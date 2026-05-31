# Pattern 11: Dead Letter Queue (DLQ)

## What is a DLQ?

```
A Dead Letter Queue is a separate queue/topic where messages that cannot be 
processed successfully are sent instead of being lost or blocking the pipeline.

NORMAL FLOW:
  Event → Consumer → Process → Success → ACK

ERROR FLOW:
  Event → Consumer → Process → FAIL → Retry (1,2,3) → FAIL → DLQ

DLQ PURPOSE:
  • Prevent pipeline blockage (one bad event shouldn't stop everything)
  • Preserve failed events for investigation
  • Enable replay after fix
  • Provide visibility into failure patterns
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DEAD LETTER QUEUE ARCHITECTURE                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  MAIN PIPELINE                                                    │       │
│  │                                                                   │       │
│  │  Kafka Topic ─→ Consumer ─→ Process ─→ Output                     │       │
│  │  (events)       (Flink)     (transform)  (Iceberg)                │       │
│  │                     │                                             │       │
│  │                     │ On failure (after retries):                  │       │
│  │                     ▼                                             │       │
│  │  ┌─────────────────────────────────────────────────────────┐     │       │
│  │  │  ERROR HANDLER                                           │     │       │
│  │  │                                                          │     │       │
│  │  │  1. Catch exception                                      │     │       │
│  │  │  2. Classify error:                                      │     │       │
│  │  │     • Transient (timeout, rate limit) → Retry with backoff│    │       │
│  │  │     • Permanent (schema error, bad data) → DLQ immediately│    │       │
│  │  │     • Unknown → Retry 3x, then DLQ                       │     │       │
│  │  │  3. Enrich with error metadata                           │     │       │
│  │  │  4. Publish to DLQ topic                                 │     │       │
│  │  └──────────────────────┬──────────────────────────────────┘     │       │
│  └──────────────────────────┼────────────────────────────────────────┘      │
│                              │                                               │
│  ┌───────────────────────────▼───────────────────────────────────────┐      │
│  │  DLQ TOPIC (Kafka: events.dead-letter)                             │      │
│  │                                                                    │      │
│  │  Message format:                                                   │      │
│  │  {                                                                 │      │
│  │    "original_event": {...},                                        │      │
│  │    "error": {                                                      │      │
│  │      "message": "Schema validation failed: field 'amount' is string",    │
│  │      "exception": "SchemaValidationError",                         │      │
│  │      "stack_trace": "...",                                         │      │
│  │      "retry_count": 3,                                             │      │
│  │      "first_failure_at": "2024-01-15T10:00:00Z",                  │      │
│  │      "last_failure_at": "2024-01-15T10:00:30Z"                    │      │
│  │    },                                                              │      │
│  │    "metadata": {                                                   │      │
│  │      "source_topic": "orders.events",                              │      │
│  │      "source_partition": 5,                                        │      │
│  │      "source_offset": 12345678,                                    │      │
│  │      "pipeline": "order-enrichment",                               │      │
│  │      "consumer_group": "order-processor-v2"                        │      │
│  │    }                                                               │      │
│  │  }                                                                 │      │
│  │                                                                    │      │
│  │  Retention: 30 days (enough time to investigate and replay)        │      │
│  └────────────────────┬──────────────────────────────────────────────┘      │
│                        │                                                     │
│  ┌─────────────────────▼─────────────────────────────────────────────┐      │
│  │  DLQ CONSUMER / DASHBOARD                                          │      │
│  │                                                                    │      │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │      │
│  │  │  Alert           │  │  Dashboard      │  │  Replay Tool    │  │      │
│  │  │  (PagerDuty)     │  │  (Grafana)      │  │  (Manual/Auto)  │  │      │
│  │  │                  │  │                  │  │                  │  │     │
│  │  │  If DLQ rate >1%│  │  • Error types   │  │  • Select events│  │      │
│  │  │  → page on-call │  │  • Failure trend │  │  • Fix applied   │  │     │
│  │  │                  │  │  • Top errors    │  │  • Replay to     │  │     │
│  │  │                  │  │  • Per-pipeline  │  │    main topic    │  │     │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │      │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Retry Strategy: Exponential Backoff with Jitter

```python
import random
import time

def retry_with_backoff(func, max_retries=3, base_delay=1.0):
    """
    Retry pattern with exponential backoff + jitter.
    
    Attempt 1: delay = 1s ± jitter
    Attempt 2: delay = 2s ± jitter
    Attempt 3: delay = 4s ± jitter
    After 3 failures → DLQ
    
    WHY JITTER: Without jitter, all failed consumers retry at 
    the same time → thundering herd → downstream overwhelmed again.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError:
            delay = base_delay * (2 ** attempt)
            jitter = random.uniform(0, delay * 0.5)
            time.sleep(delay + jitter)
        except PermanentError:
            break  # Don't retry, go straight to DLQ
    
    # All retries exhausted → DLQ
    send_to_dlq(event, error, attempts=max_retries)
```

## Error Classification

```
TRANSIENT (retry will likely succeed):
  • Network timeout → retry after backoff
  • Rate limit (429) → retry after delay
  • Downstream temporarily unavailable → retry
  • Deadlock → retry (different timing)

PERMANENT (retry will NOT help):
  • Schema validation error → bad data, needs fix
  • Null pointer → logic bug, needs code fix
  • Invalid reference (FK violation) → data issue
  • Authentication failure → config issue

UNKNOWN (err on side of caution):
  • Unexpected exceptions → retry 3x, then DLQ
  • After fix: replay from DLQ
```

