# Embeddings Scalability - Staff Architect Interview

## Question 51: Embedding Model Selection and Trade-offs
**Difficulty: Staff Level | Topic: Embedding Architecture | Asked at: Google, OpenAI, Cohere**

You're building a semantic search system for a company with 500M documents in 15 languages. Compare embedding models (OpenAI ada-002, E5-large, BGE, Cohere embed-v3, Sentence-T5) across dimensions of quality, latency, cost, and multilingual support. How do you make the selection?

### Expected Answer:

**Embedding Model Comparison Matrix:**

| Model | Dims | Languages | Quality (MTEB) | Latency/1K docs | Cost/1M embeddings | Self-hosted? |
|-------|------|-----------|----------------|-----------------|-------------------|--------------|
| OpenAI text-embedding-3-large | 3072 | 100+ | 0.644 | 2s | $0.13 | No |
| E5-large-v2 | 1024 | English | 0.632 | 0.5s (GPU) | Self-hosted | Yes |
| BGE-M3 | 1024 | 100+ | 0.640 | 0.8s (GPU) | Self-hosted | Yes |
| Cohere embed-v3 | 1024 | 100+ | 0.638 | 1.5s | $0.10 | No |
| multilingual-e5-large | 1024 | 100+ | 0.625 | 0.6s (GPU) | Self-hosted | Yes |

**Decision Framework:**

1. **Cost Analysis at Scale (500M documents):**
   ```
   API-based (OpenAI/Cohere):
   - Initial embedding: 500M × $0.10/1M = $50,000 (one-time)
   - Re-embedding on model update: $50,000 (each time)
   - Ongoing (new docs, 1M/day): $100/day = $3,000/month
   
   Self-hosted (E5/BGE):
   - GPU infrastructure: 8x A100 GPUs for 2 weeks = $15,000 (one-time)
   - Ongoing (1M/day): 8x A10G = $2,000/month
   - Engineering overhead: $5,000/month (maintenance)
   
   Break-even: Self-hosted wins after 3 months at this scale
   ```

2. **Architecture Decision:**
   ```python
   class EmbeddingStrategy:
       def select_model(self, requirements):
           if requirements.languages > 1:
               if requirements.budget == 'unlimited':
                   return 'openai-text-embedding-3-large'  # Best quality
               elif requirements.data_sovereignty:
                   return 'bge-m3'  # Self-hosted multilingual
               else:
                   return 'cohere-embed-v3'  # Good balance
           else:  # English only
               if requirements.latency_critical:
                   return 'e5-small-v2'  # Fast, good enough
               else:
                   return 'e5-large-v2'  # Best English quality
   ```

3. **Matryoshka Embeddings for Adaptive Dimensionality:**
   - Store full 1024-dim embeddings
   - Use first 256 dims for fast pre-filtering (4x less memory)
   - Use full 1024 dims for final re-ranking
   - Dynamic: Use 128 dims on mobile, 512 on web, 1024 for batch

4. **Embedding Serving Infrastructure:**
   ```
   ┌─────────────────────────────────────────┐
   │  Embedding Service (gRPC)                │
   ├─────────────────────────────────────────┤
   │  Load Balancer (round-robin)             │
   ├────────┬────────┬────────┬──────────────┤
   │GPU Pod 1│GPU Pod 2│GPU Pod 3│ ... Pod N  │
   │(A100)   │(A100)   │(A100)   │            │
   │Batch:256│Batch:256│Batch:256│            │
   └────────┴────────┴────────┴──────────────┘
   
   Features:
   - Dynamic batching (accumulate requests for 10ms, then batch)
   - Model warmup on pod start
   - Health checks with embedding quality verification
   - Auto-scaling based on queue depth
   ```

5. **Quality Monitoring:**
   - Weekly evaluation against domain-specific benchmark
   - Monitor embedding drift over time (centroid shift)
   - A/B test new models against production
   - Alerting if retrieval precision drops (proxy for embedding quality)

---

## Question 52: Embedding Drift and Model Versioning
**Difficulty: Staff Level | Topic: MLOps for Embeddings | Asked at: Spotify, Netflix, LinkedIn**

Your production system has 2B embeddings generated with model v1. You want to upgrade to model v2 which has 15% better retrieval quality. Design a zero-downtime migration strategy that handles the dual-model transition period.

### Expected Answer:

**Embedding Migration Strategy:**

1. **The Problem:**
   - Model v1 embeddings are NOT compatible with model v2
   - Can't mix: v1 query embedding vs v2 document embeddings = garbage results
   - Re-embedding 2B documents takes days/weeks
   - Can't have downtime during migration

