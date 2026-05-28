# Aerospike: Fraud Detection + Balance Check — End to End

## 1. The Big Picture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        PAYMENT FLOW                                   │
│                                                                       │
│  User → Checkout API → Payment Service → Fraud Service → PSP/Bank   │
│                              │                  │                      │
│                              │         ┌────────┴────────┐            │
│                              │         │   AEROSPIKE     │            │
│                              │         │                 │            │
│                              │         │  Velocity       │            │
│                              │         │  Counters       │            │
│                              │         │  Risk Profile   │            │
│                              │         │  Idempotency    │            │
│                              │         │  Balance/Wallet │            │
│                              │         └─────────────────┘            │
│                              │                                        │
│                              └──→ Kafka → Analytics/Reporting         │
└─────────────────────────────────────────────────────────────────────┘
```

Aerospike serves as the real-time feature store and hot state engine.
It does NOT replace the ledger database (Postgres) or analytics (OpenSearch/ClickHouse).

---

## 2. Why Aerospike Fits This Use Case

| Requirement | Why Aerospike |
|---|---|
| p99 < 20ms for fraud decision | Sub-ms single-record reads, batch reads in 2-5ms |
| 100k+ TPS concurrent updates | Lock-free single-record atomicity, no row locks |
| Time-windowed counters | TTL auto-expires old buckets — zero maintenance |
| No cold-start per request | All data in RAM (or hybrid), no connection-per-query overhead |
| Hotspot resilience | Key-based partitioning distributes across cluster |
| Atomic counter updates | `operate` command combines read+modify+write in one network call |

---

## 3. Data Model — Fraud Velocity

### 3.1 Namespace and Sets

```text
namespace: risk (RAM + persistence on SSD)

Sets:
  account_velocity    → per-user attempt counters
  device_velocity     → per-device failure counters
  ip_velocity         → per-IP fanout counters
  card_velocity       → per-card amount counters
  account_profile     → static risk profile
  decision_guard      → idempotency records
  negative_list       → blocked entities
```

### 3.2 Key Design — Time-Bucketed Windows

Each counter lives in a time-bucketed key:

```text
Pattern:
  {entity}:{id}|metric:{name}|window:{duration}|bucket:{aligned_time}
```

Concrete examples:

```text
account 5-minute attempts:
  acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40

account 1-hour attempts:
  acct:u123|metric:pay_attempts|window:1h|bucket:2026-05-28T10

card daily amount:
  card:ch_98ab|metric:amount_attempted|day:2026-05-28

device 1-hour failures:
  device:d789|metric:failed_payments|window:1h|bucket:2026-05-28T10

IP 10-minute account fanout:
  ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40

account profile (no time bucket):
  acct:u123|profile

idempotency:
  risk_decision:req_7e1f
```

### 3.3 Bins (Columns) Per Record

Counter record bins:

```text
count          → number of attempts in this window
amount_sum     → total amount attempted in this window
failed_count   → failures specifically
approved_count → successes
last_seen_at   → timestamp of last event
```

Profile record bins:

```text
risk_tier            → LOW / MEDIUM / HIGH
kyc_status           → VERIFIED / PENDING / FAILED
account_age_days     → days since account creation
chargeback_count_90d → chargebacks in last 90 days
trusted_device_count → number of trusted devices
last_good_payment_at → timestamp of last successful payment
```

---

## 4. Why Bucketing Is Required

### 4.1 The Problem Without Buckets

```text
Single counter approach (WRONG):
  key: acct:u123|metric:pay_attempts
  bins: { count: 847 }

Questions you CANNOT answer:
  - How many in last 5 minutes? → Unknown, counter is cumulative
  - When to reset? → Need a background job
  - What if the reset job crashes? → Stale data
  - What about concurrent resets? → Race condition
  - What if you want both 5m AND 1h windows? → Impossible with one counter
```

### 4.2 What Bucketing Solves

```text
Bucketed approach (CORRECT):
  key: acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40
  bins: { count: 3, amount_sum: 75000 }
  TTL: 15 minutes (auto-expires after 3× window)

  key: acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:45
  bins: { count: 1, amount_sum: 25000 }
  TTL: 15 minutes

