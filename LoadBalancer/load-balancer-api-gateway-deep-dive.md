# Load Balancer and API Gateway Deep Dive

This note explains Layer 4 load balancers, Layer 7 load balancers, their capabilities, where each one fits, and how an API Gateway is different from both.

The core idea:

```text
Client
  -> DNS / Global Traffic Manager
  -> L4 Load Balancer or L7 Load Balancer
  -> API Gateway, Web App, Service Mesh, or Backend Service
  -> Application / Database / Cache / Stream / Queue
```

A load balancer mainly answers:

```text
Which healthy backend instance should receive this connection or request?
```

An API Gateway answers a broader platform question:

```text
How should external API traffic be authenticated, authorized, shaped, protected,
transformed, observed, and routed to internal services?
```

---

## 1. Quick Mental Model

| Component | Primary Job | Layer | Understands HTTP? | Typical Scope |
|-----------|-------------|-------|-------------------|---------------|
| DNS load balancing | Return different IPs or endpoints | DNS | No | Region/global |
| Global server load balancing | Route users to best region/edge | DNS/L3/L4/L7 | Sometimes | Global |
| L4 load balancer | Distribute TCP/UDP/TLS connections | Transport | No | Network/service entry |
| L7 load balancer | Distribute HTTP/gRPC requests | Application | Yes | Web/app entry |
| Reverse proxy | Intermediary in front of servers | Usually L7 | Usually | Web/app edge |
| API Gateway | Govern and expose APIs | L7 | Yes | API platform boundary |
| Service mesh gateway | Govern service-to-service traffic | L4/L7 | Often | Internal platform |
| Ingress controller | Kubernetes L7 entry point | L7 | Yes | Kubernetes cluster |

Important distinction:

```text
L4 load balancer = connection-aware.
L7 load balancer = request-aware.
API Gateway = API-aware and policy-aware.
```

---

## 2. What Is a Load Balancer?

A load balancer sits between clients and backend targets. It improves availability, scalability, and operability by distributing traffic across multiple healthy instances.

Basic flow:

```text
Client
  -> Load Balancer
      -> health check target A
      -> health check target B
      -> health check target C
  -> Selected healthy target
```

Common capabilities:

- **Traffic distribution**: spread load across multiple servers.
- **Health checking**: stop sending traffic to unhealthy targets.
- **Failover**: route around failed instances or zones.
- **Horizontal scaling**: add or remove targets without client changes.
- **TLS handling**: terminate, pass through, or re-encrypt TLS depending on type.
- **Connection draining**: let in-flight traffic finish before removing a target.
- **Session persistence**: keep the same client on the same backend when required.
- **Observability**: access logs, metrics, latency, errors, target health.
- **Availability boundary**: expose a stable endpoint while backends change.

Load balancers are not all the same. The most important system design split is L4 vs L7.

---

## 3. OSI Layers Relevant to Load Balancing

| Layer | Name | Example Data | Load Balancer Awareness |
|-------|------|--------------|--------------------------|
| L3 | Network | IP address | Source/destination IP |
| L4 | Transport | TCP/UDP ports, connection state | IP, port, protocol, connection |
| L5/L6 | Session/presentation | TLS session, encoding | Sometimes TLS metadata |
| L7 | Application | HTTP path, host, headers, cookies, gRPC method | Full request semantics |

In practice:

```text
L4 LB decision:
  source IP + source port + destination IP + destination port + protocol

L7 LB decision:
  host + path + method + headers + cookies + query params + request metadata
```

---

## 4. Layer 4 Load Balancer

A Layer 4 load balancer operates at the transport layer. It forwards TCP, UDP, or TLS connections without understanding the application payload.

Example:

```text
Client TCP connection to 203.0.113.10:443
  -> L4 Load Balancer
      -> 10.0.1.21:443
      -> 10.0.2.31:443
      -> 10.0.3.41:443
```

The L4 load balancer does not need to know whether the bytes inside the connection are HTTP, gRPC, MQTT, PostgreSQL, Redis, Kafka, or a custom binary protocol.

### 4.1 L4 Decision Inputs

An L4 load balancer can usually route using:

- Source IP address.
- Source port.
- Destination IP address.
- Destination port.
- Protocol: TCP, UDP, TLS.
- Connection state.
- Target health.
- Optional TLS SNI in some implementations, if TLS inspection is supported.

It generally cannot route using:

- HTTP path.
- HTTP method.
- HTTP headers.
- Cookies.
- JSON body fields.
- gRPC service/method.
- User identity.
- API key.

### 4.2 L4 Capabilities

| Capability | Explanation |
|------------|-------------|
| TCP load balancing | Distributes long-lived or short-lived TCP connections. |
| UDP load balancing | Supports connectionless traffic such as DNS, gaming, VoIP, QUIC, telemetry. |
| TLS pass-through | Leaves TLS encrypted end-to-end between client and backend. |
| TLS termination | Some L4 products terminate TLS but still do not parse HTTP. |
| Static IP support | Many L4 cloud load balancers provide stable IPs. |
| Source IP preservation | Backends can see original client IP in some modes. |
| Low latency | Less parsing means lower processing overhead. |
| Very high throughput | Suitable for millions of connections or high packet volume. |
| Connection draining | Existing connections are allowed to finish during deploys. |
| Health checks | TCP connect, TLS handshake, UDP probe, or custom health probe. |
| Cross-zone distribution | Spreads connections across availability zones. |
| Long-lived connection support | Good for WebSockets, MQTT, database connections, streaming protocols. |

### 4.3 L4 Strengths

- Fast and simple.
- Works with almost any TCP or UDP protocol.
- Good for non-HTTP systems.
- Good when TLS must stay encrypted until the backend.
- Good for long-lived connections.
- Good when preserving client IP is important.
- Lower CPU overhead than full L7 request parsing.

### 4.4 L4 Limitations

