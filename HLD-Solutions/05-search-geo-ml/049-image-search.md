# Image Search System Design (Google Images / Pinterest Visual Search)

## 1. Requirements

### 1.1 Functional Requirements
| ID | Requirement | Description |
|----|-------------|-------------|
| FR1 | Text-to-Image Search | Query with text, return ranked images |
| FR2 | Reverse Image Search | Upload image, find visually similar images |
| FR3 | Image Upload Search | Search by uploading a photo |
| FR4 | Crop-Region Search | Select sub-region of image to search |
| FR5 | Multi-Modal Query | Combine text + image for refined search |
| FR6 | Safe Search Filtering | Filter NSFW/violent content |
| FR7 | Similar Image Suggestions | "More like this" recommendations |

### 1.2 Non-Functional Requirements
| Requirement | Target |
|-------------|--------|
| Availability | 99.99% uptime |
| Search Latency | < 200ms p99 |
| Index Size | 10B+ images |
| Query Throughput | 100K QPS |
| Freshness | New images indexed within 1 hour |
| Embedding Accuracy | Top-10 recall > 85% |

---

## 2. Capacity Estimation

### 2.1 Storage
```
Images indexed: 10 billion
Average metadata per image: 2 KB
Metadata storage: 10B × 2 KB = 20 TB

Visual embedding per image (512-dim float16): 1 KB
Embedding storage: 10B × 1 KB = 10 TB

Thumbnails (average 15 KB): 10B × 15 KB = 150 TB
Text index (title, alt, surrounding text): ~50 TB

Total storage: ~230 TB (without replicas)
With 3x replication: ~700 TB
```

### 2.2 Compute
```
QPS: 100,000
Embedding generation per query: ~10ms on GPU
GPU cluster for query embedding: 100K × 10ms = 1000 GPU-seconds/sec
  → ~1000 GPUs (A100) for query embedding alone

ANN search per query: ~5ms
Indexing new images: 10M/day × 50ms = ~6 GPU-hours/day

Re-ranking per query (top-1000 → top-50): ~20ms
```

### 2.3 Bandwidth
```
Query requests: 100K QPS × 1 KB avg = 100 MB/s inbound
Response (20 thumbnails × 15 KB): 100K × 300 KB = 30 GB/s outbound (CDN-served)
```

---

## 3. Data Modeling

### Entity-Relationship Diagram

```mermaid
erDiagram
    IMAGES {
        bigint image_id PK
        text source_url
        varchar domain
        text title
        char content_hash
        float safe_search_score
        float quality_score
    }
    IMAGE_LABELS {
        bigint image_id FK
        varchar label PK
        float confidence
        varchar source
    }
    IMAGE_FACES {
        bigint face_id PK
        bigint image_id FK
        float bbox_x
        float bbox_y
        varchar embedding_ref
    }
    SEARCH_FEEDBACK {
        bigint feedback_id PK
        bigint image_id FK
        char query_hash
        varchar action
        int position
    }
    IMAGES ||--o{ IMAGE_LABELS : "tagged with"
    IMAGES ||--o{ IMAGE_FACES : contains
    IMAGES ||--o{ SEARCH_FEEDBACK : "feedback on"
```

### 3.1 Image Metadata (PostgreSQL - sharded by image_id)
```sql
CREATE TABLE images (
    image_id        BIGINT PRIMARY KEY,          -- snowflake ID
    source_url      TEXT NOT NULL,
    canonical_url   TEXT,
    domain          VARCHAR(255),
    title           TEXT,
    alt_text        TEXT,
    surrounding_text TEXT,
    width           INT,
    height          INT,
    format          VARCHAR(10),                  -- jpeg, png, webp
    file_size_bytes BIGINT,
    content_hash    CHAR(64),                    -- SHA-256 for dedup
    safe_search_score FLOAT,                     -- 0.0 (safe) to 1.0 (unsafe)
    quality_score   FLOAT,                       -- image quality 0-1
    crawl_timestamp TIMESTAMPTZ NOT NULL,
    index_timestamp TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'active', -- active, removed, dmca
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_images_content_hash ON images(content_hash);
CREATE INDEX idx_images_domain ON images(domain);
CREATE INDEX idx_images_crawl_ts ON images(crawl_timestamp);

CREATE TABLE image_labels (
    image_id    BIGINT REFERENCES images(image_id),
    label       VARCHAR(255),
    confidence  FLOAT,
    source      VARCHAR(50),  -- 'model_v3', 'user_tag', 'ocr'
    PRIMARY KEY (image_id, label, source)
);

CREATE TABLE image_faces (
    face_id     BIGINT PRIMARY KEY,
    image_id    BIGINT REFERENCES images(image_id),
    bbox_x      FLOAT,
    bbox_y      FLOAT,
    bbox_w      FLOAT,
    bbox_h      FLOAT,
    embedding_ref VARCHAR(255)
);

CREATE TABLE search_feedback (
    feedback_id  BIGINT PRIMARY KEY,
    query_hash   CHAR(64),
    image_id     BIGINT,
    action       VARCHAR(20),  -- click, long_view, save, report
    position     INT,
    timestamp    TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 Visual Embeddings (Milvus / FAISS cluster)
```
Collection: image_embeddings
- image_id: INT64 (primary key)
- embedding: FLOAT_VECTOR[512]  (CLIP ViT-L/14 output)
- cluster_id: INT32             (for IVF partitioning)
- quality_score: FLOAT32

