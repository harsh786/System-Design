# Design Reddit - Community Discussion & Voting Platform

## 1. Functional Requirements

- **Subreddits**: Community creation with rules, moderators, customization
- **Posts**: Text, link, image, video, poll posts within subreddits
- **Voting**: Upvote/downvote on posts and comments (determines ranking)
- **Comments**: Threaded comment trees with infinite nesting
- **Ranking algorithms**: Hot, Top (time-based), New, Controversial, Best
- **Home feed**: Aggregated feed from subscribed subreddits
- **r/all & r/popular**: Global trending content
- **Awards/Medals**: Premium awards on posts/comments
- **Moderation**: AutoModerator, mod queue, ban, remove, flair
- **Search**: Subreddit, post, comment search
- **User profiles**: Karma, post history, about section
- **Cross-posting**: Share posts to multiple subreddits
- **Live threads**: Real-time discussion for events
- **Wiki**: Per-subreddit wiki pages

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.9% |
| Page load | < 500ms for hot page |
| Vote processing | < 100ms acknowledgment |
| Comment tree load | < 300ms for 1000+ comments |
| Scale | 1.7B MAU, 100K active subreddits |
| Voting consistency | Accurate within 1 minute |
| Hot page freshness | Updated every 30-60 seconds |
| Search freshness | Posts searchable within 5 minutes |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| DAU | 100M |
| Posts/day | 10M |
| Comments/day | 100M |
| Votes/day | 2B (posts + comments) |
| Votes/sec (peak) | 50,000 |
| Page views/day | 10B |
| Page views/sec (peak) | 200,000 |
| Active subreddits | 100K |
| Avg comments per post | 50 (viral posts: 10K+) |
| Storage (posts/day) | 10M × 5KB = 50 GB |
| Storage (comments/day) | 100M × 1KB = 100 GB |

## 4. Data Modeling

```sql
-- Subreddits
CREATE TABLE subreddits (
    id BIGINT PRIMARY KEY,
    name VARCHAR(21) UNIQUE, -- r/name, max 21 chars
    title VARCHAR(100),
    description TEXT,
    sidebar TEXT,
    subscriber_count INT DEFAULT 0,
    active_users INT DEFAULT 0, -- online now
    type VARCHAR(10), -- public, restricted, private
    over_18 BOOLEAN DEFAULT FALSE,
    created_by BIGINT,
    created_at TIMESTAMP
);

-- Posts
CREATE TABLE posts (
    id BIGINT PRIMARY KEY, -- base36 encoded for URL
    subreddit_id BIGINT,
    author_id BIGINT,
    title VARCHAR(300),
    body TEXT, -- for self posts
    url TEXT, -- for link posts
    post_type VARCHAR(10), -- text, link, image, video, poll
    score INT DEFAULT 0, -- upvotes - downvotes
    upvotes INT DEFAULT 0,
    downvotes INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    hot_score FLOAT, -- pre-computed hot ranking
    is_pinned BOOLEAN DEFAULT FALSE,
    is_locked BOOLEAN DEFAULT FALSE,
    is_removed BOOLEAN DEFAULT FALSE,
    flair_text VARCHAR(50),
    created_at TIMESTAMP
);
CREATE INDEX idx_posts_subreddit_hot ON posts(subreddit_id, hot_score DESC);
CREATE INDEX idx_posts_subreddit_new ON posts(subreddit_id, created_at DESC);
CREATE INDEX idx_posts_subreddit_top ON posts(subreddit_id, score DESC);

-- Comments (tree structure)
CREATE TABLE comments (
    id BIGINT PRIMARY KEY,
    post_id BIGINT,
    parent_id BIGINT, -- NULL for top-level
    author_id BIGINT,
    body TEXT,
    score INT DEFAULT 0,
    upvotes INT DEFAULT 0,
    downvotes INT DEFAULT 0,
    depth INT DEFAULT 0,
    path TEXT, -- materialized path: "root.parent.this" for tree queries
    is_collapsed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
);
CREATE INDEX idx_comments_post_path ON comments(post_id, path);
CREATE INDEX idx_comments_post_score ON comments(post_id, score DESC);

-- Votes
CREATE TABLE votes (
    user_id BIGINT,
    target_id BIGINT, -- post_id or comment_id
    target_type VARCHAR(10), -- post, comment
    direction SMALLINT, -- 1 (up), -1 (down), 0 (unvote)
    created_at TIMESTAMP,
    PRIMARY KEY (user_id, target_id)
);
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RANKING SYSTEM                                    │
│                                                                          │
│  HOT Algorithm (Reddit's classic):                                      │
│  hot_score = log10(max(|score|, 1)) + sign(score) × t / 45000          │
│  where t = (post_time - epoch) in seconds                               │
│                                                                          │
│  Properties:                                                             │
│  - Logarithmic: 10 votes ≈ 100 votes (diminishing returns)             │
│  - Time decay: newer posts get advantage                                 │
│  - A post with 10 votes NOW beats post with 1000 votes yesterday        │
│                                                                          │
│  BEST Algorithm (Wilson Score for comments):                            │
│  lower_bound = (p + z²/2n - z×√(p(1-p)/n + z²/4n²)) / (1 + z²/n)     │
│  where p = upvotes/total_votes, z = 1.96 (95% confidence)              │
│                                                                          │
│  TOP: Simply sort by score (optionally within time window)              │
│  NEW: Sort by created_at DESC                                            │
│  CONTROVERSIAL: high total votes but close to 50/50 split              │
└────────────────────────────────────────────────────────────────────────┘

Architecture:
  Vote → Kafka → Score Calculator → Update hot_score in DB + Redis Cache
  Subreddit page request → Redis (hot page cached) → fallback DB query
  Comment tree → Load full tree for post → sort by algorithm → serve
```

