# Facebook News Feed - System Design

## 1. Functional Requirements

### Core Features
- **Post Creation**: Users create posts with text, photos (up to 50), videos (up to 240min), links, location, tags, and audience controls
- **News Feed Generation**: Personalized, ML-ranked feed combining posts from friends, pages, groups, and ads
- **Reactions**: Like, Love, Haha, Wow, Sad, Angry on posts and comments
- **Comments**: Threaded comments with replies, reactions, media attachments
- **Shares**: Re-share posts with optional commentary; share to feed, groups, messages
- **Stories**: Ephemeral 24-hour photo/video content with viewers list
- **Groups**: Public/private/secret groups with moderation, post approval queues
- **Pages**: Business pages with follower feeds, insights, scheduled posts
- **Privacy Controls**: Per-post audience (public, friends, custom lists, only me), block lists, restricted profiles

### Extended Features
- Live video streaming with real-time comments
- Memories/On This Day
- Marketplace integration in feed
- Event invitations and RSVPs
- Fundraisers and donations

---

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% (< 52 min downtime/year) |
| Feed Load Latency | p50 < 50ms, p99 < 200ms |
| Post Publish Latency | < 5s for post visible to close friends |
| Scale | 2B+ monthly active users, 1.5B+ DAU |
| Consistency | Eventual consistency for feed (< 10s propagation) |
| Durability | Zero data loss for posts (replicated 3x minimum) |
| Throughput | 10B+ feed loads/day, 1B+ posts/day |
| Fault Tolerance | Graceful degradation; stale feed over no feed |
| Data Locality | Regional data centers, edge caching |

---

## 3. Capacity Estimation

### Traffic
```
DAU: 2 billion users
Posts/day: 1 billion (500M text, 300M photo, 150M video, 50M links)
Feed loads/day: 10 billion (avg 5 sessions/user/day)
Reactions/day: 15 billion
Comments/day: 5 billion
Shares/day: 2 billion

QPS (feed reads): 10B / 86400 ≈ 115,000 QPS (peak 3x = 350K QPS)
QPS (post writes): 1B / 86400 ≈ 12,000 QPS (peak 3x = 36K QPS)
QPS (reactions): 15B / 86400 ≈ 175,000 QPS
```

### Storage
```
Post metadata: 1B posts/day × 2KB avg = 2TB/day = 730TB/year
Photos: 300M/day × 3MB avg (multiple resolutions) = 900TB/day
Videos: 150M/day × 100MB avg (multiple bitrates) = 15PB/day
Feed cache: 2B users × 500 posts × 200 bytes = 200TB (hot cache)
Social graph: 2B users × 500 avg connections × 16 bytes = 16TB
Total active storage: 100PB+ (with replication 300PB+)
```

### Bandwidth
```
Feed read: 350K QPS × 50KB avg response = 17.5 GB/s = 140 Gbps
Media serve (CDN offloaded): 5M concurrent video streams × 5Mbps = 25 Tbps
Ingress (uploads): 900TB + 15PB = ~16PB/day = 1.5 Tbps avg
```

---

## 4. Data Modeling

### PostgreSQL - Users & Auth (Sharded by user_id)
```sql
CREATE TABLE users (
    user_id         BIGINT PRIMARY KEY,      -- Snowflake ID
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    phone           VARCHAR(20),
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100),
    profile_pic_url VARCHAR(512),
    cover_pic_url   VARCHAR(512),
    bio             TEXT,
    location        VARCHAR(100),
    privacy_level   SMALLINT DEFAULT 1,       -- 0=public, 1=friends, 2=private
    status          SMALLINT DEFAULT 1,       -- active/suspended/deleted
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL
);

CREATE TABLE friendships (
    user_id_1       BIGINT NOT NULL,
    user_id_2       BIGINT NOT NULL,
    status          SMALLINT NOT NULL,        -- 0=pending, 1=accepted, 2=blocked
    affinity_score  FLOAT DEFAULT 0.0,        -- interaction-based weight
    created_at      TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id_1, user_id_2)
);
CREATE INDEX idx_friendships_user2 ON friendships(user_id_2, status);

CREATE TABLE privacy_settings (
    user_id             BIGINT PRIMARY KEY REFERENCES users(user_id),
    default_post_audience SMALLINT DEFAULT 1,
    who_can_send_request  SMALLINT DEFAULT 0,
    who_can_see_friends   SMALLINT DEFAULT 1,
    timeline_review       BOOLEAN DEFAULT FALSE,
    tag_review            BOOLEAN DEFAULT FALSE
);
```

