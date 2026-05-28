# Aerospike End-to-End Use Case Designs

**Purpose:** Explain how to use Aerospike end to end for real production use cases: fraud velocity checks, key-value storage, recommendations, session store, durable cache, profiles, device state, ad frequency capping, counters, rate limiting, and shopping cart state.

**Core idea:** Aerospike is strongest when the application can derive the exact key or a small bounded set of keys. Design starts from the request path, then the key, then the bins, then TTL/replication/consistency.

## 1. Aerospike As A Key-Value Store

### 1.1 Mental Model

Every hot-path request should answer this question:

```text
What exact Aerospike key or small list of keys do I need?
```

If the service can derive the key, the flow is fast:

```text
request
  -> derive key
  -> Aerospike client routes to partition owner
  -> primary index locates record
  -> read/update bins
  -> return response
```

Aerospike data model:

```text
namespace -> set -> key -> record bins
```

Example:

```text
namespace: auth
set: session
key: sess:01HX9W4R8Z7E1S

bins:
  user_id = u123
  status = ACTIVE
  last_seen_at = 2026-05-28T10:00:00Z
```

### 1.2 Key Design Rules

Good Aerospike keys are:

- High cardinality.
- Stable.
- Easy to derive from request fields.
- Bounded by time or entity where needed.
- Not a single global aggregate key.
- Designed for the primary read/write path.

Bad keys:

```text
global_counter
all_sessions_today
campaign:c777|impressions_total
tenant:t1|all_requests_current_minute
user:u123|all_events_forever
```

Better keys:

```text
session:
  sess:01HX9W4R8Z7E1S

user profile:
  user:u123

device state:
  device:d789

per-user fraud feature:
  risk:user:u123|window:5m|bucket:2026-05-28T10:42

campaign frequency cap:
  tenant:t1|campaign:c777|user:u123|day:2026-05-28

sharded campaign total:
  campaign:c777|impressions_total|bucket:091
```

### 1.3 Key Naming Convention

Use explicit prefixes:

```text
entity_type:entity_id|dimension:value|bucket:value
```

Examples:

```text
user:u123
device:ios_a71
session:sess_abc
cart:user:u123|cart:active
rate:tenant:t1|api:checkout|user:u123|minute:2026-05-28T10:42
```

Why this helps:

- Easier debugging.
- Easier logs.
- Easier support tooling.
- Safer schema evolution.

### 1.4 Read-Modify-Write Pattern

For counters and state updates, prefer atomic record operations:

```text
operate key:
  add count by 1
  set last_seen_at
  set/update TTL
```

Avoid:

```text
get count
count = count + 1 in app
put count
```

The get-modify-put pattern can lose updates under concurrency unless guarded by generation checks.

### 1.5 Idempotency

For payment, fraud, cart, and ad events, retries are normal. Use an idempotency record.

Example:

```text
namespace: guard
set: idempotency
key: event:payment_authorization:req_abc123

bins:
  status = PROCESSED
  result_hash = ...
  created_at = ...
```

Flow:

```text
request arrives with request_id
  -> check idempotency key
  -> if processed, return previous result
  -> otherwise process
  -> write idempotency record with TTL
```

TTL examples:

```text
payment idempotency: 24-72 hours
ad impression event idempotency: 1-24 hours
cart operation idempotency: 1-24 hours
```

## 2. Reference Architecture

Common production architecture:

```text
Client/API Gateway
  -> Application Service
  -> Aerospike Client SDK
  -> Aerospike Cluster
  -> Event Stream for async processing
  -> Analytics/Search/ML stores
```

Example:

```text
Payment Service
  -> reads risk features from Aerospike
  -> makes fraud decision
  -> writes updated velocity counters to Aerospike
  -> publishes event to Kafka
  -> offline jobs train models and refresh features
```

Aerospike should own:

- Low-latency serving state.
- Counters.
- Recent windows.
- Profiles/features needed by online services.
- TTL-backed operational records.

Other systems should own:

- Heavy analytics.
- Model training.
- Ad hoc dashboards.
- Search.
- Long-term event history.

