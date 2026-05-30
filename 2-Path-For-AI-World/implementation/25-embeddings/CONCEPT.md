# Embeddings for AI Systems - Complete Guide

## Overview

Embeddings are dense vector representations of data (text, images, code) in a continuous vector space where semantic similarity corresponds to geometric proximity. They are the **foundation** of retrieval-augmented generation (RAG), semantic search, recommendation systems, and classification pipelines.

The embedding model you choose determines the **ceiling** of your retrieval quality. No amount of prompt engineering or reranking can recover information lost at the embedding stage.

---

## 1. Embedding Model Types (9 Categories)

### 1.1 General Text Embeddings
**Purpose:** Broad semantic understanding of English text.
**Examples:** OpenAI `text-embedding-3-large`, Cohere `embed-english-v3.0`, E5-large-v2
**Characteristics:**
- Trained on massive web corpora (Common Crawl, Wikipedia, StackOverflow, Reddit)
- Good at paraphrase detection, semantic similarity, clustering
- Dimensions: 768–3072
- Trade-off: breadth over depth in any single domain

**When to use:** Starting a new project, general-purpose search, when you don't have domain-specific training data.

### 1.2 Multilingual Embeddings
**Purpose:** Cross-lingual semantic understanding across 50–100+ languages.
**Examples:** Cohere `embed-multilingual-v3.0`, multilingual-e5-large, mGTE
**Characteristics:**
- Align representations across languages so "How are you?" and "Comment allez-vous?" are nearby
- Typically 5–15% worse than English-only models on English tasks
- Critical for global products
- Support script mixing (Hinglish, Spanglish)

**When to use:** Product serves multiple languages, user queries may be in any language, documents exist in multiple languages.

### 1.3 Code Embeddings
**Purpose:** Understand programming language semantics, not just string similarity.
**Examples:** Voyage `voyage-code-2`, OpenAI `text-embedding-3-large` (with code training), CodeBERT, UniXcoder
**Characteristics:**
- Understand that `for i in range(10)` and `for(int i=0; i<10; i++)` are semantically equivalent
- Handle function signatures, docstrings, variable naming patterns
- Some support cross-language code search (find Python equivalent of Java function)
- Typically trained on GitHub data

**When to use:** Code search, documentation retrieval for developers, code recommendation, duplicate detection.

### 1.4 Domain-Specific Embeddings
**Purpose:** Deep understanding of specialized vocabulary and relationships in a specific field.
**Examples:**
- Medical: PubMedBERT embeddings, BioLinkBERT
- Legal: Legal-BERT embeddings
- Financial: FinBERT embeddings
- Scientific: SPECTER2, SciBERT

**Characteristics:**
- Understand that "MI" means "myocardial infarction" not "Michigan"
- Capture domain relationships (drug-gene-disease interactions)
- Usually smaller models fine-tuned on domain corpora
- May perform worse on general text

**When to use:** Domain where general models consistently fail, specialized terminology is critical, you have domain evaluation data proving improvement.

### 1.5 Multimodal Embeddings
**Purpose:** Embed text, images, and sometimes audio/video into a shared vector space.
**Examples:** CLIP, SigLIP, ImageBind, Nomic Embed Vision
**Characteristics:**
- Can search images with text queries and vice versa
- Typically 512–1024 dimensions
- Image understanding is "conceptual" not "pixel-precise"
- Text understanding is often weaker than text-only models

**When to use:** Image search with text queries, product catalogs with images, multimodal RAG, visual question answering.

### 1.6 Sparse Embeddings (Learned Sparse)
**Purpose:** Token-level importance weights, combining neural understanding with term-matching precision.
**Examples:** SPLADE, SPLADEv2, DeepImpact, EPIC
**Characteristics:**
- Output is a sparse vector (mostly zeros) over vocabulary
- Naturally handles exact term matching (product IDs, names, codes)
- Interpretable: you can see which terms got high weights
- Complementary to dense embeddings (hybrid search)
- Dimensions: vocabulary size (30k–50k) but only 100–300 non-zero

**When to use:** Hybrid search alongside dense vectors, when exact keyword matching matters, product search, when interpretability is required.

