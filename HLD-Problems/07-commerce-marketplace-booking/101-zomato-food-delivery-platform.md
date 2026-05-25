# Design Zomato Food Delivery Platform - System Design Deep Dive

**Problem #101**  
**Category:** Marketplace/logistics  
**Primary pattern:** commerce booking + geo realtime marketplace  
**Deep-dive focus:** restaurant discovery, menu availability, order lifecycle, payment, delivery partner dispatch, ETA, real-time tracking, refunds, fraud

## 0. Interview Framing

Zomato is a three-sided marketplace: customers, restaurants, and delivery partners. The hardest part is not just placing an order; it is keeping restaurant availability, menu/pricing, payment state, kitchen preparation, delivery partner assignment, ETA, tracking, cancellation, refund, and support workflows consistent enough under high traffic.

In an interview, scope the answer to food discovery and food delivery first. Dining reservations, ads, loyalty, groceries, and B2B restaurant tooling can be mentioned as extensions, but the main design should focus on the customer order journey from search to delivered/refunded.

## 1. Requirements

### Functional Requirements

- Search restaurants, cuisines, dishes, offers, and nearby delivery options.
- Show restaurant status, menu, item availability, delivery fee, serviceability, ETA, ratings, and offers.
- Support cart, quote, coupon validation, taxes/fees, and payment method selection.
- Place idempotent orders and track order state from `CREATED` to `DELIVERED` or terminal failure.
- Integrate with restaurants through merchant app, POS/webhook adapters, and manual fallback.
- Assign delivery partners based on location, capacity, ETA, batching, fairness, and acceptance probability.
- Track delivery partner location in real time and update ETA for customers and restaurants.
- Support cancellation, refund, replacement, support tickets, ratings, and abuse/fraud workflows.
- Publish events for notifications, analytics, settlement, search indexing, fraud detection, and operational dashboards.

### Non-Functional Requirements

- Search and browse p99 latency below 300 ms for cacheable discovery paths.
- Checkout p99 latency below 1 second excluding external payment provider latency.
- Order state transitions must be idempotent, auditable, and protected from duplicate payment/order creation.
- Restaurant menu, availability, and price freshness should be within seconds to a few minutes depending on integration quality.
- Delivery tracking should tolerate out-of-order and missing location updates.
- The system should degrade gracefully during traffic spikes: browse/search stays available even if checkout is rate limited.
- Multi-region design should isolate city/region failures and preserve order correctness.

### Non-Goals

- Do not design every Zomato product line. Keep the core answer focused on food delivery.
- Do not build a perfect global total order of all events. Ordering is scoped to order, restaurant, delivery partner, and payment aggregates.
- Do not synchronously call every downstream system during checkout. Notifications, analytics, settlement, and search updates are asynchronous.
- Do not trust restaurant/POS inventory blindly for correctness. Use quote snapshots, restaurant confirmation, and reconciliation.

## 2. Capacity, Traffic, And Size Estimation

Use these as interview assumptions, not company facts.

| Dimension | Baseline Assumption |
|---|---|
| Customers | 20M DAU, 100M MAU |
| Restaurants | 500K active restaurants, 50M menu items |
| Delivery partners | 1M registered, 200K concurrently active at peak |
| Search/browse | 200K average QPS, 1M peak QPS during meal times |
| Cart/quote | 25K average QPS, 150K peak QPS |
| Orders | 5M orders/day, 10x lunch/dinner peak |
| Location updates | 200K active partners x 1 update / 3 seconds = 66K updates/sec |
| Notifications | 10-20 events/order plus promotions and support events |
| Storage | Order data 1-2 KB/order, event logs 5-20 KB/order, location hot retention 24-72 hours |

### Estimation Formulas

- Average order QPS = daily orders / 86,400.
- Peak order QPS = average order QPS x meal-time multiplier.
- Location update throughput = active delivery partners / update interval seconds.
- Order event storage/day = orders/day x events/order x average event size x replication factor.
- Menu index size = restaurant_count x avg_items_per_restaurant x indexed_fields_size x index_replication.
- Notification volume/day = orders/day x state_change_notifications + marketing/promo volume.

### Sizing Notes

- Discovery traffic dwarfs checkout traffic. Cache and search-index discovery aggressively.
- Location updates are high-write, short-retention telemetry. Do not store every raw point forever in the primary order DB.
- Order, payment, cancellation, refund, and settlement data require stronger correctness and longer retention than tracking telemetry.
- Partition order data by `city_id`, `order_id`, and time bucket; partition location data by `partner_id` and short time windows.

## 3. API Design

Use REST for public app APIs, gRPC for internal services, and event contracts for state propagation. Every mutation uses an idempotency key.

### Customer APIs

```http
GET /v1/restaurants/search?lat=12.9716&lon=77.5946&q=biryani&limit=30&cursor=<cursor>
Authorization: Bearer <customer_token>
```

```http
GET /v1/restaurants/{restaurant_id}/menu?lat=12.9716&lon=77.5946
Authorization: Bearer <customer_token>
```

```http
POST /v1/carts
Idempotency-Key: <uuid>
Authorization: Bearer <customer_token>
Content-Type: application/json

{
  "restaurant_id": "res_123",
  "items": [
    {
      "menu_item_id": "item_123",
      "quantity": 2,
      "customizations": [{"id": "spice_level", "value": "medium"}]
    }
  ],
  "delivery_address_id": "addr_123",
  "coupon_code": "DINNER20"
}
```

```http
POST /v1/orders
Idempotency-Key: <uuid>
Authorization: Bearer <customer_token>
Content-Type: application/json

{
  "cart_id": "cart_123",
  "quote_id": "quote_123",
  "payment_method_token": "paytok_123",
  "client_request_id": "req_123"
}
```

```http
GET /v1/orders/{order_id}
Authorization: Bearer <customer_token>
```