### Cassandra - Posts (Partitioned by user_id, clustered by created_at DESC)
```cql
CREATE TABLE posts (
    user_id         BIGINT,
    post_id         BIGINT,                 -- Snowflake ID (embeds timestamp)
    post_type       TINYINT,                -- text=0, photo=1, video=2, link=3, story=4
    content_text    TEXT,
    media_urls      LIST<TEXT>,
    media_metadata  TEXT,                   -- JSON: dimensions, duration, thumbnails
    link_preview    TEXT,                   -- JSON: title, description, image, domain
    audience        TINYINT,                -- public=0, friends=1, custom=2, only_me=3
    custom_audience TEXT,                   -- JSON: include/exclude lists
    location        TEXT,                   -- JSON: lat, lng, name
    tagged_users    SET<BIGINT>,
    is_shared       BOOLEAN,
    original_post_id BIGINT,
    reaction_counts MAP<TEXT, BIGINT>,      -- {like: 100, love: 50, ...}
    comment_count   BIGINT,
    share_count     BIGINT,
    is_deleted      BOOLEAN,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    PRIMARY KEY ((user_id), created_at, post_id)
) WITH CLUSTERING ORDER BY (created_at DESC, post_id DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_size': 1, 'compaction_window_unit': 'DAYS'}
  AND default_time_to_live = 0;

CREATE TABLE posts_by_id (
    post_id         BIGINT PRIMARY KEY,
    user_id         BIGINT,
    post_type       TINYINT,
    content_text    TEXT,
    media_urls      LIST<TEXT>,
    audience        TINYINT,
    created_at      TIMESTAMP
);
```

### Cassandra - Feed Store (Pre-computed feeds)
```cql
CREATE TABLE user_feed (
    user_id         BIGINT,
    bucket          INT,                    -- time bucket (daily) for partition size control
    post_id         BIGINT,
    author_id       BIGINT,
    post_type       TINYINT,
    ranking_score   DOUBLE,
    created_at      TIMESTAMP,
    PRIMARY KEY ((user_id, bucket), ranking_score, post_id)
) WITH CLUSTERING ORDER BY (ranking_score DESC, post_id DESC)
  AND default_time_to_live = 604800;       -- 7 day TTL
```

### Redis - Social Graph Cache & Counters
```
# Friend list (sorted set by affinity score)
ZSET  user:{uid}:friends        -> {friend_id: affinity_score}

# Followers for pages/public profiles
SET   user:{uid}:followers      -> {follower_ids}

# Post reaction counts (hash for atomic increments)
HASH  post:{pid}:reactions      -> {like: N, love: N, ...}

# User's reaction on a post (for dedup/display)
SET   post:{pid}:reactors:{type} -> {user_ids}   # only recent, spill to DB

# Online friends (for presence)
SET   user:{uid}:online_friends -> {friend_ids}

# Feed cursor cache
STRING feed:{uid}:cursor        -> serialized_cursor (TTL 5min)

# Rate limiting
STRING ratelimit:{uid}:{action} -> count (TTL window)
```

### TAO - Graph Cache (Facebook's distributed graph store)
```
TAO Models (Object + Association abstraction):

Objects:
  User(id, name, profile_pic, ...)
  Post(id, text, media, timestamp, ...)
  Comment(id, text, timestamp, ...)
  Page(id, name, category, ...)
  Group(id, name, privacy, ...)

Associations (edges with type):
  FRIEND(user_id, user_id, timestamp, affinity)
  AUTHORED(user_id, post_id, timestamp)
  LIKED(user_id, post_id, timestamp, reaction_type)
  COMMENTED(user_id, post_id, comment_id, timestamp)
  MEMBER_OF(user_id, group_id, role, timestamp)
  FOLLOWS(user_id, page_id, timestamp)
  TAGGED_IN(user_id, post_id, timestamp)

Association queries:
  assoc_get(user_123, FRIEND) -> [(user_456, 0.9), (user_789, 0.7), ...]
  assoc_count(post_123, LIKED) -> 5000
  assoc_range(user_123, AUTHORED, t1, t2) -> [post_ids]
```

### S3 / Blob Storage - Media
```
Bucket structure:
  s3://fb-media-{region}/photos/{year}/{month}/{day}/{user_id}/{photo_id}_{resolution}.jpg
  s3://fb-media-{region}/videos/{year}/{month}/{day}/{user_id}/{video_id}/{bitrate}/segment_{n}.m4s
  s3://fb-media-{region}/stories/{user_id}/{story_id}_{resolution}.{ext}

Metadata in DynamoDB:
  media_id -> {user_id, type, s3_key, dimensions, duration, upload_status, cdn_url, created_at}
```

---

## 5. High-Level Design

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENTS                                               │
│                    (iOS / Android / Web / Lite)                                          │
└─────────────────────────────────┬───────────────────────────────────────────────────────┘
                                  │ HTTPS/HTTP2/QUIC
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              CDN (Akamai / Meta CDN)                                     │
│         Static assets, cached feed fragments, photos, video segments                     │
└─────────────────────────────────┬───────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           EDGE / POP (Points of Presence)                                │
│              TLS termination, request routing, DDoS protection                           │
└─────────────────────────────────┬───────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY / LOAD BALANCER                                    │
│         Rate limiting, auth, routing, request coalescing, GraphQL endpoint               │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────────────┘
       │          │          │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼          ▼          ▼
┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│  Post    ││  Feed    ││  Social  ││  Media   ││ Notific- ││   Ads    ││  Story   │
│ Service  ││ Service  ││  Graph   ││ Service  ││  ation   ││ Service  ││ Service  │
│          ││          ││ Service  ││          ││ Service  ││          ││          │
└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘
     │           │           │           │           │           │           │
     ▼           ▼           ▼           ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              EVENT BUS (Kafka)                                            │
│    Topics: post.created, post.reaction, feed.invalidate, user.activity, ad.impression    │
└──────┬──────────┬──────────┬──────────────────────────────────────────────────────────────┘
       │          │          │
       ▼          ▼          ▼
┌──────────┐┌──────────┐┌──────────────────────────────────────────────────────┐
│  Feed    ││ Activity ││              ML RANKING PIPELINE                      │
│ Fanout   ││ Tracker  ││  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐  │
│ Workers  ││          ││  │Candidate│→│ Scoring │→│ Filtering│→│ Ranking │  │
│          ││          ││  │Generator│ │  Model  │ │  Rules   │ │  Final  │  │
└────┬─────┘└────┬─────┘│  └─────────┘ └─────────┘ └──────────┘ └─────────┘  │
     │           │      └──────────────────────────────────────────────────────┘
     ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │PostgreSQL│ │Cassandra │ │  Redis   │ │   TAO    │ │  S3/Blob │ │ RocksDB  │        │