### 1.7 Late-Interaction Embeddings
**Purpose:** Per-token embeddings with deferred interaction for higher relevance accuracy.
**Examples:** ColBERT, ColBERTv2, PLAID
**Characteristics:**
- Instead of single vector per document, stores one vector per token
- Query-document scoring via MaxSim (max similarity between each query token and all doc tokens)
- Much higher storage cost (100x+ vs single-vector)
- Significantly better on complex queries
- Can be compressed with techniques like PLAID

**When to use:** When retrieval accuracy is paramount and you can afford storage, complex multi-faceted queries, when single-vector models plateau.

### 1.8 Small/Efficient Embeddings
**Purpose:** Fast, low-resource embedding for edge deployment or cost optimization.
**Examples:** all-MiniLM-L6-v2, gte-small, nomic-embed-text-v1 (137M params), snowflake-arctic-embed-xs
**Characteristics:**
- 384 dimensions, 20–130M parameters
- 5–10x faster inference than large models
- 80–90% of large model quality
- Can run on CPU in production
- Low memory footprint

**When to use:** High-throughput systems, edge deployment, cost-sensitive applications, when 90% quality is acceptable, real-time embedding generation.

### 1.9 Large/Frontier Embeddings
**Purpose:** Maximum embedding quality regardless of cost.
**Examples:** OpenAI `text-embedding-3-large` (3072d), Cohere `embed-v3` (1024d), Voyage AI `voyage-large-2` (1536d), NV-Embed-v2
**Characteristics:**
- 1024–3072+ dimensions
- State-of-the-art on MTEB benchmarks
- Higher latency and cost
- May support Matryoshka (dimension reduction without retraining)
- Best for offline batch processing or low-QPS systems

**When to use:** Quality-critical applications, small corpus where storage isn't an issue, when you've proven small models are insufficient.

---

## 2. Embedding Architecture Choices (8 Decisions)

### 2.1 Dense vs Sparse

| Aspect | Dense | Sparse (SPLADE) |
|--------|-------|-----------------|
| Vector type | Float array [0.02, -0.15, ...] | Sparse dict {token: weight} |
| Dimensions | 384–3072 | 30k vocabulary, ~200 non-zero |
| Semantic matching | Excellent | Good |
| Exact term matching | Poor | Excellent |
| Storage per doc | dim × 4 bytes | ~200 × 8 bytes |
| Interpretability | Opaque | Transparent |
| Best for | Paraphrase, concept search | Keyword, product ID, names |

**Decision framework:**
- Pure semantic search → Dense
- Pure keyword search → Sparse (or BM25)
- Production search system → **Hybrid (Dense + Sparse)** with fusion

### 2.2 Single-Vector vs Late-Interaction

| Aspect | Single-Vector (Bi-encoder) | Late-Interaction (ColBERT) |
|--------|---------------------------|---------------------------|
| Vectors per doc | 1 | ~N (one per token) |
| Storage | dim × 4 bytes | N × dim × 4 bytes |
| Index type | Standard ANN | Specialized (PLAID) |
| Query latency | Fast (single lookup) | Slower (multi-vector scoring) |
| Quality | Good | Significantly better |
| Scaling | Easy | Complex |

**Decision framework:**
- < 1M documents, need maximum quality → Consider ColBERT
- > 10M documents, need fast retrieval → Single-vector + reranker
- Most production systems → Single-vector with cross-encoder reranker gives 95% of ColBERT quality

### 2.3 Small vs Large Dimension

| Dimension | Storage/doc | Quality (MTEB avg) | Use Case |
|-----------|------------|--------------------| ---------|
| 384 | 1.5 KB | ~58% | High-throughput, edge |
| 768 | 3 KB | ~62% | Balanced |
| 1024 | 4 KB | ~64% | Good quality |
| 1536 | 6 KB | ~65% | High quality |
| 3072 | 12 KB | ~66% | Maximum quality |

**Matryoshka embeddings:** Models like OpenAI's `text-embedding-3-large` support truncating dimensions (e.g., use first 256 of 3072) with graceful quality degradation. This lets you:
- Store 256d in the index for fast ANN search
- Store full 3072d for reranking top candidates
- Tune dimension per use case without retraining