Index: IVF_PQ
- nlist: 65536 (number of Voronoi cells)
- m: 64 (PQ sub-quantizers)
- nbits: 8
- metric: INNER_PRODUCT (cosine after L2-norm)
```

### 3.3 Text Index (Elasticsearch)
```json
{
  "mappings": {
    "properties": {
      "image_id": { "type": "long" },
      "title": { "type": "text", "analyzer": "english" },
      "alt_text": { "type": "text", "analyzer": "english" },
      "surrounding_text": { "type": "text", "analyzer": "english" },
      "labels": { "type": "keyword" },
      "domain": { "type": "keyword" },
      "dimensions": { "type": "keyword" },
      "color_palette": { "type": "keyword" },
      "safe_search": { "type": "float" },
      "quality_score": { "type": "float" },
      "crawl_date": { "type": "date" },
      "page_rank": { "type": "float" }
    }
  },
  "settings": {
    "number_of_shards": 256,
    "number_of_replicas": 2
  }
}
```

### 3.4 Thumbnail Storage (S3 + CDN)
```
Bucket structure:
s3://image-thumbnails/{shard_prefix}/{image_id}/
  - thumb_150x150.webp
  - thumb_300x300.webp
  - thumb_600x600.webp

CDN: CloudFront with edge caching
TTL: 30 days for thumbnails
```

---

## 4. High-Level Design

### 4.1 Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│   [Web App]  [Mobile App]  [API Clients]  [Chrome Extension]            │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             GATEWAY LAYER                                │
│   [Load Balancer (L7)]  →  [API Gateway]  →  [Rate Limiter]            │
│   [Auth Service]  [Query Router]  [A/B Test Config]                     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│  QUERY UNDERSTANDING │ │  IMAGE UPLOAD    │ │  EMBEDDING SERVICE   │
│                      │ │  SERVICE         │ │  (GPU Cluster)       │
│  - Query parsing     │ │  - Validate      │ │                      │
│  - Spell correction  │ │  - Resize/crop   │ │  - CLIP ViT-L/14     │
│  - Intent detection  │ │  - Hash dedup    │ │  - Text encoder      │
│  - Query expansion   │ │  - Store temp    │ │  - Image encoder     │
│  - Safe search class │ │  - Extract ROI   │ │  - Batch inference   │
└──────────┬───────────┘ └────────┬─────────┘ └──────────┬───────────┘
           │                      │                       │
           ▼                      ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          RETRIEVAL LAYER                                  │
│                                                                          │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐        │
│  │   TEXT RETRIEVAL     │    │     VECTOR RETRIEVAL              │        │
│  │                      │    │                                   │        │
│  │  Elasticsearch       │    │  Milvus Cluster (10B vectors)    │        │
│  │  - BM25 scoring      │    │  - IVF-PQ index                  │        │
│  │  - 256 shards        │    │  - HNSW graph (hot partition)    │        │
│  │  - Fuzzy matching    │    │  - Scatter-gather search         │        │
│  │  - Filter queries    │    │  - Top-K ANN (K=1000)            │        │
│  └─────────┬────────────┘    └──────────────┬───────────────────┘        │
│            │                                 │                            │
│            └────────────┬────────────────────┘                            │
│                         ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────┐        │
│  │               FUSION & RE-RANKING                             │        │
│  │                                                               │        │
│  │  - Reciprocal Rank Fusion (RRF) of text + visual scores      │        │
│  │  - Cross-encoder re-ranking (CLIP re-score top-200)          │        │
│  │  - Quality signal boosting                                    │        │
│  │  - Diversity injection (MMR algorithm)                        │        │
│  │  - Safe search filtering                                      │        │
│  │  - Personalization layer                                      │        │
│  └──────────────────────────────────┬───────────────────────────┘        │
└─────────────────────────────────────┼───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          RESPONSE ASSEMBLY                                │
│  - Fetch thumbnails from CDN                                             │
│  - Build result cards (title, source, dimensions)                        │
│  - Attach "similar images" links                                         │
│  - Cache hot results in Redis                                            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       OFFLINE / INDEXING PIPELINE                         │
│                                                                          │
│  [Web Crawler] → [Kafka] → [Image Processor] → [Embedding Gen (GPU)]   │
│       │              │            │                      │               │
│       ▼              ▼            ▼                      ▼               │
│  [URL Frontier] [Dedup Store] [Thumbnail Gen]    [Vector Index Build]   │
│                               [Metadata Extract]  [ES Index Update]      │
│                               [Safe Search Model] [Quality Scoring]      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Low-Level Design - APIs

### 5.1 Text Search API
```
POST /v1/search/text
Headers:
  Authorization: Bearer <token>
  X-Request-ID: uuid

