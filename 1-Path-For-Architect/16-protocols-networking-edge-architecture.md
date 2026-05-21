# Communication Protocols, Networking, and Edge Architecture

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 16.5 Communication Protocols Deep Dive

## gRPC

### Architecture & Internals
- Built on HTTP/2: multiplexed streams, header compression (HPACK), binary framing.
- Protocol Buffers (protobuf) as Interface Definition Language (IDL) and serialization format.
- Code generation: `.proto` files → client stubs + server skeletons in 10+ languages.
- Four communication patterns:
  - Unary RPC (request-response).
  - Server streaming (one request, stream of responses).
  - Client streaming (stream of requests, one response).
  - Bidirectional streaming (both sides stream independently).

### Key Concepts
- **Interceptors**: middleware for logging, auth, metrics, retry logic (client-side and server-side).
- **Deadlines/Timeouts**: propagated across service hops; prevents cascading hangs.
- **Metadata**: key-value pairs sent as headers (like HTTP headers but typed).
- **Channel**: virtual connection to an endpoint; manages connection pool internally.
- **Name resolution & load balancing**: client-side (pick_first, round_robin) or external (Envoy, Linkerd).
- **Reflection**: runtime schema discovery for debugging tools like `grpcurl`.
- **Health checking protocol**: standard `grpc.health.v1.Health` service for load balancers.

### gRPC vs REST Comparison

| Aspect | gRPC | REST |
|--------|------|------|
| Serialization | Protobuf (binary) | JSON (text) |
| Transport | HTTP/2 only | HTTP/1.1 or HTTP/2 |
| Streaming | Native bidirectional | SSE or WebSocket bolt-on |
| Code generation | Built-in from .proto | OpenAPI/Swagger optional |
| Browser support | Requires grpc-web proxy | Native |
| Schema evolution | Field numbers, backward-compatible | Versioned URLs |
| Performance | 2-10x faster serialization | Human-readable |
| Tooling | grpcurl, Evans, BloomRPC | curl, Postman |

### Implementation Patterns
- **Service mesh integration**: Envoy as gRPC-aware sidecar (routing, retries, circuit breaking).
- **Gateway pattern**: grpc-gateway generates REST reverse-proxy from proto annotations.
- **Error model**: rich error details via `google.rpc.Status` with typed detail messages.
- **Retry policy**: configurable in service config JSON (max attempts, backoff, retryable status codes).
- **Connection keepalive**: PING frames to detect dead connections; configurable intervals.

### Interview Questions
1. How does gRPC achieve better performance than REST? Explain the HTTP/2 and protobuf layers.
2. Design a real-time collaborative editing service using bidirectional streaming gRPC.
3. How do you handle backward compatibility when evolving protobuf schemas?
4. Explain gRPC deadline propagation across a chain of 5 microservices. What happens when one times out?
5. How would you implement authentication in gRPC? Compare token-based vs mTLS approaches.
6. What happens when a gRPC client-side load balancer detects an unhealthy backend?
7. How do you debug a gRPC call that works in development but fails in production?
8. Compare gRPC interceptors to HTTP middleware. When would you choose one over the other?
9. How would you migrate a REST API to gRPC incrementally without breaking existing clients?
10. Explain how gRPC handles flow control in streaming RPCs. What is the window update mechanism?

---

## WebSockets

### Architecture & Internals
- Upgrade handshake: HTTP/1.1 → 101 Switching Protocols → persistent TCP connection.
- Frame types: text, binary, ping/pong (heartbeat), close.
- Full-duplex: both sides send independently without request/response pairing.
- No built-in multiplexing (unlike HTTP/2); one logical channel per connection.

### Scaling WebSockets
- **Sticky sessions**: required when using in-memory connection state; ALB/NLB with connection-based routing.
- **Pub/Sub backbone**: Redis Pub/Sub, NATS, or Kafka to fan-out messages across server instances.
- **Connection limits**: OS file descriptor limits (~1M per server with tuning), memory per connection (~2-10KB).
- **Horizontal scaling architecture**:
  ```
  Client → Load Balancer (L4, connection-based)
         → WebSocket Server (maintains conn registry)
         → Redis Pub/Sub (cross-server message routing)
         → WebSocket Server (delivers to target client)
  ```

### Connection Management
- **Heartbeat/Ping-Pong**: detect dead connections (30-60s interval typical).
- **Reconnection strategy**: exponential backoff with jitter (1s, 2s, 4s, 8s... + random 0-1s).
- **Connection state recovery**: resume token / last-event-ID to replay missed messages.
- **Graceful shutdown**: send close frame, drain in-flight messages, wait for close acknowledgment.
- **Authentication**: token in query param during upgrade (not ideal) or first message after connect.

### WebSocket vs Alternatives

