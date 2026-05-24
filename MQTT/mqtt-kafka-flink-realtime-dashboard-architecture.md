# MQTT + Kafka + Flink + Analytics Real-Time Dashboard Architecture

This note explains a real-world production architecture where MQTT, Kafka,
Flink, analytics stores, metrics systems, alerting, and real-time dashboards work
together.

The key use case:

```text
Millions of devices send telemetry.
Humans see live dashboards.
Backend systems detect risk in real time.
Devices receive commands, config, and alerts back through MQTT.
```

Example domains:

- Connected vehicles.
- EV charging networks.
- Cold-chain logistics.
- Industrial IoT factories.
- Smart meters.
- Healthcare device monitoring.
- Retail store sensors.
- Smart city infrastructure.

---

## 1. The Most Important Question: How Do Devices Get Data Back?

Devices do not wait for the backend to call their IP address. Most devices are
behind NAT, mobile networks, firewalls, or intermittent links.

Instead, each device keeps an outbound MQTT connection open to the broker.
After connecting, the device subscribes to topics where the backend can send
data back.

```text
Device opens outbound MQTT/TLS connection
Device subscribes to:
  tenant/acme/device/d-123/commands
  tenant/acme/device/d-123/config
  tenant/acme/device/d-123/alerts
  tenant/acme/device/d-123/ota

Backend publishes to those topics.
Broker delivers messages over the existing device connection.
Device receives message, validates it, acts, then publishes acknowledgement.
```

So the return path is still MQTT:

```text
Backend Service
   |
   | PUBLISH tenant/acme/device/d-123/commands
   v
MQTT Broker
   |
   | existing MQTT connection
   v
Device
   |
   | execute command
   v
Device actuator / screen / local controller
```

The device "sees" data in different ways depending on device type:

| Device Type | What "See" Means |
|---|---|
| Vehicle telematics unit | Receives route/config/firmware command |
| EV charger | Shows price, charging limit, fault alert |
| Cold-chain sensor gateway | Shows temperature breach or relay action |
| Factory machine gateway | Shows local alarm or stops a process |
| Smart meter | Receives tariff/config update |
| Mobile app using MQTT | Shows push-like in-app live update |
| Local HMI panel | Displays alert and operator instruction |

The human dashboard is separate:

```text
Human sees dashboard through browser/app.
Device sees commands/config/alerts through MQTT subscriptions.
```

---

## 2. End-to-End Architecture

```text
                         Human User
                             |
                             | browser / mobile app
                             v
                    +------------------+
                    | Dashboard UI     |
                    +--------+---------+
                             |
                 REST query  |  WebSocket/SSE live push
                             v
                    +------------------+
                    | Dashboard API    |
                    +---+----------+---+
                        |          |
                        |          v
                        |   +--------------+
                        |   | WebSocket    |
                        |   | Gateway      |
                        |   +------+-------+
                        |          ^
                        v          |
              +----------------+   | live alerts/updates
              | Analytics DB   |   |
              | Pinot/ClickHouse|  |
              +--------^-------+   |
                       |           |
                       |           |
+---------+     +------+-------+   |     +----------------+
| Devices | --> | MQTT Broker  | --> --> | Kafka Topics    |
+----+----+     | Cluster      |         +--------+-------+
     ^          +------+-------+                  |
     |                 |                          v
     |                 |                 +----------------+
     |                 |                 | Flink Jobs     |
     |                 |                 +---+--------+---+
     |                 |                     |        |
     |                 |                     |        v
     |                 |                     |  Alert Topics
     |                 |                     v
     |                 |              Metrics Topics
     |                 |
     | commands/config/alerts
     |
+----+----------------+
| Command/Alert       |
| Publisher Service   |
+---------------------+
```

The system has two loops:

```text
Telemetry loop:
  Device -> MQTT -> Kafka -> Flink -> Analytics DB -> Dashboard

Control loop:
  Dashboard/Flink/Command Service -> MQTT -> Device -> Ack -> MQTT -> Kafka
```

---

## 3. Real-World Scenario: Cold-Chain Fleet

Imagine a logistics company with refrigerated trucks and containers.

Each asset sends:

- GPS location.
- Temperature.
- Door open/close events.
- Battery/fuel level.
- Compressor status.
- Network signal strength.
- Driver/device health.

Users need:

- Live map.
- Temperature breach alerts.
- Delivery risk score.
- Offline device detection.
- Command controls, such as changing cooling mode.
- Historical analytics by route, city, customer, and product type.

