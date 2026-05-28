# Design Facebook News Feed

## 1. Functional Requirements

- **News Feed generation**: Personalized feed of posts from friends, pages, groups
- **Post creation**: Text, photos, videos, live video, stories, events, polls
- **Social interactions**: Like (6 reactions), Comment, Share, Save
- **ML-ranked feed**: Machine learning ranked content (not chronological)
- **Ads integration**: Sponsored posts interspersed in feed
- **Content types**: Posts, stories, reels, marketplace, events, groups
- **Privacy controls**: Audience selection (public, friends, custom lists)
- **Aggregation**: "3 friends liked this", "5 new posts in group"
- **Real-time updates**: New post notification while scrolling
- **Infinite scroll**: Paginated feed with pre-fetching
- **Content diversity**: Mix of content types, avoid repetition

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Feed load time | < 300ms p50, < 1s p99 |
| Feed freshness | New posts visible within 2-5 minutes |
| Scale | 3B users, 2B DAU |
| Content volume | 5B+ posts/day (including stories) |
| Feed requests/sec | 10M+ |
| Ranking latency | < 100ms per feed request |
| Read:Write | 1000:1 |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| DAU | 2B |
| Posts/day | 5B (including all content types) |
| Feed loads/day | 200B (100 per user) |
| Feed loads/sec | 2.3M average, 10M peak |
| Avg friends per user | 350 |
| Avg feed candidates | 1500 (posts from friends/pages in last day) |
| Displayed per session | 50-100 posts |
| Storage (posts/day) | 5B × 5KB = 25 TB/day |
| Storage (media/day) | 2B media posts × 5MB = 10 PB/day |

## 4. Data Modeling

### Technology Selection