│  │ (Users)  │ │ (Posts/  │ │ (Cache/  │ │ (Graph)  │ │ (Media)  │ │(Embeddings│       │
│  │          │ │  Feeds)  │ │ Counters)│ │          │ │          │ │  /Features│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           OFFLINE / BATCH PROCESSING                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │  Spark   │ │   Hive   │ │  Flink   │ │  Presto  │ │ ML Train │                     │
│  │(Features)│ │(Warehouse│ │(Realtime │ │ (Ad-hoc) │ │(PyTorch) │                     │
│  │          │ │  / Logs) │ │ Features)│ │          │ │          │                     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow - Post Creation
1. Client uploads media to Media Service (presigned URLs to S3)
2. Client sends post metadata to Post Service via API Gateway
3. Post Service validates, stores in Cassandra, publishes `post.created` to Kafka
4. Feed Fanout Workers consume event, determine audience (friends list from Social Graph)
5. For celebrities (>10K friends): **pull model** - post stored, fetched at read time
6. For regular users: **push model** - write post_id to each friend's feed in Cassandra
7. Notification Service sends push notifications to close friends

### Data Flow - Feed Load
1. Client requests feed from Feed Service
2. Feed Service fetches pre-materialized feed from Cassandra (pushed posts)
3. Merges with pull-based posts from followed celebrities/pages
4. Passes candidate posts to ML Ranking Pipeline
5. Ranking scores and orders posts, injects ads
6. Returns paginated, ranked feed to client

---

## 6. Low-Level Design - APIs

### GraphQL Schema (Primary API)
```graphql
type Query {
  newsFeed(first: Int!, after: String, feedType: FeedType): FeedConnection!
  post(id: ID!): Post
  userProfile(id: ID!): User
}

type Mutation {
  createPost(input: CreatePostInput!): Post!
  reactToPost(postId: ID!, reactionType: ReactionType!): Reaction!
  commentOnPost(postId: ID!, input: CommentInput!): Comment!
  sharePost(postId: ID!, input: ShareInput!): Post!
  deletePost(postId: ID!): Boolean!
}
```

### REST APIs (Internal Microservice Communication)

#### Create Post
```
POST /v1/posts
Authorization: Bearer {token}
Content-Type: application/json

Request:
{
  "content": "Hello world! Check out this sunset.",
  "media_ids": ["media_abc123", "media_def456"],
  "audience": "FRIENDS",
  "custom_audience": null,
  "location": {"lat": 37.7749, "lng": -122.4194, "name": "San Francisco, CA"},
  "tagged_users": [123456, 789012],
  "link_url": null,
  "feeling": "happy",
  "bg_color": null
}

Response: 201 Created
{
  "post_id": "7049831205123456",
  "user_id": "100234567",
  "content": "Hello world! Check out this sunset.",
  "media": [
    {"id": "media_abc123", "url": "https://cdn.fb.com/photos/abc123_720.jpg", "type": "photo", "width": 1080, "height": 720},
    {"id": "media_def456", "url": "https://cdn.fb.com/photos/def456_720.jpg", "type": "photo", "width": 1080, "height": 1080}
  ],
  "audience": "FRIENDS",
  "location": {"lat": 37.7749, "lng": -122.4194, "name": "San Francisco, CA"},
  "tagged_users": [{"id": 123456, "name": "Alice"}, {"id": 789012, "name": "Bob"}],
  "reactions": {"total": 0},
  "comments_count": 0,
  "shares_count": 0,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Get News Feed (Cursor Pagination)
```
GET /v1/feed?limit=20&cursor={opaque_cursor}&feed_type=NEWS_FEED
Authorization: Bearer {token}

Response: 200 OK
{
  "posts": [
    {
      "post_id": "7049831205123456",
      "author": {"id": "100234567", "name": "John Doe", "profile_pic": "https://cdn.fb.com/..."},
      "content": "Just got promoted!",
      "media": [],
      "reactions": {"total": 142, "top_types": ["like", "love", "haha"], "viewer_reaction": "like"},
      "comments_count": 23,
      "shares_count": 5,
      "ranking_metadata": {"reason": "friend_posted", "score": 0.92},
      "created_at": "2024-01-15T09:00:00Z"
    }
    // ... more posts
  ],
  "pagination": {
    "next_cursor": "eyJ0IjoxNzA1MzEyMDAwLCJzIjowLjg1fQ==",
    "has_next": true
  },
  "feed_metadata": {
    "total_unseen": 47,
    "last_refresh": "2024-01-15T10:30:00Z"
  }
}
```

#### React to Post
```
POST /v1/posts/{post_id}/reactions
Authorization: Bearer {token}

Request:
{"type": "LOVE"}

Response: 200 OK
{
  "reaction_id": "react_98765",
  "post_id": "7049831205123456",
  "user_id": "100234567",
  "type": "LOVE",
  "created_at": "2024-01-15T10:35:00Z",
  "updated_counts": {"like": 100, "love": 51, "haha": 10}
}
```

#### Comment on Post
```
POST /v1/posts/{post_id}/comments
Authorization: Bearer {token}

Request:
{
  "text": "Congratulations! Well deserved!",
  "reply_to_comment_id": null,
  "media_id": null,
  "tagged_users": []
}

Response: 201 Created
{
  "comment_id": "comm_12345",
  "post_id": "7049831205123456",
  "author": {"id": "100234567", "name": "Jane Smith", "profile_pic": "..."},
  "text": "Congratulations! Well deserved!",
  "reactions": {"total": 0},
  "replies_count": 0,
  "created_at": "2024-01-15T10:36:00Z"
}
```

#### Share Post
```
POST /v1/posts/{post_id}/shares
Authorization: Bearer {token}

Request:
{
  "commentary": "Everyone should see this!",
  "audience": "FRIENDS",
  "share_to": "FEED"
}

Response: 201 Created
{
  "shared_post_id": "7049831205999999",
  "original_post": {"post_id": "7049831205123456", "author": {"id": "...", "name": "..."}},
  "commentary": "Everyone should see this!",
  "created_at": "2024-01-15T10:40:00Z"
}
```

---

## 7. Deep Dive: Feed Ranking ML Pipeline

### Architecture
```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         FEED RANKING PIPELINE                                   │
│                                                                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │  Candidate  │    │   First     │    │   Policy    │    │   Final     │    │
│  │ Generation  │───▶│   Pass      │───▶│  Filtering  │───▶│  Ranking    │    │
│  │  (~2000)    │    │  Scoring    │    │             │    │  (~50)      │    │
│  │             │    │  (~500)     │    │  (~200)     │    │             │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Stage 1: Candidate Generation
Sources of candidates:
- Pre-materialized feed (pushed posts from friends) → ~500 posts
- Pull from followed pages/celebrities → ~300 posts
- Group posts from active groups → ~200 posts
- Recommended posts (explore/suggested) → ~500 posts
- Reshared content from friends-of-friends → ~300 posts
- Ads candidates → ~200 posts

### Stage 2: Scoring Model

#### Feature Categories
```python
# PSEUDOCODE: Feed Ranking Score Computation

class FeedRanker:
    def __init__(self):
        self.model = load_model("feed_ranking_v47")  # Multi-task neural network
        self.feature_store = FeatureStore()           # Real-time + batch features

    def score_candidates(self, user_id: int, candidates: List[Post]) -> List[ScoredPost]:
        user_features = self.feature_store.get_user_features(user_id)
        scored = []

        for post in candidates:
            features = self.extract_features(user_id, post, user_features)
            predictions = self.model.predict(features)

            # Multi-objective scoring (probability of each action)
            p_like = predictions['like']           # P(user likes this post)
            p_comment = predictions['comment']     # P(user comments)
            p_share = predictions['share']         # P(user shares)
            p_click = predictions['click']         # P(user clicks/expands)
            p_hide = predictions['hide']           # P(user hides/reports)
            p_dwell = predictions['dwell_time']    # Expected dwell time (seconds)
            p_video_watch = predictions['video_completion']  # For videos

            # Weighted combination (EdgeRank-inspired but neural)
            score = (
                10.0 * p_share +
                5.0 * p_comment +
                3.0 * p_like +
                2.0 * p_click +
                1.5 * p_dwell / 30.0 +            # Normalize dwell to [0,1]
                4.0 * p_video_watch -
                50.0 * p_hide                      # Heavy penalty for predicted hide
            )

            # Time decay factor
            age_hours = (now() - post.created_at).total_seconds() / 3600
            time_decay = 1.0 / (1.0 + 0.1 * age_hours)  # Half-life ~10 hours

            # Affinity boost (social closeness)
            affinity = self.get_affinity(user_id, post.author_id)

            # Content type weight (user's historical preference)
            type_weight = user_features.content_type_affinity[post.post_type]

            final_score = score * time_decay * affinity * type_weight
            scored.append(ScoredPost(post, final_score, predictions))

        return sorted(scored, key=lambda x: x.score, reverse=True)

    def extract_features(self, user_id: int, post: Post, user_features) -> Dict:
        """Extract 1000+ features for ranking model"""
        return {
            # User-Author Interaction Features
            'friendship_duration_days': ...,
            'messages_exchanged_30d': ...,
            'profile_views_7d': ...,
            'mutual_friends_count': ...,
            'interaction_recency_hours': ...,
            'total_reactions_on_author_posts': ...,
            'comments_on_author_posts_30d': ...,

            # Post Features
            'post_age_hours': ...,
            'post_type': ...,                      # one-hot encoded
            'has_media': ...,
            'media_count': ...,
            'text_length': ...,
            'has_link': ...,
            'has_location': ...,
            'tagged_users_count': ...,
            'post_language': ...,
            'text_embedding': ...,                  # 256-dim BERT embedding

            # Engagement Signals (early engagement velocity)
            'likes_first_hour': ...,
            'comments_first_hour': ...,
            'shares_first_hour': ...,
            'engagement_velocity': ...,             # reactions/minute in first 30min

            # User History Features
            'user_avg_session_duration': ...,
            'user_posts_per_week': ...,
            'user_preferred_content_types': ...,    # embedding
            'user_active_hours': ...,               # one-hot of typical active hours
            'user_scroll_speed_percentile': ...,

            # Context Features
            'day_of_week': ...,
            'hour_of_day': ...,
            'device_type': ...,
            'connection_type': ...,                 # wifi/4g/5g
            'app_version': ...,

            # Social Graph Features
            'author_follower_count': ...,
            'author_post_frequency': ...,
            'common_group_count': ...,
            'is_close_friend': ...,
            'interaction_reciprocity_score': ...,
        }

    def get_affinity(self, user_id: int, author_id: int) -> float:
        """
        Affinity score based on interaction history.
        Inspired by original EdgeRank: Sum(ue * we * de)
        """
        interactions = self.feature_store.get_pairwise_interactions(user_id, author_id)

        affinity = 0.0
        for interaction in interactions:
            # ue = interaction weight by type
            type_weights = {
                'message': 1.0, 'comment': 0.8, 'tag': 0.7,
                'reaction': 0.5, 'click': 0.3, 'view': 0.1
            }
            ue = type_weights.get(interaction.type, 0.1)

            # de = time decay
            age_days = (now() - interaction.timestamp).days
            de = math.exp(-0.05 * age_days)  # Exponential decay, half-life ~14 days

            affinity += ue * de

        # Normalize to [0.1, 2.0] range
        return min(2.0, max(0.1, 0.1 + affinity / 10.0))
```

### Stage 3: Policy Filtering
```python
class PolicyFilter:
    def apply(self, user_id: int, scored_posts: List[ScoredPost]) -> List[ScoredPost]:
        filtered = []
        for post in scored_posts:
            # Integrity checks
            if post.integrity_score < 0.3:          # Misinformation/spam score
                continue
            if post.is_blocked_author(user_id):
                continue
            if not post.passes_audience_check(user_id):
                continue

            # Diversity rules (avoid too much of same type/author)
            # Content quality threshold
            # Civic integrity for political content
            # Well-being signals (reduce doom-scrolling triggers)

            filtered.append(post)

        return self.apply_diversity(filtered)

    def apply_diversity(self, posts: List[ScoredPost]) -> List[ScoredPost]:
        """Ensure feed diversity - no more than 2 consecutive posts from same author,
        mix of content types, balance friend vs page content"""
        result = []
        author_streak = {}
        type_counts = defaultdict(int)

        for post in posts:
            if author_streak.get(post.author_id, 0) >= 2:
                continue  # Skip, will be placed later
            if type_counts[post.post_type] > len(result) * 0.4:
                continue  # Too much of one type

            result.append(post)
            author_streak[post.author_id] = author_streak.get(post.author_id, 0) + 1
            type_counts[post.post_type] += 1

        return result
```

### Stage 4: Final Assembly
- Insert ad slots at positions determined by ad auction
- Add story tray at top
- Inject "People You May Know" cards
- Add group suggestions periodically

### Model Training Pipeline
```
Data Collection (Kafka) → Hive Data Warehouse → Feature Engineering (Spark)
    → Training Data Sampling → Model Training (PyTorch on GPU cluster)
    → Offline Evaluation (AUC, calibration) → A/B Test → Production Rollout

Training frequency: Daily retraining of engagement models
Features refresh: Real-time (Flink) for engagement velocity, hourly (Spark) for aggregates
Model size: ~500MB per ranking model, served via inference service (< 10ms p99)
```

---

## 8. Deep Dive: Social Graph (TAO)

### TAO Architecture
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │     │   Client    │     │   Client    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────┐
│              TAO Cache Layer (Leader)                  │
│  Consistent hashing by (object_id, assoc_type)       │
│  Write-through cache, read-aside                      │
│  In-memory: LRU with ~100B objects cached            │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│           TAO Cache Layer (Follower - Regional)       │
│  Async replication from leader, serves local reads   │
│  Eventual consistency (< 1s in practice)             │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│              MySQL (Persistent Storage)                │
│  Sharded by object_id                                │
│  Tables: objects, associations                        │
│  Billions of rows, SSDs, 3x replication              │
└──────────────────────────────────────────────────────┘
```

### Graph Traversal Logic
```python
class SocialGraphService:
    def __init__(self):
        self.tao = TAOClient()
        self.cache = RedisCluster()

    def get_friends(self, user_id: int, limit: int = 5000) -> List[int]:
        """Get all friends of a user, sorted by affinity"""
        cache_key = f"friends:{user_id}"
        cached = self.cache.zrevrange(cache_key, 0, limit - 1)
        if cached:
            return cached

        # TAO association query
        friends = self.tao.assoc_get(
            id1=user_id,
            assoc_type=AssocType.FRIEND,
            limit=limit
        )
        # Cache with TTL
        pipe = self.cache.pipeline()
        for friend_id, score in friends:
            pipe.zadd(cache_key, {friend_id: score})
        pipe.expire(cache_key, 3600)
        pipe.execute()

        return [f[0] for f in friends]

    def get_friends_of_friends(self, user_id: int, limit: int = 1000) -> List[Tuple[int, int]]:
        """
        2-hop graph traversal for friend suggestions and content discovery.
        Returns [(candidate_id, mutual_friend_count)] sorted by mutuals desc.
        """
        friends = set(self.get_friends(user_id))
        fof_counts = defaultdict(int)

        # Parallel fetch friends-of-friends (batched)
        batch_size = 50
        for i in range(0, len(friends), batch_size):
            batch = list(friends)[i:i + batch_size]
            # Parallel TAO queries
            results = self.tao.assoc_get_batch(
                ids=batch,
                assoc_type=AssocType.FRIEND,
                limit=500
            )
            for friend_friends in results:
                for fof_id, _ in friend_friends:
                    if fof_id != user_id and fof_id not in friends:
                        fof_counts[fof_id] += 1

        # Sort by mutual friend count
        ranked = sorted(fof_counts.items(), key=lambda x: x[1], reverse=True)
        return ranked[:limit]

    def compute_affinity_score(self, user_id: int, target_id: int) -> float:
        """
        Compute pairwise affinity between two users based on:
        - Interaction frequency and recency
        - Mutual friends overlap (Jaccard similarity)
        - Co-engagement on same content
        """
        # Interaction-based affinity
        interactions = self.tao.assoc_time_range(
            id1=user_id,
            id2=target_id,
            assoc_types=[AssocType.COMMENTED, AssocType.LIKED, AssocType.MESSAGED, AssocType.TAGGED],
            time_range=timedelta(days=90)
        )

        interaction_score = sum(
            INTERACTION_WEIGHTS[i.type] * math.exp(-0.03 * i.age_days)
            for i in interactions
        )

        # Mutual friends (Jaccard)
        user_friends = set(self.get_friends(user_id, limit=1000))
        target_friends = set(self.get_friends(target_id, limit=1000))
        jaccard = len(user_friends & target_friends) / max(len(user_friends | target_friends), 1)

        # Combined score
        affinity = 0.7 * sigmoid(interaction_score) + 0.3 * jaccard
        return affinity

    def get_feed_audience(self, author_id: int, post_audience: str, custom_list: List[int] = None) -> Set[int]:
        """Determine who should see a post based on privacy settings"""
        if post_audience == "PUBLIC":
            # Return friends + followers (for fanout)
            friends = set(self.get_friends(author_id))
            followers = set(self.tao.assoc_get(author_id, AssocType.FOLLOWED_BY, limit=100000))
            return friends | followers

        elif post_audience == "FRIENDS":
            return set(self.get_friends(author_id))

        elif post_audience == "CUSTOM":
            friends = set(self.get_friends(author_id))
            if custom_list:
                return friends & set(custom_list)  # Intersection
            return friends

        elif post_audience == "ONLY_ME":
            return {author_id}

        return set()
```

---

## 9. Component Optimization

### Kafka - Event Fanout
```
Topics & Partitioning:
  post.created:        256 partitions, key=author_id, retention=7d
  post.reaction:       128 partitions, key=post_id, retention=3d
  feed.invalidate:     64 partitions, key=user_id, retention=1d
  user.activity:       128 partitions, key=user_id, retention=30d
  ad.impression:       64 partitions, key=ad_id, retention=90d
  notification.send:   64 partitions, key=recipient_id, retention=1d

Consumer groups:
  - feed-fanout-workers (1000 consumers, push to user feeds)
  - activity-aggregator (200 consumers, update feature store)
  - notification-dispatcher (500 consumers, send push/email)
  - ml-feature-pipeline (100 consumers, real-time feature updates)
  - analytics-pipeline (50 consumers, write to Hive)

Throughput: 10M events/second across all topics
```

### Fanout Strategy (Hybrid Push/Pull)
```python
class FeedFanoutService:
    CELEBRITY_THRESHOLD = 10000  # Friends/followers count

    def fanout_post(self, post: Post, author_id: int):
        audience = self.social_graph.get_feed_audience(author_id, post.audience)
        follower_count = len(audience)

        if follower_count > self.CELEBRITY_THRESHOLD:
            # PULL MODEL: Store post, fetch at read time
            self.celebrity_post_index.add(author_id, post.post_id, post.created_at)
            # Still push to close friends (top 500 by affinity)
            close_friends = self.social_graph.get_top_friends(author_id, limit=500)
            self._push_to_feeds(post, close_friends)
        else:
            # PUSH MODEL: Write to each friend's feed
            self._push_to_feeds(post, audience)

    def _push_to_feeds(self, post: Post, recipients: Set[int]):
        # Batch write to Cassandra user_feed table
        batch_size = 1000
        for batch in chunked(recipients, batch_size):
            futures = []
            for user_id in batch:
                futures.append(
                    self.cassandra.execute_async(
                        "INSERT INTO user_feed (user_id, bucket, post_id, author_id, post_type, ranking_score, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?) USING TTL 604800",
                        (user_id, get_daily_bucket(), post.post_id, post.author_id,
                         post.post_type, 0.0, post.created_at)
                    )
                )
            # Wait for batch completion
            for f in futures:
                f.result()
```

### Memcached / TAO Caching
```
Cache hierarchy:
  L1: In-process cache (100K objects, <1ms, per-server)
  L2: Regional Memcached cluster (billions of objects, <5ms)
  L3: TAO leader cache (write-through, <10ms)
  L4: MySQL persistent store (<50ms)

Cache invalidation:
  - Write-through on mutations (immediate consistency for writer)
  - Async invalidation to follower caches (< 1s)
  - Lease-based thundering herd protection
  - Version-based cache keys for frequently updated objects (counters)

Hit rates: L1=90%, L2=99%, L3=99.9%
```

### RocksDB - Embedding Storage
```
Use case: Store user/post embeddings for nearest-neighbor retrieval in ranking

Configuration:
  - LSM-tree optimized for read-heavy workload
  - Block cache: 64GB per node
  - Bloom filters: 10 bits/key (false positive rate < 1%)
  - Compression: LZ4 for L0-L2, ZSTD for L3+
  - Sharded by user_id across 1000+ nodes

Schema:
  Key: {user_id}:{embedding_type}  (e.g., "12345:interest_v3")
  Value: 256-dim float32 vector (1KB) + metadata (timestamp, version)

Operations:
  - Point lookup: <1ms p99
  - Batch get for ranking: 50 embeddings in <5ms
  - Updated hourly via Spark pipeline
```

### Flink - Real-Time Feature Computation
```java
// Real-time engagement velocity computation
DataStream<PostEngagement> engagementStream = env
    .addSource(new KafkaSource("post.reaction"))
    .keyBy(event -> event.getPostId())
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .aggregate(new EngagementVelocityAggregator());

// Output: {post_id, likes_5min, comments_5min, shares_5min, velocity_score}
// Written to Redis for real-time ranking feature lookup

// User session features
DataStream<UserSession> sessionStream = env
    .addSource(new KafkaSource("user.activity"))
    .keyBy(event -> event.getUserId())
    .window(SessionWindows.withGap(Time.minutes(30)))
    .process(new SessionFeatureExtractor());
// Output: {user_id, session_duration, posts_viewed, scroll_depth, engagement_rate}
```

### Spark/Hive - Batch ML Features
```
Daily pipeline (runs at 2AM UTC per region):
1. Aggregate 24h interaction data → pairwise affinity scores
2. Compute user interest embeddings from engagement history
3. Calculate post quality scores from engagement signals
4. Generate training data for ranking model retraining
5. Update friend-of-friend suggestions
6. Compute content type preferences per user

Storage: Hive tables on HDFS, partitioned by date
  - user_features (2B rows, updated daily)
  - pairwise_affinity (100B rows, updated daily)
  - post_quality_scores (1B rows, updated hourly via Flink merge)
```

---

## 10. Observability & Monitoring

### Key Metrics (SLIs/SLOs)
```
Feed Service:
  - feed_load_latency_p50: < 50ms (SLO)
  - feed_load_latency_p99: < 200ms (SLO)
  - feed_load_error_rate: < 0.01% (SLO)
  - feed_empty_rate: < 0.1% (alert if feed returns 0 posts)
  - ranking_model_latency_p99: < 50ms

Post Service:
  - post_create_latency_p99: < 500ms
  - post_fanout_delay_p99: < 5s (time until post appears in friend's feed)
  - post_media_processing_time_p99: < 30s

Infrastructure:
  - kafka_consumer_lag: < 10,000 messages per partition
  - cassandra_read_latency_p99: < 10ms
  - redis_hit_rate: > 95%
  - tao_cache_hit_rate: > 99%
  - cpu_utilization: < 70% (auto-scale trigger)
```

### Distributed Tracing
```
Every feed request generates a trace spanning:
  API Gateway → Feed Service → [Parallel: TAO query, Cassandra read, Redis lookup]
  → Ranking Service → [ML Inference, Feature Fetch] → Response Assembly

Tools: Jaeger/Zipkin-compatible, custom Meta-internal tracing
Sampling: 1% for normal requests, 100% for errors/slow requests
```

### Alerting Rules
```yaml
alerts:
  - name: FeedLatencyHigh
    condition: feed_load_latency_p99 > 300ms for 5min
    severity: P1
    action: Page on-call, auto-rollback last deploy

  - name: FanoutLagHigh
    condition: kafka_consumer_lag > 100000 for 3min
    severity: P2
    action: Auto-scale fanout workers

  - name: RankingModelDegraded
    condition: ranking_model_error_rate > 1% for 2min
    severity: P1
    action: Fallback to previous model version

  - name: FeedEmptyAnomaly
    condition: feed_empty_rate > 1% for 1min
    severity: P0
    action: Circuit break to cached/stale feeds
```

---

## 11. Security & Privacy

### Data Protection
- **Encryption at rest**: AES-256 for all stored data (posts, messages, media)
- **Encryption in transit**: TLS 1.3 for all internal and external communication
- **Data residency**: Regional storage compliance (GDPR - EU data stays in EU)
- **Data deletion**: Hard delete within 90 days of account deletion, immediate soft-delete from feeds

### Privacy Controls Implementation
```python
class PrivacyEnforcement:
    def can_view_post(self, viewer_id: int, post: Post) -> bool:
        if post.audience == "PUBLIC":
            return not self.is_blocked(post.author_id, viewer_id)
        elif post.audience == "FRIENDS":
            return self.are_friends(post.author_id, viewer_id)
        elif post.audience == "CUSTOM":
            return viewer_id in post.custom_audience_include \
                   and viewer_id not in post.custom_audience_exclude
        elif post.audience == "ONLY_ME":
            return viewer_id == post.author_id
        return False

    def filter_feed_for_privacy(self, viewer_id: int, posts: List[Post]) -> List[Post]:
        """Applied AFTER ranking, removes posts viewer shouldn't see"""
        return [p for p in posts if self.can_view_post(viewer_id, p)]
```

### Rate Limiting & Abuse Prevention
- Per-user rate limits: 50 posts/day, 1000 reactions/hour, 500 comments/hour
- Spam detection ML model on post creation (blocks before fanout)
- Coordinated inauthentic behavior detection
- Content integrity classifiers (hate speech, violence, misinformation)

### Authentication & Authorization
- OAuth 2.0 with short-lived access tokens (1 hour) + refresh tokens (60 days)
- Device-based session management with anomaly detection
- Two-factor authentication (TOTP, SMS, security keys)
- Scoped permissions for third-party app access (Graph API)

---

## Summary: Key Design Decisions

| Decision | Rationale |
|---|---|
| Hybrid push/pull fanout | Handles both regular users (push for low latency) and celebrities (pull to avoid write amplification) |
| Multi-stage ranking pipeline | Reduces 2000 candidates to 50 efficiently; heavy ML only on final candidates |
| TAO graph cache | Purpose-built for social graph access patterns; locality-aware, eventually consistent |
| Cassandra for feeds | Time-series write pattern, high write throughput, TTL for auto-cleanup |
| Kafka event-driven | Decouples post creation from fanout; enables replay, multiple consumers |
| Regional deployment | Data locality for GDPR; reduced latency for users |
| Graceful degradation | Stale cached feed > empty feed > error page |
