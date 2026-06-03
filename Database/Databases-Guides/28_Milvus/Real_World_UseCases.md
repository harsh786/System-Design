# Milvus - Real World Use Cases & Production Guide

## Table of Contents
- [Use Case 1: Shopify Product Recommendations](#use-case-1-shopify-product-recommendations)
- [Use Case 2: Salesforce Einstein AI](#use-case-2-salesforce-einstein-ai)
- [Use Case 3: Trend Micro Cybersecurity](#use-case-3-trend-micro-cybersecurity)
- [Use Case 4: Tokopedia Visual Search](#use-case-4-tokopedia-visual-search)
- [Use Case 5: Zilliz RAG for Enterprise](#use-case-5-zilliz-rag-for-enterprise)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)
- [Core Concepts](#core-concepts)

---

## Use Case 1: Shopify Product Recommendations

### Problem
Shopify merchants need "Similar Products" recommendations. Traditional collaborative filtering fails for new/long-tail products. Semantic similarity via embeddings captures product relationships beyond purchase history.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Shopify Storefront                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ GET /recommendations?product_id=X
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Recommendation Service                           │
│  ┌──────────────┐    ┌────────────────┐    ┌────────────────────┐  │
│  │ Product Cache │    │  Milvus Client │    │  Reranking Layer   │  │
│  │   (Redis)     │    │                │    │  (business rules)  │  │
│  └──────┬───────┘    └───────┬────────┘    └────────┬───────────┘  │
└─────────┼────────────────────┼─────────────────────┼───────────────┘
          │                    │                      │
          ▼                    ▼                      │
┌──────────────┐    ┌──────────────────┐             │
│    Redis     │    │     Milvus       │             │
│  (metadata)  │    │   Cluster        │◄────────────┘
└──────────────┘    │                  │
                    │  Collection:     │
                    │  product_vectors │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────────┐  ┌────────────┐
│  Query Node  │  │   Query Node     │  │ Query Node │
│  (replica 1) │  │   (replica 2)    │  │ (replica 3)│
└──────────────┘  └──────────────────┘  └────────────┘

─── Embedding Pipeline (Offline) ───

┌────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌───────┐
│  Product   │    │ Text: title +   │    │  Sentence    │    │Milvus │
│  Catalog   │───▶│ description +   │───▶│ Transformers │───▶│Insert │
│  (DB)      │    │ category + tags  │    │ (768d)       │    │       │
└────────────┘    └─────────────────┘    └──────────────┘    └───────┘
```

### Collection Schema

```python
from pymilvus import CollectionSchema, FieldSchema, DataType

fields = [
    FieldSchema(name="product_id", dtype=DataType.INT64, is_primary=True),
    FieldSchema(name="shop_id", dtype=DataType.INT64),
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
    FieldSchema(name="price_bucket", dtype=DataType.INT32),  # 0-10 price tiers
    FieldSchema(name="in_stock", dtype=DataType.BOOL),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
]

schema = CollectionSchema(fields, description="Shopify product embeddings")

# Index: HNSW for low-latency serving
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 32, "efConstruction": 256}
}
```

### Embedding Pipeline

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-mpnet-base-v2')  # 768d

def embed_product(product):
    text = f"{product['title']} {product['description']} {product['category']}"
    return model.encode(text, normalize_embeddings=True)

# Batch ingestion
embeddings = model.encode(product_texts, batch_size=256, show_progress_bar=True)
```

### Search Queries

```python
# Basic similarity search
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 128}},
    limit=20,
    output_fields=["product_id", "category", "price_bucket"]
)

# Filtered search: same category, in stock, similar price
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 128}},
    limit=20,
    expr="category == 'electronics' and in_stock == true and price_bucket >= 3 and price_bucket <= 7",
    output_fields=["product_id", "category", "price_bucket"]
)

# Multi-shop partitioned search
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 128}},
    limit=20,
    partition_names=[f"shop_{shop_id}"],
    output_fields=["product_id"]
)
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Total vectors | ~500M products across all shops |
| Dimensions | 768 |
| Index type | HNSW (M=32) |
| Search latency (p50) | 8ms |
| Search latency (p99) | 25ms |
| QPS per query node | ~2,000 |
| Total QPS | ~12,000 (6 query nodes) |
| Memory per node | 64GB RAM |
| Recall@10 | 0.96 |

---

## Use Case 2: Salesforce Einstein AI

### Problem
Support agents need to find similar resolved cases and knowledge articles instantly. Vector search over case descriptions + resolutions enables "find cases like this" with semantic understanding.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Salesforce Service Cloud                     │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────┐ │
│  │  Agent    │    │  Case Feed   │    │  Knowledge Base    │ │
│  │  Console  │    │              │    │                    │ │
│  └─────┬────┘    └──────┬───────┘    └────────┬───────────┘ │
└────────┼────────────────┼─────────────────────┼──────────────┘
         │                │                     │
         ▼                ▼                     ▼
┌──────────────────────────────────────────────────────────────┐
│                   Einstein AI Platform                         │
│                                                               │
│  ┌──────────────────┐    ┌───────────────────────────────┐  │
│  │  Query Encoder   │    │   Document Encoder (Offline)   │  │
│  │  (real-time)     │    │   - Case descriptions          │  │
│  │                  │    │   - Resolutions                 │  │
│  │  Input: agent    │    │   - KB articles                 │  │
│  │  query text      │    │                                 │  │
│  └────────┬─────────┘    └──────────────┬────────────────┘  │
│           │                              │                    │
│           ▼                              ▼                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Milvus Cluster                      │   │
│  │                                                        │   │
│  │  Collection: cases        Collection: kb_articles     │   │
│  │  ├─ case_id (PK)         ├─ article_id (PK)          │   │
│  │  ├─ org_id               ├─ org_id                    │   │
│  │  ├─ status               ├─ category                  │   │
│  │  ├─ priority             ├─ last_updated              │   │
│  │  ├─ product_area         ├─ embedding (1536d)         │   │
│  │  ├─ resolution_type      └───────────────────────     │   │
│  │  ├─ embedding (1536d)                                  │   │
│  │  └─────────────────                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Object Storage (S3)    │    Message Queue (Kafka)           │
│  - Segment files        │    - CDC from Salesforce DB        │
│  - Index files          │    - Real-time case updates        │
└──────────────────────────────────────────────────────────────┘
```

### Collection Schema

```python
# Cases collection
case_fields = [
    FieldSchema(name="case_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
    FieldSchema(name="org_id", dtype=DataType.VARCHAR, max_length=32),
    FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=20),
    FieldSchema(name="priority", dtype=DataType.INT32),  # 1=Critical, 4=Low
    FieldSchema(name="product_area", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="resolution_type", dtype=DataType.VARCHAR, max_length=32),
    FieldSchema(name="created_ts", dtype=DataType.INT64),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
]

# Index: IVF_SQ8 for memory efficiency at scale
index_params = {
    "metric_type": "IP",  # Inner Product (embeddings pre-normalized)
    "index_type": "IVF_SQ8",
    "params": {"nlist": 4096}
}
```

### Embedding Pipeline

```python
import openai

def embed_case(case):
    text = f"Subject: {case['subject']}\n"
    text += f"Description: {case['description']}\n"
    text += f"Resolution: {case.get('resolution', '')}"
    
    response = openai.embeddings.create(
        model="text-embedding-3-large",  # 1536d
        input=text
    )
    return response.data[0].embedding

# Batch processing via Kafka consumer
# CDC events from Salesforce → Kafka → Embedding Service → Milvus
```

### Search Queries

```python
# Find similar resolved cases within same org
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "IP", "params": {"nprobe": 64}},
    limit=10,
    expr="org_id == 'ORG_12345' and status == 'Closed' and resolution_type != 'Duplicate'",
    output_fields=["case_id", "product_area", "resolution_type", "priority"]
)

# Hybrid search: vector + text match on product area
# First search broadly, then filter/rerank
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "IP", "params": {"nprobe": 128}},
    limit=50,
    expr="org_id == 'ORG_12345' and product_area in ['billing', 'payments']",
    output_fields=["case_id", "product_area", "priority", "created_ts"]
)
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Total vectors (cases) | ~2B across all orgs |
| Total vectors (KB articles) | ~200M |
| Dimensions | 1536 |
| Index type | IVF_SQ8 (nlist=4096) |
| Search latency (p50) | 15ms |
| Search latency (p99) | 45ms |
| QPS | ~50,000 (multi-tenant) |
| Memory per node | 128GB RAM |
| Query nodes | 24 |
| Recall@10 | 0.93 |

---

## Use Case 3: Trend Micro Cybersecurity

### Problem
New malware variants are often modifications of known malware. By embedding binary features (API calls, opcode sequences, PE headers) into vectors, similar malware families can be detected even when signatures don't match.

### Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                    Threat Detection Pipeline                        │
└───────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────┐
│ Endpoint │    │   Sandbox    │    │  Feature        │    │Vector│
│ Agent    │───▶│   Analysis   │───▶│  Extraction     │───▶│Embed │
│ (file)   │    │  (Detonate)  │    │                 │    │      │
└──────────┘    └──────────────┘    │  - API calls    │    └──┬───┘
                                    │  - Opcode freq  │       │
                                    │  - PE headers   │       ▼
                                    │  - String refs  │  ┌─────────┐
                                    │  - Network IoC  │  │  Milvus │
                                    └─────────────────┘  └────┬────┘
                                                              │
                    ┌─────────────────────────────────────────┘
                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                         Milvus Cluster                              │
│                                                                     │
│  Collection: malware_embeddings                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  sample_hash (PK)  │ VARCHAR(64)   │ SHA256 of binary      │   │
│  │  family            │ VARCHAR(64)   │ e.g., "emotet"        │   │
│  │  threat_level      │ INT32         │ 1-5 severity          │   │
│  │  first_seen        │ INT64         │ Unix timestamp        │   │
│  │  file_type         │ VARCHAR(16)   │ PE/ELF/Mach-O/Script  │   │
│  │  behavior_tags     │ JSON          │ ["ransomware","c2"]   │   │
│  │  embedding         │ FLOAT_VECTOR  │ 256 dimensions        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Index: IVF_FLAT (highest recall for security use case)            │
│  Params: nlist=2048, metric=COSINE                                  │
└───────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Threat Intelligence Output                       │
│                                                                     │
│  Query Result:                                                      │
│  "Sample X is 97.3% similar to Emotet variant detected 2024-01"   │
│  → Auto-classify family, extract IoCs, generate detection rule     │
└───────────────────────────────────────────────────────────────────┘
```

### Collection Schema

```python
fields = [
    FieldSchema(name="sample_hash", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
    FieldSchema(name="family", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="threat_level", dtype=DataType.INT32),
    FieldSchema(name="first_seen", dtype=DataType.INT64),
    FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=16),
    FieldSchema(name="behavior_tags", dtype=DataType.JSON),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=256),
]

schema = CollectionSchema(fields, description="Malware similarity embeddings")

# IVF_FLAT: prioritize recall over speed (security-critical)
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 2048}
}
```

### Embedding Pipeline

```python
import numpy as np
from malware_feature_extractor import extract_features  # internal tool

def embed_sample(binary_path):
    """
    Extract features and create embedding:
    - 64d: API call frequency vector (top 64 Windows APIs)
    - 64d: Opcode bigram frequencies
    - 64d: PE section entropy + header features
    - 64d: String/network behavioral features
    Total: 256 dimensions
    """
    features = extract_features(binary_path)
    
    api_vec = features['api_frequencies'][:64]      # 64d
    opcode_vec = features['opcode_bigrams'][:64]    # 64d
    pe_vec = features['pe_features'][:64]           # 64d
    behavior_vec = features['behavior_features'][:64]  # 64d
    
    embedding = np.concatenate([api_vec, opcode_vec, pe_vec, behavior_vec])
    embedding = embedding / np.linalg.norm(embedding)  # L2 normalize
    return embedding.tolist()
```

### Search Queries

```python
# Find similar malware samples (family classification)
results = collection.search(
    data=[sample_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"nprobe": 256}},  # High nprobe for recall
    limit=20,
    expr="threat_level >= 3",
    output_fields=["sample_hash", "family", "threat_level", "behavior_tags"]
)

# Threshold-based detection: find all samples above similarity threshold
# Use range search (Milvus 2.3+)
results = collection.search(
    data=[sample_embedding],
    anns_field="embedding",
    param={
        "metric_type": "COSINE",
        "params": {"nprobe": 512, "radius": 0.85, "range_filter": 1.0}
    },
    limit=100,
    output_fields=["sample_hash", "family", "first_seen"]
)

# Cluster hunt: find all samples in a malware family from a time range
results = collection.search(
    data=[known_emotet_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"nprobe": 256}},
    limit=500,
    expr="first_seen >= 1704067200 and file_type == 'PE'",
    output_fields=["sample_hash", "family", "behavior_tags"]
)
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Total vectors | ~800M malware samples |
| Dimensions | 256 |
| Index type | IVF_FLAT (nlist=2048) |
| Search latency (p50) | 12ms |
| Search latency (p99) | 35ms |
| QPS | ~5,000 (batch analysis) |
| Daily ingestion | ~2M new samples |
| Memory per node | 96GB RAM |
| Recall@20 | 0.99 (critical for security) |

---

## Use Case 4: Tokopedia Visual Search

### Problem
Users photograph a product and expect to find visually similar items. Text search fails here - users may not know the product name. CLIP/visual embeddings enable "photo → find similar products."

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     Mobile App / Web                            │
│   ┌──────────┐                                                │
│   │  Camera  │──── Photo ────┐                                │
│   │  Upload  │               │                                │
│   └──────────┘               ▼                                │
└──────────────────────────────┼────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                    Visual Search API                            │
│                                                                │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐   │
│  │  Image      │    │  CLIP Model  │    │  Post-process  │   │
│  │  Preprocess │───▶│  (ViT-L/14)  │───▶│  & Normalize   │   │
│  │  - Resize   │    │  768d output │    │                │   │
│  │  - Crop     │    │              │    │                │   │
│  │  - Normalize│    │  GPU Cluster │    │                │   │
│  └─────────────┘    └──────────────┘    └───────┬────────┘   │
└─────────────────────────────────────────────────┼─────────────┘
                                                  │
                                                  ▼
┌───────────────────────────────────────────────────────────────┐
│                       Milvus Cluster                            │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Collection: product_images                              │  │
│  │                                                          │  │
│  │  Partitions by category:                                 │  │
│  │  ├── fashion                                             │  │
│  │  ├── electronics                                         │  │
│  │  ├── home_garden                                         │  │
│  │  ├── beauty                                              │  │
│  │  └── ...                                                 │  │
│  │                                                          │  │
│  │  Fields:                                                 │  │
│  │  ├── image_id (PK, INT64)                               │  │
│  │  ├── product_id (INT64)                                  │  │
│  │  ├── seller_id (INT64)                                   │  │
│  │  ├── category (VARCHAR)                                  │  │
│  │  ├── price (FLOAT)                                       │  │
│  │  ├── rating (FLOAT)                                      │  │
│  │  ├── image_embedding (FLOAT_VECTOR, 768d)               │  │
│  │  └── text_embedding (FLOAT_VECTOR, 768d)  [multi-vec]   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  Index: DISKANN (disk-based for cost efficiency at scale)      │
└───────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────┐
│  Results → Product Cards         │
│  (image, title, price, rating)   │
└──────────────────────────────────┘
```

### Collection Schema

```python
fields = [
    FieldSchema(name="image_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="product_id", dtype=DataType.INT64),
    FieldSchema(name="seller_id", dtype=DataType.INT64),
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="price", dtype=DataType.FLOAT),
    FieldSchema(name="rating", dtype=DataType.FLOAT),
    FieldSchema(name="image_embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
]

schema = CollectionSchema(fields)

# DISKANN: handles billion-scale with limited memory
index_params = {
    "metric_type": "COSINE",
    "index_type": "DISKANN",
    "params": {}  # DISKANN auto-tunes
}
```

### Embedding Pipeline

```python
import torch
from transformers import CLIPModel, CLIPProcessor

model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")

def embed_image(image):
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        embedding = model.get_image_features(**inputs)
    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze().numpy().tolist()  # 768d

# Batch pipeline: Spark job processes product catalog images
# Images stored in object storage → GPU workers → embeddings → Milvus
```

### Search Queries

```python
# Visual search: user uploads photo
query_embedding = embed_image(user_photo)

results = collection.search(
    data=[query_embedding],
    anns_field="image_embedding",
    param={"metric_type": "COSINE", "params": {"search_list": 128}},  # DISKANN param
    limit=48,  # Grid of results
    output_fields=["product_id", "category", "price", "rating"]
)

# Filtered visual search: only fashion items under 500k IDR
results = collection.search(
    data=[query_embedding],
    anns_field="image_embedding",
    param={"metric_type": "COSINE", "params": {"search_list": 128}},
    limit=48,
    expr="category == 'fashion' and price <= 500000 and rating >= 4.0",
    output_fields=["product_id", "price", "rating"]
)

# Multi-vector search: combine image + text similarity
from pymilvus import AnnSearchRequest, RRFRanker

image_req = AnnSearchRequest(
    data=[image_embedding], anns_field="image_embedding",
    param={"metric_type": "COSINE", "params": {"search_list": 128}},
    limit=100
)
text_req = AnnSearchRequest(
    data=[text_embedding], anns_field="text_embedding",
    param={"metric_type": "COSINE", "params": {"search_list": 128}},
    limit=100
)

results = collection.hybrid_search(
    reqs=[image_req, text_req],
    ranker=RRFRanker(k=60),
    limit=48,
    output_fields=["product_id", "price", "category"]
)
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Total vectors | ~1.5B product images |
| Dimensions | 768 |
| Index type | DISKANN |
| Search latency (p50) | 18ms |
| Search latency (p99) | 55ms |
| QPS | ~8,000 |
| Storage (index on disk) | ~6TB NVMe SSD |
| Memory per node | 32GB (DISKANN is disk-based) |
| Recall@48 | 0.92 |
| Daily queries | ~20M visual searches |

---

## Use Case 5: Zilliz RAG for Enterprise

### Problem
LLMs hallucinate and lack proprietary knowledge. RAG (Retrieval Augmented Generation) grounds LLM responses in actual documents by retrieving relevant chunks from a vector database before generation.

### Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                          User Query                                 │
│                    "What's our refund policy                        │
│                     for enterprise contracts?"                      │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│                       RAG Orchestrator                              │
│                                                                     │
│  Step 1: Query Embedding                                           │
│  ┌────────────────────────────────────────────┐                   │
│  │  OpenAI text-embedding-3-small (1536d)     │                   │
│  │  or BGE-large-en-v1.5 (1024d)             │                   │
│  └─────────────────────┬──────────────────────┘                   │
│                        │                                            │
│  Step 2: Retrieve      ▼                                           │
│  ┌────────────────────────────────────────────┐                   │
│  │              Milvus Search                  │                   │
│  │  - Vector ANN search (top-k chunks)        │                   │
│  │  - Filter by: source, date, department     │                   │
│  │  - Return: chunk text + metadata           │                   │
│  └─────────────────────┬──────────────────────┘                   │
│                        │                                            │
│  Step 3: Generate      ▼                                           │
│  ┌────────────────────────────────────────────┐                   │
│  │              LLM (GPT-4 / Claude)           │                   │
│  │                                             │                   │
│  │  System: You are a helpful assistant.       │                   │
│  │  Use ONLY the following context:            │                   │
│  │                                             │                   │
│  │  Context:                                   │                   │
│  │  [chunk_1] [chunk_2] [chunk_3] ...          │                   │
│  │                                             │                   │
│  │  Question: {user_query}                     │                   │
│  └─────────────────────┬──────────────────────┘                   │
│                        │                                            │
│  Step 4: Response      ▼                                           │
│  ┌────────────────────────────────────────────┐                   │
│  │  Answer + Source Citations                  │                   │
│  └────────────────────────────────────────────┘                   │
└───────────────────────────────────────────────────────────────────┘

─── Document Ingestion Pipeline (Offline) ───

┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────┐
│Documents │   │  Parse   │   │  Chunk   │   │  Embed   │   │Milvus│
│PDF/DOCX/ │──▶│  Extract │──▶│  Split   │──▶│  Model   │──▶│Upsert│
│HTML/MD   │   │  Text    │   │  512 tok │   │  1536d   │   │      │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────┘
                                    │
                              ┌─────┴──────┐
                              │  Overlap:  │
                              │  64 tokens │
                              └────────────┘
```

### Collection Schema

```python
fields = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),  # filename/URL
    FieldSchema(name="department", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),  # policy/manual/faq
    FieldSchema(name="chunk_index", dtype=DataType.INT32),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),  # chunk text stored
    FieldSchema(name="updated_at", dtype=DataType.INT64),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
]

schema = CollectionSchema(fields, enable_dynamic_field=True)

# HNSW for low-latency RAG retrieval
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 200}
}
```

### Embedding Pipeline

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
import openai

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    separators=["\n\n", "\n", ". ", " "]
)

def ingest_document(doc_path, metadata):
    text = parse_document(doc_path)  # PDF/DOCX/HTML → text
    chunks = splitter.split_text(text)
    
    embeddings = []
    for batch in batched(chunks, 100):
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        embeddings.extend([e.embedding for e in response.data])
    
    # Insert into Milvus
    entities = [
        {"chunk_id": f"{metadata['doc_id']}_{i}", "doc_id": metadata['doc_id'],
         "source": metadata['source'], "department": metadata['department'],
         "doc_type": metadata['doc_type'], "chunk_index": i,
         "text": chunk, "updated_at": int(time.time()),
         "embedding": emb}
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    collection.insert(entities)
```

### Search Queries

```python
# Basic RAG retrieval
query_embedding = get_embedding(user_query)

results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=5,
    output_fields=["text", "source", "doc_type", "chunk_index"]
)

# Department-scoped RAG
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=5,
    expr="department == 'legal' and doc_type in ['policy', 'contract']",
    output_fields=["text", "source", "doc_type"]
)

# Retrieve neighboring chunks for more context
top_chunk = results[0][0]
chunk_idx = top_chunk.entity.get("chunk_index")
doc_id = top_chunk.entity.get("doc_id")

# Get surrounding chunks
neighbors = collection.query(
    expr=f"doc_id == '{doc_id}' and chunk_index >= {chunk_idx-1} and chunk_index <= {chunk_idx+1}",
    output_fields=["text", "chunk_index"]
)

# Assemble context for LLM
context = "\n\n".join([r.entity.get("text") for r in results[0]])
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Total vectors (chunks) | ~50M chunks |
| Documents ingested | ~2M documents |
| Dimensions | 1536 |
| Index type | HNSW (M=16) |
| Search latency (p50) | 5ms |
| Search latency (p99) | 15ms |
| QPS | ~10,000 |
| End-to-end RAG latency | ~1.5s (LLM dominates) |
| Memory per node | 48GB RAM |
| Recall@5 | 0.97 |

---

## Replication

### Milvus Cluster Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Milvus Cluster                               │
│                                                                       │
│  ┌─────────────────── Coordinators (Control Plane) ────────────────┐ │
│  │                                                                  │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │ │
│  │  │  Root     │  │  Query   │  │  Data    │  │  Index   │      │ │
│  │  │  Coord   │  │  Coord   │  │  Coord   │  │  Coord   │      │ │
│  │  │          │  │          │  │          │  │          │      │ │
│  │  │ Manages  │  │ Manages  │  │ Manages  │  │ Manages  │      │ │
│  │  │ topology │  │ query    │  │ data     │  │ index    │      │ │
│  │  │ & DDL    │  │ routing  │  │ channels │  │ building │      │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │ │
│  │                                                                  │ │
│  │  All coordinators: Active-Standby HA via etcd leader election   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─────────────────── Worker Nodes (Data Plane) ───────────────────┐ │
│  │                                                                  │ │
│  │  ┌─────────────────────────────────────────────────────┐       │ │
│  │  │  Proxy Nodes (Stateless)                             │       │ │
│  │  │  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐       │       │ │
│  │  │  │Proxy 1│  │Proxy 2│  │Proxy 3│  │Proxy 4│       │       │ │
│  │  │  └───────┘  └───────┘  └───────┘  └───────┘       │       │ │
│  │  │  Load balanced, handles client SDK connections       │       │ │
│  │  └─────────────────────────────────────────────────────┘       │ │
│  │                                                                  │ │
│  │  ┌─────────────────────────────────────────────────────┐       │ │
│  │  │  Query Nodes (Search + Query)                        │       │ │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │       │ │
│  │  │  │QN 1     │  │QN 2     │  │QN 3     │            │       │ │
│  │  │  │Seg A,B  │  │Seg A,C  │  │Seg B,C  │            │       │ │
│  │  │  │(replica1)│  │(replica2)│  │(replica1)│            │       │ │
│  │  │  └─────────┘  └─────────┘  └─────────┘            │       │ │
│  │  │  Load segments into memory, execute ANN search       │       │ │
│  │  └─────────────────────────────────────────────────────┘       │ │
│  │                                                                  │ │
│  │  ┌─────────────────────────────────────────────────────┐       │ │
│  │  │  Data Nodes (Ingestion)                              │       │ │
│  │  │  ┌─────────┐  ┌─────────┐                          │       │ │
│  │  │  │DN 1     │  │DN 2     │                          │       │ │
│  │  │  │Channel 1│  │Channel 2│                          │       │ │
│  │  │  └─────────┘  └─────────┘                          │       │ │
│  │  │  Consume from MQ, write to object storage            │       │ │
│  │  └─────────────────────────────────────────────────────┘       │ │
│  │                                                                  │ │
│  │  ┌─────────────────────────────────────────────────────┐       │ │
│  │  │  Index Nodes (Index Building)                        │       │ │
│  │  │  ┌─────────┐  ┌─────────┐                          │       │ │
│  │  │  │IN 1     │  │IN 2     │                          │       │ │
│  │  │  │(GPU opt)│  │(GPU opt)│                          │       │ │
│  │  │  └─────────┘  └─────────┘                          │       │ │
│  │  │  Build indexes on sealed segments, write to S3       │       │ │
│  │  └─────────────────────────────────────────────────────┘       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─────────────────── Dependencies ───────────────────────────────┐  │
│  │  ┌──────────┐    ┌──────────────────┐    ┌────────────────┐   │  │
│  │  │   etcd   │    │  Pulsar / Kafka  │    │  MinIO / S3    │   │  │
│  │  │ (meta)   │    │  (message queue) │    │ (object store) │   │  │
│  │  └──────────┘    └──────────────────┘    └────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Segment Replication

```
Segment Replication Across Query Nodes:

Collection "products" has 6 sealed segments: [S1, S2, S3, S4, S5, S6]
Replica factor = 2

Query Coord assigns segments to Query Nodes:

  Query Node 1 (Replica Group 1):  [S1, S2, S3]
  Query Node 2 (Replica Group 1):  [S4, S5, S6]
  Query Node 3 (Replica Group 2):  [S1, S2, S3]  ← replica of QN1
  Query Node 4 (Replica Group 2):  [S4, S5, S6]  ← replica of QN2

Search flow:
  1. Proxy receives search request
  2. Query Coord picks one replica group (load-balanced)
  3. Request fanned out to all QNs in that group
  4. Each QN searches its segments locally
  5. Proxy merges results (reduce phase)

If QN1 fails → Replica Group 2 serves S1,S2,S3 via QN3
```

### Consistency Levels

| Level | Guarantee | Use Case |
|-------|-----------|----------|
| **Strong** | Read-after-write. Waits for all data nodes to flush. | Financial data, security |
| **Bounded Staleness** | Reads may lag by configured time window (e.g., 10s) | Dashboard queries |
| **Session** | Read-your-own-writes within same session | Chat/RAG applications |
| **Eventually** | No ordering guarantee, fastest reads | Recommendations, analytics |

```python
# Set consistency at collection level
collection = Collection("products", consistency_level="Session")

# Or per-query override
results = collection.search(
    ...,
    consistency_level="Strong"
)
```

---

## Scalability

### Distributed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client SDKs / Applications                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌─────────┐ ┌─────────┐ ┌─────────┐
              │ Proxy 1 │ │ Proxy 2 │ │ Proxy 3 │   ← Stateless, scale horizontally
              └────┬────┘ └────┬────┘ └────┬────┘
                   │           │           │
                   └───────────┼───────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     ┌────────────┐    ┌────────────┐    ┌────────────┐
     │Query Nodes │    │ Data Nodes │    │Index Nodes │
     │(Search)    │    │(Ingestion) │    │(Build idx) │
     │            │    │            │    │            │
     │Scale for   │    │Scale for   │    │Scale for   │
     │search QPS  │    │write thru  │    │build speed │
     └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │    Object Storage (S3/MinIO)  │
              │                              │
              │  /segments/                   │
              │    /collection_1/            │
              │      /segment_001.binlog     │
              │      /segment_001.idx        │
              │    /collection_2/            │
              │      /...                    │
              └──────────────────────────────┘

Key insight: Storage and Compute are SEPARATED
- Query Nodes load segments from S3 into memory
- Index Nodes build indexes and write back to S3
- Data Nodes write raw data to S3
- Any node can be scaled independently
```

### Segment-Based Storage

```
Segment Lifecycle:

  INSERT ──▶ Growing Segment (in memory, unsearchable until flushed*)
                    │
                    │  Reaches size threshold (512MB default)
                    ▼
             Sealed Segment (immutable, flushed to S3)
                    │
                    │  Index Node picks up sealed segment
                    ▼
             Indexed Segment (index built, written to S3)
                    │
                    │  Query Node loads indexed segment
                    ▼
             Searchable Segment (loaded in Query Node memory)

* Growing segments ARE searchable via streaming search (brute-force)

Segment structure on S3:
  segment_001/
  ├── insert_log/        # Raw vector data (binlog format)
  ├── delta_log/         # Delete records
  ├── stats_log/         # Segment statistics
  └── index_files/       # Built index (HNSW/IVF/DISKANN graph)
```

### Scaling Strategies

```
Scaling for 1 Billion Vectors (768d, HNSW M=16):

Memory estimate: 1B × 768 × 4 bytes = ~3TB raw vectors
                 + HNSW graph overhead (~1.5x) = ~4.5TB total

Option A: All in-memory (HNSW)
  - 48 Query Nodes × 128GB RAM each
  - Latency: 5-10ms p99
  - Cost: $$$$$

Option B: DISKANN (disk-based)
  - 12 Query Nodes × 32GB RAM + NVMe SSD
  - Latency: 20-50ms p99
  - Cost: $$

Option C: IVF_SQ8 (quantized)
  - Memory: 1B × 768 × 1 byte = ~768GB (4x compression)
  - 8 Query Nodes × 128GB RAM
  - Latency: 10-20ms p99, lower recall
  - Cost: $$$

Partition Strategy for Billion-Scale:
┌─────────────────────────────────────────┐
│  Collection: products (1B vectors)       │
│                                          │
│  Partition by region:                    │
│  ├── partition_us (300M vectors)         │
│  ├── partition_eu (250M vectors)         │
│  ├── partition_asia (350M vectors)       │
│  └── partition_other (100M vectors)      │
│                                          │
│  Search scoped to partition → 3-4x       │
│  fewer segments to scan                  │
└─────────────────────────────────────────┘
```

### Scaling Dimensions

| Component | Scale For | How |
|-----------|-----------|-----|
| Proxy Nodes | More client connections | Add proxies behind LB |
| Query Nodes | Higher search QPS | Add nodes + replicas |
| Data Nodes | Higher ingestion throughput | Add nodes + channels |
| Index Nodes | Faster index builds | Add nodes (GPU helps) |
| Object Storage | More data | S3 scales infinitely |
| Message Queue | More write channels | Add Pulsar/Kafka partitions |

---

## Production Setup

### Kubernetes Deployment

```yaml
# Option 1: Helm Chart
# helm repo add milvus https://zilliztech.github.io/milvus-helm/
# helm install milvus milvus/milvus -f values.yaml

# values.yaml (production)
cluster:
  enabled: true

proxy:
  replicas: 3
  resources:
    requests: { cpu: "2", memory: "4Gi" }
    limits: { cpu: "4", memory: "8Gi" }

queryNode:
  replicas: 6
  resources:
    requests: { cpu: "8", memory: "64Gi" }
    limits: { cpu: "16", memory: "128Gi" }

dataNode:
  replicas: 3
  resources:
    requests: { cpu: "4", memory: "16Gi" }
    limits: { cpu: "8", memory: "32Gi" }

indexNode:
  replicas: 2
  resources:
    requests: { cpu: "8", memory: "32Gi" }
    limits: { cpu: "16", memory: "64Gi" }
    # GPU for index building:
    # nvidia.com/gpu: 1

etcd:
  replicaCount: 3
  persistence:
    size: 50Gi

pulsar:
  enabled: true
  # Or use Kafka:
  # kafka:
  #   enabled: true

minio:
  mode: distributed
  replicas: 4
  persistence:
    size: 500Gi
  # Or use S3:
  # externalS3:
  #   enabled: true
  #   host: s3.amazonaws.com
  #   bucket: milvus-data
  #   accessKey: xxx
  #   secretKey: xxx
```

```yaml
# Option 2: Milvus Operator (recommended for production)
apiVersion: milvus.io/v1beta1
kind: Milvus
metadata:
  name: milvus-production
spec:
  mode: cluster
  components:
    proxy:
      replicas: 3
    queryNode:
      replicas: 6
    dataNode:
      replicas: 3
    indexNode:
      replicas: 2
  dependencies:
    etcd:
      inCluster:
        values:
          replicaCount: 3
    storage:
      external: true
      type: S3
      secretRef: milvus-s3-secret
      endpoint: s3.amazonaws.com
      bucket: milvus-production
    msgStreamType: kafka
    kafka:
      external: true
      brokerList: ["kafka-0:9092", "kafka-1:9092", "kafka-2:9092"]
```

### Hardware Requirements

| Component | CPU | Memory | Storage | GPU |
|-----------|-----|--------|---------|-----|
| Query Node | 8-16 cores | 64-256GB RAM | Local SSD (DISKANN) | Optional |
| Data Node | 4-8 cores | 16-32GB RAM | - | - |
| Index Node | 8-16 cores | 32-64GB RAM | Temp SSD | Recommended |
| Proxy | 2-4 cores | 4-8GB RAM | - | - |
| etcd | 2 cores | 8GB RAM | 50GB SSD | - |
| MinIO/S3 | 4 cores | 16GB RAM | HDD/SSD (capacity) | - |

**Memory sizing formula:**
```
Memory = num_vectors × dim × 4 bytes (float32)
       + index_overhead (varies by type)
       + scalar_field_storage

Example (100M vectors, 768d, HNSW M=16):
  Raw vectors:  100M × 768 × 4 = 307 GB
  HNSW graph:   100M × 16 × 2 × 8 = ~25 GB
  Total:        ~332 GB → 4 Query Nodes × 96GB each (with headroom)
```

### Monitoring

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                               │
│                                                                   │
│  Milvus ──(metrics)──▶ Prometheus ──▶ Grafana Dashboards        │
│                                                                   │
│  Key Metrics:                                                     │
│  ├── milvus_proxy_search_latency_ms (p50, p99)                  │
│  ├── milvus_proxy_search_qps                                     │
│  ├── milvus_querynode_segment_loaded_count                       │
│  ├── milvus_querynode_memory_usage_bytes                         │
│  ├── milvus_datanode_flush_duration_ms                           │
│  ├── milvus_indexnode_build_duration_ms                          │
│  ├── milvus_proxy_insert_rate                                    │
│  └── milvus_collection_row_count                                 │
│                                                                   │
│  Alerts:                                                          │
│  ├── Query latency p99 > 100ms                                   │
│  ├── Memory usage > 85% on Query Nodes                           │
│  ├── Insert lag (growing segments > threshold)                   │
│  └── Index build queue depth > 10                                │
└─────────────────────────────────────────────────────────────────┘
```

### Backup & Restore

```bash
# Using milvus-backup tool
# https://github.com/zilliztech/milvus-backup

# Backup
./milvus-backup create -n backup_20240101 \
  --collections product_vectors,kb_articles

# List backups
./milvus-backup list

# Restore
./milvus-backup restore -n backup_20240101 \
  --collections product_vectors
```

### Attu (GUI Management)

```
Attu provides:
├── Collection management (create, drop, load, release)
├── Data preview and query execution
├── Index management
├── System topology view
├── Performance monitoring
└── User/role management

# Deploy Attu
docker run -p 8000:3000 \
  -e MILVUS_URL=milvus-proxy:19530 \
  zilliz/attu:latest

# Or in Kubernetes
helm install attu milvus/attu --set milvusAddress=milvus-proxy:19530
```

---

## Core Concepts

### Vector Similarity Metrics

```
Distance/Similarity Functions:

┌─────────────────────────────────────────────────────────────────────┐
│  L2 (Euclidean Distance)                                            │
│  d(a,b) = sqrt(sum((a_i - b_i)^2))                                │
│  Range: [0, +inf)  Lower = more similar                            │
│  Use: When magnitude matters (raw feature vectors)                  │
├─────────────────────────────────────────────────────────────────────┤
│  IP (Inner Product)                                                  │
│  sim(a,b) = sum(a_i * b_i)                                         │
│  Range: (-inf, +inf)  Higher = more similar                        │
│  Use: Pre-normalized vectors (equivalent to cosine)                 │
├─────────────────────────────────────────────────────────────────────┤
│  COSINE (Cosine Similarity)                                         │
│  sim(a,b) = (a · b) / (|a| × |b|)                                 │
│  Range: [-1, 1]  Higher = more similar                             │
│  Use: Text embeddings, when direction matters not magnitude         │
└─────────────────────────────────────────────────────────────────────┘
```

### ANN Index Types & Benchmarks

```
Index Type Comparison:

┌──────────────┬────────────────────────────────────────────────────────┐
│ Index        │ Description                                            │
├──────────────┼────────────────────────────────────────────────────────┤
│ FLAT         │ Brute-force, 100% recall, slowest. Baseline only.     │
│ IVF_FLAT    │ Inverted file + flat scan. Good recall, moderate speed │
│ IVF_SQ8    │ IVF + scalar quantization (4x compression)             │
│ IVF_PQ     │ IVF + product quantization (10-30x compression)        │
│ HNSW       │ Graph-based. Best latency, highest memory              │
│ DISKANN    │ Disk-based graph. Low memory, SSD-dependent            │
│ GPU_IVF_FLAT│ GPU-accelerated IVF. Massive throughput batch search  │
└──────────────┴────────────────────────────────────────────────────────┘
```

### Recall@10 vs Latency Benchmarks

**128 dimensions (1M vectors)**

| Index | Params | Recall@10 | Latency (ms) | Memory (GB) |
|-------|--------|-----------|--------------|-------------|
| FLAT | - | 1.000 | 45 | 0.5 |
| IVF_FLAT | nlist=1024, nprobe=64 | 0.98 | 4.2 | 0.6 |
| IVF_SQ8 | nlist=1024, nprobe=64 | 0.96 | 3.1 | 0.2 |
| HNSW | M=16, ef=64 | 0.98 | 1.2 | 0.9 |
| HNSW | M=32, ef=128 | 0.99 | 2.1 | 1.3 |
| DISKANN | search_list=64 | 0.96 | 5.5 | 0.1 + SSD |

**768 dimensions (10M vectors)**

| Index | Params | Recall@10 | Latency (ms) | Memory (GB) |
|-------|--------|-----------|--------------|-------------|
| FLAT | - | 1.000 | 2800 | 30 |
| IVF_FLAT | nlist=4096, nprobe=128 | 0.97 | 12 | 32 |
| IVF_SQ8 | nlist=4096, nprobe=128 | 0.94 | 8 | 9 |
| HNSW | M=16, ef=64 | 0.97 | 3.5 | 48 |
| HNSW | M=32, ef=128 | 0.99 | 6.2 | 62 |
| DISKANN | search_list=128 | 0.95 | 15 | 4 + SSD |

**1536 dimensions (10M vectors)**

| Index | Params | Recall@10 | Latency (ms) | Memory (GB) |
|-------|--------|-----------|--------------|-------------|
| FLAT | - | 1.000 | 5500 | 61 |
| IVF_FLAT | nlist=4096, nprobe=128 | 0.96 | 18 | 63 |
| IVF_SQ8 | nlist=4096, nprobe=128 | 0.92 | 11 | 17 |
| HNSW | M=16, ef=64 | 0.96 | 5.8 | 92 |
| HNSW | M=32, ef=128 | 0.98 | 9.5 | 120 |
| DISKANN | search_list=128 | 0.93 | 22 | 8 + SSD |

### Index Selection Guide

```
Decision Tree:

                    ┌─────────────────────┐
                    │ What's your priority?│
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Lowest   │    │ Lowest   │    │ Highest  │
        │ Latency  │    │ Memory   │    │ Recall   │
        └────┬─────┘    └────┬─────┘    └────┬─────┘
             │               │               │
             ▼               ▼               ▼
         ┌──────┐      ┌─────────┐     ┌─────────┐
         │ HNSW │      │ DISKANN │     │IVF_FLAT │
         │      │      │   or    │     │ (high   │
         │M=32  │      │ IVF_SQ8 │     │ nprobe) │
         │ef=128│      │         │     │         │
         └──────┘      └─────────┘     └─────────┘

         ~2-6ms         ~15-25ms        ~10-18ms
         High RAM       Low RAM         Moderate RAM
         Recall:0.98+   Recall:0.93+    Recall:0.97+
```

### Hybrid Search (Scalar + Vector)

```python
# Scalar filtering is applied BEFORE or DURING vector search
# depending on filter selectivity (Milvus optimizer decides)

# Approach 1: Attribute filtering in vector search
results = collection.search(
    data=[query_vec],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 128}},
    limit=10,
    expr='category == "electronics" and price > 100 and price < 500'
)

# Approach 2: Multi-vector search with reranking (Milvus 2.4+)
from pymilvus import AnnSearchRequest, WeightedRanker

req1 = AnnSearchRequest(data=[text_vec], anns_field="text_embedding",
                         param={"metric_type": "COSINE", "params": {"ef": 64}}, limit=50)
req2 = AnnSearchRequest(data=[image_vec], anns_field="image_embedding",
                         param={"metric_type": "COSINE", "params": {"ef": 64}}, limit=50)

results = collection.hybrid_search(
    reqs=[req1, req2],
    ranker=WeightedRanker(0.6, 0.4),  # 60% text, 40% image
    limit=10
)
```

### Partitions & Dynamic Schema

```python
# Partitions for data organization (reduces search scope)
collection.create_partition("electronics")
collection.create_partition("fashion")

# Insert into specific partition
collection.insert(data, partition_name="electronics")

# Search specific partition (faster, fewer segments to scan)
collection.search(..., partition_names=["electronics"])

# Dynamic schema (JSON fields for flexible attributes)
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
    FieldSchema(name="metadata", dtype=DataType.JSON),  # flexible schema
]

# Query JSON fields
collection.search(
    ...,
    expr='metadata["brand"] == "Nike" and metadata["sizes"] array_contains 42'
)
```

### Integration with Embedding Models

| Model | Dimensions | Use Case | Latency/embed |
|-------|-----------|----------|---------------|
| OpenAI text-embedding-3-small | 1536 | General text (RAG, search) | ~20ms |
| OpenAI text-embedding-3-large | 3072 | High-accuracy text | ~30ms |
| sentence-transformers/all-mpnet-base-v2 | 768 | Self-hosted text | ~5ms (GPU) |
| BAAI/bge-large-en-v1.5 | 1024 | Self-hosted, high quality | ~8ms (GPU) |
| openai/clip-vit-large-patch14 | 768 | Image + text (multimodal) | ~15ms (GPU) |
| Cohere embed-v3 | 1024 | Multilingual text | ~15ms |

```python
# Full pipeline: embed → insert → search
from pymilvus import connections, Collection, utility

# Connect
connections.connect(host="milvus-proxy", port="19530")

# Create collection
collection = Collection("my_collection", schema)
collection.create_index("embedding", index_params)
collection.load()

# Insert
collection.insert([ids, texts, embeddings])

# Search
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param=search_params,
    limit=10,
    output_fields=["text"]
)

# Clean up
collection.release()  # Unload from memory
```

---

## Summary: When to Choose Milvus

| Scenario | Milvus Fit | Alternative |
|----------|-----------|-------------|
| >10M vectors, need horizontal scale | Excellent | - |
| <1M vectors, simple use case | Overkill | Qdrant, pgvector |
| Billion-scale, cost-sensitive | Good (DISKANN) | Pinecone (managed) |
| Multi-tenant SaaS | Good (partitions + filtering) | Weaviate |
| Real-time RAG | Excellent (HNSW, low latency) | - |
| GPU-accelerated batch search | Excellent (GPU_IVF) | FAISS (library) |
| Fully managed, zero-ops | Use Zilliz Cloud | Pinecone |
