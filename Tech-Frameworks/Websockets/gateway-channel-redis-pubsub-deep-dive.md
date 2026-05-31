# Gateway, Channel Server, and Redis Pub/Sub Deep Dive

This note explains how a Slack-like WebSocket system routes messages between Gateway Servers, Channel Servers, Presence Servers, and Redis Pub/Sub.

The key idea:

```text
Client <-> Gateway Server <-> Backend services

Client to Gateway:
  WebSocket

Gateway to Channel/Presence/Admin:
  gRPC or internal REST

Channel/Presence/Admin to Gateway:
  Redis Pub/Sub, Kafka, or direct control RPC depending on use case
```

WebSocket is not used between every backend service. In this design, WebSocket is mainly the persistent connection between the client and the Gateway Server.

---

## 1. Core Mental Model

```text
Gateway Server
  Owns client WebSocket connections.
  Knows which users are connected to this Gateway instance.
  Subscribes to Redis topics for events it may need to push.

Channel Server
  Owns message and channel business logic.
  Validates channel membership and permissions.
  Persists messages.
  Publishes message events to Redis.

Redis Pub/Sub
  Connects event producers to event consumers.
  Knows which Gateway TCP connections subscribed to which topics.

Presence Server
  Owns active, away, offline, DND, and typing state.
  Publishes presence/typing events through Redis.
```

One important correction:

```text
Channel Server usually does not maintain a direct in-memory list of all Gateway Servers.
```

Instead:

```text
Gateway subscribes to Redis.
Channel Server publishes to Redis.
Redis delivers the event to all subscribed Gateways.
```

---

## 2. What Gateway Server Stores

Gateway stores connection-oriented state. It does not own messages or channel history.

Example local Gateway state:

```text
Gateway GW-17

local_connections:
  U001 -> [ws_conn_101, ws_conn_102]
  U002 -> [ws_conn_205]
  U009 -> [ws_conn_310]

connection_metadata:
  ws_conn_101 -> {
    user_id: U001,
    workspace_id: T001,
    device: desktop,
    last_seen_message_id: 9001
  }

local_workspace_index:
  T001 -> [U001, U002, U009]
  T002 -> [U010, U011]

redis_subscriptions:
  workspace:T001
  workspace:T002
  presence:U001
  gateway:GW-17
```

Gateway may also store a short-lived mapping from a local user to subscribed channels:

```text
local_channel_membership_cache:
  U001 -> [C001, C002, C009]
  U002 -> [C001]
```

But this is usually a cache. The source of truth remains Channel Server and the database.

---

## 3. Does Gateway Store Channel Server List?

Gateway needs to call Channel Server when the client sends a message, edits a message, joins a channel, or loads channel-related data.

But Gateway usually does not hardcode a list like this:

```text
channel_servers = [CS-1, CS-2, CS-3]
```

Instead, Gateway calls a logical service name:

```text
channel-service.internal
```

That logical name is resolved by service discovery or a service mesh:

```text
Gateway
  -> channel-service.internal
  -> Kubernetes Service / Envoy / Consul / internal load balancer
  -> one healthy Channel Server instance
```

Common options:

```text
Kubernetes Service
Envoy or Linkerd service mesh
Consul or Eureka
DNS SRV records
Internal L4/L7 load balancer
gRPC client-side load balancing
```

So Gateway knows:

```text
How to reach ChannelService.
```

It does not need to know:

```text
Every Channel Server instance by hand.
```

---

## 4. Stateless Channel Server Routing

In a simple design, every Channel Server can process every channel.

```text
GW-17 -> ChannelService.SendMessage() -> CS-8
GW-03 -> ChannelService.SendMessage() -> CS-2
GW-42 -> ChannelService.SendMessage() -> CS-11
```

This works if all Channel Servers share the same backend data stores:

```text
MySQL/Vitess for durable messages
Redis for membership cache
Kafka for event log
Redis Pub/Sub for real-time fan-out
```

In this design, adding a Channel Server is easy:

