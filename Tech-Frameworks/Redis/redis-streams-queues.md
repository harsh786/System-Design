# Redis Streams & Message Queues — Production Deep Dive

## 1. Stream Internals: Radix Tree + Listpacks

Redis Streams use a **radix tree** of macro-nodes, each containing a **listpack** (compact, sorted byte array) of entries. This gives O(log N) seeking with excellent memory density.

```
Stream Structure:
┌─────────────────────────────────────────────────┐
│ Radix Tree (indexed by entry ID prefix)         │
│                                                 │
│  Node: 1685000000000                            │
│  ┌─────────────────────────────────────┐        │
│  │ Listpack (up to ~4KB of entries)    │        │
│  │ [1685000000000-0: {k1:v1, k2:v2}]  │        │
│  │ [1685000000000-1: {k1:v3, k2:v4}]  │        │
│  │ [1685000000000-2: {k1:v5, k2:v6}]  │        │
│  └─────────────────────────────────────┘        │
│                                                 │
│  Node: 1685000001000                            │
│  ┌─────────────────────────────────────┐        │
│  │ Listpack                            │        │
│  │ [1685000001000-0: {k1:v7, k2:v8}]  │        │
│  └─────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

**Entry IDs** are `<millisecondsTimestamp>-<sequenceNumber>`. Auto-generated IDs guarantee monotonic ordering even under clock skew (Redis uses the max of current time and last ID's timestamp).

**Memory efficiency**: Streams with consistent field names across entries achieve delta compression — only the first entry in a listpack stores field names; subsequent entries reference them by offset.

---

## 2. Basic Stream Operations

```python
import redis
import time
import json
from typing import Optional

class StreamProducer:
    """Produces messages to a Redis Stream."""

    def __init__(self, r: redis.Redis, stream: str, maxlen: Optional[int] = None):
        self.r = r
        self.stream = stream
        self.maxlen = maxlen

    def publish(self, data: dict) -> str:
        """Add entry to stream. Returns the auto-generated entry ID."""
        kwargs = {}
        if self.maxlen:
            # Approximate trimming (~) is faster — trims to within ~100 entries
            kwargs["approximate"] = True
            kwargs["maxlen"] = self.maxlen

        # XADD stream [MAXLEN ~ count] * field value [field value ...]
        entry_id = self.r.xadd(self.stream, data, **kwargs)
        return entry_id

    def publish_batch(self, messages: list[dict]) -> list[str]:
        """Publish multiple messages in a pipeline."""
        pipe = self.r.pipeline(transaction=False)
        for msg in messages:
            if self.maxlen:
                pipe.xadd(self.stream, msg, maxlen=self.maxlen, approximate=True)
            else:
                pipe.xadd(self.stream, msg)
        return pipe.execute()

    def trim(self, maxlen: int = None, minid: str = None):
        """Explicit trim — by count or by minimum ID (time-based retention)."""
        if minid:
            # XTRIM stream MINID ~ <id>  — remove entries older than this ID
            self.r.xtrim(self.stream, minid=minid, approximate=True)
        elif maxlen:
            self.r.xtrim(self.stream, maxlen=maxlen, approximate=True)


class StreamReader:
    """Reads messages from a stream without consumer groups (fan-out pattern)."""

    def __init__(self, r: redis.Redis, stream: str):
        self.r = r
        self.stream = stream
        self.last_id = "0-0"  # Start from beginning

    def read_new(self, count: int = 10, block_ms: int = 0) -> list:
        """
        Read new entries since last read.
        block_ms=0 means non-blocking; block_ms>0 blocks up to that duration.
        """
        # XREAD [COUNT count] [BLOCK ms] STREAMS stream id
        results = self.r.xread(
            {self.stream: self.last_id},
            count=count,
            block=block_ms if block_ms > 0 else None
        )

        if not results:
            return []

        entries = results[0][1]  # [(id, {fields}), ...]
        if entries:
            self.last_id = entries[-1][0]  # Track position for next read
        return entries

    def read_range(self, start: str = "-", end: str = "+", count: int = 100) -> list:
        """Read a range of entries (historical replay)."""
        return self.r.xrange(self.stream, min=start, max=end, count=count)

    def read_from_timestamp(self, timestamp_ms: int, count: int = 100) -> list:
        """Read entries from a specific timestamp."""
        start_id = f"{timestamp_ms}-0"
        return self.r.xrange(self.stream, min=start_id, max="+", count=count)


# Usage
r = redis.Redis(decode_responses=True)

producer = StreamProducer(r, "orders:events", maxlen=100_000)

# Publish events
entry_id = producer.publish({
    "event_type": "order_created",
    "order_id": "ord_12345",
    "user_id": "usr_789",
    "amount": "99.99",
    "timestamp": str(int(time.time() * 1000))
})
print(f"Published: {entry_id}")  # e.g., "1685000000000-0"

# Read entries
reader = StreamReader(r, "orders:events")
entries = reader.read_new(count=5, block_ms=2000)
for entry_id, fields in entries:
    print(f"  {entry_id}: {fields}")
