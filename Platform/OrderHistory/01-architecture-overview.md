# 01 — Architecture Overview

## System Context

The Order History Service is a **CQRS read model** — a materialized view optimized for queries, fed by CDC events from the transactional OMS database. It bridges the gap between the write-optimized PostgreSQL store (OMS) and the diverse read patterns needed by merchant dashboards, reconciliation, settlement, and analytics.

```mermaid
C4Context
    title Order History Service — System Context

    System(ohs, "Order History Service", "Read-optimized OpenSearch store\nfor order/payment queries")

    System_Ext(oms, "OMS (nxt-payments-service)", "Transactional order management\nPostgreSQL write store")
    System_Ext(cdc, "Debezium CDC", "Captures outbox changes\nPublishes to Kafka")
    System_Ext(firehose, "GoTo Firehose", "Kafka HTTP sink connector\nBatches and delivers events")
    System_Ext(os, "OpenSearch Cluster", "Distributed search engine\nBi-monthly partitioned indices")
    System_Ext(redis, "Redis ElastiCache", "Score dedup cache")
    System_Ext(decision, "Decision Engine", "Acquirer gateway scoring\nRust/Axum service")

    Rel(oms, cdc, "Outbox CDC", "PostgreSQL WAL")
    Rel(cdc, firehose, "Kafka events", "Protobuf")
    Rel(firehose, ohs, "HTTP batch push", "PUT /orders/save")
    Rel(ohs, os, "Index/Query", "REST API")
    Rel(ohs, redis, "Score dedup", "Redisson")
    Rel(ohs, decision, "Score updates", "HTTP")
```

## Component Architecture

```mermaid
graph TB
    subgraph "Order History Service"
        subgraph "API Layer"
            MERCHANT_API["Merchant API<br/>GET /api/pay/v1/orders/{id}/detailed"]
            INTERNAL_API["Internal API<br/>POST /filter, /scroll, /aggregate<br/>PUT /save, PATCH /score"]
            DOWNTIME_API["Downtime API<br/>POST /downtime/unscheduled"]
            HEALTH["Health Checks<br/>GET /health/live, /health/ready"]
        end

        subgraph "Service Layer"
            OHS_SVC[OrderHistoryService<br/>Query routing, dual-index logic]
            IDX_SVC[OrderHistoryIndexService<br/>Index creation/migration]
            DT_SVC[DowntimeService<br/>Error rate monitoring]
            LOCK_SVC[LockService<br/>Distributed locking via Redis]
        end

        subgraph "Query Engine"
            QB[OrderHistoryQueryBuilder<br/>Flat vs Nested DSL construction]
        end

        subgraph "Data Access"
            DS_CLIENT[OrderHistoryDatastoreClient<br/>OpenSearch HTTP + Circuit Breaker]
            DECISION_CLIENT[DecisionEngineClient<br/>Score updates]
            DT_CLIENT[DowntimeSchedulerClient<br/>Downtime reporting]
        end
    end

    MERCHANT_API --> OHS_SVC
    INTERNAL_API --> OHS_SVC
    INTERNAL_API --> IDX_SVC
    DOWNTIME_API --> DT_SVC

    OHS_SVC --> QB
    OHS_SVC --> DS_CLIENT
    OHS_SVC --> DECISION_CLIENT
    OHS_SVC --> LOCK_SVC

    DS_CLIENT --> OS[(OpenSearch)]
    DECISION_CLIENT --> DE[Decision Engine]
    DT_CLIENT --> DTS[Downtime Scheduler]
    LOCK_SVC --> REDIS[(Redis)]
```

## Layered Architecture

| Layer | Responsibility | Key Classes |
|-------|---------------|-------------|
| **API** | HTTP endpoint definitions, request validation, response mapping | `OrderHistoryRoutes`, `InternalRoutes`, `DowntimeRoutes` |
| **Service** | Business logic, routing decisions, dual-index management | `OrderHistoryService`, `OrderHistoryIndexService`, `DowntimeService` |
| **Query Engine** | OpenSearch DSL construction (flat vs nested variants) | `OrderHistoryQueryBuilder` |
| **Data Access** | OpenSearch HTTP client, circuit breaker, versioning | `OrderHistoryDatastoreClient` |
| **Configuration** | DI wiring, Hoplite config, feature flags | `OrderHistoryServiceConfigs`, `Dependencies` |

## Deployment Topology