- Cannot make rich routing decisions based on HTTP content.
- Cannot do path-based routing such as `/api` vs `/assets`.
- Cannot apply API-specific policies like JWT validation or quota per API key.
- Cannot rewrite HTTP headers.
- Cannot inspect request bodies.
- Cannot do HTTP-aware retries safely.
- Cannot easily protect against application-layer attacks.
- Health checks may be shallow unless custom probes are configured.

### 4.5 Common L4 Use Cases

| Use Case | Why L4 Fits |
|----------|-------------|
| Database traffic | PostgreSQL, MySQL, Cassandra, Redis, MongoDB use TCP protocols. |
| Kafka brokers | Kafka has its own binary protocol and connection behavior. |
| MQTT brokers | Long-lived TCP connections and topic messaging. |
| WebSocket pass-through | Connection-level distribution is enough if app handles sessions. |
| gRPC pass-through | Useful when backend terminates HTTP/2 and TLS. |
| Gaming or VoIP | UDP traffic needs low overhead and low latency. |
| TLS pass-through | Backend owns certificates or mutual TLS. |
| Internal service endpoint | Stable virtual IP in front of backend instances. |

---

## 5. Types of L4 Load Balancing

### 5.1 TCP Load Balancer

Balances TCP connections.

```text
Client -> TCP LB:443 -> Backend A:443
                    -> Backend B:443
```

Best for:

- HTTPS pass-through.
- Database connections.
- Redis, Kafka, MQTT.
- Custom TCP protocols.
- Long-lived connections.

Key behavior:

- Routing decision usually happens when the connection is established.
- All bytes for that connection normally stay on the same backend.
- If the backend dies, the connection usually breaks. The client must reconnect.

### 5.2 UDP Load Balancer

Balances UDP datagrams or UDP flows.

Best for:

- DNS.
- QUIC and HTTP/3 pass-through.
- Video/audio streaming.
- Gaming.
- Telemetry ingestion.
- IoT protocols.

Key behavior:

- UDP has no real connection state at the protocol level.
- Load balancer may create pseudo-flow state using source/destination tuple.
- Retries and ordering are handled by application protocol, not by TCP.

### 5.3 TLS Pass-Through Load Balancer

The load balancer does not decrypt TLS.

```text
Client
  -> encrypted TLS
  -> L4 LB
  -> encrypted TLS
  -> Backend terminates TLS
```

Best for:

- End-to-end encryption requirements.
- Backend-specific client certificates.
- Strict compliance boundaries.
- Services that own their own certificates.

Tradeoff:

- The load balancer cannot inspect HTTP headers or paths.
- WAF and API policy enforcement must happen elsewhere.

### 5.4 TLS Terminating L4 Load Balancer

Some L4 products terminate TLS but still make mostly connection-level routing decisions.

```text
Client
  -> TLS
  -> L4 LB terminates TLS
  -> TCP or TLS to backend
```

Useful when:

- Central certificate management is needed.
- Backend traffic can be plaintext inside a trusted network, or re-encrypted.
- You still do not need HTTP routing.

### 5.5 Direct Server Return Load Balancer

Direct Server Return, also called DSR, sends inbound traffic through the load balancer but lets responses return directly from the backend to the client.

```text
Request:
Client -> LB -> Backend

Response:
Backend -> Client
```

Best for:

- Very high throughput.
- Response-heavy traffic.
- Low load balancer bottleneck requirements.

Tradeoffs:

- More complex networking.
- Backend must be configured carefully.
- Observability and security controls can be harder.

### 5.6 NAT-Based L4 Load Balancer

The load balancer rewrites destination IP or source IP.

```text
Client -> LB virtual IP -> NAT rewrite -> Backend private IP
```

Types:

- **DNAT**: changes destination address from virtual IP to backend IP.
- **SNAT**: changes source address so backend sees the load balancer IP.
- **Full NAT**: changes both source and destination.

Tradeoff:

- SNAT hides client IP unless proxy protocol or other metadata is used.

### 5.7 Anycast L4 Load Balancer

The same IP is announced from multiple edge locations. Network routing sends the client to a nearby or healthy location.

```text
Client -> Same Anycast IP
        -> nearest healthy edge
        -> regional backend
```

Best for:

- Global traffic entry.
- DDoS absorption.
- Low-latency edge routing.
- DNS and CDN front doors.

Tradeoff:

- Routing follows BGP/network behavior, not always application-level intent.

---

## 6. Layer 7 Load Balancer

A Layer 7 load balancer operates at the application layer. In modern systems, this usually means HTTP, HTTPS, HTTP/2, gRPC, WebSocket upgrade handling, and sometimes HTTP/3.

Example:

```text
Client HTTPS request
  GET /api/orders
  Host: shop.example.com

  -> L7 Load Balancer
      if host == shop.example.com and path starts /api
        -> order-api target group
      if path starts /static
        -> static web target group
```

An L7 load balancer is request-aware, not just connection-aware.

### 6.1 L7 Decision Inputs

An L7 load balancer can route using:

- Hostname.
- URL path.
- HTTP method.
- Headers.
- Cookies.
- Query parameters.
- Content type.
- TLS SNI.
- gRPC service and method in some products.
- Request size.
- Target health.

Some advanced L7 proxies can also use:

- JWT claims.
- Geo metadata.
- Device metadata.
- Canary headers.
- Weighted traffic rules.
- Service discovery metadata.

### 6.2 L7 Capabilities