```text
1. Start CS-20.
2. Register it as healthy.
3. Load balancer starts sending traffic to CS-20.
4. CS-20 reads/writes the same stores.
5. CS-20 publishes to the same Redis Pub/Sub topics.
```

No Gateway code change is required.

---

## 5. Sharded Channel Server Routing

At larger scale, Channel Servers may be sharded by workspace or channel.

Example:

```text
workspace T001 -> Channel shard A
workspace T002 -> Channel shard B
workspace T003 -> Channel shard C
```

The routing key is usually one of:

```text
workspace_id
channel_id
enterprise_org_id
```

For Slack-like systems, `workspace_id` is often a strong shard key because most operations are workspace-scoped.

Example:

```text
shard = consistent_hash(workspace_id)

T001 -> CS-8
T002 -> CS-9
T003 -> CS-8
T004 -> CS-12
```

Gateway still may not know the exact server. It can call a Channel Router:

```text
Gateway
  -> Channel Router
  -> correct Channel Server shard
```

Or the gRPC client/service mesh can route using metadata:

```text
gRPC metadata:
  workspace_id: T001
```

Then the routing layer chooses the right Channel Server.

---

## 6. What Happens When A Channel Server Is Added?

### Case A: Stateless Channel Servers

Adding `CS-20`:

```text
Before:
  CS-1, CS-2, CS-3

After:
  CS-1, CS-2, CS-3, CS-20
```

Impact:

```text
1. CS-20 registers with service discovery.
2. Health checks pass.
3. Load balancer starts routing some gRPC calls to CS-20.
4. Gateway does not need to update local code.
5. Redis Pub/Sub topic design does not change.
```

The new server simply becomes another worker that can process channel requests.

### Case B: Sharded Channel Servers

Adding `CS-20` may move some workspaces or channels:

```text
Before:
  T001 -> CS-8
  T002 -> CS-9
  T003 -> CS-8
  T004 -> CS-9

After adding CS-20:
  T001 -> CS-8
  T002 -> CS-9
  T003 -> CS-20
  T004 -> CS-9
```

Good systems use consistent hashing or an explicit shard map to avoid moving too much traffic.

What must be handled:

```text
Routing table update
Cache warmup
In-flight message handling
Idempotency using client_msg_id
Graceful drain from old owner
No duplicate message persistence
```

During migration, both old and new Channel Servers may briefly see traffic. The message write path must be idempotent:

```text
unique key:
  workspace_id + channel_id + client_msg_id
```

That prevents duplicate messages if retries happen.

---

## 7. Does Channel Server Maintain Gateway List?

Usually no.

Channel Server does not need this:

```text
channel_server.gateway_list = [GW-1, GW-2, GW-3, GW-4]
```

Instead, Channel Server publishes events:

```text
PUBLISH workspace:T001 "{message event}"
```

Redis already knows which Gateway instances are subscribed to `workspace:T001`.

This removes tight coupling:

```text
Channel Server does not care how many Gateways exist.
Gateway Server does not care which Channel Server published the event.
Redis connects them through topic subscriptions.
```

---

## 8. How Redis Pub/Sub Sends Message To Gateway

Redis Pub/Sub works over persistent TCP connections.

### Step 1: Gateway Connects To Redis

When `GW-17` starts, it opens a TCP connection to Redis:

```text
GW-17 -> Redis TCP connection
```

### Step 2: Gateway Subscribes

When users connect to `GW-17`, it subscribes to topics it needs:

```text
SUBSCRIBE workspace:T001
SUBSCRIBE workspace:T002
SUBSCRIBE gateway:GW-17
```

Redis internally tracks:

```text
workspace:T001 -> [tcp_connection_to_GW-17, tcp_connection_to_GW-03, tcp_connection_to_GW-42]
workspace:T002 -> [tcp_connection_to_GW-17, tcp_connection_to_GW-88]
gateway:GW-17 -> [tcp_connection_to_GW-17]
```

### Step 3: Channel Server Publishes

Channel Server receives and persists a message, then publishes:

