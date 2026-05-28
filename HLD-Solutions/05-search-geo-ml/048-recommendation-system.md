# Design Recommendation Engine (Netflix/Amazon Style)

## 1. Requirements

### 1.1 Functional Requirements
- **Personalized recommendations**: Tailored content/product suggestions per user
- **Collaborative filtering**: "Users like you also liked X"
- **Content-based filtering**: "Because you watched/bought X"
- **Trending/Popular**: Real-time trending items globally and per-segment
- **Diversity/Serendipity**: Avoid filter bubbles, introduce exploration
- **A/B testing**: Test recommendation algorithms and configurations
- **Cold start handling**: Recommendations for new users/items
- **Real-time personalization**: Adapt to current session behavior
- **Explanation generation**: "Recommended because you watched X"

### 1.2 Non-Functional Requirements
- **Availability**: 99.99% uptime
- **Latency**: < 100ms for recommendation serving (p99)
- **Freshness**: Recommendations update within 1 hour of new interaction
- **Scale**: 500M users, 50M items, 100B+ interactions
- **Throughput**: 1M recommendation requests/sec at peak
- **Model updates**: Support hourly model refreshes without downtime

## 2. Capacity Estimation

### 2.1 Traffic
- 500M users, 200M DAU
- Avg 20 recommendation requests/user/day = 4B requests/day
- Peak: 1M requests/sec
- User interactions (views, clicks, purchases): 10B events/day

### 2.2 Storage
- User profiles/features: 500M × 2KB = 1 TB
- Item metadata: 50M × 5KB = 250 GB
- User-item interaction history: 100B × 20 bytes = 2 TB (compressed)
- User embeddings (256-dim float32): 500M × 1KB = 500 GB
- Item embeddings (256-dim float32): 50M × 1KB = 50 GB
- Feature store (online): 500M users × 200 features × 8 bytes = 800 GB
- Model artifacts: 50 GB per model × 10 models = 500 GB

### 2.3 Bandwidth
- Recommendation responses: 1M/sec × 5KB = 5 GB/sec
- Event ingestion: 10B/day × 100 bytes = 12 MB/sec
- Embedding lookups: 1M/sec × 1KB = 1 GB/sec from feature store

## 3. Data Modeling

### 3.1 PostgreSQL - Metadata & Configuration

```sql
-- Items (movies, products, songs, etc.)
CREATE TABLE items (
    item_id UUID PRIMARY KEY,
    item_type VARCHAR(30) NOT NULL, -- movie, product, song, article
    title VARCHAR(500) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    tags TEXT[], -- Array of tags
    release_date DATE,
    creator_id UUID,
    language VARCHAR(10),
    country VARCHAR(5),
    duration_seconds INT, -- For video/audio
    price_cents INT, -- For products
    avg_rating DECIMAL(3,2),
    total_ratings BIGINT DEFAULT 0,
    popularity_score FLOAT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB, -- Flexible additional attributes
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_items_type_category ON items(item_type, category);
CREATE INDEX idx_items_popularity ON items(popularity_score DESC) WHERE is_active;
CREATE INDEX idx_items_release ON items(release_date DESC);
CREATE INDEX idx_items_tags ON items USING GIN(tags);
CREATE INDEX idx_items_metadata ON items USING GIN(metadata);

-- Users (profile + preferences)
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username VARCHAR(50),
    demographics JSONB, -- age_group, gender, country (aggregated, not PII)
    preferred_categories TEXT[],
    preferred_languages TEXT[],
    account_age_days INT,
    subscription_tier VARCHAR(20),
    onboarding_selections JSONB, -- Cold start preferences
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Recommendation models registry
CREATE TABLE models (
    model_id UUID PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL, -- collaborative, content_based, two_tower, sequence
    version INT NOT NULL,
    status VARCHAR(20) DEFAULT 'training', -- training, validating, serving, deprecated
    metrics JSONB, -- {ndcg, recall, precision, coverage}
    hyperparameters JSONB,
    artifact_path TEXT, -- S3 path to model weights
    training_data_range TSTZRANGE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    promoted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_models_name_version ON models(model_name, version);
CREATE INDEX idx_models_serving ON models(status) WHERE status = 'serving';

-- A/B test configurations
CREATE TABLE ab_experiments (
    experiment_id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'draft', -- draft, running, concluded
    traffic_allocation JSONB, -- {control: 50, treatment_a: 25, treatment_b: 25}
    variants JSONB, -- [{name, model_id, config}]
    primary_metric VARCHAR(50), -- click_through_rate, watch_time, purchase_rate
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    results JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 Cassandra - Interaction History

```cql
-- User interaction events (massive scale, append-heavy)
CREATE TABLE user_interactions (
    user_id UUID,
    event_date DATE,
    event_timestamp TIMESTAMP,
    item_id UUID,
    event_type TEXT, -- view, click, add_to_cart, purchase, rate, share, skip
    event_value FLOAT, -- rating value, watch_percentage, etc.
    context MAP<TEXT, TEXT>, -- device, location, time_of_day, referrer
    session_id UUID,
    PRIMARY KEY ((user_id, event_date), event_timestamp)
) WITH CLUSTERING ORDER BY (event_timestamp DESC)
  AND default_time_to_live = 31536000 -- 1 year TTL
  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_size': 1, 'compaction_window_unit': 'DAYS'};

