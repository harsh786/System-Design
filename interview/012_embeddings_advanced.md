# Embeddings Advanced Topics - Staff Architect Interview

## Question 56: Multi-Vector Representations (ColBERT)
**Difficulty: Staff Level | Topic: Advanced Retrieval | Asked at: Google Research, Microsoft**

Explain the ColBERT late interaction paradigm and compare it with single-vector representations. When does multi-vector representation justify its additional storage and computation costs?

### Expected Answer:

**ColBERT Late Interaction Architecture:**

1. **Single-Vector vs Multi-Vector:**
   ```
   Single-Vector (Bi-Encoder):
   "machine learning algorithms" → [0.1, 0.3, ..., 0.8]  (1 vector, 768-dim)
   
   Multi-Vector (ColBERT):
   "machine learning algorithms" → [
       [0.1, 0.2, ...],  # "machine" token embedding (128-dim)
       [0.3, 0.1, ...],  # "learning" token embedding
       [0.5, 0.4, ...]   # "algorithms" token embedding
   ]
   (N vectors, 128-dim each, where N = token count)
   ```

2. **Late Interaction Mechanism:**
   ```python
   class ColBERTScorer:
       def score(self, query_vectors, doc_vectors):
           """
           MaxSim: For each query token, find max similarity with any doc token.
           Final score = sum of MaxSims across query tokens.
           """
           # query_vectors: [Q, 128] (Q query tokens)
           # doc_vectors: [D, 128] (D document tokens)
           
           # Compute all pairwise similarities
           similarity_matrix = query_vectors @ doc_vectors.T  # [Q, D]
           
           # For each query token, take max similarity with any doc token
           max_sims = similarity_matrix.max(dim=1).values  # [Q]
           
           # Final relevance score
           return max_sims.sum()
   ```

3. **Storage & Computation Trade-offs:**
   | Aspect | Single-Vector | ColBERT | Impact |
   |--------|--------------|---------|--------|
   | Storage/doc | 768 * 4 = 3KB | 128 * 128 * 4 = 65KB | ~20x more |
   | Index size (1B docs) | 3TB | 60TB | Significant |
   | Search (Stage 1) | ANN: 10ms | ANN on centroids: 15ms | Similar |
   | Scoring | Dot product: 0.001ms | MaxSim: 0.5ms/doc | 500x more |
   | Quality (BEIR) | 0.44 nDCG | 0.49 nDCG | +11% |

4. **When ColBERT is Worth It:**
   - Long documents where different sections are relevant to different queries
   - Queries with multiple distinct aspects (multi-faceted information needs)
   - When retrieval quality directly impacts revenue (e-commerce, legal)
   - When you can afford the storage (SSD is cheap, RAM is not)
   - NOT worth it for: Simple factual lookups, very large corpora with tight budgets

5. **Production Optimization:**
   ```python
   class OptimizedColBERT:
       def __init__(self):
           # Compression: Reduce per-token dims
           self.dim = 128  # Instead of 768
           # Residual compression: Store only residuals from centroid
           self.centroids = self.train_centroids(n=65536)
       
       def index_document(self, doc_tokens):
           """Compressed storage with centroid residuals."""
           embeddings = self.encode(doc_tokens)  # [N, 128]
           
           # Assign each token to nearest centroid
           centroid_ids = self.assign_centroids(embeddings)  # [N] uint16
           
           # Store residuals (much smaller magnitude)
           residuals = embeddings - self.centroids[centroid_ids]
           quantized_residuals = self.quantize(residuals)  # int8
           
           # Storage: centroid_id (2 bytes) + residual (128 bytes) = 130 bytes/token
           # vs original: 512 bytes/token (float32)
           return centroid_ids, quantized_residuals
   ```

---

## Question 57: Embedding Spaces and Alignment
**Difficulty: Staff Level | Topic: Representation Learning | Asked at: Meta AI, Google DeepMind**

How do you ensure that embeddings from different models, different modalities (text, image, audio), or different time periods are aligned in the same vector space? Design a system that maintains a unified embedding space as models evolve.