| Capability | Explanation |
|------------|-------------|
| Host-based routing | `api.example.com` and `app.example.com` go to different targets. |
| Path-based routing | `/users`, `/orders`, `/payments` route to different services. |
| Header-based routing | Route by `X-Canary`, `X-Tenant`, version headers. |
| Cookie-based affinity | Keep a browser session on the same backend. |
| TLS termination | Central certificate handling and HTTPS offload. |
| HTTP/2 and gRPC support | Multiplexed streams and gRPC routing depending on product. |
| WebSocket support | Handles HTTP upgrade then maintains connection. |
| Request buffering | Protects slow backends from slow clients in some cases. |
| Compression | gzip, brotli, or response compression depending on product. |
| Redirects | HTTP to HTTPS, domain redirects, canonical URL redirects. |
| Rewrites | Change paths or headers before forwarding. |
| HTTP health checks | Check `/health`, status code, response body, or headers. |
| WAF integration | Block common application attacks. |
| Request logs | Method, path, status, latency, user agent, target. |
| Canary routing | Shift 1 percent, 5 percent, 50 percent traffic to new version. |
| Blue-green routing | Move traffic between old and new environments. |
| Circuit breaking | Stop sending traffic to failing upstreams in advanced proxies. |
| Retries/timeouts | Request-aware retry behavior for safe methods or configured routes. |

### 6.3 L7 Strengths

- Rich routing based on request semantics.
- Better for microservices and API traffic.
- Easier centralized TLS and HTTP policy.
- Better request-level observability.
- Supports canary and blue-green deploys.
- Can apply web security controls.
- Can hide internal service topology from clients.

### 6.4 L7 Limitations

- More CPU and memory overhead than L4.
- Higher latency than simple packet or connection forwarding.
- Usually tied to known application protocols.
- Must parse traffic, so protocol compatibility matters.
- Request buffering can hurt streaming if misconfigured.
- Retries can cause duplicate side effects if applied incorrectly.
- Long-lived connections require careful timeout tuning.

### 6.5 Common L7 Use Cases

| Use Case | Why L7 Fits |
|----------|-------------|
| Public website | Host/path routing, TLS, redirects, compression. |
| REST APIs | Route by path and method. |
| gRPC APIs | Route by service/method if proxy supports gRPC. |
| Microservices | One domain can front many services. |
| Canary deployments | Header, cookie, or weighted routing. |
| Multi-tenant SaaS | Route by host, header, or tenant cookie. |
| Web security edge | WAF, request size limits, suspicious pattern blocking. |
| Kubernetes ingress | HTTP routing into cluster services. |

---

## 7. Types of L7 Load Balancing

### 7.1 HTTP Reverse Proxy Load Balancer

Classic L7 proxy.

```text
Client -> Reverse Proxy -> Web Server A
                         -> Web Server B
```

Examples of capabilities:

- TLS termination.
- HTTP routing.
- Header manipulation.
- Compression.
- Static file caching in some products.
- Access logs.

Common tools:

- NGINX.
- HAProxy.
- Envoy.
- Apache HTTPD reverse proxy.
- Cloud HTTP load balancers.

### 7.2 Application Load Balancer

A managed L7 load balancer from a cloud provider.

Common capabilities:

- Managed scaling.
- Managed high availability.
- TLS certificate integration.
- Listener rules.
- Target groups.
- HTTP health checks.
- WAF integration.
- WebSocket support.
- gRPC support in some products.

Best for:

- Most public web applications.
- REST APIs.
- Container services.
- Kubernetes ingress integrations.

### 7.3 Ingress Controller

In Kubernetes, an ingress controller implements L7 routing rules and forwards traffic to services inside the cluster.

```text
Internet
  -> Cloud LB
  -> Ingress Controller
  -> Kubernetes Service
  -> Pods
```

Common ingress controllers:

- NGINX Ingress.
- Envoy Gateway.
- Traefik.
- HAProxy Ingress.
- Cloud provider ingress controllers.

Capabilities:

- Host/path routing.
- TLS termination.
- Certificate automation.
- Rewrite rules.
- Rate limits in some controllers.
- Integration with Kubernetes service discovery.

### 7.4 gRPC-Aware Load Balancer

gRPC uses HTTP/2, but not every HTTP load balancer handles it correctly.

gRPC-aware load balancers understand:

- HTTP/2 streams.
- gRPC service and method.
- gRPC status codes.
- Long-lived streaming RPCs.
- Health checking using gRPC health protocol.

Important issue:

```text
One HTTP/2 connection can carry many gRPC streams.
If load balancing happens only per TCP connection, traffic may not spread well.
```

For gRPC, request or stream-level balancing is usually better than pure connection-level balancing.

### 7.5 WebSocket-Aware L7 Load Balancer

WebSocket starts as HTTP, then upgrades to a persistent connection.

```text
Client
  -> HTTP GET with Upgrade: websocket
  -> L7 LB
  -> WebSocket server
```

Capabilities:

- Route the initial upgrade by host/path/header.
- Maintain the upgraded TCP connection.
- Apply idle timeout.
- Drain connections during deploys.

Limitations:

- After upgrade, the load balancer generally does not understand application messages.
- Sticky sessions or external connection state may be required.

### 7.6 Service Mesh Proxy

A service mesh proxy, such as Envoy-based sidecars or ambient mesh components, can load balance internal service-to-service traffic.

```text
Service A
  -> local proxy
  -> mesh load balancing
  -> Service B instance
```

Capabilities:

- mTLS between services.
- Retries and timeouts.
- Circuit breaking.
- Traffic splitting.
- Service discovery.
- Request metrics.
- Distributed tracing headers.
- Policy enforcement.

Best for:

- Internal microservice traffic.
- Zero-trust service networking.
- Gradual rollouts.
- Deep service observability.

### 7.7 Edge/CDN Load Balancer

An edge or CDN load balancer routes HTTP traffic at globally distributed locations.

Capabilities:

- Global routing.
- Static asset caching.
- TLS at edge.
- DDoS protection.
- WAF.
- Bot protection.
- Origin failover.
- Geo routing.

Best for:

- Public websites.
- Media delivery.
- APIs with global users.
- Reducing origin load.

---

## 8. L4 vs L7 Comparison