At time 10:47:
  → Current bucket is 10:45 (floor of 10:47 to 5-min boundary)
  → Read bucket 10:45 → count=1
  → Old bucket 10:40 auto-expires via TTL
  → ZERO cleanup code, ZERO background jobs
```

### 4.3 Visual: How Buckets Roll Over Time

```text
Time:     10:40    10:45    10:50    10:55    11:00
          ┌────┐
Bucket 1: │ 3  │  ← created at 10:40, expires at 10:55 (TTL=15min)
          └────┘
                   ┌────┐
Bucket 2:          │ 1  │  ← created at 10:45, expires at 11:00
                   └────┘
                            ┌────┐
Bucket 3:                   │ 5  │  ← created at 10:50, expires at 11:05
                            └────┘

At 10:47 → read bucket "10:45" → count=1 (current window answer)
At 10:52 → read bucket "10:50" → count=5 (current window answer)
Bucket "10:40" already auto-expired — zero maintenance!
```

### 4.4 Why Not a True Sliding Window?

A true sliding window (exact count in last 300 seconds from NOW) requires storing every individual event timestamp:

```text
True sliding window:
  Store: [10:41:02, 10:42:15, 10:43:44, 10:44:01, 10:46:55, ...]
  At each read: filter timestamps > (now - 5min), count remaining
  
  Problems:
  - 100k events/day = storing thousands of timestamps per entity
  - Reading all, filtering by time, counting — too slow for p99 < 20ms
  - Unbounded list growth within a single Aerospike record
  - Record size limits in Aerospike (1MB default, 8MB max)
```

Tumbling windows (bucket floors) are an acceptable approximation:

```text
Trade-off:
  - Worst case: you miss events in the partial overlap zone
  - At 5-min granularity, maximum error is ~5 minutes of stale data
  - For fraud detection, this inaccuracy is acceptable
  - Rules have safety margins (threshold 10 means concern at 7-8)
```

### 4.5 Bucket Alignment Logic

```text
Algorithm: floor current time to the nearest window boundary

floor_to_5min("10:43:22")  → "10:40"
floor_to_5min("10:47:59")  → "10:45"
floor_to_1hour("10:43:22") → "10"
floor_to_10min("10:43:22") → "10:40"

Code:
  bucket_5m  = timestamp - (timestamp % (5 * 60))
  bucket_1h  = timestamp - (timestamp % (60 * 60))
  bucket_10m = timestamp - (timestamp % (10 * 60))
```

### 4.6 The Boundary Overlap Problem

```text
Problem: "Last 5 minutes" at time 14:03 with 5-minute buckets

Timeline:
  |----bucket 13:55-13:59----|----bucket 14:00-14:04----|
                                        ^
                                     NOW (14:03)

  "Last 5 minutes" = 13:58 to 14:03
  But bucket boundary is at 14:00

  Current bucket (14:00-14:04): contains events from 14:00 to 14:03 ✓
  Previous bucket (13:55-13:59): contains ALL events from 13:55-13:59
    → But we only want 13:58-13:59 (the overlap portion)
    → We're OVER-counting by including 13:55-13:57

  Result: We see events from 13:55 to 14:03 (8 minutes worth)
          instead of exactly 13:58 to 14:03 (5 minutes)
```

This is the fundamental inaccuracy of tumbling/fixed windows — at the boundary,
you either over-count (include extra) or under-count (miss some).

### 4.7 Practical Approach: Smaller Buckets + Batch Sum

Instead of one big 5-minute bucket, use **1-minute buckets** and sum the last 5-6:

```text
Key pattern: txn_count:{user}:{minute_bucket}

At time 14:03, batch-read these keys:
  txn_count:user123:14_03  → 2  (current minute, partial — still accumulating)
  txn_count:user123:14_02  → 5
  txn_count:user123:14_01  → 3
  txn_count:user123:14_00  → 4
  txn_count:user123:13_59  → 6
  txn_count:user123:13_58  → 1  (partial overlap — included for safety)

Sum = 2 + 5 + 3 + 4 + 6 + 1 = 21 transactions in ~last 5 minutes

