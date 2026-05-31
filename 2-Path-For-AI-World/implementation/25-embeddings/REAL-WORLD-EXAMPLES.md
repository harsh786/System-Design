# Real-World Examples: Embeddings in Production

## Case Study 1: Migrating from OpenAI ada-002 to text-embedding-3-large

### Background

A Series C fintech company (450 employees) running a customer support RAG system with 2.3M document chunks embedded using `text-embedding-ada-002`. Their retrieval quality was acceptable but declining as their knowledge base grew to cover 14 product lines across 6 languages.

### The Evaluation Process

**Phase 1: Identifying the Problem (Week 1)**

The team noticed retrieval quality degradation through their monitoring:
- Recall@10 dropped from 0.82 to 0.71 over 6 months
- Users clicking "This wasn't helpful" increased from 8% to 14%
- Multilingual queries (Spanish, Portuguese) had 23% lower relevance scores

**Phase 2: Building an Evaluation Harness (Weeks 2-3)**

```python
# Their evaluation framework
class EmbeddingEvaluator:
    def __init__(self, test_queries: list[dict]):
        """
        test_queries format:
        [{"query": "How do I reset my API key?",
          "relevant_doc_ids": ["doc_442", "doc_891"],
          "language": "en",
          "category": "account_management"}]
        """
        self.test_queries = test_queries  # 1,200 manually curated pairs
        self.metrics = {}

    def evaluate_model(self, model_name: str, embed_fn: callable):
        results = {
            "recall@5": [], "recall@10": [], "recall@20": [],
            "mrr": [], "latency_ms": [], "cost_per_1k": []
        }
        for query_set in self.test_queries:
            query_embedding = embed_fn(query_set["query"])
            # Search against pre-embedded corpus for this model
            retrieved = self.vector_search(query_embedding, k=20)
            relevant = set(query_set["relevant_doc_ids"])
            
            results["recall@5"].append(
                len(set(retrieved[:5]) & relevant) / len(relevant)
            )
            results["recall@10"].append(
                len(set(retrieved[:10]) & relevant) / len(relevant)
            )
        return {k: np.mean(v) for k, v in results.items()}
```

**Phase 3: Head-to-Head Comparison (Week 4)**

They tested against a representative 50K chunk subset:

| Metric | ada-002 (1536d) | 3-small (1536d) | 3-large (3072d) | 3-large (1024d) |
|--------|----------------|-----------------|-----------------|-----------------|
| Recall@10 (EN) | 0.71 | 0.74 | 0.83 | 0.79 |
| Recall@10 (ES) | 0.58 | 0.69 | 0.78 | 0.74 |
| Recall@10 (PT) | 0.55 | 0.67 | 0.76 | 0.72 |
| MRR | 0.64 | 0.68 | 0.77 | 0.73 |
| Latency (p50) | 42ms | 38ms | 85ms | 45ms |
| Cost/1M tokens | $0.10 | $0.02 | $0.13 | $0.13 |

**Key insight**: `text-embedding-3-large` at 1024 dimensions (using Matryoshka reduction) gave 80% of the quality gain at 33% of the storage cost vs full 3072d.

### The Migration Strategy

**Phase 4: Dual-Write Architecture (Weeks 5-7)**

```python
class DualEmbeddingPipeline:
    """Run both old and new embeddings in parallel during migration."""
    
    def __init__(self):
        self.old_collection = "documents_ada002"
        self.new_collection = "documents_3large"
        self.migration_progress = Redis()  # Track progress
    
    async def ingest_new_document(self, doc: Document):
        """New documents get both embeddings."""
        old_emb = await self.embed_ada002(doc.text)
        new_emb = await self.embed_3large(doc.text)
        
        await asyncio.gather(
            self.qdrant.upsert(self.old_collection, old_emb, doc.id),
            self.qdrant.upsert(self.new_collection, new_emb, doc.id),
        )
    
    async def backfill_batch(self, doc_ids: list[str], batch_size=100):
        """Background job re-embeds existing documents."""
        for batch in chunked(doc_ids, batch_size):
            docs = await self.fetch_documents(batch)
            texts = [d.text for d in docs]
            
            # Batch embedding call (much cheaper)
            embeddings = await self.embed_3large_batch(texts)
            
            points = [
                PointStruct(id=doc.id, vector=emb, payload=doc.metadata)
                for doc, emb in zip(docs, embeddings)
            ]
            await self.qdrant.upsert(self.new_collection, points)
            
            # Track progress
            self.migration_progress.incrby("migrated_count", len(batch))
```