```http
GET /v1/orders/{order_id}/tracking
Authorization: Bearer <customer_token>
```

```http
POST /v1/orders/{order_id}/cancel
Idempotency-Key: <uuid>
Authorization: Bearer <customer_token>

{
  "reason": "customer_changed_mind"
}
```

### Restaurant APIs

```http
PATCH /v1/restaurants/{restaurant_id}/availability
Idempotency-Key: <uuid>
Authorization: Bearer <restaurant_token>

{
  "is_accepting_orders": true,
  "prep_time_minutes": 25,
  "unavailable_item_ids": ["item_456"]
}
```

```http
POST /v1/restaurant-orders/{order_id}/decision
Idempotency-Key: <uuid>
Authorization: Bearer <restaurant_token>

{
  "decision": "ACCEPTED",
  "estimated_ready_at": "2026-05-25T14:30:00Z"
}
```

### Delivery Partner APIs

```http
POST /v1/partners/{partner_id}/location
Authorization: Bearer <partner_token>

{
  "lat": 12.9716,
  "lon": 77.5946,
  "accuracy_m": 12,
  "recorded_at": "2026-05-25T14:10:00Z"
}
```

```http
POST /v1/delivery-jobs/{job_id}/decision
Idempotency-Key: <uuid>
Authorization: Bearer <partner_token>

{
  "decision": "ACCEPTED"
}
```

```http
POST /v1/delivery-jobs/{job_id}/status
Idempotency-Key: <uuid>
Authorization: Bearer <partner_token>

{
  "status": "ARRIVED_AT_RESTAURANT|PICKED_UP|ARRIVED_AT_CUSTOMER|DELIVERED",
  "proof_ref": "object://proof/photo_123"
}
```

### Internal APIs

```protobuf
service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (Order);
  rpc GetOrder(GetOrderRequest) returns (Order);
  rpc TransitionOrder(TransitionOrderRequest) returns (Order);
}

service DispatchService {
  rpc RequestAssignment(AssignmentRequest) returns (Assignment);
  rpc ReassignDelivery(ReassignmentRequest) returns (Assignment);
}

service ETAService {
  rpc EstimateDeliveryEta(EtaRequest) returns (EtaResponse);
}
```

### Error Model

- `400`: invalid cart, unavailable item, invalid transition, bad address, unsupported payment method.
- `401/403`: missing identity, restaurant mismatch, partner mismatch, or policy denial.
- `404`: restaurant/order/job not found or hidden by authorization.
- `409`: quote expired, cart changed, duplicate idempotency key with different request body, order state conflict.
- `422`: restaurant no longer serviceable, item unavailable, coupon invalid, payment authorization declined.
- `429`: customer, restaurant, partner, IP, or tenant quota exceeded.
- `5xx`: dependency failure. Return request ID and preserve idempotency for retries.

## 4. Async Event Contracts

Use transactional outbox for order/payment state changes and Kafka/Pulsar/Kinesis-style streams for high-volume telemetry.

```json
{
  "event_id": "evt_01H...",
  "event_type": "order.state_changed.v1",
  "occurred_at": "2026-05-25T14:15:30Z",
  "producer": "order-service",
  "city_id": "blr",
  "order_id": "ord_123",
  "aggregate_version": 18,
  "previous_state": "RESTAURANT_ACCEPTED",
  "new_state": "PARTNER_ASSIGNED",
  "idempotency_key": "idem_123",
  "actor": {
    "type": "system",
    "id": "dispatch-service"
  },
  "payload": {
    "restaurant_id": "res_123",
    "customer_id": "cust_123",
    "partner_id": "dp_123"
  }
}
```

### Core Event Topics

- `restaurant.availability.changed.v1`
- `menu.item.changed.v1`
- `cart.quote.created.v1`
- `order.created.v1`
- `order.state_changed.v1`
- `payment.authorized.v1`
- `payment.failed.v1`
- `delivery.assignment.requested.v1`
- `delivery.assignment.accepted.v1`
- `delivery.location.updated.v1`
- `refund.created.v1`
- `support.ticket.created.v1`

## 5. High-Level Architecture

### Architecture Design

```text
Zomato Food Delivery Platform Architecture

Actors / Clients / Partner Systems
        |
        v
DNS / Global Traffic Manager / CDN where useful
        |
        v
API Gateway
        |
        +--> Synchronous Command Path
        |       -> Pricing And Offer Service -> Cart/Quote Service -> Order Orchestrator -> Payment Service -> Dispatch Service -> Menu Service
        |       -> Source-of-Truth Write + Transactional Outbox
        |
        +--> Query / Serving Path
        |       -> Restaurant Discovery Service / Search Service / Menu Service
        |       -> Canonical Store fallback when strong freshness is required
        |
        +--> Async/Event Path
        |       -> Event Bus / Stream Processing / Workflow Queues
        |       -> Restaurant Integration Service / Notification Service
        |
        +--> Operations Path
                -> Admin Console / Audit / Reconciliation / Backfill / Disaster Recovery

Data Stores: Canonical booking/order/inventory DB + availability/search cache + payment state + event log + warehouse
Ops/Integrations: Payment/risk + partner adapters + dispatch/fulfillment + reconciliation/support
```

### Request And Data Flow

1. **Request entry:** actors enter through edge controls that authenticate, authorize, rate-limit, route, and attach trace context before reaching the Zomato Food Delivery Platform service boundary.
2. **Synchronous command path:** correctness-sensitive mutations stay inside Pricing And Offer Service -> Cart/Quote Service -> Order Orchestrator -> Payment Service -> Dispatch Service -> Menu Service; this path performs validation, idempotency checks, source-of-truth writes, and outbox publication.
3. **Query path:** read-heavy traffic is served by Restaurant Discovery Service / Search Service / Menu Service; strong reads fall back to the canonical store when stale projections are unsafe.
4. **Async path:** Restaurant Integration Service / Notification Service consume committed events for notifications, indexing, analytics, provider calls, ML/risk feedback, cleanup, and reconciliation.
5. **Operations path:** admin, audit, replay, reconciliation, backfill, and disaster-recovery workflows are isolated from user-facing latency but use the same immutable event/audit history.

