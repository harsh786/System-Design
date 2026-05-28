# Twitter/X Timeline System Design

## 1. Functional Requirements

| # | Requirement | Description |
|---|-------------|-------------|
| FR-1 | Post Tweet | Users can post text (280 chars), images (4 max), videos (2m20s), polls, threads |
| FR-2 | Home Timeline | Personalized feed of tweets from followed users + algorithmic recommendations |
| FR-3 | User Timeline | Chronological list of a user's own tweets and retweets |
| FR-4 | Retweet / Quote Tweet | Amplify content with optional commentary |
| FR-5 | Like / Bookmark | Engage with tweets; bookmarks are private |
| FR-6 | Reply / Thread | Nested conversations with parent-child tweet relationships |
| FR-7 | Follow / Unfollow | Directed graph relationship between users |
| FR-8 | Trending Topics | Real-time detection of trending hashtags and topics by region |
| FR-9 | Search | Full-text search across tweets, users, hashtags with filters (date, media, verified) |
| FR-10 | Notifications | Real-time alerts for mentions, likes, retweets, follows, DM |
| FR-11 | Media Upload | Image/video upload with transcoding, thumbnail generation |
| FR-12 | Mute / Block | Content filtering at user and keyword level |

---

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.99% (< 52.6 min downtime/year) |
| Read Latency (p99) | < 200ms for timeline fetch |
| Write Latency (p99) | < 500ms for tweet post (excluding fanout) |
| Fanout Latency (p99) | < 5s for delivery to all followers |
| Scale | 500M DAU, 1.5B MAU |
| Consistency | Eventual consistency for timelines; strong consistency for tweet creation |
| Durability | Zero tweet loss (replicated across 3 AZs) |
| Partition Tolerance | System remains available during network partitions (AP in CAP) |
| Throughput | 200B timeline reads/day |
| Data Retention | Tweets stored indefinitely; timeline cache: 800 most recent |

---

## 3. Capacity Estimation

### Users & Activity

```
DAU = 500M
MAU = 1.5B
Avg tweets/user/day = 1 (active posters ~20% of DAU)
Total tweets/day = 500M
Avg follows per user = 200
Avg followers per user = 200 (median ~50, mean skewed by celebrities)
```

### Timeline Reads

```
Reads/user/day = 400 (heavy refresh pattern)
Total timeline reads/day = 500M × 400 = 200B reads/day
Timeline QPS = 200B / 86400 ≈ 2.3M QPS (avg)
Peak QPS = 2.3M × 3 = ~7M QPS
```

### Tweet Writes

```
Tweet writes/day = 500M
Write QPS = 500M / 86400 ≈ 5,800 QPS (avg)
Peak write QPS = ~17,400 QPS
```

### Fanout Volume

```
Avg fanout per tweet = 200 followers
Total fanout writes/day = 500M × 200 = 100B timeline insertions/day
Fanout QPS = 100B / 86400 ≈ 1.16M QPS
```

### Storage

```
Tweet size (avg):
  - tweet_id: 8B
  - user_id: 8B
  - text: 280B (UTF-8, worst case 1120B)
  - metadata: 200B
  - Total per tweet: ~500B

Daily tweet storage = 500M × 500B = 250GB/day
Yearly tweet storage = 250GB × 365 = ~91TB/year

Media storage (30% tweets have media):
  - Avg media size: 2MB
  - Daily media = 500M × 0.3 × 2MB = 300TB/day

Timeline cache (Redis):
  - Per user: 800 tweet IDs × 8B = 6.4KB
  - Total: 500M × 6.4KB = 3.2TB (fits in Redis cluster)
```

### Bandwidth

```
Outbound (timeline reads):
  - Avg timeline response: 20 tweets × 500B = 10KB (metadata only)
  - Reads/sec: 2.3M
  - Bandwidth: 2.3M × 10KB = 23GB/s ≈ 184Gbps (served via CDN)

Inbound (tweet writes):
  - 5,800 × 500B = 2.9MB/s (negligible for text)
  - Media: 17,400 × 0.3 × 2MB = 10.4GB/s peak
```

---

## 4. Data Modeling

### PostgreSQL — Users & Relationships (Sharded by user_id)

