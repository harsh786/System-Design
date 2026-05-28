# Amazon Product Search System Design

## 1. Problem Statement

Design Amazon's product search system that enables users to find products among 350+ million items using text queries, filters, and faceted navigation. The system must understand user intent, handle structured product data, rank results by relevance and purchase likelihood, and deliver personalized results within 200ms.

---

## 2. Functional Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| FR1 | Text Search | Full-text search across product titles, descriptions, features |
| FR2 | Faceted Filtering | Filter by category, price range, brand, rating, Prime eligible |
| FR3 | Spell Correction | Handle misspellings and suggest corrections |
| FR4 | Query Understanding | Intent classification, NER for brand/product type extraction |
| FR5 | Relevance Ranking | Rank by relevance, popularity, purchase probability |
| FR6 | Personalization | Personalize results based on user purchase/browse history |
| FR7 | Autocomplete | Real-time suggestions with product thumbnails |
| FR8 | Sort Options | Sort by relevance, price, rating, newest, best sellers |
| FR9 | Sponsored Products | Integrate paid placements with organic results |
| FR10 | Visual Search | Search by image (find similar products) |

## 3. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Latency | p50 < 100ms, p99 < 300ms |
| NFR2 | Availability | 99.99% uptime |
| NFR3 | Throughput | 50K QPS sustained, 150K QPS peak (Black Friday) |
| NFR4 | Freshness | New products searchable within 5 minutes |
| NFR5 | Scalability | 350M+ products, growing 10M/month |
| NFR6 | Accuracy | Conversion rate optimization (relevant = purchased) |
| NFR7 | Global | Serve 20+ country-specific catalogs |

---

## 4. Capacity Estimation

### Traffic
```
Daily searches:            1.5 billion
Searches per second:       1.5B / 86400 ≈ 17,400 QPS
Peak (Black Friday, 8x):  ~140,000 QPS
Average query length:      3 words ≈ 20 bytes
Filters per query:         2-3 average
Results per page:          48 products
Pages viewed per search:   1.5 average
```

### Storage
```
Total products:            350 million
Product document size:     5KB average (title, description, attributes, images)
Product index:             350M × 5KB = 1.75 TB (document store)
Inverted index:            ~500 GB (terms → posting lists)
Vector embeddings:         350M × 768 dims × 4 bytes = 1 TB
Product images metadata:   350M × 10 images × 200 bytes = 700 GB
User profiles:             500M users × 2KB = 1 TB
Query logs:                10B queries/week × 200 bytes = 2 TB/week
```

### Bandwidth
```
Inbound (queries):         50K × 200 bytes = 10 MB/s
Outbound (results):        50K × 48 products × 500 bytes = 1.2 GB/s
Image thumbnails:          Served from CDN (not counted here)
```

### Infrastructure
```
Search cluster:            ~200 nodes (Elasticsearch-like)
Index shards:              1000 primary shards
Replicas:                  2 replicas per shard → 3000 total shards
ML inference:              50 GPU nodes for vector search + LTR
Redis (caching):           100 nodes, 10TB total
```

---

## 5. Data Modeling

### Product Document (Elasticsearch)
```json
{
    "product_id": "B09V3KXJPB",
    "title": "Apple AirPods Pro (2nd Generation) Wireless Earbuds",
    "brand": "Apple",
    "category_path": ["Electronics", "Headphones", "In-Ear"],
    "category_id": "electronics_headphones_inear",
    "description": "Active Noise Cancellation, Transparency mode...",
    "bullet_points": [
        "Next-level Active Noise Cancellation",
        "Adaptive Transparency",
        "Personalized Spatial Audio"
    ],
    "price": {
        "current": 189.99,
        "original": 249.99,
        "currency": "USD",
        "deal_type": "lightning_deal"
    },
    "rating": {
        "average": 4.7,
        "count": 128453,
        "distribution": [95234, 18765, 8234, 3120, 3100]
    },
    "attributes": {
        "color": ["White"],
        "connectivity": "Bluetooth 5.3",
        "battery_life": "6 hours",
        "weight": "5.3g per earbud",
        "noise_cancellation": true,
        "water_resistant": "IPX4"
    },
    "availability": {
        "in_stock": true,
        "prime_eligible": true,
        "delivery_days": 1,
        "seller": "Amazon.com",
        "fulfilled_by": "Amazon"
    },
    "sales_metrics": {
        "sales_rank": 3,
        "sales_velocity_7d": 45000,
        "conversion_rate": 0.12,
        "add_to_cart_rate": 0.25
    },
    "images": [
        {"url": "https://...", "type": "main", "alt": "AirPods Pro front"},
        {"url": "https://...", "type": "back", "alt": "AirPods Pro case"}
    ],
    "embedding_vector": [0.123, -0.456, ...],  // 768-dim BERT embedding
    "created_at": "2023-09-12",
    "updated_at": "2024-01-15",
    "marketplace": "US",
    "language": "en"
}
```