### Component Responsibilities

- **API Gateway**: authentication, routing, request shaping, idempotency headers, coarse rate limits, WAF, and tracing.
- **Restaurant Discovery Service**: serviceability, open/closed state, cuisine/category filters, ranking, offers, ads, and personalization.
- **Search Service**: restaurant/dish/cuisine inverted indexes, geospatial filters, and query suggestions.
- **Menu Service**: canonical menus, item availability, add-ons, dietary tags, item images, and menu versioning.
- **Pricing And Offer Service**: item prices, delivery fee, platform fee, taxes, surge fee, coupons, loyalty, and quote expiry.
- **Cart/Quote Service**: cart state, quote snapshot, inventory/menu validation, coupon validation, and final payable amount.
- **Order Orchestrator**: order state machine, saga coordination, restaurant confirmation, payment boundary, dispatch trigger, cancellation/refund.
- **Payment Service**: payment authorization/capture/refund, COD handling, wallet credits, idempotency, reconciliation, and webhooks.
- **Restaurant Integration Service**: merchant app, POS adapters, webhooks, retry queues, manual confirmation fallback.
- **Dispatch Service**: candidate delivery partner selection, batching, fairness, partner acceptance, reassignment, and SLA timers.
- **ETA Service**: prep-time prediction, road ETA, pickup/drop ETA, traffic, weather, batching, and confidence intervals.
- **Location Service**: delivery partner location ingestion, compression, latest-location cache, stream processing, and customer tracking feed.
- **Notification Service**: push/SMS/WhatsApp/email/in-app notifications, templates, preferences, retries, and provider failover.
- **Support/Refund Service**: support cases, refunds, replacement, wallet credits, policy checks, fraud review, and audit.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| Edge/API boundary | API Gateway | Authentication, authorization handoff, request validation, rate limits, routing, TLS termination, coarse abuse controls, and trace context propagation. |
| Core domain services | Pricing And Offer Service, Cart/Quote Service, Order Orchestrator, Payment Service, Dispatch Service, Menu Service | Own Zomato Food Delivery Platform business invariants, source-of-truth writes, state transitions, idempotency, and synchronous API responses. |
| Query/serving services | Restaurant Discovery Service, Search Service, Menu Service | Serve low-latency reads from caches, read models, indexes, or specialized serving stores while exposing freshness/consistency guarantees. |
| Async workers and integrations | Restaurant Integration Service, Notification Service | Consume committed events, call external systems, retry safely, update projections, run cleanup, and isolate slow dependencies from user-facing latency. |
| Data and governance | OLTP DB / cache / search index / object store / warehouse / audit log | Separate canonical state from derived stores; support rebuild, partitioning, retention, encryption, backup, and analytical access. |
| Operations | Admin console / reconciliation / observability / runbooks | Provide support investigation, replay/backfill, manual correction, compliance evidence, SLO dashboards, and incident response. |

### Data Stores

- **Relational order DB** for orders, state transitions, payments, refunds, and support-critical workflows.
- **Restaurant/menu DB** for merchant metadata, menu versions, item availability, and serviceability.
- **Search index** for restaurants, dishes, cuisines, offers, and availability-enriched discovery.
- **Geo index/cache** for active delivery partner locations and restaurant service areas.
- **Redis/cache** for hot restaurant cards, menus, quote snapshots, session state, and latest tracking state.
- **Event log** for order events, menu changes, location telemetry, notifications, and analytics.
- **Object store** for images, invoices, support evidence, proof of delivery, exports, and logs.
- **OLAP warehouse** for growth analytics, SLA analysis, fraud signals, restaurant performance, and settlement reporting.

## 6. Low-Level Design

### Core Modules

- `RestaurantDiscoveryController`: handles search/browse APIs and delegates ranking, serviceability, and personalization.
- `MenuApplicationService`: manages menu versioning, item availability, restaurant status, and POS updates.
- `CartQuoteService`: validates cart, creates immutable quote snapshots, applies offers, computes fees/taxes, and sets expiry.
- `OrderApplicationService`: owns order creation, state transitions, idempotency, and saga orchestration.
- `OrderStateMachine`: rejects invalid transitions and emits auditable state-change facts.
- `PaymentAdapter`: isolates payment providers, COD, wallet credits, refunds, and provider webhooks.
- `RestaurantOrderAdapter`: sends orders to merchant app/POS and handles accept/reject/timeouts.
- `DispatchCoordinator`: requests partner assignment, manages acceptance timeout, and triggers reassignment.
- `LocationIngestionWorker`: validates, deduplicates, and publishes partner location updates.
- `ETAEngine`: combines restaurant prep time, partner position, map routing, batching, and historical features.
- `SupportRefundService`: handles customer complaints, refund policy, evidence, approvals, and settlement adjustments.

### Interfaces

```java
interface OrderRepository {
    Optional<Order> findById(OrderId orderId, ReadConsistency consistency);
    Order save(Order order, ExpectedVersion expectedVersion);
    List<OrderTransition> transitions(OrderId orderId);
}

interface OrderStateMachine {
    TransitionResult transition(Order order, OrderAction action, Actor actor, Instant now);
}

interface QuoteService {
    Quote createQuote(CustomerId customerId, Cart cart, DeliveryAddress address, CouponCode coupon);
    Quote validateQuote(QuoteId quoteId, Cart cart, Instant now);
}

interface DispatchService {
    Assignment requestAssignment(Order order, Restaurant restaurant, DeliveryAddress address);
    Assignment reassign(OrderId orderId, ReassignmentReason reason);
}

interface ETAService {
    Eta estimate(EtaContext context);
}
```