**Phase 5: Shadow Traffic (Week 8)**

They ran 100% of production queries against both collections, logging results without serving from the new collection:

```python
async def search_with_shadow(self, query: str):
    """Serve from old, compare with new."""
    old_results = await self.search(self.old_collection, query)
    
    # Fire-and-forget shadow query
    asyncio.create_task(self._shadow_search(query, old_results))
    
    return old_results

async def _shadow_search(self, query: str, old_results):
    new_results = await self.search(self.new_collection, query)
    
    # Log comparison metrics
    overlap = set(r.id for r in old_results[:10]) & set(r.id for r in new_results[:10])
    self.metrics.log("shadow_overlap_ratio", len(overlap) / 10)
    self.metrics.log("shadow_new_top1_score", new_results[0].score)
```

**Phase 6: Gradual Cutover (Weeks 9-10)**

- 5% traffic → new collection (monitored for 48 hours)
- 25% traffic → new collection (monitored for 72 hours)
- 50% → 75% → 100% over the following week
- Old collection kept warm for 30 days as rollback

### Results

After full migration:
- Recall@10 improved from 0.71 to 0.79 (using 1024d Matryoshka)
- "Not helpful" clicks dropped from 14% to 7.2%
- Multilingual recall improved by 31% average
- Storage decreased by 33% (1024d vs 1536d)
- Monthly embedding cost increased by 30% but retrieval quality justified it
- Total migration cost: ~$4,200 in re-embedding compute for 2.3M chunks

---

## Case Study 2: How Cohere Built embed-v3 for Multilingual Excellence

### The Problem with Prior Approaches

Cohere's embed-v2 was competitive on English benchmarks but lagged on multilingual retrieval. The core challenge: most training data is English-centric, so models develop an English-biased representation space where non-English queries map poorly to non-English documents.

### Architecture Decisions in embed-v3

**Training Data Strategy:**
- 100+ languages with deliberate upsampling of low-resource languages
- Cross-lingual pairs: query in language A, relevant document in language B
- Synthetic hard negatives generated per-language using language-specific LLMs
- Total training pairs: ~1B (compared to ~500M for v2)

**Key Innovation: Compression-Aware Training**

Cohere trained embed-v3 with awareness that users would apply binary quantization:

```
During training:
1. Compute full float32 embedding
2. Apply simulated binary quantization (sign function with straight-through estimator)
3. Compute loss on BOTH the float and binary representations
4. Backpropagate through both paths

Result: The model learns to push dimensions away from zero,
making binary quantization lose less information.
```

This is why embed-v3 with binary quantization retains ~95% of float32 quality, while competing models lose 10-15%.

**Input Type Differentiation:**

embed-v3 accepts an `input_type` parameter: `search_query`, `search_document`, `classification`, `clustering`. This isn't just prompt engineering — the model has separate learned projection heads:

```python
# Conceptual architecture
class EmbedV3(nn.Module):
    def forward(self, text, input_type):
        base_repr = self.transformer(text)  # Shared backbone
        
        if input_type == "search_query":
            return self.query_projector(base_repr)  # Asymmetric
        elif input_type == "search_document":
            return self.doc_projector(base_repr)
        elif input_type == "classification":
            return self.classification_projector(base_repr)
        # ...
```

### Benchmark Results (MTEB Multilingual Subset)

| Model | avg (15 langs) | Retrieval | Classification | Clustering |
|-------|---------------|-----------|----------------|------------|
| embed-v3 | 66.3 | 59.7 | 78.2 | 52.1 |
| text-embedding-3-large | 64.1 | 57.8 | 76.5 | 49.8 |
| multilingual-e5-large | 61.5 | 55.2 | 74.1 | 47.3 |
| BGE-M3 | 63.8 | 58.9 | 72.4 | 50.1 |

### Production Implications