Request:
{
  "query": "golden retriever puppy playing in snow",
  "filters": {
    "size": "large",           // small, medium, large, xlarge
    "color": "any",            // red, blue, specific hex
    "type": "photo",           // photo, clipart, lineart, animated
    "time": "past_year",
    "license": "creative_commons",
    "safe_search": "strict"    // off, moderate, strict
  },
  "pagination": {
    "offset": 0,
    "limit": 20
  },
  "include_similar": true
}

Response (200 OK):
{
  "request_id": "uuid",
  "query_understanding": {
    "corrected_query": null,
    "intent": "visual_search",
    "expanded_terms": ["golden retriever", "puppy", "snow", "dog playing"]
  },
  "results": [
    {
      "image_id": "8923749182374",
      "thumbnail_url": "https://cdn.imgsearch.com/t/8923749182374/300x300.webp",
      "source_url": "https://example.com/dogs/golden.html",
      "title": "Golden Retriever Puppy in Snow",
      "dimensions": {"width": 4000, "height": 3000},
      "relevance_score": 0.94,
      "similar_images_url": "/v1/search/similar/8923749182374"
    }
  ],
  "total_results": 1243567,
  "search_time_ms": 142,
  "next_offset": 20
}
```

### 5.2 Reverse Image Search API
```
POST /v1/search/image
Headers:
  Content-Type: multipart/form-data
  Authorization: Bearer <token>

Request (multipart):
  - file: <binary image data>
  - crop_box: {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6}  (optional, normalized)
  - search_type: "similar"  // "similar", "exact", "products"
  - limit: 20

Response (200 OK):
{
  "request_id": "uuid",
  "uploaded_image": {
    "temp_id": "tmp_abc123",
    "dimensions": {"width": 1920, "height": 1080},
    "detected_objects": [
      {"label": "dog", "confidence": 0.97, "bbox": [0.1, 0.2, 0.6, 0.8]},
      {"label": "snow", "confidence": 0.91, "bbox": [0.0, 0.0, 1.0, 1.0]}
    ]
  },
  "results": [...],
  "exact_matches": [
    {
      "image_id": "123456",
      "source_url": "https://original-source.com/photo.jpg",
      "match_type": "exact_duplicate",
      "similarity": 1.0
    }
  ],
  "visual_similar": [...],
  "search_time_ms": 187
}
```

### 5.3 Multi-Modal Search API
```
POST /v1/search/multimodal
Request:
{
  "text_query": "similar but in red color",
  "reference_image_id": "8923749182374",
  "text_weight": 0.4,
  "image_weight": 0.6,
  "limit": 20
}

Response (200 OK):
{
  "results": [...],
  "fusion_method": "weighted_embedding_interpolation",
  "search_time_ms": 165
}
```

### 5.4 Indexing API (Internal)
```
POST /v1/internal/index
Request:
{
  "image_id": "new_image_123",
  "source_url": "https://example.com/photo.jpg",
  "metadata": {
    "title": "Beach sunset",
    "alt_text": "Beautiful sunset over ocean",
    "page_text": "...",
    "page_rank": 0.72
  },
  "embedding": [0.023, -0.156, ...],  // 512-dim
  "labels": [{"label": "sunset", "confidence": 0.95}],
  "safe_search_score": 0.02,
  "quality_score": 0.87
}
```

---

## 6. Deep Dive: Visual Embedding Pipeline

### 6.1 Architecture
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Raw Image   │────▶│ Preprocessing│────▶│  CNN/ViT     │────▶│  L2 Norm │
│  (any size)  │     │  - Resize    │     │  Backbone    │     │  + PCA   │
│              │     │  - Normalize │     │  (ViT-L/14)  │     │          │
└──────────────┘     │  - Augment   │     └──────────────┘     └────┬─────┘
                     └──────────────┘                                │
                                                                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Milvus      │◀────│  IVF-PQ     │◀────│  Quantize    │◀────│ 512-dim  │
│  Cluster     │     │  Indexing    │     │  (PQ-64x8)   │     │ Embedding│
└──────────────┘     └──────────────┘     └──────────────┘     └──────────┘
```