```

---

## 3. Consumer Groups: Distributed Processing

Consumer groups provide **exactly-once delivery semantics** (at-least-once with idempotent consumers), load balancing across consumers, message acknowledgment, and pending entry tracking.

```
Consumer Group Architecture:
┌─────────────────────────────────────────────────────────────┐
│ Stream: "orders:events"                                     │
│ [msg1] [msg2] [msg3] [msg4] [msg5] [msg6] [msg7] [msg8]   │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │ Group: "processors" │
              │ last-delivered: msg5│
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
    │Consumer A │ │Consumer B │ │Consumer C │
    │PEL: msg1  │ │PEL: msg3  │ │PEL: msg5  │
    │     msg4  │ │           │ │           │
    └───────────┘ └───────────┘ └───────────┘
    (msg2 ACK'd)  (msg3 pending) (msg5 pending)
```

```python
import redis
import time
import threading
from dataclasses import dataclass
from typing import Callable, Optional
import signal


@dataclass
class ConsumerConfig:
    stream: str
    group: str
    consumer_name: str
    batch_size: int = 10
    block_ms: int = 5000
    max_retries: int = 3
    claim_idle_ms: int = 30_000  # Claim messages idle for 30s
    ack_deadline_ms: int = 60_000  # Must ACK within 60s


class ConsumerGroupWorker:
    """
    Production-grade consumer group worker with:
    - Automatic group/stream creation
    - Pending message recovery on startup
    - Dead letter queue for poison messages
    - Graceful shutdown
    - Idle message claiming (handling crashed consumers)
    """

    def __init__(self, r: redis.Redis, config: ConsumerConfig,
                 handler: Callable[[str, dict], bool]):
        self.r = r
        self.config = config
        self.handler = handler
        self.running = False
        self._ensure_group_exists()

    def _ensure_group_exists(self):
        """Create stream and consumer group if they don't exist."""
        try:
            # XGROUP CREATE stream group id [MKSTREAM]
            self.r.xgroup_create(
                self.config.stream,
                self.config.group,
                id="0",  # Start from beginning of stream
                mkstream=True  # Create stream if it doesn't exist
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise  # Group already exists — that's fine

    def start(self):
        """Start processing: first recover pending, then read new."""
        self.running = True

        # Phase 1: Recover any pending messages from a previous crash
        self._recover_pending()

        # Phase 2: Process new messages
        self._process_loop()

    def stop(self):
        """Signal graceful shutdown."""
        self.running = False

    def _recover_pending(self):
        """
        On startup, re-process messages that were delivered but never ACK'd.
        Uses special ID "0" in XREADGROUP to get pending entries.
        """
        while self.running:
            # Reading with id="0" returns pending (unacknowledged) entries
            results = self.r.xreadgroup(
                self.config.group,
                self.config.consumer_name,
                {self.config.stream: "0"},
                count=self.config.batch_size
            )

            if not results or not results[0][1]:
                break  # No more pending messages

            entries = results[0][1]
            for entry_id, fields in entries:
                self._process_entry(entry_id, fields)

    def _process_loop(self):
        """Main processing loop — read new messages."""
        while self.running:
            try:
                # ">" means: deliver only new, never-delivered messages
                results = self.r.xreadgroup(
                    self.config.group,
                    self.config.consumer_name,
                    {self.config.stream: ">"},
                    count=self.config.batch_size,
                    block=self.config.block_ms
                )

                if not results:
                    # Timeout — also check for idle messages to claim
                    self._claim_idle_messages()
                    continue

                entries = results[0][1]
                for entry_id, fields in entries:
                    self._process_entry(entry_id, fields)

            except redis.ConnectionError:
                time.sleep(1)  # Backoff on connection failure

    def _process_entry(self, entry_id: str, fields: dict):
        """Process a single entry with retry tracking."""
        retry_count = self._get_retry_count(entry_id)

        if retry_count >= self.config.max_retries:
            self._send_to_dlq(entry_id, fields, "max_retries_exceeded")
            self.r.xack(self.config.stream, self.config.group, entry_id)
            return

        try:
            success = self.handler(entry_id, fields)
            if success:
                self.r.xack(self.config.stream, self.config.group, entry_id)
                self._clear_retry_count(entry_id)
            else:
                self._increment_retry_count(entry_id)
        except Exception as e:
            self._increment_retry_count(entry_id)
            # Don't ACK — message stays in PEL for retry

    def _claim_idle_messages(self):
        """
        Claim messages stuck in other consumers' PELs.
        XCLAIM transfers ownership of idle messages to this consumer.
        """
        # XAUTOCLAIM stream group consumer min-idle-time start [COUNT count]
        try:
            result = self.r.xautoclaim(
                self.config.stream,
                self.config.group,
                self.config.consumer_name,
                min_idle_time=self.config.claim_idle_ms,
                start_id="0-0",
                count=self.config.batch_size
            )
            # result: (next_start_id, [(id, fields), ...], [deleted_ids])
            if result and result[1]:
                for entry_id, fields in result[1]:
                    self._process_entry(entry_id, fields)
        except redis.ResponseError:
            pass  # XAUTOCLAIM not available on older Redis

    def _get_retry_count(self, entry_id: str) -> int:
        key = f"retry:{self.config.stream}:{entry_id}"
        count = self.r.get(key)
        return int(count) if count else 0

    def _increment_retry_count(self, entry_id: str):
        key = f"retry:{self.config.stream}:{entry_id}"
        self.r.incr(key)
        self.r.expire(key, 3600)  # Cleanup after 1 hour

    def _clear_retry_count(self, entry_id: str):
        key = f"retry:{self.config.stream}:{entry_id}"
        self.r.delete(key)

    def _send_to_dlq(self, entry_id: str, fields: dict, reason: str):
        """Move poison messages to a dead letter stream."""
        dlq_stream = f"{self.config.stream}:dlq"
        self.r.xadd(dlq_stream, {
            "original_id": entry_id,
            "original_stream": self.config.stream,
            "group": self.config.group,
            "reason": reason,
            "failed_at": str(int(time.time() * 1000)),
            **fields
        }, maxlen=10_000, approximate=True)


# Usage
r = redis.Redis(decode_responses=True)

def process_order(entry_id: str, fields: dict) -> bool:
    """Business logic — return True on success, False to retry."""
    order_id = fields.get("order_id")
    event_type = fields.get("event_type")
    print(f"Processing {event_type} for {order_id} (entry: {entry_id})")
    # ... actual processing ...
    return True

config = ConsumerConfig(
    stream="orders:events",
    group="fulfillment-service",
    consumer_name="worker-1",
    batch_size=10,
    block_ms=5000,
    max_retries=3,
    claim_idle_ms=30_000
)

worker = ConsumerGroupWorker(r, config, handler=process_order)

# Graceful shutdown on SIGTERM
signal.signal(signal.SIGTERM, lambda *_: worker.stop())

# Start processing (blocking)
worker.start()
```

---

## 4. Exactly-Once Processing with Idempotency

Streams guarantee **at-least-once** delivery. For **exactly-once** semantics, combine with idempotency keys:

```python
class IdempotentConsumer:
    """
    Ensures each message is processed exactly once using
    a deduplication window tracked in Redis.
    """

    def __init__(self, r: redis.Redis, dedup_ttl: int = 86400):
        self.r = r
        self.dedup_ttl = dedup_ttl

    def process_if_new(self, entry_id: str, fields: dict,
                       handler: Callable[[dict], bool]) -> bool:
        """
        Atomic check-and-process using SET NX:
        - If entry_id not seen → process and mark as done
        - If entry_id already seen → skip (already processed)
        """
        dedup_key = f"processed:{entry_id}"

        # Atomic: set only if not exists, with TTL
        is_new = self.r.set(dedup_key, "1", nx=True, ex=self.dedup_ttl)

        if not is_new:
            return True  # Already processed — ACK it

        try:
            success = handler(fields)
            if not success:
                # Processing failed — remove dedup key so we can retry
                self.r.delete(dedup_key)
                return False
            return True
        except Exception:
            self.r.delete(dedup_key)
            raise

    def process_with_transaction(self, entry_id: str, fields: dict,
                                 handler: Callable[[dict, redis.Redis], None]):
        """
        For handlers that write to Redis — use a pipeline to atomically
        mark processed AND write results.
        """
        dedup_key = f"processed:{entry_id}"

        # Check first (non-atomic but fast path for duplicates)
        if self.r.exists(dedup_key):
            return True

        # Atomic processing + dedup marking
        pipe = self.r.pipeline(transaction=True)
        pipe.watch(dedup_key)

        if pipe.get(dedup_key):
            pipe.unwatch()
            return True  # Race condition — another worker got it

        pipe.multi()
        handler(fields, pipe)  # Handler adds its commands to the pipeline
        pipe.set(dedup_key, "1", ex=self.dedup_ttl)

        try:
            pipe.execute()
            return True
        except redis.WatchError:
            return True  # Another worker processed it — that's fine
```

---

## 5. Multi-Stream Fan-In Aggregation

Process events from multiple streams in a single consumer:

```python
class MultiStreamConsumer:
    """
    Consume from multiple streams simultaneously.
    Useful for aggregating events from different services.
    """

    def __init__(self, r: redis.Redis, streams: list[str], group: str,
                 consumer: str):
        self.r = r
        self.streams = streams
        self.group = group
        self.consumer = consumer
        self._ensure_groups()

    def _ensure_groups(self):
        for stream in self.streams:
            try:
                self.r.xgroup_create(stream, self.group, id="0", mkstream=True)
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

    def read_all(self, count: int = 10, block_ms: int = 5000) -> dict:
        """
        Read from all streams simultaneously.
        Returns: {stream_name: [(entry_id, fields), ...]}
        """
        # Build stream dict: {stream: ">"} for new messages
        stream_ids = {stream: ">" for stream in self.streams}

        results = self.r.xreadgroup(
            self.group,
            self.consumer,
            stream_ids,
            count=count,
            block=block_ms
        )

        if not results:
            return {}

        # Parse results into per-stream entries
        parsed = {}
        for stream_name, entries in results:
            parsed[stream_name] = entries
        return parsed

    def ack(self, stream: str, entry_id: str):
        self.r.xack(stream, self.group, entry_id)


# Aggregate events from multiple microservices
consumer = MultiStreamConsumer(
    r,
    streams=["user:events", "order:events", "payment:events"],
    group="analytics-pipeline",
    consumer="aggregator-1"
)

while True:
    events = consumer.read_all(count=50, block_ms=2000)
    for stream, entries in events.items():
        for entry_id, fields in entries:
            # Route based on source stream
            print(f"[{stream}] {entry_id}: {fields}")
            consumer.ack(stream, entry_id)
```

---

## 6. Delayed/Scheduled Message Queue

Redis Streams don't natively support delayed messages. Use a Sorted Set as a staging area:

```python
class DelayedQueue:
    """
    Delayed message queue using ZSET (schedule) + Stream (ready).

    Flow:
    1. Producer adds to ZSET with score = delivery_timestamp
    2. Scheduler loop moves due messages from ZSET → Stream
    3. Consumers read from Stream via consumer groups

    ┌──────────┐   schedule   ┌──────────────┐   transfer   ┌────────────┐
    │ Producer ├──────────────► ZSET (delay) ├──────────────► Stream     │
    └──────────┘              └──────────────┘              └─────┬──────┘
                                                                  │
                                                           ┌──────┴──────┐
                                                           │  Consumers  │
                                                           └─────────────┘
    """

    def __init__(self, r: redis.Redis, name: str):
        self.r = r
        self.schedule_key = f"delayed:{name}:schedule"
        self.stream_key = f"delayed:{name}:stream"
        self.lock_key = f"delayed:{name}:scheduler_lock"

    def schedule(self, message: dict, delay_seconds: float) -> str:
        """Schedule a message for future delivery."""
        deliver_at = time.time() + delay_seconds
        # Encode message as JSON string for ZSET storage
        import json
        msg_id = f"{int(time.time()*1000)}-{id(message)}"
        payload = json.dumps({"id": msg_id, **message})
        self.r.zadd(self.schedule_key, {payload: deliver_at})
        return msg_id

    def schedule_at(self, message: dict, timestamp: float) -> str:
        """Schedule a message for delivery at a specific Unix timestamp."""
        import json
        msg_id = f"{int(timestamp*1000)}-{id(message)}"
        payload = json.dumps({"id": msg_id, **message})
        self.r.zadd(self.schedule_key, {payload: timestamp})
        return msg_id

    def run_scheduler(self, batch_size: int = 100, poll_interval: float = 0.1):
        """
        Scheduler loop — moves due messages to the stream.
        Only one instance should run (uses distributed lock).
        """
        while True:
            # Acquire short-lived lock to prevent duplicate transfers
            acquired = self.r.set(
                self.lock_key, "1", nx=True, px=int(poll_interval * 5000)
            )
            if not acquired:
                time.sleep(poll_interval)
                continue

            now = time.time()
            # Atomic: get and remove due messages
            lua_script = """
            local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
            if #due > 0 then
                redis.call('ZREM', KEYS[1], unpack(due))
            end
            return due
            """
            due_messages = self.r.execute_command(
                "EVAL", lua_script, 1,
                self.schedule_key, str(now), str(batch_size)
            )

            if due_messages:
                import json
                pipe = self.r.pipeline(transaction=False)
                for raw in due_messages:
                    msg = json.loads(raw)
                    pipe.xadd(self.stream_key, msg)
                pipe.execute()

            time.sleep(poll_interval)

    def pending_count(self) -> int:
        """Number of messages waiting to be delivered."""
        return self.r.zcard(self.schedule_key)

    def due_count(self) -> int:
        """Number of messages past their delivery time."""
        return self.r.zcount(self.schedule_key, "-inf", str(time.time()))


# Usage
delayed = DelayedQueue(r, "email-notifications")

# Schedule a reminder email in 30 minutes
delayed.schedule(
    {"type": "reminder", "user_id": "usr_123", "template": "cart_abandoned"},
    delay_seconds=1800
)

# Schedule a report for tomorrow at 9 AM
import datetime
tomorrow_9am = datetime.datetime.now().replace(
    hour=9, minute=0, second=0
) + datetime.timedelta(days=1)
delayed.schedule_at(
    {"type": "report", "report_id": "daily_sales"},
    timestamp=tomorrow_9am.timestamp()
)
```

---

## 7. Priority Queue Pattern

Use multiple streams with weighted consumption:

```python
class PriorityQueue:
    """
    Priority queue using multiple streams (one per priority level).
    Higher priority streams are checked first and consume more messages per cycle.

    Priority levels:
    - critical: processed immediately, 50 msgs/batch
    - high: processed next, 20 msgs/batch
    - normal: processed last, 10 msgs/batch
    - low: processed only when others are empty, 5 msgs/batch
    """

    PRIORITIES = {
        "critical": {"stream_suffix": ":critical", "batch": 50, "order": 0},
        "high": {"stream_suffix": ":high", "batch": 20, "order": 1},
        "normal": {"stream_suffix": ":normal", "batch": 10, "order": 2},
        "low": {"stream_suffix": ":low", "batch": 5, "order": 3},
    }

    def __init__(self, r: redis.Redis, queue_name: str, group: str,
                 consumer: str):
        self.r = r
        self.queue_name = queue_name
        self.group = group
        self.consumer = consumer
        self._ensure_groups()

    def _stream_name(self, priority: str) -> str:
        return f"{self.queue_name}{self.PRIORITIES[priority]['stream_suffix']}"

    def _ensure_groups(self):
        for priority in self.PRIORITIES:
            stream = self._stream_name(priority)
            try:
                self.r.xgroup_create(stream, self.group, id="0", mkstream=True)
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

    def enqueue(self, message: dict, priority: str = "normal") -> str:
        """Add a message at the specified priority level."""
        if priority not in self.PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        stream = self._stream_name(priority)
        return self.r.xadd(stream, message)

    def dequeue(self, block_ms: int = 1000) -> Optional[tuple]:
        """
        Fetch the highest-priority available message.
        Returns: (stream, entry_id, fields) or None
        """
        # Check priorities in order: critical → high → normal → low
        sorted_priorities = sorted(
            self.PRIORITIES.items(), key=lambda x: x[1]["order"]
        )

        for priority, config in sorted_priorities:
            stream = self._stream_name(priority)
            results = self.r.xreadgroup(
                self.group,
                self.consumer,
                {stream: ">"},
                count=config["batch"],
                block=0  # Non-blocking for priority scan
            )

            if results and results[0][1]:
                entries = results[0][1]
                return [(stream, eid, fields) for eid, fields in entries]

        # No messages in any priority — block on all streams
        streams = {
            self._stream_name(p): ">" for p in self.PRIORITIES
        }
        results = self.r.xreadgroup(
            self.group, self.consumer, streams,
            count=1, block=block_ms
        )
        if results:
            stream_name, entries = results[0]
            return [(stream_name, eid, fields) for eid, fields in entries]
        return None

    def ack(self, stream: str, entry_id: str):
        self.r.xack(stream, self.group, entry_id)

    def queue_lengths(self) -> dict:
        """Get pending message count per priority."""
        lengths = {}
        for priority in self.PRIORITIES:
            stream = self._stream_name(priority)
            try:
                lengths[priority] = self.r.xlen(stream)
            except redis.ResponseError:
                lengths[priority] = 0
        return lengths


# Usage
pq = PriorityQueue(r, "tasks", group="workers", consumer="w1")

# Enqueue at different priorities
pq.enqueue({"job": "send_welcome_email", "user": "u1"}, priority="normal")
pq.enqueue({"job": "fraud_alert", "txn": "t99"}, priority="critical")
pq.enqueue({"job": "generate_report", "type": "weekly"}, priority="low")

# Consume — critical messages processed first
batch = pq.dequeue(block_ms=2000)
if batch:
    for stream, entry_id, fields in batch:
        print(f"[{stream}] Processing: {fields}")
        pq.ack(stream, entry_id)
```

---

## 8. Stream Monitoring & Observability

```python
class StreamMonitor:
    """Monitor stream health, consumer lag, and pending entries."""

    def __init__(self, r: redis.Redis):
        self.r = r

    def stream_info(self, stream: str) -> dict:
        """Get comprehensive stream info."""
        info = self.r.xinfo_stream(stream, full=True)
        return {
            "length": info.get("length", 0),
            "first_entry_id": info.get("first-entry", {}).get("id") if info.get("first-entry") else None,
            "last_entry_id": info.get("last-generated-id"),
            "max_deleted_entry_id": info.get("max-deleted-entry-id"),
            "recorded_first_entry_id": info.get("recorded-first-entry-id"),
            "groups_count": len(info.get("groups", [])),
        }

    def consumer_lag(self, stream: str, group: str) -> dict:
        """
        Calculate consumer group lag.
        Lag = stream length - messages delivered to this group
        """
        try:
            groups = self.r.xinfo_groups(stream)
        except redis.ResponseError:
            return {}

        for g in groups:
            if g["name"] == group:
                stream_len = self.r.xlen(stream)
                # 'lag' field available in Redis 7.0+
                lag = g.get("lag")
                if lag is None:
                    # Approximate: stream length minus last-delivered
                    last_delivered = g.get("last-delivered-id", "0-0")
                    delivered_entries = self.r.xrange(
                        stream, min="-", max=last_delivered
                    )
                    lag = stream_len - len(delivered_entries)

                return {
                    "group": group,
                    "consumers": g["consumers"],
                    "pending": g["pending"],
                    "lag": lag,
                    "last_delivered_id": g.get("last-delivered-id"),
                }
        return {}

    def pending_summary(self, stream: str, group: str) -> dict:
        """Get summary of pending (unacknowledged) messages."""
        # XPENDING stream group
        pending = self.r.xpending(stream, group)
        if not pending or pending["pending"] == 0:
            return {"total_pending": 0, "consumers": {}}

        return {
            "total_pending": pending["pending"],
            "min_id": pending["min"],
            "max_id": pending["max"],
            "consumers": pending.get("consumers", [])
        }

    def stale_consumers(self, stream: str, group: str,
                        idle_threshold_ms: int = 300_000) -> list:
        """Find consumers idle for too long (possibly crashed)."""
        consumers = self.r.xinfo_consumers(stream, group)
        stale = []
        for c in consumers:
            if c["idle"] > idle_threshold_ms:
                stale.append({
                    "name": c["name"],
                    "idle_ms": c["idle"],
                    "pending": c["pending"]
                })
        return stale

    def delete_stale_consumers(self, stream: str, group: str,
                               idle_threshold_ms: int = 600_000):
        """Remove consumers that have been idle too long and have no pending."""
        consumers = self.r.xinfo_consumers(stream, group)
        removed = []
        for c in consumers:
            if c["idle"] > idle_threshold_ms and c["pending"] == 0:
                self.r.xgroup_delconsumer(stream, group, c["name"])
                removed.append(c["name"])
        return removed


# Health check endpoint
monitor = StreamMonitor(r)

def health_check():
    return {
        "stream": monitor.stream_info("orders:events"),
        "consumer_lag": monitor.consumer_lag("orders:events", "fulfillment-service"),
        "pending": monitor.pending_summary("orders:events", "fulfillment-service"),
        "stale_consumers": monitor.stale_consumers("orders:events", "fulfillment-service"),
    }
```

---

## 9. Backpressure & Flow Control

```python
class BackpressureProducer:
    """
    Producer with backpressure awareness.
    Slows down or rejects writes when consumers can't keep up.
    """

    def __init__(self, r: redis.Redis, stream: str, group: str,
                 max_lag: int = 10_000,
                 max_pending: int = 5_000):
        self.r = r
        self.stream = stream
        self.group = group
        self.max_lag = max_lag
        self.max_pending = max_pending

    def check_pressure(self) -> dict:
        """Assess current backpressure state."""
        stream_len = self.r.xlen(self.stream)
        pending = self.r.xpending(self.stream, self.group)
        pending_count = pending["pending"] if pending else 0

        # Estimate lag
        groups = self.r.xinfo_groups(self.stream)
        lag = 0
        for g in groups:
            if g["name"] == self.group:
                lag = g.get("lag", stream_len)
                break

        pressure = max(lag / self.max_lag, pending_count / self.max_pending)
        return {
            "lag": lag,
            "pending": pending_count,
            "stream_length": stream_len,
            "pressure": min(pressure, 1.0),  # 0.0 = no pressure, 1.0 = max
            "accepting": pressure < 0.9
        }

    def publish_with_backpressure(self, data: dict) -> Optional[str]:
        """
        Publish if system has capacity.
        Returns entry_id on success, None if backpressure triggered.
        """
        state = self.check_pressure()

        if not state["accepting"]:
            return None  # Caller should back off or queue locally

        # Add with MAXLEN to prevent unbounded growth
        return self.r.xadd(
            self.stream, data,
            maxlen=self.max_lag * 2,
            approximate=True
        )

    def publish_with_adaptive_rate(self, data: dict,
                                    base_delay: float = 0.001) -> str:
        """
        Always publishes but introduces delay proportional to pressure.
        Higher pressure = longer delay between publishes.
        """
        state = self.check_pressure()
        pressure = state["pressure"]

        if pressure > 0.5:
            # Exponential backoff based on pressure
            delay = base_delay * (2 ** (pressure * 5))
            time.sleep(min(delay, 5.0))  # Cap at 5 seconds

        return self.r.xadd(self.stream, data, maxlen=self.max_lag * 3,
                           approximate=True)
```

---

## 10. Stream-Based Event Sourcing

```python
class EventStore:
    """
    Event sourcing with Redis Streams.
    Each aggregate has its own stream of events.
    """

    def __init__(self, r: redis.Redis, namespace: str = "events"):
        self.r = r
        self.namespace = namespace

    def _stream_key(self, aggregate_type: str, aggregate_id: str) -> str:
        return f"{self.namespace}:{aggregate_type}:{aggregate_id}"

    def append_event(self, aggregate_type: str, aggregate_id: str,
                     event_type: str, event_data: dict,
                     expected_version: int = None) -> str:
        """
        Append an event to an aggregate's stream.
        Optional optimistic concurrency via expected_version.
        """
        stream = self._stream_key(aggregate_type, aggregate_id)

        if expected_version is not None:
            # Optimistic concurrency check
            current_len = self.r.xlen(stream)
            if current_len != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, "
                    f"but stream has {current_len} entries"
                )

        import json
        entry = {
            "event_type": event_type,
            "data": json.dumps(event_data),
            "timestamp": str(int(time.time() * 1000)),
            "version": str((expected_version or 0) + 1)
        }

        return self.r.xadd(stream, entry)

    def get_events(self, aggregate_type: str, aggregate_id: str,
                   from_version: int = 0) -> list:
        """Load all events for an aggregate (for state reconstruction)."""
        stream = self._stream_key(aggregate_type, aggregate_id)
        entries = self.r.xrange(stream, min="-", max="+")

        import json
        events = []
        for entry_id, fields in entries:
            version = int(fields.get("version", 0))
            if version > from_version:
                events.append({
                    "entry_id": entry_id,
                    "event_type": fields["event_type"],
                    "data": json.loads(fields["data"]),
                    "timestamp": int(fields["timestamp"]),
                    "version": version
                })
        return events

    def get_current_version(self, aggregate_type: str,
                            aggregate_id: str) -> int:
        """Get the current version (event count) of an aggregate."""
        stream = self._stream_key(aggregate_type, aggregate_id)
        return self.r.xlen(stream)

    def project_state(self, aggregate_type: str, aggregate_id: str,
                      projector: Callable[[dict, dict], dict]) -> dict:
        """
        Rebuild current state by replaying all events through a projector.
        projector(current_state, event) -> new_state
        """
        events = self.get_events(aggregate_type, aggregate_id)
        state = {}
        for event in events:
            state = projector(state, event)
        return state


class ConcurrencyError(Exception):
    pass


# Usage — Order aggregate
event_store = EventStore(r)

# Append events
event_store.append_event("order", "ord_001", "OrderCreated", {
    "user_id": "usr_123",
    "items": [{"sku": "WIDGET-1", "qty": 2, "price": 9.99}]
}, expected_version=0)

event_store.append_event("order", "ord_001", "PaymentReceived", {
    "amount": 19.98,
    "method": "card",
    "transaction_id": "txn_abc"
}, expected_version=1)

event_store.append_event("order", "ord_001", "OrderShipped", {
    "tracking": "1Z999AA10123456784",
    "carrier": "ups"
}, expected_version=2)

# Rebuild state
def order_projector(state: dict, event: dict) -> dict:
    et = event["event_type"]
    data = event["data"]

    if et == "OrderCreated":
        return {"status": "created", "items": data["items"],
                "user_id": data["user_id"]}
    elif et == "PaymentReceived":
        return {**state, "status": "paid", "payment": data}
    elif et == "OrderShipped":
        return {**state, "status": "shipped", "shipping": data}
    return state

current_state = event_store.project_state("order", "ord_001", order_projector)
# {'status': 'shipped', 'items': [...], 'user_id': 'usr_123',
#  'payment': {...}, 'shipping': {...}}
```

---

## 11. FIFO Task Queue with Reliable Delivery

A simpler alternative to consumer groups when you need strict FIFO and single-consumer semantics:

```python
class ReliableFIFOQueue:
    """
    Reliable FIFO queue using BRPOPLPUSH (List) or Stream with single consumer.

    Two implementations:
    1. List-based: BRPOPLPUSH for atomic move from queue → processing list
    2. Stream-based: Consumer group with single consumer

    List-based is simpler but lacks message history.
    Stream-based retains history and supports replay.
    """

    def __init__(self, r: redis.Redis, name: str):
        self.r = r
        self.queue_key = f"queue:{name}"
        self.processing_key = f"queue:{name}:processing"
        self.dlq_key = f"queue:{name}:dlq"

    def enqueue(self, message: str):
        """Add message to the tail of the queue."""
        self.r.lpush(self.queue_key, message)

    def dequeue(self, timeout: int = 5) -> Optional[str]:
        """
        Atomically pop from queue and push to processing list.
        If consumer crashes, message remains in processing list for recovery.
        """
        # BRPOPLPUSH source destination timeout
        # Atomic: removes from queue, adds to processing
        result = self.r.brpoplpush(
            self.queue_key, self.processing_key, timeout=timeout
        )
        return result

    def ack(self, message: str):
        """Mark message as processed — remove from processing list."""
        self.r.lrem(self.processing_key, 1, message)

    def nack(self, message: str, requeue: bool = True):
        """Reject message — requeue or send to DLQ."""
        self.r.lrem(self.processing_key, 1, message)
        if requeue:
            self.r.rpush(self.queue_key, message)
        else:
            self.r.lpush(self.dlq_key, message)

    def recover_stale(self, max_age_seconds: int = 60):
        """
        Recover messages stuck in processing (consumer crashed).
        Move them back to the main queue.
        Note: List-based queues don't track time per message,
        so this recovers ALL processing messages.
        """
        while True:
            msg = self.r.rpoplpush(self.processing_key, self.queue_key)
            if msg is None:
                break

    def length(self) -> dict:
        return {
            "queued": self.r.llen(self.queue_key),
            "processing": self.r.llen(self.processing_key),
            "dead_letter": self.r.llen(self.dlq_key),
        }
```

---

## 12. Stream Trimming & Retention Strategies

```python
class StreamRetentionManager:
    """
    Manage stream size and retention policies.

    Strategies:
    1. MAXLEN: Keep at most N entries (cap-based)
    2. MINID: Remove entries older than a timestamp (time-based)
    3. Hybrid: Both — whichever triggers first

    Always use approximate (~) trimming in production.
    Exact trimming is O(N) and blocks Redis.
    Approximate is O(1) — trims in chunks of ~100 entries.
    """

    def __init__(self, r: redis.Redis):
        self.r = r

    def trim_by_count(self, stream: str, maxlen: int):
        """Keep only the latest `maxlen` entries."""
        self.r.xtrim(stream, maxlen=maxlen, approximate=True)

    def trim_by_age(self, stream: str, max_age_seconds: int):
        """Remove entries older than max_age_seconds."""
        cutoff_ms = int((time.time() - max_age_seconds) * 1000)
        min_id = f"{cutoff_ms}-0"
        self.r.xtrim(stream, minid=min_id, approximate=True)

    def trim_with_consumer_safety(self, stream: str, group: str,
                                   maxlen: int = None,
                                   max_age_seconds: int = None):
        """
        Trim safely — never remove entries that consumers haven't processed.
        Check the last-delivered-id of the group before trimming.
        """
        groups = self.r.xinfo_groups(stream)
        min_delivered_id = None

        for g in groups:
            if g["name"] == group:
                last_id = g.get("last-delivered-id", "0-0")
                if min_delivered_id is None or last_id < min_delivered_id:
                    min_delivered_id = last_id

        if min_delivered_id and min_delivered_id != "0-0":
            # Only trim entries BEFORE the oldest unprocessed
            # Parse the ID to get its timestamp
            ts_part = min_delivered_id.split("-")[0]
            safe_cutoff = f"{int(ts_part) - 1}-0"
            self.r.xtrim(stream, minid=safe_cutoff, approximate=True)

    def archive_and_trim(self, stream: str, archive_stream: str,
                         max_age_seconds: int, batch_size: int = 1000):
        """
        Move old entries to an archive stream before trimming.
        Preserves history without unbounded growth on the hot stream.
        """
        cutoff_ms = int((time.time() - max_age_seconds) * 1000)
        cutoff_id = f"{cutoff_ms}-0"

        # Read old entries
        old_entries = self.r.xrange(stream, min="-", max=cutoff_id,
                                    count=batch_size)

        if old_entries:
            # Write to archive
            pipe = self.r.pipeline(transaction=False)
            for entry_id, fields in old_entries:
                fields["_original_id"] = entry_id
                fields["_archived_at"] = str(int(time.time() * 1000))
                pipe.xadd(archive_stream, fields)
            pipe.execute()

            # Trim the original stream
            self.r.xtrim(stream, minid=cutoff_id, approximate=True)

        return len(old_entries)


# Cron job: run every 5 minutes
retention = StreamRetentionManager(r)

# Keep last 7 days OR last 1M entries (whichever is smaller)
retention.trim_by_age("orders:events", max_age_seconds=7 * 86400)
retention.trim_by_count("orders:events", maxlen=1_000_000)

# Archive old analytics events before deletion
archived = retention.archive_and_trim(
    "analytics:events",
    "analytics:events:archive",
    max_age_seconds=24 * 3600,
    batch_size=5000
)
```

---

## 13. Performance Characteristics & Operations Reference

| Operation | Command | Complexity | Notes |
|-----------|---------|-----------|-------|
| Add entry | XADD | O(1) | O(N) if trimming by exact MAXLEN |
| Add + trim (approx) | XADD MAXLEN ~ | O(1) amortized | Always use approximate |
| Read range | XRANGE | O(log N + M) | M = entries returned |
| Read new (blocking) | XREAD BLOCK | O(1) per entry | Efficient multiplexed wait |
| Consumer group read | XREADGROUP | O(1) per entry | Adds to PEL |
| Acknowledge | XACK | O(1) | Removes from PEL |
| Stream length | XLEN | O(1) | Cached counter |
| Trim by count | XTRIM MAXLEN ~ | O(1) amortized | Approximate mode |
| Trim by ID | XTRIM MINID ~ | O(1) amortized | Redis 6.2+ |
| Claim idle | XAUTOCLAIM | O(N) | N = scanned pending entries |
| Pending summary | XPENDING | O(1) | Summary form |
| Pending detail | XPENDING ... count | O(N) | N = count |
| Delete entries | XDEL | O(1) per entry | Marks deleted, doesn't reclaim |
| Stream info | XINFO STREAM | O(1) | Use FULL for details |

### Memory & Throughput Guidelines

```
Stream entry overhead: ~100 bytes + field data
  - 1M entries with 200-byte payloads ≈ 300 MB

Throughput (single Redis instance):
  - XADD: 200K-500K ops/sec
  - XREADGROUP: 150K-300K ops/sec (depends on batch size)
  - Larger batches (COUNT 100) = higher throughput per op

Consumer group limits:
  - Max consumers per group: unlimited (practical: <100)
  - Max pending entries: limited by memory only
  - Max groups per stream: unlimited (practical: <20)
```

### Production Configuration

```
# redis.conf recommendations for heavy stream workloads

# Listpack encoding threshold (entries per node)
stream-node-max-bytes 4096      # Max bytes per listpack node
stream-node-max-entries 100     # Max entries per listpack node

# Background memory defrag (streams can fragment)
activedefrag yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10

# Persistence: Streams are AOF-friendly
appendonly yes
appendfsync everysec            # Good balance for queues
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

---

## 14. Streams vs. Other Queue Patterns

| Feature | Redis Streams | Redis Lists (BRPOPLPUSH) | Pub/Sub | Kafka |
|---------|--------------|--------------------------|---------|-------|
| Persistence | Yes (AOF/RDB) | Yes | No | Yes |
| Consumer groups | Yes | No (manual) | No | Yes |
| Message replay | Yes | No (consumed = gone) | No | Yes |
| Acknowledgment | XACK | Manual | N/A | Offset commit |
| Ordering | Per-stream FIFO | FIFO | No guarantee | Per-partition |
| Backpressure | MAXLEN/MINID | LTRIM | Dropped msgs | Consumer lag |
| Dead letter | Manual (code) | Manual | N/A | Built-in |
| Throughput/node | 200K-500K msg/s | 100K-300K msg/s | 1M+ msg/s | 200K-1M msg/s |
| Message history | Retained until trim | Consumed = removed | None | Retained (configurable) |
| Max stream size | RAM-bound | RAM-bound | N/A | Disk-bound |
| Best for | Moderate queues, event sourcing | Simple task queues | Real-time broadcast | High-volume, durable |

**Choose Streams when**: You need consumer groups, message history, and moderate throughput within a single Redis instance. For >1M msgs/sec or multi-GB retention, graduate to Kafka/Pulsar.
