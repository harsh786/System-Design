# Affordability Platform - Offer Optimization Engine

## 1. Offer Discovery & Matching Algorithm

The EMI offer discovery engine is the most computationally intensive path in the system. It determines which EMI offers are available for a given transaction context.

### 1.1 Offer Resolution Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OFFER RESOLUTION PIPELINE                              │
│                                                                          │
│  INPUT: { client, products, amount, issuer, BIN, tenure, channel }      │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 1: CLIENT RESOLUTION                                          │ │
│  │  • Lookup client by external_id + type + channel + tenant          │ │
│  │  • Get client_group_map → client_group_ids                         │ │
│  │  • Get enabled program_types (client_program_map)                  │ │
│  │  • Get client-specific cache TTL                                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 2: OFFER LOOKUP (Parallel - 4 sources)                        │ │
│  │                                                                    │ │
│  │  Source A: ISSUER OFFERS                                           │ │
│  │    SELECT * FROM offer_parameters op                               │ │
│  │    JOIN client_issuer_offer_association cioa                        │ │
│  │      ON cioa.offer_id = op.offer_id                                │ │
│  │    WHERE cioa.client_group_id IN (:clientGroupIds)                 │ │
│  │      AND op.status = 'A'                                           │ │
│  │      AND offer.state = 'APPROVED'                                  │ │
│  │      AND NOW() BETWEEN offer.start_date AND offer.end_date         │ │
│  │                                                                    │ │
│  │  Source B: PRODUCT OFFERS                                          │ │
│  │    SELECT * FROM offer_parameters op                               │ │
│  │    JOIN product_offer_association poa ON poa.offer_id = op.offer_id│ │
│  │    WHERE poa.product_id IN (:productIds)                           │ │
│  │      AND NOW() BETWEEN poa.start_date AND poa.end_date            │ │
│  │                                                                    │ │
│  │  Source C: BUNDLE OFFERS                                           │ │
│  │    SELECT * FROM offer_parameters op                               │ │
│  │    JOIN bundle_offer_map bom ON bom.offer_id = op.offer_id         │ │
│  │    JOIN bundle_product_map bpm ON bpm.bundle_id = bom.bundle_id    │ │
│  │    WHERE bpm.product_id IN (:productIds)                           │ │
│  │    GROUP BY bom.bundle_id                                          │ │
│  │    HAVING COUNT(*) = (SELECT COUNT(*) FROM bundle_product_map      │ │
│  │                        WHERE bundle_id = bom.bundle_id)            │ │
│  │                                                                    │ │
│  │  Source D: SKU_ALL OFFERS (applies to any product)                 │ │
│  │    Client-level offers with no product restriction                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 3: ISSUER EMI CONFIG MATCHING                                 │ │
│  │                                                                    │ │
│  │  For each offer_parameter, find matching issuer_emi_config:        │ │
│  │    WHERE issuer_id IN (:eligible_issuers)                          │ │
│  │      AND tenure_id IN (:offer_tenures)                             │ │
│  │      AND program_type = :program_type                              │ │
│  │      AND channel = :channel                                        │ │
│  │      AND min_amount <= :txn_amount <= max_amount                   │ │
│  │      AND (brand_id IS NULL OR brand_id = :brand_id)                │ │
│  │      AND (client_group_id IS NULL OR client_group_id IN (:groups)) │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 4: BIN RANGE FILTERING                                        │ │
│  │                                                                    │ │
│  │  If BIN provided:                                                  │ │
│  │    • Redis ZRANGEBYSCORE bin_range {bin_number} {bin_number}        │ │
│  │    • Match to bin_range_group → issuer                             │ │
│  │    • Apply bin_group_issuer_offer ROI overrides                    │ │
│  │    • Apply bin exclusions (issuer_bin_exclusion)                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 5: TEMPORAL FILTERING                                         │ │
│  │                                                                    │ │
│  │  • Check applicable_days_bitmap (Mon=1, Tue=2, ..., Sun=7)        │ │
│  │  • Check start_hour <= current_hour <= end_hour                    │ │
│  │  • Check start_date <= now <= end_date                             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 6: AMOUNT RANGE FILTERING                                     │ │
│  │                                                                    │ │
│  │  • offer_parameters.min_amount <= txn_amount <= max_amount         │ │
│  │  • issuer_emi_config.min_amount <= txn_amount <= max_amount        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 7: VELOCITY VALIDATION                                        │ │
│  │                                                                    │ │
│  │  • If card_hash provided: check CARD_HASH velocity                 │ │
│  │  • If phone provided: check MOBILE_NUMBER velocity                 │ │
│  │  • Check combined velocity cap                                     │ │
│  │  • Exclude offers where customer hit velocity limit                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Step 8: EMI CALCULATION (per eligible issuer × tenure)             │ │
│  │                                                                    │ │
│  │  For each (issuer, tenure, offer):                                 │ │
│  │    1. Get ROI from issuer_emi_config (or bin_group override)       │ │
│  │    2. Calculate monthly EMI using reducing balance formula          │ │
│  │    3. Calculate total interest                                     │ │
│  │    4. Apply subvention (multi-party, sequence-based)               │ │
│  │    5. Apply discount (multi-party, sequence-based)                 │ │
│  │    6. Calculate processing fee (with min/max bounds)               │ │
│  │    7. Calculate net payment (auth) amount                          │ │
│  │    8. Apply split EMI (if configured)                              │ │
│  │    9. Calculate down payment (if applicable)                       │ │
│  │   10. Resolve offer code (for acquirer communication)              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                          │                                               │
│                          ▼                                               │
│  OUTPUT: List<IssuerOfferDetails> grouped by issuer → tenures           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Offer Code Resolution