### Elasticsearch Index Mapping
```json
{
    "mappings": {
        "properties": {
            "title": {
                "type": "text",
                "analyzer": "product_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "autocomplete": {"type": "text", "analyzer": "autocomplete_analyzer"}
                }
            },
            "brand": {
                "type": "keyword",
                "fields": {"text": {"type": "text"}}
            },
            "category_path": {"type": "keyword"},
            "price.current": {"type": "float"},
            "rating.average": {"type": "float"},
            "rating.count": {"type": "integer"},
            "attributes": {"type": "object", "dynamic": true},
            "availability.prime_eligible": {"type": "boolean"},
            "availability.in_stock": {"type": "boolean"},
            "sales_metrics.sales_rank": {"type": "integer"},
            "embedding_vector": {
                "type": "dense_vector",
                "dims": 768,
                "index": true,
                "similarity": "cosine"
            },
            "created_at": {"type": "date"},
            "marketplace": {"type": "keyword"}
        }
    },
    "settings": {
        "number_of_shards": 1000,
        "number_of_replicas": 2,
        "analysis": {
            "analyzer": {
                "product_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "synonym_filter", "stemmer"]
                },
                "autocomplete_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "edge_ngram_filter"]
                }
            },
            "filter": {
                "synonym_filter": {
                    "type": "synonym",
                    "synonyms_path": "synonyms.txt"
                },
                "edge_ngram_filter": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20
                }
            }
        }
    }
}
```

### User Profile (for Personalization)
```sql
CREATE TABLE user_profiles (
    user_id          BIGINT PRIMARY KEY,
    preferred_brands JSONB,                  -- {"Apple": 0.8, "Samsung": 0.6}
    price_sensitivity FLOAT,                 -- 0 (low) to 1 (high)
    category_affinity JSONB,                 -- {"electronics": 0.9, "books": 0.3}
    recent_searches  JSONB,                  -- Last 50 queries with timestamps
    recent_views     JSONB,                  -- Last 100 viewed product_ids
    purchase_history JSONB,                  -- Last 200 purchased product_ids
    updated_at       TIMESTAMP
);
```

---