```sql
CREATE TABLE users (
    user_id         BIGINT PRIMARY KEY,          -- Snowflake ID
    username        VARCHAR(15) UNIQUE NOT NULL,
    display_name    VARCHAR(50),
    email           VARCHAR(255) UNIQUE,
    phone           VARCHAR(20),
    bio             TEXT,
    profile_image   VARCHAR(512),
    banner_image    VARCHAR(512),
    follower_count  BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    tweet_count     BIGINT DEFAULT 0,
    is_verified     BOOLEAN DEFAULT FALSE,
    is_celebrity    BOOLEAN DEFAULT FALSE,       -- follower_count > 10K
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- Sharded by follower_id for "who do I follow?" queries
CREATE TABLE follows (
    follower_id     BIGINT NOT NULL,
    followee_id     BIGINT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (follower_id, followee_id)
);

CREATE INDEX idx_follows_followee ON follows(followee_id, created_at DESC);
```

### Cassandra — Tweets (Partitioned by tweet_id)

```cql
CREATE TABLE tweets (
    tweet_id        BIGINT,
    user_id         BIGINT,
    text            TEXT,
    media_urls      LIST<TEXT>,
    reply_to_id     BIGINT,
    retweet_of_id   BIGINT,
    quote_tweet_id  BIGINT,
    hashtags        SET<TEXT>,
    mentions        SET<BIGINT>,
    like_count      COUNTER,
    retweet_count   COUNTER,
    reply_count     COUNTER,
    created_at      TIMESTAMP,
    PRIMARY KEY (tweet_id)
) WITH compaction = {'class': 'LeveledCompactionStrategy'};

-- User timeline (user's own tweets, ordered by time)
CREATE TABLE user_timeline (
    user_id     BIGINT,
    tweet_id    BIGINT,
    created_at  TIMESTAMP,
    PRIMARY KEY (user_id, created_at)
) WITH CLUSTERING ORDER BY (created_at DESC);
```

### Redis — Timeline Cache & Counters

```
# Home timeline: Sorted Set per user, score = tweet timestamp (epoch ms)
ZADD timeline:{user_id} {timestamp} {tweet_id}
ZREVRANGE timeline:{user_id} 0 19          -- Get latest 20

# Tweet engagement counters (avoid Cassandra counter limitations)
HINCRBY tweet:{tweet_id}:counts likes 1
HINCRBY tweet:{tweet_id}:counts retweets 1

# User session / rate limiting
SET rate:{user_id}:{window} {count} EX 60

# Trending topics (Sorted Set, score = velocity)
ZADD trending:{region} {score} {topic}
```

### Elasticsearch — Search Index

```json
{
  "mappings": {
    "properties": {
      "tweet_id": { "type": "long" },
      "user_id": { "type": "long" },
      "username": { "type": "keyword" },
      "text": { "type": "text", "analyzer": "twitter_analyzer" },
      "hashtags": { "type": "keyword" },
      "mentions": { "type": "long" },
      "created_at": { "type": "date" },
      "lang": { "type": "keyword" },
      "like_count": { "type": "integer" },
      "is_verified": { "type": "boolean" },
      "has_media": { "type": "boolean" },
      "geo": { "type": "geo_point" }
    }
  },
  "settings": {
    "number_of_shards": 64,
    "number_of_replicas": 2
  }
}
```

### S3 — Media Storage

```
Bucket structure:
s3://twitter-media/{region}/{year}/{month}/{day}/{user_id}/{media_id}.{ext}
s3://twitter-media-thumbnails/{media_id}_{resolution}.jpg

CDN origin: CloudFront → S3
Lifecycle: Move to S3-IA after 90 days, Glacier after 1 year (non-viral content)
```

### ClickHouse — Analytics

```sql
CREATE TABLE tweet_events (
    event_id        UUID,
    event_type      Enum8('impression'=1, 'like'=2, 'retweet'=3, 'reply'=4, 'click'=5),
    tweet_id        UInt64,
    user_id         UInt64,
    actor_id        UInt64,
    created_at      DateTime,
    region          LowCardinality(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(created_at)
ORDER BY (tweet_id, created_at);
```

---

## 5. High-Level Design

