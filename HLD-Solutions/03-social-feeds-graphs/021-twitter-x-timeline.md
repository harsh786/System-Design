# Design Twitter/X - Timeline & Social Platform

## 1. Functional Requirements

- **Tweet creation**: Post text (280 chars), images, videos, polls, links
- **Home timeline**: Personalized feed of tweets from followed users + recommendations
- **Follow/Unfollow**: Asymmetric social graph (follow without approval)
- **Retweet/Quote tweet**: Reshare with or without commentary
- **Like/Bookmark**: Engage with tweets, save for later
- **Reply/Thread**: Conversations with threading
- **Search**: Real-time search across tweets, users, hashtags
- **Trending**: Real-time trending topics by region
- **Notifications**: Likes, retweets, mentions, follows, DMs
- **Lists**: Curated user lists with separate timelines
- **Spaces**: Live audio rooms
- **Direct Messages**: Private messaging
- **Verified/Premium**: Blue checkmark, premium features
- **Algorithmic ranking**: ML-ranked "For You" + chronological "Following"

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Timeline load | < 200ms p50, < 500ms p99 |
| Tweet publish to follower delivery | < 5s for normal, < 30s for celebrities |
| Search freshness | < 10s for tweets to be searchable |
| Scale | 500M+ MAU, 400M tweets/day |
| Celebrity problem | Handle users with 100M+ followers |
| Read:Write ratio | 100:1 (heavily read-heavy) |
| Feed freshness | New tweets appear within seconds |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| MAU | 500M |
| DAU | 250M |
| Tweets/day | 400M |
| Tweets/sec (avg) | 4,600 |
| Tweets/sec (peak) | 50,000 |
| Timeline reads/day | 25B (100 per DAU) |
| Timeline reads/sec | 290,000 |
| Timeline reads/sec (peak) | 1.5M |
| Avg followers per user | 200 |
| Celebrity followers (top 0.01%) | 10M-100M |
| Avg tweet size | 1KB (text + metadata) |
| Media tweets | 30% with images/video |
| Storage/day (tweets) | 400M × 1KB = 400 GB |
| Storage/day (media) | 120M × 2MB = 240 TB |
| Fan-out writes/day | 400M × 200 avg = 80B |

## 4. Data Modeling

### Database Selection

