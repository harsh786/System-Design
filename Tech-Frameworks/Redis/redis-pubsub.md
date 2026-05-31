# Redis Pub/Sub — Deep Dive with Python Examples

## Table of Contents
1. [Pub/Sub Architecture Internals](#1-pubsub-architecture-internals)
2. [Basic Publish and Subscribe](#2-basic-publish-and-subscribe)
3. [Pattern-Based Subscriptions](#3-pattern-based-subscriptions)
4. [Sharded Pub/Sub (Redis 7+)](#4-sharded-pubsub-redis-7)
5. [Multi-Channel Event Router](#5-multi-channel-event-router)
6. [Reliable Pub/Sub with Acknowledgment Layer](#6-reliable-pubsub-with-acknowledgment-layer)
7. [WebSocket Bridge Pattern](#7-websocket-bridge-pattern)
8. [Service Discovery and Heartbeats](#8-service-discovery-and-heartbeats)
9. [Distributed Cache Invalidation](#9-distributed-cache-invalidation)
10. [Chat System with Presence](#10-chat-system-with-presence)
11. [Pub/Sub Monitoring and Diagnostics](#11-pubsub-monitoring-and-diagnostics)
12. [Backpressure and Slow Subscriber Handling](#12-backpressure-and-slow-subscriber-handling)
13. [Pub/Sub vs Streams Decision Matrix](#13-pubsub-vs-streams-decision-matrix)
14. [Production Patterns and Anti-Patterns](#14-production-patterns-and-anti-patterns)

---

## 1. Pub/Sub Architecture Internals

### How Redis Pub/Sub Works Under the Hood

Redis Pub/Sub is a **fire-and-forget** broadcast system. When a publisher sends a message to a channel, Redis delivers it immediately to all current subscribers. If no subscribers exist, the message is discarded — there is no persistence, no replay, no acknowledgment at the protocol level.

**Key Internal Structures:**

```
┌─────────────────────────────────────────────────────────┐
│                   Redis Server                          │
│                                                         │
│  pubsub_channels (dict):                               │
│    "orders:created"  → [client1, client2, client5]     │
│    "orders:shipped"  → [client2, client3]              │
│    "users:login"     → [client4]                       │
│                                                         │
│  pubsub_patterns (list):                               │
│    "orders:*"  → [client6, client7]                    │
│    "users:*"   → [client8]                             │
│                                                         │
│  On PUBLISH "orders:created" msg:                      │
│    1. Iterate pubsub_channels["orders:created"]        │
│    2. Iterate pubsub_patterns, match "orders:*"        │
│    3. Send msg to each matched client                  │
│    4. Return count of recipients                       │
└─────────────────────────────────────────────────────────┘
```

**Memory Model:**
- `pubsub_channels`: A hash table mapping channel names → linked list of subscribed clients
- `pubsub_patterns`: A linked list of (pattern, client) pairs iterated on every PUBLISH
- No message buffering — messages exist only during delivery
- Client output buffer holds messages until the TCP socket drains

**Complexity:**
| Operation | Time Complexity |
|-----------|----------------|
| SUBSCRIBE | O(1) per channel |
| UNSUBSCRIBE | O(1) per channel |
| PUBLISH | O(N+M) where N = channel subscribers, M = pattern count |
| PSUBSCRIBE | O(1) to add pattern |

**Critical Constraint:** Pattern subscriptions scale linearly with PUBLISH — every PUBLISH iterates *all* registered patterns. With 10,000 patterns, every single publish checks all 10,000.

---

## 2. Basic Publish and Subscribe

```python
import redis
import json
import threading
import time
from dataclasses import dataclass, asdict
from typing import Callable, Any
from datetime import datetime, timezone


@dataclass
class Event:
    type: str
    payload: dict
    timestamp: str
    source: str

    def serialize(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def deserialize(cls, data: str) -> "Event":
        return cls(**json.loads(data))


class Publisher:
    """
    Publishes events to Redis channels.

    Redis PUBLISH returns the number of subscribers who received the message.
    A return of 0 means the message was lost — no one was listening.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", source: str = "unknown"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.source = source

    def publish(self, channel: str, event_type: str, payload: dict) -> int:
        event = Event(
            type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=self.source,
        )
        recipients = self.r.publish(channel, event.serialize())
        return recipients

    def publish_raw(self, channel: str, message: str) -> int:
        return self.r.publish(channel, message)


class Subscriber:
    """
    Subscribes to Redis channels and dispatches messages to handlers.

    Important: A subscribed Redis connection is in "subscriber mode" —
    it cannot execute any commands other than SUBSCRIBE, UNSUBSCRIBE,
    PSUBSCRIBE, PUNSUBSCRIBE, PING, and RESET.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self.handlers: dict[str, list[Callable]] = {}
        self._running = False
        self._thread = None

    def subscribe(self, channel: str, handler: Callable[[Event], None]):
        if channel not in self.handlers:
            self.handlers[channel] = []
            self.pubsub.subscribe(channel)
        self.handlers[channel].append(handler)

    def _dispatch(self, message: dict):
        channel = message["channel"]
        try:
            event = Event.deserialize(message["data"])
        except (json.JSONDecodeError, TypeError, KeyError):
            return

        for handler in self.handlers.get(channel, []):
            try:
                handler(event)
            except Exception as e:
                print(f"Handler error on {channel}: {e}")

    def start(self):
        """Start listening in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        while self._running:
            message = self.pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                self._dispatch(message)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.pubsub.unsubscribe()
        self.pubsub.close()


# Usage
def on_order_created(event: Event):
    print(f"Order {event.payload['order_id']} created by {event.source}")

pub = Publisher(source="order-service")
sub = Subscriber()
sub.subscribe("orders:created", on_order_created)
sub.start()

pub.publish("orders:created", "ORDER_CREATED", {"order_id": "ORD-1234", "total": 99.99})
```

---

## 3. Pattern-Based Subscriptions

```python
class PatternSubscriber:
    """
    PSUBSCRIBE allows glob-style pattern matching on channel names.

    Supported patterns:
      - `*`   matches any sequence of characters
      - `?`   matches exactly one character
      - [ae]  matches 'a' or 'e'
      - [^a]  matches any character except 'a'
      - [a-z] matches range

    Pattern matching is performed on every PUBLISH. With many patterns
    registered, this becomes the bottleneck — O(M) per publish where M
    is the total number of patterns across all clients.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self.pattern_handlers: dict[str, Callable] = {}
        self._running = False

    def psubscribe(self, pattern: str, handler: Callable[[str, str, Event], None]):
        """
        Handler receives (pattern, channel, event).
        The channel is the actual channel the message was published to.
        The pattern is what matched.
        """
        self.pattern_handlers[pattern] = handler
        self.pubsub.psubscribe(pattern)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        while self._running:
            message = self.pubsub.get_message(timeout=1.0)
            if message and message["type"] == "pmessage":
                pattern = message["pattern"]
                channel = message["channel"]
                try:
                    event = Event.deserialize(message["data"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue
                handler = self.pattern_handlers.get(pattern)
                if handler:
                    try:
                        handler(pattern, channel, event)
                    except Exception as e:
                        print(f"Pattern handler error: {e}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.pubsub.punsubscribe()
        self.pubsub.close()


# Usage — catch all order lifecycle events
def on_order_event(pattern: str, channel: str, event: Event):
    # channel might be "orders:created", "orders:shipped", "orders:cancelled"
    action = channel.split(":")[1]
    print(f"Order lifecycle: {action} — {event.payload}")

psub = PatternSubscriber()
psub.psubscribe("orders:*", on_order_event)
psub.start()

# These all reach the pattern subscriber
pub = Publisher(source="order-service")
pub.publish("orders:created", "ORDER_CREATED", {"order_id": "1"})
pub.publish("orders:shipped", "ORDER_SHIPPED", {"order_id": "1"})
pub.publish("orders:cancelled", "ORDER_CANCELLED", {"order_id": "2"})
```

**Pattern Subscription Pitfalls:**
- A client subscribed to both `orders:*` AND `orders:created` will receive the message **twice** — once for the pattern match, once for the exact channel match
- Patterns are checked linearly — 1000 patterns means 1000 checks per PUBLISH
- No way to filter server-side beyond the glob pattern

---

## 4. Sharded Pub/Sub (Redis 7+)

```python
class ShardedPubSub:
    """
    Redis 7.0 introduced Sharded Pub/Sub (SSUBSCRIBE/SPUBLISH) for
    Redis Cluster deployments.

    Traditional Pub/Sub in a cluster broadcasts PUBLISH to ALL nodes,
    regardless of which node owns the channel. This means every node
    processes every publish, O(N) cluster-wide per message.

    Sharded Pub/Sub maps channels to specific hash slots, so messages
    only route to the node owning that slot. This dramatically reduces
    cross-node traffic.

    Restrictions:
    - No pattern subscriptions (no SPSUBSCRIBE)
    - Channel must map to a hash slot (same rules as keys)
    - Only works in Cluster mode
    """

    def __init__(self, cluster_url: str = "redis://localhost:7000"):
        # In a real cluster setup, use RedisCluster
        # This demonstrates the API pattern
        self.r = redis.from_url(cluster_url, decode_responses=True)

    def spublish(self, channel: str, message: str) -> int:
        """
        SPUBLISH routes only to the node owning the channel's hash slot.
        Returns number of subscribers on that shard.
        """
        return self.r.execute_command("SPUBLISH", channel, message)

    def ssubscribe(self, channel: str, handler: Callable):
        """
        SSUBSCRIBE connects to the specific shard owning this channel.
        If the slot migrates (resharding), the client must re-subscribe.
        """
        pubsub = self.r.pubsub()
        pubsub.execute_command("SSUBSCRIBE", channel)
        # In practice, use redis-py's built-in ssubscribe once available
        return pubsub


# Traditional vs Sharded comparison:
#
# Traditional PUBLISH "orders:created" in 6-node cluster:
#   → Broadcast to ALL 6 nodes
#   → Each node checks local subscribers
#   → O(6) network messages per publish
#
# Sharded SPUBLISH "orders:created":
#   → Route to node owning slot(crc16("orders:created") % 16384)
#   → Only that node checks subscribers
#   → O(1) network messages per publish
#
# Use Sharded Pub/Sub when:
#   - High message throughput in Cluster mode
#   - You don't need pattern subscriptions
#   - Channels map naturally to specific entities (user:{id}:notifications)
```

---

## 5. Multi-Channel Event Router

```python
import asyncio
import redis.asyncio as aioredis
from enum import Enum
from typing import Optional


class EventPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class AsyncEventRouter:
    """
    An async event router that subscribes to multiple channels and
    dispatches messages with priority ordering and dead-letter handling.

    Uses redis.asyncio for non-blocking I/O in async applications.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = aioredis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self.handlers: dict[str, list[tuple[EventPriority, Callable]]] = {}
        self._running = False

    async def subscribe(
        self,
        channel: str,
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
    ):
        if channel not in self.handlers:
            self.handlers[channel] = []
            await self.pubsub.subscribe(channel)
        self.handlers[channel].append((priority, handler))
        # Sort by priority (lower enum value = higher priority)
        self.handlers[channel].sort(key=lambda x: x[0].value)

    async def subscribe_pattern(self, pattern: str, handler: Callable):
        await self.pubsub.psubscribe(pattern)
        if pattern not in self.handlers:
            self.handlers[pattern] = []
        self.handlers[pattern].append((EventPriority.NORMAL, handler))

    async def start(self):
        self._running = True
        asyncio.create_task(self._listen())

    async def _listen(self):
        while self._running:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    await self._route(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Router error: {e}")
                await asyncio.sleep(0.1)

    async def _route(self, message: dict):
        msg_type = message["type"]
        if msg_type == "message":
            channel = message["channel"]
            handlers = self.handlers.get(channel, [])
        elif msg_type == "pmessage":
            pattern = message["pattern"]
            handlers = self.handlers.get(pattern, [])
        else:
            return

        data = message["data"]
        for priority, handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                await self._dead_letter(message, str(e))

    async def _dead_letter(self, message: dict, error: str):
        """Store failed messages for later inspection."""
        dead_letter = {
            "channel": message.get("channel", ""),
            "data": message.get("data", ""),
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.r.lpush("pubsub:dead_letters", json.dumps(dead_letter))
        await self.r.ltrim("pubsub:dead_letters", 0, 9999)

    async def stop(self):
        self._running = False
        await self.pubsub.unsubscribe()
        await self.pubsub.punsubscribe()
        await self.pubsub.close()
        await self.r.aclose()


# Usage
async def main():
    router = AsyncEventRouter()

    async def handle_payment(data: str):
        event = json.loads(data)
        print(f"Processing payment: {event['amount']}")

    async def audit_all(data: str):
        event = json.loads(data)
        print(f"Audit log: {event}")

    await router.subscribe("payments:completed", handle_payment, EventPriority.CRITICAL)
    await router.subscribe_pattern("*", audit_all)
    await router.start()

    # Publish from another connection
    pub = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    await pub.publish("payments:completed", json.dumps({"amount": 150.00, "id": "PAY-1"}))
    await asyncio.sleep(1)
    await router.stop()
    await pub.aclose()
```

---

## 6. Reliable Pub/Sub with Acknowledgment Layer

```python
class ReliablePubSub:
    """
    Standard Pub/Sub is fire-and-forget — if a subscriber is disconnected
    when a message is published, it's lost forever.

    This pattern adds a reliability layer by:
    1. Storing every published message in a Redis Stream (durable log)
    2. Broadcasting via Pub/Sub for real-time delivery
    3. On reconnection, subscribers catch up from the stream

    This gives you the real-time latency of Pub/Sub with the durability
    of Streams. The tradeoff is double the write cost (stream + publish).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", namespace: str = "reliable"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.namespace = namespace

    def publish(self, channel: str, payload: dict) -> tuple[str, int]:
        """
        Atomically write to stream and publish to channel.
        Returns (stream_entry_id, subscriber_count).
        """
        stream_key = f"{self.namespace}:log:{channel}"
        message = json.dumps(payload)

        pipe = self.r.pipeline()
        pipe.xadd(stream_key, {"data": message}, maxlen=10000)
        pipe.publish(f"{self.namespace}:live:{channel}", message)
        results = pipe.execute()

        entry_id = results[0]
        sub_count = results[1]
        return entry_id, sub_count

    def create_consumer(self, channel: str, consumer_id: str) -> "ReliableConsumer":
        return ReliableConsumer(self.r, self.namespace, channel, consumer_id)


class ReliableConsumer:
    """
    Combines Pub/Sub subscription with Stream catch-up.

    Lifecycle:
    1. On start, read last-processed ID from consumer state
    2. Catch up by reading stream entries since that ID
    3. Subscribe to Pub/Sub channel for real-time messages
    4. On each message, update last-processed ID
    5. On reconnection, repeat from step 1
    """

    def __init__(self, r: redis.Redis, namespace: str, channel: str, consumer_id: str):
        self.r = r
        self.namespace = namespace
        self.channel = channel
        self.consumer_id = consumer_id
        self.stream_key = f"{namespace}:log:{channel}"
        self.state_key = f"{namespace}:consumer:{consumer_id}:{channel}:last_id"
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self._running = False
        self._handler = None

    def _get_last_id(self) -> str:
        last_id = self.r.get(self.state_key)
        return last_id if last_id else "0-0"

    def _set_last_id(self, entry_id: str):
        self.r.set(self.state_key, entry_id)

    def start(self, handler: Callable[[dict], None]):
        """
        Start consuming. First catches up from stream, then switches
        to real-time Pub/Sub.
        """
        self._handler = handler
        self._running = True

        # Phase 1: Catch up from stream
        last_id = self._get_last_id()
        self._catchup(last_id)

        # Phase 2: Subscribe for real-time
        self.pubsub.subscribe(f"{self.namespace}:live:{self.channel}")
        self._thread = threading.Thread(target=self._listen_realtime, daemon=True)
        self._thread.start()

    def _catchup(self, since_id: str):
        """Read all stream entries after since_id."""
        entries = self.r.xrange(self.stream_key, min=f"({since_id}", max="+")
        for entry_id, fields in entries:
            payload = json.loads(fields["data"])
            try:
                self._handler(payload)
            except Exception as e:
                print(f"Catchup handler error: {e}")
            self._set_last_id(entry_id)

    def _listen_realtime(self):
        while self._running:
            message = self.pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    self._handler(payload)
                except Exception as e:
                    print(f"Realtime handler error: {e}")
                # Update last_id from stream (approximate — real-time messages
                # arrive slightly after the stream write)
                last = self.r.xrevrange(self.stream_key, count=1)
                if last:
                    self._set_last_id(last[0][0])

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.pubsub.unsubscribe()
        self.pubsub.close()


# Usage
rpub = ReliablePubSub()

# Publish — stored durably AND broadcast
entry_id, subs = rpub.publish("notifications", {"user_id": "U1", "text": "Hello"})
print(f"Stored as {entry_id}, delivered to {subs} real-time subscribers")

# Consumer — catches up on missed messages, then listens live
def handle_notification(payload: dict):
    print(f"Notification for {payload['user_id']}: {payload['text']}")

consumer = rpub.create_consumer("notifications", "worker-1")
consumer.start(handle_notification)
```

---

## 7. WebSocket Bridge Pattern

```python
import asyncio
import json
import redis.asyncio as aioredis
from dataclasses import dataclass


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket user."""
    user_id: str
    writer: asyncio.StreamWriter  # Simulates WebSocket send


class PubSubWebSocketBridge:
    """
    Bridges Redis Pub/Sub to WebSocket connections.

    Architecture:
    ┌──────────┐    PUBLISH     ┌─────────┐   WS push   ┌──────────┐
    │ Backend  │ ──────────────→│  Redis  │─────────────→│ WS Server│
    │ Service  │                │ Pub/Sub │              │ (Bridge) │
    └──────────┘                └─────────┘              └────┬─────┘
                                                              │
                                                         ┌────▼─────┐
                                                         │ Browser  │
                                                         │ Clients  │
                                                         └──────────┘

    Each WebSocket server instance subscribes to channels for its
    connected users. When a user connects, we subscribe to their
    personal channel. When they disconnect, we unsubscribe.

    For horizontal scaling, each WS server subscribes independently —
    Redis delivers to all subscribers, so the message reaches whichever
    server the user is connected to.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.r = None
        self.pubsub = None
        self.clients: dict[str, WebSocketClient] = {}  # user_id → client
        self._running = False

    async def start(self):
        self.r = aioredis.from_url(self.redis_url, decode_responses=True)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self._running = True
        asyncio.create_task(self._listener())

    async def connect_user(self, client: WebSocketClient):
        """Called when a user establishes a WebSocket connection."""
        self.clients[client.user_id] = client
        # Subscribe to user's personal channel
        await self.pubsub.subscribe(f"user:{client.user_id}:events")
        # Subscribe to user's room/group channels
        rooms = await self.r.smembers(f"user:{client.user_id}:rooms")
        for room in rooms:
            await self.pubsub.subscribe(f"room:{room}:events")

    async def disconnect_user(self, user_id: str):
        """Called when a user's WebSocket disconnects."""
        if user_id in self.clients:
            del self.clients[user_id]
            await self.pubsub.unsubscribe(f"user:{user_id}:events")
            rooms = await self.r.smembers(f"user:{user_id}:rooms")
            for room in rooms:
                # Only unsubscribe if no other connected user is in this room
                room_members = await self.r.smembers(f"room:{room}:members")
                connected_members = room_members & set(self.clients.keys())
                if not connected_members:
                    await self.pubsub.unsubscribe(f"room:{room}:events")

    async def _listener(self):
        while self._running:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1
                )
                if message and message["type"] == "message":
                    await self._route_to_websocket(message)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)

    async def _route_to_websocket(self, message: dict):
        channel = message["channel"]
        data = message["data"]

        if channel.startswith("user:"):
            # Personal message — extract user_id
            user_id = channel.split(":")[1]
            if user_id in self.clients:
                await self._send_to_client(self.clients[user_id], data)

        elif channel.startswith("room:"):
            # Room broadcast — send to all connected room members
            room_id = channel.split(":")[1]
            room_members = await self.r.smembers(f"room:{room_id}:members")
            for user_id in room_members:
                if user_id in self.clients:
                    await self._send_to_client(self.clients[user_id], data)

    async def _send_to_client(self, client: WebSocketClient, data: str):
        try:
            # In real implementation, this would be websocket.send()
            client.writer.write(data.encode())
            await client.writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            await self.disconnect_user(client.user_id)

    async def stop(self):
        self._running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.r:
            await self.r.aclose()
```

---

## 8. Service Discovery and Heartbeats

```python
import time
import uuid


class ServiceRegistry:
    """
    Uses Pub/Sub for real-time service registration/deregistration events,
    combined with sorted sets for heartbeat-based liveness detection.

    Architecture:
    - Services publish heartbeats to a sorted set (score = timestamp)
    - Registration/deregistration events broadcast via Pub/Sub
    - Watchers subscribe to get instant notification of topology changes
    - Stale services (missed heartbeats) detected by ZRANGEBYSCORE
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.heartbeat_ttl = 10  # seconds before considered dead

    def register(self, service_name: str, instance_id: str, metadata: dict):
        """Register a service instance and broadcast the event."""
        key = f"services:{service_name}:instances"
        meta_key = f"services:{service_name}:{instance_id}:meta"

        pipe = self.r.pipeline()
        pipe.zadd(key, {instance_id: time.time()})
        pipe.hset(meta_key, mapping=metadata)
        pipe.expire(meta_key, self.heartbeat_ttl * 3)
        pipe.publish(
            f"services:{service_name}:events",
            json.dumps({"event": "register", "instance": instance_id, "meta": metadata}),
        )
        pipe.execute()

    def heartbeat(self, service_name: str, instance_id: str):
        """Update heartbeat timestamp."""
        key = f"services:{service_name}:instances"
        self.r.zadd(key, {instance_id: time.time()})

    def deregister(self, service_name: str, instance_id: str):
        """Remove a service instance and broadcast."""
        key = f"services:{service_name}:instances"
        meta_key = f"services:{service_name}:{instance_id}:meta"

        pipe = self.r.pipeline()
        pipe.zrem(key, instance_id)
        pipe.delete(meta_key)
        pipe.publish(
            f"services:{service_name}:events",
            json.dumps({"event": "deregister", "instance": instance_id}),
        )
        pipe.execute()

    def get_healthy_instances(self, service_name: str) -> list[dict]:
        """Get all instances with recent heartbeats."""
        key = f"services:{service_name}:instances"
        cutoff = time.time() - self.heartbeat_ttl

        # Remove stale entries
        stale = self.r.zrangebyscore(key, "-inf", cutoff)
        if stale:
            pipe = self.r.pipeline()
            pipe.zrem(key, *stale)
            for instance_id in stale:
                pipe.publish(
                    f"services:{service_name}:events",
                    json.dumps({"event": "expired", "instance": instance_id}),
                )
            pipe.execute()

        # Return healthy instances with metadata
        healthy = self.r.zrangebyscore(key, cutoff, "+inf")
        instances = []
        for instance_id in healthy:
            meta = self.r.hgetall(f"services:{service_name}:{instance_id}:meta")
            instances.append({"id": instance_id, **meta})
        return instances


class ServiceInstance:
    """Runs inside each service to maintain its registration."""

    def __init__(self, service_name: str, host: str, port: int, redis_url: str = "redis://localhost:6379/0"):
        self.registry = ServiceRegistry(redis_url)
        self.service_name = service_name
        self.instance_id = f"{host}:{port}:{uuid.uuid4().hex[:8]}"
        self.metadata = {"host": host, "port": str(port), "started_at": str(time.time())}
        self._running = False

    def start(self):
        self.registry.register(self.service_name, self.instance_id, self.metadata)
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        while self._running:
            self.registry.heartbeat(self.service_name, self.instance_id)
            time.sleep(3)

    def stop(self):
        self._running = False
        self.registry.deregister(self.service_name, self.instance_id)


# Usage
registry = ServiceRegistry()

# Service instances register themselves
svc = ServiceInstance("payment-service", "10.0.1.5", 8080)
svc.start()

# Load balancer queries healthy instances
instances = registry.get_healthy_instances("payment-service")
# [{"id": "10.0.1.5:8080:a1b2c3d4", "host": "10.0.1.5", "port": "8080"}]
```

---

## 9. Distributed Cache Invalidation

```python
class CacheInvalidator:
    """
    Uses Pub/Sub to propagate cache invalidation across multiple
    application server instances.

    Problem: Multiple app servers each maintain local caches (in-memory
    or Redis-backed). When data changes, ALL servers must invalidate
    their cached copies.

    Solution: Publish invalidation events to a Pub/Sub channel.
    Each app server subscribes and invalidates its local cache
    upon receiving the event.

    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ App Srv │         │  Redis  │         │ App Srv │
    │    A    │ PUBLISH │ Pub/Sub │ deliver │    B    │
    │ (write) │────────→│         │────────→│ (cache) │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                    │
    invalidate          broadcast            invalidate
    local cache                              local cache
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", instance_id: str = None):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.instance_id = instance_id or uuid.uuid4().hex[:8]
        self.local_cache: dict[str, Any] = {}
        self.invalidation_channel = "cache:invalidate"
        self._subscriber = None

    def start_listener(self):
        """Start listening for invalidation events from other instances."""
        self._subscriber = self.r.pubsub(ignore_subscribe_messages=True)
        self._subscriber.subscribe(self.invalidation_channel)
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        for message in self._subscriber.listen():
            if message["type"] != "message":
                continue
            try:
                event = json.loads(message["data"])
                # Skip events we published ourselves
                if event.get("source") == self.instance_id:
                    continue
                self._handle_invalidation(event)
            except (json.JSONDecodeError, KeyError):
                pass

    def _handle_invalidation(self, event: dict):
        strategy = event.get("strategy", "key")
        if strategy == "key":
            keys = event.get("keys", [])
            for key in keys:
                self.local_cache.pop(key, None)
        elif strategy == "prefix":
            prefix = event["prefix"]
            to_remove = [k for k in self.local_cache if k.startswith(prefix)]
            for k in to_remove:
                del self.local_cache[k]
        elif strategy == "tag":
            tag = event["tag"]
            tag_key = f"cache:tag:{tag}"
            tagged_keys = self.r.smembers(tag_key)
            for key in tagged_keys:
                self.local_cache.pop(key, None)
        elif strategy == "full":
            self.local_cache.clear()

    def invalidate_keys(self, keys: list[str]):
        """Invalidate specific cache keys across all instances."""
        for key in keys:
            self.local_cache.pop(key, None)
        self.r.publish(
            self.invalidation_channel,
            json.dumps({"strategy": "key", "keys": keys, "source": self.instance_id}),
        )

    def invalidate_prefix(self, prefix: str):
        """Invalidate all keys with a given prefix."""
        to_remove = [k for k in self.local_cache if k.startswith(prefix)]
        for k in to_remove:
            del self.local_cache[k]
        self.r.publish(
            self.invalidation_channel,
            json.dumps({"strategy": "prefix", "prefix": prefix, "source": self.instance_id}),
        )

    def invalidate_tag(self, tag: str):
        """Invalidate all keys associated with a tag."""
        self.r.publish(
            self.invalidation_channel,
            json.dumps({"strategy": "tag", "tag": tag, "source": self.instance_id}),
        )

    def get(self, key: str) -> Optional[Any]:
        if key in self.local_cache:
            return self.local_cache[key]
        # Cache miss — fetch from source and populate
        return None

    def set(self, key: str, value: Any, tags: list[str] = None):
        self.local_cache[key] = value
        if tags:
            pipe = self.r.pipeline()
            for tag in tags:
                pipe.sadd(f"cache:tag:{tag}", key)
            pipe.execute()


# Usage
cache_a = CacheInvalidator(instance_id="server-a")
cache_b = CacheInvalidator(instance_id="server-b")
cache_a.start_listener()
cache_b.start_listener()

# Server A updates a user record and invalidates cache
cache_a.set("user:123", {"name": "Alice"}, tags=["users"])
cache_a.invalidate_keys(["user:123"])
# Server B's local_cache["user:123"] is now removed
```

---

## 10. Chat System with Presence

```python
class ChatRoom:
    """
    Real-time chat using Pub/Sub for message delivery and
    presence tracking with sorted sets + keyspace notifications.
    """

    def __init__(self, room_id: str, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.room_id = room_id
        self.channel = f"chat:{room_id}:messages"
        self.presence_key = f"chat:{room_id}:presence"
        self.history_key = f"chat:{room_id}:history"

    def join(self, user_id: str, display_name: str):
        """User joins the chat room."""
        pipe = self.r.pipeline()
        pipe.zadd(self.presence_key, {user_id: time.time()})
        pipe.hset(f"chat:users:{user_id}", mapping={"name": display_name, "room": self.room_id})
        pipe.publish(
            self.channel,
            json.dumps({"type": "join", "user_id": user_id, "name": display_name}),
        )
        pipe.execute()

    def leave(self, user_id: str):
        """User leaves the chat room."""
        pipe = self.r.pipeline()
        pipe.zrem(self.presence_key, user_id)
        pipe.delete(f"chat:users:{user_id}")
        pipe.publish(
            self.channel,
            json.dumps({"type": "leave", "user_id": user_id}),
        )
        pipe.execute()

    def send_message(self, user_id: str, text: str):
        """Send a message to the room."""
        message = {
            "type": "message",
            "user_id": user_id,
            "text": text,
            "timestamp": time.time(),
            "id": uuid.uuid4().hex,
        }
        serialized = json.dumps(message)

        pipe = self.r.pipeline()
        # Store in history (capped at 500 messages)
        pipe.lpush(self.history_key, serialized)
        pipe.ltrim(self.history_key, 0, 499)
        # Broadcast to subscribers
        pipe.publish(self.channel, serialized)
        # Update presence (user is active)
        pipe.zadd(self.presence_key, {user_id: time.time()})
        pipe.execute()

    def get_online_users(self) -> list[str]:
        """Get users with recent activity (last 60 seconds)."""
        cutoff = time.time() - 60
        return self.r.zrangebyscore(self.presence_key, cutoff, "+inf")

    def get_history(self, count: int = 50) -> list[dict]:
        """Get recent message history."""
        messages = self.r.lrange(self.history_key, 0, count - 1)
        return [json.loads(m) for m in messages]

    def typing_indicator(self, user_id: str):
        """Broadcast typing indicator (short-lived)."""
        self.r.publish(
            self.channel,
            json.dumps({"type": "typing", "user_id": user_id}),
        )


class ChatSubscriber:
    """Subscribes to a chat room's messages."""

    def __init__(self, room_id: str, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self.channel = f"chat:{room_id}:messages"
        self._running = False

    def start(self, on_message: Callable[[dict], None]):
        self.pubsub.subscribe(self.channel)
        self._running = True
        self._handler = on_message
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        while self._running:
            msg = self.pubsub.get_message(timeout=1.0)
            if msg and msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    self._handler(data)
                except (json.JSONDecodeError, Exception):
                    pass

    def stop(self):
        self._running = False
        self.pubsub.unsubscribe()
        self.pubsub.close()
```

---

## 11. Pub/Sub Monitoring and Diagnostics

```python
class PubSubMonitor:
    """
    Monitors Pub/Sub health and usage metrics.

    Key Redis commands for Pub/Sub inspection:
    - PUBSUB CHANNELS [pattern]  → list active channels
    - PUBSUB NUMSUB ch1 ch2     → subscriber count per channel
    - PUBSUB NUMPAT             → total pattern subscriptions
    - PUBSUB SHARDCHANNELS      → sharded channels (Redis 7+)
    - PUBSUB SHARDNUMSUB        → sharded channel subscribers (Redis 7+)
    - CLIENT LIST               → see client flags (S=subscriber, N=subscriber cmd)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)

    def get_active_channels(self, pattern: str = "*") -> list[str]:
        """List channels with at least one subscriber."""
        return self.r.pubsub_channels(pattern)

    def get_subscriber_counts(self, *channels: str) -> dict[str, int]:
        """Get subscriber count for specific channels."""
        result = self.r.pubsub_numsub(*channels)
        # Returns list of [channel, count, channel, count, ...]
        return dict(zip(result[::2], [int(c) for c in result[1::2]]))

    def get_pattern_count(self) -> int:
        """Total number of pattern subscriptions across all clients."""
        return self.r.pubsub_numpat()

    def get_subscriber_clients(self) -> list[dict]:
        """List all clients in subscriber mode."""
        clients = self.r.client_list(client_type="pubsub")
        return [
            {
                "id": c["id"],
                "addr": c["addr"],
                "age": c["age"],
                "sub": c.get("sub", 0),
                "psub": c.get("psub", 0),
                "output_buffer": c.get("omem", 0),
            }
            for c in clients
        ]

    def check_output_buffer_pressure(self) -> list[dict]:
        """
        Detect subscribers with large output buffers.

        When a subscriber is slow to consume, Redis buffers messages
        in the client's output buffer. If this exceeds the configured
        limit (client-output-buffer-limit pubsub), Redis disconnects
        the client.

        Default limits: 32mb hard / 8mb soft (60 seconds)
        """
        clients = self.get_subscriber_clients()
        pressured = []
        for client in clients:
            buf_size = int(client["output_buffer"])
            if buf_size > 1_000_000:  # > 1MB
                pressured.append({
                    **client,
                    "buffer_mb": round(buf_size / 1_048_576, 2),
                    "risk": "HIGH" if buf_size > 8_000_000 else "MEDIUM",
                })
        return pressured

    def get_throughput_estimate(self, channel: str, sample_seconds: int = 5) -> dict:
        """
        Estimate message throughput on a channel by subscribing briefly.
        """
        pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(channel)
        count = 0
        start = time.time()
        while time.time() - start < sample_seconds:
            msg = pubsub.get_message(timeout=0.1)
            if msg and msg["type"] == "message":
                count += 1
        pubsub.unsubscribe()
        pubsub.close()
        elapsed = time.time() - start
        return {
            "channel": channel,
            "messages": count,
            "duration_seconds": round(elapsed, 2),
            "rate_per_second": round(count / elapsed, 2) if elapsed > 0 else 0,
        }

    def full_diagnostic(self) -> dict:
        """Complete Pub/Sub system diagnostic."""
        channels = self.get_active_channels()
        sub_counts = self.get_subscriber_counts(*channels) if channels else {}
        return {
            "active_channels": len(channels),
            "total_pattern_subscriptions": self.get_pattern_count(),
            "subscriber_clients": len(self.get_subscriber_clients()),
            "buffer_pressure": self.check_output_buffer_pressure(),
            "top_channels": sorted(
                sub_counts.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }


# Usage
monitor = PubSubMonitor()
diag = monitor.full_diagnostic()
# {
#   "active_channels": 42,
#   "total_pattern_subscriptions": 5,
#   "subscriber_clients": 23,
#   "buffer_pressure": [{"addr": "10.0.1.5:54321", "buffer_mb": 2.4, "risk": "MEDIUM"}],
#   "top_channels": [("orders:created", 12), ("notifications:push", 8)]
# }
```

---

## 12. Backpressure and Slow Subscriber Handling

```python
class BufferedSubscriber:
    """
    Handles the fundamental Pub/Sub backpressure problem:

    If a subscriber is slow (processing takes longer than the publish
    rate), Redis buffers messages in the client output buffer. Once
    the buffer hits the hard limit (default 32MB for pubsub clients),
    Redis forcefully disconnects the client.

    This class implements:
    1. Internal ring buffer to absorb bursts
    2. Configurable drop policy when buffer is full
    3. Metrics tracking for dropped messages
    4. Automatic reconnection on disconnect
    """

    def __init__(
        self,
        redis_url: str,
        channels: list[str],
        buffer_size: int = 10000,
        drop_policy: str = "oldest",  # "oldest" or "newest"
    ):
        self.redis_url = redis_url
        self.channels = channels
        self.buffer_size = buffer_size
        self.drop_policy = drop_policy
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._metrics = {"received": 0, "processed": 0, "dropped": 0, "reconnects": 0}

    def start(self, handler: Callable[[dict], None]):
        self._handler = handler
        self._running = True
        self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._processor_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._receiver_thread.start()
        self._processor_thread.start()

    def _receive_loop(self):
        """Receives messages from Redis and buffers them."""
        while self._running:
            try:
                r = redis.from_url(self.redis_url, decode_responses=True)
                pubsub = r.pubsub(ignore_subscribe_messages=True)
                for channel in self.channels:
                    pubsub.subscribe(channel)

                while self._running:
                    msg = pubsub.get_message(timeout=1.0)
                    if msg and msg["type"] == "message":
                        self._metrics["received"] += 1
                        self._enqueue(msg)

            except (redis.ConnectionError, redis.TimeoutError):
                self._metrics["reconnects"] += 1
                time.sleep(1)  # Backoff before reconnect
            except Exception:
                time.sleep(1)

    def _enqueue(self, message: dict):
        with self._lock:
            if len(self._buffer) >= self.buffer_size:
                self._metrics["dropped"] += 1
                if self.drop_policy == "oldest":
                    self._buffer.pop(0)
                    self._buffer.append(message)
                # "newest" policy: don't add, effectively dropping the new message
            else:
                self._buffer.append(message)

    def _process_loop(self):
        """Processes messages from the internal buffer."""
        while self._running:
            message = None
            with self._lock:
                if self._buffer:
                    message = self._buffer.pop(0)

            if message:
                try:
                    self._handler(message)
                    self._metrics["processed"] += 1
                except Exception:
                    pass
            else:
                time.sleep(0.01)  # Avoid busy-wait when buffer empty

    def get_metrics(self) -> dict:
        with self._lock:
            return {
                **self._metrics,
                "buffer_depth": len(self._buffer),
                "buffer_utilization": round(len(self._buffer) / self.buffer_size * 100, 1),
            }

    def stop(self):
        self._running = False


class AdaptiveRateSubscriber:
    """
    Dynamically adjusts processing rate based on buffer depth.

    When buffer is low  → process immediately (real-time)
    When buffer is high → batch process (throughput mode)
    When buffer is critical → skip non-essential messages

    This prevents the Redis output buffer from growing by ensuring
    the subscriber always drains faster than messages arrive.
    """

    def __init__(self, redis_url: str, channel: str):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.channel = channel
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self._buffer: list[dict] = []
        self._running = False

    def start(self, handler: Callable[[list[dict]], None], priority_fn: Callable[[dict], bool] = None):
        """
        handler: receives a batch of messages (1 to N)
        priority_fn: returns True if message is high-priority (never skipped)
        """
        self._handler = handler
        self._priority_fn = priority_fn or (lambda m: True)
        self._running = True
        self.pubsub.subscribe(self.channel)

        threading.Thread(target=self._receive, daemon=True).start()
        threading.Thread(target=self._adaptive_process, daemon=True).start()

    def _receive(self):
        while self._running:
            msg = self.pubsub.get_message(timeout=0.5)
            if msg and msg["type"] == "message":
                self._buffer.append(msg)

    def _adaptive_process(self):
        while self._running:
            depth = len(self._buffer)

            if depth == 0:
                time.sleep(0.01)
                continue
            elif depth < 100:
                # Real-time mode: process one at a time
                batch = [self._buffer.pop(0)]
            elif depth < 1000:
                # Batch mode: process 10 at a time
                batch = self._buffer[:10]
                self._buffer = self._buffer[10:]
            else:
                # Critical mode: skip non-priority, batch 50
                priority = [m for m in self._buffer[:50] if self._priority_fn(m)]
                self._buffer = self._buffer[50:]
                batch = priority if priority else self._buffer[:1]

            if batch:
                try:
                    self._handler(batch)
                except Exception:
                    pass

    def stop(self):
        self._running = False
        self.pubsub.unsubscribe()
        self.pubsub.close()
```

---

## 13. Pub/Sub vs Streams Decision Matrix

| Criteria | Pub/Sub | Streams | Recommendation |
|----------|---------|---------|----------------|
| **Delivery guarantee** | At-most-once | At-least-once | Streams for reliability |
| **Message persistence** | None (fire-and-forget) | Durable (stored in stream) | Streams when messages can't be lost |
| **Replay/catch-up** | Impossible | Read from any position | Streams for late-joining consumers |
| **Consumer groups** | No (broadcast only) | Yes (partition-like) | Streams for work distribution |
| **Latency** | Sub-millisecond | ~1ms (polling interval) | Pub/Sub for real-time signals |
| **Backpressure** | Client disconnect on overflow | Consumer controls read rate | Streams for flow control |
| **Memory usage** | Zero (no storage) | Proportional to retention | Pub/Sub for ephemeral signals |
| **Pattern matching** | PSUBSCRIBE glob patterns | No built-in | Pub/Sub for dynamic routing |
| **Cluster behavior** | Broadcast to ALL nodes | Sharded by key | Streams for cluster efficiency |
| **Max throughput** | ~500K msg/s (single node) | ~200K msg/s (single node) | Pub/Sub for highest throughput |
| **Ordering** | Per-channel (single publisher) | Strict per-stream | Both ordered per-channel/stream |

### When to Use Pub/Sub

1. **Real-time notifications** — user typing indicators, presence updates
2. **Cache invalidation** — broadcast "key X changed" to all app servers
3. **Service events** — topology changes, config reload signals
4. **WebSocket bridges** — push events to connected browsers
5. **Ephemeral coordination** — "processing started" / "processing done" signals

### When to Use Streams

1. **Task queues** — reliable job processing with acknowledgment
2. **Event sourcing** — durable event log with replay
3. **Activity feeds** — ordered, persistent event history
4. **Log aggregation** — collect and process logs reliably
5. **Inter-service messaging** — when messages must not be lost

### Hybrid Pattern (Most Production Systems)

```
Use BOTH:
┌──────────────────────────────────────────────────────┐
│  WRITE PATH:                                         │
│    1. XADD to stream (durable storage)               │
│    2. PUBLISH to channel (real-time notification)     │
│                                                       │
│  SUBSCRIBER (online):                                │
│    - Gets message via Pub/Sub instantly               │
│                                                       │
│  SUBSCRIBER (reconnecting):                          │
│    - Catches up from stream since last-processed-id  │
│                                                       │
│  Result: Real-time delivery + guaranteed delivery    │
└──────────────────────────────────────────────────────┘
```

---

## 14. Production Patterns and Anti-Patterns

### Configuration Essentials

```
# redis.conf — Pub/Sub specific settings

# Output buffer limits for pubsub clients
# Format: hard-limit soft-limit soft-limit-seconds
# Default: disconnect if buffer exceeds 32MB OR exceeds 8MB for 60 seconds
client-output-buffer-limit pubsub 32mb 8mb 60

# For high-throughput systems, increase limits:
client-output-buffer-limit pubsub 256mb 64mb 120

# TCP keepalive (detect dead subscribers faster)
tcp-keepalive 60

# Timeout idle connections (0 = disabled)
timeout 300
```

### Anti-Patterns

```python
# ❌ ANTI-PATTERN 1: Using Pub/Sub as a reliable queue
# Messages are lost if no subscriber is listening
def bad_task_queue():
    r = redis.from_url("redis://localhost:6379/0")
    r.publish("tasks", json.dumps({"job": "send_email", "to": "user@example.com"}))
    # If the worker crashed, this email is lost forever

# ✅ Use Streams (XADD/XREADGROUP) for reliable task queues


# ❌ ANTI-PATTERN 2: Expensive processing in the subscriber callback
# Blocks the receive loop, causing output buffer growth
def bad_subscriber():
    pubsub = r.pubsub()
    pubsub.subscribe("events")
    for msg in pubsub.listen():
        # This takes 500ms — at 100 msg/s, we'll fall behind immediately
        result = expensive_database_call(msg["data"])
        send_http_request(result)

# ✅ Decouple receive from processing with an internal queue/buffer


# ❌ ANTI-PATTERN 3: Subscribing to thousands of channels per client
def bad_channel_explosion():
    pubsub = r.pubsub()
    for user_id in range(100000):
        pubsub.subscribe(f"user:{user_id}:notifications")
    # 100K subscriptions per client — memory and management nightmare

# ✅ Use pattern subscription or aggregate channels
# Subscribe to "user:*:notifications" with PSUBSCRIBE
# Or use per-server aggregation channels


# ❌ ANTI-PATTERN 4: No reconnection logic
def bad_no_reconnect():
    pubsub = r.pubsub()
    pubsub.subscribe("events")
    for msg in pubsub.listen():  # If connection drops, loop exits silently
        process(msg)

# ✅ Always wrap in reconnection logic with exponential backoff


# ❌ ANTI-PATTERN 5: Pattern subscriptions in high-throughput cluster
def bad_pattern_cluster():
    # In a cluster, PSUBSCRIBE forces every PUBLISH to be broadcast
    # to all nodes. With 10 nodes and 100K msg/s, that's 1M cross-node
    # messages per second.
    pubsub.psubscribe("events:*")

# ✅ Use Sharded Pub/Sub (SSUBSCRIBE) or explicit channel subscriptions
```

### Production Checklist

```python
class ProductionSubscriber:
    """Reference implementation with all production concerns."""

    def __init__(self, redis_url: str, channels: list[str]):
        self.redis_url = redis_url
        self.channels = channels
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30

    def start(self, handler: Callable):
        self._handler = handler
        self._running = True
        threading.Thread(target=self._run_with_reconnect, daemon=True).start()

    def _run_with_reconnect(self):
        while self._running:
            try:
                r = redis.from_url(self.redis_url, decode_responses=True)
                # Verify connection before subscribing
                r.ping()
                pubsub = r.pubsub(ignore_subscribe_messages=True)
                for ch in self.channels:
                    pubsub.subscribe(ch)

                self._reconnect_delay = 1  # Reset backoff on success
                self._listen(pubsub)

            except redis.ConnectionError as e:
                print(f"Connection lost: {e}. Reconnecting in {self._reconnect_delay}s")
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(self._reconnect_delay)

    def _listen(self, pubsub):
        while self._running:
            msg = pubsub.get_message(timeout=1.0)
            if msg and msg["type"] == "message":
                try:
                    self._handler(msg)
                except Exception as e:
                    # Never let handler errors kill the listener
                    print(f"Handler error (non-fatal): {e}")

    def stop(self):
        self._running = False
```

### Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Publish latency | ~10μs (local) | Measured at Redis, not including network |
| Delivery latency | ~50-200μs | Publisher → Subscriber on same machine |
| Max sustained throughput | ~500K msg/s | Single node, small messages |
| Memory per subscription | ~64 bytes | Per (channel, client) pair |
| Memory per pattern | ~80 bytes | Per (pattern, client) pair |
| Max subscribers per channel | Unlimited | Bounded by memory and output buffers |
| Output buffer default | 32MB hard / 8MB soft | Per subscriber client |

### Keyspace Notifications (Built-in Pub/Sub)

```python
class KeyspaceWatcher:
    """
    Redis can publish keyspace events on built-in channels.
    Must be enabled in config: notify-keyspace-events "KEA"

    Channel formats:
    - __keyevent@<db>__:<event>  → fired for any key affected by <event>
    - __keyspace@<db>__:<key>    → fired for any event on <key>

    Events: set, del, expire, expired, evicted, etc.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        # Enable notifications (requires CONFIG SET privilege)
        self.r.config_set("notify-keyspace-events", "KEA")

    def watch_expirations(self, handler: Callable[[str], None]):
        """Get notified when any key expires."""
        pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        pubsub.psubscribe("__keyevent@0__:expired")

        def listen():
            for msg in pubsub.listen():
                if msg["type"] == "pmessage":
                    expired_key = msg["data"]
                    handler(expired_key)

        threading.Thread(target=listen, daemon=True).start()
        return pubsub

    def watch_key(self, key: str, handler: Callable[[str, str], None]):
        """Watch all operations on a specific key."""
        pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(f"__keyspace@0__:{key}")

        def listen():
            for msg in pubsub.listen():
                if msg["type"] == "message":
                    operation = msg["data"]  # "set", "del", "expire", etc.
                    handler(key, operation)

        threading.Thread(target=listen, daemon=True).start()
        return pubsub


# Usage — session expiration detection
watcher = KeyspaceWatcher()

def on_session_expired(key: str):
    if key.startswith("session:"):
        user_id = key.split(":")[1]
        print(f"Session expired for user {user_id} — logging out")

watcher.watch_expirations(on_session_expired)
```