```
                            ┌─────────────────────────────────────────────────────────────┐
                            │                        CLIENTS                               │
                            │   (iOS / Android / Web / TweetDeck / 3rd-party API)          │
                            └──────────────────────────────┬──────────────────────────────┘
                                                           │
                                                    ┌──────▼──────┐
                                                    │   Route 53  │  (DNS + Geo routing)
                                                    └──────┬──────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │    CloudFront CDN       │  (Static + Media)
                                              └────────────┬────────────┘
                                                           │
                                                    ┌──────▼──────┐
                                                    │     WAF      │  (Rate limit, DDoS)
                                                    └──────┬──────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │   ALB (Load Balancer)    │  (L7, sticky sessions)
                                              └────────────┬────────────┘
                                                           │
                                              ┌────────────▼────────────┐
                                              │     API Gateway          │  (Auth, throttle, route)
                                              └─────┬───┬───┬───┬───┬──┘
                                                    │   │   │   │   │
                    ┌───────────────────────────────┐│   │   │   │   │┌──────────────────────┐
                    │                               ││   │   │   │   ││                      │
              ┌─────▼─────┐  ┌──────▼──────┐  ┌────▼───▼┐ ┌▼────▼──┐│  ┌──────▼─────┐  ┌───▼────┐
              │  Tweet     │  │  Timeline   │  │ Fanout  │ │ Search ││  │Notification│  │ Media  │
              │  Service   │  │  Service    │  │ Service │ │Service ││  │  Service   │  │Service │
              └─────┬──────┘  └──────┬──────┘  └────┬────┘ └───┬───┘│  └──────┬─────┘  └───┬────┘
                    │                │               │          │    │         │             │
                    │         ┌──────▼──────┐       │          │    │         │             │
                    │         │  Graph      │       │          │    │         │             │
                    │         │  Service    │       │          │    │         │             │
                    │         └──────┬──────┘       │          │    │         │             │
                    │                │               │          │    │         │             │
              ┌─────▼────────────────▼───────────────▼──────────▼────▼─────────▼─────────────▼────┐
              │                              Kafka (Event Bus)                                      │
              └─────┬────────────────┬───────────────┬──────────┬──────────────┬─────────────┬────┘
                    │                │               │          │              │             │
              ┌─────▼─────┐  ┌──────▼──────┐  ┌────▼────┐ ┌───▼────┐  ┌─────▼─────┐ ┌────▼────┐
              │Cassandra   │  │   Redis     │  │  Flink  │ │  ES    │  │ PostgreSQL│ │   S3    │
              │(Tweets)    │  │  (Cache)    │  │(Stream) │ │(Search)│  │  (Users)  │ │ (Media) │
              └────────────┘  └─────────────┘  └─────────┘ └────────┘  └───────────┘ └─────────┘
                                                    │
                                              ┌─────▼──────┐
                                              │ ClickHouse │  (Analytics)
                                              └────────────┘
```

### Trending Service

Consumes from Kafka stream, uses Flink sliding windows (5m, 15m, 1h) to compute topic velocity. Outputs to Redis sorted set per region.

---

## 6. Low-Level Design — APIs

### REST — Public APIs

#### POST /api/v1/tweets

```json
// Request
{
  "text": "Hello World! #first",
  "media_ids": ["1234567890"],
  "reply_to": null,
  "quote_tweet_id": null,
  "poll": null
}

// Response 201
{
  "id": "1760123456789",
  "text": "Hello World! #first",
  "user": { "id": "42", "username": "harsh", "display_name": "Harsh" },
  "created_at": "2024-02-20T10:30:00Z",
  "metrics": { "likes": 0, "retweets": 0, "replies": 0 }
}
```

#### GET /api/v1/timeline/home?cursor={cursor}&limit=20

```json
// Response 200
{
  "tweets": [
    {
      "id": "1760123456789",
      "text": "...",
      "user": { "id": "42", "username": "harsh" },
      "created_at": "2024-02-20T10:30:00Z",
      "metrics": { "likes": 142, "retweets": 12, "replies": 5 },
      "is_retweet": false,
      "media": [{ "url": "https://cdn.x.com/media/abc.jpg", "type": "image" }]
    }
  ],
  "next_cursor": "1760123456700",
  "has_more": true
}
```