-- Pre-computed user recommendations (generated by batch pipeline)
CREATE TABLE user_recommendations (
    user_id UUID,
    rec_type TEXT, -- personalized, trending, because_you_watched, new_releases
    generated_at TIMESTAMP,
    items LIST<FROZEN<MAP<TEXT, TEXT>>>, -- [{item_id, score, reason}]
    model_version INT,
    PRIMARY KEY ((user_id), rec_type)
);

-- Item-to-item similarity (pre-computed)
CREATE TABLE item_similarities (
    item_id UUID,
    similar_items LIST<FROZEN<MAP<TEXT, TEXT>>>, -- [{item_id, score, method}]
    updated_at TIMESTAMP,
    PRIMARY KEY (item_id)
);
```

### 3.3 Redis - Online Feature Store & Serving Cache

```redis
# User embedding vector (256-dim float32, stored as binary)
SET user:embedding:user_123 "\x3f\x80\x00\x00..."  # 1024 bytes

# Item embedding vector
SET item:embedding:item_456 "\x3f\x80\x00\x00..."

# User real-time features (updated by streaming pipeline)
HSET user:features:user_123 last_active_ts 1700000000 session_clicks 5 session_views 12 recent_categories "action,comedy,thriller" avg_session_duration 1800 days_since_last_purchase 3

# Pre-computed recommendations (hot cache)
SET user:recs:user_123:personalized "[{item_id, score}, ...]" EX 3600

# Item popularity scores (real-time, powered by Flink)
ZADD item:trending:global 985.5 item_789
ZADD item:trending:global 942.3 item_456
ZADD item:trending:category:action 850.2 item_789

# Recently interacted items (for filtering/dedup)
LPUSH user:recent:user_123 item_789 item_456 item_123
LTRIM user:recent:user_123 0 499  # Keep last 500

# Session context (current browsing session)
HSET session:sess_abc user_id user_123 items_viewed "item_1,item_2,item_3" current_category action started_at 1700000000
EXPIRE session:sess_abc 3600
```

## 4. High-Level Design

### 4.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │
│  │   Web App    │    │  Mobile App  │    │    API       │                      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                      │
└─────────┼───────────────────┼───────────────────┼───────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY + A/B Router                                 │
│  ┌─────────────┐  ┌───────────────────┐  ┌────────────────┐                   │
│  │   Auth      │  │ Experiment Router │  │  Rate Limiter  │                   │
│  └─────────────┘  └───────────────────┘  └────────────────┘                   │
└────────────────────────────────┬────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      RECOMMENDATION SERVING LAYER                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                   │
│  │   Candidate    │  │    Ranking     │  │   Blending/    │                   │
│  │   Generation   │  │    Service     │  │   Re-ranking   │                   │
│  │               │  │               │  │               │                   │
│  │ -CF retrieval │  │ -Two-tower    │  │ -Diversity    │                   │
│  │ -Content-based│  │ -Feature      │  │ -Business     │                   │
│  │ -ANN search   │  │  enrichment   │  │  rules        │                   │
│  │ -Popular      │  │ -Score fusion │  │ -Freshness    │                   │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                   │
└──────────┼───────────────────┼───────────────────┼──────────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FEATURE / MODEL LAYER                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                   │
│  │  Feature Store │  │  Model Serving │  │   Embedding    │                   │
│  │  (Redis/Dynamo)│  │  (TF Serving)  │  │   Index (FAISS)│                   │
│  └────────────────┘  └────────────────┘  └────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA / ML PIPELINES                                     │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────┐                    │
│  │              BATCH PIPELINE (Spark, daily/hourly)        │                    │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────┐    │                    │
│  │  │ Matrix   │  │  Embedding   │  │  Candidate    │    │                    │
│  │  │ Factor.  │  │  Training    │  │  Pre-compute  │    │                    │
│  │  └──────────┘  └──────────────┘  └───────────────┘    │                    │
│  └─────────────────────────────────────────────────────────┘                    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────┐                    │
│  │            REAL-TIME PIPELINE (Kafka + Flink)            │                    │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────┐    │                    │
│  │  │ Event    │  │  Feature     │  │  Trending     │    │                    │
│  │  │ Ingest   │  │  Computation │  │  Aggregation  │    │                    │
│  │  └──────────┘  └──────────────┘  └───────────────┘    │                    │
│  └─────────────────────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Cassandra│  │   S3     │  │  Redis   │  │PostgreSQL│  │  Kafka   │        │
│  │(interact)│  │(models)  │  │(features)│  │(metadata)│  │(events)  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Recommendation Request Flow

```
┌──────────┐    ┌─────────┐    ┌──────────┐    ┌────────┐    ┌─────────┐
│  Client  │    │ Gateway │    │Candidate │    │ Ranker │    │ Blender │
└────┬─────┘    └────┬────┘    └────┬─────┘    └───┬────┘    └────┬────┘
     │               │              │              │              │
     │── GET /recs ─►│              │              │              │
     │               │─ A/B route ─►│              │              │
     │               │              │              │              │
     │               │              │── Get user embedding ──────►│(Feature Store)
     │               │              │── ANN search (FAISS) ──────►│(Embedding Index)
     │               │              │── Get CF candidates ───────►│(Redis)
     │               │              │── Get trending ────────────►│(Redis)
     │               │              │              │              │
     │               │              │─ 500 candidates ─►│         │
     │               │              │              │── Get features│
     │               │              │              │── Score all  │
     │               │              │              │── Top 100 ──►│
     │               │              │              │              │── Apply rules
     │               │              │              │              │── Diversify
     │               │              │              │              │── Explain
     │               │              │              │              │
     │◄──────────── 20 ranked recommendations with explanations ─│
     │               │              │              │              │
     Latency budget: 5ms + 20ms + 30ms + 40ms + 5ms = 100ms total