### Order State Machine

```text
CREATED
  -> PAYMENT_AUTHORIZED
  -> SENT_TO_RESTAURANT
  -> RESTAURANT_ACCEPTED
  -> PARTNER_ASSIGNMENT_REQUESTED
  -> PARTNER_ASSIGNED
  -> PARTNER_AT_RESTAURANT
  -> PICKED_UP
  -> PARTNER_AT_CUSTOMER
  -> DELIVERED

Terminal failure states:
  PAYMENT_FAILED
  RESTAURANT_REJECTED
  CUSTOMER_CANCELLED
  RESTAURANT_CANCELLED
  PARTNER_CANCELLED
  AUTO_CANCELLED_TIMEOUT
  REFUNDED
```

Rules:

- `DELIVERED`, `REFUNDED`, and cancellation terminal states cannot transition back to active states.
- Payment capture happens only after a configured milestone, often restaurant acceptance or delivery depending on method and policy.
- Restaurant timeout triggers auto-cancel or manual intervention.
- Partner timeout triggers reassignment, not order cancellation unless SLA is breached.
- Refund is a separate financial workflow linked to the order and payment, not a destructive update to the order.

## 7. Database Modeling And DB Design

### Logical Model

```text
Customer
  -> has addresses, carts, orders, payments, support tickets

Restaurant
  -> has service areas, menu versions, menu items, availability, merchant users

Order
  -> references quote, restaurant, customer, payment, delivery job, support/refund records

DeliveryPartner
  -> has current session, location stream, delivery jobs, payouts
```

### Core Tables

| Table | Important Columns |
|---|---|
| `customers` | `id, phone_hash, email_hash, default_address_id, risk_score, state, created_at` |
| `customer_addresses` | `id, customer_id, lat, lon, geohash, address_text_encrypted, instructions_encrypted, state` |
| `restaurants` | `id, city_id, name, lat, lon, geohash, cuisine_tags, rating, price_band, state` |
| `restaurant_availability` | `restaurant_id, is_accepting_orders, prep_time_minutes, capacity_score, updated_at, source` |
| `service_areas` | `restaurant_id, city_id, polygon_ref, max_distance_km, delivery_enabled, updated_at` |
| `menu_versions` | `id, restaurant_id, version, status, source, created_at, published_at` |
| `menu_items` | `id, restaurant_id, menu_version_id, name, category, price, tax_code, available, image_ref` |
| `carts` | `id, customer_id, restaurant_id, items_json, coupon_code, state, updated_at` |
| `quotes` | `id, cart_id, restaurant_id, customer_id, price_snapshot_json, fee_snapshot_json, expires_at, state` |
| `orders` | `id, city_id, customer_id, restaurant_id, quote_id, payment_id, delivery_job_id, state, version, created_at` |
| `order_items` | `order_id, menu_item_id, name_snapshot, quantity, price_snapshot, customization_snapshot_json` |
| `order_transitions` | `id, order_id, from_state, to_state, actor_type, actor_id, reason, request_id, created_at` |
| `payments` | `id, order_id, provider, method, amount, currency, state, idempotency_key, updated_at` |
| `refunds` | `id, order_id, payment_id, amount, reason, state, approved_by, created_at` |
| `delivery_partners` | `id, city_id, vehicle_type, rating, state, risk_score, created_at` |
| `partner_sessions` | `id, partner_id, city_id, status, current_lat, current_lon, last_seen_at, expires_at` |
| `delivery_jobs` | `id, order_id, partner_id, pickup_geohash, drop_geohash, state, assigned_at, delivered_at` |
| `partner_locations_hot` | `partner_id, ts_bucket, recorded_at, lat, lon, accuracy_m, source` |
| `support_tickets` | `id, order_id, customer_id, category, priority, state, assigned_agent_id, created_at` |
| `audit_log` | `id, actor_type, actor_id, action, resource_type, resource_id, outcome, request_id, ts` |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | PostgreSQL/MySQL with strong transactions, or CockroachDB/Spanner for global inventory/order consistency; separate ledger DB for money if payments are in scope | orders, bookings, inventory holds, payments, and disputes require constraints, state machines, and auditability |
| Hot serving / cache | Redis Cluster for availability summaries, carts, quotes, seat/slot holds with TTL, dispatch candidates, and rate limits | keeps hot reads, sessions, counters, quotas, and derived views away from the OLTP source of truth |
| Event stream / outbox | Kafka/Pulsar/Kinesis with compacted topics for keys and retained topics for replay | decouples projections, notifications, analytics, search indexing, and recovery from the write path |
| Search / analytics | OpenSearch/Elasticsearch for discovery; ClickHouse/Druid/Pinot for marketplace, funnel, and operational analytics | serves text/filter/OLAP queries without overloading transactional tables |
| Large immutable payloads | object storage for invoices, tickets, contracts, images, proof, and support attachments | large or immutable data is cheaper, durable, and easier to lifecycle outside OLTP rows |

Interview stance: name the source-of-truth database first, then explicitly separate caches, indexes, event logs, and analytics stores. The cache, search index, and warehouse are derived systems; they must be rebuildable from canonical state and immutable events.

### Replication Strategy

- Primary store: multi-AZ synchronous or quorum replication for the primary store; asynchronous cross-region replicas for DR and read locality.
- Event log: replicate each partition across at least 3 brokers/nodes, require quorum acknowledgements for critical events, and monitor under-replicated partitions.
- Cache/read models: replicate for availability, but treat them as disposable; rebuild from source-of-truth rows plus events after corruption or cache loss.
- Object storage: use multi-AZ durability by default; enable cross-region replication only for disaster recovery, compliance, or locality requirements.
- Analytics/search stores: replicate shards for query availability, but recover by replaying events or rebuilding from snapshots when correctness is in doubt.