Offer codes are bank-specific scheme identifiers passed to acquirers during payment authorization.

### 2.1 Offer Code Matching Logic

```
issuer_emi_offer_code_config:
  ┌─────────────────────────────────────────────────────────────────┐
  │ issuer_id | tenure_id | program_type | offer_code | priority    │
  │───────────┼───────────┼──────────────┼────────────┼─────────────│
  │ 101 (HDFC)│ 3 months  │ BANK_EMI     │ HDFC3MNCE  │ 1           │
  │ 101 (HDFC)│ 6 months  │ BANK_EMI     │ HDFC6MNCE  │ 1           │
  │ 101 (HDFC)│ 12 months │ BRAND_EMI    │ HDFCBRD12  │ 1           │
  └─────────────────────────────────────────────────────────────────┘

issuer_program_offer_code_criteria:
  ┌──────────────────────────────────────────────────────────────────┐
  │ issuer_id | program_type | criteria         | offer_code_prefix  │
  │───────────┼──────────────┼──────────────────┼────────────────────│
  │ 101       │ BANK_EMI     │ ROI_BASED        │ HDFC_EMI_          │
  │ 101       │ BRAND_EMI    │ SUBVENTION_BASED │ HDFC_BRD_          │
  └──────────────────────────────────────────────────────────────────┘
```

### 2.2 Code Selection Priority
1. Exact match: issuer + tenure + program_type + brand (if applicable)
2. Partial match: issuer + tenure + program_type (any brand)
3. Criteria-based: issuer + program_type with ROI/subvention criteria
4. Default: No offer code (standard bank EMI)

---

## 3. Multi-Product Offer Resolution

For carts with multiple products, the engine uses a more complex resolution:

### 3.1 Single Product vs Multi-Product Strategy

```java
// Strategy selection based on product count
if (productDetails.size() == 1) {
    return applicationContext.getBean("EMI_SINGLE_PRODUCT_OFFER_SERVICE");
} else {
    return applicationContext.getBean("EMI_MULTI_PRODUCT_OFFER_SERVICE");
}
```

### 3.2 Multi-Product Resolution Rules