```

## 5. Low-Level Design - APIs

### 5.1 Get Recommendations API

```
GET /api/v1/recommendations?type=personalized&limit=20&context=homepage
Authorization: Bearer {token}

Response 200:
{
  "recommendations": [
    {
      "item_id": "item_789",
      "title": "Inception",
      "category": "movie",
      "score": 0.95,
      "position": 1,
      "explanation": {
        "type": "because_you_watched",
        "reference_items": ["item_123", "item_456"],
        "text": "Because you watched The Matrix and Interstellar"
      },
      "metadata": {
        "thumbnail_url": "https://cdn.example.com/thumbs/789.jpg",
        "year": 2010,
        "rating": 4.8,
        "genre": "Sci-Fi"
      }
    }
  ],
  "experiment": {
    "experiment_id": "exp_abc",
    "variant": "treatment_a"
  },
  "model_info": {
    "model_name": "two_tower_v3",
    "version": 42,
    "generated_at": "2024-01-15T10:00:00Z"
  },
  "pagination": {
    "offset": 0,
    "limit": 20,
    "has_more": true
  }
}
```

### 5.2 Record Interaction API

```
POST /api/v1/interactions
Authorization: Bearer {token}

Request:
{
  "events": [
    {
      "item_id": "item_789",
      "event_type": "click",
      "timestamp": 1700000000000,
      "context": {
        "source": "homepage_recommendations",
        "position": 3,
        "experiment_id": "exp_abc",
        "variant": "treatment_a",
        "device": "mobile",
        "session_id": "sess_xyz"
      }
    },
    {
      "item_id": "item_789",
      "event_type": "watch",
      "event_value": 0.85,  // 85% watched
      "timestamp": 1700005400000,
      "duration_seconds": 7200
    }
  ]
}

Response 200:
{
  "accepted": 2,
  "processing_id": "batch_abc123"
}
```

### 5.3 Similar Items API

```
GET /api/v1/items/{item_id}/similar?limit=10&method=hybrid

Response 200:
{
  "source_item": "item_789",
  "similar_items": [
    {
      "item_id": "item_456",
      "similarity_score": 0.92,
      "method": "content_embedding",
      "shared_attributes": ["sci-fi", "thriller", "mind-bending"]
    }
  ]
}
```

## 6. Deep Dive: Collaborative Filtering

### 6.1 Matrix Factorization with ALS

```python
import numpy as np
from scipy.sparse import csr_matrix