## 3. Velocity Check Fraud System With Aerospike

### 3.1 Problem

A payment service must decide whether a transaction is risky before authorization.

Velocity checks answer questions like:

```text
How many payments did this user attempt in the last 5 minutes?
How many failed payments happened from this device in the last 1 hour?
How many distinct cards were used by this account in the last 24 hours?
How many accounts used this IP in the last 10 minutes?
How much total amount did this card attempt today?
```

The response must be fast:

```text
p99 decision latency target: 20-50 ms inside the risk service
```

### 3.2 High-Level Flow

```text
Checkout Service
  -> Payment Authorization Request
  -> Fraud/Risk Service
  -> Aerospike batch read features
  -> rule/model evaluation
  -> Aerospike update velocity counters
  -> allow / challenge / decline
  -> publish decision event
```

Detailed request flow:

```text
1. User clicks Pay.
2. Checkout sends payment request to Payment Service.
3. Payment Service calls Fraud Service before charging.
4. Fraud Service normalizes identifiers:
   - user_id
   - account_id
   - device_id
   - ip_hash
   - card_hash
   - merchant_id
5. Fraud Service derives Aerospike keys.
6. Fraud Service batch reads current feature records.
7. Fraud Service validates thresholds and model features.
8. Fraud Service returns decision.
9. Fraud Service writes updated counters/features.
10. Event stream stores the full decision for analytics and training.
```

### 3.3 Namespaces And Sets

Example namespaces:

```text
namespace: risk
```

Sets:

```text
risk.account_velocity
risk.device_velocity
risk.ip_velocity
risk.card_velocity
risk.account_profile
risk.decision_idempotency
risk.negative_lists
```

In Aerospike naming, set names are often simple strings. The dotted names above are logical examples; actual set names may be:

```text
account_velocity
device_velocity
ip_velocity
card_velocity
account_profile
decision_guard
negative_list
```

### 3.4 Feature Key Design

Use separate records for separate entities and time windows.

Account 5-minute velocity:

```text
key = acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40
```

Account 1-hour velocity:

```text
key = acct:u123|metric:pay_attempts|window:1h|bucket:2026-05-28T10
```

Card daily amount:

```text
key = card:ch_98ab|metric:amount_attempted|day:2026-05-28
```

Device failed payments:

```text
key = device:d789|metric:failed_payments|window:1h|bucket:2026-05-28T10
```

IP account fanout:

```text
key = ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40
```

Account risk profile:

```text
key = acct:u123|profile
```

Idempotency:

```text
key = risk_decision:req_7e1f
```

### 3.5 Bins

Counter-style bins:

```text
count
amount_sum
failed_count
approved_count
declined_count
last_seen_at
```

Profile bins:

```text
risk_tier
kyc_status
account_age_days
last_good_payment_at
chargeback_count_90d
trusted_device_count
```

Approximate distinct bins:

```text
distinct_card_hll
distinct_account_hll
```

If exact distinctness is required, store separate records per pair:

```text
key = acct:u123|card:ch_98ab|seen_day:2026-05-28
```

For online fraud, exact global distinct counts are often too expensive. Use bounded windows, approximate structures, or asynchronous enrichment.

### 3.6 Fraud Decision Read Path

For transaction:

```text
request_id = req_7e1f
account_id = u123
device_id = d789
ip_hash = iphash_55aa
card_hash = ch_98ab
amount = 25000 INR
time = 2026-05-28T10:43:22
```

Derive keys:

```text
idempotency:
  risk_decision:req_7e1f

account profile:
  acct:u123|profile

account 5m attempts:
  acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40

account 1h attempts:
  acct:u123|metric:pay_attempts|window:1h|bucket:2026-05-28T10

device 1h failed:
  device:d789|metric:failed_payments|window:1h|bucket:2026-05-28T10

card daily amount:
  card:ch_98ab|metric:amount_attempted|day:2026-05-28

ip 10m accounts:
  ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40
```

Batch read:

```text
records = batch_get(keys)
```

Evaluate:

```text
if account_5m_attempts > 10:
  decline or challenge

if card_daily_amount + current_amount > daily_card_limit:
  challenge

if device_failed_1h > 5:
  challenge

if account profile risk_tier = HIGH and amount > threshold:
  challenge/decline
```

Decision result:

```text
ALLOW
CHALLENGE
DECLINE
```

### 3.7 Fraud Decision Write Path

After decision, update velocity counters:

```text
operate acct 5m attempts:
  add count +1
  add amount_sum +amount
  set last_seen_at
  set TTL = 15 minutes

operate acct 1h attempts:
  add count +1
  add amount_sum +amount
  set TTL = 3 hours

operate card daily amount:
  add amount_sum +amount
  add count +1
  set TTL = 3 days

operate device failed counter:
  if decision failed/declined:
    add failed_count +1
  set TTL = 3 hours
```

Write idempotency:

```text
put risk_decision:req_7e1f:
  decision = ALLOW
  score = 41
  created_at = now
  TTL = 72 hours
```

Publish event:

```text
risk_decision_event {
  request_id,
  account_id,
  device_id,
  card_hash,
  amount,
  features_used,
  score,
  decision,
  timestamp
}
```

### 3.8 Validation From Start To End

Validation means proving the system makes correct decisions and survives real production behavior.

Step 1: input validation.

```text
required:
  request_id
  account_id
  amount
  currency
  timestamp

normalize:
  IP -> ip_hash
  card -> card_hash/token
  device fingerprint -> device_id
```

Step 2: idempotency validation.

```text
read risk_decision:req_7e1f
if exists:
  return stored decision
```

Step 3: feature-read validation.

```text
batch read all required feature keys
if optional feature missing:
  use default value
if critical feature missing:
  use fallback rule or challenge
```

Step 4: rule validation.

```text
assert thresholds are loaded
assert currency conversion is known
assert account risk tier is valid
```

Step 5: decision validation.

```text
score >= decline_threshold -> DECLINE
score >= challenge_threshold -> CHALLENGE
else -> ALLOW
```

Step 6: write validation.

```text
counter writes use atomic add operations
idempotency record is written after decision
event is published for audit
```

Step 7: monitoring validation.

Track:

```text
decision latency p99
Aerospike batch read latency
counter update latency
missing feature rate
challenge rate
decline rate
false positive rate
chargeback rate
retry rate
idempotency hit rate
```

### 3.9 Hotspot Handling In Fraud

Potential hotspot:

```text
key = ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40
```

If a NAT/proxy IP serves millions of users, this key can become hot.

Fix with sub-buckets:

```text
key = ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40|shard:00
...
key = ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40|shard:63
```

Write:

```text
shard = hash(account_id) % 64
increment one shard
```

Read:

```text
batch read 64 shards
sum count or approximate count
cache result for a few seconds
```

Use exact summing only when needed. For high-speed fraud decisions, approximate or cached features are often acceptable if the model is designed for it.

## 4. Recommendation System With Aerospike

### 4.1 What Aerospike Should And Should Not Do

Aerospike should serve precomputed recommendation features and candidate lists with low latency.

Aerospike should not be the only system doing heavy recommendation training, joins, embeddings, or global ranking.

Recommended architecture:

```text
Event collection
  -> Kafka/Pulsar
  -> Flink/Spark/Feature pipelines
  -> Model training and candidate generation
  -> Aerospike serving store
  -> Recommendation API
```

Aerospike's role:

- Store user profile features.
- Store item features.
- Store precomputed candidate lists.
- Store short-lived personalized recommendation results.
- Store exploration counters.
- Store impression/click feedback counters.

### 4.2 End-to-End Recommendation Flow

Example: e-commerce homepage recommendations.

Offline/nearline flow:

```text
1. User views/clicks/purchases items.
2. Events go to Kafka.
3. Stream processor updates recent user features.
4. Batch pipeline trains model and computes candidates.
5. Candidate lists are written to Aerospike.
6. Recommendation API reads candidates from Aerospike at request time.
7. API applies light filters and ranking.
8. API returns top N products.
9. Impression/click feedback is written back as events/counters.
```

