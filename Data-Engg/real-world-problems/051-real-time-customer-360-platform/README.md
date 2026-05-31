# Problem 51: Real-Time Customer 360 Platform

## Problem 51: Real-Time Customer 360 Platform

### Business Context
Enterprise needs unified customer view combining data from 20+ systems 
(CRM, support tickets, transactions, web behavior, mobile app, email, social).

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              CUSTOMER 360 PLATFORM                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA SOURCES (20+ Systems)                                                  │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                │
│  │CRM │ │ERP │ │Web │ │App │ │Email│ │Chat│ │Social│ │POS │               │
│  └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └─┬──┘ └──┬──┘ └─┬──┘              │
│    │       │      │      │      │      │       │       │                    │
│  ┌─▼───────▼──────▼──────▼──────▼──────▼───────▼───────▼────────┐         │
│  │  IDENTITY RESOLUTION ENGINE                                    │         │
│  │                                                                │         │
│  │  CHALLENGE: Same person = different IDs in each system         │         │
│  │  • CRM: customer_123                                           │         │
│  │  • Web: cookie_abc                                             │         │
│  │  • App: device_xyz                                             │         │
│  │  • Email: john@email.com                                       │         │
│  │                                                                │         │
│  │  SOLUTION: Probabilistic + Deterministic matching              │         │
│  │  Deterministic: Same email/phone → same person (100%)          │         │
│  │  Probabilistic: Same name + address + behavior (90%+ conf)     │         │
│  │                                                                │         │
│  │  Output: Unified customer_id (golden record)                   │         │
│  │  Tech: Spark + Graph algorithms (connected components)         │         │
│  └──────────────────────────┬─────────────────────────────────────┘        │
│                              │                                               │
│  ┌───────────────────────────▼────────────────────────────────────┐         │
│  │  UNIFIED PROFILE STORE                                          │         │
│  │                                                                 │         │
│  │  Storage: Cassandra (wide rows per customer)                    │         │
│  │  + Redis (hot profiles, real-time attributes)                   │         │
│  │  + Elasticsearch (profile search)                               │         │
│  │                                                                 │         │
│  │  Profile Schema:                                                │         │
│  │  {                                                              │         │
│  │    "customer_id": "C360-uuid",                                  │         │
│  │    "identifiers": ["email:x", "phone:y", "cookie:z"],           │         │
│  │    "demographics": {"age": 35, "location": "NYC"},              │         │
│  │    "behavioral": {"ltv": 5000, "segment": "high_value"},        │         │
│  │    "real_time": {"last_page": "/cart", "session_active": true},  │        │
│  │    "preferences": {"channels": ["email", "sms"]},               │         │
│  │    "risk_score": 0.12,                                          │         │
│  │    "last_updated": "2024-01-15T10:30:00Z"                       │         │
│  │  }                                                              │         │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  REAL-TIME UPDATES:                                                          │
│  • Flink processes events from all sources                                   │
│  • Updates profile attributes within 5 seconds                               │
│  • Triggers: personalization, next-best-action, churn prediction             │
│                                                                              │
│  SCALABILITY:                                                                │
│  • 100M customer profiles                                                    │
│  • 1B events/day across all sources                                          │
│  • Profile lookup: <5ms (Redis) or <20ms (Cassandra)                         │
│  • Identity resolution batch: Runs hourly (Spark, 500 nodes)                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Each Technology?
```
WHY CASSANDRA for profile store?
→ Wide rows: All customer data in one partition (fast read)
→ Write-optimized: Handle 1B events/day without breaking
→ Horizontal scaling: Add nodes for more customers
→ Multi-DC: Replicate profiles globally for low latency

WHY REDIS for real-time layer?
→ Sub-ms reads for active session data
→ TTL for session expiry (auto-cleanup)
→ Pub/Sub for real-time profile change notifications
→ Trade-off: Memory-bound, only hot profiles

WHY SPARK for identity resolution?
→ Graph algorithms (connected components) at scale
→ Handles 100M+ nodes in identity graph
→ Batch is acceptable (hourly refresh)
→ Alternative: Real-time dedup with Flink (for new matches)
```