class ALSMatrixFactorization:
    """
    Alternating Least Squares for implicit feedback collaborative filtering.
    
    Model: R ≈ U × V^T
    - U: user factor matrix (num_users × k)
    - V: item factor matrix (num_items × k)
    - k: embedding dimension (typically 64-256)
    
    For implicit feedback (views, clicks, not explicit ratings):
    - Confidence: c_ui = 1 + α * r_ui (higher interaction count = more confidence)
    - Preference: p_ui = 1 if r_ui > 0, else 0
    
    Minimize: Σ c_ui * (p_ui - u_i^T * v_j)² + λ * (||U||² + ||V||²)
    """
    
    def __init__(self, num_factors: int = 128, regularization: float = 0.01,
                 alpha: float = 40, iterations: int = 15):
        self.k = num_factors
        self.reg = regularization
        self.alpha = alpha
        self.iterations = iterations
        self.user_factors = None
        self.item_factors = None
    
    def fit(self, interaction_matrix: csr_matrix):
        """
        Train model using ALS on user-item interaction matrix.
        interaction_matrix: sparse matrix (users × items) with interaction counts.
        """
        num_users, num_items = interaction_matrix.shape
        
        # Initialize factors randomly
        self.user_factors = np.random.normal(0, 0.01, (num_users, self.k))
        self.item_factors = np.random.normal(0, 0.01, (num_items, self.k))
        
        # Confidence matrix: C = 1 + alpha * R
        # (stored implicitly, computed per-user/item)
        
        for iteration in range(self.iterations):
            # Fix items, solve for users
            self._solve_users(interaction_matrix)
            # Fix users, solve for items
            self._solve_items(interaction_matrix)
            
            loss = self._compute_loss(interaction_matrix)
            print(f"Iteration {iteration}: loss = {loss:.4f}")
    
    def _solve_users(self, R: csr_matrix):
        """Solve for all user factors given fixed item factors."""
        VtV = self.item_factors.T @ self.item_factors  # k × k
        reg_matrix = self.reg * np.eye(self.k)
        
        for user_idx in range(R.shape[0]):
            # Get this user's interactions
            user_row = R[user_idx]
            item_indices = user_row.indices
            interaction_values = user_row.data
            
            if len(item_indices) == 0:
                continue
            
            # Confidence weights for this user's items
            confidence = 1 + self.alpha * interaction_values
            
            # V_i: item factors for items this user interacted with
            V_i = self.item_factors[item_indices]  # n_items × k
            
            # Weighted equation: (V^T * C * V + λI)^-1 * V^T * C * p
            # Efficient computation using the sparse structure
            CmI = np.diag(confidence - 1)  # C - I (only non-zero for interacted items)
            
            A = VtV + V_i.T @ CmI @ V_i + reg_matrix
            b = V_i.T @ (confidence * 1.0)  # p_ui = 1 for all interactions
            
            self.user_factors[user_idx] = np.linalg.solve(A, b)
    
    def _solve_items(self, R: csr_matrix):
        """Solve for all item factors given fixed user factors."""
        UtU = self.user_factors.T @ self.user_factors
        reg_matrix = self.reg * np.eye(self.k)
        
        R_csc = R.tocsc()  # Column-wise access for items
        
        for item_idx in range(R.shape[1]):
            item_col = R_csc[:, item_idx]
            user_indices = item_col.indices
            interaction_values = item_col.data
            
            if len(user_indices) == 0:
                continue
            
            confidence = 1 + self.alpha * interaction_values
            U_j = self.user_factors[user_indices]
            
            CmI = np.diag(confidence - 1)
            A = UtU + U_j.T @ CmI @ U_j + reg_matrix
            b = U_j.T @ (confidence * 1.0)
            
            self.item_factors[item_idx] = np.linalg.solve(A, b)
    
    def recommend(self, user_idx: int, n: int = 20, 
                  exclude_items: set = None) -> list:
        """Generate top-N recommendations for a user."""
        scores = self.user_factors[user_idx] @ self.item_factors.T
        
        if exclude_items:
            for item_idx in exclude_items:
                scores[item_idx] = -np.inf
        
        top_indices = np.argpartition(scores, -n)[-n:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        
        return [(idx, scores[idx]) for idx in top_indices]


class ItemItemCF:
    """
    Item-based collaborative filtering using cosine similarity.
    Pre-computes item-item similarity matrix for fast serving.
    """
    
    def compute_similarities(self, interaction_matrix: csr_matrix, 
                            top_k: int = 100) -> dict:
        """
        Compute top-K similar items for each item using cosine similarity.
        
        Optimization: Use sparse matrix operations and min-hash for
        approximate similarity on large item catalogs.
        """
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Normalize columns (items) to unit vectors
        # Each column represents an item's interaction vector across users
        item_matrix = interaction_matrix.T.tocsr()  # items × users
        
        # Compute pairwise cosine similarity (chunked for memory)
        similarities = {}
        chunk_size = 1000
        
        for start in range(0, item_matrix.shape[0], chunk_size):
            end = min(start + chunk_size, item_matrix.shape[0])
            chunk = item_matrix[start:end]
            
            # Similarity of this chunk against all items
            sim_chunk = cosine_similarity(chunk, item_matrix)
            
            for i, row in enumerate(sim_chunk):
                item_idx = start + i
                # Get top-K (excluding self)
                row[item_idx] = -1  # Exclude self-similarity
                top_k_indices = np.argpartition(row, -top_k)[-top_k:]
                top_k_indices = top_k_indices[row[top_k_indices] > 0]
                
                similarities[item_idx] = [
                    (idx, float(row[idx])) 
                    for idx in sorted(top_k_indices, key=lambda x: row[x], reverse=True)
                ]
        
        return similarities
```

### 6.2 User-User KNN with Locality Sensitive Hashing

```python
class UserUserKNN:
    """
    User-based CF with LSH for efficient neighbor finding.
    Instead of computing similarity with all 500M users,
    use LSH to find approximate nearest neighbors.
    """
    
    def __init__(self, num_hash_tables: int = 10, num_hash_functions: int = 20):
        self.num_tables = num_hash_tables
        self.num_hashes = num_hash_functions
        self.hash_tables = [{} for _ in range(num_hash_tables)]
        self.random_planes = None  # For cosine LSH
    
    def build_index(self, user_vectors: np.ndarray):
        """Build LSH index from user embedding vectors."""
        dim = user_vectors.shape[1]
        
        # Random hyperplanes for SimHash (cosine LSH)
        self.random_planes = np.random.randn(
            self.num_tables, self.num_hashes, dim
        )
        
        for user_idx in range(user_vectors.shape[0]):
            vec = user_vectors[user_idx]
            
            for table_idx in range(self.num_tables):
                # Hash: sign of dot product with random planes
                projections = self.random_planes[table_idx] @ vec
                hash_key = tuple((projections > 0).astype(int))
                
                if hash_key not in self.hash_tables[table_idx]:
                    self.hash_tables[table_idx][hash_key] = []
                self.hash_tables[table_idx][hash_key].append(user_idx)
    
    def find_neighbors(self, user_vector: np.ndarray, k: int = 50) -> list:
        """Find K nearest neighbors using LSH."""
        candidates = set()
        
        for table_idx in range(self.num_tables):
            projections = self.random_planes[table_idx] @ user_vector
            hash_key = tuple((projections > 0).astype(int))
            
            bucket = self.hash_tables[table_idx].get(hash_key, [])
            candidates.update(bucket)
        
        # Re-rank candidates by exact cosine similarity
        if not candidates:
            return []
        
        candidate_list = list(candidates)
        # ... compute exact similarities and return top-k
        return candidate_list[:k]
```

## 7. Deep Dive: Two-Tower Neural Model

### 7.1 Architecture

```python
import tensorflow as tf

class TwoTowerModel(tf.keras.Model):
    """
    Two-tower (dual encoder) model for recommendation.
    
    Architecture:
    - User tower: user features → dense layers → user embedding (256-dim)
    - Item tower: item features → dense layers → item embedding (256-dim)
    - Similarity: dot product of user and item embeddings
    
    Training: Sampled softmax loss (batch negatives + hard negatives)
    Serving: Pre-compute item embeddings, ANN search at query time
    """
    
    def __init__(self, user_feature_dims: dict, item_feature_dims: dict,
                 embedding_dim: int = 256):
        super().__init__()
        self.embedding_dim = embedding_dim
        
        # User tower
        self.user_id_embedding = tf.keras.layers.Embedding(
            input_dim=user_feature_dims["user_id_vocab"],
            output_dim=64
        )
        self.user_category_embedding = tf.keras.layers.Embedding(
            input_dim=user_feature_dims["category_vocab"],
            output_dim=32
        )
        self.user_dense = tf.keras.Sequential([
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(embedding_dim),
            tf.keras.layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=-1))
        ])
        
        # Item tower
        self.item_id_embedding = tf.keras.layers.Embedding(
            input_dim=item_feature_dims["item_id_vocab"],
            output_dim=64
        )
        self.item_category_embedding = tf.keras.layers.Embedding(
            input_dim=item_feature_dims["category_vocab"],
            output_dim=32
        )
        self.item_text_encoder = tf.keras.layers.Dense(128)  # From pre-trained BERT
        self.item_dense = tf.keras.Sequential([
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(embedding_dim),
            tf.keras.layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=-1))
        ])
    
    def user_tower(self, user_features: dict) -> tf.Tensor:
        """Encode user features into embedding vector."""
        user_id_emb = self.user_id_embedding(user_features["user_id"])
        
        # Aggregate recent category preferences
        cat_emb = self.user_category_embedding(user_features["recent_categories"])
        cat_emb = tf.reduce_mean(cat_emb, axis=1)
        
        # Numerical features
        numeric = tf.stack([
            user_features["account_age_normalized"],
            user_features["avg_rating_given"],
            user_features["session_length_normalized"],
            user_features["diversity_score"]
        ], axis=-1)
        
        combined = tf.concat([user_id_emb, cat_emb, numeric], axis=-1)
        return self.user_dense(combined)
    
    def item_tower(self, item_features: dict) -> tf.Tensor:
        """Encode item features into embedding vector."""
        item_id_emb = self.item_id_embedding(item_features["item_id"])
        cat_emb = self.item_category_embedding(item_features["category"])
        text_emb = self.item_text_encoder(item_features["title_embedding"])
        
        numeric = tf.stack([
            item_features["popularity_normalized"],
            item_features["avg_rating_normalized"],
            item_features["recency_score"]
        ], axis=-1)
        
        combined = tf.concat([item_id_emb, cat_emb, text_emb, numeric], axis=-1)
        return self.item_dense(combined)
    
    def call(self, inputs, training=False):
        user_emb = self.user_tower(inputs["user_features"])
        item_emb = self.item_tower(inputs["item_features"])
        
        # Dot product similarity
        similarity = tf.reduce_sum(user_emb * item_emb, axis=-1)
        return similarity
    
    def compute_loss(self, user_emb, item_emb, temperature=0.07):
        """
        In-batch sampled softmax loss.
        All other items in the batch serve as negatives.
        """
        # Similarity matrix: (batch_size × batch_size)
        logits = tf.matmul(user_emb, item_emb, transpose_b=True) / temperature
        
        # Labels: diagonal (each user matches their own item)
        batch_size = tf.shape(user_emb)[0]
        labels = tf.range(batch_size)
        
        loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
            labels=labels, logits=logits
        )
        return tf.reduce_mean(loss)


