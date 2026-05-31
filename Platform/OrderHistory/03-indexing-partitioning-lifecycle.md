# 03 — Indexing, Partitioning & Lifecycle

## Overview

The Order History Service uses **time-based bi-monthly index partitioning** — each ~15-day window gets its own OpenSearch index. This strategy enables:
- Controlled shard sizes (avoid giant indices)
- Efficient data lifecycle (drop old indices without reindexing)
- Rolling alias management for recon service queries
- Zero-downtime schema migrations

## Partitioning Scheme

### Index Naming Convention

```
orders_v2-{YYYY}{MM}{PP}

Where:
  YYYY = 4-digit year
  MM   = 2-digit month (01-12)
  PP   = partition within month:
         01 = days 1-15
         02 = days 16-31
```

**Examples:**
```
orders_v2-20240101  →  January 2024, days 1-15
orders_v2-20240102  →  January 2024, days 16-31
orders_v2-20240201  →  February 2024, days 1-15
orders_v2-20240202  →  February 2024, days 16-28
orders_v2-20241201  →  December 2024, days 1-15
orders_v2-20241202  →  December 2024, days 16-31
```

### Partition Derivation from OrderId

Order IDs embed their creation date:

```
Format: {prefix}-{yyMMdd}-{random}
Example: pay-240615-abc123def456
                ↑
         yy=24, MM=06, dd=15
         → Year: 2024, Month: 06, Day: 15
         → Day 15 ≤ 15, so partition = 01
         → Index: orders_v2-20240601
```

```kotlin
// Utils.kt — Index name derivation
fun getIndexNameFromOrderId(orderId: String): String {
    val datePart = orderId.split("-")[1]  // "240615"
    val yy = datePart.substring(0, 2)    // "24"
    val mm = datePart.substring(2, 4)    // "06"
    val dd = datePart.substring(4, 6)    // "15"

    val partition = if (dd.toInt() <= 15) "01" else "02"
    return "orders_v2-20${yy}${mm}${partition}"
}
```

### Partition Timeline Visualization

```mermaid
gantt
    title Index Partitions (2024 Q3 Example)
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section July 2024
    orders_v2-20240701 :j1, 2024-07-01, 15d
    orders_v2-20240702 :j2, 2024-07-16, 16d

    section August 2024
    orders_v2-20240801 :a1, 2024-08-01, 15d
    orders_v2-20240802 :a2, 2024-08-16, 16d

    section September 2024
    orders_v2-20240901 :s1, 2024-09-01, 15d
    orders_v2-20240902 :s2, 2024-09-16, 15d
```

**~24 indices per year** (2 per month × 12 months)

## Alias Management

### Alias Types

| Alias | Purpose | Rolling Window |
|-------|---------|----------------|
| `orders_v2_read` | General read queries (merchant dashboard, get-order) | All active indices |
| `orders_v2_recon_alias` | Recon service queries (time-bounded) | Last 28 days + 10 days future |

### Rolling Recon Alias

The recon alias covers a **38-day window** (28 days back + 10 days forward):

```
REMOVE_OFFSET_DAYS = -28  (remove indices older than 28 days)
ADD_OFFSET_DAYS    = +10  (add indices up to 10 days in the future)
```

```mermaid
flowchart LR
    subgraph "Today: July 20, 2024"
        REMOVE["Remove from alias:<br/>indices before June 22<br/>(orders_v2-20240601)"]
        KEEP["Keep in alias:<br/>June 22 → July 30<br/>(orders_v2-20240602<br/>orders_v2-20240701<br/>orders_v2-20240702)"]
        ADD["Add to alias:<br/>up to July 30<br/>(orders_v2-20240802 pre-created)"]
    end
```

### Alias Update API

```
POST /api/internal/v1/orders/update-aliases
```

This endpoint (called by a cron job) performs atomic alias rotation:

```mermaid
sequenceDiagram
    participant Cron as External Cron
    participant OHS as Order History Service
    participant OS as OpenSearch

    Cron->>OHS: POST /update-aliases

    OHS->>OHS: Calculate date range:<br/>today - 28d → today + 10d
    OHS->>OHS: Derive index names for range<br/>(typically 3-5 indices)

    OHS->>OS: POST /_aliases<br/>{actions: [<br/>  {remove: {index: "orders_v2-20240601", alias: "orders_v2_recon_alias"}},<br/>  {add: {index: "orders_v2-20240802", alias: "orders_v2_recon_alias"}}<br/>]}

    OS-->>OHS: 200 OK (atomic swap)
```

### Alias Configuration

```yaml
orderHistoryConfigs:
  rollingIndexAlias: "orders_v2_recon_alias"
```

## Index Creation

### Pre-Creation Strategy

New indices are created **before** they're needed (via the `ADD_OFFSET_DAYS = 10` lookahead):

```mermaid
sequenceDiagram
    participant Cron as External Cron
    participant OHS as Order History Service
    participant OS as OpenSearch

    Note over Cron: Runs daily

    Cron->>OHS: POST /create-index/20240801

    OHS->>OHS: Load order_index_mapping.json<br/>(settings + mappings)

    OHS->>OS: PUT /orders_v2-20240801<br/>{settings: {...}, mappings: {...}}

    alt Index already exists
        OS-->>OHS: 400 resource_already_exists
        OHS-->>Cron: 200 (idempotent)
    else Created
        OS-->>OHS: 200 acknowledged
        OHS-->>Cron: 201 Created
    end
```

### Index Settings (from order_index_mapping.json)

```json
{
  "settings": {
    "index": {
      "number_of_shards": 1,
      "number_of_replicas": 1
    },
    "analysis": {
      "analyzer": {
        "default": { "type": "keyword" }
      }
    }
  },
  "mappings": {
    "properties": {
      "order_id": { "type": "keyword" },
      "payments": {
        "type": "nested",
        "properties": { ... }
      }
      // ... full mapping
    }
  }
}
```

## Dual-Write Migration

### Migration Phases

The service migrated from a single flat index (`orders_v2`) to partitioned nested indices without downtime:

```mermaid
stateDiagram-v2
    [*] --> Phase1: Before dualWriteEnableDate

    state Phase1 {
        [*] --> OldOnly
        OldOnly: Write to orders_v2 only
        OldOnly: Read from orders_v2 only
    }

    Phase1 --> Phase2: dualWriteEnableDate reached

    state Phase2 {
        [*] --> DualWrite
        DualWrite: Write to BOTH orders_v2 AND orders_v2-YYYYMMPP
        DualWrite: Read from new index (fallback to old)
        DualWrite: New index failure is NON-FATAL
    }

    Phase2 --> Phase3: dualWriteDisableDate reached

    state Phase3 {
        [*] --> NewOnly
        NewOnly: Write to orders_v2-YYYYMMPP ONLY
        NewOnly: Read from new index (fallback to old for historical)
        NewOnly: New index failure is FATAL
    }

    Phase3 --> [*]
```

### Write Routing Logic

```kotlin
fun upsertOrderRequest(order: Order): WriteDecision {
    val orderDate = getDateFromOrderId(order.id)

    return when {
        // Old-world order (before migration)
        orderDate < dualWriteEnableDate -> {
            WriteDecision.OLD_ONLY  // Write to orders_v2
        }
        // During dual-write window
        orderDate in dualWriteEnableDate..dualWriteDisableDate -> {
            WriteDecision.DUAL_WRITE  // Write to both; new index failure = non-fatal
        }
        // After dual-write (new world)
        else -> {
            WriteDecision.NEW_ONLY  // Write to partition only; failure = fatal
        }
    }
}
```

### Read Routing Logic

