# Core RAG — Retrieval-Augmented Generation

## 1. What RAG Is and Why It Exists

**Retrieval-Augmented Generation (RAG)** is an architecture pattern that grounds Large Language Model (LLM) outputs in external, factual data by retrieving relevant context at inference time and injecting it into the prompt.

### The Fundamental Problem RAG Solves

LLMs have three critical limitations:
1. **Knowledge cutoff** — Training data is frozen at a point in time
2. **Hallucination** — Models confidently generate plausible but false statements
3. **No access to private data** — Enterprise knowledge, internal docs, proprietary databases

RAG addresses all three by making the model "look things up" before answering.

### RAG = Retrieval + Augmentation + Generation

```
User Query → [Retrieve relevant docs] → [Augment prompt with context] → [Generate grounded answer]
```

### Why Not Just Use a Bigger Context Window?

| Factor | RAG | Large Context Window |
|--------|-----|---------------------|
| Cost | Pay for retrieval + small context | Pay for massive token count every call |
| Latency | Fast (small prompt) | Slow (100K+ tokens processed) |
| Accuracy | High (relevant chunks only) | Degrades with "lost in the middle" effect |
| Freshness | Real-time (re-index anytime) | Requires re-stuffing every call |
| Scalability | Millions of documents | Limited by context window size |
| Auditability | Clear citation trails | Hard to trace which part influenced answer |

**Architect's rule**: Context windows are for *session memory*; RAG is for *knowledge retrieval*.

---

## 2. RAG vs Fine-Tuning vs Prompt Engineering

### Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHEN TO USE WHAT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Prompt Engineering (hours, $0-10)                                │
│  ├─ Task is well-defined with few examples                       │
│  ├─ Model already "knows" the domain                             │
│  └─ You need quick iteration                                     │
│                                                                   │
│  RAG (days-weeks, $100-10K)                                      │
│  ├─ Knowledge changes frequently                                 │
│  ├─ You need citations / auditability                            │
│  ├─ Domain data is private / proprietary                         │
│  ├─ You need factual grounding                                   │
│  └─ Data volume exceeds context window                           │
│                                                                   │
│  Fine-Tuning (weeks-months, $1K-100K)                            │
│  ├─ You need to change model BEHAVIOR (tone, format, style)      │
│  ├─ Task requires specialized reasoning patterns                 │
│  ├─ You want to reduce prompt size / latency                     │
│  └─ Domain vocabulary is highly specialized                      │
│                                                                   │
│  RAG + Fine-Tuning (the best of both worlds)                     │
│  ├─ Fine-tune for behavior, RAG for knowledge                    │
│  └─ Example: fine-tuned medical model + RAG over patient records │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Comparison Matrix

| Dimension | Prompt Eng. | RAG | Fine-Tuning |
|-----------|-------------|-----|-------------|
| Knowledge freshness | Stale | Real-time | Stale (re-train needed) |
| Implementation cost | Very Low | Medium | High |
| Latency overhead | None | +200-800ms | None (inference) |
| Hallucination control | Low | High | Medium |
| Auditability | None | Full (citations) | None |
| Behavior modification | Limited | Limited | Strong |
| Data privacy | Risky (in prompt) | Controlled | Baked into weights |
| Maintenance burden | Low | Medium (indexing) | High (re-training) |

---

## 3. Complete RAG Pattern Taxonomy

### Level 1: Foundation Patterns

#### 3.1 Naive RAG
**What**: Simple embed-query → retrieve top-k → stuff into prompt → generate.
**When**: Proof of concept, simple Q&A over small document sets.
**Limitations**: No reranking, no query optimization, poor for complex questions.

```
Query → Embed → Vector Search (top-k) → Stuff Context → LLM → Answer
```

#### 3.2 Semantic RAG (Dense Retrieval)
**What**: Uses dense embeddings (e.g., text-embedding-3-large) for semantic similarity search.
**When**: Queries use natural language that differs lexically from source text.
**Strength**: Understands meaning, handles paraphrases.
**Weakness**: Misses exact keywords, entity names, codes.

#### 3.3 Keyword/BM25 RAG (Sparse Retrieval)
**What**: Uses TF-IDF / BM25 scoring for lexical matching.
**When**: Queries contain specific terms, IDs, codes, proper nouns.
**Strength**: Exact match, no embedding drift, interpretable.
**Weakness**: Misses semantic similarity, synonyms.

#### 3.4 Hybrid RAG
**What**: Combines dense (semantic) + sparse (BM25) retrieval with score fusion.
**When**: Production systems where you need both semantic understanding AND keyword precision.
**Fusion methods**: Reciprocal Rank Fusion (RRF), Convex Combination, learned weights.

```
Query → [Dense Search] ──┐
                          ├─ Score Fusion (RRF) → Top-k → LLM
Query → [BM25 Search] ───┘
```