2. **Shadow Index Approach (Recommended):**
   ```
   Phase 1: Build Shadow Index (Days 1-14)
   ┌─────────────────┐     ┌─────────────────┐
   │  Primary Index   │     │  Shadow Index    │
   │  (Model v1)      │     │  (Model v2)      │
   │  2B vectors      │     │  Building...     │
   │  Serving traffic │     │  0% traffic      │
   └─────────────────┘     └─────────────────┘
   
   Phase 2: Validation (Days 14-17)
   - Shadow receives copy of all queries
   - Compare results quality (offline evaluation)
   - Verify latency, recall, precision
   
   Phase 3: Canary (Days 17-19)
   - Route 5% of traffic to shadow index
   - Monitor user metrics (click-through, satisfaction)
   
   Phase 4: Ramp (Days 19-21)
   - 25% → 50% → 75% → 100% to new index
   
   Phase 5: Cleanup (Day 21+)
   - Decommission v1 index after 7-day rollback window
   ```

3. **Dual-Write During Migration:**
   ```python
   class DualWriteEmbedder:
       def __init__(self):
           self.model_v1 = load_model('v1')
           self.model_v2 = load_model('v2')
           self.migration_progress = MigrationTracker()
       
       async def embed_and_index(self, document):
           # Always write to both during migration
           embedding_v1 = self.model_v1.encode(document)
           embedding_v2 = self.model_v2.encode(document)
           
           await asyncio.gather(
               self.index_v1.upsert(document.id, embedding_v1),
               self.index_v2.upsert(document.id, embedding_v2)
           )
       
       async def search(self, query, user_in_canary=False):
           if user_in_canary:
               query_embedding = self.model_v2.encode(query)
               return await self.index_v2.search(query_embedding)
           else:
               query_embedding = self.model_v1.encode(query)
               return await self.index_v1.search(query_embedding)
   ```

4. **Backfill Strategy for 2B Documents:**
   - Parallel processing: 100 GPU workers, each handling 20M docs
   - Priority queue: Embed frequently-accessed docs first (from access logs)
   - Incremental: Process in batches of 10M, checkpoint progress
   - Cost estimate: 2B docs ÷ 10K docs/min/GPU × 100 GPUs = ~33 hours
   - Idempotent: Can restart from any checkpoint without duplication

5. **Rollback Plan:**
   - Keep v1 index intact for 7 days after full migration
   - Feature flag to instantly switch back to v1
   - Monitor quality metrics continuously during and after migration
   - Automated rollback trigger: If precision drops >3% or latency >2x

---

## Question 53: Real-Time Embedding Generation at Scale
**Difficulty: Staff Level | Topic: Inference Infrastructure | Asked at: Google, Amazon, Microsoft**

Design an embedding inference service that processes 50,000 embedding requests per second with p99 latency under 20ms. Consider batching, GPU utilization, and failure handling.

### Expected Answer:

**High-Throughput Embedding Service:**

1. **Architecture:**
   ```
   Clients (50K RPS)
        │
        ▼
   ┌─────────────────────────────────────┐
   │  Load Balancer (L4, least-connections) │
   └─────────────────┬───────────────────┘
                     │
        ┌────────────┼────────────────┐
        │            │                │
   ┌────▼────┐  ┌────▼────┐    ┌────▼────┐
   │Batcher 1│  │Batcher 2│... │Batcher N│   (CPU pods)
   │(10ms win)│  │(10ms win)│   │(10ms win)│
   └────┬────┘  └────┬────┘    └────┬────┘
        │            │                │
        ▼            ▼                ▼
   ┌─────────────────────────────────────┐
   │  GPU Worker Pool (Triton/TensorRT)   │
   │  32x A100 GPUs, batch_size=512       │
   │  Model: E5-large quantized (INT8)    │
   └─────────────────────────────────────┘
   ```

2. **Dynamic Batching:**
   ```python
   class DynamicBatcher:
       """Accumulate requests and batch for GPU efficiency."""
       
       def __init__(self, max_batch=512, max_wait_ms=5):
           self.max_batch = max_batch
           self.max_wait = max_wait_ms / 1000
           self.queue = asyncio.Queue()
           self.gpu_workers = GPUWorkerPool(n_gpus=32)
       
       async def embed(self, text: str) -> np.ndarray:
           """Single request interface with batching under the hood."""
           future = asyncio.Future()
           await self.queue.put((text, future))
           return await future
       
       async def batch_loop(self):
           """Background loop that forms and dispatches batches."""
           while True:
               batch = []
               deadline = time.time() + self.max_wait
               
               # Collect up to max_batch items or until timeout
               while len(batch) < self.max_batch and time.time() < deadline:
                   try:
                       item = await asyncio.wait_for(
                           self.queue.get(), 
                           timeout=max(0, deadline - time.time())
                       )
                       batch.append(item)
                   except asyncio.TimeoutError:
                       break
               
               if batch:
                   # Dispatch batch to GPU
                   texts = [item[0] for item in batch]
                   futures = [item[1] for item in batch]
                   
                   embeddings = await self.gpu_workers.infer(texts)
                   
                   for future, embedding in zip(futures, embeddings):
                       future.set_result(embedding)
   ```