Aerospike batch read of 5-6 keys: ~2-4ms (well within p99 budget)
```

Why read 6 keys for a 5-minute window?
- At 14:03:45, the current bucket (14:03) is only 45 seconds old
- Reading only 5 buckets gives ~4 min 45 sec of history
- Reading 6 buckets guarantees at least 5 full minutes are covered
- Slight over-count is safer than under-count for fraud detection

### 4.8 Trade-off: Bucket Granularity vs Read Cost vs Precision

| Bucket Size | Keys to Read (5-min window) | Precision | Read Latency | Storage Keys/hour |
|-------------|----------------------------|-----------|--------------|-------------------|
| 5 min       | 2                          | Low (~50% error at boundary) | ~1ms  | 12  |
| 1 min       | 6                          | Good (~20% error)            | ~2-3ms | 60  |
| 30 sec      | 11                         | High (~10% error)            | ~3-4ms | 120 |
| 10 sec      | 31                         | Very high (~3% error)        | ~5-7ms | 360 |

**Sweet spot for fraud detection: 1-minute buckets**
- 6 batch reads is cheap in Aerospike (~2-3ms)
- ~20% boundary error is negligible for fraud thresholds
- TTL auto-expires old buckets (set TTL = window size + buffer = 10 minutes)
- Storage is bounded: max 60 keys/hour/entity, all auto-expired

### 4.9 Why Approximation Is Acceptable for Fraud

```text
Fraud detection is NOT a precision instrument — it's a safety net:

1. Over-counting (seeing more events than reality):
   → May trigger a false positive → transaction gets flagged for review
   → Human reviews it, approves it → slight UX delay, no real harm
   → SAFE: better to flag a legitimate user than miss a fraudster

2. Under-counting (missing events):
   → May miss a burst of fraudulent transactions
   → Money leaves the system before detection
   → DANGEROUS: this is actual financial loss

Therefore:
   - Rules have safety margins: if threshold is 10, concern triggers at 7-8
   - Over-counting by 1-2 transactions is noise within the margin
   - The system is designed to err on the side of caution
   - Exact precision would require storing individual timestamps (too expensive)
```

```text
Real-world math:
  Threshold: "block if > 10 transactions in 5 minutes"
  Actual fraud burst: 15 transactions in 4 minutes
  
  With 1-min buckets, worst case we over-count by ~1 minute of history:
    We see: 15 + (maybe 2 extra from the overlap minute) = 17
    Still way above threshold of 10 → correctly blocked ✓
  
  Under-count scenario (if we accidentally skip a bucket):
    We see: 15 - 3 = 12
    Still above threshold of 10 → correctly blocked ✓
    
  The margin handles the imprecision.
```

---

## 5. End-to-End Flow — Fraud Check

### 5.1 Transaction Arrives

```text
POST /api/v1/payments
{
  "request_id": "req_7e1f",
  "account_id": "u123",
  "device_id": "d789",
  "ip": "203.0.113.55",
  "card_token": "ch_98ab",
  "amount": 25000,
  "currency": "INR"
}
```

### 5.2 Normalize Identifiers

```python
request_id  = "req_7e1f"
account_id  = "u123"
device_id   = "d789"
ip_hash     = hash("203.0.113.55")       # consistent hash
card_hash   = "ch_98ab"                   # already tokenized by PSP
bucket_5m   = floor_to_5min(now)          # "2026-05-28T10:40"
bucket_1h   = floor_to_1hour(now)         # "2026-05-28T10"
bucket_10m  = floor_to_10min(now)         # "2026-05-28T10:40"
today       = "2026-05-28"
```

### 5.3 Idempotency Check (Single Read)

```python
idem_key = "risk_decision:req_7e1f"
existing = aerospike.get(namespace="risk", set="decision_guard", key=idem_key)

if existing:
    return existing.decision  # Already processed — return cached result
```

Purpose: Prevents duplicate decisions on retried requests.

### 5.4 Batch Read All Features (SINGLE ROUNDTRIP)

```python
keys = [
    ("risk", "account_profile",   "acct:u123|profile"),
    ("risk", "account_velocity",  "acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40"),
    ("risk", "account_velocity",  "acct:u123|metric:pay_attempts|window:1h|bucket:2026-05-28T10"),
    ("risk", "device_velocity",   "device:d789|metric:failed_payments|window:1h|bucket:2026-05-28T10"),
    ("risk", "card_velocity",     "card:ch_98ab|metric:amount_attempted|day:2026-05-28"),
    ("risk", "ip_velocity",       "ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40"),
    ("risk", "negative_list",     "entity:ch_98ab"),
]

