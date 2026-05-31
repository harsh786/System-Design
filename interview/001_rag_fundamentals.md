# RAG Architecture Fundamentals - Staff Architect Interview

## Question 1: End-to-End RAG System Design
**Difficulty: Staff Level | Topic: RAG Architecture | Asked at: Google, OpenAI**

Design a production RAG system that serves 10M daily active users with sub-200ms p99 latency. Walk through every component from document ingestion to response generation.

### Expected Answer:

**Architecture Components:**

1. **Document Ingestion Pipeline:**
   - Async document processors (PDF, HTML, Markdown parsers)
   - Chunking strategy: Semantic chunking with sliding window (512 tokens, 50 token overlap)
   - Metadata extraction pipeline (entity recognition, topic classification, date extraction)
   - Deduplication using MinHash/SimHash before embedding

2. **Embedding Layer:**
   - Model: Fine-tuned sentence-transformers (e.g., E5-large-v2 or custom)
   - Batch embedding with GPU inference servers (Triton/TensorRT)
   - Dimensionality: 768-1024 dims with Matryoshka representation for multi-resolution search
   - Embedding versioning and migration strategy

3. **Vector Store:**
   - Primary: Distributed vector DB (Pinecone/Weaviate/Milvus) with HNSW index
   - Sharding strategy: Hash-based on namespace/tenant
   - Replication factor: 3 for HA
   - Index parameters: M=16, efConstruction=200, efSearch=100

4. **Retrieval Layer:**
   - Hybrid search: Dense (vector) + Sparse (BM25) with reciprocal rank fusion
   - Re-ranking with cross-encoder (ms-marco-MiniLM-L-12)
   - Maximum Marginal Relevance (MMR) for diversity
   - Query expansion using HyDE (Hypothetical Document Embedding)

5. **Generation Layer:**
   - LLM with streaming response (GPT-4/Claude/Llama)
   - Context window management: Stuff/Map-Reduce/Refine strategies
   - Citation injection and source attribution
   - Guardrails for hallucination detection

6. **Infrastructure:**
   - CDN for cached responses
   - Redis for semantic cache (embedding similarity > 0.95)
   - Circuit breakers between services
   - Auto-scaling based on queue depth

**Latency Budget:**
- Query embedding: 10ms (cached model, GPU)
- Vector search: 20ms (in-memory HNSW)
- Re-ranking: 30ms (lightweight cross-encoder)
- LLM generation: 100-140ms (streaming first token)
- Network/overhead: 20ms

---

## Question 2: Chunking Strategy Selection
**Difficulty: Staff Level | Topic: Document Processing | Asked at: Anthropic, Microsoft**

You have a heterogeneous document corpus (legal contracts, technical docs, support tickets, code repositories). Design an adaptive chunking strategy that maximizes retrieval precision across all document types.

### Expected Answer:

**Multi-Strategy Adaptive Chunking Architecture:**

1. **Document Classification Layer:**
   ```python
   class AdaptiveChunker:
       def __init__(self):
           self.strategies = {
               'legal': SemanticSectionChunker(max_tokens=1024),
               'technical': HierarchicalChunker(levels=['h1','h2','h3']),
               'support': ConversationTurnChunker(max_turns=3),
               'code': ASTBasedChunker(granularity='function')
           }
           self.classifier = DocumentTypeClassifier()
       
       def chunk(self, doc):
           doc_type = self.classifier.predict(doc)
           return self.strategies[doc_type].chunk(doc)
   ```

2. **Strategy Details:**

   - **Legal Documents:** Section-aware chunking respecting clause boundaries. Never split mid-clause. Include parent section headers as prefix metadata. Typical chunk: 800-1200 tokens.
   
   - **Technical Documentation:** Hierarchical chunking following document structure. Each chunk includes breadcrumb path (Chapter > Section > Subsection). Code blocks kept intact. Typical chunk: 400-800 tokens.
   
   - **Support Tickets:** Conversation-turn based. Group question + answer together. Include ticket metadata (severity, product, resolution status). Typical chunk: 200-500 tokens.
   
   - **Code Repositories:** AST-based chunking at function/class level. Include imports, docstrings, and type signatures. Cross-reference related functions. Typical chunk: 300-600 tokens.