class EmbeddingIndex:
    """
    FAISS-based approximate nearest neighbor index for item embeddings.
    Supports billion-scale search in <10ms.
    """
    
    def __init__(self, embedding_dim: int = 256, num_items: int = 50_000_000):
        import faiss
        
        # IVF + PQ index for billion-scale
        # IVF: Inverted file with 4096 centroids
        # PQ: Product quantization (32 sub-quantizers, 8 bits each)
        quantizer = faiss.IndexFlatIP(embedding_dim)  # Inner product
        self.index = faiss.IndexIVFPQ(
            quantizer, embedding_dim,
            nlist=4096,      # Number of Voronoi cells
            m=32,            # Number of sub-quantizers
            nbits=8          # Bits per sub-quantizer
        )
        self.index.nprobe = 64  # Search 64 cells (accuracy vs speed)
    
    def build(self, embeddings: np.ndarray):
        """Train and add all item embeddings to index."""
        # Train on a sample
        sample_size = min(1_000_000, embeddings.shape[0])
        sample = embeddings[np.random.choice(embeddings.shape[0], sample_size, replace=False)]
        self.index.train(sample)
        
        # Add all embeddings
        self.index.add(embeddings)
    
    def search(self, query_embedding: np.ndarray, k: int = 100) -> tuple:
        """Find k nearest items to query embedding."""
        # query_embedding shape: (1, 256)
        distances, indices = self.index.search(query_embedding.reshape(1, -1), k)
        return indices[0], distances[0]
