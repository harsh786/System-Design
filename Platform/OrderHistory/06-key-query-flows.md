# 06 — Key Query Flows & Diagrams

## Overview

This document provides detailed workflow diagrams for the most critical query flows in the platform — showing how different services use OHS and what queries they generate. These are the **hot paths** that handle the majority of OHS traffic.

---

## Flow 1: Recon Service — Discover Pending Orders (AUTHZ Scenario)

The reconciliation service's most frequent query: find orders stuck in AUTHENTICATED state.

### Query Generated

```json
{
  "query": {
    "bool": {
      "filter": [
        { "terms": { "type": ["CHARGE"] } },
        { "terms": { "status": ["PENDING", "CANCEL_REQUESTED"] } },
        {
          "nested": {
            "path": "payments",
            "query": {
              "bool": {
                "filter": [
                  { "terms": { "payments.status": ["AUTHENTICATED"] } },
                  { "range": { "payments.updated_at": {
                      "gte": "2024-06-15T10:25:00Z",
                      "lte": "2024-06-15T11:20:00Z"
                  }}}
                ]
              }
            }
          }
        }
      ]
    }
  },
  "sort": [{ "payments.created_at": { "order": "desc" } }],
  "size": 1000
}
```

### End-to-End Workflow

```mermaid
sequenceDiagram
    participant Cron as Recon Cron (AUTHZ)
    participant Recon as OrderReconService
    participant OHS as Order History Service
    participant OS as OpenSearch
    participant Redis as Redis (Dedup)
    participant SQS as SQS (sqs-authz)

    Note over Cron: Every 2 minutes

    Cron->>Recon: triggerSync(AUTHZ)
    Recon->>Recon: Build filters:<br/>type=CHARGE, status=[PENDING,CANCEL_REQUESTED]<br/>payments.status=AUTHENTICATED<br/>payments.updated_at=[now-60min, now-5min]

    Recon->>OHS: POST /filter/scroll/orders_v2_recon_alias<br/>{filters, scroll_size=1000, sort=payments.created_at DESC}

    OHS->>OHS: Detect index: orders_v2_recon_alias (nested)
    OHS->>OHS: Build nested query<br/>(payments.* filters wrapped in nested block)

    OHS->>OS: POST /orders_v2_recon_alias/_search?scroll=5m<br/>body={nested_query, size=1000}
    OS-->>OHS: {hits: [1000 orders], scroll_id="abc", total=3200}
    OHS-->>Recon: {orders[1000], scrollId="abc", hasMore=true, filtered=3200}

    loop Process each order
        Recon->>Redis: SET NX SQS:DEDUP:{orderId}:AUTHZ_RECON
        alt New (not deduped)
            Recon->>SQS: SendMessage(queue=sqs-authz, delay=30s)
        end
    end

    Recon->>OHS: POST /filter/scroll<br/>{scroll_id="abc"}
    OHS->>OS: POST /_search/scroll {scroll_id="abc"}
    OS-->>OHS: {hits: [1000], scroll_id="def"}
    OHS-->>Recon: {orders[1000], scrollId="def", hasMore=true}

    Note over Recon: ... continues until hasMore=false (3200 total) ...
```

### Query Characteristics

| Metric | Value |
|--------|-------|
| Result set size | 1,000–20,000 orders per run |
| Execution frequency | Every 2 minutes |
| Target index | `orders_v2_recon_alias` (28-day window) |
| Latency (initial scroll) | ~50-200ms |
| Latency (continue scroll) | ~20-50ms |

---

## Flow 2: Recon Service — Long-Pending Termination

Find orders that have been stuck for hours and need force-termination.

### Query Generated

```json
{
  "query": {
    "bool": {
      "filter": [
        { "terms": { "type": ["CHARGE"] } },
        { "terms": { "status": ["ATTEMPTED", "PENDING", "CANCEL_REQUESTED"] } },
        {
          "nested": {
            "path": "payments",
            "query": {
              "bool": {
                "filter": [
                  { "terms": { "payments.status": [
                      "INITIATED", "AUTHENTICATED", "AUTHENTICATION_CHALLENGED",
                      "CANCEL_REQUESTED", "CANCELLED", "FAILED"
                  ]}},
                  { "range": { "payments.updated_at": {
                      "lte": "2024-06-15T08:30:00Z"
                  }}}
                ]
              }
            }
          }
        }
      ]
    }
  },
  "sort": [{ "updated_at": { "order": "desc" } }],
  "size": 1000
}
```