| Aspect | L4 Load Balancer | L7 Load Balancer |
|--------|------------------|------------------|
| OSI layer | Transport | Application |
| Protocols | TCP, UDP, TLS | HTTP, HTTPS, HTTP/2, gRPC, WebSocket |
| Routing granularity | Connection/flow | Request/route |
| Routing keys | IP, port, protocol | Host, path, method, header, cookie |
| Payload inspection | No | Yes |
| Performance | Higher throughput, lower latency | More overhead due to parsing |
| TLS | Pass-through or terminate | Usually terminates TLS |
| Health check depth | TCP/TLS/basic probes | HTTP/gRPC application health |
| Session persistence | Source IP or connection hash | Cookie/header/application metadata |
| Retries | Limited and risky | Request-aware retries possible |
| WAF | Not usually | Common |
| Protocol flexibility | Very high | Limited to supported app protocols |
| Best for | TCP/UDP services, long connections, pass-through | Web apps, APIs, microservices |

Rule of thumb:

```text
Use L4 when you need fast protocol-agnostic connection forwarding.
Use L7 when you need HTTP-aware routing, policy, or observability.
```

---

## 9. Load Balancing Algorithms

### 9.1 Round Robin

Routes requests or connections in sequence.

```text
A, B, C, A, B, C
```

Best for:

- Equal-capacity servers.
- Similar request cost.

Weakness:

- Does not account for slow or overloaded targets.

### 9.2 Weighted Round Robin

Targets receive traffic proportional to configured weights.

```text
A weight 5
B weight 3
C weight 1
```

Best for:

- Mixed instance sizes.
- Gradual traffic shifting.
- Blue-green or canary releases.

### 9.3 Least Connections

Routes to the target with the fewest active connections.

Best for:

- Long-lived connections.
- Variable request durations.
- WebSocket or database connection pools.

Weakness:

- A connection count is not always the same as real CPU or memory pressure.

### 9.4 Weighted Least Connections

Combines target capacity weights with active connection count.

Best for:

- Mixed-capacity backends.
- Long-running requests.

### 9.5 Least Response Time

Routes to the backend with the best observed latency and active load.

Best for:

- Latency-sensitive applications.
- Dynamic workloads.

Weakness:

- Needs good measurements.
- Can overreact if not smoothed.

### 9.6 Source IP Hash

Hashes client IP to choose a backend.

```text
hash(client_ip) % number_of_backends
```

Best for:

- Simple stickiness.
- Stateful backends when cookies are not available.

Weakness:

- NAT can cause many users to map to the same backend.
- Backend pool changes can remap many clients.

### 9.7 Cookie-Based Affinity

The L7 load balancer sets or reads a cookie to route a client to the same target.

Best for:

- Legacy sessionful web apps.
- Shopping carts or server-side sessions.

Weakness:

- Reduces load distribution flexibility.
- Can make deploys and failover harder.

### 9.8 Consistent Hashing

Maps keys and backends onto a hash ring so only a small portion of keys move when backends change.

Best for:

- Cache clusters.
- Stateful routing.
- Sharded services.
- Sticky routing by tenant, user, channel, or key.

Example:

```text
route_key = user_id or tenant_id or cache_key
backend = consistent_hash(route_key)
```

### 9.9 Random With Two Choices

Pick two random healthy targets, then choose the less loaded one.

Best for:

- Very large backend pools.
- Reducing central coordination overhead.

Why it works:

- It gives much better balance than pure random with very low overhead.

### 9.10 Maglev / Ring Hash / Rendezvous Hashing

Advanced hashing algorithms used in high-scale load balancers and service meshes.

Best for:

- Stable backend assignment.
- Large-scale traffic distribution.
- Minimizing churn when backends change.

---

## 10. Health Checks

Health checks determine whether a target should receive traffic.

### 10.1 L4 Health Checks

Common checks:

- TCP connection succeeds.
- TLS handshake succeeds.
- UDP probe response received.
- Custom protocol probe succeeds.

Example:

```text
LB opens TCP connection to backend:443
If connection succeeds, target is considered healthy.
```

Pros:

- Fast.
- Simple.
- Works for non-HTTP protocols.

Cons:

- A port can be open while the application is broken.
- Does not prove dependencies are healthy.

### 10.2 L7 Health Checks

Common checks:

- `GET /health` returns `200`.
- `GET /ready` returns `200` only after dependencies are ready.
- Response body contains expected text.
- gRPC health service returns `SERVING`.

Example:

```text
GET /ready

200 OK
{
  "status": "ready",
  "database": "ok",
  "cache": "ok"
}
```

Better health model:

- **Liveness**: should the process be restarted?
- **Readiness**: should the instance receive traffic?
- **Startup**: has slow initialization completed?
- **Dependency health**: are required downstreams available?

Avoid:

- Marking an instance unhealthy because an optional dependency is down.
- Doing very expensive health checks.
- Using only a shallow port check for critical HTTP applications.

---

## 11. TLS Termination Patterns

### 11.1 Terminate at Load Balancer

```text
Client -> HTTPS -> LB -> HTTP -> Backend
```

Pros:

- Central certificate management.
- Simpler backend configuration.
- L7 routing becomes possible.
- WAF and HTTP policy can be applied.

Cons:

- Backend traffic is plaintext unless private network is trusted.
- May not satisfy strict end-to-end encryption requirements.

### 11.2 Terminate and Re-Encrypt

```text
Client -> HTTPS -> LB -> HTTPS -> Backend
```

Pros:

- L7 inspection and routing at load balancer.
- Encryption on internal network.
- Good security baseline.

Cons:

- More certificate and CPU overhead.
- More operational complexity.

### 11.3 TLS Pass-Through

```text
Client -> HTTPS -> L4 LB -> HTTPS -> Backend
```

Pros:

- End-to-end encryption.
- Backend controls TLS and client certificates.
- Good for mTLS-heavy systems.

Cons:

- No HTTP inspection at load balancer.
- No path or header routing.
- WAF and API policy must move elsewhere.

---

## 12. Session Persistence and Stickiness

Stateless services do not need sticky sessions. Any healthy backend can process any request.

```text
Good design:
Session state -> Redis/database/token
Any app server can serve any request
```