3. **Universal Enhancements:**
   - **Overlap Strategy:** Semantic sentence-boundary overlap (not fixed token overlap)
   - **Context Injection:** Prepend document-level summary to each chunk
   - **Parent-Child Linking:** Store chunk hierarchy for expansion during retrieval
   - **Late Chunking:** Store full documents, chunk at query time for specific use cases

4. **Evaluation Framework:**
   - Retrieval precision@5 per document type
   - Chunk coherence score (semantic similarity within chunk)
   - Boundary quality (no mid-sentence splits)
   - A/B test different strategies per document type

---

## Question 3: RAG vs Fine-tuning Decision Framework
**Difficulty: Staff Level | Topic: Architecture Decisions | Asked at: Google, Amazon**

Your organization wants to build a domain-specific AI assistant. Create a decision framework for when to use RAG, fine-tuning, or a hybrid approach. Include cost analysis, maintenance burden, and accuracy trade-offs.

### Expected Answer:

**Decision Matrix:**

| Criterion | RAG | Fine-tuning | Hybrid |
|-----------|-----|-------------|--------|
| Knowledge freshness | Hours/minutes | Weeks/months | Hours |
| Factual accuracy | High (with citations) | Medium (hallucination risk) | Highest |
| Domain adaptation | Good for facts | Excellent for style/reasoning | Best |
| Cost (initial) | Low ($10K-50K infra) | High ($50K-500K compute) | Highest |
| Cost (ongoing) | Medium (vector DB, retrieval) | Low (inference only) | High |
| Latency | Higher (+retrieval overhead) | Lower (single inference) | Variable |
| Data requirements | Unstructured docs OK | Curated training data needed | Both |

**Decision Framework:**

1. **Use RAG When:**
   - Knowledge changes frequently (daily/weekly)
   - Source attribution/citations are required
   - You need to handle long-tail queries
   - Data is proprietary and can't be used for training
   - You need explainability (show retrieved sources)
   - Budget is limited for initial deployment

2. **Use Fine-tuning When:**
   - You need specific output format/style consistently
   - Domain reasoning patterns differ from base model
   - Latency is critical (no retrieval overhead acceptable)
   - Knowledge is stable and well-defined
   - You need the model to "think" differently, not just "know" more

3. **Use Hybrid When:**
   - You need both domain reasoning AND fresh knowledge
   - Complex multi-step tasks requiring domain expertise + facts
   - High accuracy requirements with auditability
   - Example: Fine-tune for medical reasoning, RAG for latest research papers

**Cost Analysis (1M queries/month):**
- RAG only: ~$15K/month (Vector DB: $3K, Embeddings: $2K, LLM: $8K, Infra: $2K)
- Fine-tuned only: ~$8K/month (Inference: $6K, Retraining quarterly: $2K amortized)
- Hybrid: ~$20K/month (Combined infrastructure)

**Maintenance Burden Score (1-10):**
- RAG: 6/10 (index updates, chunk quality, retrieval tuning)
- Fine-tuning: 4/10 (periodic retraining, eval pipelines)
- Hybrid: 9/10 (both systems + integration complexity)

---

## Question 4: Multi-Modal RAG Architecture
**Difficulty: Staff Level | Topic: Multi-Modal Systems | Asked at: Google, Meta**

Design a RAG system that handles text, images, tables, and diagrams from technical documentation. How do you create a unified retrieval experience across modalities?

### Expected Answer:

**Multi-Modal RAG Architecture:**

1. **Unified Embedding Space:**
   - Use multi-modal embedding models (CLIP, SigLIP, or custom)
   - Text: Standard text embeddings (1024-dim)
   - Images: Vision encoder → shared embedding space
   - Tables: Linearization + structured embedding
   - Diagrams: OCR + spatial layout encoding + vision embedding
   
   ```
   Document → Modal Splitter → [Text Chunks, Image Regions, Tables, Diagrams]
                                        ↓
                               Modal-Specific Encoders
                                        ↓
                               Unified Vector Space (1024-dim)
                                        ↓
                               Single Vector Index
   ```