**Decision framework:**
- Start with the model's native dimension
- If storage/latency is a problem, try Matryoshka truncation
- Measure recall at each dimension on YOUR data before deciding

### 2.4 General vs Domain-Specific

**Decision framework:**
1. Establish baseline with best general model on your evaluation set
2. If recall@10 > 90% → Stay with general model
3. If recall@10 < 80% → Investigate domain-specific model or fine-tuning
4. If 80-90% → Try fine-tuning general model first (cheaper than training from scratch)

**Symptoms that you need domain-specific:**
- Domain jargon consistently misunderstood
- Acronyms resolved incorrectly
- Hierarchical relationships missed (drug classes, legal precedent chains)
- Numbers and codes are semantically important

### 2.5 Multilingual Strategy

**Options:**
1. **Single multilingual model** - Simplest, one index, cross-lingual search works
2. **Language-specific models** - Best quality per language, complex routing
3. **Translate-then-embed** - Translate to English, use English model. Simple but adds latency/cost

**Decision framework:**
- < 5 languages, English dominant → Translate-then-embed
- 5–20 languages, cross-lingual search needed → Single multilingual model
- Mission-critical per-language quality → Language-specific models with routing

### 2.6 Multimodal Strategy

**Options:**
1. **Shared space (CLIP-style)** - Text and images in same vector space
2. **Separate spaces + fusion** - Best text model + best image model, fuse at retrieval
3. **Text-only with image captions** - Caption images with VLM, embed captions as text

**Decision framework:**
- Text-to-image search required → Shared space (CLIP/SigLIP)
- Best text quality + image support → Caption approach
- Research/experimentation → Separate spaces with learned fusion

### 2.7 Normalized Vectors

**Normalization:** L2-normalizing vectors so ||v|| = 1. After normalization:
- Cosine similarity = Dot product (cheaper to compute)
- All vectors lie on unit hypersphere
- Euclidean distance is monotonically related to cosine similarity

**Most embedding models output normalized vectors by default.** Always verify:
```python
import numpy as np
embedding = get_embedding("test")
norm = np.linalg.norm(embedding)
assert abs(norm - 1.0) < 0.01, f"Not normalized: norm={norm}"
```

**Decision:** Always normalize unless your model specifically requires unnormalized (rare). Use dot product for similarity (fastest).

### 2.8 Embedding Versioning

**The Problem:** When you change embedding models, old and new vectors are **incompatible**. You cannot mix them in the same index.

**Strategy:**
```
Collection: documents_v3  (model: text-embedding-3-large)
Collection: documents_v2  (model: text-embedding-ada-002)  [deprecated]
```

**Metadata to track per embedding:**
- `embedding_model`: exact model identifier
- `embedding_version`: your internal version number
- `embedding_date`: when generated
- `embedding_dimensions`: vector size
- `source_text_hash`: detect if source changed

---

## 3. How to Choose Embeddings (8-Step Process)

### Step 1: Define Your Data Characteristics
- **Language(s):** English-only? Multilingual? Code?
- **Document length:** Sentences? Paragraphs? Full documents?
- **Domain:** General web? Medical? Legal? Financial?
- **Modalities:** Text-only? Text + images? Code + docs?
- **Vocabulary:** Standard English? Heavy jargon? Acronyms?

### Step 2: Define Your Query Characteristics
- **Query length:** Keywords? Natural language questions? Long descriptions?
- **Query type:** Factual lookup? Conceptual search? Example-based?
- **Query language:** Same as documents? Could be different?
- **Expected behavior:** Exact match important? Semantic equivalence?

### Step 3: Define Constraints
- **Latency budget:** < 50ms? < 200ms? < 1s?
- **Cost budget:** Per-query cost ceiling? Monthly embedding budget?
- **Storage budget:** How many vectors? RAM vs disk?
- **Infrastructure:** Cloud API OK? Must be self-hosted? Edge deployment?
- **Privacy:** Can data leave your network?