### Expected Answer:

**Embedding Space Alignment Architecture:**

1. **The Alignment Problem:**
   - Model v1 and v2 produce embeddings in DIFFERENT spaces
   - Text and image embeddings are in DIFFERENT spaces (unless specifically trained together)
   - Same model trained on different data → slightly different spaces (drift)
   - Need: Query in one space must find relevant items in any space

2. **Alignment Techniques:**
   ```python
   class EmbeddingAligner:
       # Technique 1: Linear Projection (Fast, approximate)
       def train_linear_alignment(self, source_embeds, target_embeds):
           """Learn W such that source_embeds @ W ≈ target_embeds."""
           # Procrustes alignment (orthogonal mapping)
           U, _, Vt = np.linalg.svd(target_embeds.T @ source_embeds)
           self.W = U @ Vt
           return self.W
       
       # Technique 2: Contrastive Alignment (Better quality)
       def train_contrastive_alignment(self, paired_data):
           """Train a projection network with contrastive loss."""
           projector = nn.Linear(source_dim, shared_dim)
           
           for (source_emb, target_emb) in paired_data:
               projected = projector(source_emb)
               loss = contrastive_loss(projected, target_emb)
               loss.backward()
       
       # Technique 3: Adapter Networks (Most flexible)
       def train_adapter(self, source_model, target_space_examples):
           """Add small adapter layer on top of source model."""
           adapter = nn.Sequential(
               nn.Linear(source_dim, hidden_dim),
               nn.GELU(),
               nn.Linear(hidden_dim, target_dim),
               nn.LayerNorm(target_dim)
           )
           # Train adapter while keeping source model frozen
   ```

3. **Multi-Modal Unified Space:**
   ```
   Text  → Text Encoder  → Projection → ┐
   Image → Vision Encoder → Projection → ├→ Shared Space (1024-dim)
   Audio → Audio Encoder  → Projection → ┘
   
   Training: CLIP-style contrastive learning on paired data
   - (text, image) pairs from web
   - (audio, text) pairs from transcripts
   - (image, audio) pairs from video
   ```

4. **Temporal Alignment (Model Evolution):**
   ```python
   class TemporalAligner:
       """Keep embeddings aligned as models are updated."""
       
       def __init__(self):
           self.anchor_set = self.select_anchor_documents(n=10000)
           # Fixed set of documents that represent the space well
       
       def align_new_model(self, new_model):
           # Embed anchors with both old and new model
           old_embeds = self.old_model.encode(self.anchor_set)
           new_embeds = new_model.encode(self.anchor_set)
           
           # Learn alignment transform
           transform = self.learn_alignment(new_embeds, old_embeds)
           
           # Validate alignment quality
           if self.alignment_quality(transform) > 0.95:
               # Apply transform to new model outputs
               return AlignedModel(new_model, transform)
           else:
               # Alignment too poor, need full re-indexing
               raise AlignmentFailure("Re-indexing required")
   ```

5. **Production Considerations:**
   - Maintain alignment validation suite (1000 query-document pairs)
   - Track alignment quality metric (mean reciprocal rank on cross-space retrieval)
   - Fallback: If alignment degrades, force queries to correct space
   - Cost: Alignment adds 1-2ms latency (matrix multiply) - negligible

---

## Question 58: Sparse vs Dense vs Learned Sparse Embeddings
**Difficulty: Staff Level | Topic: Retrieval Methods | Asked at: Elastic, Vespa, Google**

Compare traditional sparse representations (TF-IDF, BM25), dense embeddings, and learned sparse embeddings (SPLADE, DeepImpact). Design a system that optimally combines all three for maximum retrieval quality.

### Expected Answer:

**Three Paradigms of Text Representation:**