| Store | Technology | Reason |
|---|---|---|
| Tweet store | Manhattan (Twitter's KV) / Cassandra | High write, append-only |
| Timeline cache | Redis Cluster | Hot feeds, low-latency reads |
| Social graph | FlockDB (Twitter) / Neo4j + PostgreSQL | Graph queries, follower lists |
| User profiles | PostgreSQL (sharded) | Relational, ACID |
| Search | Elasticsearch (Earlybird at Twitter) | Real-time inverted index |
| Media | S3/GCS + CDN | Object storage |
| Analytics | ClickHouse / Druid | Time-series engagement metrics |
| Trending | Redis + Flink | Real-time counters, decay |
| Event bus | Kafka | Tweet events, notifications |
| ML features | Feature Store (Redis + Hive) | Ranking signals |

### Schema

```sql
-- Tweets (Cassandra/Manhattan)
CREATE TABLE tweets (
    tweet_id BIGINT PRIMARY KEY, -- Snowflake ID
    user_id BIGINT,
    content TEXT,
    media_urls TEXT[], -- S3/CDN URLs
    tweet_type VARCHAR, -- original, retweet, quote, reply
    in_reply_to_tweet_id BIGINT,
    in_reply_to_user_id BIGINT,
    quoted_tweet_id BIGINT,
    retweeted_tweet_id BIGINT,
    hashtags TEXT[],
    mentions BIGINT[],
    urls TEXT[],
    poll_id BIGINT,
    like_count INT DEFAULT 0,
    retweet_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    language VARCHAR(5),
    geo JSONB,
    sensitive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
);

-- User Timeline (Redis - precomputed feed per user)
-- Key: timeline:{user_id}
-- Value: Sorted Set of tweet_ids scored by timestamp
-- Size: Last 800 tweets per user

-- Social Graph (Adjacency list in specialized store)
CREATE TABLE follows (
    follower_id BIGINT,
    following_id BIGINT,
    created_at TIMESTAMP,
    PRIMARY KEY (follower_id, following_id)
);
CREATE INDEX idx_follows_following ON follows(following_id, follower_id);
-- followers:{user_id} → list of follower_ids
-- following:{user_id} → list of following_ids

-- Engagement
CREATE TABLE likes (
    user_id BIGINT,
    tweet_id BIGINT,
    created_at TIMESTAMP,
    PRIMARY KEY (user_id, tweet_id)
);

CREATE TABLE retweets (
    user_id BIGINT,
    tweet_id BIGINT,
    created_at TIMESTAMP,
    PRIMARY KEY (user_id, tweet_id)
);
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            CLIENTS                                           │
│   iOS/Android App  │  Web App (React)  │  API Clients  │  TweetDeck        │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────────┐
│                         EDGE LAYER                                           │
│  DNS → CDN → WAF → Load Balancer → API Gateway (rate limit, auth, route)   │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────────────┐
│                        WRITE PATH                                            │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────────────┐    │
│  │ Tweet Service│ →  │  Kafka       │ →  │  Fan-out Service            │    │
│  │ - Validate   │    │ (tweet.new)  │    │  - Small accounts: push    │    │
│  │ - Store tweet│    │              │    │    (write to all follower   │    │
│  │ - Extract    │    │              │    │     timelines in Redis)     │    │
│  │   entities   │    │              │    │  - Celebrities: pull       │    │
│  │ - Media ref  │    │              │    │    (merge at read time)     │    │
│  └──────────────┘    └──────────────┘    └────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         READ PATH                                             │
│                                                                               │
│  ┌──────────────────┐    ┌────────────────────┐    ┌──────────────────────┐ │
│  │ Timeline Service │ →  │  Timeline Cache    │ →  │  Ranking Service     │ │
│  │ - Load user feed │    │  (Redis)           │    │  - ML scoring        │ │
│  │ - Merge celebrity│    │  - Pre-built feeds  │    │  - Engagement pred   │ │
│  │   tweets at read │    │  - Last 800 tweets │    │  - Diversity/fresh   │ │
│  │ - Apply ranking  │    │                    │    │  - "For You" algo    │ │
│  └──────────────────┘    └────────────────────┘    └──────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 6. Deep Dive: Fan-out Strategy

### Hybrid Fan-out (Push + Pull)

```
┌─────────────────────────────────────────────────────────────────┐
│             FAN-OUT STRATEGY                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  PUSH (Fan-out on Write) - for normal users (<10K followers):   │
│  - When user tweets, write tweet_id to EACH follower's timeline │
│  - Advantage: Fast reads (timeline pre-built)                    │
│  - Cost: 200 followers × 1 write = 200 writes per tweet         │
│  - Total: 400M tweets × 200 = 80B fan-out writes/day            │
│                                                                   │
│  PULL (Fan-out on Read) - for celebrities (>10K followers):     │
│  - Don't pre-write to follower timelines                        │
│  - At read time: merge celebrity tweets with pre-built timeline │
│  - Advantage: Avoids 100M writes per celebrity tweet            │
│  - Cost: Higher read latency (need to merge)                    │
│                                                                   │
│  HYBRID APPROACH:                                                │
│  1. User requests timeline                                       │
│  2. Load pre-built timeline from Redis (pushed tweets)           │
│  3. Identify celebrities user follows                            │
│  4. Fetch recent tweets from each celebrity (cached separately)  │
│  5. Merge + rank + return top N                                  │
│                                                                   │
│  Celebrity threshold: > 10,000 followers = pull                  │
│  Most users: pure push (fast, simple)                            │
│  Reading celebrity timeline: separate cache per celebrity        │
└─────────────────────────────────────────────────────────────────┘
```

### Timeline Assembly (Read Path)

```
1. Request: GET /api/v1/timeline/home?cursor=xxx&count=20

2. Assembly:
   a. Read user's pre-built timeline from Redis (IDs only): O(1)
   b. Get list of celebrities user follows: cached in Redis
   c. For each celebrity: get their recent tweet IDs: O(k)
   d. Merge all tweet IDs, sort by relevance/time
   e. Hydrate top N tweet IDs → full tweet objects (multi-get)
   f. Hydrate user objects for authors
   g. Attach engagement counts (likes, retweets, replies)
   h. Apply ranking model (ML inference)
   i. Return ranked results with pagination cursor

3. Latency budget:
   - Redis read (timeline IDs): 2ms
   - Celebrity merge: 5ms
   - Tweet hydration (batch): 10ms
   - Ranking inference: 20ms
   - Total: ~40ms p50
```

## 7. APIs

```
POST /api/v2/tweets
Request: {"text": "Hello world!", "media_ids": ["m_1"], "reply_settings": "everyone"}
Response: {"data": {"id": "12345", "text": "Hello world!", "created_at": "..."}}

GET /api/v2/timeline/home?max_results=20&pagination_token=xxx
Response: {"data": [tweet objects], "meta": {"next_token": "xxx", "result_count": 20}}

GET /api/v2/timeline/reverse_chronological?max_results=20
Response: {"data": [tweets in time order]}

POST /api/v2/users/{user_id}/following
Request: {"target_user_id": "67890"}
Response: {"data": {"following": true}}

GET /api/v2/tweets/search/recent?query=keyword&max_results=100
Response: {"data": [matching tweets], "meta": {...}}

PUT /api/v2/tweets/{tweet_id}/like
Response: {"data": {"liked": true}}

GET /api/v2/trends/place?id=1  (global)
Response: {"data": [{"name": "#WorldCup", "tweet_volume": 5000000, "url": "..."}]}
```

## 8. Component Optimization

### Trending Topics (Flink + Redis)
```
Pipeline:
  Kafka (tweet.new) → Flink streaming job →
    - Extract hashtags, keywords
    - Count in sliding window (5 min, 1 hour)
    - Apply decay function (recent = more weight)
    - Compare to baseline (detect spikes, not just volume)
    - Output top 10 per region every 30 seconds → Redis

Algorithm:
  score = (current_volume - baseline_volume) / baseline_volume × time_decay
  Baseline = rolling 7-day average at same hour/day
  Spike = score > 3.0 standard deviations
```

### Search (Real-time + Historical)
```
Real-time search (Earlybird):
  - In-memory inverted index for last 7 days
  - Tweets indexed within 10 seconds of creation
  - Partitioned by time (recent partitions hot)
  - Tokenize: text, hashtags, mentions, URLs

Historical search:
  - Elasticsearch cluster for older tweets
  - Relevance: engagement signals + recency + user authority
  
Query: "machine learning" → 
  Scatter to N search partitions →
  Each returns top K results →
  Merge + re-rank globally →
  Return top results
```

## 9. Observability

```yaml
Metrics:
  twitter_tweets_published_total
  twitter_timeline_load_latency_seconds{type="home|following", quantile}
  twitter_fanout_delay_seconds{quantile}
  twitter_timeline_cache_hit_rate
  twitter_search_latency_seconds{quantile}
  twitter_trending_refresh_interval_seconds
  twitter_engagement_total{type="like|rt|reply"}
  
Alerts:
  Critical: timeline latency p99 > 2s, fanout delay > 60s, tweet loss detected
  Warning: cache hit rate < 90%, search freshness > 30s
```

## 10. Considerations

### Key Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| Hybrid fan-out | Handles celebrities efficiently | Complex read path merge |
| Pre-computed timeline (Redis) | Ultra-fast reads | Memory cost (800 IDs × 250M users) |
| Eventual consistency for counts | Scalability | Counts may be slightly stale |
| Pull for celebrities | Avoids 100M writes per tweet | Higher read latency for their followers |
| Snowflake IDs | Time-ordered without DB sequence | Requires coordination service |

### Celebrity Problem Solution
- Top 10K accounts by followers use PULL model
- Their tweets stored in dedicated cache (per-celebrity)
- Timeline merge adds ~10ms latency but saves billions of writes
- Mixed approach: push to "active" followers only (logged in last 7 days)