### 4.3 Aerospike Keys

User feature record:

```text
namespace: reco
set: user_features
key: user:u123
```

Bins:

```text
favorite_categories = ["shoes", "fitness"]
price_band = "mid"
brand_affinity = map
last_purchase_category = "running"
embedding_version = "emb_v14"
updated_at
```

Candidate list:

```text
namespace: reco
set: user_candidates
key: user:u123|surface:homepage|model:v42
```

Bins:

```text
item_ids = ["p1", "p2", "p3", ...]
scores = [0.98, 0.94, 0.91, ...]
generated_at
expires_at
model_version
```

Item feature record:

```text
namespace: reco
set: item_features
key: product:p555
```

Bins:

```text
category
brand
price
inventory_status
quality_score
popularity_score
```

User recent activity:

```text
namespace: reco
set: user_recent
key: user:u123|window:1h
```

Bins:

```text
recent_views = list
recent_clicks = list
recent_cart_adds = list
```

Use bounded lists only. Do not store unlimited user history in one record.

### 4.4 Online Recommendation Read Path

Request:

```text
GET /v1/recommendations?user_id=u123&surface=homepage
```

Flow:

```text
1. Build candidate key:
   user:u123|surface:homepage|model:v42

2. Batch read:
   - candidate list
   - user features
   - recent activity

3. If candidate list exists:
   - remove unavailable items
   - remove recently purchased/viewed items if needed
   - apply business rules
   - return top N

4. If candidate list missing:
   - fallback to segment candidates
   - fallback to popular items
```

Fallback keys:

```text
segment:fitness_mid_price|surface:homepage|model:v42
popular:country:IN|surface:homepage|hour:2026-05-28T10
```

### 4.5 Online Feedback Write Path

When user sees/clicks item:

```text
event = recommendation_impression/click
publish event to Kafka
```

Optional Aerospike counters:

```text
key = item:p555|metric:impressions|hour:2026-05-28T10|bucket:00
key = item:p555|metric:clicks|hour:2026-05-28T10|bucket:00
```

Use buckets if item is very popular:

```text
bucket = hash(user_id or request_id) % 64
```

### 4.6 Validation

Validate recommendation serving:

```text
candidate hit rate
fallback rate
Aerospike read latency p99
empty response rate
stale candidate rate
model version distribution
CTR by model version
conversion by model version
```

Validate data quality:

```text
candidate list length > minimum
no duplicate item IDs
items exist in catalog
items are in stock
restricted items filtered
model_version matches deployment
generated_at is within freshness SLA
```

### 4.7 Why Aerospike Fits Recommendations

- Fast feature/candidate lookup by user ID.
- Batch reads for user, item, and segment records.
- TTL for candidate freshness.
- Durable serving store independent from model pipeline.
- Can store large enough operational feature sets without keeping everything in app memory.

## 5. Session Store

### 5.1 Problem

Store web/mobile login sessions with low latency and automatic expiry.

### 5.2 Key

```text
namespace: auth
set: session
key: sess:01HX9W4R8Z7E1S
```

Bins:

```text
user_id
device_id
status
scopes
created_at
last_seen_at
risk_level
refresh_token_hash
```

TTL:

```text
idle session: 30 minutes
remember-me session: 30 days
revoked marker: 1-24 hours
```

### 5.3 End-to-End Flow

Login:

```text
1. Validate username/password/MFA.
2. Generate random session_id.
3. Put session record with TTL.
4. Return secure cookie.
```

Request auth:

```text
1. Extract session_id.
2. Aerospike get session.
3. If missing/expired, reject.
4. If status != ACTIVE, reject.
5. If active, authorize request.
6. Optionally touch TTL/update last_seen_at.
```

Logout:

```text
delete session record
or set status = REVOKED with short TTL
```

### 5.4 Validation

```text
session ID is random and unguessable
TTL is applied
cookie is secure/httpOnly/sameSite
logout invalidates session
stolen session detection uses device/IP risk signals
```

## 6. Durable Cache Store

