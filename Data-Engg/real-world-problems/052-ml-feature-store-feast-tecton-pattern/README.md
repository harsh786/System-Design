# Problem 52: ML Feature Store (Feast/Tecton Pattern)

## Problem 52: ML Feature Store (Feast/Tecton Pattern)

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              ML FEATURE STORE ARCHITECTURE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FEATURE COMPUTATION                                                         │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  BATCH FEATURES (Spark, daily/hourly)                           │         │
│  │  • user_avg_spend_30d                                           │         │
│  │  • user_purchase_frequency                                      │         │
│  │  • product_popularity_score                                     │         │
│  │  • user_churn_probability                                       │         │
│  │                                                                 │         │
│  │  → Writes to: Offline Store (Delta Lake / BigQuery)              │         │
│  │  → Materializes to: Online Store (Redis / DynamoDB)              │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  STREAMING FEATURES (Flink, real-time)                          │         │
│  │  • user_clicks_last_5min                                        │         │
│  │  • cart_value_current_session                                   │         │
│  │  • items_viewed_this_session                                    │         │
│  │  • time_on_page_current                                         │         │
│  │                                                                 │         │
│  │  → Writes to: Online Store (Redis) directly                     │         │
│  │  → Also logs to: Offline Store (for training consistency)       │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  FEATURE REGISTRY (Metadata)                                                 │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  • Feature definitions (name, type, description)                │         │
│  │  • Data sources and transformations                             │         │
│  │  • Feature freshness SLAs                                       │         │
│  │  • Feature lineage                                              │         │
│  │  • Feature statistics (distribution, drift)                     │         │
│  │  • Access control (who can use which features)                  │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  SERVING                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                                                                 │         │
│  │  ONLINE SERVING (Real-time inference):                          │         │
│  │  ┌─────────────────────────────────────────────────┐           │         │
│  │  │  Model requests features by entity_id            │           │         │
│  │  │  Feature Store returns pre-computed values       │           │         │
│  │  │  Latency: <5ms (Redis lookup)                    │           │         │
│  │  │  Throughput: 100K requests/sec                   │           │         │
│  │  └─────────────────────────────────────────────────┘           │         │
│  │                                                                 │         │
│  │  OFFLINE SERVING (Training):                                    │         │
│  │  ┌─────────────────────────────────────────────────┐           │         │
│  │  │  Point-in-time correct feature retrieval         │           │         │
│  │  │  "What were this user's features on Jan 1?"      │           │         │
│  │  │  Prevents DATA LEAKAGE (future info in training) │           │         │
│  │  │  Reads from: Delta Lake with time-travel         │           │         │
│  │  └─────────────────────────────────────────────────┘           │         │
│  │                                                                 │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  CRITICAL CONCEPT: TRAINING-SERVING SKEW                                     │
│  ═══════════════════════════════════════                                      │
│  Problem: Features computed differently in training vs serving → bad model   │
│  Solution: Same feature definitions used for both (single source of truth)   │
│  Feature Store ensures: EXACT SAME computation, just different time ranges   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