```mermaid
graph TB
    subgraph "EKS Cluster (ap-south-1)"
        subgraph "Namespace: nxt-order-history-service"
            POD1[OHS Pod 1<br/>:8080]
            POD2[OHS Pod 2<br/>:8080]
            POD3[OHS Pod 3<br/>:8080]
            SVC[K8s Service<br/>:80 → :8080]
            ING[Ingress<br/>nginx-internal]
        end
    end

    subgraph "Firehose (Write Path)"
        FH1[order-http-order-history-firehose<br/>Kafka → HTTP sink]
        FH2[order-http-order-history-update-firehose<br/>Kafka → HTTP sink]
        FH3[order-http-order-history-downtime-firehose<br/>Kafka → HTTP sink]
    end

    subgraph "OpenSearch (Managed)"
        OS_M[Master nodes x3]
        OS_D1[Data node 1]
        OS_D2[Data node 2]
        OS_D3[Data node 3]
    end

    subgraph "Redis (ElastiCache)"
        REDIS[Redis cluster<br/>:6379]
    end

    FH1 & FH2 & FH3 -->|PUT /save| ING
    ING --> SVC --> POD1 & POD2 & POD3
    POD1 & POD2 & POD3 --> OS_D1 & OS_D2 & OS_D3
    POD1 & POD2 & POD3 --> REDIS
```

## Data Flow: Write Path

```mermaid
sequenceDiagram
    participant OMS as OMS (PostgreSQL)
    participant Debezium as Debezium CDC
    participant Kafka as Kafka MSK
    participant Firehose as GoTo Firehose
    participant OHS as Order History Service
    participant OS as OpenSearch

    Note over OMS: Payment captured → order updated
    OMS->>OMS: INSERT INTO outbox (payload=Protobuf Order)

    Debezium->>Kafka: Capture outbox INSERT<br/>Topic: outbox.event.orders
    Note over OMS: Also direct publish on payment change
    OMS->>Kafka: Publish full Order<br/>Topic: update.event.orders

    Kafka->>Firehose: Consume batch
    Firehose->>OHS: PUT /api/internal/v1/orders/save<br/>[{logMessage: Order JSON}]

    OHS->>OHS: Parse Protobuf → determine index partition
    OHS->>OS: POST /orders_v2-YYYYMMPP/_doc/{orderId}<br/>?version=N&version_type=external
    OS-->>OHS: 200 Created / 409 Version Conflict

    alt Version conflict (stale event)
        OHS-->>Firehose: 400 ORDER_ALREADY_UPDATED
        Firehose->>Firehose: Route to DLQ
    else Success
        OHS-->>Firehose: 200 OK
    end
```

## Data Flow: Read Path

```mermaid
sequenceDiagram
    participant Client as Calling Service
    participant OHS as Order History Service
    participant QB as QueryBuilder
    participant OS as OpenSearch

    Client->>OHS: POST /orders/filter/scroll<br/>{filters, scrollSize, sort}

    OHS->>OHS: Resolve routing:<br/>old index or new partition?

    alt New partitioned index
        OHS->>QB: Build nested query<br/>(payments.* wrapped in nested block)
        QB-->>OHS: OpenSearch DSL (nested)
    else Old flat index
        OHS->>QB: Build flat query
        QB-->>OHS: OpenSearch DSL (flat)
    end

    OHS->>OS: POST /{index}/_search?scroll=5m
    OS-->>OHS: {hits, scroll_id, total}

    OHS->>OHS: Deserialize JSON → Protobuf Order[]
    OHS-->>Client: {orders, scrollId, hasMore, pagination}
```

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Datastore** | OpenSearch 2.16 | Full-text + structured queries, nested aggregations, scroll API, index lifecycle |
| **Ingestion** | GoTo Firehose (HTTP Sink) | Managed Kafka→HTTP bridge; handles retries, DLQ, batching without custom consumer code |
| **Serialization** | Protobuf (JSON-encoded) | Type-safe contract from OMS; stored as-is in OpenSearch (no transformation) |
| **Concurrency control** | External versioning | Out-of-order event arrival handled correctly; latest version always wins |
| **Index type** | Nested (for payments) | Accurate per-payment queries without cross-payment false matches |
| **Circuit breaker** | Arrow Resilience | Protects OpenSearch from cascading failures during cluster instability |
| **Migration strategy** | Dual-write | Zero-downtime migration; old index remains available during transition |

## Health & Observability

### Probes

| Probe | Endpoint | Port |
|-------|----------|------|
| Liveness | `/health/live` | 8080 |
| Readiness | `/health/ready` | 8080 |

### Key Metrics

| Metric | Purpose |
|--------|---------|
| `ohs.query.latency` | OpenSearch query response time |
| `ohs.upsert.latency` | Document indexing latency |
| `ohs.version_conflict.count` | Stale events (normal at low rate) |
| `ohs.circuit_breaker.state` | OpenSearch health indicator |
| `ohs.scroll.active` | Active scroll contexts |
| `ohs.downtime.detected` | Payment method downtime signals |

### Capacity & Limits

| Parameter | Value |
|-----------|-------|
| Max page size | 1,000 |
| Default page size | 10 |
| Scroll keep-alive | 5 minutes |
| Scroll batch size | 1,000 |
| HTTP timeout | 10 seconds |
| Connection pool | 600 max connections |
| Circuit breaker failures | 200 before OPEN |