**This is the default production pattern. Start here.**

### Level 2: Quality Enhancement Patterns

#### 3.5 Reranked RAG
**What**: After initial retrieval (top-50), apply a cross-encoder reranker to rescore and select top-k.
**When**: Initial retrieval has good recall but poor precision.
**Rerankers**: Cohere Rerank, BGE Reranker, cross-encoder/ms-marco-MiniLM-L-6-v2.
**Trade-off**: +100-300ms latency, significantly better precision.

#### 3.6 Parent-Child RAG
**What**: Index small chunks (children) for precise retrieval, but return the parent (larger section) for context.
**When**: Documents have hierarchical structure; small chunks retrieve well but lack context.
**Implementation**: Store parent_id on each child chunk; after retrieval, fetch parent.

#### 3.7 Hierarchical RAG
**What**: Multi-level index: summaries at top, sections in middle, paragraphs at bottom.
**When**: Large document collections where you need to first identify relevant documents, then relevant sections.
**Flow**: Query → match document summaries → match sections → match paragraphs.

#### 3.8 Multi-Query RAG
**What**: Generate multiple reformulations of the user query, retrieve for each, merge results.
**When**: Ambiguous queries, queries that could be interpreted multiple ways.
**Example**: "How does auth work?" → ["How is authentication implemented?", "What auth protocols are used?", "How do users log in?"]

#### 3.9 Query-Decomposition RAG
**What**: Break complex questions into sub-questions, retrieve for each, synthesize.
**When**: Multi-hop questions requiring information from multiple sources.
**Example**: "Compare the pricing of Azure OpenAI vs AWS Bedrock for GPT-4 class models" → Sub-Q1: Azure pricing, Sub-Q2: AWS pricing, Sub-Q3: Model comparison.

#### 3.10 HyDE-Style RAG (Hypothetical Document Embeddings)
**What**: Generate a hypothetical answer first, embed THAT, use it to retrieve similar real documents.
**When**: Short queries that don't embed well; queries phrased as questions but documents are declarative.
**Trade-off**: Extra LLM call (+500ms), but dramatically better retrieval for question-style queries.

```
Query → LLM generates hypothetical answer → Embed hypothetical → Search → Real docs → LLM final answer
```

### Level 3: Intelligent/Adaptive Patterns

#### 3.11 Self-Query RAG
**What**: LLM extracts structured filters from the natural language query before retrieval.
**When**: Queries contain implicit metadata filters ("recent papers on transformers" → date > 2023, topic = transformers).
**Implementation**: LLM parses query → {search_text: "transformers", filters: {date_gte: "2023-01-01", type: "paper"}}.

#### 3.12 Corrective RAG (CRAG)
**What**: After retrieval, evaluate if retrieved docs are relevant. If not, fall back to web search or rephrase.
**When**: You can't guarantee your index covers all queries; need graceful degradation.
**Flow**: Retrieve → Grade relevance → If low: web search / rephrase → Generate.

#### 3.13 Adaptive RAG
**What**: Route queries to different retrieval strategies based on query classification.
**When**: Diverse query types (factual, analytical, comparative, creative) need different handling.
**Router decides**: Simple lookup → Naive RAG | Complex → Multi-query | Comparative → Decomposition.

#### 3.14 Agentic RAG
**What**: An LLM agent decides WHEN to retrieve, WHAT to retrieve, and WHETHER to retrieve again.
**When**: Complex workflows where retrieval is one tool among many (calculator, SQL, API calls).
**Key difference**: The agent can decide retrieval is unnecessary, or do iterative retrieval.

```
Agent Loop:
  Observe query → Think → Act (maybe retrieve, maybe calculate, maybe ask for clarification)
  → Observe results → Think → Act again (maybe retrieve more) → Final answer
```

### Level 4: Specialized Patterns

#### 3.15 Graph RAG
**What**: Build a knowledge graph from documents; traverse graph relationships during retrieval.
**When**: Data has rich entity relationships; questions require multi-hop reasoning across entities.
**Variants**: 
- Microsoft GraphRAG: community summaries + graph traversal
- Neo4j + Vector: hybrid graph + vector retrieval
- Entity-centric: retrieve entity nodes + their neighborhoods

#### 3.16 SQL + Vector RAG
**What**: Combine structured data (SQL) with unstructured data (vector search) in one pipeline.
**When**: Questions span both structured databases and document collections.
**Example**: "What was the revenue impact mentioned in Q3 earnings call?" → SQL for revenue numbers + Vector for earnings call transcript.

#### 3.17 Temporal RAG
**What**: Time-aware retrieval that respects document freshness, versioning, and temporal context.
**When**: Documents change over time; users need the "current" version or time-specific answers.
**Implementation**: Timestamp-weighted scoring, version-aware deduplication, temporal filters.