```

## 8. Deep Dive: Real-Time Personalization

### 8.1 Session-Based Re-ranking with Contextual Bandits

```python
class RealTimePersonalizer:
    """
    Re-ranks pre-computed candidates using real-time session signals.
    Uses contextual bandit (LinUCB) for exploration/exploitation balance.
    
    Context features: current session behavior, time of day, device, etc.
    Actions: which items to show in top positions
    Reward: click/engagement within session
    """
    
    def __init__(self, feature_dim: int = 64, alpha: float = 0.5):
        self.alpha = alpha  # Exploration parameter
        self.feature_dim = feature_dim
        # Per-item parameters (stored in Redis, loaded on demand)
        # A_a: feature_dim × feature_dim matrix
        # b_a: feature_dim vector
    
    def rerank(self, user_id: str, candidates: list, session_context: dict) -> list:
        """
        Re-rank candidates using LinUCB contextual bandit.
        
        For each candidate item:
        1. Get context features (user session + item features)
        2. Compute expected reward + confidence bound
        3. Select item with highest UCB score
        """
        context_vector = self.build_context_vector(user_id, session_context)
        
        scored_candidates = []
        for item in candidates:
            item_context = self.add_item_features(context_vector, item)
            
            # LinUCB score
            A = self.get_item_params_A(item["item_id"])
            b = self.get_item_params_b(item["item_id"])
            
            A_inv = np.linalg.inv(A)
            theta = A_inv @ b  # Estimated parameters
            
            # Expected reward
            expected = item_context @ theta
            
            # Confidence bound (exploration bonus)
            confidence = self.alpha * np.sqrt(item_context @ A_inv @ item_context)
            
            ucb_score = expected + confidence
            
            scored_candidates.append({
                **item,
                "ucb_score": ucb_score,
                "exploitation_score": expected,
                "exploration_bonus": confidence
            })
        
        # Sort by UCB score
        scored_candidates.sort(key=lambda x: x["ucb_score"], reverse=True)
        return scored_candidates
    
    def update(self, item_id: str, context_vector: np.ndarray, reward: float):
        """Update bandit parameters after observing reward."""
        A = self.get_item_params_A(item_id)
        b = self.get_item_params_b(item_id)
        
        # LinUCB update
        A += np.outer(context_vector, context_vector)
        b += reward * context_vector
        
        self.save_item_params(item_id, A, b)
    
    def build_context_vector(self, user_id: str, session: dict) -> np.ndarray:
        """
        Build context feature vector from real-time session signals.
        """
        features = []
        
        # Time features
        features.append(session.get("hour_of_day", 12) / 24.0)
        features.append(1.0 if session.get("is_weekend") else 0.0)
        
        # Session features
        features.append(min(session.get("items_viewed", 0) / 20.0, 1.0))
        features.append(min(session.get("session_duration_sec", 0) / 3600.0, 1.0))
        features.append(session.get("click_rate_this_session", 0.0))
        
        # User embedding (from feature store, pre-computed)
        user_emb = self.get_user_embedding(user_id)  # 50-dim
        features.extend(user_emb[:50])
        
        # Pad/truncate to fixed dim
        features = features[:self.feature_dim]
        features.extend([0.0] * (self.feature_dim - len(features)))
        
        return np.array(features, dtype=np.float32)
