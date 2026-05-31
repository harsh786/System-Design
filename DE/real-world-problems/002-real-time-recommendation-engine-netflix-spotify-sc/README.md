# Problem 2: Real-Time Recommendation Engine (Netflix/Spotify Scale)

## Problem 2: Real-Time Recommendation Engine (Netflix/Spotify Scale)

### Business Context
Streaming service with 200M users. Need to update recommendations within 30 seconds
of user action (watch, skip, like, browse).

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│           REAL-TIME RECOMMENDATION ENGINE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER INTERACTIONS                                                           │
│  [Play] [Pause] [Skip] [Like] [Browse] [Search] [Add to List]               │
│         │                                                                    │
│  ┌──────▼───────────────────────────────────────────────────────────┐       │
│  │  KAFKA: user-interactions (1000 partitions)                       │       │
│  │  Key: user_id (ensures order per user)                            │       │
│  │  Throughput: 500K events/sec (200M users × active ratio)          │       │
│  └──────────────┬─────────────────────────────────┬─────────────────┘       │
│                  │                                  │                         │
│  ┌───────────────▼──────────────────┐  ┌───────────▼──────────────────┐     │
│  │  FLINK: Near-RT Feature Update   │  │  SPARK: Batch Model Training │     │
│  │                                   │  │                              │      │
│  │  Updates per user:                │  │  Runs every 6 hours:         │      │
│  │  • Last 10 items interacted      │  │  • Collaborative filtering   │      │
│  │  • Category preferences (decay)  │  │  • Content-based features    │      │
│  │  • Session context               │  │  • ALS matrix factorization  │      │
│  │  • Time-of-day patterns          │  │  • Deep learning embeddings  │      │
│  │                                   │  │                              │      │
│  │  Writes to: Redis (Features)      │  │  Writes to: Feature Store    │     │
│  │  Latency: <5 seconds             │  │  + Model Registry             │     │
│  └───────────────┬──────────────────┘  └──────────────────────────────┘     │
│                   │                                                          │
│  ┌────────────────▼─────────────────────────────────────────────────┐       │
│  │  RECOMMENDATION SERVICE (Serving)                                  │       │
│  │                                                                    │       │
│  │  On user request:                                                  │       │
│  │  1. Fetch user embedding + recent features (Redis, <2ms)           │       │
│  │  2. ANN search for similar items (Milvus/Pinecone, <10ms)         │       │
│  │  3. Candidate generation (1000 items)                              │       │
│  │  4. Ranking model scores candidates (TF Serving, <20ms)           │       │
│  │  5. Business rules (diversity, freshness, filter watched)          │       │
│  │  6. Return top-50 recommendations                                  │       │
│  │                                                                    │       │
│  │  Total latency: <50ms P99                                          │       │
│  │  Cache: 80% hit rate on popular content combos                     │       │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  SCALABILITY:                                                                │
│  • 200M users, 100K concurrent                                               │
│  • Redis: 100-node cluster, 2TB RAM, user features                           │
│  • Milvus: 50-node, 1B item embeddings, HNSW index                          │
│  • Serving: 200 pods, auto-scaled on P99 latency                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Each Technology?
```
WHY KAFKA (not SQS/RabbitMQ)?
→ Replay: Can re-process user history for new models
→ Ordering: User events must be in order (per partition key)
→ Scale: 500K events/sec without breaking a sweat
→ Multi-consumer: Same events go to features AND training

WHY REDIS (not DynamoDB/Cassandra)?
→ Latency: <1ms reads (in recommendation serving hot path)
→ Data structures: Sorted sets for top-N, hashes for features
→ TTL: Auto-expire stale sessions
→ Trade-off: More expensive per GB, but speed is critical

WHY MILVUS/PINECONE (not Elasticsearch)?
→ Purpose-built for vector similarity search
→ HNSW index: O(log n) approximate nearest neighbor
→ 1B vectors searchable in <10ms
→ ES works but 5-10x slower for pure vector search

WHY ALS + DEEP LEARNING (not just one)?
→ ALS: Great for collaborative filtering (users who liked X also liked Y)
→ Deep learning: Captures content features (genre, actors, mood)
→ Together: Handles cold start (new items) + personalization (known users)
```