### Sharding And Partitioning Strategy

- Primary partition key: `market/city/tenant + aggregate_id; inventory_key for scarce resources; time bucket for transitions and audit`. Choose the key that matches the hottest write/read path, not just the entity name.
- Primary lookup path: `order_id/booking_id/reservation_id/listing_id` should be single-partition whenever possible.
- Time-partition append-heavy data such as events, audit logs, metrics, and delivery attempts so retention, archival, replay, and backfills do not scan the full corpus.
- Hot partition mitigation: serialize scarce inventory per resource, use short TTL holds, virtual shards for hot sellers/events, and queue isolation per market/provider.
- Keep tenant/cell/region boundaries explicit so one large customer, city, celebrity, event, or provider cannot overload the whole system.

### Indexing Strategy

- Required secondary indexes: `buyer_id + created_at, seller_id + created_at, inventory_key + state, state + expires_at, provider_reference`.
- Keep OLTP indexes minimal on high-write tables; move broad filtering, text search, ranking, and analytics to dedicated search/OLAP stores.
- Use composite indexes that match real query order: equality columns first, then range/sort columns such as `created_at`, `updated_at`, or `score`.
- For mutable state machines, index `(state, updated_at)` or `(state, next_attempt_at)` for workers and repair jobs.
- For audit and event tables, prefer append-only writes with time-bucketed partitions and compact indexes over many mutable secondary indexes.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Canonical command path | CP for scarce inventory and money-facing transitions | strong consistency for inventory holds, booking/order state, payment authorization, refunds, and entitlement issuance | Prefer rejecting or queuing unsafe writes over accepting divergent state. |
| Derived read models | AP/eventual for discovery, ETA/tracking projections, and read-only availability summaries with explicit staleness | Eventual consistency for search availability, recommendations, notifications, dashboards, tracking views, and analytics | Expose `pending`, `processing`, `stale_at`, or version metadata when users may observe lag. |
| Cache | AP with bounded TTL, unless used for a lock/fencing decision | Eventually consistent and invalidated by events or short TTL | Cache is never the only source of truth for correctness-critical state. |
| Search / analytics | AP/eventual | Asynchronous ingestion with replay/backfill | Results can lag; define freshness SLO and rebuild path. |
| Audit / ledger / immutable events | CP for append acceptance; replicated for durability | Append-only, immutable, replayable | Used for reconciliation, forensics, and projection rebuilds. |

### Data Lifecycle, Backups, And Rebuilds

- PITR backups, periodic restore drills, immutable event retention, and projection rebuilds from source-of-truth plus event log.
- Use transactional outbox or change-data-capture so database commits and emitted events cannot silently diverge.
- Define retention per data class: hot OLTP rows, warm history, cold object-store archives, legal holds, and deletion/anonymization workflows.
- Run checksum/control-total reconciliation between source-of-truth tables, event streams, search indexes, warehouses, and external providers.
- Document restore order: primary metadata first, immutable events second, object payloads third, then rebuild caches/search/read models.

### Platform Building Blocks And Microservice Patterns

Use these technologies only where they fit the access pattern and correctness boundary. A strong interview answer says what is on the synchronous hot path, what is asynchronous, what is derived, and what can be rebuilt.

| Concern | Recommended Building Blocks | How To Use In This Design | Key Interview Caveat |
| --- | --- | --- | --- |
| Hot-path caching | CDN, Redis Cluster, Memcached, local in-process cache, request coalescing, stale-while-revalidate | Cache hot reads, sessions, tokens, rate-limit counters, derived cards, and expensive computed views. Invalidate through events or short TTLs. | Never make cache the only source of truth for money, permissions, scarce inventory, or irreversible state. |
| Async processing | Kafka, Pulsar, Kinesis, RabbitMQ/SQS, transactional outbox/inbox, DLQ, retry with jitter | Move notifications, indexing, analytics, projections, provider calls, and slow side effects off the user-visible path. | Consumers must be idempotent; partition by aggregate when ordering matters. |
| Stream processing | Apache Flink, Kafka Streams, Spark Structured Streaming, Beam | Build rolling counters, fraud/risk signals, ranking features, ETA/features, alerting, and near-real-time materialized views. | Use event time, watermarks, replay, and exactly-once/effectively-once sinks only where the business needs it. |
| Batch jobs and workflows | Airflow, Dagster, Argo Workflows, Temporal, Cadence, Step Functions, Spark | Run backfills, reconciliation, compaction, expiry, report generation, settlement, lifecycle management, and ML feature generation. | Keep batch workers isolated from online capacity and make every job restartable and idempotent. |
| CDC and projections | Debezium, database CDC, Kafka Connect, outbox table relay | Feed search indexes, CQRS read models, lakehouse tables, caches, and audit pipelines from committed changes. | CDC is for propagation; business commands still go through domain services. |
| Event contracts | Schema Registry, Avro, Protobuf, JSON Schema, AsyncAPI, compatibility checks | Version domain events, enforce backward/forward compatibility, and document owners and consumers. | Breaking schema changes require new event versions and migration windows. |
| CQRS and read models | Command store, query projections, materialized views, search indexes | Keep canonical writes small and strongly owned; serve read-heavy views from projections optimized for query shape. | Expose freshness/version metadata and rebuild projections from events. |
| Microservice consistency patterns | Saga/process manager, transactional outbox, inbox dedupe, idempotency keys, compensating actions | Coordinate multi-service workflows without distributed transactions. | Make every state transition explicit and auditable; avoid hidden side effects. |
| Event storming and domain modeling | Commands, aggregates, events, policies, read models, bounded contexts | Identify aggregate owners, event names, invariants, side effects, and read projections before drawing service boxes. | Services should map to ownership boundaries, not arbitrary technical layers. |
| Object storage and lakehouse | S3/GCS/Azure Blob, Iceberg, Hudi, Delta Lake, Glue/Hive catalog | Store raw events, media, attachments, audit exports, feature data, and replayable history in immutable partitions. | Keep object/lake data partitioned by date/tenant/domain key and govern retention/privacy. |
| Analytics serving | Pinot, ClickHouse, Druid, Redshift, BigQuery, Snowflake, Athena/Trino/Presto | Serve dashboards, funnels, investigations, operational analytics, ad hoc SQL, and historical reports outside OLTP. | Do not run exploratory analytics against the primary transactional database. |
| Service runtime and governance | Spring Boot, Quarkus, Micronaut, Go/gRPC, Node.js, Kubernetes, service mesh, mTLS, API gateway, OpenTelemetry, config service, feature flags | Deploy independently, enforce auth, collect traces/metrics/logs, and roll out safely with canaries and kill switches. | More services increase operational load; split only when ownership, scale, or reliability justifies it. |