# One network roundtrip — Aerospike client fans out to multiple nodes in parallel
features = aerospike.batch_get(keys)
```

Key insight: Batch read sends all 7 keys to the cluster in ONE network call. The client library handles routing each key to the correct node. Total latency: 2-4ms for all 7 records.

If a record does not exist (new user, new time window), Aerospike returns null. Default to count=0.

### 5.5 Evaluate Rules

```python
# Extract features (default to 0 if record doesn't exist)
acct_5m_attempts    = features[1].get("count", 0)
acct_1h_attempts    = features[2].get("count", 0)
device_failed_1h    = features[3].get("failed_count", 0)
card_daily_amount   = features[4].get("amount_sum", 0)
ip_accounts_10m     = features[5].get("count", 0)
is_blocked          = features[6] is not None

profile = features[0] or default_profile()

# ─── Rule Engine ───
decision = "ALLOW"
score = 0

if is_blocked:
    return Decision(action="DECLINE", reason="BLOCKED_ENTITY", score=100)

if acct_5m_attempts > 10:
    score += 40
    decision = "CHALLENGE"

if device_failed_1h > 5:
    score += 30
    decision = "CHALLENGE"

if card_daily_amount + amount > DAILY_CARD_LIMIT:
    score += 25
    decision = "CHALLENGE"

if ip_accounts_10m > 50:
    score += 20  # possible proxy/NAT abuse

if profile.risk_tier == "HIGH" and amount > HIGH_RISK_THRESHOLD:
    score += 35
    decision = "DECLINE"

if score >= DECLINE_THRESHOLD:
    decision = "DECLINE"
elif score >= CHALLENGE_THRESHOLD:
    decision = "CHALLENGE"
```

### 5.6 When Do Counter Writes Happen?

CRITICAL: Counter writes happen AFTER the decision, not before.

```text
Timeline of a single transaction:
─────────────────────────────────────────────────────

T+0ms    Request arrives
T+0.5ms  Idempotency READ (1 key)
T+2ms    Batch READ all 7 feature keys    ← READS happen here
T+4ms    Rule evaluation (in-memory)
T+5ms    Decision made: ALLOW/CHALLENGE/DECLINE
T+6ms    Balance hold (if ALLOW)           ← conditional WRITE
T+7ms    Counter WRITES happen             ← ALL increments here
T+8ms    Idempotency WRITE
T+8ms    Kafka publish (async)

Reads are BEFORE decision.
Writes are AFTER decision.
```

Why writes come after decision:

```text
If you write BEFORE decision:
  - Declined requests inflate counters
  - Need rollback logic if you decline after writing
  - Adds complexity and race conditions

If you write AFTER decision:
  - Counters reflect only relevant attempts
  - No rollback needed
  - Simpler, more predictable flow
```

### 5.7 Which Counters Get Updated Based on Decision

```text
Decision = ALLOW:
  ✅ account 5m attempts: count +1, amount +amount
  ✅ account 1h attempts: count +1, amount +amount
  ✅ card daily amount: amount +amount, count +1
  ❌ device failed counter: NOT incremented (success)
  ✅ ip accounts seen: count +1
  ✅ idempotency record: written