### Step 4: Select Candidate Models (3–5 models)
Based on Steps 1–3, shortlist models:
- If general English text → OpenAI ada-3-large, Cohere embed-v3, E5-large-v2
- If multilingual → Cohere multilingual-v3, multilingual-e5-large
- If code → Voyage code-2, OpenAI with code
- If cost-sensitive → all-MiniLM-L6-v2, gte-small, nomic-embed-text
- If maximum quality → OpenAI 3-large, Voyage large-2, NV-Embed-v2

### Step 5: Create Evaluation Dataset
**Minimum 200 query-document pairs** with relevance judgments:
- 50 easy (obvious keyword overlap)
- 50 medium (paraphrased, synonyms)
- 50 hard (conceptual, multi-hop reasoning)
- 50 adversarial (misleading keywords, negation, no-answer)

**Source these from:**
- Real user queries (if available)
- Synthetic generation with LLM
- Domain expert annotation
- Query logs from existing search

### Step 6: Run Evaluation
For each candidate model:
```
Recall@1, @5, @10, @20, @50, @100
MRR (Mean Reciprocal Rank)
nDCG@10
Latency (p50, p95, p99)
Cost per 1000 embeddings
```

### Step 7: Statistical Analysis
- Don't just pick highest number—check if differences are statistically significant
- Use paired t-test or bootstrap confidence intervals
- A 1% improvement that isn't significant isn't worth the complexity

### Step 8: Production Validation
- A/B test with real users if possible
- Monitor retrieval quality over time (embedding drift)
- Plan for model updates (new versions released quarterly)

---

## 4. Benchmark Slices to Test (10 Types)

### 4.1 Exact Terms
**What:** Queries that should match documents containing exact same terms.
**Example:** Query "RFC 7231 HTTP semantics" → Document containing "RFC 7231"
**Why:** Tests whether embeddings preserve exact term matching or over-generalize.
**Failure mode:** Model embeds "RFC 7231" close to general HTTP documents, missing the specific RFC.

### 4.2 Paraphrased Questions
**What:** Query expressed differently from how the answer is written in documents.
**Example:** Query "How do I stop my program from crashing?" → Document "Exception handling prevents application termination"
**Why:** Core semantic matching capability.
**Failure mode:** Model is too lexical and misses paraphrases.

### 4.3 Multi-Hop
**What:** Queries requiring information from multiple document sections.
**Example:** Query "What's the pricing for the enterprise plan in Europe?" → Needs both pricing doc AND regional availability doc.
**Why:** Tests whether embeddings can surface partial matches that together answer the question.
**Failure mode:** Neither partial document ranks highly because neither fully matches.

### 4.4 No-Answer Queries
**What:** Queries where no document in the corpus has the answer.
**Example:** Query about a feature you don't have, or a topic outside your domain.
**Why:** Tests if the system can recognize low confidence (low similarity scores).
**Failure mode:** System always returns something with high confidence, causing hallucination downstream.

### 4.5 Stale Documents
**What:** Queries where old versions of documents exist alongside new versions.
**Example:** Query "current API rate limits" → Old doc says "100 req/min", new doc says "1000 req/min"
**Why:** Tests metadata filtering integration—embeddings alone can't know what's current.
**Failure mode:** Old document ranks equally or higher than current version.

### 4.6 Permission-Sensitive
**What:** Queries where the answer exists but shouldn't be returned to certain users.
**Example:** Query about salary data when user doesn't have HR access.
**Why:** Tests that permission filtering is applied BEFORE or DURING retrieval, not after.
**Failure mode:** Sensitive documents appear in results, relying on post-retrieval filtering.

### 4.7 Multilingual
**What:** Queries in one language, documents in another.
**Example:** Query in Spanish → Document in English
**Why:** Tests cross-lingual transfer quality.
**Failure mode:** Model only retrieves documents in query language.

### 4.8 Table-Heavy Documents
**What:** Queries about structured data in tables.
**Example:** Query "What's the memory limit for t3.medium?" → Answer is in an AWS instance type table.
**Why:** Embeddings of table text are often poor because tables lose structure when linearized.
**Failure mode:** Table rows embed to similar vectors (all look like "instance type specs").