```

### 8.2 Streaming Feature Computation (Flink)

```python
class StreamingFeatureComputer:
    """
    Flink job computing real-time user features from event stream.
    Features update within seconds of user interaction.
    """
    
    def process_event(self, event: dict):
        """
        Compute and update real-time features on each interaction event.
        Window-based aggregations:
        - Last 5 minutes: session_clicks, session_views
        - Last 1 hour: hourly_engagement_rate
        - Last 24 hours: daily_categories_explored, daily_diversity
        """
        user_id = event["user_id"]
        
        # Increment counters
        features = {
            "last_active_ts": event["timestamp"],
            "last_event_type": event["event_type"],
            "last_item_category": event.get("item_category", ""),
        }
        
        # Windowed aggregations (maintained in Flink state)
        if event["event_type"] == "click":
            self.increment_windowed_counter(user_id, "clicks_5min", window="5min")
            self.increment_windowed_counter(user_id, "clicks_1hr", window="1hr")
        
        if event["event_type"] == "view":
            self.increment_windowed_counter(user_id, "views_5min", window="5min")
        
        # Category diversity (unique categories in last 24h)
        if event.get("item_category"):
            self.add_to_set(user_id, "categories_24hr", 
                          event["item_category"], window="24hr")
            features["category_diversity_24hr"] = self.get_set_cardinality(
                user_id, "categories_24hr"
            )
        
        # Compute engagement rate
        views_5min = self.get_windowed_counter(user_id, "views_5min")
        clicks_5min = self.get_windowed_counter(user_id, "clicks_5min")
        features["engagement_rate_5min"] = (
            clicks_5min / max(views_5min, 1)
        )
        
        # Push to online feature store (Redis)
        self.update_feature_store(user_id, features)
```

## 9. Cold Start Handling

```python
class ColdStartHandler:
    """
    Handles recommendations for new users and new items
    where collaborative signals are sparse.
    """
    
    def recommend_new_user(self, user: dict, n: int = 20) -> list:
        """
        Strategies for new users (no interaction history):
        1. Onboarding preferences (if collected)
        2. Demographic-based recommendations
        3. Popularity-based with diversity
        4. Contextual (time, device, location)
        """
        candidates = []
        
        # Strategy 1: Onboarding selections
        if user.get("onboarding_selections"):
            prefs = user["onboarding_selections"]
            # Find items matching stated preferences
            content_recs = self.content_based_from_preferences(prefs)
            candidates.extend(content_recs)
        
        # Strategy 2: Demographic similarity
        if user.get("demographics"):
            similar_segment = self.find_demographic_segment(user["demographics"])
            segment_popular = self.get_segment_popular_items(similar_segment)
            candidates.extend(segment_popular)
        
        # Strategy 3: Global trending with diversity
        trending = self.get_diverse_trending(n=50)
        candidates.extend(trending)
        
        # Deduplicate and blend
        seen = set()
        final = []
        for item in candidates:
            if item["item_id"] not in seen and len(final) < n:
                seen.add(item["item_id"])
                final.append(item)
        
        return final
    
    def handle_new_item(self, item: dict) -> dict:
        """
        Strategies for new items (no interaction data):
        1. Content-based embedding (from item attributes)
        2. Creator/brand affinity transfer
        3. Exploration boost (higher weight in bandit)
        """
        # Generate content embedding from item features
        item_embedding = self.content_model.encode({
            "title": item["title"],
            "description": item["description"],
            "category": item["category"],
            "tags": item["tags"]
        })
        
        # Find similar items by content
        similar_items = self.embedding_index.search(item_embedding, k=20)
        
        # Bootstrap: assume new item has similar audience as content-similar items
        return {
            "embedding": item_embedding,
            "similar_items": similar_items,
            "exploration_boost": 2.0,  # 2x exploration bonus in bandit
            "bootstrap_audience": self.get_audience_of_items(similar_items)
        }