| Store | Technology | Purpose |
|---|---|---|
| Social graph | TAO (Facebook's graph store) | Edges: friends, likes, follows |
| Posts | TAO + MySQL (sharded) | Post content, metadata |
| Feed cache | Memcached (TAO cache) | Precomputed feeds |
| Media | Haystack/f4 | Photo/video blob storage |
| Ranking features | Feature Store (realtime) | ML features for ranking |
| Search | Unicorn (FB's custom) | Post/people search |
| Analytics | Scuba + Hive | Real-time + batch analytics |
| Event bus | Wormhole (FB's CDC) | Change propagation |
| ML model serving | PyTorch + custom infra | Feed ranking models |

### Schema (Simplified)

```sql
-- Posts
CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    author_id BIGINT,
    content TEXT,
    media_ids BIGINT[],
    privacy_level VARCHAR(20), -- public, friends, friends_except, specific, only_me
    privacy_list_id BIGINT,
    post_type VARCHAR(20), -- status, photo, video, link, event, poll
    place_id BIGINT,
    tagged_users BIGINT[],
    reaction_counts JSONB, -- {like: 50, love: 10, ...}
    comment_count INT,
    share_count INT,
    created_at TIMESTAMP
);

-- Social Graph (TAO model - association lists)
-- Object: user_id → {name, profile_pic, ...}
-- Association: (subject_id, assoc_type, object_id) → {time, data}
-- Types: FRIEND, FOLLOW, LIKE, COMMENT_ON, MEMBER_OF, etc.

-- Feed (precomputed per user - in memory/cache)
-- feed:{user_id} → [post_id_1, post_id_2, ...] (ranked order)
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          FEED GENERATION PIPELINE                            │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Step 1: CANDIDATE GENERATION (Retrieval)                              │  │
│  │ - Fetch posts from friends (last 24-48h): ~1500 candidates           │  │
│  │ - Fetch posts from followed pages/groups: ~500 candidates            │  │
│  │ - Fetch recommended posts (content you might like): ~200            │  │
│  │ - Fetch ads candidates: ~50                                           │  │
│  │ Total candidates: ~2000-2500 per feed refresh                        │  │
│  └───────────────────────────────────────────┬───────────────────────────┘  │
│                                               ▼                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Step 2: RANKING (ML Scoring)                                          │  │
│  │ - For each candidate, compute relevance score                        │  │
│  │ - Features: affinity (how close are you to author),                  │  │
│  │   content type preference, recency, engagement velocity,             │  │
│  │   predicted engagement (P(like), P(comment), P(share))               │  │
│  │ - Multi-objective optimization: engagement + time_spent + value      │  │
│  │ - Model: deep neural network (hundreds of features)                  │  │
│  └───────────────────────────────────────────┬───────────────────────────┘  │
│                                               ▼                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Step 3: POST-RANKING FILTERS                                          │  │
│  │ - Diversity: don't show 5 posts from same person in a row            │  │
│  │ - Deduplication: seen this post already? skip                        │  │
│  │ - Content type mixing: vary photo/video/text/link                    │  │
│  │ - Integrity: filter policy-violating content                         │  │
│  │ - Ad insertion: insert ads at positions 4, 8, 13, etc.               │  │
│  │ - Anti-patterns: reduce clickbait, engagement bait                   │  │
│  └───────────────────────────────────────────┬───────────────────────────┘  │
│                                               ▼                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Step 4: SERVE                                                         │  │
│  │ - Return top 50 ranked posts                                          │  │
│  │ - Pre-fetch next page in background                                   │  │
│  │ - Cache result for quick re-load                                      │  │
│  │ - Track what was shown (for engagement feedback)                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

## 6. Ranking Model Deep Dive

```
Features (hundreds, key ones):
  User-Post affinity:
    - How often user interacts with author (messages, likes, comments)
    - Time since last interaction with author
    - Relationship closeness (family, close friend, acquaintance)
    
  Content signals:
    - Post type (photo > video > text historically for user)
    - Has been liked/commented by mutual friends
    - Engagement velocity (likes/minute since posting)
    - Content length, media count
    
  Contextual:
    - Time of day (user engagement patterns)
    - Device type (video less on cellular, more on wifi)
    - User's recent feed interactions
    
  Negative signals:
    - User hid posts from this author before
    - Post reported by others
    - Clickbait/engagement-bait classifier score
    
Prediction targets (multi-task):
    P(like), P(comment), P(share), P(click), P(hide), P(time_spent > 10s)
    
Final score = weighted combination:
    0.3 × P(meaningful_interaction) + 0.25 × P(time_well_spent) + 
    0.2 × P(engagement) + 0.15 × recency_boost + 0.1 × diversity_bonus
```

## 7. APIs

```
GET /api/v1/feed?cursor=xxx&count=20
Response: {
  "posts": [{id, author, content, media, reactions, comments_preview, score, sponsored}],
  "cursor": "next_page_cursor",
  "has_more": true,
  "feed_session_id": "fs_123" // for engagement tracking
}

POST /api/v1/posts
Request: {"content": "Hello!", "media_ids": ["m_1"], "privacy": "friends", "tagged": ["u_1"]}
Response: {"post": {id, content, created_at, privacy, ...}}

POST /api/v1/posts/{post_id}/reactions
Request: {"type": "love"}
Response: {"ok": true, "counts": {"like": 50, "love": 11}}
```

## 8. Optimization

### Feed Pre-computation vs On-demand
```
Facebook uses ON-DEMAND (Fan-out on Read):
- Too many users (2B DAU) to pre-compute all feeds
- Average 350 friends × multiple posts = large write amplification
- Instead: compute feed at request time with aggressive caching
- Cache: last computed feed per user (TTL 5 min)
- Incremental: append new posts since last computation

Why NOT fan-out on write (like Twitter):
- 2B DAU × 5 posts/user/day × 350 friends = 3.5 TRILLION writes/day
- Impossible write volume
- Facebook's ML ranking means feed changes based on user's recent behavior
- Can't pre-rank (ranking is personalized + contextual)
```

### TAO (The Associations and Objects) Cache
```
- Custom distributed graph cache
- Objects: users, posts, pages, groups (key-value)
- Associations: edges (friend, like, member, tagged)
- Write-through cache with MySQL as source of truth
- Request routing by shard (consistent hashing)
- Cache billions of objects + trillions of edges
- Replicated across data centers (async replication)
- Hit rate: >99% for hot data
```

## 9. Observability

```yaml
Metrics:
  feed_generation_latency_seconds{step="retrieval|ranking|filtering", quantile}
  feed_requests_total{status}
  feed_ranking_model_latency_ms{model_version}
  feed_content_diversity_score{session}
  feed_engagement_rate{content_type, position}
  tao_cache_hit_rate{object_type}
  
Alerts:
  Critical: feed_latency_p99 > 2s, ranking_model_timeout > 5%
  Warning: engagement_rate drop > 10% week-over-week, diversity < threshold
```

## 10. Considerations

### Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| On-demand ranking (pull) | Fresh, personalized, no write amplification | Higher read latency |
| ML-ranked (not chronological) | Higher engagement, better UX | Complexity, filter bubble risk |
| TAO (custom graph cache) | Extreme performance for social graph | Custom infra maintenance |
| Multi-objective ranking | Balanced feed (not just engagement) | Harder to optimize |

### Integrity & Safety
- Content classifiers run on all posts before feed eligibility
- Misinformation: reduce distribution of flagged content
- Harmful content: remove before it appears in any feed
- Engagement bait: demote "like if you agree" style posts
- Diversity: ensure different viewpoints, not just echo chamber
