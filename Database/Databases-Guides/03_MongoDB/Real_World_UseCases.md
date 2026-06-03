# MongoDB - Real World Use Cases & Production Guide

## Table of Contents
1. [Use Case 1: eBay Product Catalog](#use-case-1-ebay-product-catalog)
2. [Use Case 2: Coinbase Cryptocurrency Platform](#use-case-2-coinbase-cryptocurrency-platform)
3. [Use Case 3: Forbes Content Management](#use-case-3-forbes-content-management)
4. [Use Case 4: Cisco IoT Platform](#use-case-4-cisco-iot-platform)
5. [Use Case 5: Adobe Experience Platform](#use-case-5-adobe-experience-platform)
6. [Replication Deep Dive](#replication-deep-dive)
7. [Scalability Patterns](#scalability-patterns)
8. [Production Setup](#production-setup)
9. [Core Concepts](#core-concepts)

---

## Use Case 1: eBay Product Catalog

### Why MongoDB?
- Flexible schema for 1B+ listings with vastly different attributes
- A laptop has CPU/RAM/Storage specs; a dress has size/color/fabric
- Schema evolution without migrations (add fields anytime)
- Rich queries on nested documents (embedded reviews, specs)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              eBay Product Catalog Architecture                       │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│  Search  │◀──▶│  Catalog API │───▶│       MongoDB (Sharded)          │
│  (Elastic│    │  Service     │    │                                  │
│  search) │    └──────────────┘    │  ┌─────────────────────────┐    │
└──────────┘           │            │  │  Config Servers (CSRS)  │    │
                       │            │  │  (3-node replica set)   │    │
                       ▼            │  └─────────────────────────┘    │
                ┌──────────────┐    │                                  │
                │   CDN/Cache  │    │  ┌───────┐ ┌───────┐ ┌───────┐ │
                │   (Redis)    │    │  │mongos │ │mongos │ │mongos │ │
                └──────────────┘    │  │(router)│ │(router)│ │(router)│ │
                                    │  └───┬───┘ └───┬───┘ └───┬───┘ │
                                    │      │         │         │      │
                                    │  ┌───┴─────────┴─────────┴───┐ │
                                    │  │         Shards             │ │
                                    │  │                           │ │
                                    │  │  Shard1     Shard2  ...   │ │
                                    │  │  (RS: P+S+S)(RS: P+S+S)  │ │
                                    │  │                           │ │
                                    │  │  Category A  Category B   │ │
                                    │  └───────────────────────────┘ │
                                    └─────────────────────────────────┘

Shard Key: { category_id: 1, _id: 1 }  (compound for locality + distribution)

Write Path (New Listing):
┌────────┐   ┌────────┐   ┌────────┐   ┌─────────────────┐
│ Seller │──▶│  API   │──▶│ mongos │──▶│ Shard (primary  │
│        │   │        │   │(routes)│   │ of replica set) │
└────────┘   └────────┘   └────────┘   └─────────────────┘
                                              │
                                              ▼
                                        ┌──────────┐
                                        │ Replicate│
                                        │ to 2     │
                                        │ secondar.│
                                        └──────────┘
```

### Document Schema

```javascript
// Product listing document (flexible schema per category)
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "listing_id": "eBay-12345678",
  "title": "Apple MacBook Pro 16-inch M3 Max",
  "category": {
    "id": 175672,
    "path": ["Electronics", "Computers", "Laptops"]
  },
  "seller": {
    "id": "seller_abc123",
    "name": "TechStore",
    "rating": 4.9,
    "feedback_count": 15000
  },
  "price": {
    "amount": 349900,          // cents
    "currency": "USD",
    "format": "fixed_price"    // or "auction"
  },
  "condition": "new",
  
  // Flexible attributes (varies by category)
  "specifications": {
    "processor": "Apple M3 Max",
    "ram_gb": 64,
    "storage_gb": 1000,
    "display_size_inches": 16.2,
    "display_type": "Liquid Retina XDR",
    "battery_hours": 22,
    "weight_lbs": 4.7,
    "color": "Space Black"
  },
  
  "images": [
    { "url": "https://...", "width": 1600, "height": 1200, "primary": true },
    { "url": "https://...", "width": 1600, "height": 1200, "primary": false }
  ],
  
  "shipping": {
    "free_shipping": true,
    "estimated_days": { "min": 2, "max": 5 },
    "locations": ["US", "CA", "UK"]
  },
  
  "inventory": {
    "quantity": 45,
    "sold": 1230
  },
  
  "reviews_summary": {
    "average_rating": 4.7,
    "count": 892,
    "distribution": { "5": 650, "4": 150, "3": 52, "2": 25, "1": 15 }
  },
  
  "status": "active",
  "created_at": ISODate("2024-01-15T10:30:00Z"),
  "updated_at": ISODate("2024-03-01T14:22:00Z"),
  "expires_at": ISODate("2024-04-15T10:30:00Z")
}
```

### Query Patterns

```javascript
// Find listings by category with filters
db.listings.find({
  "category.id": 175672,
  "price.amount": { $gte: 100000, $lte: 500000 },
  "specifications.ram_gb": { $gte: 32 },
  "status": "active"
}).sort({ "reviews_summary.average_rating": -1 }).limit(50);

// Aggregation: seller dashboard analytics
db.listings.aggregate([
  { $match: { "seller.id": "seller_abc123", "status": "active" } },
  { $group: {
      _id: "$category.path.0",
      total_listings: { $sum: 1 },
      total_value: { $sum: "$price.amount" },
      avg_rating: { $avg: "$reviews_summary.average_rating" }
  }},
  { $sort: { total_listings: -1 } }
]);

// Text search across titles and descriptions
db.listings.find({
  $text: { $search: "macbook pro m3" },
  "status": "active"
}, {
  score: { $meta: "textScore" }
}).sort({ score: { $meta: "textScore" } });
```

### Scale Numbers
- **1.5B+ active listings**
- **Hundreds of shards** across multiple clusters
- **Read-heavy**: 50:1 read:write ratio
- **Document size**: 2-50KB average
- **Query latency**: P99 < 50ms for indexed queries

---

## Use Case 2: Coinbase Cryptocurrency Platform

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│            Coinbase - Wallet & Transaction Storage                   │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐
│  Mobile  │───▶│  API Gateway │───▶│       Service Layer              │
│  App     │    │  (Kong)      │    │                                  │
└──────────┘    └──────────────┘    │  ┌─────────┐  ┌─────────────┐  │
                                    │  │ Wallet  │  │ Transaction │  │
                                    │  │ Service │  │ Service     │  │
                                    │  └────┬────┘  └──────┬──────┘  │
                                    └───────┼──────────────┼──────────┘
                                            │              │
                                            ▼              ▼
                                    ┌──────────────────────────────┐
                                    │    MongoDB (Sharded Cluster)  │
                                    │                              │
                                    │  Wallets Collection:         │
                                    │    Shard Key: user_id        │
                                    │    ~100M documents           │
                                    │                              │
                                    │  Transactions Collection:    │
                                    │    Shard Key: {user_id, ts}  │
                                    │    ~10B documents            │
                                    │                              │
                                    │  Write Concern: majority     │
                                    │  Read Concern: majority      │
                                    └──────────────────────────────┘

Multi-Document Transaction (Transfer between wallets):
┌─────────────────────────────────────────────────────────────────────┐
│  session.startTransaction({                                          │
│    readConcern: { level: "snapshot" },                               │
│    writeConcern: { w: "majority" }                                   │
│  });                                                                 │
│                                                                      │
│  // Debit sender                                                     │
│  db.wallets.updateOne(                                               │
│    { user_id: sender, "balances.currency": "BTC" },                 │
│    { $inc: { "balances.$.amount": -0.5 } }                          │
│  );                                                                  │
│                                                                      │
│  // Credit receiver                                                  │
│  db.wallets.updateOne(                                               │
│    { user_id: receiver, "balances.currency": "BTC" },               │
│    { $inc: { "balances.$.amount": 0.5 } }                           │
│  );                                                                  │
│                                                                      │
│  // Record transaction                                               │
│  db.transactions.insertOne({ ... });                                 │
│                                                                      │
│  session.commitTransaction();                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Document Schema

```javascript
// Wallet document
{
  "_id": ObjectId("..."),
  "user_id": "user_abc123",
  "balances": [
    { "currency": "BTC", "amount": NumberDecimal("2.45000000"), "locked": NumberDecimal("0.00000000") },
    { "currency": "ETH", "amount": NumberDecimal("15.30000000"), "locked": NumberDecimal("1.00000000") },
    { "currency": "USDC", "amount": NumberDecimal("5000.00"), "locked": NumberDecimal("0.00") }
  ],
  "addresses": {
    "BTC": ["bc1q...abc", "bc1q...def"],
    "ETH": ["0x123...abc"]
  },
  "created_at": ISODate("2021-03-15T..."),
  "updated_at": ISODate("2024-03-01T...")
}

// Transaction document
{
  "_id": ObjectId("..."),
  "user_id": "user_abc123",
  "type": "send",
  "currency": "BTC",
  "amount": NumberDecimal("0.50000000"),
  "fee": NumberDecimal("0.00001000"),
  "status": "completed",
  "counterparty": {
    "type": "internal",
    "user_id": "user_xyz789"
  },
  "blockchain": {
    "tx_hash": "abc123...",
    "confirmations": 6,
    "block_number": 780000
  },
  "timestamps": {
    "initiated": ISODate("2024-03-01T10:00:00Z"),
    "confirmed": ISODate("2024-03-01T10:45:00Z")
  }
}
```

---

## Use Case 3: Forbes Content Management

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              Forbes CMS - Dynamic Content Publishing                 │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Editor  │───▶│   CMS API    │───▶│   MongoDB    │───▶│   CDN Edge   │
│  (React) │    │   (Node.js)  │    │   (Primary)  │    │   (Fastly)   │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                       │                    │
                       │                    ▼
                       │            ┌──────────────┐
                       │            │ Change Stream│───▶ Invalidate CDN
                       │            └──────────────┘     + Update Search
                       ▼
                ┌──────────────┐
                │ Real-time    │
                │ Preview      │
                │ (WebSocket)  │
                └──────────────┘

Content Model:
┌─────────────────────────────────────────────────┐
│  Article                                         │
│  ├── metadata (title, author, tags, SEO)        │
│  ├── body[] (rich content blocks)               │
│  │   ├── {type: "paragraph", text: "..."}      │
│  │   ├── {type: "image", url: "...", cap: ""}  │
│  │   ├── {type: "embed", provider: "youtube"}  │
│  │   └── {type: "pullquote", text: "..."}      │
│  ├── versions[] (draft history)                 │
│  └── publishing (schedule, status, channels)    │
└─────────────────────────────────────────────────┘
```

---

## Use Case 4: Cisco IoT Platform

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              Cisco IoT - Device Telemetry at Scale                   │
└─────────────────────────────────────────────────────────────────────┘

IoT Devices (millions):
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Sensor│ │Router│ │Camera│ │Switch│
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
   │        │        │        │
   └────────┴────────┴────────┘
                │
                ▼  (MQTT/HTTP)
       ┌──────────────────┐
       │  Message Broker  │
       │  (Kafka/MQTT)    │
       └────────┬─────────┘
                │
       ┌────────┼────────┐
       │        │        │
       ▼        ▼        ▼
┌──────────┐ ┌────────┐ ┌────────────┐
│ MongoDB  │ │ Alert  │ │ Time Series│
│ (device  │ │ Engine │ │ (metrics)  │
│  state)  │ │        │ │            │
└──────────┘ └────────┘ └────────────┘

MongoDB Collections:
┌─────────────────────────────────────────────────────────┐
│  devices (current state):                                │
│    Shard Key: { org_id: 1, device_id: 1 }               │
│    ~50M documents                                        │
│                                                          │
│  telemetry (time series - MongoDB 5.0+):                │
│    Time Series Collection:                               │
│      timeField: "timestamp"                             │
│      metaField: "device_id"                             │
│      granularity: "seconds"                             │
│    ~100B data points                                     │
│                                                          │
│  device_configs (desired state):                         │
│    Shard Key: { org_id: 1, device_id: 1 }               │
└─────────────────────────────────────────────────────────┘
```

### Document Schema

```javascript
// Device state document
{
  "_id": ObjectId("..."),
  "org_id": "cisco_customer_123",
  "device_id": "ISR-4451-X-SN123456",
  "device_type": "router",
  "model": "ISR 4451-X",
  "firmware_version": "17.3.4",
  "status": "online",
  "location": {
    "type": "Point",
    "coordinates": [-122.4194, 37.7749]
  },
  "interfaces": [
    { "name": "GigabitEthernet0/0", "status": "up", "speed": "1000Mbps", "ip": "10.0.1.1" },
    { "name": "GigabitEthernet0/1", "status": "down", "speed": "1000Mbps" }
  ],
  "metrics_latest": {
    "cpu_percent": 45.2,
    "memory_percent": 72.1,
    "temperature_celsius": 52,
    "uptime_seconds": 8640000
  },
  "last_seen": ISODate("2024-03-01T14:30:00Z"),
  "tags": ["production", "datacenter-us-west", "critical"]
}

// Time Series document (MongoDB 5.0+ native time series)
{
  "timestamp": ISODate("2024-03-01T14:30:00Z"),
  "device_id": "ISR-4451-X-SN123456",
  "metrics": {
    "cpu_percent": 45.2,
    "memory_percent": 72.1,
    "packets_in": 1500000,
    "packets_out": 1200000,
    "errors_in": 0,
    "errors_out": 2
  }
}
```

---

## Use Case 5: Adobe Experience Platform

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│         Adobe Experience Platform - User Profile Storage             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────────────────────────┐
│  Adobe   │───▶│  Profile API │───▶│     MongoDB Atlas (Multi-Region) │
│  Apps    │    │  (GraphQL)   │    │                                   │
│(Photoshop│    └──────────────┘    │  ┌────────────┐ ┌────────────┐  │
│ Creative │                        │  │ US-East    │ │ EU-West    │  │
│ Cloud)   │                        │  │ (Primary)  │ │ (Secondary)│  │
└──────────┘                        │  └────────────┘ └────────────┘  │
                                    │                                   │
     ┌──────────┐                   │  Zone Sharding:                  │
     │  Events  │───────────────────│  US users → US shard             │
     │  (Kafka) │  Profile updates  │  EU users → EU shard (GDPR)     │
     └──────────┘                   └──────────────────────────────────┘

User Profile Model (deeply nested, schema-flexible):
┌─────────────────────────────────────────────────────────┐
│  {                                                       │
│    user_id: "adobe_user_123",                           │
│    identity_graph: [                                     │
│      { type: "email", value: "user@example.com" },     │
│      { type: "ecid", value: "MCID|123..." },           │
│      { type: "phone", value: "+1..." }                 │
│    ],                                                    │
│    segments: ["premium", "photographer", "us-west"],    │
│    preferences: {                                        │
│      language: "en",                                     │
│      notifications: { email: true, push: false },       │
│      creative_cloud: { storage_used_gb: 45.2, ... }    │
│    },                                                    │
│    behaviors: {                                          │
│      last_login: ISODate("..."),                        │
│      apps_used: ["Photoshop", "Lightroom"],             │
│      content_created_30d: 150                           │
│    }                                                     │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Replication Deep Dive

### Replica Set Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MongoDB Replica Set                               │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │      PRIMARY        │
                    │                     │
                    │  - Accepts writes   │
                    │  - Default reads    │
                    │  - Oplog (capped    │
                    │    collection)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────┼──────────┐
                    │ Oplog    │ Oplog    │
                    │ tailing  │ tailing  │
                    ▼          ▼          ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  SECONDARY 1 │  │  SECONDARY 2 │  │   ARBITER    │
         │              │  │              │  │  (no data)   │
         │  - Read (if  │  │  - Read (if  │  │  - Votes in  │
         │    preference│  │    preference│  │    elections │
         │    allows)   │  │    allows)   │  │  - Tie-break │
         │  - Failover  │  │  - Failover  │  │              │
         │    candidate │  │    candidate │  │              │
         └──────────────┘  └──────────────┘  └──────────────┘

Oplog (Operation Log):
┌────────────────────────────────────────────────────────┐
│ { ts: Timestamp(1709312400, 1),                        │
│   op: "i",              // i=insert, u=update, d=del  │
│   ns: "mydb.orders",   // namespace                   │
│   o: { _id: ..., ... } // document                    │
│ }                                                      │
│                                                        │
│ Oplog is a capped collection in local.oplog.rs        │
│ Default size: 5% of free disk (max 50GB)              │
│ Secondaries tail the oplog continuously               │
└────────────────────────────────────────────────────────┘
```

### Election Process

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Election Timeline                                  │
└─────────────────────────────────────────────────────────────────────┘

Time ──────────────────────────────────────────────────────────────▶

T=0s     Primary heartbeat stops
         ┌─────────┐
         │ PRIMARY │ ✗ (crashes)
         └─────────┘

T=10s    Election timeout (electionTimeoutMillis: 10000)
         Secondary detects primary unreachable
         ┌───────────────┐
         │ SECONDARY 1   │──── "I want to be primary"
         │ (highest       │     (RequestVote RPC)
         │  priority/     │
         │  most recent)  │
         └───────────────┘

T=10.1s  Voting
         ┌───────────────┐  VOTE YES  ┌───────────────┐
         │ SECONDARY 2   │───────────▶│ SECONDARY 1   │
         └───────────────┘            └───────────────┘
         ┌───────────────┐  VOTE YES  ┌───────────────┐
         │   ARBITER     │───────────▶│ SECONDARY 1   │
         └───────────────┘            └───────────────┘

T=10.2s  New Primary elected (majority votes received)
         ┌───────────────┐
         │ NEW PRIMARY   │  ← SECONDARY 1 promoted
         │ (steps up)    │
         └───────────────┘

Total failover: ~12 seconds (typical)
- Detection: 10s (electionTimeoutMillis)
- Election: 0.1-2s
- DNS/driver awareness: 1-5s
```

### Write Concerns & Read Concerns

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Write Concern Options                                │
└─────────────────────────────────────────────────────────────────────┘

w: 1 (default)          w: "majority"           w: 3 (all nodes)
┌─────────┐             ┌─────────┐             ┌─────────┐
│ Primary │ ← ACK      │ Primary │             │ Primary │
│ (wrote) │             │ (wrote) │             │ (wrote) │
└─────────┘             └────┬────┘             └────┬────┘
                             │ replicate              │ replicate
                        ┌────┼────┐             ┌────┼────┐
                        ▼         ▼             ▼         ▼
                   ┌────────┐┌────────┐    ┌────────┐┌────────┐
                   │Sec 1   ││Sec 2   │    │Sec 1   ││Sec 2   │
                   │(wrote) ││        │    │(wrote) ││(wrote) │
                   └────────┘└────────┘    └────────┘└────────┘
                        │ ← ACK (2/3)          │         │
                        └────────────┘         └─────────┘ ← ACK

Durability:    Lowest              High                 Highest
Performance:   Fastest             Medium               Slowest
Risk:          Data loss if        Survives minority    Zero loss
               primary fails       failures             (but slow)

┌─────────────────────────────────────────────────────────────────────┐
│                 Read Concern Options                                 │
└─────────────────────────────────────────────────────────────────────┘

"local"       - Returns latest data on queried node (may be rolled back)
"available"   - Like local but for sharded (no orphan filtering)
"majority"    - Returns data acknowledged by majority (durable)
"snapshot"    - Point-in-time consistent read (for transactions)
"linearizable"- Reflects all successful majority writes prior to read

Causal Consistency:
  session.startSession({ causalConsistency: true })
  → "read your own writes" guarantee across replica set
```

### Cross-Datacenter Replication

```
┌─────────────────────────────────────────────────────────────────────┐
│           Multi-Region Replica Set Deployment                       │
└─────────────────────────────────────────────────────────────────────┘

       US-East (Primary DC)          EU-West (DR DC)
    ┌────────────────────────┐    ┌────────────────────────┐
    │                        │    │                        │
    │  ┌─────────────────┐   │    │  ┌─────────────────┐   │
    │  │    PRIMARY      │   │    │  │   SECONDARY 3   │   │
    │  │  (priority: 10) │   │    │  │  (priority: 0)  │   │
    │  └─────────────────┘   │    │  │  (votes: 1)     │   │
    │                        │    │  │  (hidden: true)  │   │
    │  ┌─────────────────┐   │    │  └─────────────────┘   │
    │  │  SECONDARY 1    │   │    │                        │
    │  │  (priority: 8)  │   │    │  ┌─────────────────┐   │
    │  └─────────────────┘   │    │  │   SECONDARY 4   │   │
    │                        │    │  │  (priority: 0)  │   │
    │  ┌─────────────────┐   │    │  │  (delayed: 1hr) │   │
    │  │  SECONDARY 2    │   │    │  └─────────────────┘   │
    │  │  (priority: 5)  │   │    │                        │
    │  └─────────────────┘   │    └────────────────────────┘
    │                        │
    └────────────────────────┘

Settings:
- US nodes have higher priority (stay primary in US)
- EU nodes: priority=0 (never become primary automatically)
- Delayed member: 1-hour lag for accidental deletion recovery
- Read preference: "nearest" for geo-local reads
- Write concern: { w: "majority", wtimeout: 5000 }
```

---

## Scalability Patterns

### Sharding Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                MongoDB Sharded Cluster                               │
└─────────────────────────────────────────────────────────────────────┘

  Application
       │
       ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   mongos    │  │   mongos    │  │   mongos    │   (Stateless routers)
│  (router)   │  │  (router)   │  │  (router)   │   Deploy with app
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
              ┌─────────▼─────────┐
              │   Config Server   │  (CSRS: 3-node replica set)
              │   Replica Set     │  Stores: chunk map, shard metadata
              └─────────┬─────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Shard 1    │ │   Shard 2    │ │   Shard 3    │
│ (Replica Set)│ │ (Replica Set)│ │ (Replica Set)│
│              │ │              │ │              │
│ Chunks:      │ │ Chunks:      │ │ Chunks:      │
│ [min, "F")   │ │ ["F", "N")   │ │ ["N", max)   │
│              │ │              │ │              │
│ P + S + S    │ │ P + S + S    │ │ P + S + S    │
└──────────────┘ └──────────────┘ └──────────────┘

Chunk: 64MB (default) range of shard key values
Balancer: Background process that migrates chunks between shards
```

### Shard Key Selection

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Shard Key Selection Guide                           │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┬───────────────┬───────────────┬──────────────┐
│ Strategy             │ Cardinality   │ Distribution  │ Query Target │
├──────────────────────┼───────────────┼───────────────┼──────────────┤
│ Hashed (_id)         │ High          │ Even          │ Scatter      │
│ { _id: "hashed" }   │               │ (random)      │ (bad for     │
│                      │               │               │  range)      │
├──────────────────────┼───────────────┼───────────────┼──────────────┤
│ Ranged (timestamp)   │ High          │ Monotonic     │ Targeted     │
│ { created_at: 1 }   │               │ (HOT SHARD!)  │ (range good) │
│                      │               │               │              │
├──────────────────────┼───────────────┼───────────────┼──────────────┤
│ Compound             │ High          │ Even          │ Targeted     │
│ {tenant_id:1, _id:1}│               │               │ (best of     │
│                      │               │               │  both)       │
├──────────────────────┼───────────────┼───────────────┼──────────────┤
│ Zone sharding        │ Varies        │ Controlled    │ Geo-local    │
│ (geo-based)          │               │ (by zone)    │              │
└──────────────────────┴───────────────┴───────────────┴──────────────┘

BAD Shard Keys:
✗ { status: 1 }         → Low cardinality (only "active"/"inactive")
✗ { created_at: 1 }     → Monotonically increasing → all writes to 1 shard
✗ { country: 1 }        → Low cardinality + uneven (US gets 50%+ traffic)

GOOD Shard Keys:
✓ { user_id: "hashed" }          → Even distribution, targeted by user
✓ { tenant_id: 1, created_at: 1} → Locality per tenant + time range queries
✓ { device_id: "hashed" }        → Even distribution for IoT workloads
```

---

## Production Setup

### WiredTiger Tuning

```
┌─────────────────────────────────────────────────────────────────────┐
│                  mongod.conf Production Settings                     │
└─────────────────────────────────────────────────────────────────────┘

storage:
  dbPath: /data/mongodb
  engine: wiredTiger
  wiredTiger:
    engineConfig:
      cacheSizeGB: 100          # Rule: 50% of RAM - 1GB
                                # For 256GB RAM: (256-1)*0.5 = 127GB
      journalCompressor: snappy
      directoryForIndexes: true  # Separate disk for indexes
    collectionConfig:
      blockCompressor: snappy    # or zstd for better ratio
    indexConfig:
      prefixCompression: true

net:
  port: 27017
  maxIncomingConnections: 65536
  compression:
    compressors: [snappy, zstd]  # Network compression

replication:
  replSetName: rs0
  oplogSizeMB: 51200            # 50GB oplog (more = longer repl window)

setParameter:
  wiredTigerConcurrentReadTransactions: 128   # default
  wiredTigerConcurrentWriteTransactions: 128  # default
```

### Hardware Recommendations

```
┌─────────────────────────────────────────────────────────────────────┐
│              MongoDB Hardware Sizing                                  │
└─────────────────────────────────────────────────────────────────────┘

Golden Rule: Working Set (indexes + hot data) MUST fit in RAM

Small (< 50GB data):
├── CPU: 4-8 cores
├── RAM: 32 GB (WiredTiger cache: 15GB)
├── Storage: 200GB NVMe SSD (XFS filesystem)
└── Network: 10 Gbps

Medium (50GB-500GB data):
├── CPU: 16-32 cores
├── RAM: 128 GB (WiredTiger cache: 63GB)
├── Storage: 1-2TB NVMe SSD
├── Separate disk for journal
└── Network: 25 Gbps

Large (500GB+ data per shard):
├── CPU: 32-64 cores
├── RAM: 256 GB (WiredTiger cache: 127GB)
├── Storage: 4TB+ NVMe SSD (RAID10)
├── Separate disk for journal + indexes
└── Network: 25-100 Gbps

Disk IOPS Requirements:
- Writes: ~1000 IOPS per 1000 writes/sec (journaling)
- Reads (cache miss): 1 random read per cache miss
- Recommendation: 10K+ IOPS for production workloads
```

---

## Core Concepts

### WiredTiger Storage Engine

```
┌─────────────────────────────────────────────────────────────────────┐
│                WiredTiger Architecture                               │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │         WiredTiger Cache         │
                    │         (in-memory)              │
                    │                                 │
                    │  ┌──────────┐ ┌──────────┐     │
                    │  │ Clean    │ │ Dirty    │     │
                    │  │ Pages    │ │ Pages    │     │
                    │  └──────────┘ └──────────┘     │
                    │                                 │
                    │  B-Tree pages (data + index)    │
                    │  Document-level concurrency     │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────┬┴────────────────┐
                    │                │                 │
                    ▼                ▼                 ▼
           ┌──────────────┐ ┌──────────────┐  ┌──────────────┐
           │   Journal    │ │  Data Files  │  │ Checkpoint   │
           │  (WAL, every │ │  (.wt files) │  │ (every 60s)  │
           │   100ms or   │ │              │  │              │
           │   100MB)     │ │  Compressed  │  │  Consistent  │
           │              │ │  (snappy/    │  │  snapshot    │
           │  Durability  │ │   zstd)      │  │  to disk     │
           └──────────────┘ └──────────────┘  └──────────────┘

Write Path:
1. Document modification in WiredTiger cache (dirty page)
2. Journal entry written (every 100ms batch - configurable)
3. Checkpoint flushes dirty pages to data files (every 60s)
4. Between checkpoints: journal provides durability

Concurrency:
- Document-level locking (not collection-level)
- Multiple readers + single writer per document
- Readers don't block writers, writers don't block readers (MVCC)
- Ticket-based admission control (128 read + 128 write tickets)
```

### Index Types

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MongoDB Index Types                               │
└─────────────────────────────────────────────────────────────────────┘

1. Single Field:
   db.users.createIndex({ email: 1 })
   → B-tree on single field, supports equality + range + sort

2. Compound Index:
   db.orders.createIndex({ customer_id: 1, created_at: -1 })
   → Supports queries on prefix fields (ESR rule: Equality, Sort, Range)

3. Multikey Index (arrays):
   db.products.createIndex({ tags: 1 })
   → One index entry per array element
   → Cannot compound two multikey fields

4. Text Index:
   db.articles.createIndex({ title: "text", body: "text" })
   → Full-text search with stemming, stop words, weights

5. 2dsphere Index (geospatial):
   db.stores.createIndex({ location: "2dsphere" })
   → GeoJSON queries ($near, $geoWithin, $geoIntersects)

6. Wildcard Index:
   db.products.createIndex({ "attributes.$**": 1 })
   → Indexes all fields under a path (for flexible schemas)

7. Hashed Index:
   db.users.createIndex({ user_id: "hashed" })
   → Even distribution for shard keys, equality only

8. TTL Index:
   db.sessions.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 })
   → Auto-delete documents after time (background thread checks every 60s)

ESR Rule for Compound Indexes:
┌────────────────────────────────────────────────────┐
│  E = Equality fields first   (status: "active")   │
│  S = Sort fields next        (created_at: -1)     │
│  R = Range fields last       (price: {$gt: 100})  │
│                                                    │
│  Index: { status: 1, created_at: -1, price: 1 }   │
└────────────────────────────────────────────────────┘
```

### Change Streams

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Change Streams                                    │
└─────────────────────────────────────────────────────────────────────┘

// Watch for changes in real-time (uses oplog tailing)
const pipeline = [
  { $match: { "operationType": { $in: ["insert", "update"] } } },
  { $match: { "fullDocument.status": "urgent" } }
];

const changeStream = db.collection("orders").watch(pipeline, {
  fullDocument: "updateLookup"  // include full doc on updates
});

changeStream.on("change", (event) => {
  // event structure:
  // {
  //   _id: { _data: "..." },         // resume token
  //   operationType: "insert",
  //   clusterTime: Timestamp(...),
  //   ns: { db: "mydb", coll: "orders" },
  //   documentKey: { _id: ObjectId("...") },
  //   fullDocument: { ... }
  // }
});

Use Cases:
- Real-time notifications
- Cache invalidation
- Event-driven architectures
- Data synchronization to other systems
- Audit logging

Guarantees:
- Ordered (by oplog order)
- Resumable (via resume token)
- At-least-once delivery
- Available on replica sets and sharded clusters
```