### 6.1 Problem

Use Aerospike as a cache that survives application restarts and can hold more data than local memory.

### 6.2 Key

```text
namespace: cache
set: product_view
key: cache:v3|product:p555|locale:en-IN|currency:INR
```

Bins:

```text
payload
source_version
etag
created_at
```

TTL:

```text
price data: 5 minutes + jitter
catalog metadata: 1 hour + jitter
personalized cache: 1-10 minutes
```

### 6.3 Read-Through Flow

```text
1. Build cache key.
2. Aerospike get.
3. If hit, return payload.
4. If miss, fetch source systems.
5. Write cache record with TTL.
6. Return payload.
```

### 6.4 Thundering Herd Protection

Use a refresh lock:

```text
data key:
  cache:v3|product:p555|locale:en-IN|currency:INR

lock key:
  lock:cache:v3|product:p555|locale:en-IN|currency:INR
```

Flow:

```text
cache miss
  -> try create lock record with 5-15 second TTL
  -> winner refreshes cache
  -> losers wait or serve stale value
```

TTL jitter:

```text
ttl = base_ttl + random(0..jitter_seconds)
```

This avoids many records expiring at the same instant.

## 7. User Profile Store

### 7.1 Problem

Serve user profile data quickly for personalization, auth, and account services.

### 7.2 Key

```text
namespace: users
set: profile
key: user:u123
```

Bins:

```text
name
email_hash
phone_hash
country
language
plan
preferences
created_at
updated_at
version
```

### 7.3 End-to-End Flow

Read profile:

```text
1. API receives user_id.
2. Build key user:u123.
3. Aerospike get.
4. Return profile bins.
```

Update profile:

```text
1. Validate request.
2. Read current generation/version.
3. Apply update with generation check.
4. Publish profile_updated event.
```

Lookup by email:

```text
key = email_hash:ab91
bin user_id = u123
```

Then:

```text
read email_hash record
read user:u123 profile
```

Avoid broad secondary-index queries for login paths.

## 8. Device State Store

### 8.1 Problem

Store latest state for IoT, mobile, or connected devices.

### 8.2 Key

```text
namespace: devices
set: state
key: device:d789
```

Bins:

```text
user_id
status
firmware_version
battery_level
last_location
last_seen_at
last_event_id
config_version
```

### 8.3 End-to-End Flow

Device heartbeat:

```text
1. Device sends heartbeat.
2. API authenticates device.
3. Build key device:d789.
4. Update status, battery, last_seen_at.
5. TTL optional for auto-expiring inactive devices.
6. Publish heartbeat event for history/analytics.
```

Read current state:

```text
1. App requests device state.
2. Aerospike get device:d789.
3. If missing or last_seen_at old, show offline.
```

Do not store all historical telemetry in one Aerospike record. Send telemetry history to a time-series/analytics store.

## 9. Fraud/Risk Feature Store

This is the serving-store part of the fraud system.

### 9.1 Key Types

```text
account profile:
  acct:u123|profile

account velocity:
  acct:u123|metric:pay_attempts|window:5m|bucket:2026-05-28T10:40

device risk:
  device:d789|risk

card velocity:
  card:ch_98ab|metric:amount_attempted|day:2026-05-28

ip velocity:
  ip:iphash_55aa|metric:accounts_seen|window:10m|bucket:2026-05-28T10:40
```

### 9.2 Serving Pattern

```text
risk service
  -> batch get account/device/card/ip features
  -> evaluate rules/model
  -> update counters
  -> publish decision event
```

### 9.3 TTL

```text
5m velocity records: 15-30 minutes
1h velocity records: 2-4 hours
daily records: 2-7 days
profile records: no TTL or long TTL
idempotency records: 24-72 hours
```

## 10. Ad-Tech Frequency Capping

### 10.1 Problem

Limit how many times a user sees a campaign.

### 10.2 Key

```text
namespace: ads
set: freq_cap
key: tenant:t1|campaign:c777|user:u123|day:2026-05-28
```

Bins:

```text
impressions
clicks
last_seen_at
```