3. **GPU Optimization:**
   - **Model quantization:** INT8 inference (2x throughput, <1% quality loss)
   - **TensorRT optimization:** Fused kernels, optimized memory layout
   - **Continuous batching:** Don't wait for full batch if GPU is idle
   - **Token padding optimization:** Group similar-length texts to minimize padding
   - **Multi-stream:** Run multiple CUDA streams per GPU for better utilization

4. **Latency Budget (20ms p99):**
   | Component | p99 Latency |
   |-----------|-------------|
   | Network (client → LB) | 2ms |
   | Queuing in batcher | 5ms (max wait) |
   | Tokenization (CPU) | 1ms |
   | GPU inference (batch=512) | 8ms |
   | Network (response) | 2ms |
   | **Total** | **18ms** ✓ |

5. **Failure Handling:**
   - GPU OOM: Reduce batch size dynamically, alert on repeated OOMs
   - GPU hardware failure: Health check every 5s, remove unhealthy GPUs from pool
   - Request timeout: Return error after 20ms, client retries to different pod
   - Overload protection: Adaptive admission control (reject with 429 when queue > 10K)
   - Graceful degradation: If all GPUs busy, route to CPU fallback (slower but available)

---

## Question 54: Cross-Encoder vs Bi-Encoder Trade-offs
**Difficulty: Staff Level | Topic: Retrieval Models | Asked at: Google, Microsoft, Cohere**

Explain the architectural differences between cross-encoders and bi-encoders for semantic search. Design a production system that uses both optimally. When would you use a cross-encoder, and what are the latency implications at scale?

### Expected Answer:

**Cross-Encoder vs Bi-Encoder Architecture:**

1. **Fundamental Difference:**
   ```
   Bi-Encoder (Embedding model):
   Query  → Encoder → Query Embedding  ─┐
                                          ├── Cosine Similarity
   Doc    → Encoder → Doc Embedding    ─┘
   
   Advantage: Doc embeddings pre-computed, search is just similarity
   Speed: O(1) per comparison (with ANN index)
   Quality: Good but limited (no cross-attention between query and doc)
   
   Cross-Encoder (Reranker):
   [Query, Doc] → Joint Encoder → Relevance Score
   
   Advantage: Full attention between query and document tokens
   Speed: O(n) - must process each pair sequentially  
   Quality: Significantly better (cross-attention captures nuances)
   ```

2. **Production Two-Stage Architecture:**
   ```python
   class TwoStageRetriever:
       def __init__(self):
           self.bi_encoder = BiEncoder('e5-large-v2')  # Stage 1: Fast recall
           self.cross_encoder = CrossEncoder('ms-marco-MiniLM-L-12')  # Stage 2: Precision
       
       async def search(self, query: str, top_k: int = 5) -> List[Result]:
           # Stage 1: Bi-encoder retrieval (fast, high recall)
           query_embedding = self.bi_encoder.encode(query)
           candidates = await self.vector_db.search(
               query_embedding, top_k=100  # Over-retrieve
           )
           
           # Stage 2: Cross-encoder re-ranking (slow, high precision)
           pairs = [(query, doc.text) for doc in candidates]
           scores = self.cross_encoder.predict(pairs)
           
           # Re-rank by cross-encoder score
           reranked = sorted(
               zip(candidates, scores), 
               key=lambda x: x[1], reverse=True
           )
           return [doc for doc, score in reranked[:top_k]]
   ```

3. **Latency Analysis:**
   | Stage | Documents | Latency | Notes |
   |-------|-----------|---------|-------|
   | Bi-encoder (query) | 1 | 5ms | Encode query only |
   | ANN search | 100M index | 10ms | HNSW lookup |
   | Cross-encoder | 100 docs | 50ms | Batch inference |
   | Cross-encoder | 1000 docs | 400ms | Too slow for real-time |
   
   **Key insight:** Cross-encoder on 100 candidates is the sweet spot.

4. **Optimizing Cross-Encoder for Production:**
   ```python
   class OptimizedCrossEncoder:
       def __init__(self):
           # Use distilled/quantized model for speed
           self.model = load_model('cross-encoder-MiniLM-L-6', quantized=True)
           
       def predict_batch(self, pairs: List[Tuple[str, str]]) -> List[float]:
           # Optimization 1: Sort by length for minimal padding
           sorted_pairs = sorted(pairs, key=lambda p: len(p[0]) + len(p[1]))
           
           # Optimization 2: Batch on GPU with dynamic batching
           scores = self.model.predict(sorted_pairs, batch_size=64)
           
           # Optimization 3: Early termination
           # If top score is much higher than remaining, stop early
           return scores
   ```