1. **Comparison:**
   | Aspect | BM25 (Sparse) | Dense Embedding | SPLADE (Learned Sparse) |
   |--------|---------------|-----------------|------------------------|
   | Representation | Term frequencies | Dense vector | Sparse activated terms |
   | Dimensions | Vocab size (~30K) | 768-1024 | Vocab size (~30K) |
   | Non-zero elements | 100-300 per doc | All | 200-500 per doc |
   | Storage/doc | ~500 bytes | 3-4KB | ~1KB |
   | Interpretable | Yes (terms visible) | No (abstract dims) | Yes (expanded terms) |
   | Exact match | Excellent | Poor | Good |
   | Semantic match | Poor | Excellent | Good |
   | Out-of-vocabulary | Fails | Handles | Partially handles |
   | Zero-shot | Good (no training) | Needs training | Needs training |

2. **SPLADE (Learned Sparse) Explanation:**
   ```python
   class SPLADE:
       """
       Produces sparse vectors where dimensions = vocabulary terms.
       Key insight: BERT predicts term importance including EXPANSION terms.
       
       "deep learning" → {
           "deep": 2.3, "learning": 2.1,
           "neural": 1.5, "network": 1.2,  # Expanded terms!
           "machine": 0.8, "AI": 0.7,
           "training": 0.5, ...
       }
       """
       def encode(self, text):
           # Get BERT token logits (vocabulary-sized)
           token_logits = self.bert(text).logits  # [seq_len, vocab_size]
           
           # ReLU + log to get importance weights
           weights = torch.log1p(torch.relu(token_logits))
           
           # Max-pool over sequence to get document representation
           sparse_repr = weights.max(dim=0).values  # [vocab_size]
           
           # Sparsify: keep only top-K terms
           topk_indices = sparse_repr.topk(200).indices
           sparse_vector = {idx: sparse_repr[idx] for idx in topk_indices}
           
           return sparse_vector
   ```

3. **Triple Combination Architecture:**
   ```python
   class TripleHybridRetriever:
       async def retrieve(self, query: str, top_k: int = 10):
           # Parallel retrieval from all three
           dense_task = self.dense_search(query, top_k=50)
           sparse_task = self.bm25_search(query, top_k=50)
           learned_sparse_task = self.splade_search(query, top_k=50)
           
           dense_results, sparse_results, splade_results = await asyncio.gather(
               dense_task, sparse_task, learned_sparse_task
           )
           
           # Adaptive fusion based on query characteristics
           weights = self.get_weights(query)
           # e.g., exact term query → boost BM25
           # conceptual query → boost dense
           # domain-specific → boost SPLADE (term expansion helps)
           
           fused = self.weighted_rrf(
               [dense_results, sparse_results, splade_results],
               weights=[weights['dense'], weights['bm25'], weights['splade']]
           )
           return fused[:top_k]
   ```

4. **When Each Shines:**
   - **BM25 wins:** Error codes ("ERR-4012"), product SKUs, exact phrases, rare terms
   - **Dense wins:** "How to fix slow database queries" (conceptual, no exact match needed)
   - **SPLADE wins:** Domain jargon with expansion ("MI" → expands to "myocardial infarction")

5. **Practical Deployment:**
   - BM25: Elasticsearch/Lucene (virtually free, already deployed)
   - Dense: Vector DB (Pinecone/Weaviate/Milvus)
   - SPLADE: Can use same inverted index as BM25! (Just different weights)
   - Cost: Dense is most expensive (GPU embedding + vector DB), BM25 cheapest
   - Recommendation: Start with BM25 + Dense, add SPLADE for domains with jargon

---

## Question 59: Embedding Compression for Edge Deployment
**Difficulty: Staff Level | Topic: Edge/Mobile AI | Asked at: Apple, Google, Qualcomm**

Design an embedding system that runs on mobile devices (iPhone, Android) with constraints of 100MB model size, 50ms latency, and no network connectivity. How do you compress embeddings while maintaining quality?

### Expected Answer:

**Edge Embedding Architecture:**

1. **Model Compression Pipeline:**
   ```
   Full Model (400MB, 768-dim, FP32)
        ↓ Knowledge Distillation
   Small Model (100MB, 384-dim, FP32)
        ↓ Quantization (INT8)
   Quantized (25MB, 384-dim, INT8)
        ↓ Pruning (50% sparsity)
   Final Edge Model (15MB, 384-dim, INT8, sparse)
   ```

