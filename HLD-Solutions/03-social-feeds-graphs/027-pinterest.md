# Design Pinterest: Visual Discovery Platform

## 1. Problem Statement

Design a visual discovery and bookmarking platform where users can discover, save, and organize visual content (pins) into themed boards. The system must support visual search using image embeddings, personalized recommendations via interest graphs, collaborative boards, and shopping integration.

---

## 2. Functional Requirements

1. **Pin Creation & Management**: Upload images/videos, add descriptions, links, and metadata
2. **Board Management**: Create boards, organize pins into boards, reorder pins
3. **Visual Search**: Search by image (camera/upload), find visually similar pins
4. **Home Feed**: Personalized feed based on interests, boards, and engagement history
5. **Search & Discovery**: Text search, category browsing, trending content
6. **Social Features**: Follow users/boards, repin (save others' pins), comments
7. **Collaborative Boards**: Invite collaborators to contribute to boards
8. **Shopping Pins**: Product tagging, price tracking, buy links, shop-the-look
9. **Notifications**: Follows, repins, comments, board invites, price drops
10. **Interest Graph**: Model user interests based on engagement signals

---

## 3. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Feed Latency | < 200ms (p95) |
| Visual Search Latency | < 500ms (p95) |
| Image Upload Processing | < 5s end-to-end |
| Scale | 500M MAU, 350B+ pins saved |
| Storage | Petabytes of images |
| Durability | 99.999999999% for media |
| Consistency | Eventual (social), Strong (shopping) |

---

## 4. Capacity Estimation

### 4.1 Traffic

```
MAU: 500M
DAU: 100M
Avg pins saved per user/day: 3
Avg pins viewed per user/day: 150

Pin saves/day: 100M × 3 = 300M
Pin views/day: 100M × 150 = 15B
Visual searches/day: 50M
Feed requests/day: 500M

Write QPS (pin save): 300M / 86400 ≈ 3,500
Read QPS (pin view): 15B / 86400 ≈ 175,000
Visual search QPS: 50M / 86400 ≈ 580
Feed QPS: 500M / 86400 ≈ 5,800
Peak multiplier: 3x → Read peak: 525K QPS
```

### 4.2 Storage

```
Pins:
- Total pins: 350B (historical) + 300M/day new
- Avg image size: 500KB (original) + 200KB (resized variants)
- Pin metadata: ~1KB per pin
- Image storage: 350B × 700KB = 245 PB (object storage)
- Metadata storage: 350B × 1KB = 350 TB

Embeddings:
- 128-dim float32 per pin: 512 bytes
- 350B × 512B = 179 TB of embeddings

Interest Graph:
- 500M users × avg 200 interests = 100B edges
- Edge: ~50 bytes → 5 TB

Board data:
- 10B boards × 2KB avg metadata = 20 TB
```

### 4.3 Bandwidth

```
Ingress (uploads): 300M × 2MB avg = 600 TB/day = 55 Gbps
Egress (views): 15B × 100KB avg (thumbnails) = 1.5 PB/day = 139 Gbps
CDN offloads 95% → Origin egress: ~7 Gbps
```

---

## 5. Data Modeling

### 5.1 Pin Schema (MySQL/Vitess sharded by pin_id)

```sql
CREATE TABLE pins (
    pin_id          BIGINT PRIMARY KEY,     -- Snowflake ID
    user_id         BIGINT NOT NULL,        -- Creator
    board_id        BIGINT,                 -- Primary board
    image_url       VARCHAR(512) NOT NULL,
    title           VARCHAR(500),
    description     TEXT,
    link_url        VARCHAR(2048),          -- Source link
    domain          VARCHAR(255),
    is_video        BOOLEAN DEFAULT FALSE,
    duration_ms     INT,
    width           INT,
    height          INT,
    dominant_color  CHAR(7),                -- Hex color
    is_shopping     BOOLEAN DEFAULT FALSE,
    product_id      BIGINT,
    price_cents     INT,
    currency        CHAR(3),
    embedding_version INT DEFAULT 1,
    content_hash    CHAR(64),               -- Dedup
    privacy         ENUM('public','private','board_only'),
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    INDEX idx_user_created (user_id, created_at DESC),
    INDEX idx_board (board_id),
    INDEX idx_domain (domain)
) PARTITION BY HASH(pin_id) PARTITIONS 4096;
```

### 5.2 Board Schema

```sql
CREATE TABLE boards (
    board_id        BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    category_id     INT,
    cover_pin_id    BIGINT,
    privacy         ENUM('public','secret','collaborative'),
    pin_count       INT DEFAULT 0,
    follower_count  INT DEFAULT 0,
    is_collaborative BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_category (category_id)
);

CREATE TABLE board_pins (
    board_id        BIGINT,
    pin_id          BIGINT,
    position        INT,                    -- Custom ordering
    added_by        BIGINT,                 -- For collaborative boards
    added_at        TIMESTAMP,
    PRIMARY KEY (board_id, pin_id),
    INDEX idx_board_position (board_id, position)
);

CREATE TABLE board_collaborators (
    board_id        BIGINT,
    user_id         BIGINT,
    role            ENUM('editor','viewer'),
    invited_by      BIGINT,
    joined_at       TIMESTAMP,
    PRIMARY KEY (board_id, user_id)
);
```

### 5.3 User Interest Graph (Neo4j / Custom Graph Store)

```
Node: User {user_id, name, ...}
Node: Interest {interest_id, name, category, parent_id}
Node: Pin {pin_id, embedding_ref}

Edge: User -[INTERESTED_IN {score: 0.0-1.0, decay_ts}]-> Interest
Edge: User -[SAVED]-> Pin
Edge: User -[FOLLOWS]-> User
Edge: User -[FOLLOWS]-> Board
Edge: Pin -[TAGGED_WITH]-> Interest
Edge: Pin -[SIMILAR_TO {distance: float}]-> Pin
Edge: Interest -[CHILD_OF]-> Interest
```

### 5.4 Visual Embedding Store (Milvus / Custom ANN Index)

```
Collection: pin_embeddings
  - pin_id: INT64 (primary key)
  - embedding: FLOAT_VECTOR[128]
  - category_id: INT32 (partition key)
  - created_at: INT64

Index: IVF_PQ
  - nlist: 65536
  - m: 16 (sub-quantizers)
  - nbits: 8
  - metric: COSINE
```

### 5.5 Engagement Events (Kafka → ClickHouse)

```sql
CREATE TABLE engagement_events (
    event_id        UUID,
    user_id         UInt64,
    pin_id          UInt64,
    event_type      Enum8('view'=1,'save'=2,'click'=3,'closeup'=4,
                          'search_click'=5,'hide'=6,'report'=7),
    source          Enum8('feed'=1,'search'=2,'board'=3,'related'=4),
    session_id      String,
    dwell_time_ms   UInt32,
    position        UInt16,
    timestamp       DateTime64(3)
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (user_id, timestamp);
```

---

## 6. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                      │
│         (iOS / Android / Web / Browser Extension)                         │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │
                    ┌─────▼─────┐
                    │   CDN     │  (CloudFront / Akamai)
                    │  + WAF    │  Image serving, static assets
                    └─────┬─────┘
                          │
              ┌───────────▼───────────────┐
              │      API Gateway          │
              │  (Rate limit, Auth, Route)│
              └───────────┬───────────────┘
                          │
        ┌─────────────────┼──────────────────────────┐
        │                 │                          │
   ┌────▼────┐     ┌─────▼─────┐          ┌────────▼────────┐
   │  Pin    │     │   Feed    │          │  Visual Search  │
   │ Service │     │  Service  │          │    Service      │
   └────┬────┘     └─────┬─────┘          └────────┬────────┘
        │                 │                          │
        │          ┌──────▼──────┐          ┌───────▼───────┐
        │          │ Rec Engine  │          │  ANN Index    │
        │          │  (Spark +   │          │  (Milvus/     │
        │          │   Online)   │          │   FAISS)      │
        │          └──────┬──────┘          └───────┬───────┘
        │                 │                          │
   ┌────▼────────────────▼──────────────────────────▼────┐
   │                   DATA LAYER                          │
   │  ┌──────────┐  ┌─────────┐  ┌────────┐  ┌────────┐ │
   │  │  Vitess  │  │  Redis  │  │ Neo4j  │  │  S3    │ │
   │  │ (MySQL)  │  │ Cluster │  │ Graph  │  │ Images │ │
   │  └──────────┘  └─────────┘  └────────┘  └────────┘ │
   │  ┌──────────┐  ┌─────────┐  ┌────────┐  ┌────────┐ │
   │  │ClickHouse│  │  Kafka  │  │ Milvus │  │Elastic │ │
   │  │Analytics │  │ Events  │  │Vectors │  │ Search │ │
   │  └──────────┘  └─────────┘  └────────┘  └────────┘ │
   └──────────────────────────────────────────────────────┘
        │
   ┌────▼──────────────────────────────────┐
   │        OFFLINE / ML PIPELINE           │
   │  ┌─────────┐  ┌──────────┐  ┌──────┐ │
   │  │ Spark   │  │ Training │  │Model │ │
   │  │ ETL     │  │ Pipeline │  │Serve │ │
   │  └─────────┘  └──────────┘  └──────┘ │
   └────────────────────────────────────────┘
```

---

## 7. Low-Level Design & APIs

### 7.1 Pin Service APIs

```
POST /v1/pins
  Body: {image: multipart, title, description, link, board_id, interests[]}
  Response: {pin_id, image_url, embedding_status}
  Flow: Upload → S3 → Trigger image pipeline → Return

GET /v1/pins/{pin_id}
  Response: {pin_id, image_url, title, description, user, board, stats, related_pins[]}

POST /v1/pins/{pin_id}/save
  Body: {board_id}
  Response: {saved: true, board_pin_id}

DELETE /v1/pins/{pin_id}
  Response: {deleted: true}

GET /v1/users/{user_id}/pins?cursor=&limit=25
  Response: {pins[], next_cursor}
```

### 7.2 Feed Service APIs

```
GET /v1/feed/home?cursor=&limit=50
  Response: {pins[], next_cursor, feed_session_id}
  Headers: X-Feed-Experiment: v2_interest_boost

GET /v1/feed/following?cursor=&limit=50
GET /v1/feed/trending?category=&cursor=&limit=50

POST /v1/feed/feedback
  Body: {pin_id, action: "not_interested"|"report", reason}
```

### 7.3 Visual Search APIs

```
POST /v1/visual-search
  Body: {image: multipart, crop_box: {x,y,w,h}}
  Response: {results[]: {pin_id, score, image_url, title}, query_embedding}

POST /v1/visual-search/by-pin/{pin_id}
  Body: {limit: 50}
  Response: {similar_pins[]: {pin_id, distance, image_url}}

GET /v1/visual-search/lens
  -- Real-time camera-based search via streaming
```

### 7.4 Board Service APIs

```
POST /v1/boards
  Body: {name, description, privacy, category_id}
  Response: {board_id, ...}

PUT /v1/boards/{board_id}
PATCH /v1/boards/{board_id}/reorder
  Body: {pin_ids_ordered[]}

POST /v1/boards/{board_id}/collaborators
  Body: {user_id, role}

GET /v1/boards/{board_id}/pins?cursor=&limit=50
```

### 7.5 Shopping APIs

```
GET /v1/pins/{pin_id}/products
  Response: {products[]: {product_id, name, price, merchant, in_stock, buy_url}}

POST /v1/shopping/price-alert
  Body: {pin_id, product_id, target_price}

GET /v1/shopping/catalog?query=&filters=
```

---

## 8. Deep Dive: Visual Similarity Search

### 8.1 Image Embedding Pipeline

```
┌──────────┐    ┌──────────────┐    ┌────────────┐    ┌──────────┐
│  Image   │───►│ Preprocessing│───►│  CNN Model │───►│ Embedding│
│  Upload  │    │  (resize,    │    │ (EfficientNet│   │  128-dim │
│          │    │   normalize) │    │  /ViT)     │    │  float32 │
└──────────┘    └──────────────┘    └────────────┘    └──────────┘
                                                            │
                                          ┌─────────────────▼──────┐
                                          │  Post-processing       │
                                          │  - L2 Normalize        │
                                          │  - PCA (256→128 dim)   │
                                          │  - Quantize if needed  │
                                          └─────────────────┬──────┘
                                                            │
                                          ┌─────────────────▼──────┐
                                          │  Store in Milvus/FAISS │
                                          │  + Update ANN index    │
                                          └────────────────────────┘
```

**Model Architecture:**
- Base: EfficientNet-B4 or Vision Transformer (ViT-B/16)
- Trained with triplet loss + hard negative mining
- Output: 128-dimensional normalized embedding
- Training data: billions of pin engagement pairs (clicked together = similar)

### 8.2 Approximate Nearest Neighbor (ANN) Search

At 350B pins, brute-force search is impossible. We use a multi-level approach:

#### Level 1: Inverted File Index (IVF)

```
Step 1: Cluster all embeddings into K centroids (K=65536)
Step 2: At query time, find top-n closest centroids (nprobe=128)
Step 3: Only search pins assigned to those centroids

Reduction: Search 128/65536 = 0.2% of data
```

#### Level 2: Product Quantization (PQ)

```
128-dim vector split into m=16 sub-vectors (8 dims each)
Each sub-vector quantized to 8-bit codebook (256 codes)
Storage: 128×4 bytes → 16 bytes per vector (32x compression)

Distance computation:
- Precompute distance table: query sub-vector to all 256 codes
- Lookup + sum: 16 lookups per candidate (very fast with SIMD)

Memory for 350B vectors:
- Raw: 350B × 512B = 179 TB
- PQ compressed: 350B × 16B = 5.6 TB
- Fits in distributed memory cluster
```

#### Level 3: HNSW (Hierarchical Navigable Small World)

```
For real-time search on hot/recent pins (last 30 days):
- ~9B pins in HNSW index
- M=16 (connections per node)
- ef_construction=200
- ef_search=128

Memory: 9B × (512B embedding + 16×8B links) = ~5.7 TB
Distributed across 200 machines (28.5 GB each)

Search: O(log N) hops, ~150 distance computations for top-100
Latency: < 10ms for single query
```

#### Hybrid Search Strategy

```python
def visual_search(query_embedding, filters, top_k=100):
    # Stage 1: Category-based routing (reduce search space 10x)
    category = classify_image(query_embedding)
    partition = get_partition(category)
    
    # Stage 2: HNSW for recent pins (fast, high recall)
    recent_candidates = hnsw_index.search(
        query_embedding, 
        partition=partition,
        ef=128, 
        k=top_k * 2
    )
    
    # Stage 3: IVF-PQ for historical pins (larger corpus)
    historical_candidates = ivf_pq_index.search(
        query_embedding,
        partition=partition,
        nprobe=64,
        k=top_k * 2
    )
    
    # Stage 4: Re-rank with exact distance on top candidates
    all_candidates = merge(recent_candidates, historical_candidates)
    top_candidates = all_candidates[:top_k * 4]
    
    # Fetch full embeddings for re-ranking
    full_embeddings = fetch_embeddings(top_candidates)
    exact_distances = compute_cosine(query_embedding, full_embeddings)
    
    # Stage 5: Apply business rules (diversity, freshness, shopping)
    ranked = apply_business_rules(exact_distances, filters)
    return ranked[:top_k]
```

### 8.3 Index Update Strategy

```
New pins: 300M/day → ~3,500/sec embeddings generated

Real-time path (HNSW):
  - Embedding generated → Kafka topic "embeddings"
  - HNSW updater consumes, inserts into index
  - Latency: pin uploaded → searchable in <30 seconds

Batch path (IVF-PQ):
  - Every 6 hours, new embeddings batch-added to IVF-PQ shards
  - Weekly: full re-clustering of centroids (if distribution shifts)
  - Monthly: retrain PQ codebooks

Index Sharding:
  - Partition by category (50 categories)
  - Each partition sharded by pin_id range
  - Total: 50 × 20 shards = 1000 index shards
  - Each shard: ~350M vectors
```

---

## 9. Deep Dive: Image Processing Pipeline

### 9.1 Pipeline Architecture

```
┌────────┐     ┌──────────┐     ┌───────────────────────────────────┐
│ Upload │────►│  S3 Raw  │────►│         Image Pipeline            │
│  API   │     │  Bucket  │     │                                   │
└────────┘     └──────────┘     │  ┌─────────┐   ┌──────────────┐  │
                                │  │Validate │──►│  Generate    │  │
                                │  │& Sanitize│   │  Thumbnails  │  │
                                │  └─────────┘   │  (6 sizes)   │  │
                                │                └──────┬───────┘  │
                                │                       │          │
                                │  ┌─────────────┐  ┌──▼────────┐ │
                                │  │  Extract    │  │  NSFW/    │ │
                                │  │  Metadata   │  │  Safety   │ │
                                │  │  (EXIF,color│  │  Check    │ │
                                │  │   dominant) │  └──┬────────┘ │
                                │  └─────────────┘     │          │
                                │                  ┌───▼────────┐ │
                                │                  │  Generate  │ │
                                │                  │  Embedding │ │
                                │                  └───┬────────┘ │
                                │                      │          │
                                │                  ┌───▼────────┐ │
                                │                  │  OCR /     │ │
                                │                  │  Object    │ │
                                │                  │  Detection │ │
                                │                  └────────────┘ │
                                └───────────────────────────────────┘
```

### 9.2 Thumbnail Generation

```
Sizes generated per pin:
  - 75x75    (grid thumbnail)
  - 236xN    (feed column, maintain aspect ratio)
  - 474xN    (2x feed for retina)
  - 736xN    (closeup view)
  - 1200xN   (full resolution cap)
  - 60x60    (notification/small)

Format: WebP (primary) + JPEG (fallback)
Quality: Perceptual quality optimization (SSIM-guided)
Progressive: Yes, for images > 100KB
Storage: S3 with intelligent tiering
  - Hot (30 days): S3 Standard
  - Warm (1 year): S3 IA
  - Cold (>1 year): S3 Glacier Instant Retrieval
```

### 9.3 Content Safety

```python
class ContentSafetyPipeline:
    def __init__(self):
        self.nsfw_model = load_model("nsfw_v3")        # Binary + severity
        self.violence_model = load_model("violence_v2")
        self.spam_model = load_model("visual_spam_v1")
        self.policy_model = load_model("policy_v4")    # Self-harm, etc.
    
    def evaluate(self, image) -> SafetyResult:
        scores = {
            "nsfw": self.nsfw_model.predict(image),
            "violence": self.violence_model.predict(image),
            "spam": self.spam_model.predict(image),
            "policy": self.policy_model.predict(image),
        }
        
        # Hard blocks
        if scores["nsfw"] > 0.95 or scores["violence"] > 0.9:
            return SafetyResult(action="BLOCK", scores=scores)
        
        # Soft review
        if any(s > 0.7 for s in scores.values()):
            return SafetyResult(action="REVIEW", scores=scores)
        
        # Sensitive content label (shown with warning)
        if scores["nsfw"] > 0.4:
            return SafetyResult(action="LABEL_SENSITIVE", scores=scores)
        
        return SafetyResult(action="ALLOW", scores=scores)
```

---

## 10. Deep Dive: Interest-Based Recommendation

### 10.1 Interest Graph Construction

```
Signals for interest scoring:
┌─────────────────────────────────────────────────────┐
│ Signal              │ Weight │ Decay Half-life       │
├─────────────────────┼────────┼───────────────────────┤
│ Pin save            │ 1.0    │ 30 days               │
│ Pin closeup (>3s)   │ 0.5    │ 14 days               │
│ Pin click-through   │ 0.7    │ 14 days               │
│ Board creation      │ 1.5    │ 90 days               │
│ Search query        │ 0.8    │ 7 days                │
│ Pin hide/report     │ -2.0   │ 180 days              │
│ Time spent on topic │ 0.3    │ 7 days                │
└─────────────────────────────────────────────────────┘

Interest score formula:
  score(user, interest) = Σ (weight_i × action_count_i × decay(t_i))
  decay(t) = exp(-λ × t / half_life)
```

### 10.2 Recommendation Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION PIPELINE                       │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐ │
│  │ Candidate│──►│ Scoring  │──►│ Ranking  │──►│ Diversity  │ │
│  │Generation│   │  Model   │   │  Model   │   │  & Policy  │ │
│  │ (1000s)  │   │ (100s)   │   │ (top 50) │   │  (final)   │ │
│  └──────────┘   └──────────┘   └──────────┘   └────────────┘ │
└────────────────────────────────────────────────────────────────┘

Candidate Generation Sources:
1. Interest-based: Pins tagged with user's top interests
2. Collaborative filtering: "Users like you also saved..."
3. Pin-to-pin: Similar to recently engaged pins (ANN lookup)
4. Board-to-pin: Content similar to user's board themes
5. Trending: Popular in user's geo/demographic
6. Following: Pins from followed users/boards
7. Shopping: Products matching past purchase intent

Scoring Model (Two-Tower):
- User tower: [interests, demographics, recent_actions, context]
- Pin tower: [embedding, category, freshness, quality_score, engagement_stats]
- Score = dot_product(user_embedding, pin_embedding)
- Trained on: save events (positive), hide events (negative)

Ranking Model (Deep & Cross Network):
- Input: scoring_score + pin_features + user_features + context_features
- Cross layers capture feature interactions
- Output: P(save), P(click), P(closeup)
- Final rank = w1*P(save) + w2*P(click) + w3*P(closeup) - w4*P(hide)
```

### 10.3 Real-Time Personalization

```python
class RealTimePersonalizer:
    """Adjusts feed in real-time based on session behavior."""
    
    def __init__(self, user_id, session_id):
        self.user_id = user_id
        self.session_interests = {}  # Updated within session
        self.fatigue_counter = {}    # Topic fatigue
        self.redis = RedisCluster()
    
    def on_engagement(self, pin_id, action, interests):
        """Called on every user action in session."""
        for interest in interests:
            if action in ('save', 'closeup'):
                self.session_interests[interest] = \
                    self.session_interests.get(interest, 0) + 1
            elif action == 'hide':
                self.session_interests[interest] = \
                    self.session_interests.get(interest, 0) - 3
        
        # Store session state in Redis (TTL: 30 min)
        self.redis.hset(
            f"session:{self.session_id}:interests",
            mapping=self.session_interests
        )
    
    def adjust_candidates(self, candidates):
        """Re-rank candidates based on session signals."""
        for candidate in candidates:
            boost = 0
            for interest in candidate.interests:
                boost += self.session_interests.get(interest, 0) * 0.1
                # Apply fatigue for over-represented topics
                if self.fatigue_counter.get(interest, 0) > 10:
                    boost -= 0.3
            candidate.score += boost
        
        return sorted(candidates, key=lambda c: c.score, reverse=True)
```

---

## 11. Component Deep Dives

### 11.1 Kafka Event Streaming

```
Topics:
  - pin.created (300M/day) → partitions: 256, retention: 7d
  - pin.engagement (15B/day) → partitions: 512, retention: 3d
  - pin.embedding.generated → partitions: 128, retention: 1d
  - user.interest.updated → partitions: 128, retention: 7d
  - board.updated → partitions: 64, retention: 7d
  - shopping.price.updated → partitions: 32, retention: 1d

Consumer Groups:
  - feed-generator (consumes pin.created, pin.engagement)
  - interest-updater (consumes pin.engagement)
  - embedding-indexer (consumes pin.embedding.generated)
  - analytics-writer (consumes all → ClickHouse)
  - notification-sender (consumes pin.engagement filtered)

Kafka Config:
  - Replication factor: 3
  - Min ISR: 2
  - Compression: LZ4
  - Batch size: 64KB
  - Linger: 5ms
  - Cluster: 60 brokers, 50TB total
```

### 11.2 Redis Architecture

```
Cluster: 200 nodes, 10TB total memory

Use Cases:
1. Feed cache: Sorted sets per user (pin_id, score)
   Key: feed:{user_id} → ZSET, TTL: 30 min
   Size: top 500 pins per user

2. Session state: Hash per session
   Key: session:{session_id}:interests → HASH, TTL: 30 min

3. Rate limiting: Sliding window
   Key: rate:{user_id}:{action} → ZSET, TTL: 1 min

4. Pin stats (hot pins): Hash
   Key: pin_stats:{pin_id} → HASH {saves, views, clicks}
   Only hot pins (last 24h) in Redis; historical in ClickHouse

5. User interest cache: Sorted set
   Key: interests:{user_id} → ZSET (interest_id, score)
   TTL: 1 hour

6. Collaborative board locks: RedLock
   Key: board_lock:{board_id} → STRING, TTL: 30s
```

### 11.3 Elasticsearch

```
Index: pins
  Settings:
    - Shards: 100
    - Replicas: 2
    - Refresh: 5s
  
  Mappings:
    - title: text (analyzed, english + custom synonyms)
    - description: text (analyzed)
    - interests: keyword[] (for filtering)
    - domain: keyword
    - dominant_color: keyword
    - created_at: date
    - engagement_score: float (for boosting)
    - is_shopping: boolean
    - price_range: integer_range
    - geo: geo_point (for location-based pins)

  Custom Scoring:
    function_score:
      - engagement_score: weight 2.0, log1p modifier
      - freshness: gauss decay, scale 30d
      - pin_quality: weight 1.5
```

### 11.4 Sharding Strategy

```
Pin data (Vitess/MySQL):
  - Shard key: pin_id (hash-based)
  - 4096 shards across 256 MySQL instances
  - Cross-shard queries via Vitess scatter-gather

User data:
  - Shard key: user_id
  - 1024 shards

Board-Pin mapping:
  - Shard key: board_id
  - Co-located with board metadata

Interest Graph (Neo4j):
  - Partition by user_id hash
  - 32 graph partitions
  - Cross-partition queries via federation layer

Embedding Index:
  - Partition by category (50 partitions)
  - Each partition sharded by pin_id range
  - Enables category-scoped search (faster)
```

---

## 12. Shopping Pins Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  Merchant   │────►│  Catalog     │────►│  Product       │
│  Feed API   │     │  Ingestion   │     │  Database      │
└─────────────┘     └──────────────┘     └───────┬────────┘
                                                  │
                    ┌──────────────┐     ┌────────▼────────┐
                    │  Visual      │────►│  Pin-Product    │
                    │  Matching    │     │  Linking        │
                    └──────────────┘     └───────┬─────────┘
                                                 │
                    ┌──────────────┐     ┌───────▼─────────┐
                    │  Price       │────►│  Shopping       │
                    │  Monitoring  │     │  Experience     │
                    └──────────────┘     └─────────────────┘

Product-Pin Matching:
1. Merchant provides product catalog (images + metadata)
2. Generate embeddings for product images
3. Match product embeddings to pin embeddings (cosine > 0.92)
4. Human review for borderline cases
5. Auto-tag pins with product info

Price Tracking:
- Scrape merchant prices every 4 hours
- Store price history in TimescaleDB
- Trigger notifications on price drops > 10%
- Handle currency conversion for international users
```

---

## 13. Collaborative Boards

```
Concurrency Control:
- Optimistic locking with version vectors
- Conflict resolution: Last-writer-wins for pin ordering
- Real-time sync via WebSocket channels per board

Board Activity Stream:
- Event sourcing pattern for board modifications
- Events: PinAdded, PinRemoved, PinReordered, CollaboratorAdded
- Consumers rebuild board state from events

Permission Model:
- Owner: Full control (delete board, manage collaborators)
- Editor: Add/remove pins, reorder
- Viewer: Read-only access (for secret boards)

Real-time Updates:
- WebSocket room per active board
- Broadcast on any modification
- Offline changes queued and replayed on reconnect
```

---

## 14. Observability

### 14.1 Key Metrics

```
Business Metrics:
- Pin saves/day (target: 300M)
- Feed engagement rate (saves / impressions)
- Visual search success rate (click-through after search)
- Shopping conversion rate
- Time to first save (new user activation)

System Metrics:
- Feed generation latency: p50/p95/p99
- Visual search latency: p50/p95/p99
- Image pipeline throughput and error rate
- ANN index recall@100 (target: 95%)
- Embedding generation latency
- Cache hit rates (feed cache, interest cache)

SLOs:
- Feed: 99.9% requests < 200ms
- Visual search: 99.5% requests < 500ms
- Pin upload to visible: 99% < 5 seconds
- Image serving: 99.99% availability via CDN
```

### 14.2 Alerting

```yaml
alerts:
  - name: feed_latency_high
    condition: p95_latency > 300ms for 5 min
    severity: P1
    runbook: /runbooks/feed-latency

  - name: embedding_pipeline_lag
    condition: kafka_consumer_lag > 1M messages
    severity: P2
    runbook: /runbooks/embedding-lag

  - name: ann_recall_degraded
    condition: recall_at_100 < 0.90
    severity: P2
    runbook: /runbooks/ann-index-health

  - name: image_pipeline_error_rate
    condition: error_rate > 1%
    severity: P1
    runbook: /runbooks/image-pipeline
```

---

## 15. Key Considerations

### 15.1 Cold Start Problem
- New users: Onboarding flow picks 5+ interests → seed feed
- New pins: Embedding-based placement + creator's audience
- Explore tab: Curated trending content (interest-agnostic)

### 15.2 Embedding Model Updates
- New model generates different embedding space
- Dual-write period: Index old + new embeddings simultaneously
- Gradual rollout: 1% → 10% → 50% → 100% traffic to new index
- Keep old index alive for 30 days as rollback safety

### 15.3 Copyright & Dedup
- Content hash (perceptual hash / pHash) on upload
- Near-duplicate detection: embedding distance < 0.05
- DMCA takedown system with hash-based blocking

### 15.4 International Scale
- Image CDN: 50+ PoPs globally
- Search: Language-specific analyzers
- Embedding model: Trained on multi-lingual/multi-cultural visual content
- Interest taxonomy: Localized per region

### 15.5 Failure Modes
- ANN index partition failure: Fallback to other partitions (degraded recall)
- Embedding service down: Queue uploads, serve pins without visual search
- Feed service overload: Return cached feed (stale but available)
- Redis cluster failure: Regenerate feed from DB (slower, acceptable)

---

## 16. Summary

| Component | Technology | Scale |
|---|---|---|
| Pin Metadata | Vitess (MySQL) | 350B rows, 4096 shards |
| Image Storage | S3 + CDN | 245 PB |
| Visual Embeddings | Milvus + FAISS | 350B vectors, 5.6 TB (PQ) |
| Interest Graph | Neo4j + Redis | 100B edges |
| Feed Cache | Redis Cluster | 200 nodes, 10 TB |
| Search | Elasticsearch | 100 shards |
| Events | Kafka | 15B+ events/day |
| Analytics | ClickHouse | Petabyte-scale |
| ML Serving | TorchServe + Triton | 3,500 embeddings/sec |
| Recommendations | Spark + Real-time | 5,800 feed req/sec |