### Workflow

```mermaid
sequenceDiagram
    participant Cron as Recon Cron (LONG_PENDING)
    participant Recon as OrderReconService
    participant OHS as Order History Service
    participant SQS as SQS (sqs-order-terminate)
    participant Kafka as Kafka (long-pending-orders)

    Cron->>Recon: triggerTerminate(LONG_PENDING)
    Recon->>OHS: POST /filter/scroll<br/>{type=CHARGE, status=[ATTEMPTED,PENDING,CANCEL_REQUESTED],<br/>payments.status=[INITIATED,...,FAILED],<br/>updated_at <= now-2h}

    OHS-->>Recon: Orders stuck > 2 hours

    loop For each order
        alt Order is a charge (non-refund)
            Recon->>Kafka: Publish to long-pending-orders
            Note over Kafka: OR enqueue to SQS<br/>(based on kafkaPercent)
        else Order is a refund
            Recon->>Kafka: Publish to long-pending-refund-orders
        end
    end
```

---

## Flow 3: Merchant Dashboard — Order History List

Merchant viewing their recent orders with filters.

### Query Generated

```json
{
  "query": {
    "bool": {
      "filter": [
        { "terms": { "merchant_id": ["M_SHOP_001"] } },
        { "terms": { "type": ["CHARGE"] } },
        { "range": { "created_at": { "gte": "2024-06-01", "lte": "2024-06-30" } } }
      ]
    }
  },
  "sort": [{ "created_at": { "order": "desc" } }],
  "from": 0,
  "size": 20
}
```

### Workflow

```mermaid
sequenceDiagram
    participant Merchant as Merchant Dashboard
    participant BFF as BFF Service
    participant OHS as Order History Service
    participant OS as OpenSearch

    Merchant->>BFF: GET /orders?page=1&status=PROCESSED&from=2024-06-01
    BFF->>OHS: POST /api/internal/v1/orders/filter<br/>{merchant_id=M_SHOP_001, type=CHARGE,<br/>status=[PROCESSED], created_at range, page_no=1, per_page=20}

    OHS->>OS: POST /orders_v2_recon_alias/_search<br/>{bool filter, from=0, size=20, sort=created_at desc}
    OS-->>OHS: {total=456, hits[20]}

    OHS-->>BFF: FilterResponse{orders[20], pagination:{total=456, page=1, hasMore=true}}
    BFF-->>Merchant: Order list (page 1 of 23)
```

---

## Flow 4: Get Order Status (Payment Service → OHS)

When a payment service needs to check the current state of an order.

### Workflow

```mermaid
sequenceDiagram
    participant PSP as Payment Service
    participant OHS as Order History Service
    participant OS as OpenSearch

    PSP->>OHS: GET /api/internal/v1/orders/pay-240615-abc123/detailed

    OHS->>OHS: Derive index from orderId:<br/>pay-240615-abc123 → 2024-06-15 → orders_v2-20240601

    OHS->>OS: GET /orders_v2-20240601/_doc/pay-240615-abc123
    OS-->>OHS: 200 {_source: {order_id, status, payments[...]}}

    OHS->>OHS: Parse JSON → Protobuf Order
    OHS-->>PSP: DetailedOrderResponse
```

### Direct Document Lookup Performance

| Metric | Value |
|--------|-------|
| Latency (p50) | ~2ms |
| Latency (p99) | ~10ms |
| Index routing | Direct to partition (no alias search) |

---

## Flow 5: Settlement Aggregation

Settlement service needs total captured/refunded amounts for a merchant in a period.

### Query Generated

