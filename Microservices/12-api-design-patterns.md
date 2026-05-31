# API Design Patterns - Complete Guide

## Table of Contents
- [REST API Design](#rest-api-design)
- [GraphQL](#graphql)
- [gRPC](#grpc)
- [API Gateway Patterns](#api-gateway-patterns)
- [API Governance](#api-governance)
- [Advanced Patterns](#advanced-patterns)

---

## REST API Design

### Richardson Maturity Model

```
Level 3: Hypermedia Controls (HATEOAS)
         ▲  Resources + HTTP Verbs + Hypermedia
         │
Level 2: HTTP Verbs
         │  Resources + proper HTTP methods + status codes
         │
Level 1: Resources
         │  Multiple URIs, single HTTP method (usually POST)
         │
Level 0: The Swamp of POX
            Single URI, single HTTP method (RPC-style)
```

**Level 0 - Single Endpoint:**
```http
POST /api
{"action": "getUser", "userId": 123}
{"action": "createOrder", "data": {...}}
```

**Level 1 - Resources:**
```http
POST /users/123
POST /orders
```

**Level 2 - HTTP Verbs:**
```http
GET    /users/123          → 200 OK
POST   /orders             → 201 Created
PUT    /users/123          → 200 OK
DELETE /orders/456          → 204 No Content
```

**Level 3 - HATEOAS:**
```json
GET /orders/123
{
  "id": 123,
  "status": "pending",
  "total": 50.00,
  "_links": {
    "self": {"href": "/orders/123"},
    "cancel": {"href": "/orders/123/cancel", "method": "POST"},
    "payment": {"href": "/orders/123/payment", "method": "POST"},
    "customer": {"href": "/customers/456"}
  }
}
```

---

### Resource Naming Conventions

**Best Practices:**

| Convention | Good | Bad |
|-----------|------|-----|
| Use nouns, not verbs | `/orders` | `/getOrders` |
| Plural for collections | `/users` | `/user` |
| Hierarchical nesting | `/users/123/orders` | `/getUserOrders?id=123` |
| Lowercase with hyphens | `/order-items` | `/orderItems`, `/order_items` |
| No file extensions | `/users/123` | `/users/123.json` |
| Max 2-3 levels deep | `/users/123/orders` | `/users/123/orders/456/items/789/reviews` |

```http
# Collection
GET /api/v1/users

# Specific resource
GET /api/v1/users/123

# Sub-resource (relationship)
GET /api/v1/users/123/orders

# Actions (when CRUD doesn't fit)
POST /api/v1/orders/123/cancel
POST /api/v1/users/123/activate

# Filtering on collection
GET /api/v1/orders?status=pending&customer_id=123
```

---

### HTTP Methods Semantics

| Method | Semantics | Idempotent | Safe | Request Body | Response Body |
|--------|-----------|------------|------|-------------|---------------|
| GET | Read resource | Yes | Yes | No | Yes |
| POST | Create resource / trigger action | No | No | Yes | Yes |
| PUT | Replace entire resource | Yes | No | Yes | Yes |
| PATCH | Partial update | No* | No | Yes | Yes |
| DELETE | Remove resource | Yes | No | No | Optional |
| HEAD | GET without body (metadata) | Yes | Yes | No | No |
| OPTIONS | Supported methods (CORS preflight) | Yes | Yes | No | Yes |

*PATCH can be idempotent if using JSON Merge Patch/JSON Patch correctly.

**Idempotency explained:**
```http
# Idempotent: calling N times = same result as calling once
PUT /users/123 {"name": "John"}  → always results in name="John"
DELETE /orders/456              → first call deletes, subsequent return 404 (same end state)

# NOT idempotent: each call may have different effect
POST /orders {"item": "book"}  → creates new order each time
```

---

### Status Codes Guide

**2xx Success:**
| Code | When to Use |
|------|-------------|
| 200 OK | GET success, PUT/PATCH update success |
| 201 Created | POST created new resource (include Location header) |
| 202 Accepted | Async operation accepted, not completed yet |
| 204 No Content | DELETE success, PUT with no response body |

**3xx Redirection:**
| Code | When to Use |
|------|-------------|
| 301 Moved Permanently | Resource URL changed permanently |
| 304 Not Modified | Conditional GET, resource unchanged (ETag match) |

**4xx Client Error:**
| Code | When to Use |
|------|-------------|
| 400 Bad Request | Malformed request, validation failure |
| 401 Unauthorized | No/invalid authentication |
| 403 Forbidden | Authenticated but not authorized |
| 404 Not Found | Resource doesn't exist |
| 405 Method Not Allowed | Wrong HTTP method |
| 409 Conflict | Conflict with current state (duplicate, version mismatch) |
| 410 Gone | Resource permanently deleted (vs 404 which might return) |
| 412 Precondition Failed | Conditional request failed (If-Match ETag) |
| 422 Unprocessable Entity | Valid JSON but semantic errors |
| 429 Too Many Requests | Rate limited (include Retry-After header) |

**5xx Server Error:**
| Code | When to Use |
|------|-------------|
| 500 Internal Server Error | Unexpected server error |
| 502 Bad Gateway | Upstream service failed |
| 503 Service Unavailable | Temporarily down (include Retry-After) |
| 504 Gateway Timeout | Upstream service timed out |

**Error response format:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {"field": "email", "message": "Invalid email format"},
      {"field": "age", "message": "Must be >= 18"}
    ],
    "request_id": "req-abc-123",
    "documentation_url": "https://api.example.com/docs/errors#VALIDATION_ERROR"
  }
}
```

---

### HATEOAS (Hypermedia as the Engine of Application State)

**Description:** Clients discover available actions through hypermedia links in responses, rather than hardcoding URL patterns.

**When to use:** Public APIs where clients shouldn't hardcode URLs; when API evolves frequently.

```json
GET /api/accounts/123
{
  "id": 123,
  "balance": 500.00,
  "status": "active",
  "_links": {
    "self": {"href": "/api/accounts/123"},
    "deposit": {"href": "/api/accounts/123/deposit", "method": "POST"},
    "withdraw": {"href": "/api/accounts/123/withdraw", "method": "POST"},
    "transfer": {"href": "/api/accounts/123/transfer", "method": "POST"},
    "close": {"href": "/api/accounts/123/close", "method": "POST"}
  }
}

// If account is overdrawn, withdraw link disappears:
{
  "id": 123,
  "balance": -50.00,
  "status": "overdrawn",
  "_links": {
    "self": {"href": "/api/accounts/123"},
    "deposit": {"href": "/api/accounts/123/deposit", "method": "POST"}
    // No withdraw or transfer links!
  }
}
```

**Best practices:**
- Use standard formats: HAL, JSON:API, or JSON-LD
- Links communicate available state transitions
- Clients should follow links, not construct URLs

**Common mistakes:**
- Adding links but clients ignore them (over-engineering)
- Not removing links when actions are unavailable
- Inconsistent link relation naming

---

### Content Negotiation

```http
# Client requests specific format
GET /api/users/123
Accept: application/json

# Server responds with format
HTTP/1.1 200 OK
Content-Type: application/json

# Multiple formats supported
Accept: application/json, application/xml;q=0.9, */*;q=0.8

# Custom media types for versioning
Accept: application/vnd.myapi.v2+json
```

```python
# FastAPI example
from fastapi import Request
from fastapi.responses import JSONResponse, Response

@app.get("/users/{user_id}")
async def get_user(user_id: int, request: Request):
    user = await get_user_from_db(user_id)
    
    accept = request.headers.get("accept", "application/json")
    
    if "application/xml" in accept:
        return Response(content=user_to_xml(user), media_type="application/xml")
    elif "text/csv" in accept:
        return Response(content=user_to_csv(user), media_type="text/csv")
    else:
        return JSONResponse(content=user.dict())
```

---

### Pagination

#### Offset-based Pagination
```http
GET /api/users?page=3&per_page=20

Response:
{
  "data": [...],
  "pagination": {
    "page": 3,
    "per_page": 20,
    "total_items": 1543,
    "total_pages": 78
  }
}
```
**Pros:** Simple, allows jumping to any page.
**Cons:** Inconsistent results if data changes (items shift); slow for large offsets (OFFSET 10000).

#### Cursor-based Pagination
```http
GET /api/users?limit=20&after=eyJpZCI6MTAwfQ==

Response:
{
  "data": [...],
  "pagination": {
    "has_next": true,
    "next_cursor": "eyJpZCI6MTIwfQ==",
    "has_previous": true,
    "previous_cursor": "eyJpZCI6MTAxfQ=="
  }
}
```
**Pros:** Consistent results, performant at any depth, handles real-time data.
**Cons:** Can't jump to arbitrary page, cursor is opaque.

```python
# Cursor implementation (base64 encoded last seen ID)
import base64, json

def encode_cursor(last_id: int, last_created: str) -> str:
    return base64.b64encode(json.dumps({"id": last_id, "created": last_created}).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    return json.loads(base64.b64decode(cursor))

# Query with cursor
async def get_users(after_cursor: str = None, limit: int = 20):
    query = "SELECT * FROM users"
    if after_cursor:
        cursor = decode_cursor(after_cursor)
        query += f" WHERE (created_at, id) > ('{cursor['created']}', {cursor['id']})"
    query += f" ORDER BY created_at, id LIMIT {limit + 1}"
    
    results = await db.fetch(query)
    has_next = len(results) > limit
    items = results[:limit]
    
    return {
        "data": items,
        "pagination": {
            "has_next": has_next,
            "next_cursor": encode_cursor(items[-1].id, items[-1].created_at) if has_next else None
        }
    }
```

#### Keyset Pagination
```sql
-- Instead of OFFSET (slow):
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 10000;

-- Use keyset (fast, uses index):
SELECT * FROM orders 
WHERE created_at < '2024-01-15T10:00:00Z'
ORDER BY created_at DESC 
LIMIT 20;
```

---

### Filtering, Sorting, Field Selection

```http
# Filtering
GET /api/orders?status=pending&created_after=2024-01-01&total_min=100

# Complex filtering (LHS brackets)
GET /api/orders?price[gte]=10&price[lte]=100&status[in]=pending,processing

# Sorting
GET /api/users?sort=created_at:desc,name:asc

# Field selection (sparse fieldsets)
GET /api/users/123?fields=id,name,email

# Combined
GET /api/orders?status=pending&sort=-created_at&fields=id,total,status&page=1&per_page=20
```

```python
# FastAPI implementation
@app.get("/api/orders")
async def list_orders(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    sort: str = "-created_at",
    fields: Optional[str] = None,
    page: int = 1,
    per_page: int = Query(default=20, le=100)
):
    query = select(Order)
    
    # Filtering
    if status:
        query = query.where(Order.status == status)
    if customer_id:
        query = query.where(Order.customer_id == customer_id)
    
    # Sorting
    for field in sort.split(","):
        if field.startswith("-"):
            query = query.order_by(desc(getattr(Order, field[1:])))
        else:
            query = query.order_by(asc(getattr(Order, field)))
    
    # Pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    results = await db.execute(query)
    
    # Field selection
    if fields:
        field_list = fields.split(",")
        return [pick(r, field_list) for r in results]
    return results
```

---

### Bulk Operations

```http
# Bulk create
POST /api/users/bulk
{
  "items": [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"}
  ]
}

Response (207 Multi-Status):
{
  "results": [
    {"status": 201, "data": {"id": 1, "name": "Alice"}},
    {"status": 400, "error": {"message": "Email already exists"}}
  ],
  "summary": {"total": 2, "succeeded": 1, "failed": 1}
}

# Bulk delete
DELETE /api/users/bulk
{"ids": [1, 2, 3, 4, 5]}

# Bulk update (PATCH)
PATCH /api/users/bulk
{
  "items": [
    {"id": 1, "status": "active"},
    {"id": 2, "status": "suspended"}
  ]
}
```

**Best practices:**
- Return per-item status (207 Multi-Status)
- Set max batch size (e.g., 1000 items)
- Process atomically or report partial results
- Consider async for large batches (return 202)

---

### Long-Running Operations (Async API Design)

**Problem:** Operations that take seconds/minutes/hours to complete.

**Solution:** Accept immediately, return a polling URL or use webhooks.

```http
# 1. Client initiates long-running operation
POST /api/reports/generate
{"type": "annual", "year": 2024}

Response:
HTTP/1.1 202 Accepted
Location: /api/operations/op-abc-123
Retry-After: 30
{
  "operation_id": "op-abc-123",
  "status": "running",
  "progress": 0,
  "estimated_completion": "2024-01-15T10:05:00Z",
  "_links": {
    "status": {"href": "/api/operations/op-abc-123"},
    "cancel": {"href": "/api/operations/op-abc-123", "method": "DELETE"}
  }
}

# 2. Client polls for status
GET /api/operations/op-abc-123

Response (in progress):
HTTP/1.1 200 OK
{
  "operation_id": "op-abc-123",
  "status": "running",
  "progress": 65,
  "message": "Processing records..."
}

Response (completed):
HTTP/1.1 303 See Other
Location: /api/reports/rpt-xyz-789
{
  "operation_id": "op-abc-123",
  "status": "completed",
  "result": {"href": "/api/reports/rpt-xyz-789"}
}
```

---

### ETag and Conditional Requests

```http
# 1. GET with ETag
GET /api/users/123
HTTP/1.1 200 OK
ETag: "v1-abc123"
{
  "id": 123,
  "name": "John",
  "email": "john@example.com"
}

# 2. Conditional GET (caching)
GET /api/users/123
If-None-Match: "v1-abc123"

HTTP/1.1 304 Not Modified  ← No body, use cached version

# 3. Conditional PUT (optimistic concurrency)
PUT /api/users/123
If-Match: "v1-abc123"
{"name": "John Updated", "email": "john@example.com"}

HTTP/1.1 200 OK  ← Success, ETag matched
ETag: "v2-def456"

# 4. Conflict detection
PUT /api/users/123
If-Match: "v1-abc123"  ← Stale ETag
{"name": "Other Update"}

HTTP/1.1 412 Precondition Failed  ← Someone else modified it
```

```python
# Implementation
@app.get("/users/{user_id}")
async def get_user(user_id: int, request: Request):
    user = await db.get_user(user_id)
    etag = f'"{user.version}-{hash(user.updated_at)}"'
    
    # Check If-None-Match for caching
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    
    return JSONResponse(content=user.dict(), headers={"ETag": etag})

@app.put("/users/{user_id}")
async def update_user(user_id: int, data: UserUpdate, request: Request):
    if_match = request.headers.get("if-match")
    if not if_match:
        return JSONResponse(status_code=428, content={"error": "ETag required"})
    
    user = await db.get_user(user_id)
    current_etag = f'"{user.version}-{hash(user.updated_at)}"'
    
    if if_match != current_etag:
        return JSONResponse(status_code=412, content={"error": "Resource modified"})
    
    updated = await db.update_user(user_id, data)
    new_etag = f'"{updated.version}-{hash(updated.updated_at)}"'
    return JSONResponse(content=updated.dict(), headers={"ETag": new_etag})
```

---

### API Versioning

| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| URI path | `/api/v1/users` | Simple, visible, cacheable | URL changes, breaks clients |
| Query param | `/api/users?version=1` | Optional, backward compat | Easy to forget |
| Header | `X-API-Version: 1` | Clean URLs | Hidden, harder to test |
| Content negotiation | `Accept: application/vnd.api.v1+json` | RESTful, flexible | Complex |

**Best practices:**
- Version the API, not individual endpoints
- Support N-1 version minimum (sunset gracefully)
- Use `Sunset` header to announce deprecation
- Only increment major version for breaking changes

```http
# Sunset header
GET /api/v1/users/123
Sunset: Sat, 01 Jun 2025 00:00:00 GMT
Deprecation: true
Link: </api/v2/users/123>; rel="successor-version"
```

---

## GraphQL

### Schema Design Best Practices

```graphql
# Use clear, domain-driven types
type Order {
  id: ID!
  customer: Customer!
  items: [OrderItem!]!
  status: OrderStatus!
  total: Money!
  createdAt: DateTime!
  shippingAddress: Address
}

# Use enums for fixed sets
enum OrderStatus {
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
  CANCELLED
}

# Custom scalars for domain types
scalar DateTime
scalar Money
scalar URL

# Input types for mutations
input CreateOrderInput {
  customerId: ID!
  items: [OrderItemInput!]!
  shippingAddress: AddressInput!
}

# Connections for pagination (Relay spec)
type OrderConnection {
  edges: [OrderEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type OrderEdge {
  node: Order!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

**Best practices:**
- Nullable by default, use `!` intentionally
- Use connections for lists (pagination-ready)
- Separate input types from output types
- Use interfaces for shared fields
- Keep mutations specific (`cancelOrder` not `updateOrder(status: CANCELLED)`)

---

### Queries, Mutations, Subscriptions

```graphql
# Query - read data
type Query {
  order(id: ID!): Order
  orders(
    filter: OrderFilter
    first: Int
    after: String
    sort: OrderSort
  ): OrderConnection!
  me: User!
}

# Mutation - write data
type Mutation {
  createOrder(input: CreateOrderInput!): CreateOrderPayload!
  cancelOrder(id: ID!, reason: String): CancelOrderPayload!
}

# Mutation payload pattern (allows returning errors + data)
type CreateOrderPayload {
  order: Order
  errors: [UserError!]!
}

type UserError {
  field: [String!]
  message: String!
  code: ErrorCode!
}

# Subscription - real-time updates
type Subscription {
  orderStatusChanged(orderId: ID!): Order!
  newOrders(customerId: ID!): Order!
}
```

```python
# Resolver implementation (Strawberry/Python)
import strawberry
from strawberry.types import Info

@strawberry.type
class Query:
    @strawberry.field
    async def order(self, id: strawberry.ID, info: Info) -> Optional[Order]:
        return await info.context.order_loader.load(id)
    
    @strawberry.field
    async def orders(
        self, 
        filter: Optional[OrderFilter] = None,
        first: int = 20,
        after: Optional[str] = None
    ) -> OrderConnection:
        return await get_orders_paginated(filter, first, after)
```

---

### DataLoader Pattern (N+1 Problem)

**Problem:**
```graphql
# This query causes N+1:
{
  orders(first: 10) {
    edges {
      node {
        id
        customer {      # ← 10 separate DB queries for customer!
          name
        }
      }
    }
  }
}
```

**Solution: DataLoader batches and caches within a request.**

```python
from dataloader import DataLoader

class CustomerLoader(DataLoader):
    async def batch_load_fn(self, customer_ids: List[str]) -> List[Customer]:
        # Single query for ALL requested customers
        customers = await db.fetch(
            "SELECT * FROM customers WHERE id = ANY($1)", 
            customer_ids
        )
        # Return in same order as requested IDs
        customer_map = {c.id: c for c in customers}
        return [customer_map.get(id) for id in customer_ids]

# In resolver
@strawberry.type
class Order:
    @strawberry.field
    async def customer(self, info: Info) -> Customer:
        # DataLoader batches: 10 calls → 1 SQL query
        return await info.context.customer_loader.load(self.customer_id)

# Create new loader per request (caching is per-request)
def get_context():
    return {"customer_loader": CustomerLoader()}
```

---

### Federation (Apollo Federation v2)

**Description:** Compose multiple GraphQL services into a single unified graph.

```graphql
# Users service (subgraph)
type User @key(fields: "id") {
  id: ID!
  name: String!
  email: String!
}

type Query {
  me: User
}

# Orders service (subgraph) - extends User from another service
type User @key(fields: "id") {
  id: ID!
  orders: [Order!]!  # Adds orders field to User
}

type Order @key(fields: "id") {
  id: ID!
  total: Money!
  status: OrderStatus!
}

type Query {
  order(id: ID!): Order
}

# Router composes both into unified schema:
# query { me { name email orders { total } } }
```

**Federation v2 features:**
- `@shareable` - multiple subgraphs can resolve same field
- `@override` - migrate fields between subgraphs
- `@inaccessible` - hide fields from public API
- `@tag` - organize schema elements

---

### Schema Stitching vs Federation

| Aspect | Schema Stitching | Federation |
|--------|-----------------|------------|
| Approach | Gateway merges schemas | Subgraphs declare boundaries |
| Ownership | Gateway owns composition | Services own their types |
| Coupling | Gateway knows all services | Services independent |
| Complexity | Gateway logic heavy | Distributed across services |
| Type extension | Delegated resolvers | @key + reference resolvers |
| Recommended | Legacy, simple cases | Production microservices |

---

### Persisted Queries

**Problem:** Large query strings in requests; security concerns about arbitrary queries.

```python
# 1. At build time, register queries with hashes
registered_queries = {
    "sha256:abc123": "query GetUser($id: ID!) { user(id: $id) { name email } }",
    "sha256:def456": "query ListOrders { orders { id total } }"
}

# 2. Client sends hash instead of full query
# POST /graphql
# {"extensions": {"persistedQuery": {"sha256Hash": "abc123"}}, "variables": {"id": "1"}}

# 3. Server looks up and executes
@app.post("/graphql")
async def graphql(request):
    body = await request.json()
    
    if "extensions" in body and "persistedQuery" in body["extensions"]:
        hash = body["extensions"]["persistedQuery"]["sha256Hash"]
        query = registered_queries.get(f"sha256:{hash}")
        if not query:
            return {"errors": [{"message": "PersistedQueryNotFound"}]}
    else:
        # Optionally reject non-persisted queries in production
        return {"errors": [{"message": "Only persisted queries allowed"}]}
    
    return await execute(query, body.get("variables"))
```

**Benefits:** Smaller payloads, CDN caching, prevents malicious queries.

---

### Rate Limiting in GraphQL

**Problem:** A single GraphQL query can be extremely expensive (unlike REST where each endpoint has predictable cost).

```python
# Query complexity analysis
def calculate_complexity(query, variables):
    """Calculate cost before execution."""
    # Each field has a cost
    field_costs = {
        "users": 1,
        "orders": 2,
        "orderItems": 1,
    }
    # Multiplied by pagination limit
    # orders(first: 100) { items(first: 50) { ... } }
    # Cost: 100 * (2 + 50 * 1) = 5200
    
    total_cost = analyze_query_cost(query, field_costs)
    
    if total_cost > MAX_COMPLEXITY:
        raise QueryTooComplex(f"Cost {total_cost} exceeds limit {MAX_COMPLEXITY}")
    
    return total_cost

# Rate limit by complexity points, not requests
class GraphQLRateLimiter:
    async def check(self, user_id: str, complexity: int) -> bool:
        current = await self.redis.get(f"rate:{user_id}")
        if (current or 0) + complexity > POINTS_PER_MINUTE:
            return False
        await self.redis.incrby(f"rate:{user_id}", complexity)
        return True
```

---

### Security Considerations

```python
# 1. Query depth limiting
MAX_DEPTH = 7
# Prevents: { user { friends { friends { friends { ... } } } } }

# 2. Query complexity limiting (see above)
MAX_COMPLEXITY = 10000

# 3. Timeout
QUERY_TIMEOUT_MS = 5000

# 4. Introspection disabled in production
schema = strawberry.Schema(query=Query, enable_introspection=IS_DEV)

# 5. Field-level authorization
@strawberry.type
class User:
    @strawberry.field
    async def email(self, info: Info) -> str:
        if not info.context.user.can_view_email(self.id):
            raise PermissionError("Not authorized")
        return self._email
    
    @strawberry.field
    async def ssn(self, info: Info) -> str:
        if info.context.user.role != "admin":
            raise PermissionError("Admin only")
        return self._ssn
```

---

### GraphQL in Microservices

```
┌────────────┐     ┌────────────────────────────┐
│   Client   │────▶│  API Gateway / Federation  │
└────────────┘     │       Router               │
                   └──────┬─────────┬───────────┘
                          │         │
              ┌───────────┘         └───────────┐
              ▼                                 ▼
     ┌────────────────┐               ┌────────────────┐
     │ Users Subgraph │               │Orders Subgraph │
     │  (GraphQL)     │               │  (GraphQL)     │
     └────────────────┘               └────────────────┘
```

**Approaches:**
1. **Federation** (recommended) - Each service owns its subgraph
2. **BFF with GraphQL** - GraphQL as aggregation layer over REST services
3. **Schema stitching** - Gateway merges remote schemas

---

## gRPC

### Protocol Buffers Design

```protobuf
syntax = "proto3";

package orders.v1;

import "google/protobuf/timestamp.proto";
import "google/protobuf/wrappers.proto";  // for nullable types

// Use well-defined message types
message Order {
  string id = 1;
  string customer_id = 2;
  repeated OrderItem items = 3;
  OrderStatus status = 4;
  Money total = 5;
  google.protobuf.Timestamp created_at = 6;
  optional Address shipping_address = 7;  // explicit optional
}

message OrderItem {
  string product_id = 1;
  string product_name = 2;
  int32 quantity = 3;
  Money unit_price = 4;
}

message Money {
  int64 amount_micros = 1;  // $1.50 = 1500000 (avoid floating point)
  string currency_code = 2;  // ISO 4217
}

enum OrderStatus {
  ORDER_STATUS_UNSPECIFIED = 0;  // Always have zero value as unspecified
  ORDER_STATUS_PENDING = 1;
  ORDER_STATUS_CONFIRMED = 2;
  ORDER_STATUS_SHIPPED = 3;
  ORDER_STATUS_DELIVERED = 4;
  ORDER_STATUS_CANCELLED = 5;
}
```

**Best practices:**
- Reserve field numbers (never reuse deleted fields): `reserved 4, 7;`
- Use `UNSPECIFIED = 0` for enums
- Avoid `float`/`double` for money (use micros or string)
- Use `google.protobuf.Timestamp` not custom date formats
- Package naming: `company.service.version`

---

### Service Definition Patterns

```protobuf
service OrderService {
  // Standard CRUD
  rpc CreateOrder(CreateOrderRequest) returns (CreateOrderResponse);
  rpc GetOrder(GetOrderRequest) returns (Order);
  rpc ListOrders(ListOrdersRequest) returns (ListOrdersResponse);
  
  // Action
  rpc CancelOrder(CancelOrderRequest) returns (CancelOrderResponse);
  
  // Server streaming (real-time updates)
  rpc WatchOrder(WatchOrderRequest) returns (stream OrderUpdate);
  
  // Client streaming (bulk upload)
  rpc BulkCreateOrders(stream CreateOrderRequest) returns (BulkCreateResponse);
  
  // Bidirectional streaming (chat, real-time sync)
  rpc OrderChat(stream ChatMessage) returns (stream ChatMessage);
}

// Request/Response wrappers (don't use primitives directly)
message CreateOrderRequest {
  string customer_id = 1;
  repeated OrderItemInput items = 2;
  Address shipping_address = 3;
  string idempotency_key = 4;  // for retries
}

message CreateOrderResponse {
  Order order = 1;
}

// Pagination
message ListOrdersRequest {
  int32 page_size = 1;
  string page_token = 2;  // cursor
  string filter = 3;      // e.g., "status=PENDING"
  string order_by = 4;    // e.g., "created_at desc"
}

message ListOrdersResponse {
  repeated Order orders = 1;
  string next_page_token = 2;
  int32 total_size = 3;
}
```

---

### Streaming Patterns

```python
# Server streaming - real-time updates
class OrderService(OrderServiceServicer):
    async def WatchOrder(self, request, context):
        order_id = request.order_id
        async for update in self.order_updates.subscribe(order_id):
            yield OrderUpdate(
                order_id=order_id,
                status=update.status,
                timestamp=update.timestamp
            )
    
    # Client streaming - bulk upload
    async def BulkCreateOrders(self, request_iterator, context):
        created = 0
        failed = 0
        async for request in request_iterator:
            try:
                await self.create_order(request)
                created += 1
            except Exception:
                failed += 1
        return BulkCreateResponse(created=created, failed=failed)
    
    # Bidirectional streaming
    async def OrderChat(self, request_iterator, context):
        async for message in request_iterator:
            # Process incoming message
            response = await self.process_chat(message)
            yield response  # Stream back response
```

---

### Interceptors and Middleware

```python
# gRPC interceptor (like HTTP middleware)
class AuthInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        token = metadata.get("authorization", "")
        
        if not self.validate_token(token):
            raise grpc.aio.AbortError(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
        
        return await continuation(handler_call_details)

class LoggingInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        start = time.time()
        
        response = await continuation(handler_call_details)
        
        duration = time.time() - start
        logger.info(f"{method} completed in {duration:.3f}s")
        return response

# Apply interceptors
server = grpc.aio.server(interceptors=[AuthInterceptor(), LoggingInterceptor()])
```

---

### Load Balancing for gRPC

**Problem:** gRPC uses HTTP/2 with long-lived connections. L4 load balancers only balance at connection time, not per-request.

**Solutions:**

```
# 1. L7 (application-layer) load balancing
Client → Envoy/Nginx (L7 proxy) → gRPC Servers
# Envoy understands HTTP/2 frames, balances per-RPC

# 2. Client-side load balancing
Client has list of servers, picks one per RPC
# gRPC has built-in: round_robin, pick_first
# Service mesh: Istio/Linkerd handle this transparently

# 3. Lookaside load balancing (gRPC-LB)
Client → LB service (get server list) → direct to server
```

```python
# Client-side round-robin
import grpc

channel = grpc.insecure_channel(
    "dns:///my-service.default.svc.cluster.local:50051",
    options=[
        ("grpc.lb_policy_name", "round_robin"),
        ("grpc.service_config", '{"loadBalancingConfig": [{"round_robin":{}}]}')
    ]
)
```

---

### gRPC-Web for Browsers

**Problem:** Browsers can't use native gRPC (no HTTP/2 trailers, no binary framing control).

**Solution:** gRPC-Web protocol + Envoy proxy.

```
Browser (gRPC-Web) → Envoy Proxy (translates) → gRPC Server

# Envoy config
http_filters:
  - name: envoy.filters.http.grpc_web
  - name: envoy.filters.http.cors
  - name: envoy.filters.http.router
```

```javascript
// Browser client (grpc-web)
import { OrderServiceClient } from './generated/order_grpc_web_pb';

const client = new OrderServiceClient('https://api.example.com');

const request = new GetOrderRequest();
request.setOrderId('123');

client.getOrder(request, {authorization: 'Bearer token'}, (err, response) => {
  console.log(response.getStatus());
});
```

---

### gRPC vs REST Comparison

| Aspect | gRPC | REST |
|--------|------|------|
| Protocol | HTTP/2 | HTTP/1.1 or HTTP/2 |
| Format | Protobuf (binary) | JSON (text) |
| Payload size | ~10x smaller | Larger |
| Speed | ~7-10x faster serialization | Slower |
| Streaming | Native (4 types) | Workarounds (SSE, WebSocket) |
| Browser support | Via gRPC-Web proxy | Native |
| Tooling | protoc, grpcurl | curl, Postman, extensive |
| Schema | Required (.proto) | Optional (OpenAPI) |
| Code gen | Built-in | Third-party |
| Caching | Difficult (POST-like) | HTTP caching built-in |
| Human readable | No (binary) | Yes (JSON) |
| Best for | Internal microservices | Public APIs, web clients |

---

### Error Handling

```protobuf
import "google/rpc/status.proto";
import "google/rpc/error_details.proto";

// Rich error model
// Status code + message + details
```

```python
from grpc_status import rpc_status
from google.protobuf import any_pb2
from google.rpc import error_details_pb2, status_pb2

# Server-side rich error
async def CreateOrder(self, request, context):
    errors = validate(request)
    if errors:
        detail = any_pb2.Any()
        detail.Pack(error_details_pb2.BadRequest(
            field_violations=[
                error_details_pb2.BadRequest.FieldViolation(
                    field="customer_id",
                    description="Customer not found"
                )
            ]
        ))
        
        status = status_pb2.Status(
            code=grpc.StatusCode.INVALID_ARGUMENT.value[0],
            message="Validation failed",
            details=[detail]
        )
        await context.abort_with_status(rpc_status.to_status(status))
```

**gRPC status codes:**
| Code | Use Case |
|------|----------|
| OK (0) | Success |
| CANCELLED (1) | Client cancelled |
| INVALID_ARGUMENT (3) | Bad request data |
| NOT_FOUND (5) | Resource doesn't exist |
| ALREADY_EXISTS (6) | Duplicate |
| PERMISSION_DENIED (7) | Not authorized |
| RESOURCE_EXHAUSTED (8) | Rate limited |
| FAILED_PRECONDITION (9) | State doesn't allow operation |
| UNIMPLEMENTED (12) | Method not implemented |
| INTERNAL (13) | Server bug |
| UNAVAILABLE (14) | Transient failure (retry) |
| DEADLINE_EXCEEDED (4) | Timeout |
| UNAUTHENTICATED (16) | No valid credentials |

---

## API Gateway Patterns

### API Gateway as Single Entry Point

```
                        ┌─────────────────────────────────┐
  Mobile App ──────────▶│                                 │──▶ User Service
  Web App ─────────────▶│         API Gateway             │──▶ Order Service
  Partner API ─────────▶│                                 │──▶ Payment Service
  IoT Device ─────────▶│  • Authentication               │──▶ Notification Service
                        │  • Rate Limiting                │
                        │  • Request Routing              │
                        │  • Protocol Translation         │
                        │  • Response Caching             │
                        │  • Logging/Monitoring           │
                        └─────────────────────────────────┘
```

**Responsibilities:**
- Single entry point (simplifies client)
- Cross-cutting concerns (auth, rate limiting, logging)
- Request routing and load balancing
- API composition/aggregation
- Protocol translation (REST ↔ gRPC)
- Response transformation

---

### Backend for Frontend (BFF)

**Problem:** Different clients (mobile, web, TV) need different API shapes.

**Solution:** Dedicated gateway per client type.

```
┌────────┐     ┌───────────┐
│  Web   │────▶│  Web BFF  │──┐
└────────┘     └───────────┘  │     ┌──────────────┐
                              ├────▶│ User Service │
┌────────┐     ┌───────────┐  │     └──────────────┘
│ Mobile │────▶│Mobile BFF │──┤
└────────┘     └───────────┘  │     ┌──────────────┐
                              ├────▶│Order Service │
┌────────┐     ┌───────────┐  │     └──────────────┘
│   TV   │────▶│  TV BFF   │──┘
└────────┘     └───────────┘
```

```python
# Mobile BFF - optimized for mobile (smaller payloads, fewer calls)
@mobile_bff.get("/home")
async def mobile_home(user_id: str):
    # Aggregate multiple services into one response
    user, orders, notifications = await asyncio.gather(
        user_service.get_user_summary(user_id),  # minimal fields
        order_service.get_recent_orders(user_id, limit=3),
        notification_service.get_unread_count(user_id)
    )
    return {
        "user": {"name": user.name, "avatar_url": user.avatar_url},
        "recent_orders": [{"id": o.id, "status": o.status} for o in orders],
        "unread_notifications": notifications.count
    }

# Web BFF - richer data for desktop
@web_bff.get("/dashboard")
async def web_dashboard(user_id: str):
    # More detailed response for web
    user, orders, analytics, notifications = await asyncio.gather(
        user_service.get_full_profile(user_id),
        order_service.get_orders(user_id, limit=20),
        analytics_service.get_user_analytics(user_id),
        notification_service.get_all(user_id)
    )
    return {
        "user": user.full_dict(),
        "orders": orders,
        "analytics": analytics,
        "notifications": notifications
    }
```

**When to use:** Multiple client types with different needs, teams owning different clients.
**Common mistakes:** BFF becomes a monolith; put only aggregation logic here, not business logic.

---

### API Composition/Aggregation

**Problem:** Client needs data from multiple services.

**Solution:** Gateway aggregates multiple service calls into single response.

```python
@gateway.get("/api/order-details/{order_id}")
async def get_order_details(order_id: str):
    # Parallel calls to multiple services
    order, customer, shipment, payments = await asyncio.gather(
        order_service.get(order_id),
        customer_service.get(order.customer_id),
        shipping_service.get_by_order(order_id),
        payment_service.get_by_order(order_id),
        return_exceptions=True  # Don't fail if one service is down
    )
    
    return {
        "order": order if not isinstance(order, Exception) else None,
        "customer": customer if not isinstance(customer, Exception) else None,
        "shipment": shipment if not isinstance(shipment, Exception) else None,
        "payments": payments if not isinstance(payments, Exception) else None,
    }
```

---

### Request Routing

```yaml
# Kong/Envoy style routing
routes:
  - path: /api/users/**
    service: user-service
    strip_prefix: /api
    
  - path: /api/orders/**
    service: order-service
    strip_prefix: /api
    
  - path: /api/v2/orders/**
    service: order-service-v2
    strip_prefix: /api/v2
    
  # Header-based routing (canary)
  - path: /api/orders/**
    headers:
      x-canary: "true"
    service: order-service-canary
    weight: 10  # 10% traffic
```

---

### Protocol Translation

```python
# Gateway translates REST to gRPC
@gateway.get("/api/orders/{order_id}")
async def get_order_rest(order_id: str):
    # Client speaks REST, backend speaks gRPC
    grpc_request = GetOrderRequest(order_id=order_id)
    grpc_response = await order_stub.GetOrder(grpc_request)
    
    # Convert protobuf to JSON
    return MessageToDict(grpc_response, preserving_proto_field_name=True)

@gateway.post("/api/orders")
async def create_order_rest(body: dict):
    grpc_request = ParseDict(body, CreateOrderRequest())
    grpc_response = await order_stub.CreateOrder(grpc_request)
    return MessageToDict(grpc_response), 201
```

---

### Rate Limiting at Gateway

```python
# Token bucket algorithm
class RateLimiter:
    def __init__(self, redis):
        self.redis = redis
    
    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        """Sliding window rate limiter."""
        now = time.time()
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Count requests in window
        pipe.zcard(key)
        # Set expiry
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        request_count = results[2]
        
        return request_count <= limit

# Apply different limits per tier
RATE_LIMITS = {
    "free": {"requests": 100, "window": 3600},
    "pro": {"requests": 10000, "window": 3600},
    "enterprise": {"requests": 100000, "window": 3600},
}

# Response headers
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 95
# X-RateLimit-Reset: 1705312800
# Retry-After: 3600  (when 429)
```

---

### Kong vs Envoy vs AWS API Gateway vs Apigee

| Feature | Kong | Envoy | AWS API Gateway | Apigee |
|---------|------|-------|-----------------|--------|
| Type | API Gateway | Service proxy | Managed gateway | Full platform |
| Deployment | Self-hosted/Cloud | Sidecar/Gateway | AWS managed | GCP managed |
| Protocol | HTTP, gRPC, WebSocket | HTTP/1.1, HTTP/2, gRPC | REST, WebSocket, HTTP | REST, SOAP |
| Config | Declarative (YAML/DB) | xDS API / YAML | Console/IaC | UI/API |
| Plugins | 100+ (Lua/Go) | C++ filters / WASM | Lambda authorizers | Policies (XML) |
| Performance | High | Very High | Medium | Medium |
| Service mesh | Limited | Yes (Istio data plane) | No | No |
| Cost | Free/Enterprise | Free (OSS) | Pay per request | Expensive |
| Best for | API management | Service mesh/L7 proxy | Serverless APIs | Enterprise API program |

---

## API Governance

### API-First Design Approach

```
1. Design API spec (OpenAPI) ──▶ Review with stakeholders
2. Generate mock server ──▶ Frontend development starts
3. Generate SDK/client ──▶ Consumer teams can integrate
4. Implement server ──▶ Passes contract tests
5. Validate against spec ──▶ CI/CD gate
```

**Principles:**
- API spec is the source of truth
- Design before implementation
- Consumers involved in design review
- Spec drives code generation, testing, docs

---

### OpenAPI/Swagger Specification

```yaml
openapi: 3.1.0
info:
  title: Order Service API
  version: 2.1.0
  description: API for managing customer orders
  contact:
    name: Platform Team
    email: platform@example.com

servers:
  - url: https://api.example.com/v2
    description: Production
  - url: https://staging-api.example.com/v2
    description: Staging

paths:
  /orders:
    get:
      operationId: listOrders
      summary: List orders with filtering and pagination
      tags: [Orders]
      parameters:
        - name: status
          in: query
          schema:
            $ref: '#/components/schemas/OrderStatus'
        - name: cursor
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
      responses:
        '200':
          description: List of orders
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderList'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '429':
          $ref: '#/components/responses/RateLimited'

    post:
      operationId: createOrder
      summary: Create a new order
      tags: [Orders]
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
              schema:
                type: string
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Order'

components:
  schemas:
    Order:
      type: object
      required: [id, status, total, createdAt]
      properties:
        id:
          type: string
          format: uuid
        status:
          $ref: '#/components/schemas/OrderStatus'
        total:
          $ref: '#/components/schemas/Money'
        createdAt:
          type: string
          format: date-time

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

security:
  - bearerAuth: []
```

---

### API Linting (Spectral)

```yaml
# .spectral.yaml - API style rules
extends: ["spectral:oas"]

rules:
  # Naming conventions
  paths-kebab-case:
    given: "$.paths[*]~"
    then:
      function: pattern
      functionOptions:
        match: "^(/[a-z][a-z0-9-]*)+$"

  # Require descriptions
  operation-description:
    given: "$.paths[*][*]"
    then:
      field: description
      function: truthy

  # Require error responses
  must-have-error-responses:
    given: "$.paths[*][*].responses"
    then:
      field: "401"
      function: truthy

  # Pagination required for lists
  collection-must-have-pagination:
    given: "$.paths[*].get.responses.200.content.application/json.schema"
    then:
      field: "properties.pagination"
      function: truthy
```

```bash
# Run in CI
npx @stoplight/spectral-cli lint openapi.yaml --ruleset .spectral.yaml
```

---

### Consumer-Driven Contract Testing (Pact)

```python
# Consumer (frontend/client) defines contract
from pact import Consumer, Provider

pact = Consumer('OrderWebApp').has_pact_with(Provider('OrderService'))

# Consumer specifies what it expects
pact.given('an order exists').upon_receiving(
    'a request for order 123'
).with_request(
    method='GET', path='/api/orders/123'
).will_respond_with(
    status=200,
    body={
        'id': '123',
        'status': Like('pending'),  # any string
        'total': Like(50.00),       # any number
    }
)

# Provider verifies it meets all consumer contracts
# In provider's CI:
verifier = Verifier(provider='OrderService', provider_base_url='http://localhost:8080')
verifier.verify_with_broker(
    broker_url='https://pact-broker.example.com',
    publish_verification_results=True
)
```

**Flow:**
1. Consumer writes contract (what it expects)
2. Contract published to Pact Broker
3. Provider CI runs contracts against actual service
4. Both sides must pass before deploy (can-i-deploy check)

---

### API Changelog and Deprecation Policy

```http
# Deprecation headers
Deprecation: true
Sunset: Sat, 01 Mar 2025 00:00:00 GMT
Link: </api/v3/users>; rel="successor-version"

# Changelog (in API docs)
## v2.3.0 (2024-01-15)
### Added
- `GET /orders` now supports `sort` parameter
- New field `estimated_delivery` on Order response

### Deprecated
- `GET /orders?order_by` - use `sort` instead (removal: 2024-07-01)
- Field `delivery_date` renamed to `estimated_delivery`

### Removed (Breaking)
- `GET /legacy/orders` - removed, use `/api/v2/orders`
```

**Deprecation policy:**
1. Mark deprecated (header + docs) - minimum 6 months notice
2. Monitor usage of deprecated endpoints
3. Notify consumers directly (email/Slack)
4. Remove after sunset date + grace period

---

## Advanced Patterns

### Webhook Design Patterns

**Description:** Server pushes events to client-provided URLs.

```python
# 1. Registration
@app.post("/api/webhooks")
async def register_webhook(body: WebhookRegistration):
    """
    {
        "url": "https://client.example.com/webhooks/orders",
        "events": ["order.placed", "order.shipped"],
        "secret": "whsec_..."  # for signature verification
    }
    """
    webhook = await save_webhook(body)
    # Verify URL is reachable
    await verify_endpoint(body.url)
    return {"id": webhook.id, "status": "active"}

# 2. Delivery
async def deliver_webhook(webhook, event):
    payload = json.dumps(event)
    timestamp = str(int(time.time()))
    
    # Sign payload (HMAC-SHA256)
    signature = hmac.new(
        webhook.secret.encode(),
        f"{timestamp}.{payload}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    response = await httpx.post(
        webhook.url,
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"v1={signature}",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-ID": event["id"],
        },
        timeout=30
    )
    
    if response.status_code >= 400:
        await schedule_retry(webhook, event)  # Exponential backoff

# 3. Consumer verification
def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"v1={expected}", signature)
```

**Best practices:**
- HMAC signatures for authenticity
- Retry with exponential backoff (3 attempts over 24h)
- Idempotency keys (X-Webhook-ID) for dedup
- Disable webhooks after consecutive failures
- Allow consumers to list/replay missed events

---

### Server-Sent Events (SSE)

**Description:** Server pushes text-based events over a single HTTP connection. Simpler than WebSocket for server→client streaming.

```python
# Server (FastAPI)
from fastapi.responses import StreamingResponse

@app.get("/api/orders/{order_id}/stream")
async def stream_order_updates(order_id: str):
    async def event_generator():
        async for update in subscribe_to_order(order_id):
            yield f"event: {update.type}\n"
            yield f"data: {json.dumps(update.data)}\n"
            yield f"id: {update.id}\n"
            yield "\n"  # End of event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# Client (JavaScript)
const evtSource = new EventSource('/api/orders/123/stream');

evtSource.addEventListener('status_changed', (e) => {
    const data = JSON.parse(e.data);
    updateUI(data);
});

evtSource.addEventListener('error', (e) => {
    // Auto-reconnects with Last-Event-ID header
});
```

**When to use:** Notifications, live feeds, progress updates (server→client only).
**SSE vs WebSocket:**
| Aspect | SSE | WebSocket |
|--------|-----|-----------|
| Direction | Server → Client only | Bidirectional |
| Protocol | HTTP | WS (upgrade from HTTP) |
| Reconnection | Built-in auto-reconnect | Manual |
| Data format | Text (UTF-8) | Text or binary |
| Complexity | Simple | Complex |
| Load balancer | Standard HTTP | Needs sticky sessions |

---

### WebSocket API Design

```python
# Server (FastAPI)
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/orders/{order_id}")
async def order_websocket(websocket: WebSocket, order_id: str):
    await websocket.accept()
    
    # Authentication
    token = websocket.query_params.get("token")
    if not validate_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    try:
        while True:
            # Receive client messages
            data = await websocket.receive_json()
            
            if data["type"] == "subscribe":
                await subscribe(websocket, data["channel"])
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        await cleanup(websocket)
```

**Message protocol design:**
```json
// Client → Server
{"type": "subscribe", "channel": "orders.123"}
{"type": "unsubscribe", "channel": "orders.123"}
{"type": "ping"}

// Server → Client
{"type": "event", "channel": "orders.123", "data": {"status": "shipped"}}
{"type": "error", "code": "INVALID_CHANNEL", "message": "..."}
{"type": "pong"}
{"type": "ack", "ref": "msg-123"}
```

**Best practices:**
- Heartbeat/ping-pong to detect dead connections
- Reconnection with exponential backoff on client
- Message IDs for acknowledgment and ordering
- Authentication on connect (token in query or first message)

---

### AsyncAPI Specification

```yaml
asyncapi: 2.6.0
info:
  title: Order Events
  version: 1.0.0

channels:
  orders/placed:
    publish:
      operationId: onOrderPlaced
      message:
        $ref: '#/components/messages/OrderPlaced'
    subscribe:
      operationId: publishOrderPlaced
      message:
        $ref: '#/components/messages/OrderPlaced'

  orders/{orderId}/status:
    parameters:
      orderId:
        schema:
          type: string
    subscribe:
      message:
        $ref: '#/components/messages/OrderStatusChanged'

components:
  messages:
    OrderPlaced:
      payload:
        type: object
        properties:
          orderId:
            type: string
          customerId:
            type: string
          total:
            type: number
      headers:
        type: object
        properties:
          correlationId:
            type: string
```

**When to use:** Documenting event-driven APIs (Kafka topics, WebSocket channels, MQTT).

---

### API Composition in Microservices

**Problem:** Queries that span multiple services.

```python
# Pattern 1: API Gateway Composition
@gateway.get("/api/product-page/{product_id}")
async def product_page(product_id: str):
    product, reviews, inventory, recommendations = await asyncio.gather(
        catalog_service.get_product(product_id),
        review_service.get_reviews(product_id, limit=10),
        inventory_service.check_stock(product_id),
        recommendation_service.get_similar(product_id, limit=5),
    )
    return compose_response(product, reviews, inventory, recommendations)

# Pattern 2: CQRS materialized view (pre-composed)
# Background worker maintains denormalized read model
class ProductPageProjection:
    async def on_product_updated(self, event):
        await self.update_view(event.product_id, product=event.data)
    
    async def on_review_added(self, event):
        await self.update_view(event.product_id, new_review=event.data)

# Single query for composed data
@app.get("/api/product-page/{product_id}")
async def product_page(product_id: str):
    return await product_page_view.get(product_id)  # Single read!
```

---

### Idempotency Keys

**Problem:** Client retries create duplicate resources (double charge, double order).

**Solution:** Client sends unique key; server ensures operation executes at most once.

```python
@app.post("/api/payments")
async def create_payment(body: PaymentRequest, request: Request):
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return JSONResponse(status_code=400, content={"error": "Idempotency-Key required"})
    
    # Check if already processed
    existing = await redis.get(f"idempotency:{idempotency_key}")
    if existing:
        return JSONResponse(
            content=json.loads(existing),
            status_code=200,
            headers={"X-Idempotent-Replayed": "true"}
        )
    
    # Lock to prevent concurrent duplicates
    lock = await redis.set(f"idempotency:{idempotency_key}:lock", "1", nx=True, ex=60)
    if not lock:
        return JSONResponse(status_code=409, content={"error": "Request in progress"})
    
    try:
        # Process payment
        result = await process_payment(body)
        response = result.dict()
        
        # Cache result (expire after 24h)
        await redis.set(f"idempotency:{idempotency_key}", json.dumps(response), ex=86400)
        
        return JSONResponse(content=response, status_code=201)
    finally:
        await redis.delete(f"idempotency:{idempotency_key}:lock")
```

```javascript
// Client usage
const response = await fetch('/api/payments', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Idempotency-Key': crypto.randomUUID()  // Generate once, reuse on retry
  },
  body: JSON.stringify(paymentData)
});
```

---

### Request Correlation

**Problem:** Tracing a request across multiple services.

```python
import uuid
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar('correlation_id')

# Middleware: extract or generate correlation ID
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    correlation_id_var.set(correlation_id)
    
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

# Pass to downstream services
async def call_downstream(url: str, data: dict):
    return await httpx.post(url, json=data, headers={
        "X-Correlation-ID": correlation_id_var.get()
    })

# Include in logs
logger.info("Processing order", extra={
    "correlation_id": correlation_id_var.get(),
    "order_id": order_id
})
```

**Headers to propagate:**
- `X-Correlation-ID` / `X-Request-ID` - unique per user request
- `traceparent` (W3C Trace Context) - for distributed tracing
- `X-B3-TraceId` (Zipkin B3 format)

---

### API Throttling and Quotas

```python
# Multi-tier throttling
class ThrottlingPolicy:
    """
    Tier 1: Per-second burst limit (token bucket)
    Tier 2: Per-minute sustained limit (sliding window)
    Tier 3: Daily quota (fixed window)
    """
    
    async def check(self, api_key: str) -> ThrottleResult:
        plan = await self.get_plan(api_key)
        
        # Check burst (e.g., 50 req/sec)
        if not await self.token_bucket.consume(api_key, plan.burst_limit):
            return ThrottleResult(allowed=False, retry_after=1)
        
        # Check sustained (e.g., 1000 req/min)
        if not await self.sliding_window.check(api_key, plan.rate_limit, 60):
            return ThrottleResult(allowed=False, retry_after=60)
        
        # Check daily quota (e.g., 100,000 req/day)
        usage = await self.daily_counter.increment(api_key)
        if usage > plan.daily_quota:
            return ThrottleResult(allowed=False, retry_after=self.seconds_until_midnight())
        
        return ThrottleResult(
            allowed=True,
            remaining=plan.daily_quota - usage,
            headers={
                "X-RateLimit-Limit": str(plan.rate_limit),
                "X-RateLimit-Remaining": str(plan.rate_limit - await self.sliding_window.count(api_key, 60)),
                "X-RateLimit-Reset": str(self.window_reset_time()),
                "X-Daily-Quota-Remaining": str(plan.daily_quota - usage),
            }
        )
```

**Best practices:**
- Different limits per endpoint (write > read cost)
- Communicate limits clearly in response headers
- Return `429 Too Many Requests` with `Retry-After`
- Provide dashboard for consumers to monitor usage
- Grace period before hard enforcement

---

## Summary: Choosing the Right API Style

| Scenario | Recommendation |
|----------|---------------|
| Public API for third parties | REST (OpenAPI spec) |
| Mobile app with varying data needs | GraphQL or BFF |
| Internal microservice communication | gRPC |
| Real-time server→client updates | SSE |
| Real-time bidirectional | WebSocket |
| Event-driven async communication | AsyncAPI + Message Broker |
| File uploads/downloads | REST with multipart |
| High-performance, low-latency | gRPC |
| Browser-first, simple CRUD | REST |
| Complex data graphs, multiple clients | GraphQL (Federation) |