#### POST /api/v1/tweets/{tweet_id}/like

```json
// Response 200
{ "liked": true, "like_count": 143 }
```

#### POST /api/v1/users/{user_id}/follow

```json
// Response 200
{ "following": true, "follower_count": 1501 }
```

#### GET /api/v1/search?q=system+design&type=tweets&filter=verified

```json
// Response 200
{
  "results": [...],
  "next_cursor": "...",
  "total_estimate": 45000
}
```

#### GET /api/v1/trends?region=US

```json
{
  "trends": [
    { "name": "#SystemDesign", "tweet_count": 125000, "velocity": 2.3 },
    { "name": "OpenAI", "tweet_count": 89000, "velocity": 1.8 }
  ]
}
```

### gRPC — Internal Services

```protobuf
service FanoutService {
  rpc FanoutTweet(FanoutRequest) returns (FanoutResponse);
  rpc GetFollowerList(FollowerRequest) returns (stream FollowerBatch);
}

service TimelineService {
  rpc GetTimeline(TimelineRequest) returns (TimelineResponse);
  rpc MergeTimeline(MergeRequest) returns (TimelineResponse);  // for celebrity fanout-on-read
}

service GraphService {
  rpc GetFollowers(UserRequest) returns (stream UserBatch);
  rpc GetFollowing(UserRequest) returns (stream UserBatch);
  rpc IsFollowing(FollowCheckRequest) returns (FollowCheckResponse);
}
```

### WebSocket — Real-time

```
wss://stream.x.com/v1/timeline

// Server → Client messages:
{ "type": "new_tweet", "tweet": {...} }
{ "type": "notification", "data": { "type": "like", "actor": "harsh", "tweet_id": "..." } }
{ "type": "tweet_update", "tweet_id": "...", "metrics": { "likes": 144 } }
```

---

## 7. Fanout Strategy — Deep Dive

### The Celebrity Problem

A user with 100M followers posting a tweet would generate 100M write operations. At even 10μs per write, that's 1000 seconds — unacceptable.

### Hybrid Fanout Approach

```
┌──────────────────────────────────────────────────────────┐
│                    FANOUT DECISION                         │
│                                                          │
│   if (author.follower_count < 10,000):                   │
│       → FANOUT-ON-WRITE (push to all follower timelines) │
│                                                          │
│   if (author.follower_count >= 10,000):                  │
│       → FANOUT-ON-READ (pull at read time, merge)        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Fanout-on-Write (Push Model)

```python
# Executed asynchronously via Kafka consumer
async def fanout_on_write(tweet_id: int, author_id: int):
    """Push tweet to all follower timelines in Redis."""
    followers = await graph_service.get_followers(author_id)
    
    pipeline = redis.pipeline()
    for batch in chunked(followers, 1000):
        for follower_id in batch:
            # Add to sorted set: score=timestamp, member=tweet_id
            pipeline.zadd(
                f"timeline:{follower_id}",
                {str(tweet_id): tweet.created_at.timestamp()}
            )
            # Trim to 800 entries max
            pipeline.zremrangebyrank(f"timeline:{follower_id}", 0, -801)
        await pipeline.execute()
        pipeline = redis.pipeline()
    
    metrics.counter("fanout.writes.total").inc(len(followers))
```

### Fanout-on-Read (Pull Model for Celebrities)

```python
async def get_home_timeline(user_id: int, cursor: int, limit: int = 20):
    """Merge push timeline with celebrity tweets at read time."""
    
    # 1. Get pre-computed timeline from Redis (push results)
    push_tweet_ids = await redis.zrevrangebyscore(
        f"timeline:{user_id}",
        max=cursor or "+inf",
        min="-inf",
        start=0,
        num=limit
    )
    
    # 2. Get list of celebrities this user follows
    celebrity_followees = await graph_service.get_celebrity_followees(user_id)
    
    # 3. Fetch recent tweets from each celebrity (from cache/Cassandra)
    pull_tweets = []
    for celeb_id in celebrity_followees:
        recent = await redis.zrevrangebyscore(
            f"user_timeline:{celeb_id}",
            max=cursor or "+inf",
            min="-inf",
            start=0,
            num=5  # Only need a few per celebrity
        )
        pull_tweets.extend(recent)
    
    # 4. Merge, sort by timestamp, apply ranking
    all_tweet_ids = merge_sorted(push_tweet_ids, pull_tweets)
    
    # 5. Hydrate tweet objects
    tweets = await tweet_service.multi_get(all_tweet_ids[:limit])
    
    # 6. Apply ranking model (engagement prediction)
    ranked = await ranking_service.rank(user_id, tweets)
    
    return ranked