Sticky sessions are sometimes needed when:

- Server stores session in memory.
- WebSocket connection state is local.
- Large local cache warming is important.
- A protocol requires connection affinity.
- Legacy app cannot be made stateless quickly.

Stickiness methods:

| Method | Layer | Notes |
|--------|-------|-------|
| Source IP affinity | L4 | Simple but poor with NAT/mobile networks. |
| 5-tuple hash | L4 | Stable per connection or flow. |
| Cookie affinity | L7 | Better for browsers and HTTP sessions. |
| Header affinity | L7 | Useful for tenant or version routing. |
| Consistent hash by key | L4/L7 | Good for caches and sharded services. |

Tradeoff:

```text
Stickiness improves locality but reduces balancing quality and failover flexibility.
```

---

## 13. Connection Draining and Graceful Deploys

During deploys, a load balancer should stop sending new traffic to an instance before terminating it.

Flow:

```text
1. Mark instance draining.
2. Stop routing new requests or connections to it.
3. Allow in-flight requests to finish.
4. Close or wait for long-lived connections.
5. Terminate instance.
```

For HTTP:

- Drain usually waits for active requests to complete.
- Keep-alive connections may be closed after a grace period.

For WebSocket/MQTT:

- Connections can last hours.
- You need max drain time, reconnect hints, or connection migration strategy.

For gRPC streaming:

- Long streams need explicit timeout and retry/resume behavior.
- Client should handle `GOAWAY` or unavailable responses.

---

## 14. API Gateway

An API Gateway is an L7 component that exposes APIs to clients and applies API-specific policies before routing traffic to backend services.

It is usually placed at the boundary between external clients and internal services.

```text
Mobile App / Web App / Partner
  -> API Gateway
      -> AuthN/AuthZ
      -> Rate limit
      -> Quota
      -> Request validation
      -> API routing
      -> Observability
      -> Transformation
  -> Internal services
```

An API Gateway is more than a load balancer. It may use load balancing internally, but its main purpose is API management and governance.

---

## 15. API Gateway Capabilities

### 15.1 API Routing

Routes external API calls to internal services.

```text
GET /v1/users/123      -> user-service
POST /v1/orders        -> order-service
POST /v1/payments      -> payment-service
GET /v1/recommendation -> recommendation-service
```

Routing can be based on:

- Host.
- Path.
- Method.
- Header.
- API version.
- Tenant.
- Client application.

### 15.2 Authentication

Verifies who the caller is.

Common methods:

- JWT validation.
- OAuth 2.0 access tokens.
- OpenID Connect.
- API keys.
- mTLS client certificates.
- HMAC signatures.
- Session cookies.

Example:

```text
Client sends:
Authorization: Bearer <access_token>

Gateway:
  validates signature
  validates issuer
  validates audience
  validates expiration
  extracts subject and claims
```

### 15.3 Authorization

Decides what the caller can do.

Examples:

- User can read only their own orders.
- Partner can call only partner APIs.
- Admin can call privileged endpoints.
- Tenant A cannot access Tenant B data.

Authorization patterns:

| Pattern | Where Decision Happens | Notes |
|---------|------------------------|-------|
| Coarse-grained gateway authZ | API Gateway | Good for endpoint-level access. |
| Fine-grained service authZ | Backend service | Required for resource-level decisions. |
| External policy engine | OPA, Cedar, custom PDP | Central policy with service integration. |

Important rule:

```text
Do coarse authorization at the gateway.
Do business-critical fine-grained authorization in the service too.
```

The backend should not blindly trust that the gateway caught every authorization case.

### 15.4 Rate Limiting

Controls request rate.

Examples:

- 100 requests per second per API key.
- 10 login attempts per minute per IP.
- 1,000 requests per minute per tenant.
- 50 requests per second for expensive search endpoint.

Algorithms:

- Token bucket.
- Leaky bucket.
- Fixed window.
- Sliding window.
- Sliding log.

Rate limit keys:

- API key.
- User ID.
- Tenant ID.
- IP address.
- Route.
- Method.
- Client application.

### 15.5 Quotas

Quotas limit total usage over a larger window.

Examples:

- 1 million requests per month for free plan.
- 100 GB data transfer per day.
- 10,000 payment API calls per day.

Rate limits protect real-time stability.
Quotas enforce business and product limits.

### 15.6 Request Validation

The gateway can reject invalid requests before they reach services.

Validation examples:

- Required headers.
- Required query parameters.
- JSON schema validation.
- Request size limits.
- Content type checks.
- API version checks.
- Method restrictions.

Benefits:

- Reduces load on backend.
- Gives consistent error responses.
- Blocks malformed traffic early.

### 15.7 Request and Response Transformation

Transforms external API shape to internal service shape.

Examples:

- Rename headers.
- Add correlation IDs.
- Convert XML to JSON.
- Map `/v1/customerId` to internal `/users/id`.
- Remove internal fields from response.
- Normalize error responses.
- Add default values.

Use carefully:

```text
Small transformations at the gateway are useful.
Large business transformations can turn the gateway into a bottleneck and coupling point.
```

### 15.8 Protocol Translation

The gateway can translate protocols.

Examples:

- REST client -> gRPC backend.
- HTTP JSON -> internal event command.
- External HTTP -> internal SOAP.
- WebSocket client -> internal pub/sub.

Useful for:

- Modernizing legacy systems.
- Supporting browser clients.
- Hiding internal protocols.

Tradeoff:

- Protocol translation can make debugging harder.
- The gateway becomes part of the contract.

### 15.9 API Versioning

Gateway can route or enforce versions.

Versioning styles:

- Path: `/v1/orders`.
- Header: `Accept: application/vnd.company.v2+json`.
- Query: `?version=2`.
- Host: `v2.api.example.com`.

Gateway use:

```text
/v1/orders -> old order service
/v2/orders -> new order service
```

### 15.10 Caching

API Gateway may cache safe responses.

Good candidates:

- Public product catalog.
- Feature flags.
- Reference data.
- Exchange rates with TTL.
- User profile fragments with careful invalidation.

Avoid caching:

- Payment mutations.
- Sensitive user data unless keys and isolation are correct.
- Highly personalized responses without tenant/user cache key.

Cache key must include relevant dimensions:

```text
method + path + query + tenant + user/role + accept-language + auth scope
```

### 15.11 Observability

API Gateway is a strong place to collect edge API telemetry.

Useful data:

- Request count.
- Status code.
- Latency.
- Upstream latency.
- Route.
- Client application.
- Tenant.
- API key ID.
- Rate-limit decisions.
- Auth failures.
- Request ID and trace ID.

Logs should avoid:

- Raw passwords.
- Tokens.
- Full credit card numbers.
- Sensitive personal data.

### 15.12 Security Controls

Common gateway security features:

- TLS termination.
- mTLS for clients or partners.
- JWT validation.
- API key validation.
- IP allow/deny lists.
- Bot detection integration.
- WAF integration.
- Request body size limits.
- Header normalization.
- CORS policy.
- Schema validation.
- Threat protection for injection patterns.

### 15.13 Developer Portal and API Management

Full API management platforms may provide:

- API catalog.
- Documentation.
- Client onboarding.
- API key issuance.
- Subscription plans.
- Usage analytics.
- Billing integration.
- SDK generation.
- Deprecation notices.
- Approval workflows.

This is usually beyond a basic L7 load balancer.

---

## 16. API Gateway vs L7 Load Balancer

An API Gateway is usually implemented as an L7 proxy, but it has a different purpose.

| Aspect | L7 Load Balancer | API Gateway |
|--------|------------------|-------------|
| Primary job | Route HTTP traffic to healthy backends | Manage, secure, and govern APIs |
| Traffic unit | HTTP request | API call and API contract |
| Routing | Host/path/header/cookie | API route, version, tenant, client, product |
| AuthN/AuthZ | Basic or integrated in some products | Core capability |
| Rate limiting | Sometimes | Core capability |
| Quotas/plans | Rare | Common |
| Request validation | Limited to moderate | Strong API schema validation |
| Transformation | Basic rewrites | Rich request/response mapping |
| Developer portal | No | Often yes |
| API keys/subscriptions | No or minimal | Common |
| Monetization | No | Sometimes |
| Best for | Web routing, traffic distribution | Public/private API platform |

Simple distinction:

```text
L7 Load Balancer:
  "Where should this HTTP request go?"

API Gateway:
  "Is this API caller allowed, within limits, sending a valid contract,
   and where should the call go?"
```

---

## 17. API Gateway vs Reverse Proxy

| Aspect | Reverse Proxy | API Gateway |
|--------|---------------|-------------|
| Main focus | Proxy requests to servers | Govern API usage |
| Routing | Host/path | API route/version/consumer |
| Security | TLS, headers, sometimes WAF | Auth, quotas, API keys, scopes, policies |
| Transformation | Often basic | Often advanced |
| API lifecycle | Not usually | Often includes docs, versions, plans |
| Target users | Web/app operators | API platform teams and consumers |

Every API Gateway is a reverse proxy in the traffic path.
Not every reverse proxy is an API Gateway.

---

## 18. API Gateway vs Service Mesh

| Aspect | API Gateway | Service Mesh |
|--------|-------------|--------------|
| Traffic direction | North-south, client to platform | East-west, service to service |
| Primary users | External clients, partners, apps | Internal services |
| Policies | API auth, quotas, versioning | mTLS, retries, circuit breaking, service policy |
| Deployment | Central gateway layer | Sidecars, node proxies, or mesh data plane |
| Contract focus | API product contract | Service communication contract |
| Examples | Kong, Apigee, AWS API Gateway, Azure API Management | Istio, Linkerd, Consul, Kuma |

Common architecture:

```text
External client
  -> API Gateway
  -> Internal service
  -> Service mesh proxy
  -> Another internal service
```

Use both when:

- External API governance is needed.
- Internal service-to-service security and observability are also needed.

---

## 19. API Gateway vs BFF

BFF means Backend for Frontend.

| Aspect | API Gateway | BFF |
|--------|-------------|-----|
| Main purpose | Cross-cutting API governance | Client-specific aggregation and experience |
| Logic type | Auth, limits, routing, validation | UI-specific composition and orchestration |
| Scope | Shared API boundary | Specific frontend, such as mobile or web |
| Ownership | Platform/API team | Product/frontend-aligned team |

Example:

```text
Mobile App
  -> Mobile BFF
  -> API Gateway
  -> Services
```

Or:

```text
Mobile App
  -> API Gateway
  -> Mobile BFF
  -> Services
```

The exact order depends on ownership, network boundary, and security model.

Rule:

```text
Do not put UI-specific aggregation logic in a shared API Gateway unless it is truly reusable.
```

---

## 20. API Gateway Deployment Patterns

### 20.1 Single Shared Gateway

```text
All clients -> One API Gateway -> All services
```

Pros:

- Centralized control.
- Easier consistent policies.
- One external entry point.

Cons:

- Can become a bottleneck.
- Many teams depend on one shared layer.
- Risk of large configuration complexity.

### 20.2 Gateway per Domain

```text
api.example.com/orders   -> order gateway
api.example.com/payments -> payment gateway
api.example.com/users    -> user gateway
```

Pros:

- Domain ownership.
- Smaller blast radius.
- Independent deployment.

Cons:

- More gateways to operate.
- Policy consistency requires governance.

### 20.3 Gateway per Client Type

```text
Mobile app  -> mobile API gateway
Web app     -> web API gateway
Partners    -> partner API gateway
```

Pros:

- Tailored policies by client.
- Partner APIs can be isolated.
- Different auth and rate limits per surface.

Cons:

- Possible duplication.
- Version management can get complex.

### 20.4 Edge Gateway plus Internal Gateway