```
For N products in cart:
  1. Find offers applicable to each individual product
  2. Find bundle offers (all products in cart match a bundle)
  3. Find SKU_ALL offers (apply to any product combination)
  
  Intersection logic:
  • Issuer offers: Apply to entire cart (amount = sum of all products)
  • Product offers: Only valid if txn contains that specific product
  • Bundle offers: Only valid if ALL bundle products are in cart
  
  Amount distribution:
  • Subvention calculated on total cart amount
  • Per-product ledger entries track individual product amounts
  • Product-level offers apply proportionally to product's share of cart
```

---

## 4. Subvention Recalculation

When subvention amounts are below a threshold, the system recalculates to avoid micro-amounts:

```java
// EmiCalculatorUtil.java
if (subventionAmount < subventionRecalculationThreshold) {
    // subvention.recalculation.threshold.amount = 2500 (paisa = Rs.25)
    // Below threshold: round to 0 (no subvention applied)
    // Prevents micro-subventions that cost more to settle than they're worth
    subventionAmount = 0;
    emiType = "STANDARD_EMI";  // Downgrade from NO_COST to standard
}
```

---

## 5. Budget Optimization

### 5.1 Budget Alert Thresholds

```java
// Budget health monitoring with configurable thresholds
budget.healthy.criteria=50      // < 50% consumed = HEALTHY (green)
budget.moderate.criteria=50_80  // 50-80% consumed = MODERATE (yellow, alert)
budget.critical.criteria=80     // > 80% consumed = CRITICAL (red, urgent alert)

// Margin tracking for proactive alerts
budget.margin.rate.one=0.5     // First alert at 50% of remaining
budget.margin.rate.two=0.2     // Second alert at 80% of remaining
budget.margin.rate.three=0.1   // Third alert at 90% of remaining
budget.margin.max.amount.one=1000000   // Rs.10,000
budget.margin.max.amount.two=500000    // Rs.5,000
budget.margin.max.amount.three=100000  // Rs.1,000
```

### 5.2 Budget Enforcement Strategy

```
┌─────────────────────────────────────────────────────────────┐
│              BUDGET ENFORCEMENT DECISION TREE                 │
│                                                              │
│  is_threshold_breach_restricted = TRUE?                      │
│  ├── YES: Hard block                                        │
│  │   └── consumed + new_amount > threshold → REJECT txn     │
│  │                                                          │
│  └── NO: Soft tracking (allow but track)                    │
│      └── consumed + new_amount > threshold → ALLOW + ALERT  │
│                                                              │
│  is_global_budget_applicable = TRUE?                         │
│  ├── YES: Check global budget across all campaigns           │
│  └── NO: Check per-campaign budget only                     │
│                                                              │
│  Per-party tracking:                                         │
│  ├── threshold_subvention_amount vs consumed_subvention     │
│  ├── threshold_discount_amount vs consumed_discount          │
│  └── threshold_amount (total) vs total_consumed             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Velocity Optimization

### 6.1 Velocity Check Performance

The velocity system is designed for sub-millisecond checks:

```
Key insight: Velocity is checked DURING offer discovery (ReadServ)
to exclude offers where customer has hit the limit.

This means velocity validation runs on EVERY EMI discovery request
(high-frequency path) and must be extremely fast.