Devices need data back:

- Temperature threshold updates.
- Route changes.
- Alert messages for local display.
- Commands to change cooling mode.
- Firmware update instructions.
- Request to upload diagnostic logs.

---

## 4. Topic Model

A production topic model should separate telemetry, status, commands, config,
alerts, and acknowledgements.

```text
tenant/{tenantId}/region/{region}/device/{deviceId}/telemetry
tenant/{tenantId}/region/{region}/device/{deviceId}/status
tenant/{tenantId}/region/{region}/device/{deviceId}/alerts
tenant/{tenantId}/region/{region}/device/{deviceId}/commands
tenant/{tenantId}/region/{region}/device/{deviceId}/commands/ack
tenant/{tenantId}/region/{region}/device/{deviceId}/config/desired
tenant/{tenantId}/region/{region}/device/{deviceId}/config/reported
tenant/{tenantId}/region/{region}/device/{deviceId}/ota
```

Example:

```text
tenant/acme/region/in-north/device/truck-884/telemetry
tenant/acme/region/in-north/device/truck-884/commands
tenant/acme/region/in-north/device/truck-884/commands/ack
```

Backend services can subscribe by group:

```text
$share/telemetry-ingest/tenant/+/region/+/device/+/telemetry
$share/ack-consumers/tenant/+/region/+/device/+/commands/ack
```

Devices subscribe only to their own topics:

```text
tenant/acme/region/in-north/device/truck-884/commands
tenant/acme/region/in-north/device/truck-884/config/desired
tenant/acme/region/in-north/device/truck-884/alerts
tenant/acme/region/in-north/device/truck-884/ota
```

This prevents one device from reading another device's commands.

---

## 5. Device Boot and Subscription Flow

When a device starts:

```text
1. Device opens MQTT/TLS connection.
2. Broker authenticates certificate/token.
3. Broker authorizes client ID and topic access.
4. Device publishes retained status = online.
5. Device subscribes to commands/config/alerts/ota topics.
6. Broker delivers retained desired config if present.
7. Device publishes reported config/state.
8. Device starts publishing telemetry.
```

Sequence:

```text
Device                                  MQTT Broker
  |                                          |
  | CONNECT client_id=truck-884             |
  |----------------------------------------->|
  | CONNACK                                  |
  |<-----------------------------------------|
  | PUBLISH status online retain=true        |
  |----------------------------------------->|
  | SUBSCRIBE commands/config/alerts/ota     |
  |----------------------------------------->|
  | SUBACK                                   |
  |<-----------------------------------------|
  | retained config desired                  |
  |<-----------------------------------------|
  | PUBLISH config reported                  |
  |----------------------------------------->|
  | PUBLISH telemetry every N seconds        |
  |----------------------------------------->|
```

Device subscription is the foundation of the return path.

---

## 6. Telemetry Ingestion Path

Device publishes:

```text
topic:
  tenant/acme/region/in-north/device/truck-884/telemetry
```

Payload:

```json
{
  "event_id": "evt-10001",
  "device_id": "truck-884",
  "tenant_id": "acme",
  "lat": 28.6139,
  "lon": 77.209,
  "temperature_c": 9.7,
  "door_open": false,
  "battery_pct": 71,
  "event_time": "2026-05-24T10:15:30Z",
  "sequence": 55281,
  "schema_version": 3
}
```

Flow:

```text
Device
  -> MQTT Broker
  -> shared subscription ingest workers or broker connector
  -> Kafka topic: iot.telemetry.raw
  -> Flink
```

Kafka stores raw events so that downstream systems can replay and recover.

---

## 7. Kafka Topic Design

Common Kafka topics:

```text
iot.telemetry.raw
iot.telemetry.validated
iot.telemetry.invalid
iot.device.status
iot.commands.requested
iot.commands.sent
iot.commands.ack
iot.alerts.detected
iot.alerts.device-delivery
iot.metrics.10s
iot.metrics.1m
iot.metrics.5m
iot.latest-state.changelog
```

Partitioning:

```text
key = tenant_id + device_id
```

This keeps events for one device in order within one Kafka partition.

Kafka is used for:

- Durable buffering.
- Replay after Flink failure.
- Multiple consumers.
- Isolation between MQTT and analytics systems.
- Event history before writing to OLAP/time-series stores.

---

