# Semantic Search and Vector Databases

## Overview

Semantic search retrieves results based on meaning rather than keyword matching, powered by embedding models and efficient nearest-neighbor search.

```
Traditional: query "car" → matches documents containing "car"
Semantic:    query "car" → matches "automobile", "vehicle", "sedan", "driving"
```

---

## 1. Traditional Search

### Inverted Index

```
Document 1: "the cat sat on the mat"
Document 2: "the dog sat on the log"

Inverted Index:
  "cat" → [doc1]
  "dog" → [doc2]
  "sat" → [doc1, doc2]
  "mat" → [doc1]
  "log" → [doc2]
  "the" → [doc1, doc2]
  "on"  → [doc1, doc2]

Query "cat mat" → intersection/union of posting lists
```

### BM25 (Best Match 25)

```
BM25(D, Q) = Σ_{t ∈ Q} IDF(t) * [TF(t,D) * (k1 + 1)] / [TF(t,D) + k1 * (1 - b + b * |D|/avgdl)]

Where:
  k1 = 1.2 (term frequency saturation)
  b  = 0.75 (document length normalization)
  |D| = document length
  avgdl = average document length
```

```python
# BM25 with rank_bm25
from rank_bm25 import BM25Okapi

corpus = [
    "machine learning algorithms",
    "deep neural networks for NLP",
    "natural language processing with transformers",
    "computer vision and image recognition"
]
tokenized = [doc.split() for doc in corpus]
bm25 = BM25Okapi(tokenized)

query = "NLP transformer models"
scores = bm25.get_scores(query.split())
# [0.0, 0.45, 0.89, 0.0]  → doc 3 ranks highest
```

---

## 2. Semantic Search Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Indexing Pipeline                       │
│                                                          │
│  Documents → Chunking → Embedding Model → Vector DB     │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                   Query Pipeline                          │
│                                                          │
│  Query → Embedding Model → ANN Search → Re-rank → Results│
└─────────────────────────────────────────────────────────┘
```

---

## 3. Embedding Models for Search

### Bi-Encoder vs Cross-Encoder

```
Bi-Encoder (fast, independent encoding):
  Query  → Encoder → q_vec ─┐
                              ├── cosine(q_vec, d_vec) = score
  Doc    → Encoder → d_vec ─┘

  Pros: Pre-compute doc embeddings, fast retrieval
  Cons: No token-level query-doc interaction

Cross-Encoder (slow, joint encoding):
  [CLS] Query [SEP] Document [SEP] → Encoder → score

  Pros: Higher accuracy (sees query-doc interaction)
  Cons: O(n) forward passes for n candidates, can't pre-compute
```

```python
from sentence_transformers import SentenceTransformer, CrossEncoder

# Bi-encoder for retrieval
bi_encoder = SentenceTransformer('all-MiniLM-L6-v2')
query_emb = bi_encoder.encode("What is machine learning?")
doc_embs = bi_encoder.encode(["ML is a subset of AI", "The weather is nice"])

# Cross-encoder for re-ranking
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = cross_encoder.predict([
    ("What is machine learning?", "ML is a subset of AI"),
    ("What is machine learning?", "The weather is nice")
])
# [0.95, 0.01]  → much better discrimination
```

### Popular Embedding Models

| Model | Dimensions | Speed | Quality (MTEB) |
|-------|-----------|-------|-----------------|
| all-MiniLM-L6-v2 | 384 | Fast | Good |
| all-mpnet-base-v2 | 768 | Medium | Better |
| e5-large-v2 | 1024 | Slow | Great |
| text-embedding-3-small (OpenAI) | 1536 | API | Great |
| text-embedding-3-large (OpenAI) | 3072 | API | Best |
| voyage-3 | 1024 | API | Best (code) |

---

## 4. Vector Similarity Metrics

```python
import numpy as np

