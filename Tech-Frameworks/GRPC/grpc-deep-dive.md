# gRPC Deep Dive for System Design

## Table of Contents

1. [What gRPC Is](#1-what-grpc-is)
2. [Why gRPC Exists](#2-why-grpc-exists)
3. [Core Building Blocks](#3-core-building-blocks)
4. [How a gRPC Call Works Internally](#4-how-a-grpc-call-works-internally)
5. [Protocol Buffers and Contract Design](#5-protocol-buffers-and-contract-design)
6. [The Four Types of gRPC Streaming](#6-the-four-types-of-grpc-streaming)
7. [Channels, Stubs, Connections, and Servers](#7-channels-stubs-connections-and-servers)
8. [Deadlines, Timeouts, and Cancellation](#8-deadlines-timeouts-and-cancellation)
9. [Retry Mechanism](#9-retry-mechanism)
10. [Load Balancing](#10-load-balancing)
11. [Scalability](#11-scalability)
12. [Reliability and Fault Tolerance](#12-reliability-and-fault-tolerance)
13. [Backpressure, Flow Control, and Streaming Reliability](#13-backpressure-flow-control-and-streaming-reliability)
14. [Security](#14-security)
15. [Observability](#15-observability)
16. [Performance Characteristics](#16-performance-characteristics)
17. [gRPC vs REST vs WebSocket](#17-grpc-vs-rest-vs-websocket)
18. [Production Architecture Patterns](#18-production-architecture-patterns)
19. [Common Pitfalls](#19-common-pitfalls)
20. [Interview-Ready Summary](#20-interview-ready-summary)
21. [References](#21-references)

---

## 1. What gRPC Is

gRPC is a high-performance Remote Procedure Call framework. It lets one service
call a method on another service as if it were a local function, while gRPC
handles serialization, networking, deadlines, cancellation, load balancing,
retries, streaming, and error status propagation.

At a high level:

```text
Client application
  -> generated client stub
  -> gRPC client runtime
  -> HTTP/2 connection
  -> gRPC server runtime
  -> generated server interface
  -> service implementation
```

Example mental model:

```text
Instead of:

POST /payments/authorize
Content-Type: application/json

{
  "user_id": "u1",
  "amount": 500
}

You define:

rpc AuthorizePayment(AuthorizePaymentRequest)
    returns (AuthorizePaymentResponse);
```

The service contract is usually written in Protocol Buffers:

```proto
syntax = "proto3";

service PaymentService {
  rpc AuthorizePayment(AuthorizePaymentRequest)
      returns (AuthorizePaymentResponse);
}

message AuthorizePaymentRequest {
  string user_id = 1;
  int64 amount_cents = 2;
  string currency = 3;
}

message AuthorizePaymentResponse {
  string authorization_id = 1;
  string status = 2;
}
```

From this `.proto` file, gRPC tooling generates client and server code for
languages such as Java, Go, Python, Node.js, C++, C#, Ruby, PHP, Kotlin, Dart,
and others.

## 2. Why gRPC Exists

Traditional service-to-service HTTP APIs are simple and universal, but they have
some limitations in large distributed systems:

- JSON is text-heavy and slower to parse than compact binary formats.
- API contracts are often informal unless OpenAPI discipline is strong.
- Streaming is not ergonomic with plain REST.
- Deadlines, cancellation, retries, metadata, and status codes are often
  implemented differently by every team.
- Cross-language generated clients require extra tooling.

gRPC solves these problems by combining:

- A strongly typed interface definition language.
- Binary serialization using Protocol Buffers by default.
- HTTP/2 as the transport.
- Built-in unary and streaming RPCs.
- Standard status codes.
- Metadata headers and trailers.
- Deadlines and cancellation.
- Client-side load balancing support.
- Retry and service configuration mechanisms.
- Generated client and server bindings across languages.

The biggest design goal is efficient, strongly typed service-to-service
communication.

## 3. Core Building Blocks

### Service

A service is a collection of RPC methods.

```proto
service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
  rpc ListUserEvents(ListUserEventsRequest) returns (stream UserEvent);
}
```

### Method

A method defines one RPC endpoint. It has one request type and one response
type. Either side can be a stream.

### Message

A message is the structured payload.

```proto
message GetUserRequest {
  string user_id = 1;
}
```

### Stub

A stub is generated client code. The application calls the stub; the stub
serializes the request, sends it over the network, waits for the response, and
deserializes it.

```text
Application code -> generated stub -> gRPC runtime -> network
```

### Server Implementation

The generated server interface is implemented by your business logic.

```text
Network -> gRPC runtime -> generated service interface -> business handler
```

### Channel

A channel represents a logical connection to a service. It can manage one or
more underlying HTTP/2 connections, name resolution, load balancing,
connectivity state, TLS, interceptors, and retries.

In most languages, channels are intended to be reused instead of created per
request.

### Metadata

Metadata is key-value information sent with calls. It is used for things such
as:

- Authentication tokens.
- Request IDs.
- Trace IDs.
- Tenant IDs.
- Client version.
- Feature flags.

Metadata is not the business payload. It is closer to HTTP headers.

### Status

Every gRPC call completes with a status code and optional status message.

Common status codes:

| Status | Meaning | Common use |
|---|---|---|
| `OK` | Success | RPC completed |
| `INVALID_ARGUMENT` | Bad request | Validation failed |
| `NOT_FOUND` | Missing resource | User/order/file not found |
| `ALREADY_EXISTS` | Duplicate resource | Create conflict |
| `PERMISSION_DENIED` | Caller lacks permission | Authz failure |
| `UNAUTHENTICATED` | No valid identity | Missing/invalid token |
| `RESOURCE_EXHAUSTED` | Quota or rate limit hit | Load shedding |
| `FAILED_PRECONDITION` | System not in required state | Invalid workflow state |
| `ABORTED` | Concurrency conflict | Transaction conflict |
| `UNAVAILABLE` | Service temporarily unavailable | Retryable transient failure |
| `DEADLINE_EXCEEDED` | Deadline expired | Timeout |
| `CANCELLED` | Caller cancelled | Client closed or context cancelled |
| `INTERNAL` | Server bug or invariant failure | Unexpected server error |

Good gRPC systems use status codes deliberately. Do not return `INTERNAL` for
everything.

## 4. How a gRPC Call Works Internally

For a unary call:

```text
1. Application calls generated client stub.
2. Stub validates method shape and serializes request message.
3. Client interceptor chain runs.
4. gRPC runtime attaches metadata, deadline, compression flags, and method path.
5. Channel resolves service name to one or more backends.
6. Load balancer policy picks a subchannel/backend.
7. Request is sent as an HTTP/2 stream.
8. Server receives headers and request message.
9. Server interceptor chain runs.
10. Service handler executes business logic.
11. Server serializes response.
12. Server sends response message and trailing status.
13. Client receives response and status.
14. Stub returns response or raises an RPC error.
```

### HTTP/2 Transport

gRPC uses HTTP/2 for its standard transport.

Important HTTP/2 properties:

- One TCP connection can carry many concurrent streams.
- Each RPC is usually one HTTP/2 stream.
- Streams are multiplexed, so multiple calls can be in flight at once.
- Headers are compressed.
- Binary frames are used instead of plain text HTTP/1.1 messages.
- Flow control exists at both connection and stream levels.
- Long-lived connections are normal.

Basic mapping:

```text
gRPC channel
  -> HTTP/2 connection
      -> stream 1: GetUser RPC
      -> stream 3: CreateOrder RPC
      -> stream 5: WatchInventory RPC
```

### Request and Response Framing

Each gRPC message is length-prefixed inside HTTP/2 DATA frames.

Conceptually:

```text
Compressed flag: 1 byte
Message length: 4 bytes
Message bytes: N bytes
```

The HTTP/2 stream carries:

```text
Request headers
Request message(s)
Response headers
Response message(s)
Response trailers with grpc-status
```

gRPC status is commonly sent in trailers, not just normal HTTP status.

### Method Path

The HTTP/2 path generally looks like:

```text
/package.Service/Method
```

Example:

```text
/payments.PaymentService/AuthorizePayment
```

### Why HTTP/2 Matters

HTTP/2 gives gRPC several advantages:

- Fewer TCP connections than HTTP/1.1 request-per-connection patterns.
- Efficient multiplexing for high concurrency.
- Native bidirectional streaming.
- Better use of TLS sessions and connection warmup.
- Standard flow control.

But it also introduces operational concerns:

- Long-lived connections can make load distribution sticky.
- One overloaded connection can become a bottleneck.
- Concurrent stream limits must be tuned.
- Proxies must support HTTP/2 correctly.
- Connection draining matters during deploys.

## 5. Protocol Buffers and Contract Design

Protocol Buffers are the default interface and serialization format for gRPC.

### Why Protobuf Is Useful

- Compact binary encoding.
- Fast serialization and deserialization.
- Strong schema.
- Backward-compatible evolution when used correctly.
- Multi-language code generation.
- Clear distinction between field name and field number.

### Field Numbers Matter

In protobuf, field numbers are the wire contract.

```proto
message User {
  string id = 1;
  string email = 2;
  string display_name = 3;
}
```

The field names are for readability and generated code. The field numbers are
what make decoding possible on the wire.

### Schema Evolution Rules

Safe changes:

- Add a new optional field with a new number.
- Stop writing a field but keep its number reserved.
- Add new enum values carefully.
- Add new RPC methods to a service.

Risky or breaking changes:

- Reusing a deleted field number.
- Changing a field type incompatibly.
- Renaming services or methods without migration.
- Changing request/response semantics while keeping the same method name.
- Removing fields that old clients still need.
- Changing enum defaults carelessly.

Use `reserved` for deleted fields:

```proto
message User {
  reserved 4, 7;
  reserved "old_status";

  string id = 1;
  string email = 2;
}
```

### API Design Guidelines

Prefer clear domain operations:

```proto
rpc GetUser(GetUserRequest) returns (GetUserResponse);
rpc CreateOrder(CreateOrderRequest) returns (CreateOrderResponse);
rpc CancelOrder(CancelOrderRequest) returns (CancelOrderResponse);
```

Avoid generic RPCs:

```proto
rpc Execute(Command) returns (Result);
rpc Handle(GenericRequest) returns (GenericResponse);
```

Generic methods erase type safety and make observability, authorization, and
backward compatibility harder.

### Request Design

Good request messages include:

- The resource identifier.
- Caller intent.
- Pagination fields for list calls.
- Idempotency key for retryable mutations.
- Optional field masks for partial updates.
- Explicit filters and sort options.

Example:

```proto
message CreatePaymentRequest {
  string idempotency_key = 1;
  string user_id = 2;
  int64 amount_cents = 3;
  string currency = 4;
}
```

### Response Design

Good responses include:

- The created or fetched resource.
- Server-generated IDs.
- State transitions.
- Pagination tokens.
- Machine-readable status when domain-level status is needed.

Avoid putting transport errors inside successful responses unless the operation
really succeeded from the transport perspective.

## 6. The Four Types of gRPC Streaming

gRPC supports four RPC shapes:

```proto
service ExampleService {
  rpc Unary(Request) returns (Response);
  rpc ServerStreaming(Request) returns (stream Response);
  rpc ClientStreaming(stream Request) returns (Response);
  rpc BidirectionalStreaming(stream Request) returns (stream Response);
}
```

### 6.1 Unary RPC

Unary RPC is one request and one response.

```proto
rpc GetUser(GetUserRequest) returns (GetUserResponse);
```

Flow:

```text
Client -> request -> Server
Client <- response <- Server
```

Use cases:

- Fetch user profile.
- Create order.
- Authorize payment.
- Validate token.
- Read configuration.

Characteristics:

- Closest to a normal HTTP request-response API.
- Easiest to load balance.
- Easiest to retry safely for idempotent operations.
- Best default for simple APIs.

Design guidance:

- Always set a deadline.
- Use idempotency keys for retryable mutations.
- Keep payloads bounded.
- Use pagination instead of returning huge lists.

### 6.2 Server Streaming RPC

Server streaming is one request and multiple responses.

```proto
rpc ListUserEvents(ListUserEventsRequest) returns (stream UserEvent);
```

Flow:

```text
Client -> request -> Server
Client <- event 1 <- Server
Client <- event 2 <- Server
Client <- event 3 <- Server
...
```

Use cases:

- Download a large result set.
- Subscribe to live updates.
- Watch inventory changes.
- Tail logs.
- Stream recommendations.
- Receive progress events for a long-running job.

Characteristics:

- Client sends one request.
- Server sends a sequence of messages.
- Server controls message pacing, but HTTP/2 flow control applies.
- The stream ends with final gRPC status.

Example design:

```proto
message WatchOrderRequest {
  string order_id = 1;
}

message OrderEvent {
  string order_id = 1;
  string status = 2;
  int64 sequence = 3;
}

service OrderService {
  rpc WatchOrder(WatchOrderRequest) returns (stream OrderEvent);
}
```

Reliability concerns:

- Long-lived streams can break during deploys, network changes, or client
  restarts.
- Retrying from the beginning may duplicate events.
- Include sequence numbers or resume tokens for durable streams.
- Use heartbeats if business messages may be sparse.
- Apply server-side limits to avoid infinite resource usage.

### 6.3 Client Streaming RPC

Client streaming is multiple requests and one response.

```proto
rpc UploadTelemetry(stream TelemetryPoint) returns (UploadSummary);
```

Flow:

```text
Client -> point 1 -> Server
Client -> point 2 -> Server
Client -> point 3 -> Server
...
Client -> half-close
Client <- summary <- Server
```

Use cases:

- Upload telemetry batches.
- Upload file chunks.
- Send sensor readings.
- Send route points.
- Bulk import records.

Characteristics:

- Client sends many messages.
- Server usually aggregates or processes incrementally.
- Server sends one final response.
- Client indicates it has finished by half-closing the send side.

Example design:

```proto
message UploadChunk {
  string upload_id = 1;
  int64 offset = 2;
  bytes data = 3;
}

message UploadSummary {
  string upload_id = 1;
  int64 bytes_received = 2;
}

service FileService {
  rpc UploadFile(stream UploadChunk) returns (UploadSummary);
}
```

Reliability concerns:

- If the stream fails halfway, the server may have processed only part of it.
- Use upload IDs and offsets for resumability.
- Make chunks idempotent.
- Enforce max message size and max stream duration.
- Do not buffer the whole stream in memory.

### 6.4 Bidirectional Streaming RPC

Bidirectional streaming is multiple requests and multiple responses.

```proto
rpc Chat(stream ChatMessage) returns (stream ChatMessage);
```

Flow:

```text
Client -> message A -> Server
Client <- message B <- Server
Client -> message C -> Server
Client <- message D <- Server
...
```

Both sides can read and write independently. The request stream and response
stream are logically independent, though they share one HTTP/2 stream.

Use cases:

- Chat.
- Multiplayer game sessions.
- Collaborative editing.
- Real-time trading updates.
- Interactive command sessions.
- Voice/video signaling.
- Long-lived agent control channels.

Example design:

```proto
message SessionMessage {
  string session_id = 1;
  int64 sequence = 2;
  oneof payload {
    ClientCommand command = 3;
    ServerEvent event = 4;
    Heartbeat heartbeat = 5;
  }
}

service SessionService {
  rpc Connect(stream SessionMessage) returns (stream SessionMessage);
}
```

Reliability concerns:

- Ordering is guaranteed within a single stream, but not across multiple
  streams or reconnections.
- Long-lived streams need heartbeat, reconnect, and resume logic.
- Server deploys require graceful draining.
- Backpressure must be respected on both send paths.
- Retries are not enough for durable bidirectional sessions; design application
  level recovery.

### Streaming Comparison

| RPC type | Request shape | Response shape | Best for | Retry complexity |
|---|---:|---:|---|---|
| Unary | One | One | Normal APIs | Low |
| Server streaming | One | Many | Watch, list, subscribe | Medium |
| Client streaming | Many | One | Upload, aggregate, batch | Medium |
| Bidirectional streaming | Many | Many | Interactive real time | High |

## 7. Channels, Stubs, Connections, and Servers

### Channel Lifecycle

A channel is expensive enough that you normally create it once and reuse it.

Bad:

```text
For every request:
  create channel
  create stub
  call RPC
  close channel
```

Good:

```text
On application startup:
  create channel
  create stub

For every request:
  reuse stub/channel

On shutdown:
  close channel gracefully
```

Why reuse channels:

- TLS handshakes are expensive.
- HTTP/2 connection warmup takes time.
- Connection pooling and load balancing state need to stabilize.
- Creating too many connections can overload clients, servers, and proxies.

### Subchannel

Many gRPC implementations model each backend connection as a subchannel. A
channel may manage multiple subchannels when client-side load balancing is
enabled.

```text
Logical channel: dns:///payment-service

Subchannels:
  10.0.1.10:50051
  10.0.1.11:50051
  10.0.1.12:50051
```

### Stub Types

Depending on language, stubs may be:

- Blocking/synchronous.
- Future/promise based.
- Async/callback based.
- Reactive stream based.

Use the style that matches the service's concurrency model.

### Server Threading and Event Loops

Server internals vary by language:

- Java often uses Netty event loops and executor pools.
- Go uses goroutines.
- Node.js uses event loop based concurrency.
- C++ has synchronous and asynchronous server APIs.

Production concern:

```text
Do not block event loop threads with slow database calls, file I/O, or CPU-heavy
work. Separate network I/O from business execution where the runtime requires it.
```

### Interceptors

Interceptors are middleware around RPC calls.

Common uses:

- Authentication.
- Authorization.
- Logging.
- Metrics.
- Tracing.
- Deadline enforcement.
- Request validation.
- Rate limiting.
- Error mapping.
- Metadata injection.

Typical flow:

```text
Client call
  -> client auth interceptor
  -> client tracing interceptor
  -> client retry/deadline runtime
  -> network
  -> server tracing interceptor
  -> server auth interceptor
  -> handler
```

## 8. Deadlines, Timeouts, and Cancellation

### Timeout vs Deadline

A timeout is a duration:

```text
Wait up to 200 ms.
```

A deadline is an absolute point in time:

```text
Fail if not complete by 10:00:00.200.
```

gRPC APIs often expose deadlines or timeout-like helpers depending on language.
The operational idea is the same: the call must not wait forever.

### Why Deadlines Are Mandatory

Without deadlines:

- Clients can wait indefinitely.
- Server resources remain pinned.
- Cascading failures become worse.
- Retries can amplify load.
- Tail latency gets unbounded.
- Thread pools and connection pools can saturate.

Every production gRPC call should have a deadline.

### Deadline Flow

```text
Client receives HTTP request with 800 ms budget
  -> calls UserService with 200 ms deadline
  -> calls PaymentService with 300 ms deadline
  -> calls InventoryService with 150 ms deadline
  -> keeps remaining budget for response assembly
```

### Deadline Propagation

When service A calls service B during an incoming RPC, it should propagate the
remaining time budget instead of creating a fresh large timeout.

Bad:

```text
External request deadline: 500 ms
Service A -> Service B timeout: 5 seconds
```

Good:

```text
External request deadline: 500 ms
After 120 ms spent in Service A:
Service A -> Service B deadline: remaining 380 ms, or a smaller per-call cap
```

This prevents internal calls from continuing after the user-facing request has
already failed.

### Server-Side Deadline Handling

Servers should check cancellation/deadline state while doing work.

Conceptually:

```text
if request context is cancelled:
  stop expensive work
  release resources
  avoid writing useless downstream requests
```

This matters for:

- Database scans.
- External API calls.
- Long loops.
- Streaming handlers.
- File uploads/downloads.
- ML inference jobs.

### Choosing Timeout Values

Timeouts should be based on:

- User-facing latency budget.
- Service p95/p99 latency.
- Network distance.
- Dependency latency.
- Retry budget.
- Business criticality.

Example:

```text
End-user checkout API budget: 1 second

Auth RPC:       75 ms
Cart RPC:      100 ms
Inventory RPC: 200 ms
Payment RPC:   400 ms
Buffer:        225 ms
```

### Common Deadline Mistakes

- No deadline.
- Same large timeout for every dependency.
- Timeout longer than the caller's timeout.
- Retrying without considering remaining deadline.
- Treating `DEADLINE_EXCEEDED` as always safe to retry.
- Ignoring cancellation in server handlers.
- Setting timeouts so low that normal p99 traffic fails.

## 9. Retry Mechanism

Retries help with transient failures. They do not fix persistent overload,
incorrect data, non-idempotent mutations, or bad capacity planning.

### Transparent Retries

gRPC can perform limited transparent retries for low-level races where the
request is known not to have been processed by application logic. This can
happen even without a user-defined retry policy.

Transparent retry is intentionally conservative.

### Configured Retries

More explicit retry behavior is configured through gRPC service config in
implementations that support it.

Example service config:

```json
{
  "methodConfig": [
    {
      "name": [
        {
          "service": "payments.PaymentService",
          "method": "GetPayment"
        }
      ],
      "timeout": "1s",
      "retryPolicy": {
        "maxAttempts": 4,
        "initialBackoff": "0.1s",
        "maxBackoff": "1s",
        "backoffMultiplier": 2,
        "retryableStatusCodes": [
          "UNAVAILABLE"
        ]
      }
    }
  ],
  "retryThrottling": {
    "maxTokens": 10,
    "tokenRatio": 0.1
  }
}
```

Important fields:

| Field | Meaning |
|---|---|
| `maxAttempts` | Total attempts, including the first call |
| `initialBackoff` | Delay before the first retry |
| `maxBackoff` | Upper bound on retry delay |
| `backoffMultiplier` | Exponential backoff multiplier |
| `retryableStatusCodes` | Status codes that can trigger retry |
| `retryThrottling` | Limits retries when failures are widespread |

### Retryable Status Codes

Common retryable codes:

- `UNAVAILABLE`: backend temporarily unavailable.
- `DEADLINE_EXCEEDED`: sometimes retryable, but only if the operation is safe
  and the caller still has budget.
- `RESOURCE_EXHAUSTED`: sometimes retryable after backoff, especially for
  quota/rate limit cases.
- `ABORTED`: retryable for some concurrency conflicts.

Usually not retryable:

- `INVALID_ARGUMENT`
- `NOT_FOUND`
- `PERMISSION_DENIED`
- `UNAUTHENTICATED`
- `ALREADY_EXISTS`
- `FAILED_PRECONDITION`

### Idempotency

Retry safety depends on idempotency.

Safe to retry:

```text
GetUser(user_id)
ListOrders(user_id)
CheckInventory(sku)
```

Unsafe unless designed carefully:

```text
ChargeCreditCard(amount)
CreateOrder(cart)
SendEmail(message)
TransferMoney(source, destination, amount)
```

For retryable mutations, use idempotency keys:

```proto
message CreateOrderRequest {
  string idempotency_key = 1;
  string user_id = 2;
  repeated OrderItem items = 3;
}
```

Server behavior:

```text
If idempotency_key is new:
  perform operation
  store result by key
  return result

If idempotency_key already exists:
  return previous result
```

### Exponential Backoff and Jitter

Retries should use exponential backoff:

```text
100 ms -> 200 ms -> 400 ms -> 800 ms
```

Jitter randomizes retry delays:

```text
client A retries after 182 ms
client B retries after 237 ms
client C retries after 119 ms
```

Without jitter, many clients retry at the same time and create a retry storm.

### Retry Budget

Retries must fit inside the original deadline.

Example:

```text
Overall deadline: 500 ms

Attempt 1: 120 ms, fails UNAVAILABLE
Backoff:    50 ms
Attempt 2: 180 ms, fails UNAVAILABLE
Backoff:   100 ms
Remaining: 50 ms

Attempt 3 should probably not start if it cannot complete usefully.
```

### Retry Commit Point

Once the server has processed the request enough to send response headers or
application data, automatic retry becomes unsafe because the client cannot know
whether side effects happened.

For streaming RPCs, automatic retry is especially constrained. If a stream fails
after messages were exchanged, the application usually needs explicit resume
logic rather than relying on generic retries.

### Hedging

Hedging sends another attempt before the first attempt has failed, usually after
a short delay.

```text
t = 0 ms: send attempt 1 to backend A
t = 30 ms: no response yet, send attempt 2 to backend B
t = 45 ms: backend B responds, cancel attempt 1
```

Hedging can reduce tail latency, but it increases load. Use it only for:

- Idempotent reads.
- Strictly bounded attempts.
- Systems with spare capacity.
- Carefully chosen latency-sensitive paths.

### Retry Anti-Patterns

- Retrying every error.
- Retrying non-idempotent mutations without idempotency keys.
- Retrying longer than the caller deadline.
- Retrying during overload without throttling.
- Retrying from every layer in the call chain.
- Retrying long-lived streams without resume tokens.

## 10. Load Balancing

Load balancing gRPC is different from simple HTTP/1.1 request balancing because
gRPC uses long-lived HTTP/2 connections and multiplexed streams.

### The Core Problem

With HTTP/1.1:

```text
Request 1 -> load balancer -> backend A
Request 2 -> load balancer -> backend B
Request 3 -> load balancer -> backend C
```

With gRPC over HTTP/2:

```text
Client opens one long-lived HTTP/2 connection to backend A
RPC 1 -> backend A
RPC 2 -> backend A
RPC 3 -> backend A
...
```

If the load balancer only balances connections, traffic may become uneven.

### Load Balancing Models

There are three common models.

### 10.1 Proxy Load Balancing

A proxy sits between clients and servers.

```text
Client
  -> Envoy / NGINX / cloud load balancer
  -> gRPC servers
```

Advantages:

- Centralized traffic management.
- Works with simple clients.
- Easier policy rollout.
- Can provide TLS termination, metrics, retries, routing, and circuit breaking.
- Common in Kubernetes and service mesh architectures.

Disadvantages:

- Extra network hop.
- Proxy can become a bottleneck if undersized.
- HTTP/2 support must be correct.
- Load may still be connection-balanced depending on proxy behavior.

Use when:

- You run a service mesh.
- You need consistent traffic policy.
- You expose services across clusters or networks.
- Clients cannot support advanced gRPC load balancing.

### 10.2 Client-Side Load Balancing

The gRPC client knows about multiple backends and chooses one per call.

```text
Client channel
  -> resolver returns [A, B, C]
  -> LB policy chooses backend per RPC
  -> call goes directly to selected backend
```

Advantages:

- No extra proxy hop.
- Better per-RPC balancing.
- Client can react directly to backend health.
- Scales horizontally without central proxy bottleneck.

Disadvantages:

- More complexity in clients.
- Requires service discovery integration.
- Policy consistency can be harder across languages.
- Each client maintains connections to multiple backends.

Use when:

- You control client code.
- You need high throughput and low latency.
- Service discovery is mature.
- Language support is consistent.

### 10.3 Lookaside Load Balancing

The client asks a load balancing service for backend choices or policy.

```text
Client -> load balancing control plane
Client -> selected backend
```

This is less common than proxy-based or normal client-side load balancing in
typical application teams, but the pattern appears in advanced service mesh and
control-plane designs.

### Name Resolution

The channel target is resolved into addresses.

Examples:

```text
dns:///payment-service.default.svc.cluster.local:50051
xds:///payment-service
```

Resolvers can use:

- DNS.
- Kubernetes service discovery.
- Consul.
- etcd.
- xDS control planes.
- Custom resolvers.

### Load Balancing Policies

Common policies:

| Policy | Behavior | Use case |
|---|---|---|
| `pick_first` | Connect to the first usable address | Simple, low connection count |
| `round_robin` | Rotate calls across backends | Better distribution |
| xDS policies | Control-plane driven routing | Service mesh, advanced routing |

Example service config:

```json
{
  "loadBalancingConfig": [
    {
      "round_robin": {}
    }
  ]
}
```

### Kubernetes Load Balancing

Common setup:

```text
Client pod -> Kubernetes Service -> server pods
```

Potential issue:

- Kubernetes Service load balances connections.
- gRPC keeps long-lived HTTP/2 connections.
- A client may stick to one backend for a long time.

Better options:

- Use an L7 proxy with gRPC support.
- Use a headless service plus gRPC client-side round-robin.
- Use a service mesh such as Envoy-based xDS.
- Increase connection count carefully if client-side LB is not available.

### Health Checking

gRPC has a standard health checking protocol. A client can watch backend health
and avoid sending calls to unhealthy backends when supported by the load
balancing policy and implementation.

Conceptual flow:

```text
Client connects to backend
Client starts health Watch RPC
Backend reports SERVING
Client sends application RPCs
Backend reports NOT_SERVING
Client stops routing new RPCs to that backend
```

Health checks should represent real readiness:

- Server is started.
- Dependencies required for serving are available.
- Instance is not draining.
- Critical background initialization is complete.

Do not report healthy just because the process is alive.

### Load Balancing for Streaming

Streaming calls are harder to balance than unary calls.

Unary:

```text
Every call can be balanced independently.
```

Long-lived stream:

```text
One stream may stay on one backend for minutes or hours.
```

Implications:

- Backends can become unevenly loaded.
- Deploy draining takes longer.
- Per-connection limits matter.
- Hot users or tenants may pin to one backend.

Mitigations:

- Use max stream duration with graceful reconnect.
- Use resume tokens.
- Shard by tenant/session when necessary.
- Monitor active stream count per backend.
- Drain streams during deployments.
- Avoid putting too many unrelated subscriptions on one stream unless the server
  can isolate them internally.

## 11. Scalability

Scalability in gRPC systems depends on connection management, concurrency,
payload size, streaming behavior, service discovery, and downstream bottlenecks.

### Horizontal Scaling

The normal scaling model:

```text
Client fleet
  -> service discovery / load balancing
  -> N stateless gRPC server replicas
  -> databases, caches, queues, object stores
```

Scale server replicas based on:

- CPU.
- Memory.
- QPS.
- In-flight RPC count.
- Active stream count.
- Tail latency.
- Queue depth.
- Downstream dependency saturation.

### Stateless Handlers

Unary RPC handlers should be stateless when possible.

Good:

```text
Any backend can handle any GetUser request.
```

Harder to scale:

```text
Only backend A has user u1's session state in memory.
```

If stateful routing is needed, make it explicit:

- Consistent hashing.
- Sticky sessions.
- Sharded ownership.
- External state store.
- Actor model.

### Connection Scaling

Each gRPC server handles:

- TCP connections.
- TLS sessions.
- HTTP/2 streams.
- Application requests.
- Flow control buffers.
- Keepalive pings.

Track:

```text
connections_per_instance
active_streams_per_connection
active_streams_per_instance
new_connections_per_second
connection_age
```

### Concurrent Stream Limits

HTTP/2 allows many streams per connection, but servers often enforce a maximum.
If the max concurrent streams per connection is reached, clients need additional
connections or must wait.

Symptoms:

- High client-side queuing.
- Low server CPU but high latency.
- Calls stuck waiting for transport capacity.

Mitigations:

- Increase concurrent stream limit if safe.
- Use multiple channels/connections for very high throughput clients.
- Spread load across backends.
- Reduce long-lived streams on the same channel as latency-sensitive unary RPCs.

### Separate Traffic Classes

Do not always put every RPC on the same channel or server pool.

Separate when needed:

- Low-latency reads.
- Expensive batch calls.
- Long-lived streaming calls.
- Admin/debug calls.
- Background jobs.

Example:

```text
payment-read channel      -> read-optimized server pool
payment-write channel     -> write server pool
payment-stream channel    -> streaming server pool
```

This prevents slow streams or batch jobs from starving critical unary calls.

### Payload Size

gRPC is efficient, but large messages still hurt scalability.

Problems with huge messages:

- Memory pressure.
- Head-of-line blocking within application queues.
- Higher GC pressure.
- Slow retries.
- Longer tail latency.
- More expensive compression.

Prefer:

- Pagination for lists.
- Server streaming for large result sets.
- Chunked client streaming for uploads.
- Object storage for very large blobs.
- Field masks to avoid over-fetching.

### Compression

Compression can reduce bandwidth, but it costs CPU.

Use compression when:

- Payloads are large and compressible.
- Network is the bottleneck.
- CPU has spare capacity.

Avoid compression when:

- Payloads are tiny.
- Payloads are already compressed.
- CPU is the bottleneck.
- Latency is extremely sensitive.

### Scaling Streaming Systems

Streaming scale depends on:

- Number of active streams.
- Message rate per stream.
- Fanout pattern.
- Per-stream memory.
- Backpressure handling.
- Reconnect behavior.
- Server drain strategy.

Example issue:

```text
100,000 clients each maintain one WatchNotifications stream.
Average stream is idle.
During an incident, all clients reconnect at once.
```

Mitigations:

- Reconnect jitter.
- Admission control.
- Connection draining.
- Resume tokens.
- Regional routing.
- Backpressure.
- Server-side fanout queues with limits.

## 12. Reliability and Fault Tolerance

Reliability is not one feature. It is a set of controls that prevent failures
from spreading and make recovery predictable.

### Reliability Toolkit

Use:

- Deadlines.
- Cancellation.
- Retries with backoff and jitter.
- Idempotency keys.
- Health checks.
- Load balancing.
- Circuit breakers.
- Rate limits.
- Bulkheads.
- Graceful shutdown.
- Connection draining.
- Observability.
- Runbooks and SLOs.

### Failure Types

| Failure | Example | Response |
|---|---|---|
| Transient network failure | Packet loss, reset | Retry if safe |
| Backend crash | Pod killed | Retry/load balance |
| Overload | CPU/thread pool saturated | Backoff, shed load |
| Bad request | Invalid field | Return `INVALID_ARGUMENT` |
| Auth failure | Missing token | Return `UNAUTHENTICATED` |
| Permission failure | No access | Return `PERMISSION_DENIED` |
| Dependency failure | DB unavailable | Return `UNAVAILABLE` or domain-specific failure |
| Slow dependency | DB p99 spike | Deadline, fallback, circuit breaker |

### Graceful Shutdown

During deploys, servers should stop accepting new calls and allow in-flight work
to finish within a drain window.

Conceptual flow:

```text
1. Instance receives shutdown signal.
2. Readiness changes to NOT_SERVING.
3. Load balancers stop sending new calls.
4. Server sends GOAWAY or otherwise drains connections.
5. In-flight unary calls finish.
6. Long-lived streams receive graceful close or reconnect signal.
7. Instance exits after drain timeout.
```

Without graceful shutdown:

- Deploys cause unnecessary `UNAVAILABLE` errors.
- Clients retry more.
- Streams break abruptly.
- Tail latency spikes.

### Wait-for-Ready

By default, if a channel cannot connect, some calls may fail quickly. Wait-for-
ready changes behavior so calls wait for the channel to become ready until their
deadline expires.

Use wait-for-ready for:

- Startup ordering issues.
- Batch/background jobs.
- Non-user-facing workflows.

Avoid wait-for-ready for:

- Low-latency user requests that should fail fast.
- Calls without deadlines.
- Overload scenarios where waiting makes queues worse.

### Circuit Breaking

Circuit breakers are often implemented outside core gRPC libraries, commonly in
client libraries, service meshes, or resilience frameworks.

Purpose:

```text
If dependency is failing badly:
  stop sending more traffic for a short window
  fail fast or use fallback
  periodically probe for recovery
```

Circuit breakers protect both callers and dependencies.

### Bulkheads

Bulkheads isolate resources so one traffic class cannot exhaust everything.

Examples:

- Separate thread pools for read and write RPCs.
- Separate server pools for streaming and unary APIs.
- Per-tenant concurrency limits.
- Separate channels for critical and background calls.

### Load Shedding

When overloaded, it is better to reject quickly than accept work that will time
out anyway.

Return:

- `RESOURCE_EXHAUSTED` for quota/rate/concurrency limits.
- `UNAVAILABLE` when the service cannot currently serve.

Add retry-after semantics through metadata if clients can use it.

### Idempotent Recovery

For critical operations:

- Store idempotency keys.
- Use transactionally written operation records.
- Return the same result for duplicate requests.
- Make side effects observable and auditable.

Example payment flow:

```text
CreatePayment(idempotency_key = k1)
  -> insert operation row if absent
  -> call payment processor
  -> persist processor result
  -> return result

Retry CreatePayment(k1)
  -> find previous operation row
  -> return stored result
```

## 13. Backpressure, Flow Control, and Streaming Reliability

### Backpressure

Backpressure means a slow receiver can signal the sender to slow down.

In gRPC:

- HTTP/2 provides transport-level flow control.
- Language APIs may expose readiness or async write completion.
- Application code must still avoid unbounded buffering.

Bad:

```text
Read messages from Kafka as fast as possible
Write to gRPC stream without checking readiness
Buffer millions of messages in memory
```

Good:

```text
Read only when the stream can accept more
Bound in-memory queues
Slow upstream when downstream is slow
Fail or shed load when limits are reached
```

### Flow Control

HTTP/2 has:

- Connection-level flow control.
- Stream-level flow control.

This prevents one receiver from being overwhelmed at the transport level. It
does not automatically make your business logic safe. You still need bounded
queues and resource limits.

### Ordering

Within one gRPC stream:

```text
Messages are delivered in order.
```

Across different streams:

```text
No global ordering guarantee.
```

Across reconnects:

```text
No automatic continuation guarantee.
```

If ordering matters, include:

- Sequence number.
- Partition key.
- Resume token.
- Server-side offset.

### Resume Tokens

For durable server streams, include a cursor.

```proto
message WatchEventsRequest {
  string tenant_id = 1;
  string resume_token = 2;
}

message Event {
  string id = 1;
  int64 sequence = 2;
  string resume_token = 3;
}
```

Reconnect flow:

```text
1. Client receives events up to token T.
2. Stream breaks.
3. Client reconnects with resume_token = T.
4. Server resumes from the next event.
```

### Heartbeats

Use heartbeats when application messages may be idle.

```text
Server -> heartbeat every 30 seconds
Client considers stream stale after 90 seconds without message
Client reconnects with jitter
```

Transport keepalives detect dead connections, but application heartbeats can
also prove that the logical subscription is alive.

### Stream Lifetime Limits

Long-lived streams should often have a maximum lifetime.

Example:

```text
Server asks clients to reconnect every 30 minutes with jitter.
```

Benefits:

- Rebalances clients across new backends.
- Helps deploys drain.
- Reduces stale state.
- Allows server-side resource cleanup.

## 14. Security

### TLS

Use TLS for service-to-service communication unless traffic is strictly inside a
trusted and encrypted environment.

TLS provides:

- Encryption in transit.
- Server identity.
- Protection against passive network sniffing.

### Mutual TLS

mTLS authenticates both client and server.

```text
Client verifies server certificate.
Server verifies client certificate.
```

Use mTLS for:

- Internal microservices.
- Zero-trust networks.
- Service mesh identity.
- Regulated environments.

### Authentication

Common patterns:

- Bearer token in metadata.
- JWT in metadata.
- mTLS identity.
- API key for external clients.
- OAuth2 access token.

Example metadata:

```text
authorization: Bearer <token>
x-request-id: req-123
x-tenant-id: tenant-7
```

### Authorization

Authentication answers:

```text
Who is calling?
```

Authorization answers:

```text
Is this caller allowed to perform this RPC on this resource?
```

Authorization can be enforced:

- In server interceptors.
- In each service method.
- Through a policy engine.
- Through service mesh policy for coarse-grained rules.

### Security Pitfalls

- Trusting client-provided tenant IDs without validation.
- Not validating message size.
- Exposing reflection in public environments without controls.
- Logging sensitive metadata.
- Allowing unauthenticated health/admin methods.
- Using plaintext across untrusted networks.

## 15. Observability

Good gRPC observability has metrics, logs, traces, and structured status codes.

### Metrics

Track per service and method:

- Request count.
- Error count by status code.
- Latency histogram.
- Deadline exceeded count.
- Retry attempts.
- In-flight calls.
- Active streams.
- Message count per stream.
- Request and response payload size.
- Connection count.
- Queue time.

Example metric dimensions:

```text
grpc_service = payments.PaymentService
grpc_method = AuthorizePayment
grpc_status = OK
```

Avoid high-cardinality labels such as user ID, request ID, or raw error message.

### Logs

Log:

- Method.
- Status code.
- Duration.
- Request ID.
- Trace ID.
- Peer service.
- Deadline.
- Retry attempt.
- Important domain identifiers when safe.

Do not log:

- Passwords.
- Tokens.
- Payment card data.
- Large payloads.
- Sensitive PII.

### Tracing

Distributed tracing is especially important because gRPC is commonly used in
microservices.

Trace propagation should include:

- Trace ID.
- Span ID.
- Parent span.
- Baggage only when necessary.

Trace view:

```text
CheckoutAPI
  -> UserService.GetUser
  -> CartService.GetCart
  -> InventoryService.Reserve
  -> PaymentService.Authorize
```

### Error Details

Use rich error details when clients need machine-readable failure information.

Examples:

- Field validation errors.
- Quota failure details.
- Retry delay hints.
- Resource info.

Keep domain errors clear and stable.

## 16. Performance Characteristics

### Strengths

gRPC performs well because:

- Protobuf is compact.
- Serialization is fast.
- HTTP/2 multiplexes calls.
- Connections are reused.
- Streaming avoids request-per-message overhead.
- Generated code avoids dynamic parsing overhead.

### Costs

gRPC still has costs:

- Protobuf encoding/decoding.
- TLS.
- Compression.
- Flow control bookkeeping.
- Interceptor chains.
- Context propagation.
- Load balancing state.
- Memory buffers.

### Performance Tuning Checklist

Tune:

- Deadlines.
- Max message size.
- Max concurrent streams.
- Connection pooling/channel count.
- Keepalive settings.
- Server executor/thread pool.
- Compression.
- Payload shape.
- Streaming batch size.
- Database/client pool sizes.

Measure before tuning. gRPC is often not the bottleneck; downstream databases,
locks, thread pools, or oversized payloads usually are.

### Unary vs Streaming Performance

Use unary when:

- Request-response is naturally small.
- Calls are independent.
- Retries and load balancing should be simple.

Use streaming when:

- Many messages belong to one logical session.
- You need server push.
- You need to avoid repeated request setup.
- You are transferring large sequences.

Do not use streaming just because it sounds faster. Streaming increases
connection lifetime, recovery complexity, and load balancing complexity.

## 17. gRPC vs REST vs WebSocket

| Dimension | gRPC | REST | WebSocket |
|---|---|---|---|
| Contract | `.proto` | OpenAPI or informal | Usually custom |
| Payload | Protobuf by default | JSON common | Custom text/binary |
| Transport | HTTP/2 | HTTP/1.1 or HTTP/2 | WebSocket over TCP |
| Browser support | Limited direct support; gRPC-Web needed | Native | Native |
| Streaming | Built in | Limited/varies | Built in full-duplex |
| Service-to-service | Excellent | Good | Less common |
| Public APIs | Less common | Excellent | Specialized |
| Code generation | First-class | Optional | Custom |
| Load balancing | Needs HTTP/2-aware design | Mature/simple | Sticky long-lived |
| Best use | Internal typed RPC | Public resource APIs | Real-time client sessions |

### When to Use gRPC

Use gRPC for:

- Internal microservice communication.
- Low-latency service-to-service calls.
- Strongly typed contracts.
- Polyglot backend systems.
- Streaming between backend services.
- High-throughput APIs.
- Mobile clients when supported.

### When Not to Use gRPC

Avoid or reconsider gRPC for:

- Simple public APIs consumed by browsers.
- APIs where human debugging with curl is a major requirement.
- Teams without protobuf/schema discipline.
- Environments where HTTP/2 is poorly supported.
- Very cache-heavy APIs that benefit from HTTP semantics/CDNs.

### gRPC-Web

Browsers do not expose full raw HTTP/2 semantics needed by standard gRPC. For
browser clients, use gRPC-Web with a compatible proxy or server implementation.

## 18. Production Architecture Patterns

### Pattern 1: Simple Internal Service

```text
Service A
  -> gRPC channel to Service B
  -> DNS/service discovery
  -> Service B replicas
```

Use:

- Unary RPCs.
- Deadlines.
- Basic retries for idempotent reads.
- Health checks.
- Metrics and tracing.

### Pattern 2: Kubernetes with Envoy

```text
Client pod
  -> local Envoy sidecar
  -> Envoy sidecar near server
  -> gRPC server
```

Use:

- xDS/service mesh routing.
- mTLS.
- Outlier detection.
- Circuit breaking.
- Retries.
- Traffic splitting.
- Observability.

Tradeoff:

- Strong traffic control, but more operational complexity.

### Pattern 3: Headless Service with Client-Side Round Robin

```text
Client channel
  -> DNS resolver returns pod IPs
  -> round_robin policy
  -> direct backend connections
```

Use:

- High-throughput internal systems.
- Controlled client libraries.
- Fewer proxy hops.

Tradeoff:

- Client configuration and behavior must be consistent.

### Pattern 4: Streaming Gateway

```text
Clients
  -> streaming gateway gRPC service
  -> pub/sub or event log
  -> backend producers
```

Use:

- Notifications.
- Watch APIs.
- Real-time operational feeds.

Key requirements:

- Resume tokens.
- Heartbeats.
- Per-client limits.
- Backpressure.
- Graceful reconnect.

### Pattern 5: Public Edge Translation

```text
Browser/mobile/public client
  -> REST/JSON or gRPC-Web edge API
  -> internal gRPC services
```

Use:

- REST externally.
- gRPC internally.
- Edge handles auth, rate limits, request shaping, and protocol translation.

This is common because public API ergonomics and internal service efficiency are
different concerns.

## 19. Common Pitfalls

### Pitfall 1: No Deadlines

Symptom:

```text
Threads pile up, clients wait forever, incidents cascade.
```

Fix:

```text
Set deadlines on every client call and respect cancellation on the server.
```

### Pitfall 2: Retrying Unsafe Mutations

Symptom:

```text
Duplicate orders, duplicate payments, repeated emails.
```

Fix:

```text
Use idempotency keys or do not retry the mutation automatically.
```

### Pitfall 3: Connection-Level Load Balancing Only

Symptom:

```text
One backend is hot while others are idle.
```

Fix:

```text
Use HTTP/2-aware proxying, client-side round_robin, headless services, or xDS.
```

### Pitfall 4: Huge Unary Responses

Symptom:

```text
High memory, long GC pauses, slow p99 latency.
```

Fix:

```text
Use pagination or server streaming.
```

### Pitfall 5: Long-Lived Streams Without Resume

Symptom:

```text
Deploys or network blips cause missed events.
```

Fix:

```text
Add sequence numbers, resume tokens, and reconnect logic.
```

### Pitfall 6: Treating gRPC Status as HTTP Status

Symptom:

```text
Proxies show HTTP 200 while application call failed with grpc-status != OK.
```

Fix:

```text
Monitor gRPC status codes from trailers and runtime metrics.
```

### Pitfall 7: Blocking Event Loop Threads

Symptom:

```text
Low CPU but high latency and stalled connections.
```

Fix:

```text
Move blocking work to proper worker pools or use async clients.
```

### Pitfall 8: Unbounded Streaming Buffers

Symptom:

```text
Memory grows until process crashes.
```

Fix:

```text
Respect backpressure and set queue limits.
```

### Pitfall 9: Schema Changes Without Compatibility Rules

Symptom:

```text
Old clients fail after deployment.
```

Fix:

```text
Never reuse field numbers. Add fields safely. Reserve removed fields.
```

## 20. Interview-Ready Summary

### One-Minute Explanation

gRPC is a high-performance RPC framework that uses Protocol Buffers for typed
contracts and HTTP/2 for transport. A service defines methods in a `.proto`
file, code generators create clients and servers, and each RPC runs over an
HTTP/2 stream. gRPC supports unary calls, server streaming, client streaming,
and bidirectional streaming. In production, the most important concerns are
deadlines, retries with idempotency, HTTP/2-aware load balancing, health checks,
graceful shutdown, backpressure, and observability.

### Load Balancing Answer

gRPC uses long-lived HTTP/2 connections, so connection-level load balancing can
create uneven backend utilization. Production systems usually solve this with
HTTP/2-aware proxies such as Envoy, service mesh/xDS, or client-side load
balancing with service discovery and policies like round robin. For streaming
RPCs, load balancing is harder because streams can stay pinned to a backend, so
systems need draining, max stream lifetimes, resume tokens, and active stream
metrics.

### Retry Answer

gRPC supports limited transparent retries and configurable retry policies in
service config. Retries should use exponential backoff, jitter, retryable status
codes, and a retry budget within the original deadline. Only idempotent
operations should be retried automatically. Mutations need idempotency keys.
Streaming retries usually require application-level resume logic.

### Timeout Answer

Every gRPC call should have a deadline. Deadlines prevent indefinite waiting,
bound resource usage, and reduce cascading failures. Services should propagate
remaining time budget to downstream calls and stop work when the caller cancels
or the deadline expires.

### Streaming Answer

gRPC has four RPC types: unary, server streaming, client streaming, and
bidirectional streaming. Unary is best for ordinary request-response APIs.
Server streaming is useful for watch APIs and large result sets. Client
streaming is useful for uploads and aggregations. Bidirectional streaming is
useful for interactive real-time sessions. The more streaming you use, the more
you must design for backpressure, reconnects, ordering, resume tokens, and
graceful draining.

## 21. References

This note was prepared using current Context7 results from the official gRPC
documentation set:

- gRPC core concepts: service method types and streaming shapes.
- gRPC service config: method timeouts and load balancing configuration.
- gRPC retry guide: transparent retries, configured retry policies, backoff,
  retry throttling, and retryable status codes.
- gRPC deadlines guide: client-side deadlines and timeout behavior.
- gRPC health checking guide: client health checking and serving status.