```mermaid
flowchart TD
    QUERY[Incoming query] --> HAS_INDEX{Explicit indexName<br/>specified?}

    HAS_INDEX -->|Yes| USE_EXPLICIT[Use specified index]
    HAS_INDEX -->|No| CHECK_PIVOT{System past<br/>pivot date?}

    CHECK_PIVOT -->|No| USE_OLD[Query orders_v2<br/>(flat, legacy)]
    CHECK_PIVOT -->|Yes| USE_ALIAS[Query orders_v2_recon_alias<br/>(nested, partitioned)]

    USE_ALIAS --> RESULT{Results found?}
    RESULT -->|Yes| RETURN[Return results]
    RESULT -->|No/Error| FALLBACK[Fallback to orders_v2]
    FALLBACK --> RETURN
```

## External Versioning (Optimistic Concurrency)

### Problem: Out-of-Order Events

CDC events can arrive out of order due to:
- Kafka partition rebalancing
- Firehose retry/DLQ replay
- Dual-topic (outbox + update) race conditions

### Solution: External Version Type

```
POST /orders_v2-20240701/_doc/pay-240701-abc123?version=5&version_type=external
```

OpenSearch's external versioning guarantees:
- If document's stored version >= request version → **409 Conflict** (rejected)
- If document's stored version < request version → **200 OK** (accepted)

```mermaid
sequenceDiagram
    participant Firehose as Firehose
    participant OHS as OHS
    participant OS as OpenSearch

    Note over OS: Document: orderId=abc, version=3

    Firehose->>OHS: Event: order version=5 (payment captured)
    OHS->>OS: PUT /_doc/abc?version=5&version_type=external
    OS-->>OHS: 200 OK (5 > 3, accepted)
    Note over OS: Document updated, version=5

    Firehose->>OHS: Event: order version=4 (stale, from outbox topic)
    OHS->>OS: PUT /_doc/abc?version=4&version_type=external
    OS-->>OHS: 409 Conflict (4 < 5, rejected)
    Note over OS: Document unchanged, version=5

    OHS-->>Firehose: 400 ORDER_ALREADY_UPDATED
    Firehose->>Firehose: Route to DLQ (expected, not an error)
```

### Version Increment in OMS

The OMS uses database-level optimistic locking with a `version` column:
```sql
UPDATE orders SET status='PROCESSED', version=version+1
WHERE id='abc' AND version=4;
```

Every state change increments the version, which flows through CDC to OHS.

## Index Lifecycle

### Capacity Planning

| Metric | Value |
|--------|-------|
| Orders per day | ~500,000–1,000,000 |
| Avg document size | ~4 KB |
| Index size (15 days) | ~30–60 GB |
| Total active indices | ~5–6 (recon alias) |
| Total historical indices | ~48 (2 years retained) |
| Shard count per index | 1 primary + 1 replica |

### Data Retention

```mermaid
flowchart LR
    CREATE[Create index<br/>10 days ahead] --> ACTIVE[Active writes<br/>15 days]
    ACTIVE --> RECON[In recon alias<br/>28 days]
    RECON --> COLD[Read-only<br/>historical queries]
    COLD --> DELETE[Delete index<br/>after retention policy]
```

| Phase | Duration | Status |
|-------|----------|--------|
| Pre-created | Up to 10 days before first write | Empty, in alias |
| Active | 15 days (bi-monthly window) | Receiving writes |
| Recon window | 28 days after last write | In recon alias, queryable |
| Historical | Varies (months to years) | Read-only, queryable by explicit name |
| Deleted | After retention policy | Removed from cluster |

### Index Health Monitoring

| Check | Alert Condition |
|-------|-----------------|
| Shard size > 50 GB | P2 — Consider splitting |
| Unassigned shards > 0 | P1 — Cluster capacity issue |
| Index creation failure | P1 — Pre-creation cron failed |
| Alias has 0 indices | P1 — Recon queries will fail |
| Version conflict rate > 10% | P2 — Event ordering degradation |