### 4.9 Short Vague Queries
**What:** One or two word queries with ambiguous intent.
**Example:** Query "pricing" or "deploy" or "error"
**Why:** Tests how model handles underspecified queries.
**Failure mode:** Returns random documents since everything is equidistant from a vague query.

### 4.10 Adversarial Queries
**What:** Queries designed to trick the embedding model.
**Example:** "I do NOT want information about Python" → Should NOT return Python docs.
**Example:** "cheap alternatives to expensive product X" → Should not return X's marketing page.
**Why:** Tests robustness to negation, contrast, and misleading signals.
**Failure mode:** Model ignores negation words and matches on "Python" or "product X".

---

## 5. Embedding Migration Rule

> **"Treat embedding model change like a database schema migration."**

### Why This Rule Exists
- Old embeddings and new embeddings are **incompatible vectors**
- You cannot cosine-similarity compare a vector from model A with a vector from model B
- You cannot incrementally update—ALL vectors must be regenerated
- A bad migration can take down your entire search system

### Migration Principles

1. **Never mix embedding versions in the same index**
   - Even if dimensions match, the vector spaces are different
   - Results will be nonsensical

2. **Always run old and new in parallel before switching**
   - Generate new embeddings into a shadow index
   - Compare retrieval quality on evaluation set
   - Only switch when new provably better

3. **Keep old index alive until rollback window closes**
   - Typical: 2 weeks after migration
   - Monitor quality metrics daily
   - Have one-click rollback ready

4. **Budget for full re-embedding cost**
   - 1M documents × $0.13/1M tokens (OpenAI) = relatively cheap for API
   - But: compute time, rate limits, validation time
   - For large corpora: plan for days/weeks of re-embedding

5. **Version everything**
   ```
   index_name: docs_v{version}_{model_short_name}
   metadata: {model, version, date, config}
   ```

---

## 6. Embedding Model Comparison

| Model | Provider | Dimensions | MTEB Avg | Cost (per 1M tokens) | Max Tokens | Notes |
|-------|----------|-----------|----------|----------------------|------------|-------|
| text-embedding-3-large | OpenAI | 3072 (Matryoshka) | ~64.6 | $0.13 | 8191 | Matryoshka support, can truncate to 256d |
| text-embedding-3-small | OpenAI | 1536 | ~62.3 | $0.02 | 8191 | 5x cheaper, good quality |
| embed-english-v3.0 | Cohere | 1024 | ~64.5 | $0.10 | 512 | Input type parameter (search_doc/search_query) |
| embed-multilingual-v3.0 | Cohere | 1024 | ~63.0 | $0.10 | 512 | 100+ languages |
| voyage-large-2 | Voyage AI | 1536 | ~64.8 | $0.12 | 16000 | Long context, great for documents |
| voyage-code-2 | Voyage AI | 1536 | Best for code | $0.12 | 16000 | Specialized for code |
| bge-large-en-v1.5 | BAAI | 1024 | ~63.0 | Free (self-host) | 512 | Open source, Apache 2.0 |
| e5-large-v2 | Microsoft | 1024 | ~62.0 | Free (self-host) | 512 | Requires "query: " prefix |
| e5-mistral-7b-instruct | Microsoft | 4096 | ~66.6 | Free (self-host) | 32768 | LLM-based, expensive to run |
| instructor-xl | hkunlp | 768 | ~61.0 | Free (self-host) | 512 | Task-specific instructions |
| gte-large-en-v1.5 | Alibaba | 1024 | ~63.5 | Free (self-host) | 8192 | Long context, open source |
| nomic-embed-text-v1.5 | Nomic | 768 | ~62.0 | Free (self-host) | 8192 | Matryoshka, long context |
| all-MiniLM-L6-v2 | SBERT | 384 | ~56.0 | Free (self-host) | 256 | Ultra-fast, tiny |
| NV-Embed-v2 | NVIDIA | 4096 | ~69.3 | Free (self-host) | 32768 | SOTA on MTEB, huge model |
| snowflake-arctic-embed-l | Snowflake | 1024 | ~63.8 | Free (self-host) | 512 | Excellent open-source option |

### Choosing Between API and Self-Hosted