### 10.3 Flow

```text
1. Bid request arrives.
2. Build user-campaign-day key.
3. Get frequency record.
4. If impressions >= cap, do not bid.
5. If under cap, allow bid.
6. On impression, increment impressions.
7. TTL expires old cap records.
```

### 10.4 Campaign Total Counter

Bad:

```text
campaign:c777|impressions_total
```

Better:

```text
campaign:c777|impressions_total|bucket:000
...
campaign:c777|impressions_total|bucket:255
```

Write:

```text
bucket = hash(user_id or impression_id) % 256
increment one bucket
```

Read exact total:

```text
batch read all 256 buckets
sum impressions
cache total for 1-5 seconds
```

Dashboard total:

```text
use stream processing and analytics store
```

## 11. Real-Time Counters

### 11.1 Problem

Track counts at high write QPS.

Examples:

```text
likes
views
API requests
feature usage
tenant billing counters
campaign impressions
```

### 11.2 Single Counter

Use only when QPS is low/moderate:

```text
key = product:p555|views|day:2026-05-28
```

Operation:

```text
atomic add count +1
```

### 11.3 Sharded Counter

Use when one entity can become hot:

```text
key = product:p555|views|day:2026-05-28|bucket:000
...
key = product:p555|views|day:2026-05-28|bucket:127
```

Write:

```text
bucket = hash(request_id) % 128
increment bucket
```

Read:

```text
batch get buckets
sum counts
cache aggregate
```

### 11.4 Validation

```text
counter never uses one global key for viral objects
bucket count is enough for peak write QPS
read path can tolerate aggregation cost
aggregate cache TTL is acceptable
```

## 12. Rate Limiting And Quota Counters

### 12.1 Problem

Limit requests per user, tenant, API, or IP.

### 12.2 User Rate Limit Key

```text
namespace: limits
set: request_counter
key: tenant:t1|api:checkout|user:u123|minute:2026-05-28T10:42
```

Bins:

```text
count
first_seen_at
last_seen_at
```

TTL:

```text
2-5 minutes for minute window counters
```

Flow:

```text
1. Request arrives.
2. Build counter key.
3. Atomic increment count.
4. If count > limit, reject.
5. Else allow.
```

### 12.3 Tenant Quota Key

Tenant quota can be hot. Use buckets:

```text
tenant:t1|api:checkout|minute:2026-05-28T10:42|bucket:00
...
tenant:t1|api:checkout|minute:2026-05-28T10:42|bucket:63
```

Write:

```text
bucket = hash(request_id) % 64
increment bucket
```

Enforcement options:

- Exact: read all buckets and sum before allowing.
- Approximate: maintain local app counters and use Aerospike as shared backing.
- Strict: central admission service or reservation allocator.

## 13. Shopping Cart / Session-Like State

### 13.1 Problem

Store active shopping cart state with fast reads and writes.

### 13.2 Key

```text
namespace: commerce
set: cart
key: user:u123|cart:active
```

Bins:

```text
items
coupon_code
currency
shipping_address_id
updated_at
version
```

TTL:

```text
anonymous cart: 7-30 days
logged-in cart: 30-90 days
checked-out cart marker: short TTL or archived elsewhere
```

### 13.3 Flow

Add item:

```text
1. Validate product and inventory status.
2. Get cart record.
3. Update bounded items list/map.
4. Use generation check to avoid overwriting concurrent updates.
5. Write cart with TTL refresh.
6. Publish cart_updated event.
```

Read cart:

```text
1. Build user cart key.
2. Aerospike get cart.
3. If missing, return empty cart.
4. Fetch latest prices/inventory from pricing/catalog service or cache.
5. Return cart view.
```

Checkout:

```text
1. Read cart.
2. Validate prices/inventory.
3. Create order in source-of-truth order system.
4. Mark cart as checked_out or delete.
5. Publish checkout event.
```

### 13.4 Pitfalls

- Do not store unlimited cart history in one record.
- Do not trust cached price as final checkout price.
- Use generation/version checks for concurrent cart updates.
- Keep item list bounded.