2. **Knowledge Distillation:**
   ```python
   class EmbeddingDistiller:
       def distill(self, teacher_model, student_model, data):
           """Train small student to mimic large teacher."""
           for batch in data:
               # Teacher generates target embeddings
               with torch.no_grad():
                   teacher_embeds = teacher_model(batch)  # 768-dim
               
               # Student learns to match (with projection)
               student_embeds = student_model(batch)  # 384-dim
               projected = self.projection(student_embeds)  # 384 → 768
               
               # MSE loss + cosine similarity loss
               loss = (
                   0.5 * mse_loss(projected, teacher_embeds) +
                   0.5 * (1 - cosine_similarity(projected, teacher_embeds).mean())
               )
               loss.backward()
   ```

3. **On-Device Index Design:**
   ```python
   class OnDeviceVectorSearch:
       """Optimized for mobile constraints."""
       
       def __init__(self, max_vectors=100_000):
           # Use product quantization for storage
           self.pq = ProductQuantizer(n_subvectors=48, n_bits=8)
           # IVF for search speed (no HNSW - too much memory)
           self.n_clusters = 256
           self.ivf_index = IVFIndex(self.n_clusters, self.pq)
           
       def search(self, query_embedding, top_k=10):
           """Search ~100K vectors in <50ms on mobile CPU."""
           # Step 1: Find nearest clusters (2ms)
           nearest_clusters = self.find_clusters(query_embedding, n_probe=8)
           
           # Step 2: PQ distance computation within clusters (30ms)
           # Pre-compute distance table (query vs codebook centroids)
           distance_table = self.pq.compute_distance_table(query_embedding)
           
           # Step 3: Scan candidates using lookup table (fast!)
           candidates = self.scan_clusters(nearest_clusters, distance_table)
           
           return candidates[:top_k]
   ```

4. **Offline-First Architecture:**
   ```
   ┌─────────────────────────────────────┐
   │  On-Device                           │
   │  ┌─────────────┐ ┌──────────────┐   │
   │  │ Small Model  │ │ Local Index  │   │
   │  │ (15MB, INT8) │ │ (PQ, 50MB)  │   │
   │  └──────┬──────┘ └──────┬───────┘   │
   │         │               │            │
   │         └───────┬───────┘            │
   │                 │                    │
   │         Local Search (50ms)          │
   └─────────────────┬───────────────────┘
                     │ (When online)
                     ▼
   ┌─────────────────────────────────────┐
   │  Cloud (Optional Enhancement)        │
   │  - Full model re-ranking             │
   │  - Larger index search               │
   │  - Sync new embeddings to device     │
   └─────────────────────────────────────┘
   ```

5. **Quality Preservation Metrics:**
   | Metric | Full Model | Edge Model | Acceptable? |
   |--------|-----------|------------|-------------|
   | Recall@10 | 0.95 | 0.88 | Yes (>0.85) |
   | nDCG@10 | 0.82 | 0.74 | Yes (>0.70) |
   | Model size | 400MB | 15MB | Yes (<100MB) |
   | Latency | 5ms (GPU) | 45ms (CPU) | Yes (<50ms) |
   | Power draw | N/A | 50mW | Yes (< 100mW) |

---

## Question 60: Embedding Space Analysis and Debugging
**Difficulty: Staff Level | Topic: MLOps | Asked at: Google, Spotify, Pinterest**

Your retrieval quality has dropped 15% over the past month but no code changes were made. How do you diagnose issues in the embedding space? Design a monitoring and debugging toolkit for production embeddings.

### Expected Answer:

**Embedding Space Monitoring & Debugging:**