2. **Document Decomposition Pipeline:**
   - **Layout Analysis:** Use document AI (LayoutLMv3/DocTR) to identify regions
   - **Table Extraction:** Convert to markdown/structured format + generate natural language descriptions
   - **Image Processing:** Generate captions (BLIP-2/LLaVA), extract text (OCR), encode visual features
   - **Diagram Understanding:** Flow detection, entity extraction, relationship mapping

3. **Retrieval Strategy:**
   ```python
   class MultiModalRetriever:
       def retrieve(self, query, modalities=['text','image','table']):
           # Embed query in unified space
           query_embedding = self.encode_query(query)
           
           # Search across all modalities
           results = self.vector_db.search(
               query_embedding, 
               top_k=20,
               filter={'modality': {'$in': modalities}}
           )
           
           # Cross-modal re-ranking
           reranked = self.cross_modal_reranker(query, results)
           
           # Context assembly with modal-aware formatting
           context = self.assemble_context(reranked[:5])
           return context
   ```

4. **Context Assembly for LLM:**
   - Text chunks: Direct insertion
   - Tables: Markdown format with column descriptions
   - Images: Base64 for vision LLMs, or detailed captions for text-only LLMs
   - Diagrams: Structured description + relationships + original image

5. **Challenges & Solutions:**
   - **Alignment problem:** Fine-tune contrastive loss across modalities on domain data
   - **Granularity mismatch:** Images are "one chunk" but may contain multiple concepts → region-based encoding
   - **Evaluation:** Separate metrics per modality + unified relevance score
   - **Cost:** Vision embeddings are 10x more expensive → cache aggressively

---

## Question 5: RAG Failure Modes and Mitigation
**Difficulty: Staff Level | Topic: Reliability Engineering | Asked at: OpenAI, Anthropic**

Enumerate the top failure modes in production RAG systems and design mitigation strategies for each. How do you build a self-healing RAG pipeline?

### Expected Answer:

**Critical Failure Modes & Mitigations:**

1. **Retrieval Failures:**
   
   | Failure Mode | Detection | Mitigation |
   |---|---|---|
   | Semantic gap (query ≠ document language) | Low retrieval scores | Query expansion, HyDE, multi-query |
   | Stale/outdated documents | Freshness timestamps | TTL-based re-indexing, freshness scoring |
   | Missing coverage | Null/low-confidence results | Graceful fallback to parametric knowledge |
   | Over-retrieval (noise) | Low precision scores | Stricter similarity thresholds, re-ranking |
   | Index corruption | Periodic integrity checks | Redundant indices, automatic rebuild |

2. **Generation Failures:**
   
   | Failure Mode | Detection | Mitigation |
   |---|---|---|
   | Hallucination despite context | NLI-based fact checking | Citation enforcement, constrained decoding |
   | Context overflow | Token count monitoring | Recursive summarization, map-reduce |
   | Irrelevant response | Relevance classifier | Answer validation against query intent |
   | Harmful/biased output | Content safety classifiers | Output guardrails, RLHF alignment |

3. **Self-Healing Architecture:**
   ```
   Query → Retrieval → Generation → Validation → Response
              ↓              ↓            ↓
         Fallback 1    Fallback 2    Retry Loop
              ↓              ↓            ↓
     Alternative    Rephrase &     Flag for
     Index/Search   Regenerate     Human Review
   ```

4. **Automated Recovery Mechanisms:**
   - **Query reformulation loop:** If retrieval confidence < threshold, automatically rephrase (max 3 attempts)
   - **Cascading retrieval:** Vector → BM25 → Knowledge Graph → Web Search
   - **Response validation:** NLI model checks if response is entailed by retrieved context
   - **Confidence scoring:** Aggregate retrieval score + generation confidence + validation score
   - **Circuit breaker:** If error rate > 5% in 5min window, fallback to cached/static responses

5. **Monitoring & Alerting:**
   - Real-time dashboards: Retrieval precision, response latency, hallucination rate
   - Automated regression detection: Compare daily metrics against baseline
   - User feedback loop: Thumbs up/down → fine-tune retrieval model weekly
   - Shadow evaluation: Run new models in parallel, compare before promoting