```text
Internet
  -> Edge Gateway
      -> auth, WAF, DDoS, TLS
  -> Internal Gateway
      -> service routing, internal policies
  -> Services
```

Pros:

- Strong security separation.
- Good for large enterprises.
- Clear external/internal boundary.

Cons:

- More hops.
- More latency.
- More operational complexity.

---

## 21. Where L4, L7, and API Gateway Sit Together

A realistic stack can use all of them.

```text
Internet Client
  -> DNS / Global Traffic Manager
  -> Edge L4 or Anycast Layer
  -> L7 Load Balancer / CDN / WAF
  -> API Gateway
  -> Internal L7 Service Load Balancer
  -> Service Mesh
  -> Backend Service
  -> Database behind L4 Load Balancer
```

Not every system needs every layer. Add layers only when they provide real value.

### Example: Public REST API

```text
Client
  -> DNS
  -> CDN/WAF
  -> API Gateway
  -> L7 internal load balancer
  -> microservices
```

Why:

- CDN/WAF protects and accelerates edge traffic.
- API Gateway handles auth, rate limits, quotas, API versioning.
- Internal L7 load balancing routes to healthy service instances.

### Example: Database Cluster

```text
App
  -> L4 Load Balancer
  -> Database primary/replica endpoints
```

Why:

- Database protocol is TCP and not HTTP.
- Need low overhead and protocol pass-through.

### Example: WebSocket Chat System

```text
Client
  -> L4 or L7 Load Balancer
  -> Gateway servers holding WebSocket connections
  -> Redis/Kafka/PubSub
  -> Channel/message services
```

Why:

- Initial WebSocket handshake may use L7 routing.
- Long-lived connection behavior must be tuned.
- Message fanout usually needs a pub/sub backbone, not just a load balancer.

### Example: gRPC Microservices

```text
Service A
  -> gRPC-aware L7 proxy or service mesh
  -> Service B instances
```

Why:

- HTTP/2 multiplexing can make pure L4 balancing uneven.
- gRPC status, method routing, deadlines, and retries need protocol awareness.

---

## 22. Choosing Between L4, L7, and API Gateway

### 22.1 Choose L4 When

- Traffic is TCP or UDP and not HTTP-aware.
- You need very low latency.
- You need TLS pass-through.
- You need static IPs.
- You need source IP preservation.
- You are balancing databases, caches, message brokers, MQTT, or custom protocols.
- You have long-lived connections and simple routing needs.

### 22.2 Choose L7 When

- Traffic is HTTP, HTTPS, gRPC, or WebSocket.
- You need host/path/header/cookie routing.
- You need centralized TLS termination.
- You need HTTP redirects or rewrites.
- You need better request logs.
- You need HTTP health checks.
- You need canary or weighted routing by route.
- You need WAF integration.

### 22.3 Choose API Gateway When

- You expose APIs to web, mobile, third-party, or partner clients.
- You need authentication and authorization at the edge.
- You need API keys, subscriptions, quotas, or usage plans.
- You need per-consumer rate limits.
- You need request validation against an API contract.
- You need API versioning and lifecycle management.
- You need developer portal or API onboarding.
- You need protocol translation or response transformation.
- You need API analytics per consumer or tenant.

### 22.4 Avoid API Gateway When

- You only need simple web traffic distribution.
- All traffic is internal and already managed by service mesh.
- You do not need API-level policy.
- The gateway would become a place for business logic.
- Latency budget is extremely tight and gateway features are unused.

---

## 23. Common Architecture Patterns

### 23.1 Simple Web App

```text
Browser
  -> L7 Load Balancer
  -> Web app instances
  -> Database
```

Use:

- L7 load balancer for TLS and path routing.
- No API Gateway unless API management is needed.

### 23.2 Public API Platform

```text
Client
  -> CDN/WAF
  -> API Gateway
  -> Services
```

Use:

- API Gateway for auth, keys, limits, quotas, validation, analytics.
- L7 load balancing inside or behind the gateway.

### 23.3 High-Performance TCP Service

```text
Client
  -> L4 Load Balancer
  -> TCP service pool
```

Use:

- L4 for low overhead.
- Protocol-specific observability in the service.

### 23.4 Kubernetes Application

```text
Client
  -> Cloud Load Balancer
  -> Ingress Controller
  -> Kubernetes Service
  -> Pods
```

Use:

- Cloud LB for external stable endpoint.
- Ingress for HTTP routing.
- Kubernetes Service for internal pod load balancing.

### 23.5 Enterprise Multi-Layer Edge

```text
Internet
  -> DNS/GSLB
  -> CDN
  -> WAF
  -> L7 Load Balancer
  -> API Gateway
  -> Internal services
```

Use:

- DNS/GSLB for regional routing.
- CDN for caching and edge performance.
- WAF for attack filtering.
- API Gateway for API governance.
- Internal load balancing for service pools.

---

## 24. Reliability Considerations

### 24.1 Avoid Single Points of Failure

Load balancers must be highly available.

Good design:

- Multi-AZ load balancer.
- Multiple gateway replicas.
- Health checks.
- Automated target registration.
- Failover testing.
- No manual backend list updates.

### 24.2 Use Timeouts Everywhere

Important timeouts:

- Client request timeout.
- Load balancer idle timeout.
- Backend connect timeout.
- Backend response timeout.
- Gateway policy timeout.
- Streaming timeout.
- Drain timeout.

Bad timeout setup can cause:

- Hung connections.
- Thread pool exhaustion.
- Retry storms.
- Broken WebSocket/gRPC streams.

### 24.3 Be Careful With Retries

Retries are useful for transient failures, but dangerous for non-idempotent operations.

Safer to retry:

- GET.
- HEAD.
- Idempotent PUT.
- Requests with idempotency keys.

Risky to retry:

- Payment charge.
- Order creation.
- Message publish.
- Any mutation without idempotency protection.

### 24.4 Use Circuit Breakers and Outlier Detection