def cosine_similarity(a, b):
    """Range: [-1, 1]. Most common for normalized embeddings."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def dot_product(a, b):
    """Range: (-∞, ∞). Faster; equivalent to cosine if vectors normalized."""
    return np.dot(a, b)

def euclidean_distance(a, b):
    """Range: [0, ∞). Lower = more similar."""
    return np.linalg.norm(a - b)

# For normalized vectors: cosine = dot product, and ranking by L2 = ranking by cosine
# Most embedding models output normalized vectors → use dot product (fastest)
```

---

## 5. Approximate Nearest Neighbor (ANN) Algorithms

Exact nearest neighbor is O(n·d) — too slow for millions of vectors. ANN trades accuracy for speed.

### HNSW (Hierarchical Navigable Small World)

```
Structure: Multi-layer graph
  Layer 2: [A] ─── [F]                    (sparse, long-range)
  Layer 1: [A] ─ [C] ─ [F] ─ [H]         (medium density)
  Layer 0: [A]-[B]-[C]-[D]-[E]-[F]-[G]-[H] (dense, all nodes)

Search:
  1. Start at top layer, greedily move to nearest neighbor
  2. Drop to next layer, continue greedy search
  3. At layer 0, explore local neighborhood

Parameters:
  M = max connections per node (16-64)
  ef_construction = search width during build (higher = better index, slower build)
  ef_search = search width during query (higher = better recall, slower query)
```

### IVF (Inverted File Index)

```
1. Cluster vectors into k centroids (k-means)
2. Assign each vector to nearest centroid
3. At query time:
   a. Find nprobe nearest centroids to query
   b. Search only vectors in those clusters

Trade-off: nprobe ↑ → recall ↑, speed ↓
Typical: k=1024, nprobe=10-50
```

### Product Quantization (PQ)

```
Compress 768-dim vector into ~64 bytes:
1. Split vector into m subvectors (e.g., 768 → 96 subvectors of 8 dims)
2. Cluster each subspace into 256 centroids (1 byte each)
3. Store only centroid IDs → m bytes per vector

Distance: approximate by summing subvector distances (lookup table)
Memory: 768 floats (3072 bytes) → 96 bytes!
```

### Comparison

| Algorithm | Build Time | Query Time | Memory | Recall |
|-----------|-----------|------------|--------|--------|
| Flat (exact) | O(1) | O(n·d) | O(n·d) | 100% |
| HNSW | O(n·log n) | O(log n) | O(n·M·d) | 95-99% |
| IVF | O(n·k) | O(n/k·nprobe) | O(n·d) | 85-95% |
| IVF+PQ | O(n·k) | O(n/k·nprobe) | O(n·m) | 80-90% |
| ScaNN | O(n) | O(√n) | O(n·m) | 90-95% |

---

## 6. Vector Database Comparison

| Database | Type | ANN Algorithm | Unique Features | Scale |
|----------|------|--------------|-----------------|-------|
| Pinecone | Managed | Proprietary | Serverless, metadata filtering | Billions |
| Weaviate | Self-hosted/Cloud | HNSW | GraphQL, modules, hybrid | Millions |
| Milvus | Self-hosted/Cloud | IVF, HNSW, DiskANN | GPU support, streaming | Billions |
| Qdrant | Self-hosted/Cloud | HNSW | Rust, payload filtering | Millions |
| ChromaDB | Embedded | HNSW | Simple API, Python-native | Thousands-Millions |
| pgvector | Extension | IVFFlat, HNSW | PostgreSQL integration | Millions |
| FAISS | Library | All | Facebook research, GPU | Billions |

### ChromaDB (Simple Local)

```python
import chromadb
from chromadb.utils import embedding_functions

# Create client and collection
client = chromadb.PersistentClient(path="./chroma_db")
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.create_collection("docs", embedding_function=ef)

# Add documents
collection.add(
    documents=["Machine learning is great", "I love pizza", "Neural networks are powerful"],
    ids=["doc1", "doc2", "doc3"],
    metadatas=[{"topic": "ml"}, {"topic": "food"}, {"topic": "ml"}]
)

# Query
results = collection.query(query_texts=["AI and deep learning"], n_results=2)
# Returns doc1, doc3 (semantically similar to query)
```

### FAISS (High Performance)

```python
import faiss
import numpy as np

# Create index
d = 384  # embedding dimension
n = 100000  # number of vectors

# Flat (exact) index
index_flat = faiss.IndexFlatIP(d)  # Inner Product (for normalized vectors = cosine)

# HNSW index
index_hnsw = faiss.IndexHNSWFlat(d, 32)  # M=32
index_hnsw.hnsw.efConstruction = 200
index_hnsw.hnsw.efSearch = 50

# IVF index
nlist = 1024  # number of clusters
quantizer = faiss.IndexFlatL2(d)
index_ivf = faiss.IndexIVFFlat(quantizer, d, nlist)
index_ivf.train(vectors)  # need to train on data
index_ivf.nprobe = 10

# Add vectors
index_hnsw.add(vectors)

# Search
query = np.random.randn(1, d).astype('float32')
distances, indices = index_hnsw.search(query, k=10)
```

### pgvector (PostgreSQL)

```sql
-- Enable extension
CREATE EXTENSION vector;

-- Create table with vector column
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(384)
);

-- Create HNSW index
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Insert
INSERT INTO documents (content, embedding) VALUES ('Hello world', '[0.1, 0.2, ...]');

-- Query (cosine similarity)
SELECT content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 10;
```

---

## 7. Hybrid Search (BM25 + Dense Vectors)

```
Why hybrid?
- BM25 excels at exact keyword matching ("error code 404")
- Dense vectors excel at semantic matching ("how to fix page not found")
- Combine for best of both worlds

Fusion methods:
1. Reciprocal Rank Fusion (RRF):
   score(d) = Σ 1/(k + rank_i(d))   where k=60 typically

2. Weighted linear combination:
   score(d) = α * normalize(bm25_score) + (1-α) * normalize(vector_score)
```

```python
# Hybrid search with Weaviate
# client.query.get("Document", ["content"])
#   .with_hybrid(query="machine learning", alpha=0.5)
#   .with_limit(10)

# Manual hybrid with RRF
def reciprocal_rank_fusion(rankings_list, k=60):
    """Combine multiple ranking lists using RRF."""
    scores = {}
    for rankings in rankings_list:
        for rank, doc_id in enumerate(rankings, 1):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

bm25_results = ["doc3", "doc1", "doc5", "doc2"]  # BM25 ranking
vector_results = ["doc1", "doc3", "doc2", "doc4"]  # Vector ranking
fused = reciprocal_rank_fusion([bm25_results, vector_results])
```

---

## 8. Re-ranking Strategies

```
Pipeline:
  Query → Retrieve 100 candidates (bi-encoder) → Re-rank top 100 (cross-encoder) → Return top 10

Why two stages?
  - Bi-encoder: fast retrieval from millions (O(1) with ANN)
  - Cross-encoder: accurate scoring of small candidate set (O(100))
```

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

query = "What causes climate change?"
candidates = [
    "Climate change is caused by greenhouse gas emissions",
    "The weather in London is unpredictable",
    "CO2 levels have risen significantly since industrialization",
    "Climate refers to long-term weather patterns"
]

# Score each (query, candidate) pair
pairs = [(query, doc) for doc in candidates]
scores = reranker.predict(pairs)
# [0.95, 0.02, 0.88, 0.15]  → reorder by score

ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
```

---

## 9. Indexing Strategies for Billion-Scale

```
Challenge: 1 billion vectors × 768 dims × 4 bytes = 3 TB in memory!

Solutions:
┌──────────────────────────────────────────────────────────┐
│ Strategy           │ Approach                             │
├──────────────────────────────────────────────────────────┤
│ Quantization       │ Reduce precision (FP32→INT8, PQ)    │
│ Sharding           │ Split across multiple nodes          │
│ DiskANN            │ SSD-based index (Vamana graph)      │
│ Tiered storage     │ Hot vectors in RAM, cold on disk    │
│ Dimensionality red.│ Reduce dims (PCA, Matryoshka)       │
│ Filtering first    │ Metadata pre-filter, then ANN       │
└──────────────────────────────────────────────────────────┘
```

### Matryoshka Embeddings

```python
# OpenAI text-embedding-3 supports dimension reduction
# Full: 3072 dims → can truncate to 1024, 512, 256 with minimal quality loss
# Trade storage/speed for quality

from openai import OpenAI
client = OpenAI()

response = client.embeddings.create(
    input="Hello world",
    model="text-embedding-3-large",
    dimensions=256  # truncate from 3072 to 256
)
```

---

## 10. Production Considerations

### Chunking Strategy

```
Document → Chunks (for embedding)

Strategies:
1. Fixed-size (512 tokens with 50-token overlap)
2. Semantic (split at paragraph/section boundaries)
3. Recursive (split by separator hierarchy: \n\n → \n → sentence → word)
4. Document-specific (code: by function; legal: by clause)

Overlap is critical: prevents losing context at chunk boundaries
```

### Evaluation Metrics

```python
def recall_at_k(retrieved_ids, relevant_ids, k):
    """What fraction of relevant docs appear in top-k?"""
    retrieved_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(retrieved_k & relevant) / len(relevant)

def mrr(retrieved_ids, relevant_ids):
    """Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0

