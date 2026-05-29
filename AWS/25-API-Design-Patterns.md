# API Design & Communication Patterns - Complete Guide

---

## 1. API Styles Comparison

| | REST | GraphQL | gRPC |
|--|---|---|---|
| Protocol | HTTP/1.1 (JSON) | HTTP/1.1 (JSON) | HTTP/2 (Protobuf) |
| Contract | OpenAPI/Swagger | Schema + Types | .proto files |
| Data format | JSON (text) | JSON (text) | Protocol Buffers (binary) |
| Performance | Good | Good | Excellent (10× faster serialization) |
| Streaming | SSE, WebSocket (addon) | Subscriptions (WebSocket) | Native bidirectional streaming |
| Caching | HTTP caching (CDN, ETag) | Difficult (all POST) | Not HTTP-cacheable |
| Tooling | Mature, universal | Good (Apollo, Relay) | Good (grpc-tools, protoc) |
| Learning curve | Low | Medium | Medium-High |
| Browser support | Native | Native | Needs grpc-web proxy |
| **Best for** | Public APIs, CRUD, caching | BFF, mobile, complex nested data | Microservices, low-latency, streaming |

---

## 2. REST API Design

### Resource-Oriented Design
```
Nouns (resources), not verbs (actions):
  ✓ GET /users/123/orders       (get user's orders)
  ✗ GET /getUserOrders?id=123   (RPC-style, avoid)
  
  ✓ POST /orders                (create order)
  ✗ POST /createOrder           (verb in URL, avoid)
  
  ✓ PATCH /orders/456/status    (update order status)
  ✗ POST /updateOrderStatus     (verb in URL, avoid)
```

### HTTP Methods Semantics
| Method | Idempotent | Safe | Use |
|--------|-----------|------|-----|
| GET | Yes | Yes | Retrieve resource(s) |
| POST | No | No | Create resource, trigger action |
| PUT | Yes | No | Full replace of resource |
| PATCH | No* | No | Partial update |
| DELETE | Yes | No | Remove resource |
| HEAD | Yes | Yes | Like GET but no body (check existence) |
| OPTIONS | Yes | Yes | CORS preflight, API discovery |

*PATCH can be made idempotent with careful design

### HTTP Status Codes
| Code | Meaning | When to Use |
|------|---------|-------------|
| 200 OK | Success | GET, PUT, PATCH successful |
| 201 Created | Resource created | POST successful (include Location header) |
| 202 Accepted | Async processing started | Long-running operations |
| 204 No Content | Success, no body | DELETE successful |
| 301 Moved | Permanent redirect | Resource URL changed permanently |
| 304 Not Modified | Cached | Conditional GET (ETag/If-Modified-Since) |
| 400 Bad Request | Client error | Validation failure, malformed request |
| 401 Unauthorized | Not authenticated | Missing or invalid auth token |
| 403 Forbidden | Not authorized | Valid auth but insufficient permissions |
| 404 Not Found | Resource doesn't exist | Invalid resource ID |
| 409 Conflict | State conflict | Duplicate creation, optimistic lock failure |
| 422 Unprocessable | Semantic error | Valid syntax but business rule violation |
| 429 Too Many Requests | Rate limited | Include Retry-After header |
| 500 Internal Server Error | Server error | Unexpected failure |
| 502 Bad Gateway | Upstream error | Downstream service failed |
| 503 Service Unavailable | Temporarily down | Maintenance, overloaded |
| 504 Gateway Timeout | Upstream timeout | Downstream service too slow |

### API Versioning Strategies
| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| URL path | `/v1/users`, `/v2/users` | Simple, explicit, cacheable | URL changes, rigid |
| Header | `Accept: application/vnd.api+json;version=2` | Clean URLs | Hidden, harder to test |
| Query param | `/users?version=2` | Easy to add | Pollutes query string |
| Content negotiation | `Accept: application/vnd.company.v2+json` | RESTful | Complex |
| **Recommended** | URL path (`/v1/`) | Most practical, widely used | |