1. **Diagnostic Framework:**
   ```
   Quality Degradation Detected (Retrieval precision down 15%)
        │
        ▼
   ┌─────────────────────────────────────┐
   │  Step 1: Data Distribution Shift?    │
   │  - Compare document distribution     │
   │  - New vocabulary/topics?            │
   │  - Language distribution changed?    │
   └─────────────────────┬───────────────┘
                         │
   ┌─────────────────────▼───────────────┐
   │  Step 2: Embedding Quality Metrics   │
   │  - Intrinsic: uniformity, alignment  │
   │  - Extrinsic: retrieval benchmarks   │
   └─────────────────────┬───────────────┘
                         │
   ┌─────────────────────▼───────────────┐
   │  Step 3: Index Health                │
   │  - Fragmentation? Stale vectors?     │
   │  - Capacity issues? Hot spots?       │
   └─────────────────────┬───────────────┘
                         │
   ┌─────────────────────▼───────────────┐
   │  Step 4: Query Pattern Changes       │
   │  - Query distribution shifted?       │
   │  - New query types not seen before?  │
   └─────────────────────────────────────┘
   ```

2. **Embedding Health Metrics:**
   ```python
   class EmbeddingMonitor:
       def compute_health_metrics(self, embeddings_sample):
           metrics = {}
           
           # 1. Uniformity: Are embeddings well-distributed?
           # Low uniformity = collapse (all embeddings similar)
           metrics['uniformity'] = self.compute_uniformity(embeddings_sample)
           # Target: -2.0 to -1.0 (lower is more uniform)
           
           # 2. Alignment: Are similar items close?
           metrics['alignment'] = self.compute_alignment(
               embeddings_sample, self.known_similar_pairs
           )
           # Target: < 0.5 (lower is better aligned)
           
           # 3. Isotropy: Is the space used efficiently?
           # Anisotropic = most variance in few directions
           eigenvalues = np.linalg.eigvalsh(np.cov(embeddings_sample.T))
           metrics['isotropy'] = self.compute_isotropy(eigenvalues)
           # Target: > 0.5 (higher is more isotropic)
           
           # 4. Cluster quality: Are semantic clusters still well-separated?
           metrics['silhouette_score'] = silhouette_score(
               embeddings_sample, self.known_labels
           )
           
           # 5. Dimensional collapse: Are any dimensions "dead"?
           dim_variance = np.var(embeddings_sample, axis=0)
           metrics['dead_dimensions'] = (dim_variance < 1e-6).sum()
           
           return metrics
   ```

3. **Root Cause Analysis:**
   ```python
   class EmbeddingDebugger:
       def diagnose_quality_drop(self):
           # Compare current vs baseline (30 days ago)
           current_embeddings = self.sample_recent_embeddings(n=10000)
           baseline_embeddings = self.load_baseline_snapshot()
           
           # Distribution shift detection
           shift = self.maximum_mean_discrepancy(current_embeddings, baseline_embeddings)
           if shift > threshold:
               # Embeddings have drifted! Why?
               
               # Check 1: New document types being indexed?
               new_doc_types = self.compare_document_distributions()
               
               # Check 2: Embedding model serving issues?
               model_health = self.validate_model_outputs(self.test_inputs)
               
               # Check 3: Tokenization issues? (library update?)
               tokenization_diff = self.compare_tokenizations(self.test_inputs)
               
               return DiagnosticReport(
                   shift_detected=True,
                   probable_causes=[new_doc_types, model_health, tokenization_diff]
               )
   ```

4. **Visualization Toolkit:**
   - UMAP/t-SNE projections of embedding space (before vs after)
   - Nearest neighbor consistency plots
   - Query-document similarity distribution histograms
   - Per-topic retrieval quality heatmaps
   - Dimensional contribution analysis

5. **Alerting Rules:**
   | Metric | Warning | Critical | Action |
   |--------|---------|----------|--------|
   | Uniformity increase > 20% | Warn | Alert | Check for collapse |
   | Dead dimensions > 5% | Warn | Alert | Model issue |
   | Distribution shift (MMD) > 0.1 | Warn | Alert | Data drift |
   | Retrieval precision drop > 5% | Warn | Alert | Full investigation |
   | Embedding latency p99 > 2x | Warn | Alert | Infra issue |