```json
{
  "query": {
    "bool": {
      "filter": [
        { "terms": { "merchant_id": ["M_SHOP_001"] } },
        { "range": { "created_at": { "gte": "2024-06-01", "lte": "2024-06-30" } } }
      ]
    }
  },
  "size": 0,
  "aggs": {
    "captured_amount": {
      "nested": { "path": "payments" },
      "aggs": {
        "captured_filter": {
          "filter": { "term": { "payments.status": "CAPTURED" } },
          "aggs": {
            "total_amount": { "sum": { "field": "payments.amount.value" } }
          }
        }
      }
    },
    "refunded_amount": {
      "nested": { "path": "payments" },
      "aggs": {
        "refunded_filter": {
          "filter": { "term": { "payments.status": "REFUNDED" } },
          "aggs": {
            "total_amount": { "sum": { "field": "payments.amount.value" } }
          }
        }
      }
    }
  }
}
```

### Workflow

```mermaid
sequenceDiagram
    participant Settlement as Settlement Service
    participant OHS as Order History Service
    participant OS as OpenSearch

    Settlement->>OHS: POST /api/internal/v1/orders/aggregate<br/>{merchant_id=M_SHOP_001, date range}

    OHS->>OHS: Build nested aggregation query

    OHS->>OS: POST /orders_v2_recon_alias/_search<br/>body={query + aggs, size=0}
    OS-->>OHS: {<br/>  hits.total=12345,<br/>  aggregations: {<br/>    captured_amount.captured_filter.total_amount.value: 15000000,<br/>    refunded_amount.refunded_filter.total_amount.value: 500000<br/>  }<br/>}

    OHS-->>Settlement: AggregationResponse{<br/>  number_of_orders=12345,<br/>  captured_amount=15000000,<br/>  refunded_amount=500000<br/>}
```

---

## Flow 6: Back-Post Order Lookup (Recon → OHS)

When an acquirer sends a late callback, recon searches OHS by provider reference ID.

### Query Generated

```json
{
  "query": {
    "bool": {
      "filter": [
        {
          "nested": {
            "path": "payments",
            "query": {
              "bool": {
                "should": [
                  { "term": { "payments.provider_reference_id": "HDFC_TXN_789012" } },
                  { "term": { "payments.acquirer_details.rrn": "423456789012" } }
                ],
                "minimum_should_match": 1
              }
            }
          }
        }
      ]
    }
  },
  "sort": [{ "payments.created_at": { "order": "desc" } }],
  "size": 25
}
```

### Workflow

```mermaid
sequenceDiagram
    participant Acquirer as Acquirer (Late Callback)
    participant Recon as Order Recon Service
    participant OHS as Order History Service
    participant OS as OpenSearch
    participant OMS as OMS

    Acquirer->>Recon: POST /orders/back-post<br/>{providerRefId: "HDFC_TXN_789012", status: "CAPTURED"}

    Recon->>Recon: Map acquirer fields<br/>(BackPostRequestMapper)

    Recon->>OHS: POST /orders/filter<br/>{payments.provider_reference_id="HDFC_TXN_789012"<br/> OR payments.acquirer_details.rrn="423456789012"}

    OHS->>OS: POST /_search (nested query on payments)
    OS-->>OHS: Matching order(s)
    OHS-->>Recon: Order found: pay-240615-abc123

    Recon->>OMS: PUT /force-close/pay-240615-abc123<br/>{status: CAPTURED, rrn: "423456789012"}
    OMS-->>Recon: 200 (order force-closed)
```

---

## Flow 7: Recon — Refund Discovery

Find refund orders waiting for acquirer confirmation.

### Query Generated

```json
{
  "query": {
    "bool": {
      "filter": [
        { "terms": { "type": ["REFUND"] } },
        { "terms": { "status": ["PENDING"] } },
        {
          "nested": {
            "path": "payments",
            "query": {
              "bool": {
                "filter": [
                  { "terms": { "payments.status": ["CAPTURE_REQUESTED"] } },
                  { "range": { "payments.updated_at": {
                      "gte": "2024-06-15T09:30:00Z",
                      "lte": "2024-06-15T11:25:00Z"
                  }}}
                ]
              }
            }
          }
        }
      ]
    }
  },
  "sort": [{ "payments.created_at": { "order": "desc" } }],
  "size": 1000
}
```

### Workflow