Advanced L7 load balancers, API gateways, and service meshes can detect bad upstreams.

Capabilities:

- Eject targets with high error rate.
- Stop routing to slow targets.
- Limit concurrent requests.
- Fail fast when dependency is unhealthy.

### 24.5 Plan for Overload

Overload controls:

- Queue limits.
- Rate limits.
- Concurrency limits.
- Request body size limits.
- Load shedding.
- Priority traffic.
- Backpressure.
- Graceful degradation.

---

## 25. Security Considerations

### 25.1 Client IP Handling

At L7, original client IP is often passed using:

```text
X-Forwarded-For
Forwarded
X-Real-IP
```

Risk:

```text
Clients can spoof these headers unless the edge overwrites or sanitizes them.
```

Best practice:

- Strip incoming forwarded headers at the trusted edge.
- Re-add trusted headers.
- Configure backends to trust only known proxy IPs.

### 25.2 Header Normalization

Gateways and L7 proxies should normalize or reject ambiguous headers.

Examples:

- Duplicate `Content-Length`.
- Conflicting `Transfer-Encoding`.
- Oversized headers.
- Invalid characters.

This helps prevent request smuggling and proxy parsing inconsistencies.

### 25.3 TLS Policy

Decide:

- Minimum TLS version.
- Allowed ciphers.
- Certificate rotation process.
- mTLS requirements.
- Whether backend traffic is re-encrypted.

### 25.4 WAF vs API Gateway

| Control | WAF | API Gateway |
|---------|-----|-------------|
| SQL injection pattern blocking | Strong | Sometimes |
| Bot and attack signatures | Strong | Sometimes |
| JWT validation | Usually no | Strong |
| API keys and quotas | Usually no | Strong |
| Schema validation | Limited | Strong |
| API analytics | Limited | Strong |

They complement each other.

---

## 26. Observability Checklist

Track at each layer:

- Requests or connections per second.
- Active connections.
- New connections per second.
- Backend target health.
- Backend error rate.
- 4xx and 5xx status codes.
- P50, P90, P95, P99 latency.
- TLS handshake errors.
- Timeout count.
- Retry count.
- Rate-limited requests.
- Authentication failures.
- Request size and response size.
- Top routes and top consumers.

For API Gateway specifically:

- API key ID or client app ID.
- Tenant ID.
- User subject, if safe to log.
- Route ID.
- Policy decision.
- Quota consumption.
- Auth failure reason.
- Upstream service latency.

---

## 27. Common Mistakes

| Mistake | Why It Hurts | Better Approach |
|---------|--------------|-----------------|
| Using L7 for every protocol | Breaks or slows non-HTTP protocols | Use L4 for TCP/UDP protocols |
| Using L4 for APIs that need policy | No auth, quota, or route-level control | Use API Gateway or L7 proxy |
| Relying only on TCP health checks | Port open does not mean app is ready | Use readiness endpoints |
| Retrying unsafe POST requests | Can duplicate side effects | Use idempotency keys |
| Sticky sessions by default | Reduces resilience and balance | Make services stateless where possible |
| Putting business logic in API Gateway | Gateway becomes coupled bottleneck | Keep domain logic in services |
| No connection draining | Deploys drop user traffic | Configure drain and graceful shutdown |
| Bad idle timeouts | Breaks WebSocket/gRPC/SSE | Tune per protocol |
| Trusting client-sent `X-Forwarded-For` | Enables IP spoofing | Sanitize at edge |
| No rate limits | One consumer can overload platform | Apply per-user/tenant/client limits |

---

## 28. Interview-Ready Summary

Use this concise explanation:

```text
A Layer 4 load balancer distributes TCP or UDP connections using network
metadata such as IP, port, and protocol. It is fast, protocol-agnostic, and
good for databases, message brokers, MQTT, WebSockets, TLS pass-through, and
other long-lived or non-HTTP traffic.

A Layer 7 load balancer understands application protocols such as HTTP,
HTTPS, gRPC, and WebSocket upgrade. It can route by host, path, headers,
cookies, and methods. It supports TLS termination, HTTP health checks,
rewrites, redirects, WAF integration, canary routing, and request-level logs.

An API Gateway is an L7 component focused on API governance. It may load
balance, but its real job is authentication, authorization, rate limiting,
quotas, API keys, request validation, transformation, versioning, analytics,
and developer onboarding. L7 load balancer asks where a request should go.
API Gateway asks whether the API call is valid, allowed, within limits, and
then where it should go.
```

---

## 29. Decision Table

| Requirement | Best Fit |
|-------------|----------|
| TCP database traffic | L4 load balancer |
| UDP game traffic | L4 load balancer |
| TLS pass-through | L4 load balancer |
| Static IP endpoint | Usually L4 or global accelerator |
| Path-based routing | L7 load balancer |
| Host-based routing | L7 load balancer |
| HTTP redirects | L7 load balancer |
| Web app TLS termination | L7 load balancer |
| Public REST API with auth and quotas | API Gateway |
| Partner API with API keys | API Gateway |
| Request schema validation | API Gateway |
| Developer portal | API Gateway/API management platform |
| Internal service-to-service mTLS | Service mesh |
| Global routing to nearest region | DNS/GSLB/CDN/global LB |
| Static assets and edge caching | CDN |
| Web attack filtering | WAF plus L7/API Gateway |

---

## 30. Final Mental Model

```text
DNS/GSLB:
  Which region or edge should the user hit?

L4 Load Balancer:
  Which backend should get this TCP/UDP connection?

L7 Load Balancer:
  Which backend should get this HTTP/gRPC request?

API Gateway:
  Is this API call authenticated, authorized, valid, within quota,
  observable, and mapped to the right internal service?

Service Mesh:
  How should internal services securely and reliably talk to each other?
```

If you remember only one thing:

```text
L4 is connection-level traffic distribution.
L7 is request-level traffic distribution.
API Gateway is API-level control, governance, and protection.
```