Teams choosing embed-v3 for multilingual workloads gain:
- Better cross-lingual retrieval (query in English, doc in Japanese)
- Superior binary quantization compatibility (32x storage reduction with 5% quality loss)
- Explicit task-type optimization (don't use the same embedding for search and clustering)

---

## MTEB Leaderboard: Practical Comparison for Real Use Cases

### Understanding MTEB (Massive Text Embedding Benchmark)

MTEB evaluates embeddings across 7 task categories with 56+ datasets. Here's how top models perform as of early 2024, and what it means for architecture decisions:

### Retrieval-Focused Use Cases (RAG, Search)

If your primary use case is retrieval (finding relevant documents given a query):

| Model | MTEB Retrieval Avg | Dimensions | Max Tokens | API/Open |
|-------|-------------------|------------|------------|----------|
| voyage-3 | 67.8 | 1024 | 32K | API |
| text-embedding-3-large | 66.2 | 3072 | 8191 | API |
| NV-Embed-v2 | 69.1 | 4096 | 32K | Open |
| SFR-Embedding-2 | 68.3 | 4096 | 32K | Open |
| BGE-en-icl | 67.5 | 4096 | 32K | Open |
| embed-v3 (Cohere) | 65.9 | 1024 | 512 | API |
| GTE-Qwen2-7B | 67.2 | 3584 | 32K | Open |

**Decision framework for retrieval:**
- Need long context (>8K tokens)? → voyage-3 or NV-Embed-v2
- Budget-constrained with high volume? → text-embedding-3-small (cheaper, decent quality)
- Must self-host for compliance? → NV-Embed-v2 or GTE-Qwen2-7B
- Multilingual retrieval? → embed-v3 or BGE-M3

### Classification Use Cases (Intent Detection, Sentiment)

| Model | MTEB Classification Avg | Notes |
|-------|------------------------|-------|
| GTE-Qwen2-7B | 85.4 | Best but 7B params, expensive to self-host |
| voyage-3 | 83.1 | Best API option |
| text-embedding-3-large | 82.5 | Good balance |
| all-MiniLM-L6-v2 | 74.2 | Fast, 22M params, good for edge |

**Key insight**: For classification, you often don't need the biggest model. A fine-tuned smaller model frequently beats a general-purpose large model on your specific taxonomy.

### Clustering Use Cases (Topic Modeling, Deduplication)

| Model | MTEB Clustering Avg | Notes |
|-------|---------------------|-------|
| SFR-Embedding-2 | 56.2 | Best overall |
| NV-Embed-v2 | 55.8 | Close second |
| text-embedding-3-large | 51.3 | Adequate |
| all-MiniLM-L6-v2 | 42.1 | Struggles with nuance |

**Key insight**: Clustering is the hardest task for embeddings. If clustering quality is critical, strongly consider fine-tuning or using a specialized model.

---

## Fine-Tuning Embeddings: Legal Firm Case Study

### Background

A top-20 US law firm with 1.2M legal documents needed their RAG system to understand legal terminology nuances:
- "consideration" (legal: something of value exchanged) vs (common: thoughtful regard)
- "discovery" (legal: pre-trial evidence process) vs (common: finding something)
- "execution" (legal: signing a document) vs (common: carrying out a plan)

Their baseline system using `text-embedding-3-large` had Recall@10 of 0.68 on their legal test set, vs 0.81 on general English.

### Training Data Preparation

**Step 1: Mining Hard Negatives from Production Logs**

```python
class LegalHardNegativeMiner:
    """
    Find cases where the model retrieved wrong documents
    that a legal expert marked as irrelevant.
    """
    def mine_from_feedback(self, feedback_log: list[dict]):
        triplets = []
        for entry in feedback_log:
            query = entry["query"]
            # Documents the lawyer said were relevant
            positives = entry["relevant_doc_ids"]
            # Documents the model ranked highly but lawyer rejected
            hard_negatives = entry["rejected_doc_ids"]
            
            for pos_id in positives:
                for neg_id in hard_negatives:
                    triplets.append({
                        "query": query,
                        "positive": self.get_doc_text(pos_id),
                        "negative": self.get_doc_text(neg_id),
                    })
        return triplets  # ~15,000 triplets from 6 months of feedback
```

**Step 2: Augmentation with Legal Paraphrases**

```python
# Used GPT-4 to generate legal query variations
augmentation_prompt = """
Given this legal research query, generate 5 paraphrases that a lawyer
might use to search for the same concept. Maintain legal precision.

Original: "What constitutes adequate consideration in a unilateral contract?"
Paraphrases:
1. "Sufficiency of consideration for unilateral agreements"
2. "Is forbearance valid consideration in one-sided contracts?"
3. "Consideration requirements when only one party is bound"
...
"""
```

**Step 3: Final Training Dataset**

- 15,000 hard negative triplets from production feedback
- 8,000 synthetic triplets from legal textbook Q&A pairs
- 12,000 augmented triplets from paraphrase generation
- Total: 35,000 training triplets, 3,500 validation triplets

### Fine-Tuning Method

They used the Sentence Transformers library with Multiple Negatives Ranking Loss on a base `BAAI/bge-large-en-v1.5` model:

```python
from sentence_transformers import SentenceTransformer, losses, InputExample
from torch.utils.data import DataLoader

model = SentenceTransformer("BAAI/bge-large-en-v1.5")

train_examples = [
    InputExample(texts=[t["query"], t["positive"], t["negative"]])
    for t in training_triplets
]

train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=32)
train_loss = losses.MultipleNegativesRankingLoss(model)

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=500,
    evaluation_steps=1000,
    evaluator=retrieval_evaluator,  # Custom legal eval set
    output_path="models/legal-bge-large-ft",
    use_amp=True,  # Mixed precision for faster training
)
```

**Training infrastructure**: 2x A100 80GB, ~4 hours total training time.

### Results

| Metric | Base BGE-large | Fine-tuned | Improvement |
|--------|---------------|------------|-------------|
| Recall@10 (legal queries) | 0.69 | 0.81 | +12.3% |
| Recall@10 (general queries) | 0.79 | 0.78 | -1.0% |
| MRR (legal) | 0.55 | 0.67 | +12.0% |
| "Consideration" disambiguation | 42% correct | 89% correct | +47pp |
| Latency (p50) | 12ms | 12ms | No change |

**Critical observation**: General query performance barely degraded (-1%), meaning the model learned legal semantics without catastrophic forgetting.

### Cost Analysis

- Training compute: ~$50 (4 hours on 2x A100 spot instances)
- Data preparation (lawyer time): ~$15,000 (3 weeks of associate feedback curation)
- Ongoing maintenance: Re-fine-tune quarterly with new feedback (~$200/quarter compute)
- ROI: Lawyers reported 20% faster research time → ~$500K/year productivity gain

---

## Embedding Dimensions: When 256d Is Enough vs When You Need 3072d

### The Experiment

A search startup ran controlled experiments on their 5M document corpus across different dimensionality:

**Setup:**
- Model: `text-embedding-3-large` with Matryoshka dimension reduction
- Corpus: 5M chunks from technical documentation
- Test set: 2,000 queries with human-labeled relevance
- Vector DB: Qdrant with HNSW index

### Results by Dimension

| Dimensions | Recall@10 | Storage (5M vectors) | Index Build Time | Query Latency (p95) |
|-----------|-----------|---------------------|-----------------|-------------------|
| 256 | 0.72 | 4.9 GB | 8 min | 3.2ms |
| 512 | 0.77 | 9.8 GB | 14 min | 4.1ms |
| 1024 | 0.81 | 19.5 GB | 26 min | 5.8ms |
| 1536 | 0.83 | 29.3 GB | 38 min | 7.2ms |
| 3072 | 0.84 | 58.6 GB | 71 min | 12.4ms |

### Decision Guidelines

**256 dimensions are sufficient when:**
- Your corpus is <500K documents (less ambiguity to resolve)
- Queries are simple keyword-like patterns ("reset password steps")
- You need edge deployment (mobile, IoT)
- Cost is primary constraint and 0.72 recall is acceptable
- You're doing coarse filtering before a reranker

**1024 dimensions hit the sweet spot when:**
- Corpus is 1M-50M documents
- Queries are natural language with moderate complexity
- You have standard cloud infrastructure
- You want 95% of max quality at 33% of max storage

**3072 dimensions are justified when:**
- Subtle semantic distinctions matter (legal, medical, scientific)
- Corpus has many near-duplicate documents that need disambiguation
- You're NOT using a reranker (embeddings are your only signal)
- Budget allows 6x storage vs 512d

### The Reranker Effect

Adding a cross-encoder reranker after retrieval dramatically changes the dimension calculus:

| Setup | Recall@10 | End-to-end Latency |
|-------|-----------|-------------------|
| 3072d, no reranker | 0.84 | 12.4ms |
| 256d + reranker (top 50) | 0.86 | 45ms |
| 1024d + reranker (top 20) | 0.89 | 32ms |

**Key insight**: With a reranker, you can use lower dimensions for the first stage and achieve HIGHER final quality than high-d embeddings alone. The tradeoff is latency.

---

## Multimodal Embeddings: Product Catalog Search with CLIP/SigLIP

### The Problem

An e-commerce company with 8M products needed unified search across:
- Text queries: "red running shoes for men"
- Image queries: User uploads a photo of a shoe they like
- Mixed: "Something like this [image] but in blue"

### Architecture with SigLIP

```python
import torch
from transformers import AutoModel, AutoProcessor

class MultimodalProductSearch:
    def __init__(self):
        # SigLIP outperforms CLIP on zero-shot image classification
        self.model = AutoModel.from_pretrained("google/siglip-so400m-patch14-384")
        self.processor = AutoProcessor.from_pretrained("google/siglip-so400m-patch14-384")
    
    def embed_product(self, product: dict) -> np.ndarray:
        """
        Embed a product using both its image and text description.
        Strategy: Average image embedding + text embedding for richer representation.
        """
        # Image embedding
        image = load_image(product["image_url"])
        img_inputs = self.processor(images=image, return_tensors="pt")
        img_emb = self.model.get_image_features(**img_inputs)
        
        # Text embedding (title + key attributes)
        text = f"{product['title']}. {product['color']} {product['category']}"
        txt_inputs = self.processor(text=text, return_tensors="pt")
        txt_emb = self.model.get_text_features(**txt_inputs)
        
        # Weighted combination (image carries more signal for visual products)
        combined = 0.6 * F.normalize(img_emb) + 0.4 * F.normalize(txt_emb)
        return F.normalize(combined).detach().numpy()
    
    def search(self, query_text: str = None, query_image = None, k=20):
        """Unified search supporting text, image, or both."""
        embeddings = []
        if query_text:
            txt_inputs = self.processor(text=query_text, return_tensors="pt")
            embeddings.append(self.model.get_text_features(**txt_inputs))
        if query_image:
            img_inputs = self.processor(images=query_image, return_tensors="pt")
            embeddings.append(self.model.get_image_features(**img_inputs))
        
        query_emb = F.normalize(torch.mean(torch.stack(embeddings), dim=0))
        return self.vector_db.search(query_emb.numpy(), k=k)
```

### Results

| Query Type | Recall@10 (CLIP ViT-L) | Recall@10 (SigLIP-400M) |
|-----------|------------------------|------------------------|
| Text → Product | 0.61 | 0.68 |
| Image → Product | 0.72 | 0.79 |
| Text+Image → Product | 0.74 | 0.82 |

### Production Considerations

**Embedding cost for 8M products:**
- Initial embedding: ~36 hours on 4x A100 (batch processing)
- New products: Real-time embedding via GPU inference endpoint (~15ms/product)
- Storage: 8M × 1152d × 4 bytes = ~35 GB

**Limitation**: CLIP/SigLIP embeddings are 768-1152d and don't capture fine-grained text semantics as well as text-only models. For queries like "shoes with arch support for plantar fasciitis," a text-only model dramatically outperforms. Solution: hybrid search with both text and multimodal indices.

---

## Embedding Drift: Migration Strategy When You Upgrade Models

### The Core Problem

Embeddings from different models live in incompatible vector spaces. You cannot:
- Search a collection embedded with Model A using a query embedded with Model B
- Gradually replace vectors (you'd have mixed spaces)
- Use simple transformations to align spaces (non-linear differences)

### A Real Migration: 14B Vectors Across 3 Regions

A large search company needed to migrate 14 billion vectors from `e5-large-v2` to `gte-large-en-v1.5` across 3 geographic regions. Here's their strategy:

**Phase 1: Parallel Collection Architecture**

```
Region US-East:
  ├── collection_v2 (e5-large-v2)     ← serving traffic
  └── collection_v3 (gte-large-en-v1.5) ← backfilling

Region EU-West:
  ├── collection_v2
  └── collection_v3

Region AP-Southeast:
  ├── collection_v2
  └── collection_v3
```

**Phase 2: Backfill Pipeline**

```python
class EmbeddingMigrationPipeline:
    def __init__(self, config):
        self.source_model = "e5-large-v2"
        self.target_model = "gte-large-en-v1.5"
        self.batch_size = 512
        self.workers = 64  # Parallel embedding workers
        self.rate_limit = 10_000  # embeddings/second budget
    
    async def migrate_shard(self, shard_id: int):
        """Migrate one shard of documents."""
        cursor = self.db.scan(shard_id)
        
        async for batch in cursor.batches(self.batch_size):
            texts = [doc.text for doc in batch]
            
            # Embed with new model
            new_embeddings = await self.embed_batch(
                texts, model=self.target_model
            )
            
            # Upsert to new collection
            await self.vector_db.upsert(
                collection="collection_v3",
                points=[
                    {"id": doc.id, "vector": emb, "payload": doc.metadata}
                    for doc, emb in zip(batch, new_embeddings)
                ]
            )
            
            # Progress tracking
            await self.progress.increment(shard_id, len(batch))
```

**Phase 3: Traffic Shift with Quality Gates**

```python
class MigrationTrafficRouter:
    def __init__(self):
        self.rollout_percentage = 0  # Start at 0%
        self.quality_gate_threshold = 0.95  # New must be >= 95% of old quality
    
    async def search(self, query: str, user_id: str):
        if self.should_use_new(user_id):
            new_emb = await self.embed(query, model="gte-large-en-v1.5")
            results = await self.vector_db.search("collection_v3", new_emb)
            # Also shadow-query old for comparison
            asyncio.create_task(self._compare(query, results))
            return results
        else:
            old_emb = await self.embed(query, model="e5-large-v2")
            return await self.vector_db.search("collection_v2", old_emb)
```

**Timeline:**
- Backfill: 11 days (14B vectors ÷ 10K/sec ÷ 64 workers, with rate limiting)
- Shadow testing: 5 days
- Gradual rollout: 7 days (5% → 25% → 50% → 100%)
- Old collection decommission: 30 days after full rollout
- Total compute cost: ~$28,000 in GPU inference for re-embedding

---

## Late Interaction Models: ColBERT vs Single-Vector Embeddings

### How ColBERT Works

Instead of compressing a document into a single vector, ColBERT keeps one vector per token:
- Document with 200 tokens → 200 vectors (each 128d)
- Query with 32 tokens → 32 vectors
- Relevance = sum of max similarities between each query token and all doc tokens

```
Score(Q, D) = Σ_i max_j (q_i · d_j)
              for each query token i, find best matching doc token j
```

### When ColBERT Beats Single-Vector

**Experiment on legal contract search (10K contracts, 500 test queries):**

| Model | Recall@10 | Storage/Doc | Query Latency |
|-------|-----------|-------------|---------------|
| text-embedding-3-large (single) | 0.74 | 12 KB | 5ms |
| ColBERTv2 | 0.86 | 180 KB | 45ms |
| ColBERTv2 + PLAID indexing | 0.86 | 24 KB | 12ms |

ColBERT excels when:
- Documents are long (>500 tokens) and queries match specific passages
- Exact term matching matters alongside semantic understanding
- You need interpretability (which doc token matched which query token)

### The Cost Tradeoff

For 10M documents at average 300 tokens:
- Single-vector (1024d): 10M × 4KB = 40 GB storage
- ColBERT (naive): 10M × 300 × 512B = 1.5 TB storage
- ColBERT (PLAID compressed): 10M × 300 × 32B = 90 GB storage

**Decision**: Use ColBERT when retrieval quality on complex queries justifies 2-4x storage and infrastructure cost. Common pattern: use single-vector for first-pass retrieval (top 1000), then ColBERT for reranking (top 1000 → top 20).

---

## Embedding Caching: Avoiding Redundant Computation

### The Problem

A documentation platform re-embeds content on every deployment, even when 95% of pages haven't changed. At 50K pages and 3 deployments/day, they were spending $450/month on redundant embedding calls.

### Hash-Based Deduplication Strategy

```python
import hashlib
from typing import Optional

class EmbeddingCache:
    def __init__(self, redis_client, ttl_days=90):
        self.redis = redis_client
        self.ttl = ttl_days * 86400
    
    def content_hash(self, text: str, model: str, dimensions: int) -> str:
        """Deterministic hash of content + model config."""
        key_material = f"{model}:{dimensions}:{text}"
        return hashlib.sha256(key_material.encode()).hexdigest()
    
    async def get_or_embed(self, text: str, model: str, dimensions: int) -> list[float]:
        """Return cached embedding or compute and cache."""
        cache_key = f"emb:{self.content_hash(text, model, dimensions)}"
        
        cached = await self.redis.get(cache_key)
        if cached:
            self.metrics.increment("embedding_cache_hit")
            return json.loads(cached)
        
        self.metrics.increment("embedding_cache_miss")
        embedding = await self.openai.embed(text, model=model, dimensions=dimensions)
        
        # Cache with TTL (embeddings never change for same input+model)
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(embedding)
        )
        return embedding
    
    async def batch_get_or_embed(self, texts: list[str], model: str, dimensions: int):
        """Batch-aware: only embed cache misses."""
        results = [None] * len(texts)
        to_embed = []  # (index, text) pairs needing embedding
        
        # Check cache for all
        for i, text in enumerate(texts):
            cache_key = f"emb:{self.content_hash(text, model, dimensions)}"
            cached = await self.redis.get(cache_key)
            if cached:
                results[i] = json.loads(cached)
            else:
                to_embed.append((i, text))
        
        if to_embed:
            # Batch embed only misses
            miss_texts = [t for _, t in to_embed]
            embeddings = await self.openai.embed_batch(miss_texts, model=model)
            
            for (i, text), emb in zip(to_embed, embeddings):
                results[i] = emb
                cache_key = f"emb:{self.content_hash(text, model, dimensions)}"
                await self.redis.setex(cache_key, self.ttl, json.dumps(emb))
        
        return results
```

### Results

- Cache hit rate: 67% (much content is repeated across pages or unchanged between deploys)
- Monthly cost: $450 → $148 (67% reduction)
- Deployment speed: 12 min → 4 min (only embed changed content)
- Cache storage: ~8 GB in Redis for 50K pages × multiple chunk embeddings

---

## Sparse vs Dense vs Hybrid: SPLADE Results

### The Landscape

| Approach | How It Works | Strengths | Weaknesses |
|----------|-------------|-----------|------------|
| Dense (e.g., BGE) | Single dense vector | Semantic understanding | Misses exact keywords |
| Sparse (e.g., SPLADE) | Learned sparse vector (30K dims, mostly zeros) | Keyword precision, interpretable | Weaker on paraphrases |
| Hybrid | Both dense + sparse, combined score | Best of both worlds | 2x storage, more complex |

### Real Benchmark: E-commerce Product Search (2M products, 5K test queries)

| Method | NDCG@10 | Recall@100 | Exact Match Accuracy |
|--------|---------|-----------|---------------------|
| BM25 (baseline) | 0.38 | 0.52 | 0.91 |
| Dense only (BGE-large) | 0.51 | 0.71 | 0.63 |
| SPLADE-v3 | 0.49 | 0.68 | 0.88 |
| Hybrid (Dense + SPLADE) | 0.58 | 0.79 | 0.89 |
| Hybrid + Reranker | 0.64 | 0.79 | 0.91 |

### When Sparse Matters

Sparse models like SPLADE shine when:
- Product names/SKUs must match exactly ("iPhone 15 Pro Max 256GB")
- Domain-specific jargon exists that dense models haven't seen ("ASTM F2413-18 compliance")
- Users type model numbers, part codes, or identifiers
- You need explainability (which terms activated the match)

### Implementation with Qdrant Hybrid Search

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    NamedSparseVector, NamedVector, SearchRequest, FusionQuery
)

# Collection with both dense and sparse vectors
client.create_collection(
    "products",
    vectors_config={"dense": VectorParams(size=1024, distance="Cosine")},
    sparse_vectors_config={"sparse": SparseVectorParams()},
)

# Search with Reciprocal Rank Fusion
results = client.query_points(
    "products",
    prefetch=[
        Prefetch(query=dense_query_vector, using="dense", limit=100),
        Prefetch(query=sparse_query_vector, using="sparse", limit=100),
    ],
    query=FusionQuery(fusion="rrf"),  # Reciprocal Rank Fusion
    limit=20,
)
```

---

## Embedding Cost Optimization: Real Strategies Saving 60%

### Strategy 1: Batching (20% savings)

```python
# BAD: Individual calls
for doc in documents:  # 10,000 documents
    embedding = openai.embeddings.create(input=doc.text, model="text-embedding-3-large")
    # 10,000 API calls, high overhead

# GOOD: Batch calls (max 2048 inputs per call)
for batch in chunked(documents, 2048):
    response = openai.embeddings.create(
        input=[doc.text for doc in batch],
        model="text-embedding-3-large"
    )
    # 5 API calls, same result
```

Savings: Reduced API overhead, better throughput, lower rate-limit pressure.

### Strategy 2: Matryoshka Dimension Reduction (35% savings)

```python
# Instead of storing full 3072d vectors:
embedding = openai.embeddings.create(
    input=text,
    model="text-embedding-3-large",
    dimensions=1024  # Matryoshka: truncate to 1024d
)
# Storage: 3072d × 4B = 12KB → 1024d × 4B = 4KB per vector
# At 10M vectors: 120GB → 40GB (saves ~$200/month on vector DB)
```

### Strategy 3: Tiered Embedding Models (25% savings)

```python
class TieredEmbeddingRouter:
    """Use cheap model for simple content, expensive model for complex."""
    
    def select_model(self, text: str, metadata: dict) -> str:
        # Short, simple content → cheap model
        if len(text) < 200 and metadata.get("type") == "faq":
            return "text-embedding-3-small"  # $0.02/1M tokens
        
        # Long, complex documents → quality model
        if metadata.get("type") in ("legal", "technical", "research"):
            return "text-embedding-3-large"  # $0.13/1M tokens
        
        # Default: mid-tier
        return "text-embedding-3-small"
```

### Strategy 4: Content Deduplication Before Embedding

```python
class DeduplicatingEmbedder:
    def embed_corpus(self, documents: list[str]):
        # Many documents share paragraphs (headers, footers, boilerplate)
        unique_chunks = {}
        chunk_to_docs = defaultdict(list)
        
        for doc_id, doc in enumerate(documents):
            for chunk in self.chunk(doc):
                chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
                unique_chunks[chunk_hash] = chunk
                chunk_to_docs[chunk_hash].append(doc_id)
        
        # Only embed unique chunks
        # Typical dedup ratio: 15-40% fewer embeddings needed
        unique_embeddings = self.batch_embed(list(unique_chunks.values()))
```

### Combined Savings Example

A company processing 50M tokens/month:

| Strategy | Before | After | Monthly Savings |
|----------|--------|-------|-----------------|
| No batching → Batching | 50M tokens | 50M tokens | $0 (same tokens, less overhead) |
| 3072d → 1024d | 120GB storage | 40GB storage | $160 |
| All large → Tiered | $6,500 embed cost | $3,200 | $3,300 |
| No dedup → Dedup | 50M tokens | 35M tokens | $1,950 |
| No cache → Cache (67% hit) | 50M tokens/day | 16.5M tokens/day | $4,355 |
| **Total** | **$11,000/mo** | **$4,400/mo** | **60% reduction** |

---

## Summary: Decision Matrix for Embedding Architecture

| Decision | Recommendation | When to Deviate |
|----------|---------------|-----------------|
| Model choice | text-embedding-3-large for most cases | Multilingual → Cohere embed-v3; Self-host → NV-Embed-v2 |
| Dimensions | 1024d with reranker | Edge/mobile → 256d; No reranker + high precision → 3072d |
| Sparse component | Add SPLADE for keyword-heavy domains | Pure semantic search (creative writing, research) → skip |
| Fine-tuning | Only if domain-specific Recall@10 < 0.75 | Always validate on held-out set, watch for overfitting |
| Caching | Always implement hash-based cache | Skip for one-time batch jobs |
| Migration | Dual-write + shadow traffic + gradual cutover | Small corpus (<100K) → just re-embed and swap |