#### 3.18 Multimodal RAG
**What**: Retrieve and reason over text, images, tables, charts, and diagrams.
**When**: Documents contain critical visual information (architecture diagrams, charts, screenshots).
**Approaches**: 
- Embed images with CLIP/SigLIP → multimodal vector search
- OCR + captioning → text-based retrieval
- Native multimodal models (GPT-4V, Gemini) for understanding

#### 3.19 Federated RAG
**What**: Query multiple independent RAG systems and merge results.
**When**: Data lives in multiple teams/systems with different access controls, schemas, or freshness requirements.
**Architecture**: Query router → Fan-out to N indices → Merge + deduplicate → Generate.

#### 3.20 Memory-Augmented RAG
**What**: Maintain a conversation memory / user preference store alongside document retrieval.
**When**: Multi-turn conversations where context accumulates; personalized responses.
**Stores**: Short-term (conversation buffer), Long-term (user preferences), Episodic (past interactions).

### Level 5: Emerging Patterns

#### 3.21 Speculative RAG
**What**: Generate multiple draft answers in parallel using different retrieved subsets, then verify.
**When**: High-stakes applications where you want to cross-check multiple "perspectives."

#### 3.22 Cache-Augmented RAG
**What**: Pre-compute answers for frequent queries; serve from cache, fall through to full RAG.
**When**: High-traffic systems with repetitive query patterns.

#### 3.23 Late-Interaction RAG (ColBERT-style)
**What**: Store per-token embeddings; compute fine-grained similarity at retrieval time.
**When**: Need better retrieval quality than single-vector, but faster than cross-encoder reranking.

---

## 4. Pattern Decision Matrix

| Situation | Recommended Pattern | Why |
|-----------|-------------------|-----|
| MVP / POC | Naive RAG | Fast to build, validates concept |
| First production system | Hybrid RAG + Reranking | Best quality/complexity ratio |
| Complex multi-part questions | Query Decomposition | Breaks problem into solvable parts |
| Ambiguous queries | Multi-Query | Covers interpretation space |
| Structured + unstructured data | SQL + Vector RAG | Bridges both worlds |
| Highly relational data | Graph RAG | Leverages entity connections |
| Multi-turn conversation | Memory-Augmented RAG | Maintains context across turns |
| Unknown query coverage | Corrective RAG | Graceful degradation |
| Diverse query types | Adaptive RAG | Right tool for each query |
| Complex multi-tool workflows | Agentic RAG | Agent decides retrieval strategy |
| Visual documents (PDFs, diagrams) | Multimodal RAG | Captures visual information |
| Time-sensitive data | Temporal RAG | Freshness-aware retrieval |
| Multi-team/multi-system | Federated RAG | Respects data boundaries |
| Short question, long docs | HyDE | Bridges query-document gap |

---

## 5. RAG Failure Modes and Diagnosis

### Failure Taxonomy

| Failure Mode | Symptom | Root Cause | Fix |
|-------------|---------|------------|-----|
| **Missing retrieval** | Answer says "I don't know" but info exists | Poor chunking, bad embeddings, missing metadata | Improve chunking, try hybrid search |
| **Wrong retrieval** | Answer cites irrelevant docs | Query-document semantic gap | Add reranking, try HyDE or multi-query |
| **Partial retrieval** | Answer is incomplete | Relevant info split across chunks | Parent-child chunking, increase top-k |
| **Stale retrieval** | Answer uses outdated info | No re-indexing pipeline | Add temporal awareness, version tracking |
| **Hallucinated synthesis** | Answer adds info not in context | LLM ignoring/embellishing context | Stronger system prompts, groundedness checks |
| **Lost in the middle** | Misses info in middle of context | LLM attention bias to start/end | Reorder chunks by relevance, reduce context size |
| **Over-retrieval** | Too much irrelevant context dilutes answer | Low precision, no reranking | Add reranking, stricter similarity thresholds |
| **Access violation** | Returns info user shouldn't see | Missing ACL filtering | Implement access-controlled retrieval |
| **Format mismatch** | Tables/code rendered poorly | Chunking breaks structured content | Table-aware chunking, format preservation |

### Diagnosis Workflow

1. **Check retrieval quality FIRST** — Is the right information being retrieved?
   - Log retrieved chunks for failed queries
   - Compute recall@k against ground truth
2. **Check chunk quality** — Are chunks self-contained and meaningful?
   - Review chunk boundaries manually
   - Check chunk sizes (too small = no context, too large = noise)
3. **Check generation quality** — Given perfect context, does the LLM answer correctly?
   - Test with manually curated perfect context
   - If still fails → prompt engineering or model issue

---

## 6. RAG Quality Metrics

### Retrieval Metrics