```

### Kafka Topic Design for Fanout

```
Topics:
  tweet.created          → Fanout consumers (partitioned by author_id)
  tweet.engagement       → Counter update consumers
  fanout.normal          → Workers for < 10K follower fanout
  fanout.celebrity       → Dedicated workers (higher parallelism)
  
Consumer groups:
  fanout-workers (200 consumers, each handles ~5K fanout ops/sec)
  search-indexer (32 consumers)
  notification-workers (64 consumers)
  analytics-ingester (16 consumers → ClickHouse)
```

---

## 8. Component Optimization

### Kafka Configuration

```yaml
# tweet.created topic
partitions: 256
replication_factor: 3
retention_ms: 604800000  # 7 days
compression: lz4
min.insync.replicas: 2
acks: all  # Durability for tweet events
```

### Redis Timeline Cache

```
Architecture: Redis Cluster (100+ nodes)
Memory per node: 128GB
Total cluster memory: ~12.8TB (supports 500M user timelines + hot data)

Eviction policy: volatile-lru (only evict keys with TTL)
Timeline TTL: 7 days (inactive users get evicted, rebuilt on next access)

Sorted Set operations:
  ZADD: O(log N) — N=800 max entries per timeline
  ZREVRANGE: O(log N + M) — M=20 items returned
  
Pipeline batching: 1000 ops per pipeline for fanout
```

### Flink — Trending Topics

```java
DataStream<TweetEvent> tweets = env.addSource(kafkaConsumer);

tweets
    .flatMap(tweet -> tweet.getHashtags())
    .keyBy(hashtag -> hashtag)
    .window(SlidingEventTimeWindows.of(Time.minutes(15), Time.minutes(1)))
    .aggregate(new VelocityAggregator())  // count + acceleration
    .filter(trend -> trend.velocity > THRESHOLD)
    .addSink(new RedisTrendingSink());
```

### Database Sharding

```
PostgreSQL (Users):
  - Shard key: user_id % 64 (64 shards)
  - Each shard: primary + 2 read replicas
  - Cross-shard follows: resolved via scatter-gather

Cassandra (Tweets):
  - Partition key: tweet_id (uniform distribution via Snowflake IDs)
  - RF=3, consistency: LOCAL_QUORUM for writes, ONE for reads
  - 200+ nodes across 3 data centers

Elasticsearch:
  - 64 shards, 2 replicas
  - Index rotation: daily indices (tweets-2024-02-20)
  - Alias: tweets-current → last 30 days of indices
```

### CDN Strategy

```
CloudFront:
  - Edge locations: 400+ globally
  - Media cached at edge with 24h TTL
  - Timeline API responses: NOT cached (personalized)
  - Static assets (JS/CSS): cached with content-hash URLs
  
Origin Shield: enabled (reduce origin load by 60%)
Lambda@Edge: image resizing on-the-fly for different devices
```

---

## 9. Observability

### Prometheus Metrics

```yaml
# Key SLIs
- twitter_timeline_latency_seconds{quantile="0.99"}  # Target: < 0.2s
- twitter_tweet_post_latency_seconds{quantile="0.99"}  # Target: < 0.5s
- twitter_fanout_lag_seconds  # Time from tweet creation to last follower delivery
- twitter_timeline_cache_hit_ratio  # Target: > 95%
- twitter_kafka_consumer_lag{topic, group}
- twitter_error_rate{service, status_code}