### 6.2 Model Architecture (CLIP ViT-L/14)
```python
class ImageEmbeddingPipeline:
    """
    Visual embedding using CLIP ViT-L/14 for joint text-image space.
    Output: 512-dimensional L2-normalized embedding.
    """

    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
        self.pca_matrix = load_pca_matrix("pca_768_to_512.npy")  # dim reduction

    def preprocess(self, image: PIL.Image) -> torch.Tensor:
        """Resize to 224x224, normalize with CLIP stats."""
        # Handle various input formats
        if image.mode != 'RGB':
            image = image.convert('RGB')

        inputs = self.processor(images=image, return_tensors="pt")
        return inputs['pixel_values']

    def extract_embedding(self, pixel_values: torch.Tensor) -> np.ndarray:
        """Extract visual embedding from ViT backbone."""
        with torch.no_grad():
            # Get image features from CLIP vision encoder
            image_features = self.model.get_image_features(pixel_values)
            # Project to shared space
            embedding = image_features.cpu().numpy()

        # Apply PCA for dimensionality reduction (768 → 512)
        embedding = embedding @ self.pca_matrix

        # L2 normalize for cosine similarity via dot product
        embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
        return embedding.astype(np.float16)

    def extract_region_embedding(self, image: PIL.Image, bbox: dict) -> np.ndarray:
        """Extract embedding for a cropped region of interest."""
        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        img_w, img_h = image.size
        crop_box = (int(x*img_w), int(y*img_h),
                    int((x+w)*img_w), int((y+h)*img_h))
        cropped = image.crop(crop_box)
        pixel_values = self.preprocess(cropped)
        return self.extract_embedding(pixel_values)

    def batch_extract(self, images: List[PIL.Image], batch_size=64) -> np.ndarray:
        """Batch embedding extraction for indexing pipeline."""
        all_embeddings = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            pixel_values = torch.cat([self.preprocess(img) for img in batch])
            embeddings = self.extract_embedding(pixel_values)
            all_embeddings.append(embeddings)
        return np.vstack(all_embeddings)
```

### 6.3 ANN Index Building (Offline)
```python
class ANNIndexBuilder:
    """
    Build IVF-PQ index for 10B vectors using FAISS.
    Strategy: Train on sample, then add in sharded batches.
    """

    def __init__(self, dim=512, nlist=65536, m=64, nbits=8):
        self.dim = dim
        self.nlist = nlist  # Voronoi cells
        self.m = m          # PQ sub-vectors
        self.nbits = nbits

    def train_index(self, training_vectors: np.ndarray):
        """Train quantizer on representative sample (1-10M vectors)."""
        # Coarse quantizer (IVF)
        quantizer = faiss.IndexFlatIP(self.dim)

        # IVF + Product Quantization
        self.index = faiss.IndexIVFPQ(
            quantizer, self.dim, self.nlist, self.m, self.nbits,
            faiss.METRIC_INNER_PRODUCT
        )

        # Train on sample
        print(f"Training on {len(training_vectors)} vectors...")
        self.index.train(training_vectors)
        print("Training complete.")

    def add_vectors_sharded(self, vector_iterator, shard_size=10_000_000):
        """Add vectors in batches, building sharded index."""
        shard_id = 0
        for batch_ids, batch_vectors in vector_iterator:
            self.index.add_with_ids(batch_vectors, batch_ids)

            if self.index.ntotal % shard_size == 0:
                # Write shard to disk
                shard_path = f"index_shard_{shard_id}.faiss"
                faiss.write_index(self.index, shard_path)
                shard_id += 1

    def build_hnsw_overlay(self, hot_vectors: np.ndarray, hot_ids: np.ndarray):
        """Build HNSW index for frequently accessed images (top 100M)."""
        hnsw_index = faiss.IndexHNSWFlat(self.dim, 32)  # M=32
        hnsw_index.hnsw.efConstruction = 200
        hnsw_index.add(hot_vectors)
        return hnsw_index

    def search(self, query_vector: np.ndarray, top_k=1000, nprobe=128):
        """Search with tuned nprobe for recall/latency tradeoff."""
        self.index.nprobe = nprobe
        distances, indices = self.index.search(query_vector, top_k)
        return distances, indices
```

---

## 7. Deep Dive: Multi-Modal Retrieval

### 7.1 CLIP Joint Embedding Space
```
┌─────────────────────────────────────────────────┐
│           CLIP Joint Embedding Space             │
│                                                  │
│   Text: "red car"  ──────┐                      │
│                           ├──▶ Same region       │
│   Image: [photo of       │    in 512-d space    │
│           red car]  ─────┘                      │
│                                                  │
│   Similarity = dot_product(text_emb, img_emb)   │
└─────────────────────────────────────────────────┘
```