```text
PUBLISH workspace:T001 "{
  \"type\": \"message\",
  \"workspace_id\": \"T001\",
  \"channel_id\": \"C001\",
  \"sender_id\": \"U001\",
  \"text\": \"hello\",
  \"ts\": \"1716547200.000100\",
  \"recipients\": [\"U002\", \"U003\", \"U004\"]
}"
```

### Step 4: Redis Writes To Subscriber Sockets

Redis looks up subscribers for `workspace:T001`.

Then Redis writes the message to each subscribed Gateway TCP connection:

```text
Redis -> GW-17 Redis client connection
Redis -> GW-03 Redis client connection
Redis -> GW-42 Redis client connection
```

### Step 5: Gateway Pushes To WebSocket Clients

Each Gateway receives the Pub/Sub event through its Redis client callback:

```text
onRedisMessage(event):
  parse event
  find local connected users
  filter by recipients/channel membership
  push to matching WebSocket connections
```

Example:

```text
GW-17 local users:
  U001, U002, U009

event recipients:
  U002, U003, U004

GW-17 pushes only to:
  U002
```

`U003` and `U004` are handled by other Gateway instances if they are connected there.

---

## 9. End-To-End Message Flow

```text
1. Alice sends message

   Alice Client
     -> WebSocket
   Gateway GW-17

2. Gateway calls Channel Server

   GW-17
     -> gRPC SendMessage()
   Channel Server CS-8

3. Channel Server validates and persists

   CS-8:
     - validate user is member of C001
     - check posting permission
     - assign message timestamp
     - write message to MySQL/Vitess
     - update unread counters/cache

4. Channel Server returns ACK

   CS-8
     -> gRPC response
   GW-17
     -> WebSocket ACK
   Alice Client

5. Channel Server publishes event

   CS-8
     -> Redis PUBLISH workspace:T001

6. Redis delivers to subscribed Gateways

   Redis
     -> GW-17
     -> GW-03
     -> GW-42

7. Gateways push to local WebSocket clients

   GW-17 -> Bob
   GW-03 -> Carol
   GW-42 -> Dave
```

---

## 10. Why Gateway Still Filters Pub/Sub Events

If Gateway subscribes at workspace level, it receives many events.

Example event:

```json
{
  "type": "message",
  "workspace_id": "T001",
  "channel_id": "C001",
  "sender_id": "U001",
  "recipients": ["U002", "U003", "U004"]
}
```

Gateway local state:

```text
GW-17 local users:
  U001
  U002
  U009
```

Gateway decision:

```text
U001: sender, maybe skip same connection but push to other devices
U002: recipient, push
U009: not recipient, skip
```

Filtering prevents leaking channel messages to users who should not receive them.

---

## 11. What Happens When A Gateway Server Is Added?

Suppose a new Gateway `GW-99` is added.

```text
Before:
  GW-17, GW-03, GW-42

After:
  GW-17, GW-03, GW-42, GW-99
```

Impact:

```text
1. GW-99 starts.
2. GW-99 registers as healthy in the load balancer.
3. New WebSocket connections may be routed to GW-99.
4. Existing WebSocket connections usually stay on old Gateways.
5. As users connect to GW-99, it subscribes to relevant Redis topics.
6. Redis starts sending matching Pub/Sub events to GW-99.
```

Channel Server does not need a code change.

Channel Server still does:

```text
PUBLISH workspace:T001 event
```

Redis handles the fact that another Gateway is now subscribed.

---

## 12. What Happens When A Gateway Server Dies?

Suppose `GW-17` crashes.

```text
1. Client WebSocket connections on GW-17 drop.
2. GW-17's Redis TCP subscription connection closes.
3. Redis removes GW-17 from subscriber lists automatically.
4. Clients reconnect through load balancer.
5. Some clients land on GW-03 or GW-99.
6. New Gateway restores session state and subscribes to needed Redis topics.
7. Client fetches missed messages from durable history if needed.
```

Redis Pub/Sub is not durable. If a Gateway was disconnected when an event was published, that event is missed by that Gateway.

Recovery is done through durable storage:

```text
Client reconnects with last_seen_message_id or last_ts.
Gateway asks Channel Server for missed messages.
Channel Server reads from DB/Kafka-backed history.
Client catches up.
```

---

## 13. What Happens When A New Slack Channel Is Created?

This means a user-visible channel like `#project-alpha`, not a new Channel Server instance.

Flow:

```text
1. Alice creates #project-alpha.

   Client
     -> REST/gRPC API
   Channel Server

2. Channel Server checks permission.

   Channel Server
     -> Admin Server CheckPermission()

3. Channel Server writes channel metadata.

   INSERT INTO channels (...)
   INSERT INTO channel_members (...)

4. Channel Server publishes event.

   PUBLISH workspace:T001 "{
     \"type\": \"channel_created\",
     \"channel_id\": \"C999\",
     \"name\": \"project-alpha\"
   }"

5. Gateways subscribed to workspace:T001 receive the event.

6. Gateways push to connected clients.

7. Clients show the new channel in sidebar/search.
```

No new Gateway Server is required. No new Channel Server instance is required.

---

## 14. Pub/Sub Topic Design Options

### Workspace-Level Topic

```text
workspace:T001
```

Pros:

```text
Simple subscription model.
Good for workspace-wide events.
New channels do not require new subscriptions.
```

Cons:

```text
Gateways receive extra events and must filter locally.
Can become noisy for very large workspaces.
```

### Channel-Level Topic

```text
channel:C001
```

Pros:

```text
Less overdelivery.
Good for very high-traffic channels.
```

Cons:

```text
Many users are in many channels.
Gateways may need many subscriptions.
Subscription churn increases when users join/leave/switch workspace.
```

### Gateway-Level Topic

```text
gateway:GW-17
```

Pros:

```text
Very targeted delivery.
Useful for control messages like force disconnect.
Useful when Channel Server groups recipients by Gateway.
```

Cons:

```text
Requires accurate user-to-gateway mapping.
More complex during reconnects and Gateway failures.
```

### User-Level Topic

```text
user:U001
```

Pros:

```text
Precise direct delivery.
Good for low-volume personal events.
```

Cons:

```text
Huge number of topics.
Harder to scale for every event.
```

Large systems often combine these:

```text
workspace:T001       broad workspace events
channel:C001         high-volume channel events
presence:U001        presence watcher events
gateway:GW-17        gateway-specific control commands
```

---

## 15. Optimized Fan-Out With User-To-Gateway Mapping

At high scale, Channel Server may avoid broad workspace fan-out by grouping recipients by Gateway.

Session registry:

```text
Redis:
  HSET user_gateway:T001 U001 GW-17
  HSET user_gateway:T001 U002 GW-17
  HSET user_gateway:T001 U003 GW-03
  HSET user_gateway:T001 U004 GW-42
```

Message recipients:

```text
U002 -> GW-17
U003 -> GW-03
U004 -> GW-42
```

Channel Server groups recipients:

```text
GW-17 -> [U002]
GW-03 -> [U003]
GW-42 -> [U004]
```

Then publishes targeted events:

```text
PUBLISH gateway:GW-17 "{recipients:[U002], message:{...}}"
PUBLISH gateway:GW-03 "{recipients:[U003], message:{...}}"
PUBLISH gateway:GW-42 "{recipients:[U004], message:{...}}"
```

This reduces unnecessary Gateway work.

Tradeoff:

```text
The system must keep user-to-gateway mapping fresh.
It must handle multi-device users.
It must remove stale mappings when a Gateway crashes.
It must handle reconnect races.
```

For example, a user may be connected from desktop and mobile:

```text
U001 -> [GW-17:desktop, GW-42:mobile]
```

So the mapping is often:

```text
user_id -> set of active connection locations
```

not a single Gateway.

---

## 16. Presence Server Pub/Sub Flow

Presence uses the same pattern as messages, but the data is more ephemeral.

Example: Bob becomes away.