For this design, use Redis for quotes/availability/holds with canonical revalidation, Kafka/outbox for order lifecycle events, sagas/process managers for payment and fulfillment, Flink for fraud/ETA/marketplace signals, S3 + Iceberg for history, and Pinot/ClickHouse for operational dashboards.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

## 8. Critical Flows

### Restaurant Discovery Flow

1. Customer app sends location, query, filters, and personalization context.
2. API gateway authenticates customer and applies coarse throttling.
3. Discovery service finds serviceable restaurants by geohash/city and filters closed or overloaded restaurants.
4. Search service retrieves candidate restaurants/dishes using query text, cuisine, menu terms, and availability signals.
5. Ranking service scores candidates using distance, ETA, rating, price, offers, reliability, personalization, and ad/promoted slots.
6. Response returns restaurant cards with ETA, delivery fee, offer summary, rating, and cache metadata.

### Checkout And Order Placement Flow

1. Customer creates cart with restaurant, menu items, address, and coupon.
2. Cart/Quote service validates item availability, restaurant status, serviceability, coupon, taxes, fees, surge, and ETA.
3. Customer places order with `quote_id`, payment token, and idempotency key.
4. Order service validates quote expiry and creates order in `CREATED` state.
5. Payment service authorizes payment or records COD/wallet state.
6. Order service transitions to `SENT_TO_RESTAURANT` and emits outbox event.
7. Restaurant integration service asks merchant/POS to accept or reject the order.
8. If accepted, order transitions to `RESTAURANT_ACCEPTED` and dispatch begins.
9. If rejected or timed out, order transitions to terminal failure and refund/reversal is triggered.

### Dispatch And Delivery Flow

1. Dispatch service receives `order.restaurant_accepted`.
2. Candidate generator finds nearby active partners using geospatial index and filters by vehicle, current job, rating, risk, and freshness.
3. ETA service estimates pickup and drop ETA for top candidates.
4. Dispatch scorer balances ETA, acceptance probability, batching, fairness, partner utilization, and SLA.
5. Assignment request is sent to the selected partner with an acceptance deadline.
6. If accepted, order moves to `PARTNER_ASSIGNED`; if timed out/rejected, dispatch tries the next candidate or escalates.
7. Partner app streams location updates. Location service updates latest-location cache and publishes telemetry.
8. Customer tracking reads latest partner location, order state, and ETA projection.
9. Delivery completion captures payment if needed, emits settlement/notification events, and closes the delivery job.

### Cancellation And Refund Flow

1. Customer, restaurant, support agent, or system requests cancellation.
2. Order service checks state-specific cancellation policy and actor permissions.
3. If cancellation is allowed, order transitions to terminal cancel state with reason.
4. Refund service computes refund amount based on payment method, order state, restaurant prep, policy, and goodwill rules.
5. Payment service reverses/captures/refunds through provider or wallet ledger.
6. Settlement and restaurant/partner payout adjustments are emitted asynchronously.

## 9. Deep-Dive Focus Areas

- **Restaurant discovery**: Use geospatial filtering before ranking; merge search relevance, serviceability, ETA, restaurant reliability, rating, offers, and personalization.
- **Menu availability**: Keep menu versions immutable and availability mutable; quote snapshots protect checkout from price/item drift.
- **Order lifecycle**: Model every transition explicitly; use idempotency keys, expected versions, and immutable transition logs.
- **Restaurant integration**: Support merchant app, POS webhook, polling, retries, timeout, and manual fallback because partner integrations vary in quality.
- **Delivery dispatch**: Candidate generation is geo-heavy; final scoring is multi-factor and must account for fairness and acceptance probability.
- **ETA**: Combine prep time, queue depth, road ETA, traffic, partner location freshness, batching, weather, and restaurant historical reliability.
- **Real-time tracking**: Use latest-location cache for app reads and event stream/object storage for telemetry retention.
- **Payment and refunds**: Keep payment authorization, capture, refund, wallet credits, COD reconciliation, and settlement as auditable workflows.
- **Fraud and abuse**: Score customers, restaurants, partners, coupons, COD, refunds, fake GPS, self-orders, collusion, and repeated complaints.

## 10. Scaling Bottlenecks And Mitigations