### 7.2 Hybrid Scoring Algorithm
```python
class HybridRetriever:
    """
    Combines text-based BM25 retrieval with visual ANN retrieval
    using Reciprocal Rank Fusion (RRF) or learned fusion.
    """

    def __init__(self, es_client, milvus_client, clip_model):
        self.es = es_client
        self.milvus = milvus_client
        self.clip = clip_model

    def search_text_only(self, query: str, top_k=1000) -> List[ScoredResult]:
        """BM25 text retrieval from Elasticsearch."""
        es_results = self.es.search(
            index="images",
            body={
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3", "alt_text^2", "labels^2", "surrounding_text"],
                        "type": "best_fields"
                    }
                },
                "size": top_k
            }
        )
        return [(hit['_id'], hit['_score']) for hit in es_results['hits']['hits']]

    def search_visual(self, query_embedding: np.ndarray, top_k=1000) -> List[ScoredResult]:
        """ANN search in vector database."""
        results = self.milvus.search(
            collection_name="image_embeddings",
            data=[query_embedding.tolist()],
            limit=top_k,
            search_params={"nprobe": 128}
        )
        return [(hit.id, hit.distance) for hit in results[0]]

    def reciprocal_rank_fusion(self, ranked_lists: List[List], k=60) -> List:
        """
        RRF: score(d) = Σ 1/(k + rank_i(d))
        Provably effective fusion without score normalization.
        """
        fused_scores = defaultdict(float)
        for ranked_list in ranked_lists:
            for rank, (doc_id, _) in enumerate(ranked_list):
                fused_scores[doc_id] += 1.0 / (k + rank + 1)

        # Sort by fused score descending
        return sorted(fused_scores.items(), key=lambda x: -x[1])

    def search_multimodal(self, text_query: str, image=None,
                          text_weight=0.5, image_weight=0.5,
                          top_k=50) -> List[SearchResult]:
        """
        Multi-modal search combining text and visual signals.
        """
        results_lists = []

        # 1. Text retrieval (always)
        text_embedding = self.clip.encode_text(text_query)
        text_results = self.search_text_only(text_query, top_k=1000)
        results_lists.append(text_results)

        # 2. Visual retrieval via text embedding in CLIP space
        visual_from_text = self.search_visual(text_embedding, top_k=1000)
        results_lists.append(visual_from_text)

        # 3. If reference image provided, also search by image embedding
        if image is not None:
            image_embedding = self.clip.encode_image(image)
            # Interpolate text and image embeddings
            combined_embedding = (text_weight * text_embedding +
                                  image_weight * image_embedding)
            combined_embedding /= np.linalg.norm(combined_embedding)
            visual_from_combined = self.search_visual(combined_embedding, top_k=1000)
            results_lists.append(visual_from_combined)

        # 4. Fuse all result lists
        fused = self.reciprocal_rank_fusion(results_lists)

        # 5. Re-rank top candidates with cross-encoder
        top_candidates = fused[:200]
        reranked = self.cross_encoder_rerank(text_query, image, top_candidates)

        return reranked[:top_k]

    def cross_encoder_rerank(self, query_text, query_image,
                             candidates: List) -> List:
        """Re-rank using full CLIP similarity with original resolution."""
        candidate_ids = [c[0] for c in candidates]
        candidate_embeddings = self.milvus.get_vectors(candidate_ids)

        # Compute precise similarity
        query_emb = self.clip.encode_text(query_text)
        similarities = np.dot(candidate_embeddings, query_emb.T).flatten()

        # Combine with original fusion score
        reranked = []
        for i, (doc_id, fusion_score) in enumerate(candidates):
            final_score = 0.7 * similarities[i] + 0.3 * fusion_score
            reranked.append((doc_id, final_score))

        return sorted(reranked, key=lambda x: -x[1])
```

### 7.3 Diversity Injection (MMR)
```python
def maximal_marginal_relevance(query_emb, doc_embs, doc_scores,
                                lambda_param=0.7, top_k=20):
    """
    MMR: Balances relevance with diversity to avoid near-duplicate results.
    MMR(d) = λ * Sim(q, d) - (1-λ) * max(Sim(d, d_selected))
    """
    selected = []
    remaining = list(range(len(doc_scores)))

    for _ in range(top_k):
        best_idx = None
        best_mmr = -float('inf')

        for idx in remaining:
            relevance = doc_scores[idx]

            # Max similarity to already selected docs
            if selected:
                selected_embs = doc_embs[selected]
                max_sim = np.max(np.dot(selected_embs, doc_embs[idx]))
            else:
                max_sim = 0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    return selected
```

---

## 8. Deep Dive: Efficient ANN at Scale (10B vectors)