# Capacity signals
- twitter_redis_memory_usage_bytes
- twitter_cassandra_disk_usage_bytes
- twitter_active_websocket_connections
```

### Distributed Tracing (OpenTelemetry)

```
Trace: POST /api/v1/tweets
  └─ API Gateway: auth check (2ms)
  └─ Tweet Service: validate + persist (15ms)
      └─ Cassandra write (8ms)
  └─ Kafka produce: tweet.created (3ms)
  └─ [Async] Fanout Service: push to 200 timelines (450ms)
      └─ Redis pipeline: 200 ZADD ops (12ms)
  └─ [Async] Search Indexer: ES index (80ms)
  └─ [Async] Notification Service: mentions (25ms)
```

### Alerting Rules

```yaml
groups:
  - name: twitter-sla
    rules:
      - alert: TimelineLatencyHigh
        expr: histogram_quantile(0.99, twitter_timeline_latency_seconds) > 0.2
        for: 5m
        labels: { severity: critical }

      - alert: FanoutLagHigh
        expr: twitter_fanout_lag_seconds > 10
        for: 2m
        labels: { severity: warning }

      - alert: CacheHitRateLow
        expr: twitter_timeline_cache_hit_ratio < 0.90
        for: 10m
        labels: { severity: warning }

      - alert: KafkaConsumerLag
        expr: twitter_kafka_consumer_lag > 100000
        for: 5m
        labels: { severity: critical }

      - alert: ErrorRateHigh
        expr: rate(twitter_error_rate{status_code=~"5.."}[5m]) > 0.01
        for: 2m
        labels: { severity: critical }
```

---

## 10. Considerations & Tradeoffs

### Celebrity Problem (Thundering Herd)

| Approach | Pros | Cons |
|----------|------|------|
| Pure push | Low read latency | 100M writes per celebrity tweet |
| Pure pull | No fanout cost | High read latency, N+1 queries |
| **Hybrid (chosen)** | Balanced | Complexity in merge logic |

The 10K follower threshold is tunable. In practice, Twitter uses ~10K-50K based on engagement patterns.

### Hot Partitions

- **Viral tweets**: Engagement counters on a single tweet get millions of writes/sec
  - Solution: Redis sharded counters (`tweet:{id}:likes:{shard}`) with periodic aggregation
- **Celebrity user timelines**: Read-heavy
  - Solution: Dedicated Redis replicas for top 1000 users

### Consistency vs Availability

| Operation | Model | Rationale |
|-----------|-------|-----------|
| Tweet creation | Strong (sync to Cassandra QUORUM) | Cannot lose tweets |
| Timeline delivery | Eventual (async fanout) | Acceptable delay of seconds |
| Like/retweet counts | Eventual (async counter) | Approximate counts are fine |
| Follow graph | Strong (PostgreSQL) | Must be consistent for correct fanout |
| Search index | Eventual (~30s delay) | Acceptable for search freshness |

### Failure Modes & Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Redis cluster down | Timelines unavailable | Fallback to Cassandra user_timeline scan + circuit breaker |
| Kafka lag spike | Delayed tweet delivery | Auto-scale consumers, priority queue for celebrity tweets |
| Cassandra node failure | Reduced write capacity | RF=3 handles single node loss transparently |
| Elasticsearch down | Search unavailable | Graceful degradation, show cached trends instead |

### Rate Limiting

```
Tweet creation: 300/3h per user
Timeline reads: 1500/15m per user
Likes: 1000/day per user
Follows: 400/day per user
Search: 300/15m per user (API), 180/15m (app)
```

### Data Privacy & Compliance

- GDPR: right to deletion propagates through all stores (Cassandra, ES, Redis, S3, ClickHouse)
- Soft-delete with 30-day grace period before hard purge
- Geo-fencing for content restricted by jurisdiction

---

## Summary

The Twitter/X timeline system is fundamentally a **massive fanout problem** solved through:

1. **Hybrid push/pull** — push for normal users, pull for celebrities
2. **Async processing** — Kafka decouples tweet creation from delivery
3. **Tiered caching** — Redis for hot timelines, Cassandra for persistence
4. **Horizontal scaling** — every component shards independently
5. **Eventual consistency** — trade freshness for availability at scale

The system handles **200B reads/day** at **<200ms p99** by keeping pre-computed timelines in Redis and only merging celebrity content at read time for the small percentage of users who follow high-follower accounts.