| Metric | Formula | What It Measures |
|--------|---------|-----------------|
| **Recall@k** | (Relevant docs in top-k) / (Total relevant docs) | Coverage — did we find all relevant docs? |
| **Precision@k** | (Relevant docs in top-k) / k | Precision — are retrieved docs actually relevant? |
| **MRR** | 1/rank of first relevant doc | How quickly do we surface relevant info? |
| **nDCG@k** | Normalized Discounted Cumulative Gain | Ranking quality with graded relevance |
| **Hit Rate** | Queries with at least 1 relevant doc in top-k | Basic coverage check |

### Generation Metrics

| Metric | What It Measures | How to Compute |
|--------|-----------------|----------------|
| **Groundedness** | Is the answer supported by retrieved context? | LLM-as-judge or NLI model |
| **Faithfulness** | Does the answer avoid adding information beyond context? | Claim decomposition + verification |
| **Answer Relevance** | Does the answer address the question? | LLM-as-judge scoring |
| **Completeness** | Does the answer cover all aspects of the question? | Rubric-based evaluation |
| **Citation Accuracy** | Do citations point to correct source passages? | Automated verification |

### End-to-End Metrics

| Metric | What It Measures |
|--------|-----------------|
| **Answer Correctness** | Factual accuracy against ground truth |
| **Latency (P50/P95/P99)** | End-to-end response time |
| **Cost per query** | Embedding + retrieval + LLM token costs |
| **User satisfaction** | Thumbs up/down, follow-up questions |

### Evaluation Frameworks

- **RAGAS** — Open-source RAG evaluation (faithfulness, answer relevance, context recall/precision)
- **DeepEval** — LLM evaluation framework with RAG-specific metrics
- **Azure AI Evaluation SDK** — Built-in groundedness, relevance, coherence metrics
- **Custom evals** — Domain-specific rubrics evaluated by LLM-as-judge

---

## 7. Architect's Rules for RAG

### Rule 1: Start Simple, Add Complexity Only When Evals Demand It

```
Start: Naive RAG (embed + retrieve + generate)
  ↓ Eval shows poor retrieval? → Add hybrid search
  ↓ Eval shows wrong docs in top-k? → Add reranking  
  ↓ Eval shows incomplete answers? → Add parent-child chunking
  ↓ Eval shows query-doc mismatch? → Add query rewriting / HyDE
  ↓ Eval shows diverse failure modes? → Add adaptive routing
  ↓ Eval shows multi-hop failures? → Add query decomposition
  ↓ Business requires multi-tool? → Go agentic
```

### Rule 2: Measure Before You Optimize

Never add a pattern because it's "cool." Add it because your evaluation suite shows a specific failure that the pattern addresses. Every added component is:
- More latency
- More cost
- More failure points
- More maintenance

### Rule 3: Chunking Is the Most Important Decision

Bad chunking cannot be fixed downstream. Get this right first:
- Chunks must be semantically self-contained
- Chunks must retain enough context to be useful alone
- Chunk size should match your retrieval evaluation results (benchmark 256 vs 512 vs 1024 tokens)

### Rule 4: Retrieval Quality > Generation Quality

If retrieval is bad, no amount of prompt engineering will save you. Invest 80% of effort in:
1. Chunking strategy
2. Embedding model selection
3. Hybrid retrieval
4. Reranking

### Rule 5: Build Evaluation First

Before building your RAG pipeline, build your evaluation pipeline:
1. Curate 50-100 question-answer pairs with source references
2. Automate retrieval and generation metric computation
3. Run evals on every pipeline change
4. Track metrics over time (regression detection)

---

## Summary: The RAG Architect's Mental Model

```
                    ┌─────────────────────────────────────┐
                    │         USER QUERY                    │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │     QUERY UNDERSTANDING               │
                    │  • Classification                     │
                    │  • Rewriting                          │
                    │  • Decomposition                      │
                    │  • Filter extraction                  │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │     RETRIEVAL                         │
                    │  • Dense (semantic)                   │
                    │  • Sparse (BM25)                      │
                    │  • Hybrid fusion                      │
                    │  • Metadata filtering                 │
                    │  • Reranking                          │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │     CONTEXT ASSEMBLY                  │
                    │  • Token budget management            │
                    │  • Deduplication                      │
                    │  • Ordering (relevance/recency)       │
                    │  • Citation preparation               │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │     GENERATION                        │
                    │  • Grounded generation                │
                    │  • Citation injection                 │
                    │  • Confidence signaling               │
                    │  • Format control                     │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────▼───────────────────────┐
                    │     POST-PROCESSING                   │
                    │  • Groundedness verification          │
                    │  • Hallucination detection            │
                    │  • Response formatting                │
                    │  • Observability logging              │
                    └─────────────────────────────────────┘
```

**The best RAG system is the simplest one that passes your evaluations.**