```mermaid
sequenceDiagram
    participant Cron as Recon Cron (REFUND)
    participant OHS as Order History Service
    participant RMS as Refund Management Service

    Cron->>OHS: POST /filter/scroll<br/>{type=REFUND, status=PENDING,<br/>payments.status=CAPTURE_REQUESTED,<br/>payments.updated_at=[now-120min, now-5min]}

    OHS-->>Cron: Refund orders stuck > 5 min

    loop For each refund
        alt Direct recon (70%)
            Cron->>RMS: POST /reconcile/{orderId}
        else Kafka (30%)
            Cron->>Cron: Publish to recon-refunds topic
        end
    end
```

---

## Flow 8: Firehose Ingestion (Real-Time Indexing)

The most critical write flow — every order state change must be indexed.

```mermaid
sequenceDiagram
    participant OMS as OMS (PostgreSQL)
    participant Kafka as Kafka MSK
    participant Firehose as GoTo Firehose
    participant OHS as Order History Service
    participant OS as OpenSearch

    Note over OMS: Customer pays → payment CAPTURED

    par Outbox path
        OMS->>OMS: INSERT outbox (version=5)
        Note over OMS: Debezium captures...
        OMS-->>Kafka: outbox.event.orders (version=5)
    and Direct path
        OMS->>Kafka: update.event.orders (version=5)
    end

    Kafka->>Firehose: Batch consume (both topics)

    par Firehose #1 (outbox)
        Firehose->>OHS: PUT /orders/save [{logMessage: Order v5}]
    and Firehose #2 (update)
        Firehose->>OHS: PUT /orders/save [{logMessage: Order v5}]
    end

    Note over OHS: First arrival wins

    OHS->>OS: PUT /orders_v2-20240601/_doc/pay-240615-abc123<br/>?version=5&version_type=external
    OS-->>OHS: 200 OK (indexed)

    Note over OHS: Second arrival (same version)
    OHS->>OS: PUT /orders_v2-20240601/_doc/pay-240615-abc123<br/>?version=5&version_type=external
    OS-->>OHS: 409 Conflict (already at version 5)
    OHS-->>Firehose: 400 ORDER_ALREADY_UPDATED (→ DLQ, harmless)
```

---

## Flow 9: Index Lifecycle Management

Daily operations for partition management.

```mermaid
sequenceDiagram
    participant Cron as Daily Ops Cron
    participant OHS as Order History Service
    participant OS as OpenSearch

    Note over Cron: Create index for 10 days ahead
    Cron->>OHS: POST /create-index/20240725<br/>(today + 10 days)
    OHS->>OS: PUT /orders_v2-20240702<br/>{settings, mappings from order_index_mapping.json}
    OS-->>OHS: 200 acknowledged

    Note over Cron: Update recon alias (rolling 28-day window)
    Cron->>OHS: POST /update-aliases
    OHS->>OHS: Calculate: remove indices before today-28d<br/>Add indices up to today+10d

    OHS->>OS: POST /_aliases<br/>{actions: [<br/>  {remove: {index: "orders_v2-20240501", alias: "orders_v2_recon_alias"}},<br/>  {add: {index: "orders_v2-20240702", alias: "orders_v2_recon_alias"}}<br/>]}
    OS-->>OHS: 200 (atomic swap)
```

---

## Query Performance Summary

| Query Pattern | Latency (p50) | Latency (p99) | Frequency |
|---------------|---------------|---------------|-----------|
| Get by ID (direct) | 2ms | 10ms | ~50,000/min |
| Filter (paginated, page 1) | 10ms | 100ms | ~10,000/min |
| Filter (deep page >100) | 50ms | 500ms | ~100/min |
| Scroll (initial) | 50ms | 200ms | ~500/min |
| Scroll (continue) | 20ms | 50ms | ~5,000/min |
| Aggregation (nested) | 20ms | 200ms | ~100/min |
| Back-post search | 30ms | 150ms | ~50/min |
| Upsert (write) | 5ms | 50ms | ~10,000/min |

## Common Query Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Deep pagination (page 500+) | O(n) cost grows linearly | Use scroll API instead |
| Querying all indices | Shard fan-out overhead | Use alias or explicit index |
| Scripted aggregations | 33x slower than native | Use nested type + native aggs |
| Large result size (>1000) | Memory pressure | Use scroll with batches |
| Frequent get-by-id without partition hint | Searches all indices | Extract date from orderId → direct index |
| Range on `created_at` without merchant_id | Scans entire time window | Always include merchant_id for selectivity |