### Versioning Best Practices
- **Only version on breaking changes** (additive changes don't need new version)
- **Breaking changes:** Removing field, changing type, changing behavior, removing endpoint
- **Non-breaking:** Adding field, adding endpoint, adding optional parameter
- **Sunset policy:** Announce deprecation → 6-12 months → remove old version
- **Maximum 2 supported versions** at any time (current + previous)

---

## 3. Pagination

### Offset-Based (Traditional)
```
GET /orders?page=3&limit=20
Response: { data: [...], total: 1500, page: 3, limit: 20, pages: 75 }
```
- **Pros:** Simple, user can jump to any page
- **Cons:** Inconsistent with real-time data (items shift between pages), slow for large offsets (DB scans)

### Cursor-Based (Recommended for large datasets)
```
GET /orders?limit=20&cursor=eyJpZCI6MTIzfQ==
Response: { 
  data: [...], 
  cursors: { 
    next: "eyJpZCI6MTQzfQ==", 
    previous: "eyJpZCI6MTI0fQ==",
    hasMore: true 
  }
}
```
- **Cursor:** Encoded pointer (usually base64 of last item's ID/timestamp)
- **Pros:** Consistent (immune to insertions/deletions), efficient (index seek)
- **Cons:** Can't jump to arbitrary page, cursor may expire

### Keyset Pagination (Seek method)
```sql
-- Instead of: SELECT * FROM orders OFFSET 10000 LIMIT 20 (slow!)
-- Use: SELECT * FROM orders WHERE id > 10000 ORDER BY id LIMIT 20 (fast!)
```

---

## 4. Idempotency

### Why Idempotency Matters
```
Client → POST /payments → Server (processes payment)
Network error: Client doesn't receive response
Client retries: POST /payments → Server processes AGAIN?!
Result: Double charge! 

Solution: Idempotency key
Client → POST /payments (Idempotency-Key: "abc-123") → Server
  Server: "I already processed abc-123, return cached response"
```

### Implementation Pattern
```python
# Idempotency implementation
@app.route('/payments', methods=['POST'])
def create_payment():
    idempotency_key = request.headers.get('Idempotency-Key')
    
    if not idempotency_key:
        return error(400, "Idempotency-Key header required")
    
    # Check if already processed
    existing = dynamodb.get_item(
        TableName='idempotency',
        Key={'key': idempotency_key}
    )
    
    if existing:
        return existing['response']  # Return cached response
    
    # Process payment
    result = process_payment(request.json)
    
    # Store result with TTL (24 hours)
    dynamodb.put_item(
        TableName='idempotency',
        Item={
            'key': idempotency_key,
            'response': result,
            'ttl': int(time.time()) + 86400
        },
        ConditionExpression='attribute_not_exists(#k)',  # Prevent race condition
        ExpressionAttributeNames={'#k': 'key'}
    )
    
    return result
```

### Idempotency Rules
- **GET, PUT, DELETE:** Naturally idempotent (safe to retry)
- **POST:** NOT idempotent → requires explicit idempotency key
- **Key generation:** Client generates UUID or deterministic hash of request
- **TTL:** Keys expire after 24 hours (don't store forever)
- **Scope:** Per API key/user + idempotency key (different users can reuse same key)

---

## 5. Rate Limiting

### Algorithms
| Algorithm | How | Pros | Cons |
|-----------|-----|------|------|
| Fixed Window | Count requests per time window | Simple | Burst at window edges |
| Sliding Window | Rolling window average | Smooth | More complex |
| Token Bucket | Tokens added at rate, consumed per request | Allows burst | Slightly complex |
| Leaky Bucket | Queue requests, process at fixed rate | Smooth output | No burst tolerance |

### Rate Limit Headers (RFC 6585 / draft-ietf-httpapi-ratelimit-headers)
```
HTTP/1.1 429 Too Many Requests
RateLimit-Limit: 100
RateLimit-Remaining: 0
RateLimit-Reset: 1705312800
Retry-After: 30
```

### Multi-Tier Rate Limiting
```
API Gateway:
  Per-IP: 1000 req/sec (DDoS protection)
  Per-API-Key: 100 req/sec (fair usage)
  Per-Endpoint: POST /payments: 10 req/sec (expensive operation)
  
Application level:
  Per-User: 50 req/min for free tier, 500 req/min for paid
  Per-Resource: /reports/generate: 5 req/hour (heavy computation)
  
Implementation (AWS):
  API Gateway: Usage plans + API keys (built-in throttling)
  WAF: Rate-based rules (per-IP)
  Application: Token bucket in ElastiCache (Redis INCR + TTL)
```

---

## 6. API Authentication & Security

### Authentication Methods
| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| API Key | Server-to-server, public APIs | Simple | Can't identify user, no expiry |
| Bearer Token (JWT) | User-facing APIs | Stateless, no DB lookup | Can't revoke easily, size |
| OAuth 2.0 | Third-party access | Standard, scoped | Complex |
| mTLS | Service-to-service (internal) | Strong mutual auth | Certificate management |
| AWS Signature V4 | AWS API access | Secure, timestamp-bound | AWS-specific, complex |

### JWT Best Practices
```
Token structure:
  Header: { "alg": "RS256", "kid": "key-1" }
  Payload: { "sub": "user-123", "exp": 1705312800, "scope": "read write" }
  Signature: RS256(header + payload, private_key)

Best practices:
  - Short expiry (15 min access token, 7 day refresh token)
  - Use RS256 (asymmetric) not HS256 (symmetric) for services
  - Include only necessary claims (minimize token size)
  - Key rotation: "kid" header + JWKS endpoint for public keys
  - Revocation: Token blacklist in Redis (for compromised tokens)
  - Don't store sensitive data in JWT (it's base64, not encrypted)
```

### API Security Checklist
```
Transport:
  ✓ TLS 1.2+ only (HSTS header)
  ✓ Certificate pinning (mobile apps)

Authentication:
  ✓ OAuth 2.0 / JWT for user-facing
  ✓ mTLS for service-to-service
  ✓ Rotate API keys regularly

Authorization:
  ✓ Principle of least privilege (scoped tokens)
  ✓ RBAC or ABAC for fine-grained access
  ✓ Validate permissions on EVERY request (not just auth)

Input:
  ✓ Validate all input (schema validation, OpenAPI spec)
  ✓ Parameterized queries (prevent SQL injection)
  ✓ Content-Type validation
  ✓ Request size limits (prevent DoS via large payloads)

Output:
  ✓ Don't expose internal errors to clients
  ✓ Remove server version headers
  ✓ Filter response fields (don't return more than needed)
  ✓ CORS configuration (restrict origins)

Rate limiting:
  ✓ Per-user, per-IP, per-endpoint limits
  ✓ Return 429 with Retry-After header
```

---

## 7. GraphQL Design

### When to Use GraphQL
- **Good for:** Mobile apps (minimize data transfer), BFF (Backend for Frontend), nested relationships, rapidly evolving UI
- **Not for:** Simple CRUD, server-to-server, file upload, caching-heavy workloads
- **Anti-patterns:** Using as a database query language, deeply nested queries without limits

### Schema Design
```graphql
type Query {
  user(id: ID!): User
  orders(userId: ID!, first: Int, after: String): OrderConnection!
}

type Mutation {
  createOrder(input: CreateOrderInput!): CreateOrderPayload!
  cancelOrder(id: ID!, reason: String): CancelOrderPayload!
}

type Subscription {
  orderStatusChanged(orderId: ID!): Order!
}

type User {
  id: ID!
  name: String!
  email: String!
  orders(first: Int, after: String): OrderConnection!
}

type Order {
  id: ID!
  status: OrderStatus!
  items: [OrderItem!]!
  total: Money!
  createdAt: DateTime!
}

# Relay-style pagination
type OrderConnection {
  edges: [OrderEdge!]!
  pageInfo: PageInfo!
}
```

### GraphQL Performance Issues & Solutions
| Problem | Solution |
|---------|----------|
| N+1 queries | DataLoader (batching + caching per request) |
| Deep queries | Query depth limiting (max 10 levels) |
| Wide queries | Query complexity analysis (cost per field) |
| Large responses | Pagination (cursor-based, Relay spec) |
| Abuse | Persisted queries (only allow pre-approved queries) |
| Caching | CDN: Persisted queries as GET. App: Response-level caching |

---

## 8. gRPC Design

### When to Use gRPC
- **Ideal:** Microservice-to-microservice, low latency, streaming, polyglot
- **Not ideal:** Browser clients (needs proxy), public APIs (REST more universal)
- **Performance:** 7-10× faster than JSON/REST (binary serialization, HTTP/2 multiplexing)

### Proto File Design
```protobuf
syntax = "proto3";
package orders.v1;

service OrderService {
  // Unary (request-response)
  rpc GetOrder(GetOrderRequest) returns (GetOrderResponse);
  rpc CreateOrder(CreateOrderRequest) returns (CreateOrderResponse);
  
  // Server streaming
  rpc WatchOrderStatus(WatchOrderRequest) returns (stream OrderStatusUpdate);
  
  // Client streaming
  rpc UploadOrderItems(stream OrderItem) returns (UploadResponse);
  
  // Bidirectional streaming
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

message GetOrderRequest {
  string order_id = 1;
}

message Order {
  string id = 1;
  OrderStatus status = 2;
  repeated OrderItem items = 3;
  google.protobuf.Timestamp created_at = 4;
  Money total = 5;
}

enum OrderStatus {
  ORDER_STATUS_UNSPECIFIED = 0;
  ORDER_STATUS_PENDING = 1;
  ORDER_STATUS_CONFIRMED = 2;
  ORDER_STATUS_SHIPPED = 3;
}
```

### gRPC Best Practices
- **Proto file versioning:** `package orders.v1;` (new version = new package)
- **Field numbers:** Never reuse (deleted fields: `reserved 5, 6;`)
- **Default values:** All fields have defaults (0, "", false). Use wrapper types for nullable
- **Backward compatibility:** Only add fields (don't remove or change types)
- **Error handling:** Use gRPC status codes (OK, NOT_FOUND, INVALID_ARGUMENT, etc.)
- **Deadlines:** Always set deadlines (prevent hung connections). Propagate across services
- **Health checking:** gRPC health checking protocol (ALB/NLB support)

### gRPC on AWS
```
External clients:
  CloudFront → ALB (gRPC target group, HTTP/2) → ECS/EKS gRPC service
  
Internal (service mesh):
  Service A → App Mesh (Envoy sidecar, mTLS) → Service B (gRPC)
  
EKS:
  Service A Pod → Kubernetes Service → Service B Pod (gRPC)
  Load balancing: Client-side (grpc-go balancer) or L7 proxy (Envoy/Istio)
  
API Gateway:
  NOT supported for gRPC (use ALB directly)
```

---

## 9. API Gateway Patterns

### Backend for Frontend (BFF)
```
Mobile App → Mobile BFF (GraphQL, optimized payloads) → Microservices
Web App → Web BFF (REST, rich responses) → Microservices
Partner API → Partner Gateway (REST, API keys, rate limiting) → Microservices

Benefits:
  - Optimized per client (mobile gets less data)
  - Independent evolution (mobile team owns mobile BFF)
  - Different auth strategies per client type
```

### API Composition / Aggregation
```
Client: GET /dashboard

API Gateway → Parallel calls:
  → User Service: GET /users/123
  → Order Service: GET /users/123/orders?recent=5
  → Notification Service: GET /users/123/notifications
  → Recommendation Service: GET /users/123/recommendations
  
API Gateway: Aggregate responses → single response to client

Implementation: Lambda authorizer + Step Functions, or custom Node.js aggregator
```

### API Gateway + Service Discovery
```
API Gateway (fixed endpoint) → Service Discovery → Dynamic backends

AWS implementation:
  API Gateway → VPC Link → Cloud Map (AWS Service Discovery)
  → ECS services auto-register/deregister
  
  OR
  
  ALB (path-based routing):
    /api/users/* → User Service target group (ECS auto-scaling)
    /api/orders/* → Order Service target group (ECS auto-scaling)
```

---

## 10. Communication Patterns for Microservices

### Synchronous Patterns
| Pattern | When | Example |
|---------|------|---------|
| Request-Response | Need immediate answer | Payment validation |
| API Gateway | External clients | Mobile/Web → backend |
| Service Mesh | Internal service-to-service | gRPC with mTLS |
| BFF | Client-specific needs | Mobile BFF, Web BFF |

### Asynchronous Patterns
| Pattern | When | Example |
|---------|------|---------|
| Event-driven | Notify interested parties | OrderPlaced → multiple consumers |
| Command queue | Decouple + buffer | SQS between API and worker |
| Saga (choreography) | Distributed transaction | Events trigger next step |
| Saga (orchestration) | Complex distributed transaction | Step Functions coordinates |
| CQRS | Separate read/write models | Event → update read model |

### Choosing Sync vs Async
```
Use SYNCHRONOUS when:
  - Client needs immediate response (user waiting)
  - Operation is fast (< 1 second)
  - Strong consistency required (check balance before debit)
  - Simple request-response (no complex orchestration)

Use ASYNCHRONOUS when:
  - Long-running operation (report generation, video processing)
  - Multiple services need to react (fan-out)
  - Resilience to downstream failures (queue buffers)
  - Eventually consistent is acceptable
  - Traffic spikes need smoothing (queue absorbs burst)
```

### Circuit Breaker Pattern
```python
class CircuitBreaker:
    CLOSED = 'closed'       # Normal operation
    OPEN = 'open'           # Failing, reject immediately
    HALF_OPEN = 'half_open' # Testing if service recovered
    
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
    
    def call(self, func, *args):
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.HALF_OPEN
            else:
                raise CircuitOpenError("Service unavailable")
        
        try:
            result = func(*args)
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
            raise
```

### Retry with Exponential Backoff + Jitter
```python
import random, time

def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError:
            if attempt == max_retries - 1:
                raise
            # Exponential backoff with full jitter
            delay = base_delay * (2 ** attempt)
            jittered_delay = random.uniform(0, delay)
            time.sleep(jittered_delay)
    
# Without jitter: All retries happen at same time (thundering herd)
# With jitter: Retries spread out over time window (reduces contention)
```

---

## 11. API Documentation & Contracts

### OpenAPI (Swagger) Best Practices
```yaml
openapi: 3.1.0
info:
  title: Order Service API
  version: 2.1.0
  description: Manages customer orders
paths:
  /orders:
    post:
      operationId: createOrder
      summary: Create a new order
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          description: Order created
          headers:
            Location:
              schema: { type: string }
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Order'
        '400':
          $ref: '#/components/responses/BadRequest'
        '429':
          $ref: '#/components/responses/RateLimited'
```

### Contract Testing
```
Provider (API owner):
  - Publishes OpenAPI spec (contract)
  - Runs provider verification tests (does implementation match spec?)
  
Consumer (API client):
  - Writes consumer contract tests (what fields/endpoints do I use?)
  - Pact/contract testing framework verifies against provider
  
Benefits:
  - Provider can't break consumer without failing tests
  - Consumer documents exactly what they depend on
  - Decoupled deployment (no need for integration environment)
  
Tools: Pact, Spring Cloud Contract, Prism (OpenAPI mock/validate)
```

---

## 12. Scenario-Based Interview Questions

### Q1: Design API strategy for 100-microservice platform
**Answer:**
```
Standards:
  External (public): REST + OpenAPI 3.1 (universal, cacheable, documented)
  Internal (service-to-service): gRPC (performance, type safety, streaming)
  Mobile BFF: GraphQL (minimize over-fetching, client-driven queries)
  Async: EventBridge events with JSON Schema (event catalog)

Governance:
  API Design Guide: Internal doc with naming conventions, error formats, versioning rules
  API Registry: Backstage catalog (discover all APIs, owners, versions)
  Schema validation: CI pipeline fails if OpenAPI/proto changes break backward compat
  Review process: API design review before implementation (architect approval)
  
Infrastructure:
  External: API Gateway (throttling, auth, WAF) → ALB → Services
  Internal: Service mesh (App Mesh/Istio) → mTLS, observability, retry
  Events: EventBridge + Schema Registry (typed events, versioned)
  
Observability:
  Every API call: Request ID, trace correlation, latency, status code
  SLOs: P99 latency < 200ms (internal), < 500ms (external)
  Dashboard: Per-API error rate, latency percentiles, throughput
  
Versioning:
  REST: URL path (/v1/, /v2/) with 12-month deprecation notice
  gRPC: Package versioning (orders.v1, orders.v2)
  Events: Schema Registry versioning (backward compatible evolution)
```

### Q2: API endpoint handling 10K RPS starts returning 504 timeouts. Diagnose and fix.
**Answer:**
```
Diagnosis (systematic):
  1. Where is timeout? API Gateway → ALB → App → Database?
     - API Gateway logs: Integration latency (time waiting for backend)
     - ALB logs: Target response time
     - X-Ray trace: Which subsegment is slow?
     
  2. Common causes:
     a. Database: Connection pool exhausted (too many concurrent queries)
     b. Downstream service: Dependency is slow/down (cascading failure)
     c. Resource exhaustion: CPU/memory maxed on compute
     d. Thread starvation: All threads blocked waiting
     e. Network: Security group, NAT Gateway capacity, ENI limits
     
  3. Check metrics:
     - RDS: DatabaseConnections near max? CPU? ReadIOPS?
     - ECS/EKS: CPU > 80%? Memory? Task count at max?
     - ALB: TargetResponseTime? UnhealthyHostCount?

Immediate fixes:
  1. Scale horizontally: Increase ECS task count / EKS replicas
  2. Circuit breaker: If downstream is failing, fail fast (return cached/fallback)
  3. Increase timeout at API Gateway (if backend is just slow, not failing)
  4. Add caching: ElastiCache for repeated database queries
  
Long-term fixes:
  1. Connection pooling: RDS Proxy (handles thousands of Lambda/container connections)
  2. Async for heavy operations: Return 202, process in background
  3. Rate limiting: Protect backend from sudden spikes
  4. Auto-scaling: Scale on request count, not just CPU
  5. Performance optimization: Query optimization, index tuning, caching strategy
  
Prevention:
  - Load testing: Know breaking point BEFORE production traffic hits it
  - Capacity planning: Monitor growth trend, pre-scale before events
  - Circuit breakers on all downstream calls (fail fast, don't cascade)
  - Timeout budget: Total API timeout (e.g., 5s) = sum of all downstream timeouts
```

### Q3: Design backward-compatible API evolution strategy
**Answer:**
```
Principles:
  - Additive changes are always safe (new fields, new endpoints)
  - Never remove or rename fields in same version
  - Never change field types or semantics
  - Clients must ignore unknown fields (tolerant reader pattern)
  
Strategy (REST):
  Version when: Breaking change unavoidable
  How: POST new version (/v2/), deprecate old (/v1/)
  Timeline: Announce → 3 months migration → 3 months deprecated → remove
  
  Non-breaking evolution (no new version):
    - Add optional fields to responses (clients ignore what they don't know)
    - Add optional query parameters
    - Add new endpoints
    - Add new enum values (if client handles unknown gracefully)
  
Strategy (gRPC):
  - Never reuse field numbers: `reserved 5, 8 to 10;`
  - Only add new fields (all fields optional in proto3)
  - New RPC methods are safe to add
  - Breaking change: New service version package (orders.v2)
  
Strategy (Events/Async):
  - Schema Registry: Backward compatibility check on publish
  - Schema evolution rules:
    - Can add optional fields
    - Can't remove required fields
    - Can't change field types
  - Consumers: Must handle unknown fields gracefully
  
Database migrations to support:
  Phase 1: Add new column (both old and new code work)
  Phase 2: Deploy new code (writes to both old and new columns)
  Phase 3: Backfill new column from old
  Phase 4: New code reads from new column only
  Phase 5: Remove old column (after all consumers migrated)
```

### Q4: Design API rate limiting for multi-tenant SaaS
**Answer:**
```
Tier system:
  Free:     100 req/min, 1000 req/day
  Pro:      1000 req/min, 100K req/day
  Enterprise: 10K req/min, custom daily limit
  
Implementation:
  Layer 1 - API Gateway:
    Usage Plans + API Keys (per customer)
    Throttle: Steady-state rate + burst capacity
    Quota: Daily/monthly request cap
    
  Layer 2 - Application (ElastiCache Redis):
    Token bucket per customer:
      Key: rate_limit:{customer_id}:{endpoint}
      INCR + TTL (sliding window counter)
    
    Distributed rate limiting (multi-region):
      Local counter + periodic sync to global
      Slight over-limit possible (acceptable trade-off vs latency)
  
  Headers (every response):
    X-RateLimit-Limit: 1000
    X-RateLimit-Remaining: 743
    X-RateLimit-Reset: 1705312860
    
  When limited (429):
    {
      "error": "rate_limit_exceeded",
      "message": "Rate limit of 1000 req/min exceeded",
      "retry_after": 17,
      "upgrade_url": "https://myapp.com/pricing"
    }
    
  Fairness:
    - Per-endpoint limits (expensive endpoints have lower limits)
    - Burst allowance (short spike OK, sustained abuse blocked)
    - Graceful degradation (serve cached/stale data instead of 429)
    - Priority queue: Enterprise customers bypass during capacity pressure
    
  Monitoring:
    - Dashboard: Rate limit hits per customer, per endpoint
    - Alert: Customer hitting limits consistently → sales opportunity
    - Alert: Global rate abnormally high → possible abuse/attack
```

### Q5: Microservices communication is causing cascading failures. Design resilience.
**Answer:**
```
Current problem:
  Service A → Service B → Service C
  C goes down → B waits (timeout) → A waits → All services degrade

Solution: Defense in depth

  1. Timeouts (every call):
     - Service C timeout: 2 seconds
     - Service B timeout: 3 seconds (> C, leaves room for retry)
     - Service A total timeout: 5 seconds (API-level SLA)
     - Rule: Each layer's timeout < caller's timeout
     
  2. Circuit breaker (per dependency):
     - Threshold: 50% failures in last 10 seconds → OPEN
     - Recovery: Try 1 request every 30 seconds (HALF-OPEN)
     - Fallback: Cached data, degraded response, or error message
     
  3. Bulkhead (isolate failures):
     - Separate thread pools per dependency
     - Service B down doesn't consume A's threads for Service C calls
     - Kubernetes: Separate pods/services (not one monolith calling all)
     
  4. Retry with backoff:
     - Only retry transient errors (5XX, timeout, network error)
     - Don't retry: 4XX (client error, retrying won't help)
     - Backoff: 100ms, 200ms, 400ms + jitter
     - Max retries: 2-3 (don't amplify load on struggling service)
     
  5. Async where possible:
     - If A doesn't NEED C's response immediately → queue it
     - A → SQS → C (decoupled, C processes when healthy)
     
  6. Graceful degradation:
     Recommendation service down? → Show "popular items" (cached)
     Payment service slow? → Accept order, process payment async
     Non-critical feature down? → Hide feature, don't fail entire page
     
  7. Load shedding:
     - When overloaded: Reject new requests (503) rather than degrading all
     - Priority: Serve important requests, shed low-priority
     - Implementation: Adaptive concurrency limiting (Netflix concurrency-limits)
     
  AWS implementation:
    - App Mesh: Circuit breaker + retry policies (Envoy-based)
    - Lambda destinations: On failure → DLQ (don't lose events)
    - Step Functions: Retry + catch + compensation (saga)
    - ALB: Health checks remove unhealthy targets
```