## 14. Merchant Transaction Dashboard Listing

### 14.1 Question

Can Aerospike be used when merchants do around 100,000 transactions per day and want to see all transactions on a dashboard?

Short answer:

```text
Use Aerospike for transaction lookup, recent summary counters, fraud/risk features, and cache-like dashboard acceleration.
Do not use Aerospike as the primary engine for full transaction dashboard listing, filtering, sorting, and pagination.
```

### 14.2 Why Full Dashboard Listing Is Different

Aerospike is excellent when the request has exact keys:

```text
get transaction by transaction_id
get merchant summary by merchant_id + day
get latest dashboard cache by merchant_id
increment merchant daily counters
```

Dashboard listing usually asks for:

```text
show all transactions for merchant M today
filter by status = FAILED
sort by created_at desc
paginate page 1, page 2, page 3
search by customer/email/order id
export CSV for last 30 days
```

That is a range/list/query workload, not a pure key-value lookup workload.

For one merchant:

```text
100,000 transactions/day
30 days = 3,000,000 rows
```

If the dashboard supports filters, sorting, search, and export, the access pattern becomes closer to OLAP/search/wide-column listing than direct key-value access.

### 14.3 Where Aerospike Fits Well

Aerospike can be used for the operational side:

Transaction detail lookup:

```text
namespace: payments
set: transaction
key: txn:tx_123

bins:
  merchant_id
  amount
  currency
  status
  created_at
  customer_id
  payment_method
```

Merchant daily summary:

```text
key = merchant:m123|summary|day:2026-05-28

bins:
  total_count
  success_count
  failed_count
  total_amount
  refund_count
```

Recent dashboard cache:

```text
key = merchant:m123|dashboard:latest|window:15m

bins:
  recent_txn_ids
  summary_json
  generated_at
```

Fraud/risk velocity:

```text
key = merchant:m123|metric:txn_count|minute:2026-05-28T10:42|bucket:00
```

These are good Aerospike patterns because the keys are exact and bounded.

### 14.4 Where Aerospike Is A Poor Primary Fit

Avoid making Aerospike the only source for:

```text
list all merchant transactions with arbitrary pagination
filter by many columns
sort by created_at across large ranges
search customer/order fields
export millions of rows
run dashboard analytics across months
```

You could try to maintain an index record like:

```text
key = merchant:m123|txns|day:2026-05-28
bin txn_ids = [tx1, tx2, tx3, ... 100k ids]
```

But this is risky:

- One merchant-day record can become large.
- Appending every transaction to one record creates a hot write record.
- Pagination from a huge list becomes awkward.
- Filtering by status/date/customer needs more custom indexes.
- Concurrent updates can create contention.

### 14.5 Recommended Architecture

Use a dual-store design:

```text
Payment Service
  -> write transaction event
  -> Aerospike for hot transaction state / counters / dashboard cache
  -> Kafka/Pulsar event stream
  -> dashboard listing store
  -> Merchant Dashboard API
```

Recommended dashboard listing stores:

| Store | Good for |
|---|---|
| Postgres/MySQL partitioned tables | Strong transactional listing at moderate scale, rich filters. |
| OpenSearch/Elasticsearch | Search/filter dashboard, text lookup, flexible merchant queries. |
| ClickHouse/Pinot/Druid | Analytics, aggregations, exports, large date ranges. |
| ScyllaDB/Cassandra-style wide-column table | Predictable query: merchant + day + time-ordered transactions. |

For 100,000 transactions/day/merchant, a common design is:

```text
Aerospike:
  latest transaction state
  daily counters
  rate/fraud features
  short-lived dashboard cache

ClickHouse/OpenSearch/Postgres/Scylla:
  transaction listing
  filtering
  sorting
  pagination
  export
```

### 14.6 Example Dashboard Listing Model Outside Aerospike

If using a wide-column store:

```text
partition key = merchant_id + day
sort key = created_at desc + transaction_id
```

Query:

```text
merchant = m123
day = 2026-05-28
limit = 50
cursor = last_seen_created_at + last_seen_transaction_id
```

