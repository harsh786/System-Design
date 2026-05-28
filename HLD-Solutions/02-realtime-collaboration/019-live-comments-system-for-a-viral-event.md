# Design Live Comments System for Viral Events

## 1. Functional Requirements

- **Real-time comment streaming**: Display comments as they arrive during live events
- **High-throughput ingestion**: Handle millions of comments/second during viral moments
- **Comment moderation**: Real-time filtering of spam, hate speech, profanity
- **Rate limiting**: Per-user rate limits to prevent spam flooding
- **Reactions/Likes**: Quick emoji reactions on live comments
- **Pinned comments**: Host can pin important comments
- **Comment threading**: Reply to specific comments (limited depth)
- **Top comments**: Surface popular/relevant comments via ranking
- **Slow mode**: Configurable delay between user posts (1s, 5s, 30s)
- **Follower/subscriber only mode**: Restrict commenting to subscribers
- **Highlighted messages**: Paid/super chat style highlighted comments
- **Comment count**: Real-time total comment counter
- **Replay**: View comments synced to video playback for VOD

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.9% (during live events) |
| Ingestion latency | < 100ms from post to visible |
| Peak throughput | 10M comments/second (World Cup final, NYE) |
| Fanout | Single event with 50M+ concurrent viewers |
| Delivery | Best-effort (dropping OK under extreme load) |
| Moderation | < 200ms to filter/flag before display |
| Comment ordering | Approximate ordering (not strict) |
| Scale gracefully | Degrade gracefully: drop low-value comments first |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| Peak concurrent viewers (mega event) | 50M |
| Average concurrent viewers | 5M |
| Comments/sec (peak viral) | 10M |
| Comments/sec (average event) | 100K |
| Average comment size | 200 bytes |
| Ingress (peak) | 10M × 200B = 2 GB/s |
| Egress (peak) | Not all comments delivered to all; sampled 100 comments/s × 50M = 1 TB/s (impossible) |
| Solution: Each viewer sees sampled subset | 50M viewers × 100 comments/s × 200B = 1 TB/s → must sample |
| Actual per-viewer delivery | 20-50 comments/second (human readable rate) |
| Actual egress | 50M × 50 × 200B = 500 GB/s (still huge, needs CDN/edge) |

### Key Insight: Sampling is mandatory for viral events

## 4. Data Modeling

### Storage

| Store | Technology | Purpose |
|---|---|---|
| Live comments stream | Kafka | Ordered ingestion, partitioned by event |
| Comment persistence | Cassandra | High write, time-series per event |
| Moderation ML | Redis + ML service | Real-time scoring |
| Top comments | Redis sorted set | Real-time ranking |
| Rate limits | Redis | Sliding window counters |
| Event metadata | PostgreSQL | Event config, moderators |
| Analytics | ClickHouse | Engagement metrics |

### Schema

```sql
-- Cassandra: Comments per event
CREATE TABLE event_comments (
    event_id UUID,
    comment_id TIMEUUID,
    user_id BIGINT,
    content TEXT,
    type VARCHAR, -- normal, super_chat, pinned, system
    amount DECIMAL, -- for paid highlights
    moderation_status VARCHAR, -- approved, filtered, pending
    score FLOAT, -- relevance/popularity score
    reactions MAP<TEXT, INT>, -- emoji → count
    created_at TIMESTAMP,
    PRIMARY KEY ((event_id), comment_id)
) WITH CLUSTERING ORDER BY (comment_id DESC);

-- Redis: Live state
event:{event_id}:top_comments → ZSET (comment_id, score) -- top 100
event:{event_id}:count → INT (total comment count)
event:{event_id}:rate → INT (comments per second)
ratelimit:{event_id}:{user_id} → sliding window counter
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              VIEWERS (50M+)                                      │
│   App/Web clients connected via WebSocket or Server-Sent Events                 │
└───────────────────────────────────┬────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────────────┐
│                    EDGE DELIVERY LAYER (CDN/Edge Compute)                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Edge Nodes (Cloudflare Workers / CloudFront Lambda@Edge)                │   │
│  │  - Serve sampled comment stream per region                               │   │
│  │  - Reduce origin load by 99%                                             │   │
│  │  - Each edge node gets full stream, samples for its viewers              │   │
│  │  - Cache top comments, pinned comments                                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────────────┐
│                         COMMENT INGESTION                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │  Rate Limiter    │→ │  Moderation      │→ │  Comment Router              │ │
│  │  - Per user      │  │  - ML filter     │  │  - Write to Kafka            │ │
│  │  - Per event     │  │  - Keyword block  │  │  - Update counters           │ │
│  │  - Slow mode     │  │  - Spam detection │  │  - Score & rank              │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────────────┐
│                       STREAM PROCESSING                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │  Kafka           │→ │  Flink/Sampler   │→ │  Fan-out to Edge Nodes       │ │
│  │  (event stream)  │  │  - Top comments  │  │  - Push to regional edges    │ │
│  │                  │  │  - Sampling algo  │  │  - SSE/WS endpoints         │ │
│  │                  │  │  - Rate control   │  │                              │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Comment Sampling Strategy

```
Problem: 10M comments/sec → viewer can only read 50/sec