### 8.1 Sharding Strategy
```
┌─────────────────────────────────────────────────────────────────┐
│                    ANN SEARCH CLUSTER                             │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Shard 0    │  │  Shard 1    │  │  Shard N    │             │
│  │  IVF-PQ    │  │  IVF-PQ    │  │  IVF-PQ    │   ...        │
│  │  500M vecs │  │  500M vecs │  │  500M vecs │             │
│  │  (3 replicas)│  │  (3 replicas)│  │  (3 replicas)│         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                 │                 │                     │
│         └────────────┬────┴────────────────┘                     │
│                      ▼                                           │
│              [Scatter-Gather Coordinator]                         │
│              - Fan out query to all shards                        │
│              - Merge top-K from each shard                        │
│              - Return global top-K                                │
└─────────────────────────────────────────────────────────────────┘

Sharding approach: Hash-based (image_id % num_shards)
  - 10B vectors / 500M per shard = 20 shards
  - Each shard: ~500 GB with IVF-PQ (highly compressed)
  - Actual memory per shard: ~30 GB (PQ codes only)
  - Total cluster memory: 20 shards × 3 replicas × 30 GB = 1.8 TB
```

### 8.2 Product Quantization Detail
```python
class ProductQuantizationExplained:
    """
    PQ compresses 512-dim float32 vector (2048 bytes)
    into 64 bytes (64 sub-vectors × 8-bit codes).
    Compression ratio: 32x
    
    Memory for 10B vectors:
    - Raw: 10B × 2048 bytes = 20 TB
    - PQ-compressed: 10B × 64 bytes = 640 GB
    - With IVF centroids + metadata: ~800 GB total
    """

    def encode(self, vector: np.ndarray) -> np.ndarray:
        """Encode 512-d vector into 64 PQ codes."""
        # Split into 64 sub-vectors of 8 dimensions each
        sub_vectors = vector.reshape(64, 8)
        codes = np.zeros(64, dtype=np.uint8)

        for i, sub_vec in enumerate(sub_vectors):
            # Find nearest centroid in sub-codebook i
            distances = np.linalg.norm(
                self.codebooks[i] - sub_vec, axis=1
            )
            codes[i] = np.argmin(distances)

        return codes  # 64 bytes total

    def asymmetric_distance(self, query: np.ndarray, pq_code: np.ndarray) -> float:
        """
        ADC: Compute approximate distance without decoding.
        Precompute distance tables for speed.
        """
        sub_queries = query.reshape(64, 8)
        distance = 0.0
        for i in range(64):
            # Lookup precomputed distance
            distance += self.distance_tables[i][pq_code[i]]
        return distance
```

### 8.3 Scatter-Gather Search
```python
class DistributedANNSearch:
    """Distributed search across sharded vector index."""

    def __init__(self, shard_clients: List[ShardClient], num_shards=20):
        self.shards = shard_clients
        self.num_shards = num_shards

    async def search(self, query_vector: np.ndarray, top_k=1000,
                     timeout_ms=150) -> List[Tuple[int, float]]:
        """
        Scatter query to all shards, gather and merge results.
        Timeout budget: 150ms for ANN portion.
        """
        # Fan out to all shards concurrently
        tasks = []
        for shard in self.shards:
            task = asyncio.create_task(
                shard.search(query_vector, top_k=top_k // 2, nprobe=64)
            )
            tasks.append(task)

        # Gather with timeout
        done, pending = await asyncio.wait(
            tasks, timeout=timeout_ms / 1000,
            return_when=asyncio.ALL_COMPLETED
        )

        # Cancel timed-out shards (graceful degradation)
        for task in pending:
            task.cancel()

        # Merge results from completed shards
        all_results = []
        for task in done:
            try:
                shard_results = task.result()
                all_results.extend(shard_results)
            except Exception:
                continue  # Skip failed shards

        # Global top-K selection
        all_results.sort(key=lambda x: -x[1])
        return all_results[:top_k]

    async def search_with_routing(self, query_vector: np.ndarray,
                                   cluster_hint: int = None,
                                   top_k=1000) -> List:
        """
        Optimized: If we know the query's cluster, route to fewer shards.
        Uses coarse quantizer to identify relevant shards.
        """
        if cluster_hint is not None:
            # Route to shards containing this cluster's vectors
            relevant_shards = self.cluster_to_shard_map[cluster_hint]
            shards_to_query = [self.shards[i] for i in relevant_shards]
        else:
            shards_to_query = self.shards

        return await self._scatter_gather(shards_to_query, query_vector, top_k)
```

---

## 9. Component Optimization

### 9.1 GPU Cluster for Embedding
```
GPU Fleet Configuration:
- Query embedding: 200× NVIDIA A100 (40GB)
  - Batch size: 32 queries per GPU
  - Throughput: ~3200 queries/sec per GPU → handles 100K QPS
  - Model: CLIP ViT-L/14 (half precision)

- Index building: 50× NVIDIA A100
  - Batch size: 256 images per GPU
  - Throughput: 5000 images/sec per GPU
  - Daily capacity: 50 × 5000 × 86400 = 21.6B images/day

- Auto-scaling based on QPS with 30s warm-up
- Model served via Triton Inference Server
- TensorRT optimization: 2x throughput vs PyTorch
```