def ndcg_at_k(retrieved_ids, relevance_scores, k):
    """Normalized Discounted Cumulative Gain."""
    dcg = sum(relevance_scores.get(doc, 0) / np.log2(i + 2) 
              for i, doc in enumerate(retrieved_ids[:k]))
    ideal = sorted(relevance_scores.values(), reverse=True)[:k]
    idcg = sum(score / np.log2(i + 2) for i, score in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0
```

### Operational Concerns

| Concern | Solution |
|---------|----------|
| Index freshness | Incremental updates, eventual consistency |
| Cold start | Fall back to BM25 until embeddings ready |
| Drift | Monitor query-result similarity distribution |
| Multi-tenancy | Namespace/partition per tenant |
| Cost | Quantize, use tiered storage, right-size dims |
| Latency SLA | Pre-warm, cache frequent queries |

---

## 11. Complete Semantic Search Pipeline

```python
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb
from typing import List

class SemanticSearchPipeline:
    def __init__(self):
        self.bi_encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        self.client = chromadb.PersistentClient("./search_db")
        self.collection = self.client.get_or_create_collection("documents")
    
    def index(self, documents: List[str], ids: List[str]):
        """Index documents with embeddings."""
        embeddings = self.bi_encoder.encode(documents).tolist()
        self.collection.add(documents=documents, embeddings=embeddings, ids=ids)
    
    def search(self, query: str, top_k: int = 10, rerank_top: int = 50):
        """Retrieve with bi-encoder, re-rank with cross-encoder."""
        # Stage 1: Retrieve candidates
        results = self.collection.query(
            query_embeddings=self.bi_encoder.encode([query]).tolist(),
            n_results=rerank_top
        )
        candidates = results['documents'][0]
        
        # Stage 2: Re-rank with cross-encoder
        pairs = [(query, doc) for doc in candidates]
        scores = self.cross_encoder.predict(pairs)
        
        # Sort by cross-encoder score
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

# Usage
pipeline = SemanticSearchPipeline()
pipeline.index(["doc1 text", "doc2 text", ...], ["id1", "id2", ...])
results = pipeline.search("How does photosynthesis work?")
```

---

## Exercises

1. Build a hybrid search system combining BM25 and SBERT with RRF fusion
2. Benchmark HNSW vs IVF on 1M vectors: measure recall@10, QPS, and memory
3. Implement a two-stage retrieval pipeline with bi-encoder + cross-encoder re-ranking
4. Compare chunking strategies (fixed vs semantic) on a QA retrieval task
5. Set up pgvector and compare query performance with and without HNSW indexing

## Interview Questions

1. **Why use a two-stage retrieval (bi-encoder + cross-encoder) instead of just cross-encoder?**
   - Cross-encoder can't pre-compute embeddings; scoring 1M docs per query is infeasible. Bi-encoder narrows to top-k candidates cheaply, cross-encoder refines.

2. **When would BM25 outperform dense retrieval?**
   - Exact keyword queries, rare/domain terms not in embedding training data, zero-shot without domain adaptation, short queries with specific entities.

3. **How does HNSW achieve O(log n) search time?**
   - Hierarchical layers create "highways" for long-range navigation; greedy search at each layer progressively narrows to local neighborhood at bottom layer.

4. **What's the trade-off between IVF nprobe and recall?**
   - Higher nprobe searches more clusters → higher recall but slower. Need to tune per use case. Typical sweet spot: nprobe = sqrt(nlist).

5. **How would you handle real-time document updates in a vector search system?**
   - Append-only with periodic compaction, write-ahead log, dual-index (serving + building), or use databases with native CRUD (Qdrant, Weaviate, Milvus).