This gives efficient dashboard pagination:

```text
page 1: newest 50 transactions
page 2: next 50 using cursor
```

If using ClickHouse:

```text
ORDER BY (merchant_id, created_date, created_at, transaction_id)
```

Good for:

- dashboard aggregations
- filters
- reporting
- export

If using OpenSearch:

Good for:

- search by customer/order/email
- status filters
- flexible dashboard queries

### 14.7 Final Recommendation

Do not use Aerospike alone for full merchant transaction dashboard listing.

Use Aerospike for:

- `txn_id -> transaction detail`
- merchant daily counters
- payment/fraud velocity features
- recent dashboard summary cache
- hot operational reads

Use another store for:

- merchant transaction list
- date range pagination
- filtering
- sorting
- search
- exports
- long-term reporting

Best production answer:

```text
Aerospike is the low-latency serving/state store.
The dashboard listing store should be query/analytics optimized.
Events keep both stores updated.
```

## 15. Choosing Consistency And TTL By Use Case

| Use case | Typical consistency | TTL |
|---|---|---|
| Session store | AP often acceptable; SC for critical auth | 30 min to 30 days |
| Durable cache | AP | seconds to hours |
| User profile | AP or SC depending correctness | long/no TTL |
| Device state | AP | optional inactivity TTL |
| Fraud features | AP for velocity, SC for critical guardrails if needed | minutes to days |
| Frequency cap | AP commonly | campaign/day window |
| Counters | AP commonly | window based |
| Recommendation lookup | AP | minutes to hours |
| Rate limits | AP for soft limits, stricter design for hard limits | window based |
| Shopping cart | AP or SC based on business risk | days to months |
| Merchant dashboard cache | AP | seconds to minutes |
| Transaction detail lookup | AP or SC based on payment correctness | business retention policy |

## 16. Production Checklist For Every Aerospike Use Case

Before approving a design:

```text
Can the service derive exact keys?
Are keys high-cardinality?
Can any key become hot?
Do hot keys need buckets?
How many buckets are needed?
How does read aggregation work?
What TTL applies?
Is TTL jitter needed?
What consistency mode is required?
What is the replication factor?
What is the record size p50/p99?
What is the record count?
What is primary-index memory usage?
What is peak read/write QPS?
What happens on retry?
Is idempotency required?
What are fallback paths?
What metrics prove correctness?
What alerts detect hotspots?
What system owns long-term history?
```

## 17. Validation And Testing Plan

### 17.1 Functional Tests

```text
session expires after TTL
cache miss populates cache
fraud velocity threshold triggers challenge
rate limit rejects after threshold
cart concurrent updates do not overwrite each other
recommendation fallback works when user candidates missing
```

### 17.2 Load Tests

Test:

```text
normal QPS
peak QPS
viral hot key
hot tenant
node failure
retry storm
TTL expiration burst
cache stampede
```

### 17.3 Correctness Tests

```text
idempotent retry returns same fraud decision
counter buckets sum to expected total
rate limit window expires correctly
shopping cart generation check prevents lost update
frequency cap does not exceed configured threshold beyond acceptable tolerance
```

### 17.4 Observability

Track:

```text
Aerospike read latency p99
Aerospike write latency p99
batch read latency
timeouts
retries
record not found rate
expiration rate
eviction rate
hot key estimates
top tenants
cache hit ratio
fraud decision latency
recommendation candidate hit rate
rate-limit reject rate
cart update conflict rate
```

## 18. Summary

Aerospike works well when you design from keys first.

The common successful pattern is:

```text
request field -> deterministic key -> direct Aerospike read/update -> bounded response
```

For high write workloads, avoid one hot record. Use:

- Time buckets.
- Hash buckets.
- Sharded counters.
- TTL.
- Idempotency records.
- Batch reads for bounded aggregation.
- Async streams for analytics.

For recommendation and fraud systems, Aerospike is the serving store, not the entire intelligence pipeline. Use it to serve fresh operational features at low latency, while event streams and offline/nearline systems compute the features and models.