## 8. Flink Real-Time Processing

Flink consumes Kafka and performs stateful stream processing.

```text
iot.telemetry.raw
  -> parse
  -> validate
  -> dedupe by event_id
  -> assign event time
  -> watermark for late/out-of-order events
  -> enrich with device/customer/route data
  -> compute latest state
  -> compute rolling metrics
  -> detect anomalies
  -> emit alerts
```

Example windows:

```text
Per tenant + region every 10 seconds:
  active_device_count
  avg_temperature
  max_temperature
  offline_count
  alert_count

Per device every 5 minutes:
  avg_temperature
  max_temperature
  battery_drain_rate
  gps_distance
  signal_quality
```

Example alert rules:

```text
temperature_c > 8 for 3 consecutive minutes
door_open = true while truck is moving
battery_pct < 15 and no charger nearby
no telemetry for 5 minutes
gps jump > 5 km in 10 seconds
```

Flink emits:

```text
iot.metrics.10s
iot.metrics.1m
iot.alerts.detected
iot.latest-state.changelog
```

---

## 9. Alert Path Back to Devices

This is the important reverse path.

Flink detects alert:

```json
{
  "alert_id": "alert-777",
  "tenant_id": "acme",
  "device_id": "truck-884",
  "type": "temperature_breach",
  "severity": "critical",
  "message": "Container temperature above 8C for 3 minutes",
  "detected_at": "2026-05-24T10:18:30Z"
}
```

Flow:

```text
Flink
  -> Kafka topic: iot.alerts.detected
  -> Alert Service
  -> persist alert
  -> decide recipients/actions
  -> publish MQTT device alert
  -> publish WebSocket dashboard event
```

MQTT publish back to device:

```text
topic:
  tenant/acme/region/in-north/device/truck-884/alerts

payload:
  {
    "alert_id": "alert-777",
    "severity": "critical",
    "display": "Temperature breach. Check container.",
    "action_required": true,
    "suggested_action": "inspect_cooling_unit",
    "expires_at": "2026-05-24T10:28:30Z"
  }
```

Device receives it because it already subscribed to:

```text
tenant/acme/region/in-north/device/truck-884/alerts
```

Device behavior:

```text
1. Validate alert_id and signature if used.
2. Check expiry.
3. Display on local screen or HMI.
4. Sound buzzer or flash indicator if configured.
5. Optionally trigger local actuator.
6. Publish acknowledgement.
```

Device acknowledgement:

```text
topic:
  tenant/acme/region/in-north/device/truck-884/commands/ack

payload:
  {
    "correlation_id": "alert-777",
    "kind": "alert_ack",
    "status": "displayed",
    "device_time": "2026-05-24T10:18:32Z"
  }
```

That acknowledgement returns to Kafka and the dashboard.

---

## 10. Command Path Back to Devices

Commands can come from:

- Human dashboard user.
- Automation service.
- Flink rule.
- Scheduled maintenance workflow.
- ML risk engine.

Example: operator changes cooling target from dashboard.

```text
Dashboard User
  -> Dashboard API
  -> Command Service
  -> Command DB: status=PENDING
  -> MQTT publish to device command topic
  -> Device receives command
  -> Device acts
  -> Device publishes ack
  -> Command Service updates status=APPLIED
  -> Dashboard updates in real time
```

MQTT command:

```text
topic:
  tenant/acme/region/in-north/device/truck-884/commands
```

Payload:

```json
{
  "command_id": "cmd-9001",
  "type": "set_temperature_target",
  "target_c": 4,
  "requested_by": "operator-17",
  "created_at": "2026-05-24T10:20:00Z",
  "expires_at": "2026-05-24T10:25:00Z"
}
```

Device ack:

```json
{
  "command_id": "cmd-9001",
  "device_id": "truck-884",
  "status": "applied",
  "applied_at": "2026-05-24T10:20:04Z",
  "current_target_c": 4
}
```

Command reliability rules:

- Use QoS 1 for command publish.
- Use command ID for idempotency.
- Use expiry to avoid stale commands.
- Persist command state outside MQTT.
- Device must dedupe repeated command IDs.
- Dashboard should show `PENDING`, `SENT`, `APPLIED`, `FAILED`, or `EXPIRED`.

---

## 11. Config and Device Shadow Pattern

For desired state, use a shadow-like model.

```text
Desired config:
  tenant/acme/region/in-north/device/truck-884/config/desired

Reported config:
  tenant/acme/region/in-north/device/truck-884/config/reported
```