```text
1. Bob client sends heartbeat.

   Bob Client
     -> WebSocket ping/activity
   Gateway GW-17

2. Gateway reports activity.

   GW-17
     -> gRPC PresenceService.ReportActivity()
   Presence Server

3. Presence Server updates state.

   HSET presence:U002 status away last_activity 1716547200

4. Presence Server finds watchers.

   SMEMBERS presence_watchers:U002
     -> [U001, U003, U007]

5. Presence Server publishes event.

   PUBLISH presence:U002 "{
     \"type\": \"presence_change\",
     \"user_id\": \"U002\",
     \"presence\": \"away\",
     \"watchers\": [\"U001\", \"U003\", \"U007\"]
   }"

6. Gateways receive event and push to local watcher clients.
```

Typing indicator:

```text
1. Alice starts typing in C001.
2. Client sends typing event to Gateway.
3. Gateway calls PresenceService.StartTyping().
4. Presence Server sets TTL key:

   SETEX typing:C001:U001 5 "1"

5. Presence Server publishes:

   PUBLISH channel:C001 "{
     \"type\": \"user_typing\",
     \"channel_id\": \"C001\",
     \"user_id\": \"U001\"
   }"

6. Gateways push only to users currently viewing C001.
7. If no more typing events arrive, TTL expires and UI clears typing indicator.
```

---

## 17. Where gRPC Fits

gRPC is used when one service needs to ask another service to perform an operation and return a response.

Examples:

```text
Gateway -> Channel Server:
  SendMessage()
  EditMessage()
  FetchMissedMessages()

Gateway -> Presence Server:
  ReportActivity()
  StartTyping()
  SubscribePresence()

Channel Server -> Admin Server:
  CheckPermission()
  GetWorkspacePolicy()

Admin Server -> Gateway:
  DisconnectUser()     optional; often event-based instead
```

Example proto-style interface:

```protobuf
service ChannelService {
  rpc SendMessage(SendMessageRequest) returns (SendMessageResponse);
  rpc FetchMissedMessages(FetchMissedMessagesRequest) returns (FetchMissedMessagesResponse);
}

message SendMessageRequest {
  string workspace_id = 1;
  string channel_id = 2;
  string user_id = 3;
  string text = 4;
  string client_msg_id = 5;
}

message SendMessageResponse {
  bool ok = 1;
  string message_ts = 2;
  string error = 3;
}
```

Use gRPC for:

```text
Synchronous request/response
Typed contracts
Low-latency internal service calls
Deadlines, retries, cancellation, load balancing
```

Use Redis Pub/Sub for:

```text
Async fan-out
Gateway event delivery
Presence updates
Typing indicators
Workspace/channel broadcasts
```

---

## 18. Redis Pub/Sub Delivery Semantics

Redis Pub/Sub is fast, but it is not durable.

Important behavior:

```text
If Gateway is subscribed and connected, it receives the event.
If Gateway is disconnected at publish time, it misses the event.
Redis Pub/Sub does not replay old messages.
```

That is why real chat messages must be persisted before fan-out:

```text
1. Write message to durable store.
2. Publish real-time event.
3. If client misses event, fetch missed messages on reconnect.
```

For durable event replay, use Kafka or database history:

```text
Redis Pub/Sub:
  low latency, ephemeral delivery

Kafka:
  durable ordered event log

MySQL/Vitess:
  source of truth for message history
```

---

## 19. Final Summary

```text
Gateway knows:
  - local WebSocket connections
  - local user/session/device state
  - Redis topics it subscribed to
  - logical backend service names for gRPC calls

Channel Server knows:
  - channel membership
  - message validation rules
  - persistence logic
  - which Redis topic to publish after a message is accepted

Redis knows:
  - channel/topic -> subscribed TCP connections
  - which Gateway Redis clients should receive each published event

Presence Server knows:
  - user activity state
  - typing TTLs
  - presence watchers
  - which presence/typing events to publish
```

Best short version:

```text
Gateway pulls events from Redis subscriptions.
Channel Server pushes message events into Redis.
Presence Server pushes presence events into Redis.
Redis delivers events to subscribed Gateway TCP connections.
Gateway pushes final events to clients over WebSocket.
```

