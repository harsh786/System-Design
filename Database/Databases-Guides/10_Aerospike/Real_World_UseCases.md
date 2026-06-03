# Aerospike - Real World Use Cases & Production Guide

## Table of Contents
- [Real-World Use Cases](#real-world-use-cases)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)
- [Core Concepts](#core-concepts)

---

## Real-World Use Cases

---

### 1. The Trade Desk - Real-Time Ad Bidding

**Problem:** Respond to ad bid requests in <10ms with user profile lookups across 600B+ records globally.

**Why Aerospike:**
- Sub-millisecond reads for user segment lookups
- Hybrid memory: index in RAM (64 bytes/record), data on NVMe SSD
- Predictable P99 < 2ms even at 10M+ TPS
- Cost-effective storage for 600B+ records (SSD vs all-RAM alternatives)

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AD EXCHANGES                            │
│            (Google AdX, AppNexus, Rubicon)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Bid Requests (10M+/sec)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   BID REQUEST ROUTERS                        │
│              (Stateless, Geo-distributed)                    │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────┐          ┌─────────────────────────┐
│  AEROSPIKE CLUSTER  │          │    BIDDING ENGINE        │
│  (User Profiles)    │◄────────►│  (Decision + ML Model)  │
│                     │  <1ms    │                          │
│  - 600B+ records    │          │  - Segment matching      │
│  - 40 nodes         │          │  - Budget pacing         │
│  - NVMe SSDs        │          │  - Frequency capping     │
└─────────────────────┘          └─────────────────────────┘
           │
           │ XDR Replication
           ▼
┌─────────────────────┐
│  AEROSPIKE CLUSTER  │
│  (Secondary DC)     │
└─────────────────────┘
```

#### Namespace & Data Model

```
# Namespace Configuration
namespace adtech {
    memory-size 128G              # Index memory
    storage-engine device {
        device /dev/nvme0n1
        device /dev/nvme1n1
        write-block-size 128K
        defrag-lwm-pct 50
    }
    replication-factor 2
    default-ttl 30d              # Expire stale profiles
    high-water-memory-pct 80
    stop-writes-pct 90
}
```

```
Set: user_profiles
┌──────────────────────────────────────────────────────────┐
│ Key: device_id / cookie_hash (string)                    │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   segments     : List<int>     [1024, 2048, 5001...]     │
│   demographics : Map           {age: "25-34", geo: "US"} │
│   freq_caps    : Map           {camp_123: 3, camp_456: 1}│
│   last_seen    : int           (epoch timestamp)         │
│   bid_history  : List<Map>     (last 10 impressions)     │
└──────────────────────────────────────────────────────────┘

Set: campaign_budgets
┌──────────────────────────────────────────────────────────┐
│ Key: campaign_id (integer)                               │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   daily_budget  : int          (cents)                   │
│   spent_today   : int          (atomic increment)        │
│   pacing_rate   : double                                 │
└──────────────────────────────────────────────────────────┘
```

**Production Numbers:**
| Metric | Value |
|--------|-------|
| Records | 600B+ |
| Cluster Size | 40 nodes per DC |
| Read TPS | 10M+ |
| P50 Latency | 0.3ms |
| P99 Latency | 1.5ms |
| Storage per node | 8x NVMe SSDs (3.2TB each) |
| RAM per node | 256GB (index only) |

---

### 2. PayPal - Fraud Detection

**Problem:** Score every transaction for fraud risk in real-time at 4M+ TPS globally without adding user-visible latency.

**Why Aerospike:**
- Predictable sub-ms reads for velocity counters and device fingerprints
- Atomic read-modify-write for counters (no distributed locks needed)
- Strong consistency mode for financial accuracy
- Scales linearly - add nodes without downtime

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  PAYMENT GATEWAY                             │
│           (Transaction Ingestion Layer)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                FRAUD SCORING ENGINE                          │
│         (Real-time ML Model Inference)                      │
│                                                             │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐               │
│  │Velocity │  │  Device   │  │   Graph     │               │
│  │ Checks  │  │Fingerprint│  │  Lookups    │               │
│  └────┬────┘  └─────┬─────┘  └──────┬──────┘               │
└───────┼──────────────┼───────────────┼──────────────────────┘
        │              │               │
        ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│              AEROSPIKE CLUSTER (Strong Consistency)          │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐     │
│  │ velocity_   │  │  device_     │  │  entity_       │     │
│  │ counters    │  │  profiles    │  │  graph         │     │
│  │             │  │              │  │                │     │
│  │ 5min/1hr/   │  │ fingerprint  │  │ user-merchant  │     │
│  │ 24hr windows│  │ + risk score │  │ relationships  │     │
│  └─────────────┘  └──────────────┘  └────────────────┘     │
│                                                             │
│  Nodes: 60+ per DC  |  Replication: 3  |  Mode: SC         │
└─────────────────────────────────────────────────────────────┘
        │                              │
        │         XDR (Active-Active)  │
        ▼                              ▼
┌──────────────────┐       ┌──────────────────┐
│  DC: US-EAST     │◄─────►│  DC: US-WEST     │
└──────────────────┘       └──────────────────┘
```

#### Namespace & Data Model

```
namespace fraud {
    memory-size 256G
    storage-engine device {
        device /dev/nvme0n1
        device /dev/nvme1n1
        device /dev/nvme2n1
        device /dev/nvme3n1
        write-block-size 128K
    }
    replication-factor 3
    strong-consistency true       # Financial data needs SC
    default-ttl 0                 # Never expire
}
```

```
Set: velocity_counters
┌──────────────────────────────────────────────────────────┐
│ Key: "user:<user_id>:txn_count"                          │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   count_5min   : int        (sliding window counter)     │
│   count_1hr    : int                                     │
│   count_24hr   : int                                     │
│   amount_5min  : int        (cents)                      │
│   amount_1hr   : int                                     │
│   amount_24hr  : int                                     │
│   last_txn_ts  : int        (epoch ms)                   │
│   last_geo     : GeoJSON    (lat/lng)                    │
└──────────────────────────────────────────────────────────┘

Set: device_profiles
┌──────────────────────────────────────────────────────────┐
│ Key: device_fingerprint_hash                             │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   users_seen    : List<string>  (user IDs seen on device)│
│   risk_score    : double        (0.0 - 1.0)             │
│   first_seen    : int           (epoch)                  │
│   txn_count     : int                                    │
│   fraud_flags   : int           (bitmap)                 │
└──────────────────────────────────────────────────────────┘
```

**Production Numbers:**
| Metric | Value |
|--------|-------|
| TPS | 4M+ (reads + writes) |
| P50 Latency | 0.5ms |
| P99 Latency | 2ms |
| Cluster Size | 60+ nodes per DC |
| DCs | 3 (Active-Active XDR) |
| Records | 10B+ |
| Availability | 99.999% |

---

### 3. Flipkart - Session Store

**Problem:** Manage sessions and shopping cart data for 200M+ users with flash sale spikes (10x traffic in seconds).

**Why Aerospike:**
- Handles traffic spikes without pre-provisioning (linear scale-out)
- Session reads in <1ms - critical for page load times
- TTL-based auto-expiry of sessions (no garbage collection needed)
- Hybrid memory keeps cost manageable at petabyte scale

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MOBILE / WEB CLIENTS                      │
│                  (200M+ Monthly Active)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     API GATEWAY                              │
│              (NGINX / Envoy / Custom)                        │
│         Session Token → Aerospike Key Mapping               │
└─────────┬───────────────────────────────────────┬───────────┘
          │                                       │
          ▼                                       ▼
┌───────────────────────┐           ┌──────────────────────────┐
│   AEROSPIKE CLUSTER   │           │   APPLICATION SERVERS    │
│   (Session Store)     │           │                          │
│                       │◄─────────►│  - Product Service       │
│  Namespace: sessions  │   <1ms    │  - Cart Service          │
│  - 500M active sess.  │           │  - Recommendation Svc    │
│  - TTL: 30 min idle   │           │  - Checkout Service      │
│                       │           │                          │
│  Namespace: carts     │           └──────────────────────────┘
│  - 100M active carts  │
│  - TTL: 7 days        │
│                       │
│  20 nodes, RF=2       │
└───────────────────────┘
          │
          │  Flash Sale: Auto-scales
          │  with Kubernetes HPA
          ▼
┌───────────────────────┐
│  OVERFLOW CLUSTER     │
│  (Burst capacity)     │
│  10 additional nodes  │
└───────────────────────┘
```

#### Namespace & Data Model

```
namespace sessions {
    memory-size 64G
    storage-engine device {
        device /dev/nvme0n1
        write-block-size 128K
    }
    replication-factor 2
    default-ttl 1800              # 30 min session timeout
    nsup-period 120               # Expire check every 2 min
    high-water-memory-pct 70
}

namespace carts {
    memory-size 32G
    storage-engine device {
        device /dev/nvme1n1
        write-block-size 128K
    }
    replication-factor 2
    default-ttl 604800            # 7 days
}
```

```
Set: active_sessions
┌──────────────────────────────────────────────────────────┐
│ Key: session_token (UUID string)                         │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   user_id       : string                                 │
│   device_type   : string     ("mobile", "web", "app")    │
│   login_ts      : int        (epoch)                     │
│   last_active   : int        (epoch, touch on each req)  │
│   preferences   : Map        {lang, currency, theme}     │
│   ab_flags      : int        (bitmap for A/B tests)      │
│   cart_id       : string     (link to cart record)       │
└──────────────────────────────────────────────────────────┘

Set: shopping_carts
┌──────────────────────────────────────────────────────────┐
│ Key: cart_id (UUID)                                      │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   items         : List<Map>  [{sku, qty, price, seller}] │
│   coupon_codes  : List<str>                              │
│   subtotal      : int        (paisa / cents)             │
│   updated_at    : int        (epoch)                     │
│   version       : int        (optimistic locking)        │
└──────────────────────────────────────────────────────────┘
```

**Production Numbers:**
| Metric | Value |
|--------|-------|
| Active Sessions | 500M+ |
| Read TPS (normal) | 2M |
| Read TPS (flash sale) | 15M+ |
| P50 Latency | 0.4ms |
| P99 Latency | 1.8ms |
| Cluster Size | 20 nodes (expands to 30 during sales) |
| Storage | 4x NVMe per node |

---

### 4. Dream11 - Fantasy Sports

**Problem:** Handle 100M+ concurrent users during IPL cricket matches with real-time leaderboard updates and contest joins.

**Why Aerospike:**
- Extreme read throughput for leaderboard queries
- Atomic operations for contest join counters (no overselling)
- Predictable latency under extreme concurrency
- Cost-effective vs Redis for this data volume

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              100M+ CONCURRENT USERS                          │
│           (During IPL Match, 8PM Peak)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CDN + API GATEWAY                         │
│              (Rate Limiting, Auth, Routing)                  │
└──────┬──────────────────────────────────┬───────────────────┘
       │                                  │
       ▼                                  ▼
┌──────────────────┐            ┌──────────────────────────┐
│  CONTEST SERVICE │            │  LEADERBOARD SERVICE     │
│                  │            │                          │
│  - Join contest  │            │  - Real-time rankings    │
│  - Team submit   │            │  - Point calculations    │
│  - Slot counter  │            │  - Prize distribution    │
└───────┬──────────┘            └────────────┬─────────────┘
        │                                    │
        ▼                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  AEROSPIKE CLUSTER                           │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐     │
│  │  contests   │  │   teams      │  │  leaderboards  │     │
│  │             │  │              │  │                │     │
│  │ slots_left  │  │ user teams   │  │ sorted scores  │     │
│  │ (atomic)    │  │ per match    │  │ per contest    │     │
│  └─────────────┘  └──────────────┘  └────────────────┘     │
│                                                             │
│         50 nodes  |  RF=2  |  AP mode (fast writes)         │
└─────────────────────────────────────────────────────────────┘
        │
        │  Score Updates (Kafka → Workers → Aerospike)
        │
┌───────┴─────────────────────────────────────────────────────┐
│              SCORE INGESTION PIPELINE                        │
│                                                             │
│  Live Feed ──► Kafka ──► Score Workers ──► Aerospike        │
│  (Cricket)      (Buffer)   (Calculate)     (Update)         │
└─────────────────────────────────────────────────────────────┘
```

#### Namespace & Data Model

```
namespace fantasy {
    memory-size 192G
    storage-engine device {
        device /dev/nvme0n1
        device /dev/nvme1n1
        device /dev/nvme2n1
        device /dev/nvme3n1
        write-block-size 128K
    }
    replication-factor 2
    default-ttl 0
    high-water-memory-pct 80
}
```

```
Set: contests
┌──────────────────────────────────────────────────────────┐
│ Key: contest_id (integer)                                │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   match_id      : int                                    │
│   max_slots     : int         (e.g., 1000000)           │
│   slots_filled  : int         (atomic increment)         │
│   entry_fee     : int         (paisa)                    │
│   prize_pool    : int                                    │
│   status        : int         (0=open, 1=live, 2=done)   │
└──────────────────────────────────────────────────────────┘

Set: user_teams
┌──────────────────────────────────────────────────────────┐
│ Key: "user:<uid>:match:<mid>:team:<tid>"                 │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   players       : List<int>    [player_ids x 11]         │
│   captain       : int          (2x points)               │
│   vice_captain  : int          (1.5x points)             │
│   total_points  : double       (updated live)            │
│   contests      : List<int>    [contest_ids joined]      │
└──────────────────────────────────────────────────────────┘

Set: leaderboards
┌──────────────────────────────────────────────────────────┐
│ Key: "lb:<contest_id>:rank:<rank>"                       │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   user_id       : int                                    │
│   team_id       : int                                    │
│   points        : double                                 │
│   rank          : int                                    │
└──────────────────────────────────────────────────────────┘
```

**Production Numbers:**
| Metric | Value |
|--------|-------|
| Concurrent Users (Peak) | 100M+ |
| TPS (Peak) | 20M+ |
| P50 Latency | 0.5ms |
| P99 Latency | 3ms |
| Cluster Size | 50 nodes |
| Contest Joins/sec | 500K+ |
| Score Updates/match | 5B+ |

---

### 5. Airtel - Subscriber Profile & Real-Time Charging

**Problem:** Real-time charging and subscriber profile lookups for 350M+ customers with <5ms SLA for every call/data session.

**Why Aerospike:**
- Strong consistency for balance deductions (no double-spending)
- 350M+ subscriber records with sub-ms access
- Hybrid memory keeps TCO manageable vs all-RAM solutions
- XDR for disaster recovery across data centers

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NETWORK ELEMENTS                          │
│         (GGSN, PCRF, OCS, IVR, SMSC, USSD)                │
└────────┬────────────────────────────────┬───────────────────┘
         │                                │
         ▼                                ▼
┌─────────────────────┐        ┌──────────────────────────┐
│   CHARGING ENGINE   │        │  SUBSCRIBER MGMT LAYER   │
│   (Online Charging) │        │                          │
│                     │        │  - Plan activation       │
│  - Balance check    │        │  - Recharge processing   │
│  - Debit/Credit     │        │  - Profile updates       │
│  - Rate lookup      │        │  - Number portability    │
└──────────┬──────────┘        └────────────┬─────────────┘
           │                                │
           ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│              AEROSPIKE CLUSTER (Strong Consistency)          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │ subscribers  │  │   balances   │  │  rate_plans    │    │
│  │              │  │              │  │                │    │
│  │ 350M records │  │ prepaid/post │  │  plan configs  │    │
│  │ profile data │  │ real-time    │  │  tariff rules  │    │
│  └──────────────┘  └──────────────┘  └────────────────┘    │
│                                                             │
│  80 nodes  |  RF=3  |  Strong Consistency  |  2 DCs        │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         │        XDR (Active-Passive)        │
         ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│  DC: Mumbai      │─────────────►│  DC: Bangalore   │
│  (Primary)       │              │  (DR)            │
└──────────────────┘              └──────────────────┘
```

#### Namespace & Data Model

```
namespace telecom {
    memory-size 512G
    storage-engine device {
        device /dev/nvme0n1
        device /dev/nvme1n1
        device /dev/nvme2n1
        device /dev/nvme3n1
        device /dev/nvme4n1
        device /dev/nvme5n1
        write-block-size 128K
    }
    replication-factor 3
    strong-consistency true
    default-ttl 0                 # Subscriber data never expires
}
```

```
Set: subscribers
┌──────────────────────────────────────────────────────────┐
│ Key: msisdn (phone number as string)                     │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   imsi          : string                                 │
│   plan_id       : int                                    │
│   circle        : string      ("MH", "DL", "KA"...)     │
│   subscriber_type: int        (prepaid=1, postpaid=2)    │
│   kyc_status    : int                                    │
│   activated_on  : int         (epoch)                    │
│   services      : Map         {voLTE:1, 5g:1, roam:0}   │
│   last_recharge : int         (epoch)                    │
└──────────────────────────────────────────────────────────┘

Set: balances
┌──────────────────────────────────────────────────────────┐
│ Key: msisdn                                              │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   main_bal      : int         (paisa, atomic ops)        │
│   data_bal_mb   : int         (MB remaining)             │
│   sms_bal       : int                                    │
│   validity      : int         (epoch expiry)             │
│   last_debit    : int         (epoch)                    │
│   last_debit_amt: int         (paisa)                    │
│   reserved      : int         (in-flight charges)        │
└──────────────────────────────────────────────────────────┘

Set: rate_plans
┌──────────────────────────────────────────────────────────┐
│ Key: plan_id (integer)                                   │
├──────────────────────────────────────────────────────────┤
│ Bins:                                                    │
│   voice_rate    : int         (paisa/sec)                │
│   data_rate     : int         (paisa/MB)                 │
│   sms_rate      : int         (paisa/sms)                │
│   roam_mult     : double      (multiplier)               │
│   fup_limit_gb  : int                                    │
│   post_fup_speed: int         (kbps)                     │
└──────────────────────────────────────────────────────────┘
```

**Production Numbers:**
| Metric | Value |
|--------|-------|
| Subscribers | 350M+ |
| Charging TPS | 2M+ |
| P50 Latency | 0.3ms |
| P99 Latency | 1.5ms |
| Cluster Size | 80 nodes |
| Replication Factor | 3 |
| Availability | 99.9999% (six nines target) |
| Data Centers | 2 (Active-Passive XDR) |

---

## Replication

### Intra-Cluster Replication (Automatic & Rack-Aware)

```
┌─────────────────────────────────────────────────────────────┐
│                    AEROSPIKE CLUSTER                         │
│                                                             │
│  ┌─────────── RACK 1 ──────────┐  ┌────── RACK 2 ────────┐│
│  │                              │  │                       ││
│  │  ┌──────┐  ┌──────┐         │  │  ┌──────┐  ┌──────┐  ││
│  │  │Node 1│  │Node 2│         │  │  │Node 3│  │Node 4│  ││
│  │  │      │  │      │         │  │  │      │  │      │  ││
│  │  │P:1-10│  │P:11-20│        │  │  │P:1-10│  │P:11-20│ ││
│  │  │(mstr)│  │(mstr) │        │  │  │(repl)│  │(repl) │ ││
│  │  └──────┘  └──────┘         │  │  └──────┘  └──────┘  ││
│  │                              │  │                       ││
│  └──────────────────────────────┘  └───────────────────────┘│
│                                                             │
│  Rack-Aware Policy: Master and replica NEVER on same rack   │
│  Survives: single node failure, entire rack failure         │
└─────────────────────────────────────────────────────────────┘

Write Path (RF=2):
  Client ──► Master Node ──► Write to storage
                  │
                  ├──► Replicate to Replica Node (same DC)
                  │
                  └──► ACK to client (after replica confirms)
```

### AP Mode vs SC (Strong Consistency) Mode

```
┌─────────────────────────────┬──────────────────────────────────┐
│         AP MODE             │          SC MODE                  │
│   (Available & Partition-   │   (Strong Consistency)            │
│    tolerant)                │                                   │
├─────────────────────────────┼──────────────────────────────────┤
│ • Default mode              │ • Roster-based membership         │
│ • Last-write-wins conflict  │ • Paxos-like consensus            │
│ • Always accepts writes     │ • May reject writes if no quorum  │
│ • Reads may be stale during │ • Linearizable reads              │
│   partition                 │ • No stale reads ever             │
│ • Use for: caching, session │ • Use for: financial, billing,    │
│   stores, analytics         │   inventory, charging             │
│ • Conflict resolution:      │ • Conflict resolution:            │
│   generation + LUT          │   Not needed (consensus)          │
├─────────────────────────────┼──────────────────────────────────┤
│ Availability: HIGH          │ Availability: Depends on quorum   │
│ Consistency: Eventual       │ Consistency: Strong (linearizable)│
│ Latency: Lowest             │ Latency: Slightly higher (~10%)   │
└─────────────────────────────┴──────────────────────────────────┘
```

### Strong Consistency - Roster Based

```
Roster: Ordered list of nodes that MUST participate

  Roster = [Node1, Node2, Node3, Node4, Node5]

  For RF=3, a partition needs majority (2 of 3 copies) to be available:

  ┌────────────────────────────────────────────────────┐
  │              WRITE (SC Mode, RF=3)                  │
  │                                                    │
  │  Client ──► Master                                 │
  │               │                                    │
  │               ├──► Replica1: ACK ✓                 │
  │               ├──► Replica2: ACK ✓   (majority!)   │
  │               │                                    │
  │               └──► Commit + ACK to Client          │
  │                                                    │
  │  If Master + 1 Replica down → partition UNAVAILABLE│
  │  (refuses reads/writes to maintain consistency)    │
  └────────────────────────────────────────────────────┘
```

### Cross-Datacenter Replication (XDR)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        XDR TOPOLOGIES                                │
└─────────────────────────────────────────────────────────────────────┘

1. ACTIVE-PASSIVE (Disaster Recovery)
   ┌──────────────┐         Ship Log         ┌──────────────┐
   │   DC1        │ ═══════════════════════►  │   DC2        │
   │  (Primary)   │                           │   (DR)       │
   │              │    Writes replicated       │              │
   │  Reads ✓     │    asynchronously         │  Reads ✓     │
   │  Writes ✓    │                           │  Writes ✗    │
   └──────────────┘                           └──────────────┘

2. ACTIVE-ACTIVE (Multi-region)
   ┌──────────────┐                           ┌──────────────┐
   │   DC1        │ ◄═══════════════════════► │   DC2        │
   │  (US-East)   │                           │  (US-West)   │
   │              │    Bi-directional XDR      │              │
   │  Reads ✓     │                           │  Reads ✓     │
   │  Writes ✓    │                           │  Writes ✓    │
   └──────────────┘                           └──────────────┘
        ▲                                           ▲
        │              ┌──────────────┐             │
        └══════════════│   DC3        │═════════════┘
                       │  (EU-West)   │
                       │  Reads ✓     │
                       │  Writes ✓    │
                       └──────────────┘

3. STAR TOPOLOGY (Hub-and-Spoke)
                       ┌──────────────┐
              ┌═══════►│   HUB DC     │◄═══════┐
              ║        │  (Aggregator) │        ║
              ║        └──────┬───────┘        ║
              ║               │                ║
        ┌─────╨──────┐  ┌────┴───────┐  ┌─────╨──────┐
        │  Spoke DC1 │  │  Spoke DC2 │  │  Spoke DC3 │
        └────────────┘  └────────────┘  └────────────┘
```

### XDR Conflict Resolution

```
When same record written in multiple DCs simultaneously:

Resolution Order:
  1. Generation count (higher wins) - more writes = newer
  2. Last-update-time (LUT) - wall clock comparison
  3. Source DC precedence (configurable tiebreaker)

Example:
  DC1 writes Key "X" → gen=5, LUT=1000
  DC2 writes Key "X" → gen=5, LUT=1002

  DC2 wins (same generation, higher LUT)

Configuration:
  xdr {
      dc DC2 {
          node-address-port 10.0.2.1 3000
          namespace telecom {
              ship-only-specified-sets true
              ship-set subscribers
              ship-set balances
              write-policy update     # update | replace
              conflict-resolution generation  # or last-update-time
          }
      }
  }
```

---

## Scalability

### Smart Client Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SMART CLIENT                             │
│                                                             │
│  ┌────────────────────────────────────────────────────┐     │
│  │              PARTITION MAP (cached)                 │     │
│  │                                                    │     │
│  │  Partition 0    → Node 3 (master), Node 7 (replica)│     │
│  │  Partition 1    → Node 1 (master), Node 5 (replica)│     │
│  │  Partition 2    → Node 4 (master), Node 2 (replica)│     │
│  │  ...                                               │     │
│  │  Partition 4095 → Node 6 (master), Node 8 (replica)│     │
│  └────────────────────────────────────────────────────┘     │
│                                                             │
│  Key "user:123" ──► RIPEMD-160 hash ──► partition 2847      │
│                                     ──► direct to Node X    │
│                                                             │
│  NO PROXY! Client talks directly to correct node.           │
│  Single-hop reads. No coordinator bottleneck.               │
└─────────────────────────────────────────────────────────────┘

  Compared to proxy-based systems:

  Traditional:   Client → Proxy → Any Node → Redirect → Correct Node
  Aerospike:     Client → Correct Node (direct, single hop)

  Result: ~50% lower latency, no proxy as SPOF
```

### Hybrid Memory Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  SINGLE AEROSPIKE NODE                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    DRAM (RAM)                          │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │          PRIMARY INDEX (in-memory)              │  │  │
│  │  │                                                 │  │  │
│  │  │  Each entry = 64 bytes:                         │  │  │
│  │  │  ┌────────┬──────────┬────────┬──────────────┐  │  │  │
│  │  │  │20B key │ metadata │ tree   │ storage ptr  │  │  │  │
│  │  │  │digest  │ (gen,ttl)│pointers│ (SSD offset) │  │  │  │
│  │  │  └────────┴──────────┴────────┴──────────────┘  │  │  │
│  │  │                                                 │  │  │
│  │  │  1 Billion records = ~64 GB RAM for index       │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │       SECONDARY INDEXES (in-memory)             │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          │ pointer                           │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  NVMe SSD                             │  │
│  │                                                       │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │  │
│  │  │Write│ │Write│ │Write│ │Write│ │Write│ ...         │  │
│  │  │Block│ │Block│ │Block│ │Block│ │Block│             │  │
│  │  │128KB│ │128KB│ │128KB│ │128KB│ │128KB│             │  │
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘           │  │
│  │                                                       │  │
│  │  Record data stored here (bins, metadata)             │  │
│  │  Single read = single SSD I/O (direct, no filesystem) │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Storage Engine Modes

```
┌─────────────────┬──────────────────┬─────────────────┬──────────────────┐
│                 │  HYBRID (Default)│  ALL-FLASH       │  MEMORY-ONLY     │
├─────────────────┼──────────────────┼─────────────────┼──────────────────┤
│ Index Location  │ RAM              │ SSD (Flash)      │ RAM              │
│ Data Location   │ SSD              │ SSD              │ RAM              │
│ Cost            │ Medium           │ Lowest           │ Highest          │
│ Latency         │ <1ms typical     │ 1-2ms typical    │ <0.5ms           │
│ Capacity/node   │ Billions         │ Tens of Billions │ Millions         │
│ Use Case        │ Most workloads   │ Huge datasets    │ Caching, session │
├─────────────────┼──────────────────┼─────────────────┼──────────────────┤
│ Config          │ storage-engine   │ storage-engine   │ storage-engine   │
│                 │   device {...}   │   device {       │   memory         │
│                 │                  │   index-type     │                  │
│                 │                  │     flash {...}  │                  │
│                 │                  │   }              │                  │
└─────────────────┴──────────────────┴─────────────────┴──────────────────┘
```

### Data Distribution (4096 Partitions)

```
Key Hashing → Partition Assignment → Node Mapping

  "user:12345"
       │
       ▼
  RIPEMD-160(key) = 20-byte digest
       │
       ▼
  digest[0:12] mod 4096 = Partition ID (e.g., 2847)
       │
       ▼
  Partition Map: 2847 → Node 5 (master)
       │
       ▼
  Client sends request directly to Node 5


Distribution across 10-node cluster:
  ┌────────┬────────────────────────────────────┐
  │ Node   │ Partitions Owned (master)          │
  ├────────┼────────────────────────────────────┤
  │ Node 1 │ ~410 partitions (4096/10)          │
  │ Node 2 │ ~410 partitions                    │
  │ Node 3 │ ~409 partitions                    │
  │ ...    │ ...                                │
  │ Node 10│ ~409 partitions                    │
  └────────┴────────────────────────────────────┘

  Adding Node 11:
  - Each existing node gives up ~37 partitions
  - Migration happens in background
  - Zero downtime, reads/writes continue
```

### Cluster Rebalancing (Migrations)

```
Before: 4 nodes, RF=2, 4096 partitions

  Node1: P[0-1023] master     + P[2048-3071] replica
  Node2: P[1024-2047] master  + P[3072-4095] replica
  Node3: P[2048-3071] master  + P[0-1023] replica
  Node4: P[3072-4095] master  + P[1024-2047] replica

After adding Node5:
  ┌─────────────────────────────────────────────────┐
  │  MIGRATION IN PROGRESS                          │
  │                                                 │
  │  Node1: gives ~205 master partitions to Node5   │
  │  Node2: gives ~205 master partitions to Node5   │
  │  Node3: gives ~205 master partitions to Node5   │
  │  Node4: gives ~205 master partitions to Node5   │
  │                                                 │
  │  Total: Node5 receives ~820 master partitions   │
  │         (4096/5 ≈ 819)                          │
  │                                                 │
  │  During migration:                              │
  │  - Reads served from current master             │
  │  - Writes go to new master (proxied if needed)  │
  │  - Zero downtime                                │
  └─────────────────────────────────────────────────┘
```

---

## Production Setup

### Hardware Recommendations

```
┌─────────────────────────────────────────────────────────────┐
│              RECOMMENDED HARDWARE PER NODE                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CPU:    24-48 cores (Aerospike is I/O bound, not CPU)      │
│                                                             │
│  RAM:    256GB - 512GB                                      │
│          Formula: (num_records × 64 bytes) + overhead       │
│          1B records = ~64GB for primary index               │
│          Add 30% overhead for secondary indexes             │
│                                                             │
│  Storage: 4-8x NVMe SSDs (CRITICAL)                        │
│           Intel Optane P5800X (best) or                     │
│           Samsung PM9A3 / Micron 9400                       │
│           Enterprise-grade with power-loss protection       │
│           NO SATA SSDs (latency too high)                   │
│           NO HDDs (completely unsuitable)                   │
│           NO RAID (Aerospike manages SSDs directly)         │
│           Raw device access (no filesystem!)                │
│                                                             │
│  Network: 25Gbps+ (for replication and migrations)          │
│           Dedicated NIC for heartbeat recommended           │
│                                                             │
│  OS:     Linux (RHEL/CentOS/Ubuntu)                         │
│          Kernel: 4.15+ (NVMe optimizations)                 │
│          Scheduler: noop or none for NVMe                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

CRITICAL: Aerospike bypasses filesystem - writes directly to raw device.
  Setup: Do NOT format the SSD. Use /dev/nvme0n1 directly.
```

### Namespace Configuration (Production)

```bash
# /etc/aerospike/aerospike.conf

service {
    user root
    group root
    proto-fd-max 15000
    cluster-name production-cluster
}

logging {
    file /var/log/aerospike/aerospike.log {
        context any info
        context migrate debug
    }
}

network {
    service {
        address any
        port 3000
    }
    heartbeat {
        mode mesh
        address 10.0.1.1
        port 3002
        mesh-seed-address-port 10.0.1.2 3002
        mesh-seed-address-port 10.0.1.3 3002
        interval 150
        timeout 10
    }
    fabric {
        port 3001
    }
}

namespace production {
    memory-size 256G
    replication-factor 2
    default-ttl 0
    high-water-memory-pct 70
    stop-writes-pct 90
    nsup-period 120

    storage-engine device {
        device /dev/nvme0n1
        device /dev/nvme1n1
        device /dev/nvme2n1
        device /dev/nvme3n1
        write-block-size 128K
        max-write-cache 256M
        defrag-lwm-pct 50
        defrag-sleep 1000
        min-avail-pct 5
        post-write-queue 256
    }
}

# XDR configuration
xdr {
    dc DC2 {
        node-address-port 10.0.2.1 3000
        node-address-port 10.0.2.2 3000
        node-address-port 10.0.2.3 3000
        namespace production {
            ship-only-specified-sets true
            ship-set critical_data
        }
    }
}
```

### Monitoring (Aerospike Monitoring Stack)

```
┌─────────────────────────────────────────────────────────────┐
│              MONITORING ARCHITECTURE                         │
│                                                             │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐   │
│  │  Aerospike   │───►│ Aerospike   │───►│  Prometheus  │   │
│  │  Cluster     │    │ Exporter    │    │              │   │
│  │              │    │ (per node)  │    │  (scrape     │   │
│  │  Port 3000   │    │ Port 9145   │    │   every 15s) │   │
│  └──────────────┘    └─────────────┘    └──────┬───────┘   │
│                                                 │           │
│                                                 ▼           │
│                                         ┌──────────────┐   │
│                                         │   Grafana     │   │
│                                         │              │   │
│                                         │  Dashboards: │   │
│                                         │  - Ops/sec   │   │
│                                         │  - Latency   │   │
│                                         │  - Memory    │   │
│                                         │  - Disk      │   │
│                                         │  - Migrations│   │
│                                         └──────┬───────┘   │
│                                                │           │
│                                                ▼           │
│                                         ┌──────────────┐   │
│                                         │ AlertManager │   │
│                                         │ (PagerDuty)  │   │
│                                         └──────────────┘   │
└─────────────────────────────────────────────────────────────┘

Key Metrics to Alert On:
  - cluster_size != expected          (node down!)
  - stop_writes = true                (CRITICAL - cluster stopped)
  - hwm_breached = true               (evictions starting)
  - migrate_partitions_remaining > 0  (rebalancing in progress)
  - client_connections > threshold    (connection leak)
  - device_available_pct < 10         (disk almost full)
```

### Backup and Restore

```bash
# Full backup
asbackup --host 10.0.1.1 \
         --namespace production \
         --directory /backup/full/$(date +%Y%m%d) \
         --parallel 8 \
         --compress zstd

# Incremental backup (records modified after timestamp)
asbackup --host 10.0.1.1 \
         --namespace production \
         --directory /backup/incr/$(date +%Y%m%d) \
         --modified-after "2024-01-15_00:00:00" \
         --parallel 8

# Restore
asrestore --host 10.0.1.1 \
          --namespace production \
          --directory /backup/full/20240115 \
          --parallel 8 \
          --no-generation       # Overwrite regardless of gen count

# Backup specific sets only
asbackup --host 10.0.1.1 \
         --namespace production \
         --set subscribers \
         --directory /backup/subscribers/
```

### Rolling Upgrades

```
Procedure (zero-downtime):

  1. Verify cluster healthy:
     $ asadm -e "info" → all nodes UP, no migrations

  2. For each node (one at a time):

     a. Quiesce the node (drain connections):
        $ asadm -e "manage quiesce node <node-id>"

     b. Stop Aerospike:
        $ systemctl stop aerospike

     c. Upgrade package:
        $ rpm -Uvh aerospike-server-enterprise-*.rpm

     d. Start Aerospike:
        $ systemctl start aerospike

     e. Wait for migrations to complete:
        $ asadm -e "show statistics like migrate"
        (wait until migrate_partitions_remaining = 0)

     f. Undo quiesce:
        $ asadm -e "manage quiesce-undo node <node-id>"

  3. Proceed to next node

  Total time: ~5-10 min per node
  Cluster remains available throughout
```

### Capacity Planning Formula

```
INDEX MEMORY:
  RAM needed = num_records × 64 bytes × replication_factor
             + secondary_index_overhead (varies)

  Example: 2 billion records, RF=2
  RAM = 2B × 64B × 2 = 256 GB per cluster
  Per node (8 nodes) = 32 GB just for index
  Add 30-50% headroom = ~48 GB per node minimum

SSD STORAGE:
  Storage needed = num_records × avg_record_size × replication_factor
                 ÷ defrag_efficiency (typically 0.5 - 0.6)

  Example: 2B records × 1KB avg × RF=2 ÷ 0.5
  Storage = 8 TB raw across cluster
  Per node (8 nodes) = 1 TB per node

THROUGHPUT:
  Single NVMe SSD = ~200K-400K random read IOPS
  4 SSDs per node = ~1M read ops/sec per node
  8-node cluster = ~8M read ops/sec

NETWORK:
  Bandwidth = write_tps × avg_record_size × replication_factor
  Example: 500K writes/sec × 1KB × RF=2 = 1 GB/s intra-cluster
  → 10Gbps minimum, 25Gbps recommended
```

---

## Core Concepts

### Hybrid Memory Architecture (Detailed)

```
┌─────────────────────────────────────────────────────────────────┐
│                      READ PATH                                  │
│                                                                 │
│  1. Client hashes key → partition → node (Smart Client)         │
│  2. Node looks up 64-byte index entry in RAM (~50ns)            │
│  3. Index has SSD block pointer                                 │
│  4. Single direct I/O read from SSD (~80-100μs on NVMe)         │
│  5. Return record to client                                     │
│                                                                 │
│  Total: ~100-200μs (0.1-0.2ms) for typical read                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      WRITE PATH                                 │
│                                                                 │
│  1. Client sends write to master node                           │
│  2. Node updates in-memory index                                │
│  3. Record buffered in write-block (128KB buffer)               │
│  4. When buffer full → sequential write to SSD                  │
│  5. Replicate to replica node(s)                                │
│  6. ACK to client                                               │
│                                                                 │
│  Key insight: Writes are SEQUENTIAL (not random) → SSD-friendly │
│  Reads are random but NVMe handles random reads excellently     │
└─────────────────────────────────────────────────────────────────┘

WHY THIS IS FAST:
  - RAM lookup: O(1) hash → ~50ns
  - NVMe random read: ~80-100μs (vs ~5ms for HDD)
  - No filesystem overhead (raw device access)
  - No page cache pollution (direct I/O)
  - Write amplification minimized by large write blocks
```

### Single-Record Transactions

```
Aerospike guarantees atomicity at the SINGLE RECORD level:

  Read-Modify-Write (atomic):
  ┌──────────────────────────────────────────────┐
  │  Client: operate(key, [                      │
  │    read("balance"),                           │
  │    add("balance", -100),                      │
  │    write("last_txn", now())                   │
  │  ])                                          │
  │                                              │
  │  → All operations execute atomically         │
  │  → No other client sees intermediate state   │
  │  → Uses generation check for CAS semantics   │
  └──────────────────────────────────────────────┘

  Generation-based optimistic locking:
  ┌──────────────────────────────────────────────┐
  │  1. Read record → gen=5                      │
  │  2. Modify locally                           │
  │  3. Write with policy: generation=5          │
  │                                              │
  │  If another write happened (gen now 6):      │
  │  → Write REJECTED with GENERATION_ERROR      │
  │  → Client retries from step 1               │
  └──────────────────────────────────────────────┘

  NOTE: Multi-record transactions not natively supported.
  Use single-record design or application-level saga patterns.
```

### Secondary Indexes

```
Secondary indexes are stored IN MEMORY (co-located with data):

  Create index:
    CREATE INDEX idx_circle ON production.subscribers (circle) STRING

  Query:
    SELECT * FROM production.subscribers WHERE circle = "MH"

  Architecture:
  ┌──────────────────────────────────────────────────────┐
  │  Node 1 (owns partitions 0-1023)                     │
  │                                                      │
  │  Secondary Index (in RAM):                           │
  │    "MH" → [digest1, digest5, digest99, ...]          │
  │    "DL" → [digest2, digest7, ...]                    │
  │    "KA" → [digest3, digest4, ...]                    │
  │                                                      │
  │  Only indexes records THIS node owns                 │
  │  Query fans out to ALL nodes (scatter-gather)        │
  └──────────────────────────────────────────────────────┘

  Limitations:
  - High cardinality bins → large memory overhead
  - Scatter-gather on all nodes (not partition-aware for queries)
  - Best for: low-to-medium cardinality lookups
  - NOT a replacement for: full-text search, complex queries
```

### UDFs (User Defined Functions) with Lua

```lua
-- Example: Atomic balance transfer within single record
-- File: /opt/aerospike/usr/udf/lua/charging.lua

function debit(rec, amount, txn_id)
    local balance = rec["balance"]
    if balance < amount then
        return aerospike:create_error(1, "Insufficient balance")
    end
    rec["balance"] = balance - amount
    rec["last_txn"] = txn_id
    rec["last_debit_ts"] = os.time()
    aerospike:update(rec)
    return rec["balance"]  -- Return new balance
end

function credit(rec, amount, txn_id)
    rec["balance"] = (rec["balance"] or 0) + amount
    rec["last_credit_ts"] = os.time()
    aerospike:update(rec)
    return rec["balance"]
end
```

```
UDF Execution:
  ┌─────────────────────────────────────────────────┐
  │  Client calls: execute(key, "charging", "debit",│
  │                        [500, "TXN123"])          │
  │                                                 │
  │  Executes on server-side:                       │
  │  - Record locked during UDF execution           │
  │  - Atomic (all-or-nothing)                      │
  │  - No network round-trips for read-modify-write │
  │                                                 │
  │  Use cases:                                     │
  │  - Complex atomic operations                    │
  │  - Conditional updates                          │
  │  - Aggregation (stream UDFs on scans)           │
  └─────────────────────────────────────────────────┘

  NOTE: UDFs add latency (~2-5x vs native ops). 
  Prefer operate() multi-op for simple cases.
```

### Batch Operations

```
Batch reads: Fetch multiple records in single network call

  Client.batch_read([
      Key("ns", "set", "key1"),
      Key("ns", "set", "key2"),
      Key("ns", "set", "key3"),
      ...  # up to thousands of keys
  ])

  Execution:
  ┌─────────────────────────────────────────────────────────┐
  │  Client groups keys by destination node:                │
  │                                                         │
  │  Node1: [key1, key4, key7]  ──► parallel request        │
  │  Node2: [key2, key5, key8]  ──► parallel request        │
  │  Node3: [key3, key6, key9]  ──► parallel request        │
  │                                                         │
  │  All requests sent in parallel                          │
  │  Response assembled client-side                         │
  │                                                         │
  │  Latency ≈ max(individual node latencies)               │
  │  NOT sum of all latencies                               │
  └─────────────────────────────────────────────────────────┘

  Batch writes (Aerospike 6.0+):
  - Atomic per-record (not across batch)
  - Significantly higher throughput vs individual writes
```

### Scan and Query Operations

```
SCAN: Read all records in namespace/set (full table scan)
  - Used for: analytics, data migration, background processing
  - Runs in parallel across all nodes
  - Can apply UDF to each record (stream UDFs)
  - Throttle with records-per-second to avoid cluster impact

QUERY: Read records matching secondary index filter
  - Requires secondary index on the bin
  - Scatter-gather across all nodes
  - Can combine with expression filters

  ┌─────────────────────────────────────────────────────────┐
  │  SCAN (all records in set "users")                      │
  │                                                         │
  │  Client ──► Node1: scan partitions 0-1023               │
  │         ──► Node2: scan partitions 1024-2047            │
  │         ──► Node3: scan partitions 2048-3071            │
  │         ──► Node4: scan partitions 3072-4095            │
  │                                                         │
  │  All nodes scan in parallel                             │
  │  Results streamed back to client                        │
  │  Pagination via partition filter (resume from part N)   │
  └─────────────────────────────────────────────────────────┘
```

### Expression Filters

```
Server-side filtering without secondary indexes:

  // Read records where age > 25 AND city == "Mumbai"
  Expression filter = Exp.and(
      Exp.gt(Exp.intBin("age"), Exp.val(25)),
      Exp.eq(Exp.stringBin("city"), Exp.val("Mumbai"))
  )

  // Apply on read, write, scan, or query
  policy.filterExp = filter

  Execution:
  ┌─────────────────────────────────────────────────────────┐
  │  Without expression filter:                             │
  │    Client ← all records ← Server (filter client-side)  │
  │    Network: HIGH, Client CPU: HIGH                      │
  │                                                         │
  │  With expression filter:                                │
  │    Client ← matching records only ← Server (filtered)  │
  │    Network: LOW, Server CPU: slightly higher            │
  │                                                         │
  │  Supported expressions:                                 │
  │    - Comparison: eq, ne, gt, ge, lt, le                 │
  │    - Logical: and, or, not                              │
  │    - List/Map: contains, size, get_by_rank              │
  │    - Regex: matches                                     │
  │    - Geo: within_region, contains_point                 │
  │    - Metadata: record_size, ttl, gen, last_update       │
  └─────────────────────────────────────────────────────────┘

  Key advantage: Reduces network transfer and client processing.
  Works on ANY bin without requiring a secondary index.
```

### Predicate Filtering (Legacy, prefer Expression Filters)

```
Predicate filters (older API, superseded by Expression Filters):

  // Equivalent to expression filter but older API
  PredExp[] predExps = new PredExp[] {
      PredExp.integerBin("age"),
      PredExp.integerValue(25),
      PredExp.integerGreater(),
      PredExp.stringBin("city"),
      PredExp.stringValue("Mumbai"),
      PredExp.stringEqual(),
      PredExp.and(2)
  };

  NOTE: Deprecated in newer clients. Use Expression Filters instead.
  Expression Filters are more readable and support more operations.
```

---

## Summary: When to Choose Aerospike

```
┌─────────────────────────────────────────────────────────────┐
│  CHOOSE AEROSPIKE WHEN:                                     │
│                                                             │
│  ✓ Need sub-millisecond latency at millions of TPS          │
│  ✓ Dataset too large for RAM (billions of records)          │
│  ✓ Need predictable P99 (not just P50)                      │
│  ✓ Simple key-value or document access patterns             │
│  ✓ Need linear horizontal scaling                           │
│  ✓ Cross-DC replication required                            │
│  ✓ Cost-sensitive (hybrid memory vs all-RAM)                │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  DO NOT CHOOSE AEROSPIKE WHEN:                              │
│                                                             │
│  ✗ Need complex joins or SQL queries                        │
│  ✗ Need multi-record ACID transactions                      │
│  ✗ Primary use case is full-text search                     │
│  ✗ Data fits comfortably in Redis (< 100GB)                 │
│  ✗ Need rich query language (use PostgreSQL, MongoDB)        │
│  ✗ Small scale (< 1M TPS) where simpler DB suffices         │
└─────────────────────────────────────────────────────────────┘

Typical Production Latency Profile:
  P50:  0.3 - 0.5 ms
  P95:  0.8 - 1.5 ms
  P99:  1.5 - 3.0 ms
  P999: 3.0 - 5.0 ms
```