Desired config can be retained:

```json
{
  "config_version": 42,
  "sampling_interval_sec": 10,
  "temperature_threshold_c": 8,
  "firmware_channel": "stable",
  "updated_at": "2026-05-24T10:00:00Z"
}
```

When a device reconnects:

```text
1. Device subscribes to config/desired.
2. Broker immediately sends retained latest config.
3. Device applies if config_version is newer.
4. Device publishes config/reported.
```

This is how offline devices catch up to latest config without the backend
knowing exactly when they reconnect.

---

## 12. Dashboard Real-Time Path

The dashboard has two kinds of data.

### Latest Live Events

For live alerts and map updates:

```text
Flink
  -> Kafka: iot.alerts.detected / iot.latest-state.changelog
  -> WebSocket Gateway
  -> Browser dashboard
```

The browser receives only filtered, user-authorized updates.

Example:

```text
user belongs to tenant acme
dashboard is open for region in-north

send only:
  tenant=acme and region=in-north events
```

### Queryable Metrics and History

For charts, tables, and historical analysis:

```text
Flink
  -> Pinot / ClickHouse / Druid
  -> Dashboard API
  -> Browser dashboard
```

Dashboard queries:

```sql
SELECT
  region,
  count(*) AS active_devices,
  avg(temperature_c) AS avg_temp,
  sum(alert_count) AS alerts
FROM device_metrics_1m
WHERE tenant_id = 'acme'
  AND window_start > now() - interval '1 hour'
GROUP BY region;
```

The dashboard should not subscribe to every raw device event. At scale, it
should receive aggregates, latest state, and alert events.

---

## 13. Metrics and Observability Path

There are two metric categories.

### Business Metrics

Business metrics come from device data:

```text
active vehicles
offline devices
temperature breach count
average battery
commands applied
delivery risk score
```

Flow:

```text
MQTT telemetry -> Kafka -> Flink -> analytics DB -> dashboard
```

### Platform Metrics

Platform metrics come from infrastructure:

```text
MQTT connected clients
MQTT reconnect rate
MQTT publish in/out rate
Kafka consumer lag
Flink checkpoint duration
Flink backpressure
WebSocket connected users
dashboard API latency
```

Flow:

```text
Broker/Kafka/Flink/API metrics
  -> Prometheus
  -> Grafana / Alertmanager
```

Production teams need both:

```text
Business dashboard:
  What is happening to devices and customers?

Operations dashboard:
  Is the platform healthy?
```

---

## 14. Scaling to Millions

Example scale:

```text
5 million registered devices
1 million connected concurrently
200,000 telemetry messages/sec at peak
50,000 command/alert messages/sec at peak during incident
10,000 dashboard users during operations
```

### MQTT Scaling

Use:

- Regional broker clusters.
- TLS termination strategy.
- Strict client ID uniqueness.
- Topic ACLs.
- Shared subscriptions for ingest consumers.
- Bounded persistent sessions.
- Message expiry for commands and alerts.
- Reconnect backoff with jitter.
- Per-tenant quotas.

Avoid:

- One global broker cluster for all traffic.
- Unlimited offline queues.
- Global wildcard subscribers in hot paths.
- Sending every raw event to every dashboard.

### Kafka Scaling

Use:

- Partition by `tenant_id + device_id`.
- Separate raw, validated, metrics, alert, and command topics.
- Retention based on replay needs.
- Consumer groups for Flink, storage, alerting, and audit.
- Dead-letter topics for invalid payloads.

### Flink Scaling

Use:

- Parallelism based on Kafka partitions.
- Keyed state by device or tenant/device.
- Event-time watermarks.
- Checkpoints.
- RocksDB state backend for large state.
- Separate jobs for telemetry metrics, alerting, and command ack processing
  when isolation is needed.

### Dashboard Scaling

Use:

- Pre-aggregated metrics.
- Latest-state cache.
- WebSocket rooms by tenant/region/user scope.
- Server-side filtering.
- Rate limits on live map updates.
- Downsampled streams for UI.

---

## 15. Handling Offline Devices

If a device is offline, the backend still may need to send commands, alerts,
configuration, or firmware instructions. The correct design is not "call the
device later." The correct design is:

```text
MQTT delivers.
Database remembers.
Device acknowledges.
Dashboard reflects database state.
```