| Bottleneck | Why It Happens | Mitigation |
|---|---|---|
| Meal-time traffic spike | Search, checkout, payment, and dispatch spike in lunch/dinner windows. | City-level autoscaling, queue isolation, cache warming, rate limits, and graceful degradation. |
| Hot restaurants | Popular restaurants receive disproportionate menu/order traffic. | Hot restaurant cache, per-restaurant capacity controls, queueing, throttled acceptance, and realistic ETA. |
| Location update flood | Active delivery partners send frequent GPS updates. | Adaptive update intervals, compression, dedupe, latest-location cache, stream processing, and TTL storage. |
| Payment provider latency | External providers add tail latency and timeouts. | Idempotent async confirmation, provider failover, payment state machine, and reconciliation. |
| Restaurant/POS outage | Orders cannot be confirmed. | Merchant app fallback, timeout policy, auto-cancel/refund, manual support queue, and restaurant health score. |
| Dispatch starvation | Some orders are hard to assign because of distance, weather, supply shortage, or low payout. | Dynamic incentives, batching, reassignment, SLA escalation, and city operations alerts. |
| Search index staleness | Restaurant/menu updates lag behind discovery. | Event-driven indexing, freshness indicators, read-through validation at quote time, and index lag alerts. |

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Authenticate customer, restaurant, partner, admin, and service identities separately.
- Authorize every order read/write by role: customer can view own orders, restaurant can view own restaurant orders, partner can view assigned jobs, support requires audited access.
- Encrypt addresses, phone numbers, payment references, support evidence, and location history at rest.
- Tokenize payment instruments. Do not store raw card/UPI/bank credentials in the core order system.
- Sign provider webhooks and restaurant/POS callbacks; reject replayed callbacks with nonce/timestamp validation.
- Limit location visibility: customers see assigned partner location only during active delivery windows.
- Apply WAF, bot defense, coupon abuse limits, account velocity checks, fake GPS detection, and refund abuse detection.
- Keep immutable audit logs for admin actions, refunds, manual overrides, partner reassignment, and customer data access.
- Apply retention controls for personal data, location history, support evidence, invoices, and legal/tax records.

## 12. Reliability, Failure Modes, And Recovery

| Failure Mode | Impact | Recovery Strategy |
|---|---|---|
| Order DB shard unavailable | Checkout and state transitions fail for affected city/shard. | Multi-AZ failover, circuit breaker, city-level traffic shaping, and explicit retry-safe responses. |
| Payment webhook delayed | Order payment state may remain pending. | Poll provider, reconcile by payment reference, keep order in pending state, and notify customer if action is needed. |
| Restaurant does not respond | Customer waits and delivery cannot start. | Timeout, auto-cancel or support fallback, refund/reversal, restaurant reliability score update. |
| Partner app loses network | Tracking stale and job updates delayed. | Last-known location, heartbeat timeout, customer messaging, fallback calling/support, reassignment if needed. |
| Event broker lag | Notifications, analytics, search updates, and dispatch side effects lag. | Lag alerts, consumer autoscaling, priority topics for order-critical events, replay from offsets. |
| Bad menu or price update | Wrong item availability or incorrect quote. | Versioned menus, quote snapshots, approval workflow for bulk updates, rollback, and merchant audit. |
| Region/city outage | City-specific operations impacted. | City partition isolation, cross-region read fallback, order-safe failover runbook, and RPO/RTO per workflow. |

## 13. Deployment And Operations

- Deploy services across multiple availability zones with city-aware partitioning.
- Separate online checkout/dispatch services from analytics, notification, and backfill workloads.
- Use canary deployments gated by order success rate, payment failure rate, restaurant acceptance rate, dispatch latency, and ETA error.
- Apply backward-compatible schema migrations: expand, dual-write/backfill if needed, verify, then contract.
- Maintain kill switches for coupons, COD, specific payment providers, restaurant POS adapters, batching, and promotional ranking.
- Keep operational consoles for city ops: restaurant health, order backlog, unassigned orders, partner supply heatmap, ETA outliers, and refund queue.
- Run game days for provider outage, event lag, city traffic spike, payment duplicate, and large restaurant outage.

## 14. Observability: SLIs, SLOs, Dashboards, Alerts

### SLIs And SLOs

| Area | SLI | Example SLO |
|---|---|---|
| Discovery latency | p95/p99 restaurant search latency | p99 < 300 ms |
| Checkout success | successful order creations / checkout attempts | > 99% excluding customer/payment declines |
| Payment correctness | duplicate or lost payment/order cases | zero known unhandled money correctness issues |
| Restaurant confirmation | accepted/rejected/timed-out order decision time | 95% decisions within configured restaurant SLA |
| Dispatch latency | time from restaurant acceptance to partner assigned | 95% under city-specific threshold |
| Tracking freshness | age of latest partner location shown to customer | p95 < 10 seconds during active delivery |
| ETA quality | absolute ETA error at pickup/drop | p50 and p90 tracked by city/restaurant/partner |
| Event freshness | order event consumer lag | critical consumers within seconds |

### Dashboards

- Search funnel: query QPS, result count, zero-result rate, latency, cache hit ratio, index freshness.
- Checkout funnel: cart creation, quote success, payment authorization, restaurant acceptance, order cancellation.
- City ops: active orders, unassigned orders, partner supply, restaurant backlog, SLA breaches, weather/traffic impact.
- Dispatch: candidate count, assignment acceptance rate, reassignment rate, batching rate, pickup/drop ETA error.
- Payment/refund: provider latency, authorization failures, duplicate idempotency attempts, pending refunds, reconciliation breaks.
- Restaurant health: POS failures, acceptance time, rejection rate, item unavailable rate, prep-time accuracy.
- Security/fraud: coupon abuse, COD abuse, fake GPS, suspicious refunds, admin overrides, data access.

### Alerts

- Page on checkout SLO burn, duplicate order/payment detection, payment provider outage, dispatch assignment collapse, severe event lag, or data leak signal.
- Ticket on rising zero-result rate, moderate ETA drift, restaurant integration degradation, refund queue growth, or index freshness lag.
- Route alerts by city, service, severity, and owner with runbook links.

## 15. Cost Model And Trade-Offs

### Cost Drivers

- Search index replicas and discovery QPS.
- Location telemetry ingestion, stream processing, hot cache, and retention.
- Order/payment relational DB write capacity and replicas.
- Notification provider calls, especially SMS/WhatsApp.
- Map/routing/ETA calls and geospatial compute.
- Object storage for menu images, proof of delivery, invoices, and support evidence.
- OLAP storage and query compute for operational dashboards.