## 6. Comment Tree Handling

```
Materialized Path Approach:
  Comment tree stored with path column:
  - Root comment: path = "001"
  - Reply to root: path = "001.002"
  - Reply to reply: path = "001.002.003"
  
  Loading tree for post:
  SELECT * FROM comments WHERE post_id = X ORDER BY path;
  → Returns pre-ordered tree traversal
  
  Loading subtree:
  SELECT * FROM comments WHERE post_id = X AND path LIKE '001.002%';

For deeply nested threads (Reddit's "continue this thread"):
  - Load first 3 levels fully
  - For deeper: "Continue this thread →" link (lazy load)
  
Performance at scale (posts with 10K+ comments):
  - Cache top 200 comments (sorted by best) in Redis
  - Load more on demand
  - Collapse low-score comment trees by default
```

## 7. APIs

```
GET /api/v1/r/{subreddit}/hot?after=t3_abc&limit=25
Response: {"posts": [...], "after": "t3_xyz"}

GET /api/v1/r/{subreddit}/comments/{post_id}?sort=best&limit=200
Response: {"post": {...}, "comments": [tree structure]}

POST /api/v1/vote
Request: {"target": "t3_abc", "direction": 1}
Response: {"ok": true, "new_score": 1543}

POST /api/v1/r/{subreddit}/submit
Request: {"title": "...", "body": "...", "type": "text", "flair": "Discussion"}
Response: {"post": {"id": "t3_new", "url": "/r/subreddit/comments/new/..."}}

POST /api/v1/comment
Request: {"parent": "t3_abc", "body": "Great post!"}
Response: {"comment": {"id": "t1_xyz", ...}}
```

## 8. Optimization

```
Caching:
- Hot page per subreddit: Redis sorted set, recomputed every 30s
- Top 200 comments per viral post: Redis hash
- Vote counts: Redis counter, flush to DB every 5 minutes
- User karma: computed async, cached in Redis

Vote Processing:
- Immediate: Redis INCR for real-time score display
- Async: Kafka event → update hot_score → rerank page
- Anti-gaming: shadow-ban suspected bot votes
- Rate limit: max 100 votes/minute per user

Home Feed:
- User subscribes to 50 subreddits on average
- Feed = merge top posts from each subscribed subreddit
- Weighted by subreddit size and user engagement history
- Cache home feed per user (TTL 5 min)
```

## 9. Observability & Considerations

```yaml
Metrics: vote_processing_latency, hot_page_cache_hit_rate, comment_tree_load_time
Alerts: vote_lag > 60s, cache_miss > 20%, page_load > 2s
```

### Key Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| Pre-computed hot scores | Fast page loads | Async update (30s staleness) |
| Materialized path for comments | Efficient tree loading | Path string storage overhead |
| Vote fuzzing (Reddit feature) | Anti-bot/gaming | Users see approximate scores |
| Cached vote counts | Fast reads at scale | Eventually consistent (acceptable) |