The device comes back online by opening a new outbound MQTT connection using
the same stable identity. Then the broker and backend decide what data should be
delivered.

### Offline Device Problem

Devices can go offline because of:

- Cellular network loss.
- Wi-Fi loss.
- Power failure.
- Vehicle moving through poor coverage.
- Gateway reboot.
- Broker/load balancer disconnect.
- Certificate/token expiry.
- Firmware crash.

During this time, the backend may still create:

- Commands.
- Alerts.
- Desired configuration updates.
- Firmware update instructions.
- Requests for diagnostics.

The system needs to answer:

```text
Should the device receive every missed message?
Should it receive only the latest desired state?
Should old commands expire?
Who remembers pending work?
How does the dashboard know delivery status?
```

There is no single mechanism for all of these. Use the right mechanism per
message type.

### Offline Delivery Decision Table

| Data Type | Best Mechanism | Why |
|---|---|---|
| Latest config | Retained desired-state topic | Only the latest config matters |
| Short-lived command | MQTT persistent session + QoS 1 + expiry | Deliver soon or expire |
| Critical command | Command DB + MQTT delivery + ack | Needs audit, retry, and status |
| Device alert | MQTT QoS 1 + expiry | Alert should not live forever |
| Firmware update instruction | Retained OTA desired state + command DB | Device can pick up latest version |
| Historical telemetry missed by backend | Device local buffer + upload/replay | MQTT broker should not be the history store |
| Dashboard status | Command/alert database | UI needs durable truth |

Options:

### Option 1: Persistent MQTT Session

The broker can queue QoS 1 or QoS 2 messages for an offline device if the device
has a persistent session.

For MQTT 3.1.1:

```text
client_id = truck-884
clean_session = false
```

For MQTT 5:

```text
client_id = truck-884
clean_start = false
session_expiry_interval = 3600 seconds
```

The device must subscribe to its command topics while online:

```text
tenant/acme/region/in-north/device/truck-884/commands
tenant/acme/region/in-north/device/truck-884/alerts
tenant/acme/region/in-north/device/truck-884/config/desired
```

If the device disconnects and the session has not expired, the broker remembers
the subscriptions. When the backend publishes a matching QoS 1 command, the
broker can queue it for that device.

Flow:

```text
Device connects with persistent session.
Device subscribes to commands.
Device disconnects.
Backend publishes QoS 1 command.
Broker queues command for that session.
Device reconnects with same client_id.
Broker resumes session.
Broker delivers queued command.
Device publishes ack.
```

Use for:

- Short offline periods.
- Important commands.
- Bounded queue size.
- Networks where devices reconnect frequently.

Must configure:

- Session expiry.
- Max queued messages.
- Max queued bytes.
- Message expiry.
- Max in-flight QoS messages.
- Drop policy when queue is full.

Do not use persistent sessions as unlimited storage. If one million devices are
offline and each accumulates thousands of messages, the broker becomes a
database accidentally.

### Persistent Session Example

Backend publishes:

```text
topic:
  tenant/acme/region/in-north/device/truck-884/commands

qos:
  1

message_expiry:
  300 seconds
```

Payload:

```json
{
  "command_id": "cmd-9001",
  "type": "set_temperature_target",
  "target_c": 4,
  "created_at": "2026-05-24T10:20:00Z",
  "expires_at": "2026-05-24T10:25:00Z"
}
```

If `truck-884` reconnects before expiry, it receives the command. If it
reconnects after expiry, the command should not be delivered or should be
ignored by the device.

### Option 2: Retained Desired State

Backend publishes latest desired config as retained message.

Use for:

- Config.
- Latest target state.
- Firmware channel.
- Last known instruction that supersedes older ones.

When device reconnects and subscribes, it receives only the latest retained
desired state.

Example retained topic:

```text
tenant/acme/region/in-north/device/truck-884/config/desired
```

Payload:

```json
{
  "config_version": 42,
  "sampling_interval_sec": 10,
  "temperature_threshold_c": 8,
  "firmware_channel": "stable",
  "updated_at": "2026-05-24T10:00:00Z"
}
```

Device reconnect flow:

```text
Device reconnects.
Device subscribes to config/desired.
Broker sends retained latest desired config.
Device compares config_version.
Device applies if newer.
Device publishes config/reported.
```

Reported config:

```text
tenant/acme/region/in-north/device/truck-884/config/reported
```

Payload:

```json
{
  "config_version": 42,
  "status": "applied",
  "reported_at": "2026-05-24T10:31:00Z"
}
```

Retained messages are best when old values are obsolete. They are not command
history.

### Option 3: Command Database Retry

Command service stores command in DB and sends when device returns online.

Use for:

- Critical commands needing audit trail.
- Commands requiring approval/workflow.
- Long offline windows.

The device online event can trigger command dispatch.

Command database:

| Field | Purpose |
|---|---|
| `command_id` | Idempotency key |
| `device_id` | Target device |
| `type` | Command type |
| `payload` | Command body |
| `status` | Pending, waiting, sent, applied, failed, expired |
| `created_at` | Audit timestamp |
| `expires_at` | Staleness boundary |
| `attempt_count` | Retry tracking |
| `last_error` | Debugging |

Statuses:

```text
PENDING
WAITING_FOR_DEVICE
SENT
DELIVERED_OR_ACKED_BY_MQTT
APPLIED
FAILED
EXPIRED
```

For business correctness, `APPLIED` should come from device acknowledgement,
not only from broker publish success.

### Full Offline Command Flow

```text
1. Device truck-884 is offline.
2. Broker publishes retained status:
     tenant/acme/.../truck-884/status = offline
3. Operator sends command from dashboard.
4. Command Service writes command DB row:
     status = WAITING_FOR_DEVICE
5. Command Service may publish MQTT QoS 1 command with message expiry.
6. If persistent session exists, broker queues it.
7. Device reconnects with same client_id.
8. Device publishes retained status = online.
9. Broker resumes persistent session and sends queued command.
10. Device validates command_id, expiry, schema, and current state.
11. Device executes command.
12. Device publishes ack to commands/ack.
13. Ack flows MQTT -> Kafka -> Command Service.
14. Command Service updates DB status = APPLIED or FAILED.
15. Dashboard receives WebSocket update and shows final state.
```

Sequence:

```text
Dashboard       Command Service       MQTT Broker          Device
   |                  |                    |                  |
   | create command   |                    |                  |
   |----------------->|                    |                  |
   |                  | save WAITING       |                  |
   |                  | publish QoS 1      |                  |
   |                  |------------------->| queued/offline   |
   |                  |                    |                  |
   |                  |                    | CONNECT same ID  |
   |                  |                    |<-----------------|
   |                  |                    | deliver command  |
   |                  |                    |----------------->|
   |                  |                    |                  | validate/apply
   |                  |                    | ack              |
   |                  |<-------------------|<-----------------|
   | update APPLIED   |                    |                  |
   |<-----------------|                    |                  |
```

### Device-Side Rules After Reconnect

The device should not blindly execute everything it receives.

For every command or alert:

```text
if command_id already applied:
  publish ack with previous result
  do not execute again

if expires_at < current_time:
  publish ack status = expired
  do not execute

if config_version <= current_config_version:
  ignore or report already_applied

if command is invalid for current device state:
  publish ack status = rejected
```

Device local state should include:

- Last applied command IDs.
- Current config version.
- Last processed sequence number when ordering matters.
- Safe-mode flag.
- Local clock quality or server-time offset.

### Offline Telemetry From Device to Cloud

The reverse problem also exists: the device may collect telemetry while offline.

For important telemetry, the device should keep a local bounded buffer:

```text
Device offline.
Device stores telemetry locally.
Device reconnects.
Device uploads buffered events with original event_time and sequence.
Backend dedupes by event_id.
Flink processes with event-time handling and late-event policy.
```

Rules:

- Keep a bounded local buffer.
- Drop or compact low-priority telemetry first.
- Preserve critical events.
- Include original `event_time`.
- Include `event_id` and sequence number.
- Backend must dedupe.
- Flink must define late-event handling.

Do not expect MQTT retained messages or broker offline queues to store long
telemetry history.

### Broker Queue Limits

At scale, offline queues can become dangerous.

Example:

```text
500,000 offline devices
100 queued messages per device
1 KB average message

queued payload only = 50 GB
plus broker metadata, indexes, replication, and protocol state
```

Therefore configure:

- Max queued messages per client.
- Max queued bytes per client.
- Max session expiry.
- Max message expiry.
- Per-tenant queue quota.
- Drop policy for stale messages.
- Alerting on queue depth and queue age.

### What the Dashboard Should Show

For offline devices, the dashboard should not just say "command sent." It should
show the real lifecycle:

```text
Device status:
  offline

Command status:
  waiting for device

Delivery:
  queued or pending retry

Expiry:
  expires in 4m 12s

Final state:
  applied / failed / expired / rejected
```

The dashboard reads this from the command database and device status store, not
from temporary memory inside the MQTT publisher.

Best production pattern:

```text
Use MQTT for delivery.
Use database for command truth.
Use retained state for latest desired config.
Use message expiry to avoid stale actions.
Use device acknowledgement for final status.
```

---

## 16. Safety and Idempotency

A device must never blindly execute every message.

Device should validate:

- Topic belongs to itself.
- Payload schema version is supported.
- Command ID is not already applied.
- Command has not expired.
- Sender is authorized by broker policy.
- Optional message signature is valid for critical commands.
- Command is valid for current device state.

Device local state:

```text
last_applied_command_ids
current_config_version
last_sequence_seen
safe_mode_enabled
```

For duplicate command:

```text
if command_id already applied:
  do not execute again
  publish ack with previous result
```

This matters because QoS 1 can redeliver messages.

---

## 17. Alerting Design

There are three alert destinations.

### Human Alert

```text
Flink -> Kafka -> Alert Service -> PagerDuty/Slack/Email/WebSocket dashboard
```

For operators and support teams.

### Device Alert

```text
Flink -> Kafka -> Alert Service -> MQTT -> device alerts topic
```

For local display, buzzer, or automatic safe action.

### Platform Alert

```text
Prometheus -> Alertmanager -> on-call
```

For infrastructure problems like broker overload or Kafka lag.

Do not mix these together. A temperature breach is a business/device alert. A
Flink checkpoint failure is a platform alert.

---

## 18. Full Example Flow

### Temperature Breach

```text
1. Device publishes temperature 10.2C.
2. MQTT broker receives telemetry.
3. Ingest worker writes event to Kafka iot.telemetry.raw.
4. Flink reads event, dedupes, applies watermark.
5. Flink sees temperature > 8C for 3 minutes.
6. Flink emits alert to Kafka iot.alerts.detected.
7. Alert Service persists alert.
8. Alert Service pushes dashboard event through WebSocket.
9. Alert Service publishes MQTT alert to device.
10. Device displays warning and starts local buzzer.
11. Device publishes alert acknowledgement.
12. Ack flows through MQTT -> Kafka -> dashboard.
13. Operator sends command to lower cooling target.
14. Command Service publishes MQTT command.
15. Device applies command and sends ack.
16. Dashboard shows command APPLIED.
```

End-to-end loop:

```text
Telemetry -> Detection -> Human visibility -> Device action -> Ack -> Audit
```

---

## 19. What Goes Where

| Concern | System |
|---|---|
| Device connection | MQTT |
| Device command delivery | MQTT |
| Device latest config | MQTT retained message or shadow service |
| Durable raw event log | Kafka |
| Replay | Kafka |
| Real-time window metrics | Flink |
| Alert detection | Flink |
| Command source of truth | Command DB |
| Historical analytics | Pinot / ClickHouse / Druid |
| Latest state lookup | Redis / compacted Kafka topic / OLAP table |
| Human live dashboard push | WebSocket / SSE |
| Platform metrics | Prometheus / Grafana |
| Business alerts | Alert service |

---

## 20. Practical Production Rules

- MQTT is the device connectivity and return-command layer.
- Kafka is the durable streaming backbone.
- Flink is the real-time intelligence layer.
- Analytics DB is the dashboard query layer.
- WebSocket/SSE is the browser live update layer.
- Prometheus/Grafana is the platform observability layer.
- Devices receive data back by subscribing to command/config/alert topics.
- Devices should ack every important command or alert.
- Every important command needs `command_id`, expiry, and idempotency.
- The dashboard should show command and alert state from databases, not from
  memory inside one service.
- Do not push raw telemetry for millions of devices directly to browsers.
- Pre-aggregate, filter, and downsample for dashboards.
- Keep command/control traffic isolated from high-volume telemetry traffic when
  scale becomes large.

---

## 21. References

- MQTT.js current documentation lookup through Context7: `/mqttjs/mqtt.js`
- MQTT.org:
  <https://mqtt.org/>
- OASIS MQTT Version 5.0 specification:
  <https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html>
- Apache Kafka:
  <https://kafka.apache.org/>
- Apache Flink:
  <https://flink.apache.org/>