### 9.2 Redis Query Cache
```
Cache Strategy:
- Key: SHA256(normalized_query + filters)
- Value: serialized top-50 results
- TTL: 1 hour for popular queries, 5 min for others
- Cache hit rate target: 40% (power-law query distribution)

Memory: 10M cached queries × 5 KB avg = 50 GB Redis cluster
Benefit: Saves ~40K QPS from hitting retrieval layer
```

### 9.3 Kafka Crawl Pipeline
```
Topics:
- crawl.urls.discovered (partitions: 256)
- crawl.images.downloaded (partitions: 128)
- crawl.images.processed (partitions: 64)
- index.embeddings.computed (partitions: 64)
- index.updates.batch (partitions: 32)

Consumer groups:
- image-downloader (128 consumers)
- embedding-generator (64 consumers, GPU-backed)
- index-updater (32 consumers)
- safe-search-classifier (32 consumers)

Retention: 7 days
Throughput: 10M images/day = ~115 images/sec sustained
```

---

## 10. Observability

### 10.1 Key Metrics
```yaml
# Search Quality
- ndcg@10: target > 0.75
- click_through_rate: track per query type
- zero_result_rate: target < 2%
- abandonment_rate: target < 15%

# Latency Breakdown (p99 budget = 200ms)
- query_understanding: 10ms
- embedding_generation: 15ms (GPU)
- text_retrieval: 30ms
- vector_retrieval: 40ms
- fusion_reranking: 50ms
- result_assembly: 20ms
- network_overhead: 35ms
- TOTAL: 200ms

# Infrastructure
- gpu_utilization: target 70-85%
- cache_hit_rate: target > 40%
- index_freshness_lag: target < 1 hour
- shard_balance: max_shard_size / avg_shard_size < 1.2
```

### 10.2 Alerting Rules
```yaml
alerts:
  - name: search_latency_high
    condition: p99_latency > 300ms for 5 minutes
    severity: critical
    action: page_oncall

  - name: embedding_gpu_saturation
    condition: gpu_queue_depth > 1000 for 2 minutes
    severity: warning
    action: auto_scale_gpu_fleet

  - name: index_stale
    condition: newest_indexed_image_age > 2 hours
    severity: warning
    action: check_kafka_pipeline

  - name: vector_search_degraded
    condition: shards_responding < 18/20
    severity: critical
    action: failover_to_replicas
```

---

## 11. Trade-off Analysis

| Decision | Option A | Option B | Choice | Rationale |
|----------|----------|----------|--------|-----------|
| Embedding model | ResNet-50 (2048-d) | CLIP ViT-L/14 (512-d) | CLIP | Joint text-image space enables multi-modal |
| ANN algorithm | HNSW (graph) | IVF-PQ (quantization) | IVF-PQ + HNSW hybrid | PQ for cold, HNSW for hot 100M |
| Sharding | Hash-based | Cluster-based | Hash-based | Even distribution, simpler operations |
| Fusion method | Linear combination | RRF | RRF | Score-agnostic, no normalization needed |
| Storage | All in memory | Disk-backed with cache | Disk + memory cache | 10B vectors too large for pure memory |
| Text index | Solr | Elasticsearch | Elasticsearch | Better ecosystem, scale proven |
| Re-ranking | None | Cross-encoder top-200 | Cross-encoder | +8% NDCG for acceptable 50ms cost |

### Key Design Decisions

1. **CLIP over separate models**: Single model for both text and images in shared space eliminates the need for separate text-to-image mapping.

2. **IVF-PQ over pure HNSW**: At 10B scale, HNSW requires ~500 bytes/vector for graph links alone (5 TB). IVF-PQ compresses to 64 bytes/vector (640 GB).

3. **Two-stage retrieval**: Coarse ANN (1000 candidates) + precise re-ranking achieves better recall than single-stage with same latency budget.

4. **Hybrid text+visual**: Pure visual search misses semantic concepts not visually obvious. Pure text misses visual attributes hard to describe.

---

## 12. Failure Modes & Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| GPU cluster down | No new embeddings for queries | Pre-computed embedding cache for popular queries |
| Vector DB shard loss | Partial results | 3x replication, serve from replicas |
| ES cluster degraded | Text retrieval slow/down | Fall back to vector-only search |
| Image upload spike | Embedding queue overflow | Rate limit uploads, async processing |
| Cache stampede | Backend overload on cache miss | Probabilistic early expiration |
| Model drift | Quality degradation over time | A/B test new models, gradual rollout |

---

## 13. Evolution Path

```
Phase 1 (MVP): Text search + basic reverse image search (1B images)
Phase 2: Multi-modal search, CLIP integration, 5B images
Phase 3: Real-time personalization, 10B images, video frame search
Phase 4: Generative search (text-to-image generation as fallback)
```

---

## 12. Sequence Diagrams

### 12.1 Image Upload + Embedding Generation

