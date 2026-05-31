# MQTT Deep Dive for Production System Design

MQTT is a lightweight publish/subscribe messaging protocol designed for
devices, mobile clients, gateways, and services that need efficient real-time
messaging over unreliable networks.

It is most commonly associated with IoT, but the design is useful anywhere
clients maintain long-lived connections and exchange small messages:

```text
Device / App / Gateway
        |
        | MQTT over TCP/TLS/WebSocket
        v
   MQTT Broker / Broker Cluster
        |
        | fan-out / rules / bridges / shared subscriptions
        v
Consumers, Kafka, Flink, databases, command services, dashboards
```

The important production idea is this:

> MQTT is excellent at connection-oriented command and telemetry messaging, but
> it is not a general event log like Kafka. Use MQTT at the edge, then bridge to
> durable streaming or storage systems when you need replay, analytics, joins,
> long retention, or large-scale downstream processing.

---

## Table of Contents

1. [What MQTT Solves](#1-what-mqtt-solves)
2. [Core Architecture](#2-core-architecture)
3. [Protocol Stack](#3-protocol-stack)
4. [MQTT Control Packets](#4-mqtt-control-packets)
5. [Topics and Wildcards](#5-topics-and-wildcards)
6. [Publish and Subscribe Flow](#6-publish-and-subscribe-flow)
7. [QoS Deep Dive](#7-qos-deep-dive)
8. [Sessions and Offline Delivery](#8-sessions-and-offline-delivery)
9. [Retained Messages](#9-retained-messages)
10. [Last Will and Testament](#10-last-will-and-testament)
11. [MQTT 5 Features](#11-mqtt-5-features)
12. [Use Cases](#12-use-cases)
13. [Production Architecture Patterns](#13-production-architecture-patterns)
14. [Scaling MQTT to Millions](#14-scaling-mqtt-to-millions)
15. [Failure Handling](#15-failure-handling)
16. [Ordering, Duplicates, and Idempotency](#16-ordering-duplicates-and-idempotency)
17. [Security](#17-security)
18. [Backpressure and Flow Control](#18-backpressure-and-flow-control)
19. [Observability](#19-observability)
20. [Capacity Planning](#20-capacity-planning)
21. [MQTT vs Other Technologies](#21-mqtt-vs-other-technologies)
22. [Reference Architectures](#22-reference-architectures)
23. [Production Checklist](#23-production-checklist)
24. [Common Anti-Patterns](#24-common-anti-patterns)
25. [References](#25-references)

---

## 1. What MQTT Solves

Traditional HTTP is request/response:

```text
Client -> request -> Server
Client <- response <- Server
```

This works well for APIs, but it becomes inefficient when:

- Devices need to push telemetry frequently.
- Servers need to send commands to devices.
- Clients stay online for hours or days.
- Networks are unreliable, expensive, or high latency.
- Messages are small and frequent.
- A single event must fan out to multiple subscribers.

MQTT changes the model:

```text
Publisher -> Broker -> Subscriber
```

Publishers and subscribers do not need to know each other. They communicate
through topic names.

Example:

```text
Device publishes:
  devices/device-123/telemetry

Command service publishes:
  devices/device-123/commands

Monitoring service subscribes:
  devices/+/telemetry

Specific dashboard subscribes:
  devices/device-123/#
```

MQTT is optimized for:

- Small message headers.
- Long-lived client connections.
- Bidirectional messaging.
- Low bandwidth.
- Intermittent connectivity.
- Topic-based routing.
- Delivery levels through QoS 0, 1, and 2.
- Offline session state for subscribed clients.
- Retained "last known value" messages.

MQTT is not optimized for:

- Large payload transfer.
- Historical replay for arbitrary consumers.
- Complex stream processing.
- SQL-style querying.
- Full event sourcing.
- Strong global ordering.
- Unlimited offline queues.
- Broker-side business logic beyond routing and broker extensions/rules.

---

## 2. Core Architecture

MQTT has two main entity types:

- `Client`: any publisher, subscriber, or both. A sensor, phone, vehicle, edge
  gateway, service, dashboard, or worker can be an MQTT client.
- `Broker`: the server that accepts connections, authenticates clients, stores
  sessions when configured, routes publications to matching subscriptions, and
  enforces authorization.

```text
                    ┌────────────────────┐
                    │    MQTT Broker     │
                    │                    │
                    │ authn/authz        │
                    │ sessions           │
                    │ subscriptions      │
                    │ retained messages  │
                    │ routing            │
                    └─────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌────────▼───────┐   ┌────────▼────────┐
│ Device Client  │   │ Mobile Client  │   │ Backend Service │
│ publish/sub    │   │ publish/sub    │   │ publish/sub     │
└────────────────┘   └────────────────┘   └─────────────────┘
```

### Important Broker Responsibilities

The broker is responsible for:

- Accepting MQTT connections.
- Validating protocol version and packet structure.
- Authenticating client identity.
- Authorizing topic-level publish and subscribe operations.
- Tracking topic filters for each client session.
- Routing each publish to matching subscribers.
- Managing QoS handshakes.
- Storing persistent session state when enabled.
- Storing retained messages when enabled.
- Publishing Will messages after unexpected disconnects.
- Enforcing quotas, rate limits, packet limits, and keepalive timeouts.

### MQTT Is Not Peer-to-Peer

Two devices do not connect directly to each other. The broker mediates all
communication.

```text
Device A -> Broker -> Device B
```

This is useful because:

- Devices do not need public IP addresses.
- NAT traversal is simpler.
- Security policy is centralized.
- Fan-out is handled by the broker.
- Consumers can be added without changing publishers.

---

## 3. Protocol Stack

MQTT usually runs over TCP.

```text
Application payload
MQTT packet
TCP
IP
```

Common transports:

| Transport | Common Port | Use Case |
|---|---:|---|
| MQTT over TCP | `1883` | Internal or test networks without TLS |
| MQTT over TLS | `8883` | Production device-to-cloud and service-to-broker |
| MQTT over WebSocket | `443` | Browsers, restrictive firewalls, corporate networks |
| MQTT over WebSocket + TLS | `443` | Browser/mobile production traffic |

Production systems should normally use TLS.

```text
Device
  |
  | TCP + TLS + MQTT
  v
Load Balancer
  |
  v
Broker Cluster
```

### Why WebSocket Transport Exists

MQTT over WebSocket is useful when clients cannot open raw TCP connections to
port `8883`, especially:

- Browser applications.
- Corporate networks that only allow HTTPS.
- Mobile networks with restrictive middleboxes.
- SaaS dashboards connecting through standard HTTPS infrastructure.

It adds WebSocket framing overhead but makes MQTT easier to pass through common
web infrastructure.

---

## 4. MQTT Control Packets

MQTT communication is made of control packets.

| Packet | Direction | Purpose |
|---|---|---|
| `CONNECT` | Client -> Broker | Open MQTT session |
| `CONNACK` | Broker -> Client | Accept/reject connection and return settings |
| `PUBLISH` | Either | Send an application message |
| `PUBACK` | Either | QoS 1 acknowledgement |
| `PUBREC` | Either | QoS 2 publish received |
| `PUBREL` | Either | QoS 2 publish release |
| `PUBCOMP` | Either | QoS 2 publish complete |
| `SUBSCRIBE` | Client -> Broker | Subscribe to topic filters |
| `SUBACK` | Broker -> Client | Confirm subscription grants |
| `UNSUBSCRIBE` | Client -> Broker | Remove subscriptions |
| `UNSUBACK` | Broker -> Client | Confirm unsubscribe |
| `PINGREQ` | Client -> Broker | Keepalive ping |
| `PINGRESP` | Broker -> Client | Keepalive response |
| `DISCONNECT` | Either in MQTT 5 | Gracefully close connection |
| `AUTH` | Either in MQTT 5 | Enhanced authentication exchange |

Basic connection flow:

```text
Client                                      Broker
  |                                           |
  |  CONNECT                                  |
  |------------------------------------------>|
  |                                           |
  |  CONNACK                                  |
  |<------------------------------------------|
  |                                           |
  |  SUBSCRIBE topic filters                  |
  |------------------------------------------>|
  |                                           |
  |  SUBACK                                   |
  |<------------------------------------------|
  |                                           |
  |  PUBLISH messages                         |
  |<----------------------------------------->|
  |                                           |
  |  PINGREQ / PINGRESP                       |
  |<----------------------------------------->|
```

---

## 5. Topics and Wildcards

MQTT routes messages by topic name.

Example topic:

```text
tenant/acme/site/delhi/floor/2/device/device-123/telemetry
```

A subscription uses a topic filter.

```text
tenant/acme/site/+/floor/+/device/+/telemetry
```

### Topic Levels

Topic levels are separated by `/`.

```text
devices/device-123/telemetry/temperature
```

Levels:

```text
devices
device-123
telemetry
temperature
```

### Wildcards

| Wildcard | Meaning | Example |
|---|---|---|
| `+` | Matches exactly one topic level | `devices/+/telemetry` |
| `#` | Matches zero or more levels and must be last | `devices/#` |

Examples:

```text
devices/+/telemetry
```

matches:

```text
devices/device-1/telemetry
devices/device-2/telemetry
```

does not match:

```text
devices/device-1/state/battery
```

This:

```text
devices/#
```

matches:

```text
devices/device-1/telemetry
devices/device-1/state/battery
devices/device-2/commands/ack
```

### Topic Design Guidelines

Good topic design is one of the biggest production decisions.

Prefer:

```text
tenant/{tenantId}/region/{region}/device/{deviceId}/telemetry
tenant/{tenantId}/region/{region}/device/{deviceId}/commands
tenant/{tenantId}/region/{region}/device/{deviceId}/commands/ack
tenant/{tenantId}/region/{region}/device/{deviceId}/status
```

Avoid:

```text
all
data
telemetry
device123
/random/freeform/topic
```

A scalable topic model should:

- Include tenant or customer boundary near the front.
- Include region/site when useful for routing and operations.
- Include device ID or gateway ID for identity mapping.
- Separate telemetry, commands, status, config, and acknowledgements.
- Avoid putting high-cardinality values before authorization boundaries if ACLs
  become expensive.
- Avoid unbounded wildcard subscribers like `#` in production data paths.
- Keep topic names free of secrets and personal data.
- Version payload schemas in payload metadata or a topic level when needed.

### Topic Names Are Not Payloads

Topic names should route. Payloads should carry business data.

Bad:

```text
device/123/temperature/36.7/humidity/80/battery/low
```

Better:

```text
topic:
  tenant/acme/device/123/telemetry

payload:
  {
    "temperature_c": 36.7,
    "humidity_pct": 80,
    "battery": "low",
    "schema_version": 3
  }
```

---

## 6. Publish and Subscribe Flow

MQTT decouples publishing from subscribing.

```text
Publisher                         Broker                         Subscriber
    |                               |                                 |
    | PUBLISH devices/123/temp      |                                 |
    |------------------------------>|                                 |
    |                               | match subscriptions             |
    |                               |-------------------------------->|
    |                               | PUBLISH devices/123/temp        |
```

Important behavior:

- The publisher does not know how many subscribers exist.
- A message can fan out to zero, one, or many subscribers.
- The broker routes using topic filters.
- The delivery QoS to a subscriber is the lower of the publish QoS and the
  subscription's granted maximum QoS.
- A normal subscription means every subscriber gets a copy.
- A shared subscription means only one subscriber in a group gets each message.

### Fan-Out Example

```text
Device publishes:
  tenant/acme/device/d1/telemetry

Subscribers:
  tenant/acme/device/+/telemetry       -> ingest service
  tenant/acme/device/d1/#              -> live dashboard
  tenant/acme/#                        -> audit/debug tool
```

Result:

```text
One publish can produce three broker-to-client deliveries.
```

At large scale, this matters more than inbound traffic. One million inbound
messages per second with average fan-out of five becomes five million outbound
deliveries per second.

---

## 7. QoS Deep Dive

MQTT defines three quality of service levels.

| QoS | Name | Delivery Meaning | Tradeoff |
|---:|---|---|---|
| `0` | At most once | Fire-and-forget | Fastest, may lose messages |
| `1` | At least once | Retransmit until acknowledged | Can duplicate messages |
| `2` | Exactly once at MQTT protocol hop | Four-step handshake | Highest overhead |

### Critical Clarification

MQTT QoS is not the same as application-level exactly-once processing.

QoS controls delivery between MQTT peers:

```text
Publisher <-> Broker
Broker    <-> Subscriber
```

It does not guarantee that:

- A downstream database committed the event.
- A Kafka sink produced the event exactly once.
- A business workflow executed once.
- A subscriber's application code is idempotent.
- A duplicate will never be observed after reconnects, retries, or downstream
  failure.

For production correctness, application messages still need:

- `event_id`
- producer timestamp
- producer sequence number when ordering matters
- idempotency key
- schema version
- dedupe policy downstream

### QoS 0: At Most Once

Flow:

```text
Publisher                         Broker
    |                               |
    | PUBLISH QoS 0                 |
    |------------------------------>|
    |                               |
    | no acknowledgement            |
```

Use QoS 0 when:

- Data is frequent and replaceable.
- Losing a sample is acceptable.
- Lower latency matters more than reliability.
- Network bandwidth or device battery is constrained.

Examples:

- Temperature sampled every second.
- GPS location where next sample supersedes previous.
- Live dashboard counters.
- Non-critical heartbeat telemetry.

Failure behavior:

- If the packet is lost, it is lost.
- If the client disconnects during send, the message may not arrive.
- There is no protocol-level retry.

### QoS 1: At Least Once

Flow:

```text
Publisher                         Broker
    |                               |
    | PUBLISH QoS 1, packet id      |
    |------------------------------>|
    |                               |
    | PUBACK                        |
    |<------------------------------|
```

If the publisher does not receive `PUBACK`, it can retry. The broker or
subscriber may receive duplicates.

Use QoS 1 when:

- Missing a message is worse than processing a duplicate.
- Consumers are idempotent.
- Events have IDs and dedupe is possible.
- You need a practical production default.

Examples:

- Device state changes.
- Command acknowledgements.
- Payment-terminal status events.
- Industrial alerts.
- Fleet telemetry that feeds billing or compliance.

Production rule:

```text
QoS 1 + idempotent consumers is the default for many serious systems.
```

### QoS 2: Exactly Once at MQTT Delivery Layer

Flow:

```text
Publisher                         Broker
    |                               |
    | PUBLISH QoS 2                 |
    |------------------------------>|
    |                               |
    | PUBREC                        |
    |<------------------------------|
    |                               |
    | PUBREL                        |
    |------------------------------>|
    |                               |
    | PUBCOMP                       |
    |<------------------------------|
```

Use QoS 2 only when:

- Duplicate MQTT delivery itself is unacceptable.
- Message rate is moderate.
- Broker and client implementations are tested under reconnects.
- You accept extra latency, state, and protocol overhead.

Avoid QoS 2 for:

- Very high-volume telemetry.
- Constrained devices unless required.
- Large fleets without careful capacity testing.
- Cases where downstream systems can still duplicate processing.

### QoS Selection Matrix

| Message Type | Recommended QoS | Reason |
|---|---:|---|
| Frequent sensor samples | `0` or `1` | Use `0` if replaceable, `1` if analytics must not miss samples |
| Device online status retained message | `1` | State should update reliably |
| Cloud-to-device command | `1` | Device should receive at least once and dedupe by command ID |
| Command acknowledgement | `1` | Backend needs confirmation, duplicates are manageable |
| Firmware update trigger | `1` | Use command ID and explicit state machine |
| Billing/compliance event | `1` plus durable bridge | MQTT alone is not enough |
| Safety-critical action | Usually not MQTT alone | Needs domain-specific safety protocol and confirmation |
| Live dashboard update | `0` | Latest value matters more than every value |

---

## 8. Sessions and Offline Delivery

An MQTT session is state associated with a client ID.

Session state can include:

- Subscriptions.
- In-flight QoS 1 and QoS 2 messages.
- Queued messages for offline clients when persistent sessions are enabled.
- QoS handshake state.

### Clean Session vs Clean Start

MQTT 3.1.1 uses `Clean Session`.

```text
Clean Session = 1
  Start fresh every connection.
  Broker discards previous session state.

Clean Session = 0
  Reuse existing session for the same client ID.
  Broker can store subscriptions and queued QoS messages.
```

MQTT 5 uses `Clean Start` plus `Session Expiry Interval`.

```text
Clean Start = true
  Start with a new session.

Session Expiry Interval = 0
  Delete session at disconnect.

Session Expiry Interval > 0
  Keep session for that many seconds after disconnect.

Session Expiry Interval = max value
  Keep session until explicitly removed or broker policy evicts it.
```

### Persistent Session Flow

```text
Device connects with persistent session.
Device subscribes to commands topic.
Device disconnects due to network loss.
Command service publishes QoS 1 command.
Broker queues matching command for that device session.
Device reconnects with same client ID.
Broker resumes session and delivers queued command.
```

### Persistent Sessions Are Not Infinite Queues

Production brokers should enforce:

- Session expiry.
- Max queued messages per client.
- Max queued bytes per client.
- Max in-flight messages.
- Max offline duration.
- Drop policy for stale messages.
- Dead-letter or audit handling where supported.

Without limits, offline clients can exhaust broker memory or disk.

### When to Use Persistent Sessions

Use persistent sessions when:

- Devices are intermittently connected.
- Cloud-to-device commands must survive temporary disconnects.
- The device has stable client identity.
- Queued messages have bounded size and lifetime.

Avoid persistent sessions when:

- Client IDs are unstable.
- Clients are browsers or short-lived sessions.
- Messages become stale quickly.
- You cannot bound offline queue growth.

### Session Takeover

MQTT client IDs must be unique within the broker namespace. If a second client
connects with the same client ID, brokers usually disconnect the old connection.

This is useful for device replacement, but dangerous when client IDs are reused
accidentally.

Production handling:

- Generate stable unique client IDs for devices.
- Do not let multiple devices share a client ID.
- Alert on frequent session takeovers.
- Use certificate identity or token claims to bind client ID to the principal.

---

## 9. Retained Messages

A retained message is the broker's stored last message for a topic.

```text
Publisher:
  PUBLISH topic=devices/d1/status retain=true payload="online"

Broker:
  Stores latest retained message for devices/d1/status

New subscriber:
  SUBSCRIBE devices/d1/status
  Immediately receives retained "online"
```

Retained messages are useful for last-known state.

Examples:

- Device online/offline status.
- Current configuration pointer.
- Latest firmware version available.
- Latest reported shadow-like state.
- Last known sensor reading for dashboards.

### Retained Message Is Not a History

For each topic, the broker stores at most one retained message.

```text
devices/d1/temp retained=22
devices/d1/temp retained=23
devices/d1/temp retained=24

New subscriber receives:
  24 only
```

If you need history:

- Write telemetry to Kafka, S3, Iceberg, Pinot, ClickHouse, or a time-series DB.
- Do not expect retained messages to behave like a log.

### Deleting a Retained Message

In MQTT, a retained publish with a zero-byte payload removes the retained
message for that topic.

```text
PUBLISH retain=true payload=""
```

### Retained Messages vs Persistent Sessions

| Feature | Retained Message | Persistent Session |
|---|---|---|
| Who decides storage? | Publisher | Subscriber/session |
| Stored per | Topic | Client session |
| Stores history? | No, latest only | Queued matching QoS messages while offline |
| Good for | Current state | Offline command/event delivery |
| Needs prior subscription? | No | Yes, subscription must exist in session |
| Risk | Too many retained topics | Offline queue explosion |

Use both together carefully:

```text
Retained status:
  devices/d1/status = offline

Persistent command session:
  devices/d1/commands queued while device is offline
```

---

## 10. Last Will and Testament

Last Will and Testament, usually called LWT or Will Message, lets a client tell
the broker what to publish if the client disconnects unexpectedly.

Connection setup:

```text
CONNECT
  client_id = device-123
  will_topic = devices/device-123/status
  will_payload = {"status":"offline","reason":"unexpected_disconnect"}
  will_qos = 1
  will_retain = true
```

Normal lifecycle:

```text
Device connects.
Device publishes retained status = online.
Device disconnects gracefully with DISCONNECT.
Broker does not publish Will.
```

Unexpected lifecycle:

```text
Device connects.
Device publishes retained status = online.
Network fails or keepalive timeout occurs.
Broker publishes Will status = offline.
Subscribers see device offline.
```

Use LWT for:

- Device presence.
- Gateway presence.
- Worker health.
- Fleet connectivity dashboards.
- Alerting on unexpected disconnect.

Do not use LWT as the only source of truth for safety-critical state. It depends
on broker disconnect detection, keepalive timeout, and network behavior.

### Will Delay in MQTT 5

MQTT 5 adds Will Delay Interval. This allows the broker to delay publishing the
Will, giving a client time to reconnect after a brief network flap.

Example:

```text
will_delay = 30 seconds
keepalive = 60 seconds
```

This reduces false offline/online flapping for cellular or mobile clients.

---

## 11. MQTT 5 Features

MQTT 5 keeps the core MQTT model but adds operational features that matter in
large production systems.

### Reason Codes

MQTT 5 responses can include reason codes.

Instead of a generic failure, clients can learn:

- Not authorized.
- Topic name invalid.
- Packet too large.
- Quota exceeded.
- QoS not supported.
- Retain not supported.
- Shared subscriptions not supported.

This improves client behavior and observability.

### User Properties

MQTT 5 messages can carry user properties.

Use carefully for metadata such as:

- Trace ID.
- Tenant ID when not already encoded in topic.
- Schema version.
- Producer version.
- Correlation labels.

Do not put secrets in user properties.

### Message Expiry Interval

A message can expire if it is not delivered within a configured time.

Useful for:

- Commands that become stale.
- Offers or notifications with deadline.
- Telemetry that should not queue forever.

Example:

```text
Command:
  "turn_fan_on"
  message_expiry = 30 seconds
```

If the device is offline for one hour, it should not receive a stale fan command
after reconnect.

### Session Expiry Interval

MQTT 5 separates starting a clean session from how long session state survives
after disconnect.

This is better than MQTT 3.1.1 `Clean Session` because production systems can
express:

```text
Start clean now, but keep future session for 1 hour after disconnect.
```

### Receive Maximum

`Receive Maximum` is flow control for QoS 1 and QoS 2. It limits how many
unacknowledged QoS messages can be in flight.

This prevents a sender from overwhelming a receiver.

```text
receive_maximum = 20

Sender may have at most 20 unacknowledged QoS > 0 publishes in flight.
```

### Maximum Packet Size

Broker and client can advertise max packet size. This protects constrained
clients and brokers from oversized payloads.

Production systems should set explicit limits.

### Topic Alias

Topic aliases reduce repeated topic-name overhead on a connection.

Useful when:

- Topic names are long.
- Message frequency is high.
- Bandwidth is constrained.

### Subscription Identifiers

A subscriber can attach an identifier to a subscription and then use that ID to
map incoming messages to a local handler.

Useful for:

- Clients with many subscriptions.
- SDK dispatch tables.
- Observability of which subscription matched.

### Request/Response

MQTT 5 includes response topic and correlation data properties, making
request/response patterns easier.

Example:

```text
Requester publishes:
  topic = devices/d1/rpc/get-state
  response_topic = replies/service-a/req-789
  correlation_data = req-789

Device publishes response:
  topic = replies/service-a/req-789
  correlation_data = req-789
```

Use this for controlled RPC-like flows, not for high-volume general APIs.

### Shared Subscriptions

Shared subscriptions allow multiple subscribers to share a subscription group.
Each matching message is delivered to one subscriber in the group.

Syntax:

```text
$share/{groupName}/{topicFilter}
```

Example:

```text
$share/ingest-workers/tenant/acme/device/+/telemetry
```

Without shared subscription:

```text
worker-1 subscribes tenant/acme/device/+/telemetry
worker-2 subscribes tenant/acme/device/+/telemetry
worker-3 subscribes tenant/acme/device/+/telemetry

Each telemetry message goes to all 3 workers.
```

With shared subscription:

```text
worker-1 subscribes $share/ingest/tenant/acme/device/+/telemetry
worker-2 subscribes $share/ingest/tenant/acme/device/+/telemetry
worker-3 subscribes $share/ingest/tenant/acme/device/+/telemetry

Each telemetry message goes to one worker.
```

This is essential for horizontally scalable MQTT consumers.

---

## 12. Use Cases

### IoT Telemetry

Devices publish measurements:

```text
factory/acme/line/7/machine/m-123/telemetry
```

Payload:

```json
{
  "event_id": "evt-001",
  "machine_id": "m-123",
  "temperature_c": 72.4,
  "vibration": 0.17,
  "event_time": "2026-05-24T08:00:00Z",
  "schema_version": 3
}
```

Why MQTT fits:

- Devices can maintain long-lived connections.
- Payloads are small.
- Network may be unreliable.
- QoS can be tuned by signal importance.
- Edge gateways can aggregate local devices.

### Cloud-to-Device Commands

Backend sends commands:

```text
devices/device-123/commands
```

Payload:

```json
{
  "command_id": "cmd-991",
  "type": "set_sampling_rate",
  "value": "10s",
  "expires_at": "2026-05-24T08:10:00Z"
}
```

Device replies:

```text
devices/device-123/commands/ack
```

Payload:

```json
{
  "command_id": "cmd-991",
  "status": "applied",
  "applied_at": "2026-05-24T08:00:03Z"
}
```

Production handling:

- Use QoS 1.
- Include `command_id`.
- Make command execution idempotent.
- Add expiry.
- Persist command state outside MQTT.
- Alert on commands without acknowledgement.

### Device Presence

Use retained messages plus LWT:

```text
devices/device-123/status
```

On connect:

```json
{"status":"online","timestamp":"2026-05-24T08:00:00Z"}
```

Will message:

```json
{"status":"offline","reason":"unexpected_disconnect"}
```

### Fleet Tracking

Vehicles publish:

```text
fleet/{tenantId}/vehicle/{vehicleId}/location
```

MQTT fits because:

- Vehicles move between networks.
- GPS updates are frequent and small.
- Latest location can be retained for dashboards.
- Full history can be streamed to Kafka or time-series storage.

### Industrial Monitoring

Factories use MQTT for:

- Machine telemetry.
- Alarms.
- Gateway-to-cloud messaging.
- Edge-to-edge coordination.
- SCADA integration through protocol gateways.

Production concerns:

- Local broker at edge for offline operation.
- Bridge to central broker/cloud.
- Strict topic ACLs per line/site.
- QoS 1 for alarms.
- Retained state for current machine status.

### Smart Home

MQTT is common for:

- Sensor events.
- Light/switch commands.
- Home automation state.
- Local-first control.

Pattern:

```text
home/living-room/light-1/set
home/living-room/light-1/state
home/living-room/temperature
```

### Mobile and Browser Real-Time Apps

MQTT over WebSocket can support:

- Live dashboards.
- Notifications.
- Collaborative apps.
- Chat-like systems.
- Operational consoles.

However, for general web apps, compare MQTT with WebSockets/SSE. MQTT is better
when topic routing, QoS, retained state, or broker fan-out is valuable.

### Backend Microservice Fan-Out

MQTT can fan out state changes to multiple services.

Use shared subscriptions when services should load-balance work:

```text
$share/billing-workers/events/payment/#
```

But for durable backend eventing, Kafka/Pulsar/NATS JetStream is often a better
core event backbone.

### Edge Gateway Pattern

Many local devices connect to an edge gateway. The gateway publishes upstream.

```text
Local sensors -> Edge MQTT broker/gateway -> Cloud MQTT broker -> Stream pipeline
```

Benefits:

- Reduces cloud connection count.
- Buffers during WAN outages.
- Normalizes protocols.
- Enforces local control loops.
- Allows local dashboards even when cloud is down.

---

## 13. Production Architecture Patterns

### Pattern 1: MQTT as Device Ingress, Kafka as Durable Backbone

```text
Devices
  |
  v
MQTT Broker Cluster
  |
  | shared subscription / broker rule / connector
  v
Kafka
  |
  +--> Flink stream processing
  +--> Object storage
  +--> Analytics DB
  +--> Alerting service
```

Use MQTT for:

- Device connectivity.
- Topic routing.
- QoS handshakes.
- Presence and command channels.

Use Kafka for:

- Replay.
- Long retention.
- Stream processing.
- Multiple independent consumer groups.
- Backfills.
- Exactly-once processing with compatible sinks.

### Pattern 2: Command Service with MQTT Ack State Machine

```text
API request
  |
  v
Command Service
  |
  | persist command: PENDING
  v
MQTT publish devices/{id}/commands
  |
  v
Device
  |
  | publish devices/{id}/commands/ack
  v
Command Service
  |
  | update command: APPLIED / FAILED / EXPIRED
  v
Database
```

Command table:

| Field | Purpose |
|---|---|
| `command_id` | Idempotency key |
| `device_id` | Target |
| `payload` | Command content |
| `status` | Pending, sent, acked, failed, expired |
| `expires_at` | Avoid stale execution |
| `attempt_count` | Retry tracking |
| `last_error` | Operational debugging |

### Pattern 3: Retained State for Dashboards

```text
Device publishes retained:
  devices/d1/state

Dashboard subscribes:
  devices/d1/state

Dashboard immediately sees latest known state.
```

Use for:

- Online/offline.
- Latest telemetry snapshot.
- Current config.

Do not use for:

- Audit history.
- Time-series analytics.
- Command queues.

### Pattern 4: Shared Subscription Workers

```text
Broker
  |
  | $share/ingest/tenant/+/device/+/telemetry
  |
  +--> worker-1
  +--> worker-2
  +--> worker-3
```

Each message goes to one worker. This is the MQTT equivalent of competing
consumers.

Use for:

- Horizontal ingest services.
- Database writers.
- Rule processors.
- Alert evaluators.

### Pattern 5: Multi-Region MQTT

```text
             ┌───────────────────┐
Devices ---> │ Region A Broker   │ ---> Regional stream/storage
             └───────────────────┘

             ┌───────────────────┐
Devices ---> │ Region B Broker   │ ---> Regional stream/storage
             └───────────────────┘

             ┌───────────────────┐
Devices ---> │ Region C Broker   │ ---> Regional stream/storage
             └───────────────────┘
```

Use region-local brokers for:

- Lower latency.
- Data residency.
- Fault isolation.
- Connection count distribution.
- Reduced blast radius.

Avoid making every device depend on a single global MQTT cluster.

---

## 14. Scaling MQTT to Millions

Scaling MQTT is not just "number of connected clients." You must scale several
dimensions at the same time.

### Scale Dimensions

| Dimension | Why It Matters |
|---|---|
| Concurrent connections | File descriptors, memory, TCP state, TLS state |
| Connect rate | CPU-heavy TLS/auth spikes during fleet reconnects |
| Inbound publish rate | Broker ingress CPU/network |
| Outbound delivery rate | Fan-out can dominate cost |
| Average payload size | Network, memory copy, persistence cost |
| QoS level | Higher QoS means more packets and state |
| Subscriptions per client | Subscription table size |
| Wildcard subscriptions | Matching complexity and routing overhead |
| Retained messages | Broker storage and startup/recovery impact |
| Offline queued messages | Memory/disk pressure |
| Auth checks | Per-connect and per-topic authorization cost |
| Rule engine/connectors | Downstream bottlenecks |

### Basic Throughput Formula

```text
inbound_messages_per_sec =
  connected_publishers * messages_per_publisher_per_sec

outbound_messages_per_sec =
  inbound_messages_per_sec * average_fanout

network_bytes_per_sec =
  messages_per_sec * (payload_bytes + MQTT_overhead + TLS/TCP_overhead)
```

Example:

```text
1,000,000 devices
10% active at any second
1 message every 10 seconds per active device

active publishers = 100,000
inbound = 10,000 messages/sec
average fanout = 3
outbound = 30,000 messages/sec
payload = 300 bytes

raw payload egress = 9 MB/sec before protocol overhead
```

Now compare a bad fan-out case:

```text
100,000 inbound messages/sec
average fanout = 50 dashboard/debug subscribers

outbound = 5,000,000 messages/sec
```

Fan-out is often the real bottleneck.

### Broker Cluster

At millions of connections, use a broker designed for clustering.

Broker clusters need to manage:

- Connection distribution.
- Session ownership.
- Subscription routing.
- Retained message storage.
- Queued messages.
- Node failure recovery.
- Cluster metadata propagation.
- Rolling upgrades.
- Rebalancing.

Vendor implementations differ. Validate these behaviors in your selected
broker rather than assuming all MQTT brokers cluster the same way.

### Load Balancing

MQTT connections are long-lived, so load balancing is different from stateless
HTTP.

Common options:

- L4 TCP load balancer.
- TLS passthrough to brokers.
- TLS termination at load balancer only if client identity and mTLS needs are
  handled correctly.
- DNS-based regional routing.
- MQTT over WebSocket through L7 load balancers.

Important concerns:

- Keep idle timeout greater than MQTT keepalive behavior.
- Avoid draining nodes by killing all connections at once.
- Use connection draining during deployments.
- Make reconnect jitter mandatory.
- Monitor load per broker node, not only per load balancer.

### Reconnect Storms

Reconnect storms happen when a network event, broker restart, bad deployment,
certificate expiry, or DNS issue causes many clients to reconnect at the same
time.

Symptoms:

- Huge TLS handshake spike.
- Authentication service overload.
- Broker CPU spike.
- Session restore storm.
- Offline queues draining at the same time.
- Command and retained messages redelivered in bursts.

Client requirements:

```text
initial_backoff = random(1s, 5s)
max_backoff = 1m to 5m
jitter = mandatory
do not reconnect in lockstep
do not resubscribe aggressively if session resumes
```

Broker/platform requirements:

- Rate-limit connection attempts per tenant/device group.
- Protect authentication dependencies.
- Cache authorization decisions carefully.
- Use circuit breakers for downstream rules/connectors.
- Test fleet reconnects in load tests.
- Roll out firmware and config changes gradually.

### Topic Partitioning

Topic design affects routing and authorization cost.

Good:

```text
tenant/{tenantId}/region/{region}/device/{deviceId}/telemetry
tenant/{tenantId}/region/{region}/device/{deviceId}/status
tenant/{tenantId}/region/{region}/device/{deviceId}/commands
```

Benefits:

- Natural tenant isolation.
- Regional routing.
- Easier ACLs.
- Easier bridge rules.
- Better operational dashboards.

Avoid too many global subscriptions:

```text
#
tenant/+/#
+/+/+/+/+/+
```

These can become expensive and dangerous.

### Shared Subscriptions for Consumer Scale

Use shared subscriptions for backend workers:

```text
$share/telemetry-ingest/tenant/+/device/+/telemetry
```

Scale workers horizontally:

```text
worker replicas = ceil(inbound_msg_rate / safe_msg_rate_per_worker)
```

If one worker can process 2,000 messages/sec safely and peak telemetry is
100,000 messages/sec:

```text
workers = ceil(100000 / 2000) = 50
```

Add headroom for:

- Spikes.
- Rebalances.
- Retries.
- Downstream latency.
- Deployment rollout.

### Avoid One Giant Tenant-Agnostic Cluster When Isolation Matters

For large platforms, consider isolation by:

- Region.
- Tenant tier.
- Device class.
- Criticality.
- Traffic type.

Example:

```text
premium tenants -> dedicated cluster or namespace
free tenants    -> shared cluster with stricter quotas
high-volume telemetry -> telemetry-specific cluster
commands/control -> separate low-latency cluster
```

This prevents one noisy tenant or traffic type from damaging all workloads.

### Payload Size Control

MQTT can technically carry larger payloads depending on broker limits, but
production MQTT should usually send small messages.

Prefer:

```text
payload < 1 KB for high-volume telemetry
payload < 16 KB for regular control/status messages
```

For large files:

```text
1. Upload file to object storage.
2. Publish MQTT message with URL/object key/checksum.
3. Device downloads through HTTPS.
```

Do not send firmware binaries through MQTT publishes.

---

## 15. Failure Handling

### Client Network Loss

What happens:

```text
Network drops.
Broker eventually detects keepalive timeout.
Broker closes connection.
Broker publishes Will if configured.
Client reconnects with backoff.
Session resumes if persistent and not expired.
```

Client handling:

- Use keepalive appropriate to network type.
- Reconnect with exponential backoff and jitter.
- Reuse same client ID for persistent sessions.
- Detect session present/session resumed.
- Resubscribe only when needed.
- Republish unacknowledged QoS messages according to client library behavior.
- Do not execute duplicate commands twice.

### Broker Node Failure

What happens:

```text
Clients connected to failed node disconnect.
Clients reconnect through load balancer.
Cluster/session behavior depends on broker implementation.
Queued messages may be restored, replicated, delayed, or lost depending on
configuration and durability guarantees.
```

Production handling:

- Use broker clustering with tested failure behavior.
- Use persistent storage/replication where required.
- Test node kill scenarios.
- Test rolling restart scenarios.
- Test reconnect storm behavior.
- Use connection draining during planned maintenance.

### Subscriber Down

If subscriber has no persistent session:

```text
Messages published while it is offline are not delivered later,
except retained latest value.
```

If subscriber has persistent session:

```text
Matching QoS messages may queue until session expiry or queue limit.
```

Handling:

- Use shared subscriptions for worker pools.
- Keep workers stateless and horizontally scalable.
- Use downstream durable queues/logs for long outages.
- Set message expiry for stale work.
- Monitor queue depth and age.

### Publisher Faster Than Subscriber

Symptoms:

- Subscriber in-flight window fills.
- Broker queues grow.
- Latency increases.
- Memory/disk pressure grows.
- Broker starts dropping or disconnecting clients.

Handling:

- Use MQTT 5 Receive Maximum.
- Limit max in-flight messages in clients.
- Apply per-client and per-tenant publish rate limits.
- Use shared subscriptions.
- Bridge high-volume topics to Kafka.
- Drop stale telemetry rather than queueing forever.

### Poison Payloads

MQTT does not define application payload schema. A subscriber can receive bad
JSON, unknown schema version, too-large payload, or invalid fields.

Handling:

- Validate payloads at ingest boundary.
- Include schema version.
- Use schema registry for high-value pipelines.
- Send invalid events to dead-letter storage.
- Track invalid payload rate by firmware/client version.
- Do not crash MQTT consumers on parse errors.

---

## 16. Ordering, Duplicates, and Idempotency

### Ordering

MQTT can preserve order in limited cases, but production systems should avoid
assuming global ordering.

Order can be affected by:

- Multiple publishers on same topic.
- Multiple broker nodes.
- Reconnects.
- QoS retries.
- Shared subscription worker selection.
- Downstream parallel processing.
- Bridging to Kafka or databases.

If order matters, use:

- One publisher per ordered stream.
- Stable topic per ordered entity.
- `sequence_number` in payload.
- `event_time` and `producer_time`.
- Downstream partitioning by entity ID.
- Gap detection.
- Idempotent state updates.

Example:

```json
{
  "event_id": "evt-100",
  "device_id": "d1",
  "sequence": 8812,
  "event_time": "2026-05-24T08:00:00Z",
  "type": "state_update"
}
```

### Duplicates

Duplicates can happen with:

- QoS 1 retry.
- Client reconnect.
- Broker redelivery.
- Subscriber crash after processing but before acknowledgement.
- Downstream retry.
- Shared subscription reassignment.

Consumer handling:

```text
if event_id already processed:
  ignore or merge
else:
  process and record event_id
```

For commands:

```text
if command_id already applied:
  return previous result
else:
  execute command and store result
```

### Idempotency Requirements

Every important MQTT message should have:

- Stable ID.
- Producer identity.
- Timestamp.
- Sequence number when needed.
- Schema version.
- Expiry where relevant.

Without these, QoS 1 can turn duplicates into business bugs.

---

## 17. Security

MQTT security must cover transport, identity, topic authorization, payload
validation, and operational abuse.

### Transport Security

Use:

- TLS 1.2+ or TLS 1.3.
- Server certificate validation on clients.
- Mutual TLS for managed devices when possible.
- Certificate rotation plan.
- Strong cipher policies.
- SNI where required by managed cloud platforms.

Avoid:

- Plain MQTT over the public internet.
- Disabling certificate verification.
- Long-lived shared passwords across fleets.

### Authentication

Common options:

- mTLS client certificates.
- Username/password over TLS.
- JWT or OAuth tokens.
- Custom broker authentication plugin.
- Cloud provider IoT credentials.

For device fleets, mTLS is common because each device can have a unique
certificate.

### Authorization

Authorization should be topic-level.

Example policy:

```text
device certificate subject = device-123

Allowed publish:
  tenant/acme/device/device-123/telemetry
  tenant/acme/device/device-123/status
  tenant/acme/device/device-123/commands/ack

Allowed subscribe:
  tenant/acme/device/device-123/commands
  tenant/acme/device/device-123/config

Denied:
  tenant/acme/device/+/commands
  tenant/other-tenant/#
  #
```

### Multi-Tenant Isolation

Never rely only on topic naming conventions. Enforce ACLs.

Good:

```text
tenant/{tenantId}/...
```

with broker policy:

```text
principal.tenant_id must equal topic.tenant_id
```

### Abuse Controls

Protect brokers with:

- Max packet size.
- Max client connections per tenant.
- Max subscriptions per client.
- Max topic depth/length.
- Max publish rate.
- Max queued messages.
- Max retained messages.
- Authentication rate limits.
- Connection rate limits.
- Ban/quarantine for misbehaving clients.

### Payload Security

MQTT does not inspect payload semantics by default.

Add:

- Schema validation.
- Size limits.
- Content-type metadata.
- Encryption at application layer when broker operators must not read payloads.
- Signature or MAC for high-integrity commands.
- Replay protection for commands.

### Last Will Abuse

LWT can publish messages on unexpected disconnect. A malicious client could set
misleading Will topics if authorization is weak.

Require:

- Will topic authorization at connect time.
- Will payload size limits.
- Will retain policy.
- Audit logs for Will publications.

---

## 18. Backpressure and Flow Control

MQTT systems need backpressure at multiple layers.

### Client-Side Controls

Configure:

- Max in-flight QoS messages.
- Reconnect backoff.
- Publish queue size.
- Offline publish queue policy.
- Message expiry.
- Write timeout.
- Keepalive.

For constrained devices:

```text
max_inflight = small
offline_queue = bounded
drop_policy = newest or oldest depending on signal type
```

### Broker Controls

Configure:

- Per-client rate limits.
- Per-tenant rate limits.
- Receive maximum.
- Max packet size.
- Max queued messages.
- Max session expiry.
- Max retained messages.
- Slow consumer handling.
- Connection limit.
- Subscription limit.

### Downstream Controls

MQTT brokers often bridge to:

- Kafka.
- HTTP services.
- Databases.
- Functions.
- Rule engines.

If downstream is slow, do not let the broker become an unlimited buffer.

Pattern:

```text
MQTT broker -> bounded connector -> durable queue/log -> workers
```

When downstream fails:

- Stop accepting high-volume non-critical telemetry if necessary.
- Shed low-priority traffic.
- Preserve critical command/status traffic.
- Alert before queues hit hard limits.

---

## 19. Observability

Monitor MQTT at protocol, broker, client, and business levels.

### Broker Metrics

Track:

- Connected clients.
- Connection attempts/sec.
- Disconnects/sec by reason.
- Authentication failures.
- Authorization denials.
- Publish messages in/sec.
- Publish messages out/sec.
- Bytes in/out.
- QoS 0/1/2 distribution.
- In-flight message count.
- Queued message count.
- Queue age.
- Retained message count.
- Subscription count.
- Shared subscription group lag/queue.
- Dropped messages.
- Throttled clients.
- Broker CPU, memory, disk, file descriptors.
- Network connections and packet retransmits.
- Cluster replication/routing latency.

### Client Metrics

Track by SDK/firmware version:

- Connect success rate.
- Reconnect count.
- Time since last successful connect.
- Publish success/failure.
- PUBACK latency.
- Offline queue size.
- Dropped local messages.
- Keepalive timeouts.
- TLS/auth failures.
- Command ack latency.

### Business Metrics

Track:

- Active devices.
- Silent devices.
- Telemetry freshness.
- Command success rate.
- Command timeout rate.
- Device online/offline flapping.
- Firmware version distribution.
- Invalid payload rate.
- Events written to durable storage.
- End-to-end latency from device event time to storage/alert.

### Useful Logs

Log:

- Connect and disconnect reason.
- Client ID.
- Principal/certificate identity.
- Source IP/region.
- Protocol version.
- Session present/resumed.
- Auth failure reason.
- Topic authorization denials.
- Packet too large.
- Quota exceeded.
- Will message publication.

Avoid logging full payloads by default, especially in regulated environments.

---

## 20. Capacity Planning

### Memory Model

Broker memory is affected by:

```text
connection_memory =
  TCP state
  TLS state
  MQTT session object
  subscriptions
  in-flight messages
  queued offline messages
  client buffers
```

Rough planning:

```text
total_memory =
  connected_clients * memory_per_connection
  + subscriptions * memory_per_subscription
  + queued_messages * average_queued_message_size
  + retained_messages * average_retained_message_size
  + broker overhead
```

You must measure this with your broker, TLS settings, payload sizes, and
subscription patterns.

### CPU Model

CPU is affected by:

- TLS handshakes.
- Authentication.
- Authorization checks.
- Topic matching.
- QoS state machine.
- Persistence.
- Compression if used outside MQTT.
- Rule engine transformations.
- Bridge/connector serialization.

Connect storms are often more CPU-expensive than steady-state traffic.

### Network Model

Network planning:

```text
inbound bandwidth =
  publish_in_per_sec * average_packet_size

outbound bandwidth =
  publish_out_per_sec * average_packet_size

publish_out_per_sec =
  publish_in_per_sec * average_fanout
```

For QoS 1 and QoS 2, include acknowledgement packets.

### File Descriptors and OS Limits

Millions of connections require OS tuning:

- File descriptor limits.
- TCP backlog.
- Ephemeral port handling on load generators.
- TCP keepalive settings.
- Kernel memory.
- Network interface queues.
- TLS offload if applicable.

Use broker vendor guidance and load tests. Do not assume default OS limits are
safe for million-connection workloads.

### Load Testing

Test these separately:

- Connection scale.
- Publish throughput.
- Fan-out throughput.
- Subscription churn.
- Reconnect storm.
- Persistent session restore.
- Offline queue drain.
- Retained message load.
- Shared subscription worker failure.
- Broker node failure.
- Downstream connector failure.

Example test matrix:

| Test | Goal |
|---|---|
| 1M idle clients | Validate connection memory and keepalive load |
| 100k msg/sec QoS 0 | Validate telemetry ingest |
| 50k msg/sec QoS 1 | Validate ack and persistence overhead |
| 10x reconnect spike | Validate auth/TLS/broker storm handling |
| 1M retained messages | Validate retained storage behavior |
| 100k offline sessions | Validate queue limits and reconnect drain |
| kill broker node | Validate failover and client backoff |

---

## 21. MQTT vs Other Technologies

| Technology | Best For | MQTT Comparison |
|---|---|---|
| HTTP REST | Request/response APIs | MQTT is better for long-lived bidirectional small messages |
| WebSocket | Custom real-time bidirectional apps | MQTT adds brokered pub/sub, QoS, retained messages, sessions |
| SSE | Server-to-browser event stream | MQTT is bidirectional and topic-based |
| Kafka | Durable event log and replay | MQTT is better for device connectivity; Kafka is better for backend replay |
| AMQP | Enterprise messaging/queues | MQTT is lighter and more device-friendly |
| NATS | Low-latency service messaging | MQTT has stronger IoT/client features |
| CoAP | Constrained REST-like IoT over UDP | MQTT uses brokered pub/sub over TCP |
| gRPC | Service-to-service RPC | MQTT is asynchronous pub/sub |

### Common Combination

```text
MQTT for edge/device connectivity
Kafka for durable backend event streaming
Flink for stream processing
Pinot/ClickHouse/TSDB for serving analytics
Object storage for raw long-term data
```

---

## 22. Reference Architectures

### Architecture A: Million-Device Telemetry Platform

```text
                  ┌─────────────────────┐
                  │ Device Fleet         │
                  │ 1M+ clients          │
                  └──────────┬──────────┘
                             │ MQTT/TLS
                             v
                  ┌─────────────────────┐
                  │ Regional LB          │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          v                  v                  v
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Broker Node │    │ Broker Node │    │ Broker Node │
   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
          └──────────────────┼──────────────────┘
                             │ shared subscriptions/rules
                             v
                    ┌────────────────┐
                    │ Kafka / Log     │
                    └───────┬────────┘
                            │
          ┌─────────────────┼─────────────────┐
          v                 v                 v
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │ Flink       │   │ Data Lake   │   │ Alerting    │
   └─────────────┘   └─────────────┘   └─────────────┘
```

Key decisions:

- Devices publish QoS 0 or QoS 1 based on data criticality.
- Broker accepts only authenticated device identities.
- ACL binds device to its own topic subtree.
- Ingest workers use shared subscriptions.
- Kafka stores durable event history.
- Raw events are written to object storage.
- Retained message stores latest device state only.
- Commands use separate topics and QoS 1.

### Architecture B: Command and Control

```text
Operator/API
    |
    v
Command Service
    |
    | write command PENDING
    v
Command DB
    |
    | publish QoS 1 command
    v
MQTT Broker
    |
    v
Device
    |
    | execute idempotently
    | publish ack QoS 1
    v
MQTT Broker
    |
    v
Ack Consumer
    |
    | update command status
    v
Command DB
```

Rules:

- Every command has `command_id`.
- Device stores last applied command IDs.
- Command expires.
- Backend retries publish only while command is valid.
- Acknowledgement includes final status.
- UI reads command DB, not MQTT session state.

### Architecture C: Edge Broker with Cloud Bridge

```text
Local PLCs / sensors
      |
      v
Edge Gateway / Local MQTT Broker
      |
      | bridge over WAN
      v
Cloud MQTT Broker
      |
      v
Cloud Processing
```

Use when:

- Factory/site must continue locally if WAN fails.
- Local protocols need translation.
- Cloud connection count should be reduced.
- Edge filtering or aggregation is needed.

Handling:

- Edge broker queues bounded data during WAN outage.
- Critical local commands remain local.
- Cloud bridge uses QoS 1 for important events.
- Duplicate handling exists in cloud pipeline.

---

## 23. Production Checklist

### Protocol and Client

- Choose MQTT 5 when client and broker support it.
- Use QoS 1 for important events and commands.
- Use QoS 0 for replaceable high-frequency telemetry.
- Use QoS 2 only after measuring overhead.
- Configure keepalive per network type.
- Implement reconnect backoff with jitter.
- Use bounded offline queues.
- Include event IDs and command IDs.
- Include schema version.
- Include message expiry for stale commands.

### Broker

- Use TLS in production.
- Enforce unique client identity.
- Enforce topic-level ACLs.
- Set max packet size.
- Set rate limits.
- Set session expiry limits.
- Set offline queue limits.
- Set retained message limits.
- Configure slow-consumer policy.
- Use clustering for HA and scale.
- Test node failure and rolling upgrades.

### Scaling

- Model connected clients, publish rate, fan-out, QoS, and payload size.
- Use shared subscriptions for worker pools.
- Avoid global wildcard subscriptions in hot paths.
- Partition by tenant/region/device class when needed.
- Bridge durable data to Kafka or another event log.
- Run reconnect storm tests.
- Run offline queue drain tests.

### Security

- Use mTLS or strong token auth.
- Rotate credentials/certificates.
- Bind client ID to authenticated principal.
- Prevent cross-tenant topic access.
- Validate Will topic authorization.
- Do not put secrets in topics.
- Audit auth failures and denied topic access.

### Operations

- Monitor connection count and churn.
- Monitor publish in/out and fan-out.
- Monitor queues and queue age.
- Monitor retained message count.
- Monitor auth failures.
- Monitor broker resource saturation.
- Track command ack latency.
- Track silent devices.
- Alert on reconnect storms.

---

## 24. Common Anti-Patterns

### Anti-Pattern: MQTT as Kafka Replacement

Problem:

```text
Expecting MQTT broker to provide durable replay for arbitrary consumers.
```

Fix:

```text
Bridge MQTT messages to Kafka/Pulsar/object storage for replay and analytics.
```

### Anti-Pattern: No Idempotency with QoS 1

Problem:

```text
QoS 1 can duplicate messages, but consumer inserts blindly.
```

Fix:

```text
Use event_id/command_id and dedupe at the consumer or storage layer.
```

### Anti-Pattern: Unlimited Persistent Sessions

Problem:

```text
Offline devices accumulate unbounded queued messages.
```

Fix:

```text
Set session expiry, queue size, message expiry, and stale-message drop policy.
```

### Anti-Pattern: Shared Client IDs

Problem:

```text
Multiple devices use same client ID and disconnect each other.
```

Fix:

```text
Bind one stable client ID to one authenticated identity.
```

### Anti-Pattern: Overusing Retained Messages

Problem:

```text
Retained messages used as database/history.
```

Fix:

```text
Use retained messages only for latest state. Store history elsewhere.
```

### Anti-Pattern: Global Wildcard Consumers

Problem:

```text
Many services subscribe to # and receive everything.
```

Fix:

```text
Use precise topic filters and dedicated routing/bridge rules.
```

### Anti-Pattern: No Reconnect Jitter

Problem:

```text
Fleet reconnects at the same time after outage.
```

Fix:

```text
Exponential backoff plus random jitter in every client SDK.
```

### Anti-Pattern: Sending Large Files Over MQTT

Problem:

```text
Firmware/image/log file is published as MQTT payload.
```

Fix:

```text
Upload/download large files through object storage or HTTPS.
Send only metadata, URL, checksum, and command over MQTT.
```

---

## 25. References

- MQTT.org, "MQTT: The Standard for IoT Messaging":
  <https://mqtt.org/>
- OASIS MQTT Version 5.0 specification:
  <https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html>
- OASIS MQTT Version 3.1.1 specification:
  <https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html>
- HiveMQ documentation, MQTT broker clusters:
  <https://docs.hivemq.com/hivemq/latest/user-guide/cluster.html>
- EMQX documentation, clustering:
  <https://docs.emqx.com/en/emqx/latest/deploy/cluster/introduction.html>
- AWS IoT Core MQTT documentation:
  <https://docs.aws.amazon.com/iot/latest/developerguide/mqtt.html>
- Context7 MQTT.js documentation lookup used for current client-library feature
  context: `/mqttjs/mqtt.js`.