| Feature | WebSocket | SSE | Long Polling | gRPC Streaming |
|---------|-----------|-----|--------------|----------------|
| Direction | Bidirectional | Server → Client | Simulated bidir | Bidirectional |
| Protocol | WS over TCP | HTTP/1.1 | HTTP/1.1 | HTTP/2 |
| Reconnection | Manual | Automatic | Automatic | Manual |
| Binary data | Yes | No (text only) | Yes | Yes (protobuf) |
| Browser support | All modern | All modern | All | Requires proxy |
| Through proxies | Sometimes blocked | Always works | Always works | Usually works |
| Max connections | ~6 per domain (browser) | ~6 per domain | ~6 per domain | Multiplexed |

### Interview Questions
1. Design a chat system supporting 10M concurrent WebSocket connections. How do you scale?
2. How do you handle WebSocket authentication and token refresh without dropping the connection?
3. Explain the WebSocket upgrade handshake. What happens if a proxy doesn't support it?
4. How do you implement exactly-once message delivery over WebSockets?
5. Design a real-time dashboard with 100K concurrent viewers. WebSocket vs SSE? Why?
6. How do you detect and handle zombie WebSocket connections (half-open state)?
7. Explain back-pressure in WebSocket streaming. What happens when the client can't keep up?
8. How would you implement room-based messaging (like Slack channels) at scale?
9. Compare WebSocket connection cost vs HTTP/2 server push for a stock ticker use case.
10. How do you test WebSocket-based systems? What failure modes do you simulate?

---

## Server-Sent Events (SSE)

### Architecture
- Unidirectional: server → client only over a standard HTTP/1.1 connection.
- `Content-Type: text/event-stream` with chunked transfer encoding.
- Built-in reconnection: browser automatically reconnects with `Last-Event-ID` header.
- Event format: `id:`, `event:`, `data:`, `retry:` fields.

### When to Use SSE vs WebSocket
- SSE: notifications, live feeds, dashboards, progress updates (server-initiated only).
- WebSocket: chat, gaming, collaborative editing (client needs to send data frequently).
- SSE advantages: works through all proxies/CDNs, automatic reconnection, simpler implementation.
- SSE limitations: text only, unidirectional, limited to ~6 connections per domain in HTTP/1.1.

### Interview Questions
1. When would you choose SSE over WebSocket for a real-time feature? Give three scenarios.
2. How does SSE handle reconnection and message replay? What is the `Last-Event-ID` mechanism?
3. Can you scale SSE through a CDN? How?
4. Design a deployment progress tracker using SSE. How do you handle long-running operations?
5. How do you work around the 6-connection-per-domain browser limit with SSE?

---

# 16.6 Caching Deep Dive

## 16.9 Infrastructure & Networking Deep Dive

### Load Balancers

**L4 vs L7 Comparison:**
| Feature | L4 (Transport) | L7 (Application) |
|---------|-----------------|-------------------|
| Layer | TCP/UDP | HTTP/HTTPS/gRPC |
| Speed | Faster (no payload inspection) | Slower (parses headers/body) |
| Routing | IP + Port | URL path, headers, cookies |
| SSL Termination | Pass-through or terminate | Always terminates |
| Session Persistence | Source IP hash | Cookie-based affinity |
| Health Checks | TCP connect / UDP | HTTP status code, body check |
| Use Case | Database, TCP services | Web apps, APIs, microservices |
| Examples | AWS NLB, HAProxy (TCP) | AWS ALB, Nginx, Envoy |

**Load Balancing Algorithms:**
| Algorithm | How It Works | Best For |
|-----------|--------------|----------|
| Round Robin | Sequential rotation | Equal-capacity servers |
| Weighted Round Robin | Rotation with weights | Mixed-capacity servers |
| Least Connections | Route to least-busy server | Variable request duration |
| Weighted Least Connections | Least connections + weights | Mixed capacity + variable duration |
| IP Hash | Hash source IP to server | Session persistence without cookies |
| Consistent Hashing | Hash ring for minimal redistribution | Cache servers, stateful routing |
| Random Two Choices | Pick 2 random, choose least loaded | Large server pools |
| Least Response Time | Route to fastest responding | Latency-sensitive applications |

**AWS ALB vs NLB vs CLB:**
| Feature | ALB | NLB | CLB (Legacy) |
|---------|-----|-----|--------------|
| Layer | 7 | 4 | 4/7 |
| Protocols | HTTP, HTTPS, gRPC | TCP, UDP, TLS | TCP, HTTP |
| WebSocket | Yes | Yes (TCP) | No |
| Static IP | No (use Global Accelerator) | Yes (Elastic IP per AZ) | No |
| Latency | ~ms added | ~µs added | ~ms added |
| Target Types | Instance, IP, Lambda | Instance, IP, ALB | Instance only |
| Path Routing | Yes | No | No |
| Cross-zone | Default on | Default off (cost) | Default on |

### API Gateway