```mermaid
sequenceDiagram
    participant User
    participant API as API Gateway
    participant Upload as Upload Service
    participant S3 as Object Storage (S3)
    participant Queue as Processing Queue (SQS)
    participant Embed as Embedding Service (GPU)
    participant Model as CLIP/ViT Model
    participant VecDB as Vector DB (Milvus/Pinecone)
    participant MetaDB as Metadata DB (PostgreSQL)

    User->>API: POST /images/upload {image_file, tags, description}
    API->>Upload: Process upload
    Upload->>S3: Store original image + generate thumbnails
    S3-->>Upload: image_url, thumbnail_urls
    Upload->>MetaDB: INSERT image record (id, url, tags, user_id)
    Upload->>Queue: Enqueue embedding job {image_id, s3_path}
    Upload-->>User: 202 Accepted {image_id, status: "processing"}

    Queue->>Embed: Dequeue job
    Embed->>S3: Download image
    S3-->>Embed: Image bytes
    Embed->>Embed: Preprocess: resize 224×224, normalize
    Embed->>Model: Forward pass through vision encoder
    Model-->>Embed: 512-dim embedding vector
    Embed->>VecDB: Upsert(image_id, vector, metadata_filter_fields)
    Embed->>MetaDB: UPDATE images SET embedding_status='ready' WHERE id=image_id
    
    Note over VecDB: Image is now searchable by visual similarity
```

### 12.2 Visual Similarity Search

```mermaid
sequenceDiagram
    participant User
    participant API as API Gateway
    participant Search as Search Service
    participant Model as CLIP Model (GPU)
    participant VecDB as Vector DB (HNSW Index)
    participant MetaDB as Metadata DB
    participant Rank as Re-ranker
    participant Cache as Result Cache

    alt Text-to-Image Search
        User->>API: GET /search?q="red sports car on mountain road"
        API->>Search: textSearch(query)
        Search->>Model: Encode text → 512-dim vector (CLIP text encoder)
        Model-->>Search: query_vector
    else Reverse Image Search
        User->>API: POST /search/reverse {image_file}
        API->>Search: reverseSearch(image)
        Search->>Model: Encode image → 512-dim vector (CLIP image encoder)
        Model-->>Search: query_vector
    end
    
    Search->>Cache: Check (vector_hash + filters)
    alt Cache Miss
        Search->>VecDB: ANN search(query_vector, k=100, filters={license: "free"})
        Note over VecDB: HNSW graph traversal: O(log n) with ef_search=128
        VecDB-->>Search: Top-100 results with distances
        Search->>MetaDB: Batch fetch metadata for 100 results
        MetaDB-->>Search: Titles, URLs, dimensions, tags
        Search->>Rank: Re-rank by relevance + quality + freshness
        Rank-->>Search: Final top-20
        Search->>Cache: Store (TTL=10min)
    end
    Search-->>API: Results with thumbnails + similarity scores
    API-->>User: {results: [{image_url, similarity: 0.92, ...}, ...]}
```

---

## 13. Deep Dive: Visual Embedding & ANN Search

### 13.1 CLIP Embedding Pipeline

```
CLIP (Contrastive Language-Image Pre-training):
- Jointly trains image encoder + text encoder
- Same embedding space: text and images are directly comparable
- cosine_similarity(encode_image(cat_photo), encode_text("a photo of a cat")) ≈ 0.85

Image Encoder (ViT-L/14):
  Input: 224×224 RGB image
  → Patch embedding (14×14 patches = 256 tokens)
  → 24 transformer layers
  → Output: 768-dim → projection to 512-dim

Text Encoder:
  Input: tokenized text (max 77 tokens)
  → 12 transformer layers  
  → Output: 512-dim (same space as image)

Why CLIP is powerful for search:
- "Red car" query finds red cars even if no text metadata says "red car"
- Cross-modal: search images with text, or find similar images
```

### 13.2 HNSW (Hierarchical Navigable Small World) for ANN

```
Structure: Multi-layer graph where each layer is a "small world" network

Layer 2 (sparse, long-range links):     ●─────────────────●
                                         │                 │
Layer 1 (medium density):        ●───●───●───●─────●──────●───●
                                 │   │   │   │     │      │   │
Layer 0 (all points, short links): ●●●●●●●●●●●●●●●●●●●●●●●●●●●

Search algorithm (greedy):
1. Enter at top layer, find nearest node using few long-range links
2. Drop to next layer, use current best as starting point
3. At layer 0, do fine-grained local search

Time complexity: O(log n) average for k-NN query
Build complexity: O(n log n)
Space: O(n × M) where M = max connections per node (typically 16-64)

Tuning parameters:
- M (max connections): 16 (low memory) to 64 (high recall)
- ef_construction: 200 (build quality, higher = better graph)
- ef_search: 128 (query quality, higher = better recall, slower)

At 10B images: recall@10 ≈ 0.95, query time ≈ 5ms (with quantization)
```
