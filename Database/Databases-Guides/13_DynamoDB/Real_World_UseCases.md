# Amazon DynamoDB - Real World Use Cases & Production Guide

## Table of Contents
- [Real-World Use Cases](#real-world-use-cases)
- [Core Concepts](#core-concepts)
- [Replication & Durability](#replication--durability)
- [Scalability Architecture](#scalability-architecture)
- [Production Setup](#production-setup)
- [Cost Optimization](#cost-optimization)

---

## Real-World Use Cases

### 1. Amazon.com Shopping Cart (The Original Dynamo Paper)

The 2007 Dynamo paper was written specifically to solve Amazon's shopping cart reliability problem - "customers should always be able to add to cart, even during failures."

```
┌─────────────────────────────────────────────────────────────────┐
│                    Amazon Shopping Cart Flow                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Customer ──► API Gateway ──► Cart Service ──► DynamoDB          │
│     │                              │              │               │
│     │                              ▼              ▼               │
│     │                        Cart Lambda    ┌──────────┐         │
│     │                              │        │ Table:   │         │
│     │                              │        │ Carts    │         │
│     │                              ▼        │          │         │
│     │                        DynamoDB       │ 3 AZs   │         │
│     │                        Streams        │ replicas │         │
│     │                              │        └──────────┘         │
│     │                              ▼                              │
│     │                     Analytics/                              │
│     │                     Recommendations                        │
│     │                                                            │
│     └──── CloudFront ──► S3 (Product Images)                     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Single-Table Design:**

| PK | SK | Attributes |
|---|---|---|
| `USER#u123` | `CART#active` | status, lastModified, itemCount |
| `USER#u123` | `ITEM#asin-001` | qty, price, title, addedAt |
| `USER#u123` | `ITEM#asin-002` | qty, price, title, addedAt |
| `USER#u123` | `CART#2024-01-15` | status=completed, orderRef |

**GSI1 (for abandoned cart analysis):**
| GSI1-PK | GSI1-SK | Projected |
|---|---|---|
| `STATUS#active` | `lastModified` | userId, itemCount, cartValue |

**Access Patterns:**
1. Get active cart for user → Query PK=`USER#u123`, SK begins_with `ITEM#`
2. Add/update item → PutItem with condition expression
3. Checkout → TransactWriteItems (update cart status + create order)
4. Abandoned carts → Query GSI1 PK=`STATUS#active`, SK < 7_days_ago

**DynamoDB Streams Integration:**
- Stream triggers Lambda on cart modifications
- Publishes to EventBridge for recommendation engine
- Feeds abandoned cart email campaigns (items idle > 24hrs)

**Scale & Cost:**
- ~300M active carts during peak (Prime Day)
- Millions of writes/second during flash sales
- On-demand billing: ~$1.25/million writes, ~$0.25/million reads
- Estimated cost: $50K-100K/month for cart service alone

---

### 2. Snap (Snapchat) Stories - 5B+ Snaps/Day

Snapchat migrated from Google Cloud Datastore to DynamoDB for their Stories feature, handling ephemeral content with strict TTL requirements.

```
┌─────────────────────────────────────────────────────────────────┐
│                   Snapchat Stories Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Mobile App ──► CloudFront ──► ALB ──► Stories Service           │
│      │                                      │                    │
│      │              ┌───────────────────────┼──────────┐         │
│      │              │                       ▼          │         │
│      │              │  ┌─────────────────────────┐     │         │
│      │              │  │   DynamoDB (Stories)     │     │         │
│      │              │  │                         │     │         │
│      │              │  │  On-Demand Capacity     │     │         │
│      │              │  │  TTL: 24hrs (Stories)   │     │         │
│      │              │  │  TTL: 10s (Snaps)       │     │         │
│      │              │  └────────┬────────────────┘     │         │
│      │              │           │                      │         │
│      │              │           ▼ Streams              │         │
│      │              │     ┌──────────┐                 │         │
│      │              │     │  Lambda   │──► S3 Archive  │         │
│      │              │     └──────────┘                 │         │
│      │              │                                  │         │
│      │              │  DAX Cluster (read-heavy feeds)  │         │
│      │              └──────────────────────────────────┘         │
│      │                                                           │
│      └──► S3 (media blobs, encrypted, lifecycle policy)          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Single-Table Design:**

| PK | SK | TTL | Attributes |
|---|---|---|---|
| `USER#u456` | `STORY#2024-01-20T10:30:00` | +24hrs | mediaRef, viewCount, filters |
| `USER#u456` | `STORY#2024-01-20T11:00:00` | +24hrs | mediaRef, viewCount, filters |
| `STORY#s789` | `VIEW#u111` | +48hrs | viewedAt, screenshotted |
| `STORY#s789` | `META` | +24hrs | creatorId, duration, type |

**GSI1 (Feed generation - friends' stories):**
| GSI1-PK | GSI1-SK | Projected |
|---|---|---|
| `FRIEND_CIRCLE#fc001` | `createdAt` | userId, storyId, thumbnail |

**GSI2 (Discover/trending):**
| GSI2-PK | GSI2-SK | Projected |
|---|---|---|
| `REGION#us-east` | `viewCount` | storyId, creatorId, category |

**Access Patterns:**
1. Post story → PutItem with 24hr TTL
2. Get friend stories feed → Query GSI1, filter active stories
3. Record view → UpdateItem with ADD for atomic counter
4. Expire content → TTL auto-deletion (no write cost!)
5. Trending stories → Query GSI2 by region

**DynamoDB Streams Integration:**
- View counter aggregation (batch updates to avoid hot keys)
- Notification fan-out when friends post
- Analytics pipeline to Kinesis → Redshift
- Content moderation trigger (ML inference on new posts)

**Scale & Cost:**
- 5B+ snaps/day = ~58,000 writes/second sustained, 200K+ peak
- Read amplification for feeds: ~500K reads/second
- DAX reduces DynamoDB reads by 90% for feed queries
- TTL deletes ~5B items/day at zero write cost
- Estimated: $200K-500K/month (DynamoDB + DAX)
- Storage is minimal due to TTL (media in S3)

---

### 3. Lyft Ride Matching - Single-Digit Millisecond Latency

Lyft uses DynamoDB for real-time geospatial ride matching where latency directly impacts rider wait time and driver utilization.

```
┌─────────────────────────────────────────────────────────────────┐
│                  Lyft Ride Matching Architecture                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Rider App ──► API GW ──► Matching Service                       │
│                                 │                                │
│                    ┌────────────┼────────────────┐               │
│                    │            ▼                │               │
│                    │   ┌────────────────┐        │               │
│  Driver App ──►    │   │  DynamoDB      │        │               │
│  (location         │   │  (Drivers)     │        │               │
│   updates          │   │               │        │               │
│   every 4s) ──►    │   │  + DAX Cache   │        │               │
│                    │   └───────┬────────┘        │               │
│                    │           │                  │               │
│                    │           ▼                  │               │
│                    │   ┌────────────────┐        │               │
│                    │   │  DynamoDB      │        │               │
│                    │   │  (Rides)       │        │               │
│                    │   └───────┬────────┘        │               │
│                    │           │ Streams          │               │
│                    │           ▼                  │               │
│                    │   Lambda ──► Kinesis         │               │
│                    │         ──► Pricing Service  │               │
│                    │         ──► ETA Service      │               │
│                    └─────────────────────────────┘               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Single-Table Design (Drivers Table):**

| PK | SK | Attributes |
|---|---|---|
| `GEOHASH#9q8yy` | `DRIVER#d001` | lat, lng, status, vehicleType, heading, speed |
| `GEOHASH#9q8yy` | `DRIVER#d002` | lat, lng, status, vehicleType, heading, speed |
| `GEOHASH#9q8yz` | `DRIVER#d003` | lat, lng, status, vehicleType, heading, speed |
| `DRIVER#d001` | `PROFILE` | name, rating, vehicleInfo, documents |
| `DRIVER#d001` | `RIDE#r555` | riderId, pickup, dropoff, status, fare |

**GSI1 (Driver by status):**
| GSI1-PK | GSI1-SK | Projected |
|---|---|---|
| `STATUS#available#CITY#sf` | `rating` | driverId, geohash, vehicleType |

**Access Patterns:**
1. Find nearby drivers → Query PK=`GEOHASH#<prefix>` (adjacent cells too)
2. Update driver location → UpdateItem (every 4 seconds per driver)
3. Match ride → TransactWriteItems (assign driver + create ride atomically)
4. Get ride status → GetItem PK=`DRIVER#d001`, SK=`RIDE#r555`
5. Driver history → Query PK=`DRIVER#d001`, SK begins_with `RIDE#`

**Geohash Strategy:**
- Use geohash precision 5 (~5km cells) as PK
- Query adjacent 8 cells for boundary coverage
- Drivers update their geohash PK on cell transitions
- Condition expression prevents double-assignment

**DynamoDB Streams Integration:**
- Location updates trigger surge pricing recalculation
- Ride state changes push notifications to rider/driver
- Completed rides feed billing service
- Analytics for supply/demand heatmaps

**Scale & Cost:**
- ~2M active drivers, location update every 4s = 500K writes/second
- Matching queries: ~100K reads/second with <5ms p99 via DAX
- Provisioned capacity with auto-scaling (predictable patterns)
- Write: 500K WCU × $0.00065/hr = ~$325/hr = ~$234K/month
- DAX: 5x r5.large nodes = ~$3K/month
- Total estimated: ~$250K/month

---

### 4. Capital One Banking - Account Data with ACID Transactions

Capital One is one of DynamoDB's largest enterprise customers, running core banking workloads that require transactional consistency.

```
┌─────────────────────────────────────────────────────────────────┐
│              Capital One Banking Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Mobile/Web ──► API GW ──► Lambda (Authorizer)                   │
│                                │                                 │
│                                ▼                                 │
│                    ┌───────────────────────┐                     │
│                    │   Account Service     │                     │
│                    │   (ECS Fargate)       │                     │
│                    └───────────┬───────────┘                     │
│                                │                                 │
│         ┌──────────────────────┼──────────────────┐             │
│         │                      │                  │             │
│         ▼                      ▼                  ▼             │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  DynamoDB   │    │  DynamoDB    │    │  DynamoDB    │       │
│  │  Accounts   │    │  Transactions│    │  Customers   │       │
│  │             │    │              │    │              │       │
│  │  Encrypted  │    │  Encrypted   │    │  Encrypted   │       │
│  │  at rest    │    │  at rest     │    │  at rest     │       │
│  └──────┬──────┘    └──────┬───────┘    └──────────────┘       │
│         │                  │                                     │
│         │  Streams         │  Streams                            │
│         ▼                  ▼                                     │
│  ┌─────────────────────────────────┐                            │
│  │  Lambda ──► Fraud Detection     │                            │
│  │         ──► Compliance Audit    │                            │
│  │         ──► Real-time Alerts    │                            │
│  └─────────────────────────────────┘                            │
│                                                                   │
│  Global Tables: us-east-1 ◄──► us-west-2 (DR)                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Single-Table Design (Accounts):**

| PK | SK | Attributes |
|---|---|---|
| `CUST#c001` | `ACCOUNT#checking-001` | balance, status, openDate, branch |
| `CUST#c001` | `ACCOUNT#savings-001` | balance, status, interestRate |
| `CUST#c001` | `PROFILE` | name, ssn(encrypted), address, kycStatus |
| `ACCT#checking-001` | `TXN#2024-01-20T10:30:00#t001` | amount, type, merchant, balance_after |
| `ACCT#checking-001` | `TXN#2024-01-20T11:00:00#t002` | amount, type, merchant, balance_after |
| `ACCT#checking-001` | `MONTHLY#2024-01` | openBalance, closeBalance, txnCount |

**GSI1 (Transaction lookup by reference):**
| GSI1-PK | GSI1-SK | Projected |
|---|---|---|
| `TXN_REF#ref-abc-123` | `ACCT#checking-001` | amount, date, status |

**GSI2 (Compliance - transactions by date range):**
| GSI2-PK | GSI2-SK | Projected |
|---|---|---|
| `ACCT#checking-001` | `date#amount` | txnId, type, merchant |

**ACID Transaction Example (Transfer between accounts):**
```
TransactWriteItems:
  - Update ACCT#checking-001 balance -= $500
    ConditionExpression: balance >= 500
  - Update ACCT#savings-001 balance += $500
  - Put TXN record for checking (debit)
  - Put TXN record for savings (credit)
  - Update daily aggregate for both accounts
```
All 5 operations succeed or all fail. 25-item limit per transaction.

**Access Patterns:**
1. View account balance → GetItem (strongly consistent)
2. Transfer funds → TransactWriteItems (up to 25 items)
3. Transaction history → Query with SK begins_with `TXN#`, ScanIndexForward=false
4. Monthly statement → Query SK begins_with `TXN#2024-01`
5. Fraud check → Stream triggers real-time ML scoring

**DynamoDB Streams Integration:**
- Every transaction triggers fraud detection Lambda (<100ms)
- Compliance audit trail (immutable, shipped to S3 Glacier)
- Real-time balance alerts (low balance, large transactions)
- Regulatory reporting aggregation

**Scale & Cost:**
- Tens of millions of accounts
- ~50K transactions/second peak
- Strongly consistent reads for balance checks
- Provisioned with reserved capacity (3-year term: 77% savings)
- Encryption: AWS KMS CMK (customer-managed keys)
- Estimated: $300K-800K/month (with reserved capacity discounts)
- Compliance: SOC2, PCI-DSS, HIPAA all supported

---

### 5. Duolingo User Progress - 500M+ Users Learning Progress

Duolingo stores all user learning progress, streaks, XP, and lesson state in DynamoDB, enabling their gamification engine.

```
┌─────────────────────────────────────────────────────────────────┐
│                Duolingo Learning Platform                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Mobile/Web ──► CloudFront ──► ALB ──► Learning Service          │
│       │                                     │                    │
│       │              ┌──────────────────────┼──────────┐         │
│       │              │                      ▼          │         │
│       │              │  ┌────────────────────────┐     │         │
│       │              │  │  DynamoDB              │     │         │
│       │              │  │  (User Progress)       │     │         │
│       │              │  │                        │     │         │
│       │              │  │  On-Demand Capacity    │     │         │
│       │              │  │  Global Tables:        │     │         │
│       │              │  │  us-east-1, eu-west-1  │     │         │
│       │              │  │  ap-southeast-1        │     │         │
│       │              │  └───────────┬────────────┘     │         │
│       │              │              │                   │         │
│       │              │              ▼ Streams           │         │
│       │              │  ┌────────────────────────┐     │         │
│       │              │  │  Lambda Functions       │     │         │
│       │              │  │  - Streak Calculator    │     │         │
│       │              │  │  - Leaderboard Update   │     │         │
│       │              │  │  - Achievement Unlock   │     │         │
│       │              │  │  - Push Notifications   │     │         │
│       │              │  └────────────────────────┘     │         │
│       │              │                                  │         │
│       │              │  DAX (lesson content caching)    │         │
│       │              └──────────────────────────────────┘         │
│       │                                                           │
│       └──► S3 (audio files, images)                              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Single-Table Design:**

| PK | SK | Attributes |
|---|---|---|
| `USER#u789` | `PROFILE` | username, streak, totalXP, gems, tier, joinDate |
| `USER#u789` | `COURSE#es` | level, xp, crowns, lessonsCompleted |
| `USER#u789` | `COURSE#fr` | level, xp, crowns, lessonsCompleted |
| `USER#u789` | `LESSON#es#basics-1#3` | score, mistakes, timeSpent, completedAt |
| `USER#u789` | `STREAK#2024-01-20` | xpEarned, lessonsCount, practiceMinutes |
| `USER#u789` | `STREAK#2024-01-19` | xpEarned, lessonsCount, practiceMinutes |
| `LEAGUE#diamond#week-2024-03` | `RANK#00001#USER#u789` | xpThisWeek, username |
| `LEAGUE#diamond#week-2024-03` | `RANK#00002#USER#u222` | xpThisWeek, username |

**GSI1 (Leaderboard by league):**
| GSI1-PK | GSI1-SK | Projected |
|---|---|---|
| `LEAGUE#diamond#week-2024-03` | `xpThisWeek` | userId, username, avatar |

**GSI2 (User lookup by username):**
| GSI2-PK | GSI2-SK | Projected |
|---|---|---|
| `USERNAME#duo_learner` | `USER#u789` | totalXP, streak, tier |

**Access Patterns:**
1. Load user home screen → Query PK=`USER#u789` (get all user data in one query)
2. Complete lesson → TransactWriteItems (update XP + streak + course progress)
3. Check streak → Query PK=`USER#u789`, SK begins_with `STREAK#`, limit 1, reverse
4. Weekly leaderboard → Query GSI1 PK=`LEAGUE#diamond#week-2024-03`, limit 30
5. Friend progress → BatchGetItem for friend user IDs

**DynamoDB Streams Integration:**
- Lesson completion → Achievement evaluation Lambda
- XP change → Leaderboard position update
- Streak at risk (no activity by 8pm) → Push notification trigger
- A/B test event logging → Kinesis → analytics

**Scale & Cost:**
- 500M+ registered users, ~30M DAU
- Peak: lesson completions at ~200K writes/second (global)
- Reads: ~1M/second (home screen loads, progress checks)
- On-demand capacity (unpredictable viral growth spikes)
- Global Tables across 3 regions for low-latency worldwide
- DAX for lesson content: reduces read cost by 80%
- Estimated: $150K-300K/month
- Storage: ~50TB (sparse attributes keep per-user cost low)

---

## Core Concepts

### Partition Key Hashing

DynamoDB uses a hash function (MD5-based) on the partition key to determine which physical partition stores the item.

```
Partition Key ──► Hash Function ──► Hash Value ──► Partition Assignment

Example:
  "USER#u123"  ──► MD5 ──► 0x7A3F...  ──► Partition 7 (of N)
  "USER#u456"  ──► MD5 ──► 0x2B1C...  ──► Partition 2 (of N)
  "USER#u789"  ──► MD5 ──► 0x7A41...  ──► Partition 7 (of N)

┌─────────────────────────────────────────────────────────┐
│                    Hash Ring                              │
│                                                          │
│  Partition 1    Partition 2    ...    Partition N         │
│  ┌─────────┐   ┌─────────┐         ┌─────────┐        │
│  │ Items   │   │ Items   │         │ Items   │        │
│  │ sorted  │   │ sorted  │         │ sorted  │        │
│  │ by SK   │   │ by SK   │         │ by SK   │        │
│  │(B-tree) │   │(B-tree) │         │(B-tree) │        │
│  └─────────┘   └─────────┘         └─────────┘        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### B-Tree Within Partitions

Within each partition, items sharing the same partition key are stored in a B-tree sorted by the sort key. This enables efficient range queries on the sort key.

```
Partition for PK = "USER#u123"
            ┌─────────────────────┐
            │   B-Tree Root       │
            │   SK: COURSE#fr     │
            └──────┬──────┬───────┘
                   │      │
         ┌─────────┘      └──────────┐
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│ SK: CART#active │        │ SK: LESSON#...  │
│ SK: COURSE#es  │        │ SK: PROFILE     │
│ SK: COURSE#fr  │        │ SK: STREAK#...  │
└─────────────────┘        └─────────────────┘
```

This is why `begins_with`, `between`, `>`, `<` work on sort keys but NOT on partition keys.

### Eventually vs Strongly Consistent Reads

| Aspect | Eventually Consistent | Strongly Consistent |
|---|---|---|
| Latency | Lower (~2-5ms) | Higher (~5-10ms) |
| Cost | 1x (default) | 2x RCU consumption |
| Staleness | Up to 1 second | Always latest |
| Availability | Higher (reads from any replica) | Lower (reads from leader) |
| Use case | Feeds, analytics, caching | Balances, inventory, counters |

```
Write ──► Leader Replica (AZ-1)
              │
              ├──► Follower (AZ-2)  [async, ~ms delay]
              │
              └──► Follower (AZ-3)  [async, ~ms delay]

Eventually Consistent Read: Can hit any replica (may get stale data)
Strongly Consistent Read: Must hit leader (always current)
```

### Transactions (TransactWriteItems / TransactGetItems)

- Up to 100 items per transaction (reads) or 25 items (writes)
- All-or-nothing semantics across multiple items/tables
- 2x WCU cost (prepare + commit phases)
- Serializable isolation level
- Idempotent with client tokens

```
TransactWriteItems Example (Fund Transfer):
┌────────────────────────────────────────────────┐
│  1. Update: Account-A balance -= $100          │
│     Condition: balance >= 100                  │
│                                                │
│  2. Update: Account-B balance += $100          │
│                                                │
│  3. Put: Transaction record (debit)            │
│                                                │
│  4. Put: Transaction record (credit)           │
│                                                │
│  Result: ALL succeed OR ALL fail               │
│  Cost: 2x normal WCU for each operation        │
└────────────────────────────────────────────────┘
```

### Condition Expressions

Prevent race conditions with server-side conditional logic:

```
// Optimistic locking
UpdateItem:
  Key: {PK: "ITEM#001", SK: "META"}
  UpdateExpression: "SET stock = stock - 1"
  ConditionExpression: "stock > 0 AND version = :expected_version"

// Idempotent writes
PutItem:
  ConditionExpression: "attribute_not_exists(PK)"

// Compare-and-swap
UpdateItem:
  ConditionExpression: "status = :expected_status"
  UpdateExpression: "SET status = :new_status"
```

### Single-Table vs Multi-Table Design

| Aspect | Single-Table | Multi-Table |
|---|---|---|
| Queries | Fewer, broader | More, targeted |
| Complexity | High (requires upfront planning) | Lower (familiar relational thinking) |
| Cost | Lower (fewer tables, fewer GSIs) | Higher (more GSIs, more tables) |
| Flexibility | Harder to evolve | Easier to modify |
| Team | Needs DynamoDB expertise | Accessible to broader team |
| Best for | High-scale, stable access patterns | Evolving apps, microservices |

**When to use single-table:** You know all access patterns upfront, performance is critical, team has DynamoDB expertise.

**When to use multi-table:** Microservice boundaries, evolving access patterns, team familiarity, or using DynamoDB as one of several data stores.

---

## Replication & Durability

### Multi-AZ (Automatic - 3 AZs)

Every DynamoDB table automatically replicates across 3 Availability Zones within a region. This is not configurable - it's built-in.

```
┌──────────────── Region: us-east-1 ────────────────┐
│                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │  AZ-1    │    │  AZ-2    │    │  AZ-3    │    │
│  │ (Leader) │    │(Follower)│    │(Follower)│    │
│  │          │    │          │    │          │    │
│  │ Full     │◄──►│ Full     │◄──►│ Full     │    │
│  │ Replica  │    │ Replica  │    │ Replica  │    │
│  └──────────┘    └──────────┘    └──────────┘    │
│                                                    │
│  Write: Acknowledged after 2/3 replicas confirm    │
│  Read (eventual): Any replica                      │
│  Read (strong): Leader only                        │
│                                                    │
│  Durability: 99.999999999% (11 9s)                │
│  Availability: 99.999% (table class)              │
└────────────────────────────────────────────────────┘
```

### Global Tables (Active-Active Multi-Region)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Global Tables v2 (2019+)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐                      │
│  │ us-east-1    │◄───────►│ eu-west-1    │                      │
│  │              │         │              │                      │
│  │ Read/Write   │         │ Read/Write   │                      │
│  │ Full replica │         │ Full replica │                      │
│  └──────┬───────┘         └──────┬───────┘                      │
│         │                        │                               │
│         │    ┌──────────────┐    │                               │
│         └───►│ ap-south-1   │◄───┘                               │
│              │              │                                    │
│              │ Read/Write   │                                    │
│              │ Full replica │                                    │
│              └──────────────┘                                    │
│                                                                   │
│  Replication latency: typically <1 second                        │
│  Conflict resolution: Last Writer Wins (by timestamp)            │
│  Cost: Normal WCU in source + rWCU in each replica               │
│  Replica WCU cost = 1.5x normal WCU                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key characteristics:**
- Active-active: Read AND write to any region
- Replication typically <1 second (not guaranteed)
- Each region maintains its own capacity independently
- Streams required (automatically enabled)

### DynamoDB Streams

```
┌────────────────────────────────────────────────────────┐
│                  DynamoDB Streams                        │
├────────────────────────────────────────────────────────┤
│                                                         │
│  Table Write ──► Stream Record (ordered, per-item)      │
│                                                         │
│  Stream View Types:                                     │
│  ┌─────────────────────────────────────────────┐       │
│  │ KEYS_ONLY      - Only PK/SK                  │       │
│  │ NEW_IMAGE      - Full item after change      │       │
│  │ OLD_IMAGE      - Full item before change     │       │
│  │ NEW_AND_OLD    - Both (most flexible)        │       │
│  └─────────────────────────────────────────────┘       │
│                                                         │
│  Retention: 24 hours                                    │
│  Ordering: Per-item guaranteed                          │
│  Consumers: Lambda, Kinesis Adapter, Custom             │
│  Shards: ~1 per 1000 WCU                              │
│                                                         │
│  Common Patterns:                                       │
│  - Event sourcing / CDC                                │
│  - Cross-region replication (Global Tables use this)   │
│  - Materialized views (aggregate tables)               │
│  - Elasticsearch sync                                  │
│  - Audit trails                                        │
│  - Cache invalidation                                  │
│                                                         │
└────────────────────────────────────────────────────────┘
```

### Conflict Resolution (Last Writer Wins)

Global Tables use a last-writer-wins strategy based on timestamps:

```
Region A writes: {PK: "user1", name: "Alice"} at T=100
Region B writes: {PK: "user1", name: "Bob"}   at T=101

Result in ALL regions: {PK: "user1", name: "Bob"}  (T=101 wins)
```

**Implications:**
- No application-level merge logic
- Clock skew could cause unexpected results (AWS uses NTP sync)
- Design tip: Avoid concurrent writes to same item from multiple regions
- Pattern: Route users to "home region" for writes, read from nearest

### Point-in-Time Recovery (PITR)

- Continuous backups with 1-second granularity
- Restore to any point in last 35 days
- Restores to a NEW table (doesn't overwrite existing)
- No performance impact on source table
- Cost: ~$0.20/GB/month (of table size)
- Recovery time: varies by table size (minutes to hours)

---

## Scalability Architecture

### Partition Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                   Partition Limits                               │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Each partition:                                                  │
│  ┌────────────────────────────────────────┐                     │
│  │  Max Storage:  10 GB                    │                     │
│  │  Max Read:     3,000 RCU               │                     │
│  │  Max Write:    1,000 WCU               │                     │
│  │  Max Item:     400 KB                   │                     │
│  └────────────────────────────────────────┘                     │
│                                                                  │
│  Number of partitions = MAX(                                     │
│    Capacity: (RCU/3000) + (WCU/1000),                           │
│    Storage:  TableSize / 10GB                                    │
│  )                                                               │
│                                                                  │
│  Example: Table with 10,000 RCU + 5,000 WCU + 80GB             │
│    By capacity: (10000/3000) + (5000/1000) = 3.3 + 5 = 9       │
│    By storage:  80/10 = 8                                        │
│    Result: 9 partitions                                          │
│                                                                  │
│  IMPORTANT: Partitions only split, never merge!                  │
│  (This is why over-provisioning then scaling down can be costly) │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Adaptive Capacity

```
┌────────────────────────────────────────────────────────────────┐
│              Adaptive Capacity (Automatic)                       │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Before (uniform distribution required):                         │
│                                                                  │
│  Table: 10,000 WCU across 10 partitions = 1,000 WCU each       │
│  Partition "hot_key" needs 2,000 WCU → THROTTLED!               │
│                                                                  │
│  After (adaptive capacity):                                      │
│                                                                  │
│  DynamoDB "borrows" unused capacity from cold partitions:        │
│                                                                  │
│  Partition 1 (hot):  2,500 WCU  ←── borrowed from others        │
│  Partition 2 (cold):   500 WCU                                   │
│  Partition 3 (cold):   500 WCU                                   │
│  ...                                                             │
│  Total still = 10,000 WCU                                        │
│                                                                  │
│  Instant Adaptive Capacity (2019+):                              │
│  - Kicks in immediately (previously took 5-30 min)              │
│  - Can boost a partition up to table-level throughput            │
│  - Isolates hot items onto their own partitions automatically   │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Hot Partition Mitigation Strategies

```
Problem: A single partition key receives disproportionate traffic

Strategies:
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  1. Write Sharding (distribute hot key)                      │
│     PK: "COUNTER#page_views#<random_suffix_0-9>"            │
│     Read: Query all 10 shards, sum client-side              │
│                                                              │
│  2. Caching with DAX                                         │
│     Hot reads → DAX absorbs 90%+ of read load              │
│                                                              │
│  3. Time-based partitioning                                  │
│     PK: "SENSOR#s001#2024-01-20"                            │
│     Naturally distributes across time                        │
│                                                              │
│  4. Composite keys                                           │
│     Instead of: PK="COUNTRY#US"                             │
│     Use: PK="COUNTRY#US#STATE#CA"                           │
│                                                              │
│  5. On-demand mode                                           │
│     Handles spikes up to 2x previous peak instantly         │
│     Scales to any level within minutes                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### DAX (DynamoDB Accelerator) Caching Layer

```
┌────────────────────────────────────────────────────────────────┐
│                     DAX Architecture                             │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Application ──► DAX Cluster ──► DynamoDB                       │
│       │              │                                          │
│       │         ┌────┴────┐                                     │
│       │         │         │                                     │
│       │     ┌───┴───┐ ┌───┴───┐                                │
│       │     │Primary│ │Replica│  (3-11 nodes)                  │
│       │     │ Node  │ │ Nodes │                                │
│       │     └───────┘ └───────┘                                │
│       │                                                         │
│       │  Two caches:                                            │
│       │  ┌──────────────────────────────────────┐              │
│       │  │ Item Cache: GetItem/BatchGetItem     │              │
│       │  │   TTL: 5 min default                  │              │
│       │  │   LRU eviction                        │              │
│       │  │                                       │              │
│       │  │ Query Cache: Query/Scan results       │              │
│       │  │   TTL: 5 min default                  │              │
│       │  │   Full result set cached              │              │
│       │  └──────────────────────────────────────┘              │
│       │                                                         │
│       │  Write-through: Writes go to DDB first, then DAX       │
│       │  Read: DAX first, miss → DDB → populate cache          │
│       │                                                         │
│  Latency: <1ms reads (vs 2-10ms DynamoDB direct)               │
│  Cost: ~$0.27/hr per node (r5.large)                           │
│  NOT suitable for: Strong consistency, write-heavy workloads    │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### On-Demand vs Provisioned Capacity

| Aspect | On-Demand | Provisioned |
|---|---|---|
| Pricing | Per-request ($1.25/M writes, $0.25/M reads) | Per-hour ($0.00065/WCU-hr, $0.00013/RCU-hr) |
| Scaling | Instant (to 2x previous peak) | Auto-scaling (minutes to react) |
| Minimum cost | $0 (pay only for usage) | Reserved capacity minimum |
| Best for | Unpredictable traffic, new tables, spiky | Steady, predictable traffic |
| Cost crossover | ~14.4% utilization breakeven | Cheaper above ~14.4% sustained |
| Burst | 2x previous peak instantly, unlimited within minutes | Burst pool: 300 seconds of unused capacity |

**Cost comparison example (100K writes/second sustained):**
- On-demand: 100K × 3600 × 24 × 30 / 1M × $1.25 = ~$324K/month
- Provisioned: 100K WCU × $0.00065 × 720 hrs = ~$47K/month
- Reserved (1yr): ~$30K/month (36% savings)
- Reserved (3yr): ~$18K/month (77% savings)

---

## Production Setup

### Single-Table Design Methodology

**Step-by-step approach:**

1. **List all entities** (User, Order, Product, Review...)
2. **Define access patterns** (all queries your app needs)
3. **Design PK/SK schema** to satisfy access patterns
4. **Add GSIs** for access patterns not covered by base table
5. **Validate** with sample data

```
Entity-Chart Method:
┌────────────────────────────────────────────────────────┐
│ Access Pattern          │ Key Condition    │ Index     │
├─────────────────────────┼──────────────────┼───────────┤
│ Get user profile        │ PK=USER#id       │ Table     │
│                         │ SK=PROFILE       │           │
│ Get user orders         │ PK=USER#id       │ Table     │
│                         │ SK begins ORDR#  │           │
│ Get order by ID         │ PK=ORDR#id       │ Table     │
│                         │ SK=META          │           │
│ Orders by date (all)    │ GSI1-PK=STATUS   │ GSI1      │
│                         │ GSI1-SK=date     │           │
│ Product reviews         │ PK=PROD#id       │ Table     │
│                         │ SK begins REV#   │           │
└────────────────────────────────────────────────────────┘
```

### GSI/LSI Design

**GSI (Global Secondary Index):**
- Different partition key than base table
- Eventually consistent only
- Has its own provisioned capacity
- Max 20 GSIs per table
- Can be added/removed anytime
- Projects selected attributes (ALL, KEYS_ONLY, INCLUDE)

**LSI (Local Secondary Index):**
- Same partition key, different sort key
- Supports strongly consistent reads
- Shares capacity with base table
- Max 5 LSIs per table
- Must be created at table creation time (cannot add later!)
- 10GB limit per partition key value

**GSI Overloading Pattern:**
```
GSI1-PK and GSI1-SK contain different entity types:

| PK         | SK           | GSI1-PK            | GSI1-SK        |
|------------|--------------|--------------------|--------------  |
| USER#u1    | PROFILE      | EMAIL#a@b.com      | USER#u1        |
| USER#u1    | ORDER#o1     | STATUS#shipped     | 2024-01-20     |
| PROD#p1    | META         | CATEGORY#electronics| price#299      |
```

### TTL (Time-to-Live) Cleanup

```
┌────────────────────────────────────────────────────────┐
│                   TTL Best Practices                     │
├────────────────────────────────────────────────────────┤
│                                                         │
│  • Attribute must be Number type (Unix epoch seconds)   │
│  • DynamoDB deletes within ~48 hours of expiry          │
│    (not instant! Plan for stale reads)                  │
│  • NO WCU cost for TTL deletions                        │
│  • TTL deletions appear in Streams (for cleanup logic)  │
│  • Filter expired items in queries until actually deleted│
│                                                         │
│  Use cases:                                             │
│  - Session tokens (expire after 24hrs)                  │
│  - Ephemeral messages (Snapchat-style)                  │
│  - Cart abandonment (expire after 7 days)              │
│  - Log/event data (retain 90 days)                     │
│  - Rate limiting windows                                │
│                                                         │
│  Filter expression for safety:                          │
│  FilterExpression: "ttl > :now OR attribute_not_exists(ttl)"│
│                                                         │
└────────────────────────────────────────────────────────┘
```

### Streams + Lambda Patterns

```
┌────────────────────────────────────────────────────────────────┐
│              Common Stream + Lambda Patterns                     │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Aggregation (materialized views)                            │
│     Order created → Lambda → Update daily sales total            │
│                                                                  │
│  2. Cross-service events                                         │
│     User signup → Lambda → EventBridge → Email + Analytics       │
│                                                                  │
│  3. Search sync                                                  │
│     Item change → Lambda → OpenSearch/Elasticsearch              │
│                                                                  │
│  4. Audit log                                                    │
│     Any change → Lambda → S3 (immutable audit trail)            │
│                                                                  │
│  5. Cache invalidation                                           │
│     Item update → Lambda → Invalidate CloudFront/Redis          │
│                                                                  │
│  Lambda configuration:                                           │
│  - BatchSize: 100-1000 (balance latency vs efficiency)          │
│  - MaximumBatchingWindowInSeconds: 0-300                        │
│  - StartingPosition: TRIM_HORIZON or LATEST                     │
│  - MaximumRetryAttempts: 1-10000                                │
│  - BisectBatchOnFunctionError: true                             │
│  - ParallelizationFactor: 1-10                                  │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Backup Strategy

| Method | RPO | RTO | Cost | Use Case |
|---|---|---|---|---|
| On-demand backup | Point-in-time snapshot | Hours (size-dependent) | $0.10/GB (backup) + $0.15/GB (restore) | Manual snapshots before deployments |
| PITR | 1 second | Minutes-hours | $0.20/GB/month | Continuous protection, accidental deletes |
| Export to S3 | Snapshot time | N/A (for analytics) | $0.11/GB | Analytics, cross-account, long-term archive |
| Global Tables | <1 second (regional failure) | Seconds (DNS failover) | rWCU cost | Regional disaster recovery |

### Cost Optimization

```
┌────────────────────────────────────────────────────────────────┐
│                  Cost Optimization Checklist                     │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Right-size capacity mode                                     │
│     □ On-demand: <14.4% utilization OR unpredictable            │
│     □ Provisioned: >14.4% sustained utilization                 │
│     □ Reserved: Steady baseline (1yr: 36%, 3yr: 77% savings)   │
│                                                                  │
│  2. Reduce item size                                             │
│     □ Short attribute names (saves storage + RCU/WCU)           │
│     □ Compress large values (gzip before storing)               │
│     □ Store large blobs in S3, reference in DynamoDB            │
│     □ Remove redundant attributes                               │
│                                                                  │
│  3. Optimize reads                                               │
│     □ Use eventually consistent reads where possible (50% off)  │
│     □ DAX for read-heavy workloads                              │
│     □ Project only needed attributes (ProjectionExpression)     │
│     □ Avoid Scan operations                                     │
│                                                                  │
│  4. Optimize writes                                              │
│     □ Batch writes (BatchWriteItem: 25 items)                   │
│     □ Smaller items = fewer WCUs (1 WCU = 1KB write)           │
│     □ Avoid unnecessary updates                                  │
│                                                                  │
│  5. TTL for data lifecycle                                       │
│     □ Auto-delete old data (no WCU cost!)                       │
│     □ Archive to S3 before TTL via Streams                      │
│                                                                  │
│  6. GSI optimization                                             │
│     □ Project only needed attributes (not ALL)                  │
│     □ Sparse indexes (only items with GSI keys get indexed)     │
│     □ Remove unused GSIs                                         │
│                                                                  │
│  7. Table class                                                   │
│     □ Standard: Frequent access                                  │
│     □ Standard-IA: Infrequent access (60% lower storage cost,   │
│        25% higher read/write cost)                               │
│                                                                  │
│  Pricing Summary (us-east-1):                                    │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ On-demand writes:     $1.25  per million              │       │
│  │ On-demand reads:      $0.25  per million              │       │
│  │ Provisioned WCU:      $0.00065 per WCU-hour          │       │
│  │ Provisioned RCU:      $0.00013 per RCU-hour          │       │
│  │ Storage:              $0.25  per GB/month             │       │
│  │ Streams:              $0.02  per 100K read requests   │       │
│  │ Global Tables rWCU:   $1.875 per million (on-demand)  │       │
│  │ PITR:                 $0.20  per GB/month             │       │
│  │ DAX (r5.large):       $0.269 per hour per node       │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────────┐
│                DynamoDB Limits Quick Reference                   │
├────────────────────────────────────────────────────────────────┤
│  Max item size:              400 KB                              │
│  Max partition key:          2048 bytes                          │
│  Max sort key:               1024 bytes                          │
│  Max GSIs per table:         20                                  │
│  Max LSIs per table:         5                                   │
│  Max items per transaction:  100 (read) / 25 (write)            │
│  Max BatchGetItem:           100 items / 16 MB                   │
│  Max BatchWriteItem:         25 items / 16 MB                    │
│  Max Query/Scan response:    1 MB (paginate for more)           │
│  Partition throughput:       3000 RCU + 1000 WCU                │
│  Partition storage:          10 GB                               │
│  Max table size:             Unlimited                           │
│  Max item count:             Unlimited                           │
│  Stream retention:           24 hours                            │
│  PITR retention:             35 days                             │
│  On-demand burst:            2x previous peak (instant)          │
│  Account default limits:     40,000 RCU + 40,000 WCU/region    │
│  Consistent read unit:       4 KB (strong) / 8 KB (eventual)   │
│  Write unit:                 1 KB                                │
└────────────────────────────────────────────────────────────────┘
```

---

## When NOT to Use DynamoDB

- Complex ad-hoc queries (use PostgreSQL/MySQL)
- Full-text search (use OpenSearch/Elasticsearch)
- Graph traversals (use Neptune)
- OLAP/analytics (use Redshift/Athena)
- Strong consistency across items without transactions
- Data models that change frequently without known access patterns
- Small datasets with complex relationships (<1GB, many JOINs)