**API Gateway Responsibilities:**
```
┌─────────────────────────────────────────────────────┐
│                   API Gateway                        │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │  Auth &  │ │   Rate   │ │  Request/Response │  │
│  │  AuthZ   │ │ Limiting │ │   Transformation  │  │
│  └──────────┘ └──────────┘ └───────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Routing  │ │ Caching  │ │   Load Balancing  │  │
│  └──────────┘ └──────────┘ └───────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Logging  │ │ Circuit  │ │   API Versioning  │  │
│  │& Metrics │ │ Breaker  │ │                   │  │
│  └──────────┘ └──────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**API Gateway Comparison:**
| Feature | Kong | AWS API Gateway | Envoy | Nginx | Traefik |
|---------|------|-----------------|-------|-------|---------|
| Deployment | Self-hosted/Cloud | Managed | Sidecar/Edge | Self-hosted | Self-hosted |
| Protocol | HTTP, gRPC, TCP | HTTP, WebSocket | HTTP/2, gRPC, TCP | HTTP, TCP | HTTP, TCP, gRPC |
| Plugin System | Lua/Go plugins | Lambda authorizers | WASM/C++ filters | Lua/NJS | Middleware |
| Service Discovery | DNS, Consul | Built-in (AWS) | xDS API (Istio) | DNS, static | Docker, K8s, Consul |
| Observability | Prometheus, Datadog | CloudWatch | Built-in stats | Access logs | Prometheus, Datadog |
| Config Model | DB-backed (Postgres) | AWS Console/API | xDS (control plane) | File-based | Auto-discovery |

### Service Mesh

**Istio Architecture:**
```
┌────────────────── Control Plane ──────────────────┐
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐ │
│  │  Pilot │  │ Citadel│  │ Galley │  │ Mixer  │ │
│  │(config)│  │(certs) │  │(valid.)│  │(policy)│ │
│  └────────┘  └────────┘  └────────┘  └────────┘ │
└───────────────────────────────────────────────────┘
         ▲            ▲            ▲
         │            │            │
┌────────┼────────────┼────────────┼────────────────┐
│        ▼            ▼            ▼   Data Plane   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  Envoy   │ │  Envoy   │ │  Envoy   │         │
│  │ (sidecar)│ │ (sidecar)│ │ (sidecar)│         │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘         │
│  ┌─────▼────┐ ┌─────▼────┐ ┌─────▼────┐         │
│  │ Service A│ │ Service B│ │ Service C│         │
│  └──────────┘ └──────────┘ └──────────┘         │
└───────────────────────────────────────────────────┘
```

**Service Mesh Comparison:**
| Feature | Istio | Linkerd | Consul Connect | AWS App Mesh |
|---------|-------|---------|----------------|--------------|
| Proxy | Envoy | linkerd2-proxy (Rust) | Built-in / Envoy | Envoy |
| Complexity | High | Low | Medium | Medium |
| Performance Overhead | ~3-5ms p99 | ~1ms p99 | ~2-3ms p99 | ~2-3ms p99 |
| mTLS | Yes (auto) | Yes (auto) | Yes (manual/auto) | Yes |
| Multi-cluster | Yes | Yes | Yes (WAN Federation) | Cross-account |
| Protocol Support | HTTP/1.1, HTTP/2, gRPC, TCP | HTTP/1.1, HTTP/2, gRPC, TCP | HTTP, gRPC, TCP | HTTP, HTTP/2, gRPC |

### Infrastructure Interview Questions

1. Design a global load balancing strategy for a service deployed across 5 regions with failover requirements.
2. When would you choose an API Gateway over a service mesh, and vice versa?
3. How does consistent hashing improve cache hit rates during scaling events?
4. Explain how a CDN handles cache invalidation for dynamic content.
5. Design a DNS-based traffic management system with health checking and failover.
6. How would you implement zero-downtime deployments with blue-green and canary strategies at the load balancer level?
7. Compare sidecar proxy (Envoy) vs library-based (Hystrix) approaches to service communication.
8. How would you design connection draining during a rolling deployment?
9. Explain GeoDNS routing and its failure modes. How do you prevent cascading failures?
10. Design an API Gateway that handles 100K RPS with sub-10ms added latency.

---


## 20.3 API Gateway, Load Balancing, and Edge Architecture

### API Gateway Responsibilities

- TLS termination or pass-through.
- Authentication and authorization integration.
- Request routing and version routing.
- Rate limiting and quota enforcement.
- Request validation and normalization.
- Response transformation where unavoidable.
- Correlation IDs and trace propagation.
- WAF integration and bot protection.
- Canary and shadow routing.
- Developer portal and API lifecycle governance.

### Load Balancer Deep Dive

- Layer 4 vs Layer 7 load balancing.
- Algorithms: round robin, least connections, weighted routing, consistent hashing, EWMA latency.
- Health checks: active, passive, readiness-aware, dependency-aware.
- Connection draining during deployment.
- Sticky sessions and why they hurt elasticity.
- Global load balancing with DNS, Anycast, or traffic managers.
- Fail-open vs fail-closed decisions.
- Overload protection and queue limits.

### Scaling Decisions

- Vertical scaling: simpler, bounded by machine limits.
- Horizontal scaling: needs stateless services or externalized state.
- Autoscaling signals: CPU, memory, RPS, queue depth, Kafka lag, custom SLO burn.
- Scale-out risks: database saturation, cache hot keys, connection storms, noisy neighbors.
- Backpressure: reject early, shed low-priority work, degrade gracefully.
- Capacity planning: peak traffic, p95/p99 latency, headroom, regional failover, cost.