5. **When NOT to use Cross-Encoder:**
   - Real-time autocomplete (latency too high even for 10 docs)
   - First-stage retrieval (can't pre-compute, too slow for full corpus)
   - Mobile/edge deployment (model too large)
   - When bi-encoder quality is sufficient (simple factual lookups)
   - When cost constraints are tight (GPU compute for every query)

---

## Question 55: Embedding Fine-tuning for Domain Adaptation
**Difficulty: Staff Level | Topic: Model Training | Asked at: Cohere, OpenAI, Anthropic**

Your general-purpose embedding model performs poorly on domain-specific retrieval (medical, legal, financial). Design a fine-tuning pipeline that improves domain performance without catastrophic forgetting of general capabilities.

### Expected Answer:

**Domain-Adaptive Embedding Fine-tuning:**

1. **Training Data Generation:**
   ```python
   class DomainTrainingDataGenerator:
       def generate_pairs(self, domain_documents):
           training_data = []
           
           # Method 1: Synthetic query generation
           for doc in domain_documents:
               queries = self.llm.generate(
                   f"Generate 5 diverse questions that this document answers:\n{doc}"
               )
               for query in queries:
                   training_data.append({
                       'query': query,
                       'positive': doc,
                       'negatives': self.mine_hard_negatives(query, doc)
                   })
           
           # Method 2: Click-through data (if available)
           for log in self.search_logs:
               if log.clicked:
                   training_data.append({
                       'query': log.query,
                       'positive': log.clicked_doc,
                       'negatives': log.shown_but_not_clicked
                   })
           
           # Method 3: Document structure exploitation
           # Heading → paragraph pairs as positive pairs
           for doc in domain_documents:
               for heading, paragraph in doc.heading_paragraph_pairs():
                   training_data.append({
                       'query': heading,
                       'positive': paragraph,
                       'negatives': self.random_paragraphs(exclude=paragraph)
                   })
           
           return training_data
   ```

2. **Training Strategy (Avoid Catastrophic Forgetting):**
   ```python
   class DomainFinetuner:
       def fine_tune(self, base_model, domain_data, general_data):
           # Strategy 1: Mixed training (70% domain, 30% general)
           mixed_data = self.mix_datasets(
               domain_data, weight=0.7,
               general_data, weight=0.3
           )
           
           # Strategy 2: Learning rate scheduling
           optimizer = AdamW(
               model.parameters(),
               lr=2e-5,  # Small LR to preserve general knowledge
               weight_decay=0.01
           )
           scheduler = WarmupCosineSchedule(
               warmup_steps=500,
               total_steps=10000
           )
           
           # Strategy 3: Selective layer freezing
           # Freeze bottom 6 layers (general knowledge), fine-tune top 6
           for i, layer in enumerate(model.layers):
               if i < 6:
                   layer.requires_grad_(False)
           
           # Strategy 4: Contrastive loss with hard negatives
           loss_fn = MultipleNegativesRankingLoss(
               with_in_batch_negatives=True
           )
           
           # Train
           for batch in DataLoader(mixed_data, batch_size=128):
               loss = loss_fn(
                   model(batch.queries),
                   model(batch.positives),
                   model(batch.negatives)
               )
               loss.backward()
               optimizer.step()
   ```

3. **Hard Negative Mining:**
   ```python
   def mine_hard_negatives(self, query, positive_doc, n_negatives=7):
       """Find documents that are similar but NOT relevant (hard negatives)."""
       # Embed query with current model
       query_emb = self.model.encode(query)
       
       # Find top-50 similar documents
       candidates = self.index.search(query_emb, top_k=50)
       
       # Filter out the positive
       candidates = [c for c in candidates if c.id != positive_doc.id]
       
       # Select hard negatives (similar but not relevant)
       # Use cross-encoder to verify they're NOT relevant
       hard_negatives = []
       for candidate in candidates:
           relevance = self.cross_encoder.predict(query, candidate.text)
           if relevance < 0.3:  # Not relevant despite high similarity
               hard_negatives.append(candidate)
           if len(hard_negatives) >= n_negatives:
               break
       
       return hard_negatives
   ```

4. **Evaluation Protocol:**
   - **Domain metrics:** Retrieval precision@5 on domain test set (target: +15% over base)
   - **General metrics:** MTEB benchmark subset (target: <2% regression)
   - **A/B test:** Compare fine-tuned vs base model on production traffic
   - **Per-query analysis:** Identify query types where fine-tuning helps most
   
5. **Production Deployment:**
   - Train on 100K domain pairs (2-4 hours on 8x A100)
   - Evaluate against holdout test set + MTEB general benchmark
   - If both pass: Deploy with shadow traffic first
   - Re-embed all domain documents with new model (batch job)
   - Keep general model as fallback for out-of-domain queries
   - Re-train monthly with new domain data (continuous improvement)