**Use API (OpenAI/Cohere/Voyage) when:**
- < 10M embeddings to generate
- Don't want to manage GPU infrastructure
- Need quick start
- Data can leave your network

**Use Self-Hosted when:**
- Data privacy requirements (PII, HIPAA, classified)
- Very high throughput needs (> 1M embeddings/day ongoing)
- Cost optimization at scale
- Need model fine-tuning
- Offline/air-gapped environments

---

## 7. Embedding Fine-Tuning

### When to Fine-Tune
- General model recall@10 < 85% on your evaluation set
- Domain-specific terminology consistently misunderstood
- You have > 10,000 query-document positive pairs
- You've already optimized chunking and retrieval pipeline

### When NOT to Fine-Tune
- Haven't tried multiple off-the-shelf models yet
- Don't have a proper evaluation dataset
- Problem is in chunking, not embedding quality
- < 1000 training pairs available

### How to Fine-Tune

**Training Data Format:**
```json
{"query": "What are the side effects of metformin?", "positive": "Metformin commonly causes GI upset...", "negative": "Metformin is a biguanide class..."}
```

**Key Techniques:**
1. **Contrastive Learning (InfoNCE loss):** Pull query close to positive, push away from negatives
2. **Hard Negative Mining:** Use current model to find near-misses as hard negatives
3. **In-Batch Negatives:** Other batch items as negatives (memory efficient)
4. **Matryoshka Training:** Supervise at multiple dimension truncations

**Expected Improvement:** 5–15% recall improvement on domain-specific queries with good training data.

**Risks:**
- Catastrophic forgetting (loses general capability)
- Overfitting to training distribution
- Evaluation contamination (training on test queries)

---

## 8. Embedding Caching Strategies

### Why Cache
- Same text embedded multiple times wastes money and time
- Document chunks don't change often
- Queries repeat (20% of queries = 80% of traffic)

### Cache Key Design
```python
cache_key = hash(model_name + model_version + text + input_type)
```

### Cache Layers

1. **In-Memory LRU Cache (Hot)**
   - Last 10,000 embeddings
   - Sub-millisecond lookup
   - For repeated queries

2. **Redis/Memcached (Warm)**
   - Last 1M embeddings
   - 1–5ms lookup
   - Shared across service instances

3. **Database/S3 (Cold)**
   - All ever-generated embeddings
   - Keyed by (text_hash, model_version)
   - For re-indexing without re-embedding unchanged chunks

### Cache Invalidation
- Model version change → invalidate ALL (different vector space)
- Text change → invalidate that text's entry
- TTL: embeddings don't expire unless model changes

### Cost Impact
Typical cache hit rates:
- Query embeddings: 30–60% hit rate (queries repeat)
- Document embeddings: 90%+ hit rate (documents rarely change)
- Estimated cost savings: 40–70% of embedding API costs

---

## 9. Embedding Versioning in Production

### Version Schema
```
{service}_embeddings_v{major}_{model_short}
Example: search_embeddings_v3_oai3large
```

### Version Metadata
```json
{
  "version": 3,
  "model": "text-embedding-3-large",
  "dimensions": 1024,
  "created_at": "2024-03-15T00:00:00Z",
  "config": {
    "truncate_dim": 1024,
    "normalize": true,
    "input_type": "search_document"
  },
  "evaluation": {
    "recall_at_10": 0.92,
    "mrr": 0.87,
    "eval_dataset": "eval_v2_500_queries"
  },
  "status": "active",
  "previous_version": 2,
  "rollback_available_until": "2024-04-15T00:00:00Z"
}
```

### Deployment Pattern
```
v2 (active, serving traffic)
    ↓ [deploy v3 shadow]
v2 (active) + v3 (shadow, generating embeddings)
    ↓ [evaluate v3, confirm better]
v2 (draining) + v3 (active, serving traffic)
    ↓ [rollback window passes]
v3 (active) — v2 deleted
```

### Monitoring in Production
- Track similarity score distributions (sudden drop = problem)
- Track recall on golden set (run weekly)
- Track latency (new model may be slower)
- Alert on: mean similarity drop > 10%, recall drop > 5%, latency p95 > threshold