Decision = DECLINE:
  ✅ account 5m attempts: count +1 (tracks pressure)
  ✅ account 1h attempts: count +1
  ❌ card daily amount: NOT incremented (didn't actually charge)
  ✅ device failed counter: failed_count +1
  ✅ ip accounts seen: count +1
  ✅ idempotency record: written

Decision = CHALLENGE (OTP/2FA sent, pending user action):
  ✅ account 5m attempts: count +1
  ❌ others: wait until challenge is resolved
```

### 5.8 Counter Write Implementation (Atomic Operate)

```python
# Each write is an atomic 'operate' — read-modify-write in ONE call
# No race conditions even under high concurrency

aerospike.operate(
    key="acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40",
    ops=[
        add("count", 1),
        add("amount_sum", amount),
        write("last_seen_at", now),
    ],
    meta={"ttl": 900}  # 15 minutes (3× the 5-min window)
)

aerospike.operate(
    key="acct:u123|metric:pay_attempts|window:1h|bucket:2026-05-28T10",
    ops=[
        add("count", 1),
        add("amount_sum", amount),
    ],
    meta={"ttl": 10800}  # 3 hours
)

aerospike.operate(
    key="card:ch_98ab|metric:amount_attempted|day:2026-05-28",
    ops=[
        add("amount_sum", amount),
        add("count", 1),
    ],
    meta={"ttl": 259200}  # 3 days
)

# Only increment failure counter if declined/challenged
if decision in ("DECLINE", "CHALLENGE"):
    aerospike.operate(
        key="device:d789|metric:failed_payments|window:1h|bucket:2026-05-28T10",
        ops=[add("failed_count", 1)],
        meta={"ttl": 10800}  # 3 hours
    )

aerospike.operate(
    key="ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40",
    ops=[add("count", 1)],
    meta={"ttl": 1800}  # 30 minutes
)
```

Why atomic `operate` matters:

```text
Without operate (get-modify-put):
  Thread A: read count=5
  Thread B: read count=5
  Thread A: write count=6
  Thread B: write count=6  ← WRONG! Should be 7

With operate (atomic add):
  Thread A: add count +1  → Aerospike internally: 5→6
  Thread B: add count +1  → Aerospike internally: 6→7  ← CORRECT
  
  Both operations are atomic at the storage engine level.
  No locks needed. No race conditions.
```

### 5.9 Write Idempotency Guard

```python
aerospike.put(
    key="risk_decision:req_7e1f",
    bins={"decision": decision, "score": score, "created_at": now},
    meta={"ttl": 259200}  # 72 hours
)
```

### 5.10 Publish Event to Kafka

```python
kafka.produce("risk.decisions", {
    "request_id": request_id,
    "account_id": account_id,
    "device_id": device_id,
    "card_hash": card_hash,
    "amount": amount,
    "features_snapshot": {
        "acct_5m_attempts": acct_5m_attempts,
        "acct_1h_attempts": acct_1h_attempts,
        "device_failed_1h": device_failed_1h,
        "card_daily_amount": card_daily_amount,
        "ip_accounts_10m": ip_accounts_10m,
    },
    "score": score,
    "decision": decision,
    "latency_ms": elapsed,
    "timestamp": now
})
```

Events are consumed by:
- Analytics/reporting system (dashboards)
- ML training pipeline (model retraining)
- Audit log (compliance)

---

## 6. Balance Check Pattern

### 6.1 Important Distinction

```text
Aerospike = HOT BALANCE (sub-ms reads for real-time authorization)
Postgres  = SOURCE OF TRUTH (ledger, audit trail, reconciliation)

Aerospike is NOT a replacement for your ledger database.
It holds a fast-access cached copy for real-time decisions.
```

### 6.2 Balance Data Model

```text
namespace: wallet
set: balance

key: wallet:u123

bins:
  available_balance    → amount available for spending (in paise/cents)
  held_balance         → amount in authorization holds
  currency             → "INR"
  last_updated_at      → timestamp
  version              → manual version for audit trail
```

### 6.3 Balance Check + Hold (Authorization)

Approach A: Optimistic with Generation Check (CAS):

```python
def authorize_payment(account_id: str, amount: int) -> AuthResult:
    key = f"wallet:{account_id}"
    
    # Read current balance with generation number
    record = aerospike.get(key, return_gen=True)
    generation = record.generation
    available = record.bins["available_balance"]
    
    # Insufficient funds — reject immediately
    if available < amount:
        return AuthResult(status="DECLINED", reason="INSUFFICIENT_FUNDS")
    
    # Atomic debit + hold using generation check (CAS)
    try:
        aerospike.operate(
            key=key,
            ops=[
                add("available_balance", -amount),   # deduct from available
                add("held_balance", +amount),        # move to held
                write("last_updated_at", now),
            ],
            policy={"gen": generation}  # fails if record was modified since read
        )
        return AuthResult(status="AUTHORIZED", hold_id=generate_hold_id())
    
    except GenerationError:
        # Another transaction modified the record between read and write
        # Retry with backoff (max 3 retries)
        return authorize_payment(account_id, amount)
```

Why generation check:

```text
Without generation check:
  Thread A: read balance=10000
  Thread B: read balance=10000
  Thread A: deduct 8000 → write balance=2000    ← success
  Thread B: deduct 8000 → write balance=2000    ← WRONG! Overdraft!

With generation check:
  Thread A: read balance=10000, gen=5
  Thread B: read balance=10000, gen=5
  Thread A: deduct 8000, gen_policy=5 → success, gen becomes 6
  Thread B: deduct 8000, gen_policy=5 → FAILS (gen is now 6)
  Thread B: retries → read balance=2000, gen=6 → insufficient funds → DECLINE
```

Approach B: Pessimistic with Expression Filter (Aerospike 5.6+):

```python
def authorize_payment_v2(account_id: str, amount: int) -> AuthResult:
    key = f"wallet:{account_id}"
    
    # Single atomic operation — no read-then-write race
    try:
        aerospike.operate(
            key=key,
            ops=[
                add("available_balance", -amount),
                add("held_balance", +amount),
                write("last_updated_at", now),
            ],
            policy={
                "expression_filter": "available_balance >= amount"
                # Only executes if expression is true
                # Otherwise returns FILTERED_OUT error
            }
        )
        return AuthResult(status="AUTHORIZED")
    
    except FilteredOutError:
        return AuthResult(status="DECLINED", reason="INSUFFICIENT_FUNDS")
```

Comparison:

```text
Approach A (Optimistic + Gen Check):
  ✅ Works on all Aerospike versions
  ✅ Simple to understand
  ❌ Retries under high concurrency (e.g., 50 concurrent txns for one merchant)
  Best for: Low-to-medium contention scenarios

Approach B (Expression Filter):
  ✅ Zero retries — single atomic call
  ✅ No read-before-write roundtrip
  ❌ Requires Aerospike 5.6+
  ❌ Slightly more complex expression syntax
  Best for: High-contention scenarios (popular merchants with burst traffic)
```

### 6.4 Balance Capture (Settlement)

```python
def capture_payment(account_id: str, amount: int, hold_id: str):
    """Convert hold to permanent debit — money leaves the wallet."""
    key = f"wallet:{account_id}"
    
    aerospike.operate(
        key=key,
        ops=[
            add("held_balance", -amount),  # release hold
            # available_balance unchanged — already deducted during auth
        ]
    )
    
    # Publish to ledger system for permanent record
    kafka.produce("wallet.captures", {
        "account_id": account_id,
        "amount": amount,
        "hold_id": hold_id,
        "timestamp": now
    })
```

### 6.5 Balance Reversal (Refund / Hold Release)

```python
def release_hold(account_id: str, amount: int, hold_id: str):
    """Release authorization hold — money returns to available."""
    key = f"wallet:{account_id}"
    
    aerospike.operate(
        key=key,
        ops=[
            add("available_balance", +amount),  # restore to available
            add("held_balance", -amount),       # release hold
            write("last_updated_at", now),
        ]
    )
    
    kafka.produce("wallet.reversals", {
        "account_id": account_id,
        "amount": amount,
        "hold_id": hold_id,
        "reason": "HOLD_EXPIRED",
        "timestamp": now
    })
```

### 6.6 Balance State Machine

```text
                    authorize()
  AVAILABLE ──────────────────────→ HELD
     ↑                                 │
     │         release_hold()          │  capture()
     ←─────────────────────────────────│
                                       ↓
                                   CAPTURED (money gone)
                                       │
                                       │  refund()
                                       ↓
                                   REFUNDED (money back to AVAILABLE)
```

### 6.7 Balance Sync — Aerospike ↔ Ledger DB

```text
┌─────────────────────────────────────────────────────────┐
│  Source of Truth: Postgres (ledger table)                 │
│  Hot Cache: Aerospike (sub-ms reads for authorization)   │
│                                                           │
│  Sync Pattern:                                            │
│                                                           │
│  On payment event:                                        │
│    1. Aerospike: atomic update (real-time, synchronous)   │
│    2. Kafka event published (async)                       │
│    3. Consumer: update Postgres ledger (eventual)         │
│                                                           │
│  Reconciliation (every 5 min):                            │
│    - Compare Aerospike balance vs Postgres balance        │
│    - If drift > threshold: alert + correct Aerospike     │
│    - Log discrepancies for audit                          │
│                                                           │
│  Recovery (on Aerospike restart/failover):                │
│    - Rebuild Aerospike balance from Postgres              │
│    - Replay uncommitted Kafka events                      │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Combined Flow — Fraud + Balance Together

```text
┌──────────────────── COMPLETE AUTHORIZATION FLOW ────────────────────┐
│                                                                       │
│  1. Request arrives with amount + identifiers         T+0ms          │
│  2. Idempotency check (Aerospike get)                 T+0.5ms       │
│  3. Batch read 7 velocity features (one roundtrip)    T+2-4ms       │
│  4. Rule/model evaluation (in-process, no I/O)        T+4-5ms       │
│  5. If DECLINE → return immediately, skip balance                    │
│  6. Balance check + hold (Aerospike operate+gen)      T+6-7ms       │
│  7. If insufficient funds → DECLINE                                  │
│  8. Update velocity counters (Aerospike operate ×5)   T+7-8ms       │
│  9. Write idempotency record                          T+8ms         │
│  10. Return AUTHORIZED to Payment Service                            │
│  11. Publish event to Kafka (async, non-blocking)     background     │
│                                                                       │
│  Total latency: ~8-12ms p95                                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 8. Handling Hotspots

### 8.1 Problem: NAT/Proxy IP Serves Millions of Users

```text
BAD — single hot key:
  key = ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40
  
  If this IP is a corporate proxy with 10,000 users, this ONE key gets
  10,000 writes per 10-minute window. One Aerospike partition handles it all.
```

### 8.2 Solution: Sub-Bucketing (Sharding the Key)

```text
GOOD — sharded across 64 sub-keys:
  shard = hash(account_id) % 64
  key = ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40|shard:07

Write path:
  - Compute shard from account_id
  - Increment ONE shard record (1 network call)
  - Load distributed across up to 64 different partitions

Read path:
  - Batch read all 64 shards (1 batch call)
  - Sum counts locally
  - Cache result for 2-5 seconds (approximate is fine for fraud)
```

### 8.3 When to Apply Sharding

```text
Apply sharding when:
  - A single key receives > 1000 writes/second
  - Aerospike monitoring shows hot partition alerts
  - One node has significantly higher latency than others

Do NOT shard when:
  - Write rate is low (most user-level counters)
  - The entity is naturally distributed (individual users)
  
Rule of thumb:
  - Per-user keys: no sharding needed (traffic distributes naturally)
  - Per-IP keys: shard if the IP is shared (proxy, NAT, CDN)
  - Per-campaign keys: always shard (one campaign = one hot key)
  - Global counters: always shard
```

---

## 9. TTL Strategy

| Record Type | TTL | Reason |
|---|---|---|
| 5-min velocity | 15 minutes | 3× window for late reads + clock skew |
| 10-min velocity | 30 minutes | 3× window |
| 1-hour velocity | 3 hours | 3× window |
| Daily counters | 3 days | Handle timezone edge cases |
| Account profile | No TTL or 90 days | Long-lived, updated by enrichment |
| Idempotency | 72 hours | Cover retry windows and support queries |
| Balance | No TTL | Must persist until explicit update |
| Negative list | No TTL or manual | Removed when investigation clears entity |

Why 3× the window duration for TTL:

```text
Window = 5 minutes
TTL = 15 minutes

Scenario:
  - Bucket 10:40 created at 10:40
  - Request at 10:44 reads bucket 10:40 (current window)
  - If TTL were exactly 5 min, bucket would expire at 10:45
  - But at 10:44:59 a read might still need it
  - With TTL=15min, bucket lives until 10:55 — safe for any read in the window
  - Also handles clock skew between application servers and Aerospike
```

---

## 10. Validation Checklist

### Step 1: Input Validation

```text
Required fields:
  request_id, account_id, amount, currency, timestamp

Normalize:
  IP → ip_hash (consistent hash)
  card → card_hash/token (from PSP)
  device fingerprint → device_id
  
Reject if:
  amount <= 0
  currency not supported
  timestamp too far in past/future
```

### Step 2: Idempotency

```text
Read risk_decision:{request_id}
If exists: return stored decision immediately
If not: continue with fresh evaluation
```

### Step 3: Feature Read

```text
Batch read all required feature keys
If optional feature missing: use default value (count=0)
If critical feature missing (profile): use conservative fallback rules
```

### Step 4: Rule Evaluation

```text
Assert thresholds are loaded from config
Assert currency conversion is available (if multi-currency)
Assert risk tier is valid enum
Apply rules in priority order
```

### Step 5: Decision Output

```text
score >= decline_threshold → DECLINE
score >= challenge_threshold → CHALLENGE
else → ALLOW
```

### Step 6: Write Validation

```text
Counter writes use atomic add operations (no lost updates)
Idempotency record written after decision
Balance update uses generation check (no overdraft)
Event published for audit trail
```

### Step 7: Monitoring

```text
Track these metrics:
  - decision_latency_p99
  - aerospike_batch_read_latency_p99
  - counter_update_latency_p99
  - missing_feature_rate
  - challenge_rate
  - decline_rate
  - false_positive_rate (from chargeback feedback loop)
  - retry_rate (generation conflicts)
  - idempotency_hit_rate
  - balance_reconciliation_drift
```

---

## 11. What Goes Wrong and How to Fix It

| Problem | Cause | Fix |
|---|---|---|
| Counter overshoot | Concurrent increments before check | Accept approximate for fraud; use gen check for balance |
| Stale balance | Aerospike/Postgres drift | Periodic reconciliation every 5 min |
| Hot partition | Popular IP/merchant/campaign | Shard the key into 64-256 sub-buckets |
| Missing features on new user | No historical data | Default to conservative rules, challenge on first txn |
| Clock skew across servers | Different bucket assignment | Use NTP, TTL=3× window absorbs minor skew |
| Idempotency miss after restart | In-flight requests lost | TTL on idempotency records; PSP handles retries |
| Expired hold not released | Capture never called | Background job releases holds older than 30 min |
| Balance goes negative | Race in gen check retry | Use expression filter (Approach B) for high-contention |

---

## 12. Production Sizing

For a system doing 100k transactions/day:

```text
Peak TPS estimate:
  100k/day ÷ 86400 = ~1.2 avg TPS
  Peak (10× avg) = ~12 TPS
  Burst (flash sale) = ~100 TPS

Records per day:
  Per txn: ~5 velocity records created/updated
  100k × 5 = 500k records/day
  But TTLs expire most within hours
  Steady-state in Aerospike: ~200k-500k active records

Memory estimate:
  Avg record size: ~200 bytes (key + bins)
  500k records × 200 bytes = ~100 MB
  With overhead (indexes, metadata): ~300 MB
  
  This fits easily in a single-node Aerospike with 4GB RAM.
  For HA: 2-node cluster with replication factor 2.

Aerospike cluster for this scale:
  - 2 nodes (for HA)
  - 4 GB RAM each
  - SSD for persistence
  - Replication factor: 2
```

---

## 13. Summary: Aerospike's Role in the Payment Stack

```text
┌──────────────────────────────────────────────────────────────┐
│                                                                │
│  AEROSPIKE: Real-time decision engine state store             │
│    ✅ Velocity counters (sub-ms atomic increment)             │
│    ✅ Balance hot cache (sub-ms auth check)                   │
│    ✅ Idempotency guards (duplicate detection)                │
│    ✅ Risk profiles (feature serving)                         │
│    ✅ Negative lists (block checks)                           │
│                                                                │
│  POSTGRES: Source of truth                                     │
│    ✅ Ledger (complete transaction history)                   │
│    ✅ Balance reconciliation                                  │
│    ✅ Audit trail                                             │
│    ✅ Regulatory reporting                                    │
│                                                                │
│  KAFKA: Event backbone                                         │
│    ✅ Decision events (for analytics/ML)                      │
│    ✅ Balance events (for ledger sync)                        │
│    ✅ Enrichment events (profile updates)                     │
│                                                                │
│  OPENSEARCH/CLICKHOUSE: Analytics                              │
│    ✅ Dashboard listing (merchant sees all transactions)      │
│    ✅ Reporting and aggregations                              │
│    ✅ Pattern analysis for fraud model training               │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```