Strategy: Multi-tier Sampling
┌─────────────────────────────────────────────────────────┐
│  Tier 1 - ALWAYS SHOW (bypass sampling):                │
│    - Pinned comments from host                          │
│    - Super chat / paid highlights                       │
│    - Comments from followed users                       │
│    - Comments with high engagement (many reactions)     │
│                                                          │
│  Tier 2 - PRIORITY SAMPLE:                              │
│    - Comments from verified accounts                    │
│    - Comments with @mentions                            │
│    - Questions (detected via NLP: ends with ?)          │
│    - Comments with media/links                          │
│                                                          │
│  Tier 3 - RANDOM SAMPLE:                                │
│    - Reservoir sampling from remaining comments         │
│    - Weighted by recency (newer = more likely)          │
│    - Rate: fill remaining slots to reach target rate    │
│                                                          │
│  Delivery rate per viewer: 30-50 comments/second        │
│  Viewport: show last 100-200 comments in scrollable UI │
└─────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design - APIs

```
# Post a comment
POST /api/v1/events/{event_id}/comments
Request: {"content": "Amazing goal! ⚽️", "type": "normal", "reply_to": null}
Response: {"id": "c_123", "status": "published", "timestamp": 1716672000}

# SSE Stream for viewers
GET /api/v1/events/{event_id}/comments/stream
Accept: text/event-stream
Response:
  event: comment
  data: {"id":"c_123","user":"John","content":"Amazing!","ts":1716672000}
  
  event: comment
  data: {"id":"c_124","user":"Jane","content":"What a save!","ts":1716672001}
  
  event: pinned
  data: {"id":"c_100","user":"Host","content":"Welcome everyone!"}
  
  event: stats
  data: {"total_comments":5000000,"rate":85000,"viewers":45000000}

# React to comment
POST /api/v1/events/{event_id}/comments/{comment_id}/react
Request: {"emoji": "🔥"}
Response: {"ok": true, "count": 1542}

# Host: Pin comment
POST /api/v1/events/{event_id}/comments/{comment_id}/pin
Response: {"ok": true}
```

## 7. Component Deep Dive

### Moderation Pipeline (< 200ms)
```
1. Keyword blocklist check (Redis, <1ms)
2. Rate limit check (Redis, <1ms)  
3. ML model inference (GPU, <50ms):
   - Toxicity score
   - Spam probability
   - Sentiment analysis
4. Decision: approve / reject / hold for review
5. If approved: forward to stream
6. If rejected: notify user, don't publish
7. If hold: publish with "pending" flag, human reviews

At 10M comments/sec:
- Need 200+ GPU instances for ML inference
- Batch inference: process 100 comments per batch
- Pipeline: async, don't block post if moderation slow
- Fallback: if ML overloaded, use keyword-only filter
```

### Graceful Degradation Under Load
```
Load Levels:
  Level 0 (Normal, <100K/s): All comments processed, full moderation
  Level 1 (High, 100K-1M/s): Sample moderation (every 10th comment)
  Level 2 (Extreme, 1M-5M/s): Keyword-only filter, increase sampling
  Level 3 (Viral, >5M/s): Subscriber-only mode, heavy sampling, deferred persistence
  
Auto-trigger: based on Kafka consumer lag + processing latency
```

## 8. Optimization

### Kafka Configuration
```
Topic: events.comments.{event_id}
  - 256 partitions (handle 10M/s with batching)
  - Key: event_id (all comments for event in same partition set)
  - Retention: 7 days (for replay feature)
  - Compression: lz4

Consumer Groups:
  moderation-group: filter inappropriate content
  persistence-group: write to Cassandra
  sampling-group: select comments for delivery
  analytics-group: real-time metrics to ClickHouse
```

### Edge Delivery (CDN-based fan-out)
```
Instead of: Origin → 50M individual WebSocket connections (impossible)
Use: Origin → 200 Edge PoPs → 50M connections

Each Edge PoP:
- Receives full approved comment stream from origin (~50K/s after moderation)
- Applies local sampling algorithm for connected viewers
- Delivers 30-50 comments/sec per viewer via SSE
- Caches pinned comments, top comments locally
- Handles reconnection with cursor-based sync

Architecture:
  Origin publishes to Kafka → Regional aggregators consume →
  Push to edge via persistent HTTP/2 connection →
  Edge fans out to viewers via SSE/WebSocket
```

## 9. Observability

```yaml
Metrics:
  comments_ingested_total{event_id}
  comments_per_second_gauge{event_id}
  moderation_latency_seconds{model, quantile}
  moderation_rejected_total{reason}
  sampling_ratio{event_id} # what % of comments reach viewers
  viewer_delivery_latency_seconds{region, quantile}
  edge_connection_count{pop, event_id}
  kafka_consumer_lag{topic, group}

Alerts:
  Critical: ingestion drops to 0, moderation latency > 1s
  Warning: sampling_ratio < 0.01% (extreme dropping), consumer lag > 1M
```

## 10. Considerations

### Key Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| SSE over WebSocket | Simpler, CDN-compatible, one-way sufficient | No bidirectional on same connection |
| Sampling | Handle unlimited scale | Viewers miss most comments |
| Edge delivery | Massive fan-out without origin overload | Complexity, eventual consistency |
| Eventual persistence | Don't bottleneck live on DB | May lose comments if Kafka has issues |
| Approximate counts | Real-time counter updates | Not perfectly accurate |

### Assumptions
- Viewers accept not seeing ALL comments (impossible at scale anyway)
- Comments are ephemeral during live; VOD replay is separate concern
- Mobile viewers tolerate higher latency (buffer 2-3s for smooth scroll)
- Geographic distribution: comments and viewers globally distributed
