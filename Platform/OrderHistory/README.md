# Order History Service (nxt-order-history-service)

> Comprehensive architecture, data modeling, partitioning, and query documentation for Plural Platform V3's read-optimized order store.

## Service Identity

| Attribute | Value |
|-----------|-------|
| **Service** | `nxt-order-history-service` |
| **Language** | Kotlin 1.9.25 / JVM 17 |
| **Framework** | Ktor 2.3.4 (CIO engine) |
| **DI** | Koin 3.5.1 |
| **Config** | Hoplite (YAML + env vars) |
| **Datastore** | OpenSearch 2.16 |
| **Cache** | Redis (Redisson 3.22) |
| **Port** | 8080 |
| **Repo** | `nxt_order_history_service` |

## Purpose

The Order History Service is the platform's **read-optimized query layer** — a materialized view over the OMS transactional database, optimized for:

1. **Real-time order lookup** — Sub-millisecond retrieval by orderId
2. **Complex filtering** — Multi-field queries across order/payment state, time ranges, merchants
3. **Deep pagination** — Scroll-based iteration over millions of orders (for recon, reporting)
4. **Aggregation** — Captured/refunded amounts, order counts
5. **Downtime detection** — Monitoring payment method health via error rate analysis

## Document Map

| # | Document | Description |
|---|----------|-------------|
| 01 | [Architecture Overview](./01-architecture-overview.md) | System context, CDC pipeline, component design, deployment |
| 02 | [Data Model & OpenSearch Schema](./02-data-model-and-schema.md) | Document structure, field mappings, nested objects, Protobuf contract |
| 03 | [Indexing, Partitioning & Lifecycle](./03-indexing-partitioning-lifecycle.md) | Bi-monthly partitions, dual-write migration, alias rotation, versioning |
| 04 | [CDC Ingestion Pipeline](./04-cdc-ingestion-pipeline.md) | Debezium → Kafka → Firehose → OHS, event processing, upsert logic |
| 05 | [Query Patterns & API Workflows](./05-query-patterns-and-workflows.md) | All API endpoints, filter/scroll/aggregate queries, routing decisions |
| 06 | [Key Query Flows & Diagrams](./06-key-query-flows.md) | Recon queries, merchant dashboard, get-status, aggregation workflows |

## Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **OpenSearch over PostgreSQL for reads** | Sub-ms full-text + structured queries at scale; avoids read load on transactional DB |
| **Bi-monthly index partitioning** | Limits shard size (~15-day windows); enables index lifecycle (delete old data) |
| **Nested type for payments** | Enables per-payment aggregations and filters without cross-object pollution |
| **External versioning** | Optimistic concurrency — only the latest version wins regardless of arrival order |
| **No Kafka consumer (Firehose HTTP sink)** | Decouples OHS from Kafka consumer group management; Firehose handles retries/DLQ |
| **Dual-write migration** | Zero-downtime migration from flat to nested index without data loss |
| **Protobuf as canonical format** | Single serialization format (from OMS → Kafka → OHS → OpenSearch) eliminates transformation bugs |
| **Redis dedup for score updates** | Prevents flooding Decision Engine with redundant acquirer score updates |

## Service Interactions

```mermaid
graph LR
    subgraph "Upstream (Write Path)"
        OMS[OMS<br/>nxt-payments-service]
        OUTBOX[(Outbox Table)]
        DEBEZIUM[Debezium CDC]
        KAFKA[Kafka MSK<br/>outbox.event.orders<br/>update.event.orders]
        FIREHOSE[GoTo Firehose<br/>HTTP Sink Connector]
    end

    subgraph "Order History Service"
        API[HTTP API<br/>Ktor :8080]
        SVC[OrderHistoryService]
        QB[QueryBuilder]
        CLIENT[DatastoreClient]
    end

    subgraph "Datastore"
        OS[(OpenSearch Cluster<br/>Bi-monthly indices)]
        REDIS[(Redis<br/>Score dedup cache)]
    end

    subgraph "Downstream (Read Path)"
        RECON[Order Recon Service]
        MERCHANT_DASH[Merchant Dashboard]
        WEBHOOK[Webhook Service]
        SETTLEMENT[Settlement Service]
        PAYMENT_SVC[Payment Services]
        DECISION[Decision Engine]
    end

    OMS -->|INSERT outbox| OUTBOX
    OUTBOX -->|CDC| DEBEZIUM
    DEBEZIUM --> KAFKA
    OMS -->|Direct publish| KAFKA
    KAFKA --> FIREHOSE
    FIREHOSE -->|PUT /orders/save| API

    API --> SVC --> QB --> CLIENT --> OS
    SVC --> REDIS
    SVC -->|Score update| DECISION

    RECON -->|POST /filter/scroll| API
    MERCHANT_DASH -->|GET /orders/{id}/detailed| API
    WEBHOOK -->|GET order| API
    SETTLEMENT -->|POST /aggregate| API
    PAYMENT_SVC -->|POST /filter| API
```

## Quick Reference: API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/pay/v1/orders/{orderId}/detailed` | Merchant-facing order details |
| GET | `/api/internal/v1/orders/{id}/detailed` | Internal order details |
| PUT | `/api/internal/v1/orders/save` | Upsert order (from Firehose) |
| POST | `/api/internal/v1/orders/filter/{indexName?}` | Paginated filter search |
| POST | `/api/internal/v1/orders/filter/scroll/{indexName?}` | Scroll-based deep search |
| POST | `/api/internal/v1/orders/aggregate/{indexName?}` | Aggregation queries |
| PATCH | `/api/internal/v1/orders/acquirer-score` | Update acquirer gateway score |
| POST | `/api/internal/v1/orders/create-index/{dateStamp}` | Create new partition index |
| POST | `/api/internal/v1/orders/update-aliases` | Rotate rolling aliases |
| POST | `/api/internal/v1/orders/delete-by-query/{indexName}` | Cleanup old data |
| POST | `/api/internal/v1/orders/raw-search` | Raw OpenSearch pass-through |

## Quick Reference: Index Naming

```
orders_v2                    ← Legacy flat index (deprecated, read-only)
orders_v2-2024011           ← Jan 2024, days 1-15
orders_v2-2024012           ← Jan 2024, days 16-31
orders_v2-2024021           ← Feb 2024, days 1-15
orders_v2-2024022           ← Feb 2024, days 16-28
orders_v2_read               ← Read alias (points to recent partitions)
orders_v2_recon_alias        ← Rolling alias for recon service (28-day window)
```