## 6. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AMAZON PRODUCT SEARCH ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │  User/App    │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  CloudFront  │── Static assets, thumbnails
                         │  CDN + ALB   │
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   Search API Gateway   │
                    │   (Rate Limit, Auth)   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Query Understanding  │
                    │   Service              │
                    │  ┌─────┐ ┌─────┐     │
                    │  │ NER │ │Intent│     │
                    │  └─────┘ └─────┘     │
                    └───────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
   ┌──────▼──────┐     ┌───────▼───────┐     ┌──────▼──────┐
   │  Inverted   │     │   Vector      │     │  Sponsored  │
   │  Index      │     │   Search      │     │  Products   │
   │  (BM25)     │     │   (ANN/HNSW)  │     │  (Ad Auction│
   └──────┬──────┘     └───────┬───────┘     └──────┬──────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Merge & Re-rank     │
                    │   (Learning-to-Rank)  │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Personalization     │
                    │   Layer              │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Response Assembly   │
                    │   (Facets, Filters)   │
                    └───────────────────────┘

═══════════════════ OFFLINE / NEAR-REAL-TIME PIPELINE ═══════════════

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Product    │────▶│  Indexing    │────▶│  Search     │
│  Catalog    │     │  Pipeline   │     │  Index      │
│  (DynamoDB) │     │  (Kafka +   │     │  (ES/       │
└─────────────┘     │   Spark)    │     │   OpenSearch)│
                    └─────────────┘     └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Click/Buy  │────▶│  Feature    │────▶│  LTR Model  │
│  Logs       │     │  Engineering│     │  Training   │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## 7. Low-Level Design (LLD) - APIs

### Search API
```
GET /v1/search?q={query}&category={cat}&brand={brand}&price_min={min}&price_max={max}
    &rating={min_rating}&prime={true|false}&sort={relevance|price_asc|price_desc|rating|newest}
    &page={page}&page_size={size}

Headers:
  X-User-Id: <user_id>
  X-Session-Id: <session>
  X-Marketplace: US
  X-Device: mobile|desktop

Response 200:
{
    "query": "wireless earbuds",
    "corrected_query": null,
    "query_intent": {
        "category": "Electronics > Headphones > In-Ear",
        "product_type": "earbuds",
        "attributes": {"connectivity": "wireless"}
    },
    "total_results": 45892,
    "page": 1,
    "results": [
        {
            "product_id": "B09V3KXJPB",
            "title": "Apple AirPods Pro (2nd Generation)",
            "brand": "Apple",
            "price": {"current": 189.99, "original": 249.99},
            "rating": {"average": 4.7, "count": 128453},
            "image_url": "https://images-na.ssl-images-amazon.com/...",
            "prime": true,
            "delivery": "Tomorrow",
            "badge": "Best Seller",
            "sponsored": false,
            "relevance_score": 0.97
        }
    ],
    "facets": {
        "brand": [
            {"value": "Apple", "count": 234, "selected": false},
            {"value": "Samsung", "count": 189, "selected": false},
            {"value": "Sony", "count": 156, "selected": false}
        ],
        "price_range": [
            {"min": 0, "max": 25, "count": 5423},
            {"min": 25, "max": 50, "count": 8934},
            {"min": 50, "max": 100, "count": 12045},
            {"min": 100, "max": 200, "count": 9876},
            {"min": 200, "max": null, "count": 9614}
        ],
        "rating": [
            {"min": 4, "count": 23456},
            {"min": 3, "count": 34567}
        ],
        "features": [
            {"value": "Noise Cancelling", "count": 8923},
            {"value": "Waterproof", "count": 6734}
        ]
    },
    "related_searches": ["airpods pro", "noise cancelling earbuds"],
    "sponsored_banner": {...}
}
```

### Autocomplete API
```
GET /v1/suggest?q={prefix}&category={cat}&marketplace=US

Response 200:
{
    "suggestions": [
        {
            "text": "wireless earbuds",
            "type": "query",
            "category": "Electronics",
            "result_count": 45892
        },
        {
            "text": "wireless earbuds for iphone",
            "type": "query",
            "category": "Electronics",
            "result_count": 12345
        },
        {
            "text": "Apple AirPods Pro",
            "type": "product",
            "product_id": "B09V3KXJPB",
            "image_url": "https://...",
            "price": 189.99
        }
    ]
}
```

---

## 8. Deep Dive: Hybrid Retrieval (Inverted Index + Vector Search)

```python
import numpy as np
from dataclasses import dataclass


@dataclass
class SearchResult:
    product_id: str
    score: float
    source: str  # "lexical", "semantic", or "hybrid"


class HybridRetriever:
    """
    Combines lexical (BM25) and semantic (vector) search for product retrieval.
    
    Why hybrid?
    - Lexical: Exact matches for brand names, model numbers, SKUs
    - Semantic: Handles synonyms, intent ("noise cancelling" → "ANC")
    
    Fusion strategy: Reciprocal Rank Fusion (RRF)
    """
    
    def __init__(self, es_client, vector_index, embedding_model):
        self.es = es_client
        self.vector_index = vector_index  # FAISS/HNSW index
        self.embedding_model = embedding_model
        
        # Fusion parameters
        self.rrf_k = 60  # RRF constant
        self.lexical_weight = 0.6
        self.semantic_weight = 0.4
    
    def search(self, query: str, filters: dict, top_k: int = 1000) -> list[SearchResult]:
        """
        Hybrid search pipeline:
        1. Lexical retrieval (Elasticsearch BM25)
        2. Semantic retrieval (ANN vector search)
        3. Fusion using Reciprocal Rank Fusion
        """
        # Phase 1: Lexical search
        lexical_results = self._lexical_search(query, filters, top_k)
        
        # Phase 2: Semantic search
        query_embedding = self.embedding_model.encode(query)
        semantic_results = self._semantic_search(query_embedding, filters, top_k)
        
        # Phase 3: Reciprocal Rank Fusion
        fused = self._rrf_fusion(lexical_results, semantic_results)
        
        return fused[:top_k]
    
    def _lexical_search(self, query: str, filters: dict, top_k: int) -> list[SearchResult]:
        """
        Elasticsearch BM25 search with field boosting.
        Title matches weighted 3x, brand 2x, description 1x.
        """
        es_query = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "title^3",
                                "title.keyword^5",  # Exact title match
                                "brand^2",
                                "bullet_points^1.5",
                                "description",
                                "attributes.*"
                            ],
                            "type": "best_fields",
                            "tie_breaker": 0.3
                        }
                    }
                ],
                "filter": self._build_filters(filters)
            }
        }
        
        # Add function score for popularity boost
        function_score_query = {
            "function_score": {
                "query": es_query,
                "functions": [
                    {
                        "field_value_factor": {
                            "field": "sales_metrics.sales_velocity_7d",
                            "modifier": "log1p",
                            "factor": 0.1
                        }
                    },
                    {
                        "field_value_factor": {
                            "field": "rating.average",
                            "modifier": "none",
                            "factor": 0.05
                        }
                    }
                ],
                "score_mode": "sum",
                "boost_mode": "sum"
            }
        }
        
        response = self.es.search(index="products", body={
            "query": function_score_query,
            "size": top_k
        })
        
        return [
            SearchResult(
                product_id=hit['_id'],
                score=hit['_score'],
                source="lexical"
            )
            for hit in response['hits']['hits']
        ]
    
    def _semantic_search(self, query_vector: np.ndarray, 
                        filters: dict, top_k: int) -> list[SearchResult]:
        """
        Approximate Nearest Neighbor search using HNSW index.
        
        HNSW (Hierarchical Navigable Small World) properties:
        - Build time: O(n log n)
        - Query time: O(log n)
        - Recall@10: > 0.95 with ef_search=200
        """
        # Search vector index
        # In production: OpenSearch k-NN or dedicated FAISS serving
        distances, indices = self.vector_index.search(
            query_vector.reshape(1, -1), 
            top_k * 2  # Over-fetch for post-filtering
        )
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                break
            product_id = self.index_to_product_id[idx]
            # Convert L2 distance to similarity score
            score = 1.0 / (1.0 + dist)
            results.append(SearchResult(product_id=product_id, score=score, source="semantic"))
        
        # Post-filter (apply filters that couldn't be applied in ANN)
        results = self._post_filter(results, filters)
        
        return results[:top_k]
    
    def _rrf_fusion(self, lexical: list[SearchResult], 
                   semantic: list[SearchResult]) -> list[SearchResult]:
        """
        Reciprocal Rank Fusion (RRF):
        RRF_score(d) = Σ 1/(k + rank_i(d))
        
        Where k=60 (constant), rank_i is the rank in system i.
        
        Benefits over linear combination:
        - No need to normalize scores across different systems
        - Robust to outliers
        - Works well empirically
        """
        scores = {}
        
        # Add lexical contributions
        for rank, result in enumerate(lexical):
            rrf_score = self.lexical_weight / (self.rrf_k + rank + 1)
            scores[result.product_id] = scores.get(result.product_id, 0) + rrf_score
        
        # Add semantic contributions
        for rank, result in enumerate(semantic):
            rrf_score = self.semantic_weight / (self.rrf_k + rank + 1)
            scores[result.product_id] = scores.get(result.product_id, 0) + rrf_score
        
        # Sort by fused score
        fused = [
            SearchResult(product_id=pid, score=score, source="hybrid")
            for pid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return fused
    
    def _build_filters(self, filters: dict) -> list:
        """Convert user filters to Elasticsearch filter clauses"""
        es_filters = []
        
        if 'category' in filters:
            es_filters.append({"term": {"category_path": filters['category']}})
        
        if 'brand' in filters:
            es_filters.append({"terms": {"brand": filters['brand']}})
        
        if 'price_min' in filters or 'price_max' in filters:
            price_range = {}
            if 'price_min' in filters:
                price_range['gte'] = filters['price_min']
            if 'price_max' in filters:
                price_range['lte'] = filters['price_max']
            es_filters.append({"range": {"price.current": price_range}})
        
        if 'rating' in filters:
            es_filters.append({"range": {"rating.average": {"gte": filters['rating']}}})
        
        if filters.get('prime'):
            es_filters.append({"term": {"availability.prime_eligible": True}})
        
        # Always filter to in-stock
        es_filters.append({"term": {"availability.in_stock": True}})
        
        return es_filters
```

---

## 9. Deep Dive: Learning-to-Rank (LambdaMART)

```python
import numpy as np
from typing import List, Dict


class LearningToRank:
    """
    LambdaMART-based re-ranking for product search.
    
    LambdaMART = Lambda (pairwise loss) + MART (gradient boosted trees)
    
    Training data: Click logs with relevance labels
    - Purchased after search = relevance 4 (high)
    - Added to cart = relevance 3
    - Clicked with dwell > 30s = relevance 2
    - Clicked with dwell < 10s = relevance 1
    - Impression but no click = relevance 0
    
    Features: ~300 features across query, document, and query-document interaction
    """
    
    FEATURE_GROUPS = {
        'query_features': [
            'query_length',              # Number of tokens
            'query_frequency',           # How often this query is searched
            'query_intent_score',        # P(transactional intent)
            'query_specificity',         # General ("shoes") vs specific ("nike air max 90 white size 10")
            'has_brand_in_query',        # Boolean
            'has_model_in_query',        # Boolean
        ],
        'document_features': [
            'price',                     # Current price
            'price_relative_to_category', # Price percentile in category
            'rating_average',            # 1-5 star rating
            'rating_count',              # Number of reviews
            'rating_recency',            # Average age of recent reviews
            'sales_rank',                # Best sellers rank
            'sales_velocity_7d',         # Units sold last 7 days
            'conversion_rate',           # Historical CVR
            'return_rate',               # Product return rate
            'prime_eligible',            # Boolean
            'delivery_speed',            # Days to deliver
            'fulfilled_by_amazon',       # Boolean
            'image_count',               # Number of images
            'bullet_point_count',        # Number of features listed
            'description_length',        # Word count of description
            'product_age_days',          # Days since listing
            'brand_authority',           # Brand-level trust score
            'seller_rating',             # Seller performance
            'stock_level',               # Inventory status
        ],
        'query_document_features': [
            'bm25_title',                # BM25 score for title field
            'bm25_description',          # BM25 for description
            'bm25_brand',               # BM25 for brand field
            'bm25_bullets',             # BM25 for bullet points
            'exact_title_match',         # Query is substring of title
            'exact_brand_match',         # Query matches brand
            'category_match',            # Product in predicted category
            'semantic_similarity',       # Cosine similarity of embeddings
            'query_term_coverage',       # Fraction of query terms in title
            'title_term_coverage',       # Fraction of title terms matching query
        ],
        'personalization_features': [
            'user_brand_affinity',       # User's preference for this brand
            'user_category_affinity',    # User's preference for this category
            'user_price_match',          # How well price matches user's range
            'previously_viewed',         # User has viewed this product
            'previously_purchased',      # User has bought this product
            'similar_to_purchased',      # Cosine sim to past purchases
        ],
        'context_features': [
            'time_of_day',              # Hour (affects purchase patterns)
            'day_of_week',              # Weekend vs weekday
            'is_holiday_season',        # Near major shopping events
            'device_type',              # Mobile vs desktop
        ]
    }
    
    def __init__(self, model_path: str):
        """Load trained LambdaMART model (e.g., XGBoost/LightGBM)"""
        import lightgbm as lgb
        self.model = lgb.Booster(model_file=model_path)
        self.feature_names = self._get_all_features()
    
    def rerank(self, query: str, candidates: list, user_context: dict) -> list:
        """
        Re-rank candidates using LambdaMART model.
        
        Input: ~1000 candidates from retrieval stage
        Output: Ordered by predicted relevance/purchase probability
        """
        # Extract features for all candidates
        feature_matrix = self._extract_features(query, candidates, user_context)
        
        # Predict relevance scores
        scores = self.model.predict(feature_matrix)
        
        # Sort by predicted score
        ranked_indices = np.argsort(scores)[::-1]
        
        return [candidates[i] for i in ranked_indices]
    
    def _extract_features(self, query: str, candidates: list, 
                         user_context: dict) -> np.ndarray:
        """Extract feature matrix for all query-document pairs"""
        features = np.zeros((len(candidates), len(self.feature_names)))
        
        query_features = self._compute_query_features(query)
        
        for i, product in enumerate(candidates):
            # Query features (same for all candidates)
            features[i, :len(query_features)] = query_features
            
            # Document features
            doc_features = self._compute_doc_features(product)
            offset = len(query_features)
            features[i, offset:offset + len(doc_features)] = doc_features
            
            # Query-document interaction features
            qd_features = self._compute_qd_features(query, product)
            offset += len(doc_features)
            features[i, offset:offset + len(qd_features)] = qd_features
            
            # Personalization features
            personal = self._compute_personal_features(product, user_context)
            offset += len(qd_features)
            features[i, offset:offset + len(personal)] = personal
        
        return features
    
    def _compute_query_features(self, query: str) -> list:
        tokens = query.split()
        return [
            len(tokens),                          # query_length
            self.query_freq_lookup.get(query, 0), # query_frequency
            self.intent_classifier.predict(query), # query_intent_score
            1.0 / len(tokens) if tokens else 0,   # query_specificity (inverse length as proxy)
            float(self._has_brand(query)),         # has_brand_in_query
            float(self._has_model(query)),         # has_model_in_query
        ]
    
    def train_model(self, train_data: str, valid_data: str):
        """
        Train LambdaMART using LightGBM.
        
        Objective: lambdarank (optimizes NDCG directly)
        """
        import lightgbm as lgb
        
        params = {
            'objective': 'lambdarank',
            'metric': 'ndcg',
            'eval_at': [5, 10, 20],
            'num_leaves': 255,
            'learning_rate': 0.05,
            'min_data_in_leaf': 50,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'num_threads': 32,
            'lambdarank_truncation_level': 20,
        }
        
        train_set = lgb.Dataset(train_data)
        valid_set = lgb.Dataset(valid_data, reference=train_set)
        
        self.model = lgb.train(
            params,
            train_set,
            num_boost_round=1000,
            valid_sets=[valid_set],
            callbacks=[lgb.early_stopping(50)]
        )
```

---

## 10. Deep Dive: Query Understanding (NER + Intent)

```python
class QueryUnderstandingService:
    """
    Understand user query to improve retrieval and ranking.
    
    Components:
    1. Tokenization & normalization
    2. Named Entity Recognition (brand, product type, attributes)
    3. Intent classification (browse vs specific product vs comparison)
    4. Category prediction
    5. Query rewriting
    """
    
    def analyze_query(self, query: str) -> dict:
        """
        Full query analysis pipeline.
        
        Example: "apple airpods pro noise cancelling under 200"
        → {
            "brand": "Apple",
            "product_type": "earbuds",
            "product_name": "AirPods Pro",
            "attributes": {"noise_cancellation": true},
            "price_constraint": {"max": 200},
            "intent": "specific_product",
            "predicted_category": "Electronics > Headphones > In-Ear"
        }
        """
        # Step 1: Tokenize and normalize
        tokens = self.tokenize(query)
        
        # Step 2: NER
        entities = self.extract_entities(tokens)
        
        # Step 3: Intent classification
        intent = self.classify_intent(query, entities)
        
        # Step 4: Category prediction
        category = self.predict_category(query, entities)
        
        # Step 5: Query rewriting
        rewritten = self.rewrite_query(query, entities)
        
        return {
            "original_query": query,
            "entities": entities,
            "intent": intent,
            "predicted_category": category,
            "rewritten_query": rewritten,
            "tokens": tokens
        }
    
    def extract_entities(self, tokens: list) -> dict:
        """
        NER using fine-tuned BERT model.
        
        Entity types:
        - BRAND: Apple, Samsung, Nike
        - PRODUCT_TYPE: earbuds, laptop, shoes
        - PRODUCT_NAME: AirPods Pro, MacBook Air
        - ATTRIBUTE: noise cancelling, wireless, waterproof
        - COLOR: black, red, blue
        - SIZE: large, 10 inches, size 42
        - MATERIAL: leather, cotton, stainless steel
        - PRICE: under 200, cheap, expensive
        
        Model: Fine-tuned DistilBERT on Amazon query logs
        Latency: < 5ms on GPU
        """
        # Predict BIO tags
        input_text = ' '.join(tokens)
        predictions = self.ner_model.predict(input_text)
        
        entities = {
            'brands': [],
            'product_types': [],
            'product_names': [],
            'attributes': [],
            'colors': [],
            'sizes': [],
            'price_constraints': []
        }
        
        current_entity = None
        current_tokens = []
        
        for token, tag in zip(tokens, predictions):
            if tag.startswith('B-'):
                # Save previous entity
                if current_entity:
                    entities[current_entity].append(' '.join(current_tokens))
                # Start new entity
                current_entity = tag[2:].lower() + 's'
                current_tokens = [token]
            elif tag.startswith('I-') and current_entity:
                current_tokens.append(token)
            else:
                if current_entity:
                    entities[current_entity].append(' '.join(current_tokens))
                current_entity = None
                current_tokens = []
        
        # Save last entity
        if current_entity:
            entities[current_entity].append(' '.join(current_tokens))
        
        return entities
    
    def classify_intent(self, query: str, entities: dict) -> str:
        """
        Intent types:
        - "specific_product": User wants a specific item ("iphone 15 pro max 256gb")
        - "category_browse": User exploring a category ("running shoes")
        - "comparison": User comparing options ("airpods vs galaxy buds")
        - "deal_seeking": User looking for discounts ("black friday laptop deals")
        - "question": User asking about a product ("is macbook air good for coding")
        
        Impact on search:
        - specific_product: Boost exact matches, show single product prominently
        - category_browse: Show diverse results, emphasize facets
        - comparison: Show comparison table
        - deal_seeking: Boost deals, sort by discount
        """
        features = {
            'query_length': len(query.split()),
            'has_brand': len(entities.get('brands', [])) > 0,
            'has_model': len(entities.get('product_names', [])) > 0,
            'has_comparison_word': any(w in query.lower() for w in ['vs', 'versus', 'compare', 'or']),
            'has_deal_word': any(w in query.lower() for w in ['deal', 'discount', 'sale', 'cheap', 'under']),
            'has_question_word': any(w in query.lower() for w in ['is', 'can', 'does', 'how', 'what', 'which']),
        }
        
        # Rule-based + ML hybrid
        if features['has_comparison_word']:
            return 'comparison'
        if features['has_deal_word']:
            return 'deal_seeking'
        if features['has_question_word']:
            return 'question'
        if features['has_brand'] and features['has_model']:
            return 'specific_product'
        
        return 'category_browse'
    
    def predict_category(self, query: str, entities: dict) -> str:
        """
        Predict most likely product category for the query.
        Used to:
        - Restrict search to relevant category (faster)
        - Display appropriate facets
        - Apply category-specific ranking features
        
        Model: Hierarchical classifier trained on (query, clicked_category) pairs
        """
        # Use product type entity as primary signal
        product_types = entities.get('product_types', [])
        
        if product_types:
            # Lookup product type → category mapping
            for pt in product_types:
                if pt in self.product_type_to_category:
                    return self.product_type_to_category[pt]
        
        # Fallback: ML classifier
        return self.category_classifier.predict(query)
    
    def rewrite_query(self, query: str, entities: dict) -> str:
        """
        Query rewriting for better retrieval:
        - Expand abbreviations: "bt" → "bluetooth"
        - Normalize units: "6ft" → "6 feet"
        - Add implicit terms: "iphone case" → "iphone case cover"
        - Remove noise words that hurt retrieval
        """
        rewritten = query
        
        # Abbreviation expansion
        abbreviations = {
            'bt': 'bluetooth', 'wifi': 'wi-fi', 'usb-c': 'usb type-c',
            'gb': 'gigabyte', 'tb': 'terabyte', '4k': '4k uhd',
        }
        for abbr, expansion in abbreviations.items():
            if abbr in rewritten.lower().split():
                rewritten = rewritten.replace(abbr, f"{abbr} {expansion}")
        
        return rewritten
```

---

## 11. Indexing Pipeline

```python
class ProductIndexingPipeline:
    """
    Near-real-time indexing pipeline.
    Product catalog changes → Kafka → Processing → Elasticsearch
    
    Latency target: New/updated products searchable within 5 minutes.
    """
    
    def __init__(self):
        self.kafka_consumer = None
        self.es_client = None
        self.embedding_model = None
    
    def process_product_event(self, event: dict):
        """
        Process a single product change event.
        
        Event types: CREATE, UPDATE, DELETE, PRICE_CHANGE, STOCK_CHANGE
        """
        event_type = event['type']
        product = event['product']
        
        if event_type == 'DELETE':
            self.es_client.delete(index='products', id=product['product_id'])
            return
        
        # Enrich product document
        enriched = self.enrich_product(product)
        
        # Generate embedding
        text_for_embedding = f"{product['title']} {product['brand']} {' '.join(product.get('bullet_points', []))}"
        enriched['embedding_vector'] = self.embedding_model.encode(text_for_embedding).tolist()
        
        # Index/update in Elasticsearch
        self.es_client.index(
            index='products',
            id=product['product_id'],
            body=enriched,
            refresh='false'  # Don't refresh immediately (batched every 1s)
        )
    
    def enrich_product(self, product: dict) -> dict:
        """Add computed fields to product document"""
        product['sales_metrics'] = self.compute_sales_metrics(product['product_id'])
        product['brand_authority'] = self.get_brand_authority(product.get('brand', ''))
        return product
    
    def bulk_reindex(self, batch_size: int = 5000):
        """
        Full reindex for schema changes or model updates.
        Uses scroll + bulk API for efficiency.
        
        Strategy: Index to new index alias, atomic swap when complete.
        """
        from elasticsearch.helpers import bulk
        
        new_index = f"products_v{int(time.time())}"
        self.es_client.indices.create(index=new_index, body=self.get_mapping())
        
        # Bulk index all products
        actions = []
        for product in self.scan_all_products():
            enriched = self.enrich_product(product)
            text = f"{product['title']} {product['brand']}"
            enriched['embedding_vector'] = self.embedding_model.encode(text).tolist()
            
            actions.append({
                '_index': new_index,
                '_id': product['product_id'],
                '_source': enriched
            })
            
            if len(actions) >= batch_size:
                bulk(self.es_client, actions)
                actions = []
        
        if actions:
            bulk(self.es_client, actions)
        
        # Atomic alias swap
        self.es_client.indices.update_aliases(body={
            "actions": [
                {"remove": {"index": "products_*", "alias": "products"}},
                {"add": {"index": new_index, "alias": "products"}}
            ]
        })
```

---

## 12. Caching & Performance

```
Caching Strategy:

Layer 1: Client-side (Browser)
  - Autocomplete responses: 60s TTL
  - Search results for back button: session-based

Layer 2: CDN (CloudFront)
  - Static facets/category pages: 5 min TTL
  - NOT used for personalized search results

Layer 3: Application Cache (Redis Cluster)
  - Popular query results (non-personalized): 5 min TTL
  - Facet aggregations: 10 min TTL
  - Category → product count mappings: 1 hour TTL
  - Product metadata (for result assembly): 1 hour TTL
  
  Key design: Cache by (query + filters + sort) hash
  - Personalization applied AFTER cache lookup (re-rank cached results)
  - Allows high cache hit rate despite personalization

Layer 4: Elasticsearch OS Page Cache
  - Hot index segments cached in OS memory
  - Typically 80%+ of index fits in page cache

Cache Invalidation:
  - Price changes: Invalidate queries where this product appears in top-100
  - Stock changes: Same as price
  - New products: TTL-based (new products appear after cache expires)
  - Trending/seasonal: Reduce TTL during high-change periods
```

---

## 13. Observability

### Key Metrics
```yaml
search_quality:
  - ndcg@10: target > 0.55
  - conversion_rate: searches → purchases (target > 8%)
  - add_to_cart_rate: target > 15%
  - zero_results_rate: target < 0.5%
  - click_position_avg: average position of first click (target < 3)
  - time_to_first_click: target < 10 seconds

performance:
  - search_latency_p50: target < 100ms
  - search_latency_p99: target < 300ms
  - retrieval_time: BM25 + vector search time
  - reranking_time: LTR inference time
  - facet_computation_time: aggregation time

infrastructure:
  - index_size_gb: total index footprint
  - shard_balance: query distribution evenness
  - cache_hit_rate: Redis cache effectiveness (target > 40%)
  - indexing_lag: time from product update to searchable
  - embedding_throughput: vectors generated per second

business:
  - revenue_per_search: GMV attributed to search
  - sponsored_fill_rate: queries with relevant ads
  - search_exit_rate: users leaving after search (target < 20%)
```

---

## 14. Considerations & Trade-offs

### Relevance vs Revenue
```
Trade-off: Organic relevance vs sponsored product placement
Decision:
- Max 2 sponsored slots in top-10 results
- Sponsored must have minimum relevance threshold
- Long-term: Optimizing user trust drives more searches/revenue
```

### Freshness vs Index Quality
```
Trade-off: Real-time indexing may have incomplete features (no sales data yet)
Decision:
- New products get indexed within 5 minutes (basic features)
- Sales/behavioral features backfilled within 24 hours
- Use "new product boost" to give visibility while features accumulate
```

### Personalization vs Exploration
```
Trade-off: Over-personalization creates filter bubbles
Decision:
- Cap personalization influence at 20% of final score
- Always show some diverse/unexpected results
- A/B test personalization level continuously
```

---

## 15. Summary

| Dimension | Approach |
|-----------|----------|
| Retrieval | Hybrid: BM25 (lexical) + HNSW (semantic), RRF fusion |
| Ranking | 3-stage: BM25 → LambdaMART (300 features) → personalization |
| Query Understanding | NER (brand/product/attribute) + intent classification |
| Indexing | Near-real-time via Kafka → Elasticsearch (< 5 min) |
| Personalization | User affinity features in LTR + post-retrieval re-rank |
| Scale | 350M products, 50K QPS, 1000 shards, Redis caching |
| Freshness | Streaming index updates, full reindex for model changes |