### Cost Formula

```text
monthly_cost = service_compute_hours
             + search_index_tb_months
             + relational_db_storage_and_iops
             + cache_memory_gb_hours
             + event_stream_ingest_and_retention
             + location_telemetry_storage
             + notification_provider_calls
             + map_routing_api_calls
             + object_storage_tb_months
             + network_egress_tb
             + observability_ingest_gb
```

### Cost Controls

- Cache restaurant cards, menus, offers, and geospatial serviceability results.
- Use adaptive partner location update frequency based on active job state and movement.
- Store only latest location in hot cache; downsample or expire raw telemetry.
- Batch notification sends where product allows and prefer push over paid channels when reliable.
- Precompute popular search facets and restaurant rankings per city/meal window.
- Use city-level autoscaling and isolate backfills from online traffic.

## 16. Key Trade-Offs

| Decision | Option A | Option B | Interview Guidance |
|---|---|---|---|
| Menu consistency | Always validate with restaurant/POS at checkout | Trust cached menu until restaurant accepts | Validate quote and restaurant acceptance for correctness; cache for browse speed. |
| Payment timing | Capture before restaurant acceptance | Authorize first, capture after acceptance/delivery | Authorization-first reduces refund pain; capture timing depends on payment method and policy. |
| Dispatch timing | Assign partner before restaurant accepts | Assign after restaurant accepts | After acceptance avoids wasted partner time; early assignment can reduce ETA for reliable restaurants. |
| ETA | Simple distance-based model | Feature/model-based ETA | Start simple, but production needs prep time, traffic, partner state, batching, and restaurant reliability. |
| Tracking storage | Store all raw GPS forever | Hot latest + short raw retention + downsampled analytics | Keep customer experience fast and privacy risk bounded. |
| Search freshness | Update index synchronously | Event-driven async indexing | Async indexing scales better; quote validation protects correctness. |

## 17. Common Interview Follow-Ups

- How do you prevent duplicate orders when the app retries after timeout?
- What happens if payment succeeds but order creation or restaurant confirmation fails?
- How do you handle restaurant rejection after payment authorization?
- How do you assign delivery partners during rain or city-wide traffic spikes?
- How do you detect fake GPS from delivery partners?
- How do you keep menu prices and item availability fresh across POS integrations?
- What data is strongly consistent, and what can be eventually consistent?
- How would you support batching two nearby orders for one delivery partner?
- How do you reconcile COD, wallet credits, refunds, restaurant settlement, and partner payout?

## 18. Final Interview Checklist

- Clarify whether the scope is food delivery only or includes dining, ads, loyalty, and groceries.
- Draw separate flows for discovery, checkout, restaurant confirmation, dispatch, tracking, cancellation, and refund.
- Name the source of truth for order, payment, restaurant menu, delivery job, and partner location.
- State consistency choices: strong for order/payment/refund; eventual for search, tracking history, analytics, counters, and notifications.
- Explain idempotency, retries, outbox events, state machine transitions, and reconciliation.
- Cover geo partitioning, location telemetry scale, dispatch scoring, ETA quality, operational dashboards, security, privacy, and cost.

## 19. World-Class Interview Review

### What A Strong Interview Answer Must Demonstrate

- **Correctness boundary:** the canonical aggregate store and immutable event/audit history is the authority; derived caches, search indexes, dashboards, and analytics must be rebuildable.
- **Hot path clarity:** start from `core request path` and walk the synchronous command path before discussing secondary features.
- **Service ownership:** explicitly assign responsibilities to API Gateway, Restaurant Discovery Service, Search Service, Menu Service, Pricing And Offer Service, Cart/Quote Service; avoid vague boxes that do not own data or decisions.
- **Data ownership:** ground the design in `canonical aggregate, idempotency, event, and audit tables` and explain partitioning, indexes, retention, and replay.
- **Event model:** use `restaurant.availability.changed.v1, menu.item.changed.v1, cart.quote.created.v1, order.created.v1, order.state_changed.v1, payment.authorized.v1` to decouple slow work while preserving idempotency and ordering per aggregate.
- **Operational maturity:** include backpressure, DLQs, reconciliation, runbooks, audit trails, and safe manual correction.

### Bar-Raiser Drill-Down Prompts

- Which service owns the final decision for `core request path`, and what exact write makes it durable?
- What is the idempotency key scope, and what happens if the same key is retried with a different payload?
- Which read paths can be stale, and which user actions must revalidate against the source of truth?
- What breaks during a dependency outage, and how does the system converge after callbacks or reports arrive late?
- Which metric would page the on-call engineer before user-visible correctness, data safety, or money correctness is impacted?

### Common Weak Answers To Avoid

- Drawing only a generic API -> service -> database diagram without ownership boundaries.
- Skipping idempotency, retries, duplicate callbacks, and reconciliation.
- Putting all features on the synchronous path and ignoring backpressure or degradation.
- Treating cache/search/analytics as source of truth for critical decisions.
- Listing databases without explaining partition key, consistency model, retention, and recovery.

### Domain-Specific Bar Raiser Notes
- Prove scarce inventory/assignment correctness before optimizing ranking.
- Show quote/hold/commit/cancel/refund lifecycle and partner timeout handling.
- Separate discovery freshness from checkout/source-of-truth validation.

### 5-Minute Whiteboard Structure

- First minute: scope actors, constraints, and `core request path`.
- Minutes 2-3: draw edge, command path, query path, async path, and data stores; name API Gateway, Restaurant Discovery Service, Search Service, Menu Service, Pricing And Offer Service, Cart/Quote Service.
- Minute 4: walk one critical flow and call out idempotency, consistency, and failure recovery.
- Minute 5: close with scale bottlenecks, security/privacy, observability, cost, and trade-offs.