Optimization:
1. Velocity rules loaded in-memory (ConcurrentHashMap)
2. Transaction counts maintained in Redis (atomic INCR/DECR)
3. Window-based expiry (EXPIRE on velocity counter keys)
4. Batch validation: Check all applicable rules in single Redis MGET
```

### 6.2 Velocity Rule Types

| Type | Identifier | Use Case |
|------|-----------|----------|
| CARD_HASH | SHA-256 of card PAN | Prevent repeated use of same card |
| MOBILE_NUMBER | Customer phone | Prevent repeated cardless EMI claims |
| CARDLESS | Cardless issuer reference | Limit cardless EMI frequency |

### 6.3 Frequency Windows

| Frequency | Window | Example |
|-----------|--------|---------|
| DAILY | 00:00 - 23:59 (IST) | Max 1 no-cost EMI per card per day |
| WEEKLY | Monday 00:00 - Sunday 23:59 | Max 3 brand EMIs per week |
| MONTHLY | 1st 00:00 - last day 23:59 | Max 5 subvention claims per month |
| CAMPAIGN | Campaign start_date - end_date | Max 2 per campaign lifetime |

---

## 7. Performance Benchmarks

### 7.1 Offer Discovery Latency Breakdown

| Step | P50 | P95 | P99 | Notes |
|------|-----|-----|-----|-------|
| Cache key generation (SHA-256) | <1ms | <1ms | <1ms | CPU-bound |
| Redis GET (compressed) | 2ms | 5ms | 10ms | Network + decompress |
| Client lookup (cached) | 1ms | 3ms | 5ms | Redis or in-memory |
| Offer parameters query | 10ms | 30ms | 50ms | Native SQL, indexed |
| Issuer EMI config (cached) | 2ms | 5ms | 10ms | Redis |
| BIN range lookup | 1ms | 2ms | 5ms | Redis sorted set |
| EMI calculation (per tenure) | <1ms | <1ms | <1ms | Pure math |
| Response serialization | 2ms | 5ms | 10ms | JSON + GZIP |
| **Total (cache HIT)** | **5ms** | **15ms** | **30ms** | Redis only |
| **Total (cache MISS)** | **50ms** | **150ms** | **300ms** | DB + compute |

### 7.2 Transaction API Latency

| Operation | P50 | P95 | P99 | Notes |
|-----------|-----|-----|-----|-------|
| Create Payment | 20ms | 50ms | 100ms | DB insert only |
| Pre-Payment (all tasks) | 100ms | 300ms | 500ms | 3 external calls |
| Complete Payment | 50ms | 150ms | 300ms | EMI calc + ledger insert |
| Settle Payment | 30ms | 80ms | 150ms | DB update + Kafka |
| Void Payment | 40ms | 100ms | 200ms | Reverse tasks |
| Refund Payment | 50ms | 120ms | 250ms | Reverse + new ledger |

---

## 8. Scalability Design

### 8.1 Horizontal Scaling Points

```
┌──────────────────────────────────────────────────────────────────┐
│               SCALING STRATEGY BY SERVICE                          │
│                                                                   │
│  ReadServ (Stateless, CPU-bound):                                │
│  ├── Scale by: CPU utilization (target: 60%)                     │
│  ├── Min replicas: 3                                             │
│  ├── Max replicas: 20                                            │
│  └── Bottleneck: DB read replicas, Redis connections             │
│                                                                   │
│  TransactionServ (Stateless, I/O-bound):                         │
│  ├── Scale by: Request rate                                      │
│  ├── Min replicas: 3                                             │
│  ├── Max replicas: 15                                            │
│  └── Bottleneck: DB writer (single instance), external calls     │
│                                                                   │
│  Gateway Adapter (Stateless, Network-bound):                     │
│  ├── Scale by: Connection count                                  │
│  ├── Min replicas: 3                                             │
│  ├── Max replicas: 10                                            │
│  └── Bottleneck: Downstream service capacity                     │
│                                                                   │
│  CacheManagement (Single-leader, Background):                    │
│  ├── Scale: NOT horizontally (single writer for consistency)     │
│  ├── Replicas: 1 (with distributed lock safety)                  │
│  └── Bottleneck: Redis SCAN operations                           │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Database Scaling

```
PostgreSQL:
  Writer: 1 instance (r5.2xlarge) — all writes, DDL
  Readers: 3-5 instances (r5.xlarge) — all reads via round-robin
  
  Connection budget:
    ReadServ: 100 connections × 3 pods = 300 per replica
    Total across 5 replicas: 1500 connections (within PG max_connections=2000)

Redis (ElastiCache):
  Mode: Cluster (3 shards × 2 replicas)
  Total memory: 32GB per shard = 96GB cluster
  Max connections: 65,000 per node
```