```

## 10. Component Configuration

### 10.1 Model Serving (TensorFlow Serving)

```yaml
tf_serving:
  model_config:
    - name: two_tower_user
      base_path: s3://models/two_tower_user/
      model_platform: tensorflow
      version_policy: {specific: {versions: [42, 43]}}  # A/B versions
      
    - name: ranker
      base_path: s3://models/ranker/
      model_platform: tensorflow
      
  server_config:
    num_load_threads: 8
    num_unload_threads: 4
    max_num_load_retries: 5
    
  batching:
    max_batch_size: 128
    batch_timeout_micros: 5000  # 5ms
    max_enqueued_batches: 100
    num_batch_threads: 16

  resources:
    instances: 30
    cpu: 16 cores
    memory: 64GB
    gpu: 1x V100 (for ranker inference)
```

### 10.2 FAISS Embedding Index

```yaml
faiss_index:
  embedding_dim: 256
  num_items: 50_000_000
  index_type: IVF4096_PQ32x8  # 4096 centroids, 32 sub-quantizers
  nprobe: 64  # Trade-off: higher = more accurate, slower
  
  memory_per_index: ~12GB (with PQ compression)
  
  deployment:
    replicas: 6
    memory: 32GB per replica
    rebuild_frequency: daily
    
  performance:
    search_latency_p50: 3ms
    search_latency_p99: 8ms
    recall@100: 0.95
```

### 10.3 Kafka + Flink Pipeline

```yaml
kafka:
  topics:
    user.interactions:
      partitions: 128
      replication: 3
      retention: 7d
      throughput: 120K events/sec
      
    features.updates:
      partitions: 64
      replication: 3
      retention: 24h
      compaction: enabled

flink:
  jobs:
    feature_computer:
      parallelism: 64
      checkpoint_interval: 30s
      state_backend: rocksdb
      state_ttl: 24h
      
    trending_aggregator:
      parallelism: 16
      window: tumbling(5min)
      
    interaction_enricher:
      parallelism: 32
      watermark: bounded(30s)
```

## 11. Observability

### 11.1 Key Metrics

```yaml
recommendation_quality:
  - click_through_rate (CTR) by position, model, experiment
  - normalized_discounted_cumulative_gain (NDCG@10, NDCG@20)
  - coverage (% of catalog recommended)
  - diversity (intra-list diversity score)
  - novelty (avg inverse popularity of recommended items)
  - serendipity (unexpected but liked items)
  
system_metrics:
  - serving_latency_ms (p50, p95, p99 per stage)
  - candidate_generation_latency_ms
  - ranking_latency_ms
  - feature_store_hit_rate
  - embedding_index_recall
  - model_inference_latency_ms
  - cache_hit_rate (pre-computed recs)
  
pipeline_metrics:
  - feature_freshness_seconds (time from event to feature update)
  - model_staleness_hours (time since last model update)
  - kafka_consumer_lag
  - batch_pipeline_duration_minutes
  
alerts:
  - CTR drops > 10% from baseline → page
  - serving_latency_p99 > 200ms → warn
  - feature_freshness > 5min → warn
  - model_serving_errors > 0.1% → critical
  - embedding_index_stale > 24h → warn
```

## 12. Trade-offs and Considerations

### 12.1 Batch vs Real-Time Recommendations
- **Batch only**: Stale (hours), cheap compute, good recall
- **Real-time only**: Fresh, expensive, limited model complexity
- **Chosen**: Batch for candidate generation + real-time re-ranking (best of both)

### 12.2 Relevance vs Diversity
- Pure relevance optimization → filter bubble, bored users
- Pure diversity → irrelevant recommendations, low CTR
- Solution: MMR (Maximal Marginal Relevance) scoring that balances both

### 12.3 Exploration vs Exploitation
- All exploitation → stuck in local optima, cold items never surfaced
- Too much exploration → poor UX, low engagement
- Solution: Contextual bandits with decaying exploration rate

### 12.4 Embedding Dimension Trade-off
- Higher dim (512): More expressive, slower search, more storage
- Lower dim (64): Fast, less nuanced recommendations
- Chosen: 256 dims with PQ compression for storage efficiency

### 12.5 Online vs Offline Evaluation
- Offline (NDCG, recall): Fast, cheap, doesn't capture real user behavior
- Online (A/B test CTR): Ground truth, expensive, slow (needs traffic)
- Solution: Offline for model iteration, online for final validation

### 12.6 Privacy Considerations
- User interaction data is sensitive (reveals preferences, habits)
- Federated learning: Train on-device, aggregate updates
- Differential privacy: Add noise to user embeddings
- Right to be forgotten: Ability to remove user from all models
