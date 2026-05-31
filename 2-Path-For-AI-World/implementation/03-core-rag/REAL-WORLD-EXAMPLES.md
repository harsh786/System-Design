# Core RAG: Real-World Examples & Case Studies

## Case Study 1: How Notion AI Built Their RAG System

### Context
Notion launched Notion AI in early 2023, serving 30M+ users with AI-powered search and Q&A over their personal and team workspaces. The challenge: user-generated content is wildly heterogeneous — meeting notes, project specs, personal journals, databases, embedded files — all needing to be searchable with AI.

### Chunking Strategy for User-Generated Content

Notion's content model is block-based (paragraphs, headings, toggles, databases, embeds). Their chunking strategy leverages this structure:

```
Notion's Hierarchical Chunking Approach:
─────────────────────────────────────────
Level 1: Page-level metadata envelope
  ├── Title, created_by, last_edited, workspace, permissions
  │
Level 2: Semantic sections (split on H1/H2 boundaries)
  ├── Section: "Q3 Planning" (H2 boundary)
  │   ├── Chunk A: paragraphs 1-4 (≈380 tokens)
  │   ├── Chunk B: paragraphs 5-7 + bullet list (≈290 tokens)
  │   └── Chunk C: embedded database summary (≈150 tokens)
  │
Level 3: Atomic blocks (for database rows, code blocks)
  └── Each database row = 1 chunk with column context prepended
```

**Key design decisions:**
- **Target chunk size: 256-512 tokens** — they found this sweet spot through A/B testing on answer quality
- **Context window prepending**: Every chunk gets a "breadcrumb" prefix: `[Workspace: Acme Corp > Project: Q3 Launch > Page: Sprint Planning > Section: Timeline]`
- **Database rows as first-class chunks**: A Notion database with 200 rows produces 200 individual chunks, each prefixed with column headers as context
- **Toggle blocks expand**: Content inside collapsed toggles is indexed as if expanded — users expect AI to find content regardless of UI state

### Hybrid Search Architecture

```
User Query: "What was the decision on the pricing model?"
                    │
                    ▼
┌─────────────────────────────────────────────┐
│           Query Understanding               │
│  • Expand: "pricing model" → "pricing",    │
│    "monetization", "revenue model"          │
│  • Detect intent: factual lookup            │
└─────────────────────┬───────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────┐    ┌─────────────────────┐
│  Vector Search  │    │  Keyword Search     │
│  (Pinecone)     │    │  (Elasticsearch)    │
│                 │    │                     │
│  embed(query)   │    │  BM25 + boosting:   │
│  → top-40       │    │  title^3, H1^2,     │
│  cosine sim     │    │  body^1             │
│                 │    │  → top-40           │
└────────┬────────┘    └──────────┬──────────┘
         │                        │
         └────────────┬───────────┘
                      ▼
┌─────────────────────────────────────────────┐
│        Reciprocal Rank Fusion (RRF)         │
│  score = Σ 1/(k + rank_i), k=60            │
│  Merge → top-20 candidates                 │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│           Reranking (Cohere Rerank)         │
│  Cross-encoder scoring → top-5             │
└─────────────────────┬───────────────────────┘
                      ▼
┌─────────────────────────────────────────────┐
│        Permission Filtering (post-hoc)      │
│  Check: user has access to parent page?     │
│  Filter out unauthorized chunks             │
│  Backfill from rank 6+ if needed            │
└─────────────────────────────────────────────┘
```

### Multi-Workspace Isolation

Notion's multi-tenancy requirement is strict — a user in Workspace A must never see results from Workspace B, even if they're the same person.

**Implementation:**
- **Pinecone namespaces**: Each workspace gets its own namespace. Queries are scoped to namespace at the infrastructure level — no filter-based isolation.
- **Metadata filtering**: Within a namespace, additional filters for page-level permissions (private pages, shared pages, team spaces)
- **Permission cache**: Redis cache of user→accessible_page_ids with 5-minute TTL. On permission change, cache is invalidated via webhook from Notion's permission service.

```
Isolation Guarantees:
─────────────────────
• Workspace isolation: Infrastructure-level (Pinecone namespaces)
• Page isolation: Query-time metadata filter + post-retrieval check
• Freshness: Permission changes reflected within 5 minutes
• Audit: Every RAG query logged with workspace_id, user_id, retrieved_page_ids
```

---

## Case Study 2: How Perplexity.ai Combines RAG + Web Search

### Architecture Overview

Perplexity serves 10M+ queries/day combining real-time web search with RAG over cached/indexed content. Their system is a hybrid that treats the live web as a dynamic knowledge base.

```
Perplexity's Query Pipeline (simplified):
──────────────────────────────────────────

User: "What are the latest developments in EU AI regulation?"
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Query Classification                │
│  • Temporal signal: "latest" → needs web    │
│  • Topic: policy/regulation → authoritative │
│    sources needed                           │
│  • Complexity: multi-faceted → needs        │
│    multiple sources                         │
└─────────────────────┬───────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌──────────────┐ ┌──────────┐ ┌───────────────┐
│ Web Search   │ │ News API │ │ Cached Index  │
│ (Bing API)   │ │ (recent  │ │ (previously   │
│ top-10 URLs  │ │ 24hrs)   │ │ crawled EU    │
│              │ │          │ │ policy docs)  │
└──────┬───────┘ └────┬─────┘ └──────┬────────┘
       │               │              │
       ▼               ▼              ▼
┌─────────────────────────────────────────────┐
│         Parallel Content Fetching           │
│  • Crawl top URLs (Playwright headless)     │
│  • Extract main content (readability)       │
│  • Chunk on-the-fly (paragraph-level)       │
│  • Timeout: 3 seconds max per URL           │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│      Relevance Scoring & Deduplication      │
│  • Cross-encoder reranking of all chunks    │
│  • Deduplicate near-identical content       │
│  • Source authority scoring (domain trust)   │
│  • Recency weighting (newer = higher)       │
│  → Select top-8 chunks for context          │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│         Answer Generation (LLM)             │
│  • System: "Cite sources with [1][2]..."    │
│  • Context: 8 chunks with source metadata   │
│  • Generate answer with inline citations    │
│  • Follow-up questions suggested            │
└─────────────────────────────────────────────┘
```

### Key Technical Decisions

**1. Aggressive caching of web content:**
- Previously crawled pages stored in their own vector index
- If a URL was crawled < 24hrs ago, serve from cache
- Reduces crawl load by ~60% for popular topics

**2. Query decomposition for complex questions:**
```
Original: "Compare EU AI Act with US executive order on AI safety"
    │
    ├── Sub-query 1: "EU AI Act key provisions 2024"
    ├── Sub-query 2: "US executive order AI safety October 2023"
    └── Sub-query 3: "EU vs US AI regulation comparison"
    
Each sub-query → independent retrieval → merged context
```

**3. Source reliability scoring:**
```python
# Perplexity's domain authority heuristic (conceptual)
SOURCE_TIERS = {
    "tier_1": ["reuters.com", "nature.com", "gov.uk", "arxiv.org"],  # weight: 1.5x
    "tier_2": ["techcrunch.com", "theverge.com", "bbc.com"],          # weight: 1.2x
    "tier_3": ["medium.com", "substack.com"],                          # weight: 0.8x
    "tier_4": ["reddit.com", "quora.com"],                             # weight: 0.5x
}
# Combined with recency: score = relevance * authority * recency_decay(age_hours)
```

**4. Latency budget:**
```
Total target: < 4 seconds end-to-end
├── Query understanding: 100ms
├── Web search API call: 400ms
├── Parallel crawling (3s timeout, but most return in): 1500ms
├── Reranking: 200ms
├── LLM generation (streaming starts at): 800ms
└── Buffer: 1000ms
```

---

## Case Study 3: Enterprise Legal Document Search

### Company Profile
A top-20 US law firm with 120,000+ legal documents (contracts, briefs, memos, case law annotations) needed AI-powered search with precise citation and strict access controls.

### Requirements That Shaped Architecture

| Requirement | Impact on Design |
|---|---|
| Exact citation (page, paragraph) | Chunks must preserve location metadata |
| Attorney-client privilege | Zero tolerance for cross-client data leakage |
| Regulatory compliance (SOC2, HIPAA) | On-premise vector DB, no data leaves network |
| Long documents (200+ pages) | Hierarchical chunking with parent-child |
| Precedent finding | Semantic similarity across case types |
| Audit trail | Every retrieval logged for compliance |

### Architecture

```
Legal RAG Architecture:
───────────────────────

Document Ingestion:
┌─────────────────────────────────────────────────────────┐
│  PDF/DOCX → Layout Parser (Microsoft Document AI)       │
│  ├── Detect: headers, paragraphs, footnotes, tables     │
│  ├── Preserve: page numbers, section numbers            │
│  ├── Extract: defined terms, party names, dates         │
│  └── Output: structured JSON with positional metadata   │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  Chunking: Legal-Aware Strategy                         │
│  ├── Split on: section boundaries (§), article breaks   │
│  ├── Keep together: definition + its usage context      │
│  ├── Max chunk: 512 tokens (with 50-token overlap)      │
│  ├── Each chunk gets:                                   │
│  │   • document_id, page_number, section_path           │
│  │   • client_id (access control)                       │
│  │   • matter_id (case grouping)                        │
│  │   • document_type (contract/brief/memo/statute)      │
│  │   • jurisdiction, practice_area                      │
│  └── Parent chunk: full section for context expansion    │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  Storage: Weaviate (on-premise, air-gapped)             │
│  ├── Collection per practice area                       │
│  ├── Multi-tenancy: client_id as tenant key             │
│  ├── Vectors: text-embedding-3-large (1536d)            │
│  └── Inverted index: for exact term matching            │
└─────────────────────────────────────────────────────────┘

Query Time:
┌─────────────────────────────────────────────────────────┐
│  1. Auth check: user → client_ids they can access       │
│  2. Query expansion: legal synonyms ("breach" →         │
│     "default", "violation", "non-compliance")           │
│  3. Hybrid search: vector + BM25 with client filter     │
│  4. Rerank: cross-encoder fine-tuned on legal Q&A       │
│  5. Parent retrieval: expand top chunks to full section  │
│  6. Citation formatting: "See [Doc Name], §4.2, p.17"   │
│  7. Audit log: query, user, retrieved docs, timestamp   │
└─────────────────────────────────────────────────────────┘
```

### Access Control Implementation

```python
# Pre-query permission resolution
class LegalAccessControl:
    """
    Three-tier access model:
    1. Firm-wide: statutes, public case law (all attorneys)
    2. Practice group: shared precedent within group
    3. Matter-specific: only assigned attorneys + partners
    """
    
    def resolve_accessible_scope(self, user_id: str) -> SearchScope:
        user = self.get_user(user_id)
        return SearchScope(
            client_ids=user.assigned_client_ids,
            matter_ids=user.assigned_matter_ids,
            practice_areas=user.practice_groups,
            firm_wide_collections=["statutes", "public_case_law"],
        )
    
    def post_retrieval_verify(self, user_id: str, chunks: list) -> list:
        """Second check — defense in depth against filter bypass."""
        scope = self.resolve_accessible_scope(user_id)
        verified = []
        for chunk in chunks:
            if chunk.client_id in scope.client_ids or chunk.is_firm_wide:
                verified.append(chunk)
            else:
                self.alert_security_team(user_id, chunk.document_id)
        return verified
```

### Citation Generation

```
Query: "What is the termination clause in the Acme Corp MSA?"

Retrieved chunk:
  document: "Acme Corp Master Services Agreement v3.2"
  section_path: "Article VII > Section 7.2 > Termination for Convenience"
  page: 34
  paragraph: 2

Generated citation:
  "Either party may terminate this Agreement for convenience upon sixty (60) 
   days' prior written notice..."
   
   — Acme Corp MSA v3.2, Art. VII, §7.2(b), p.34
```

---

## Chunking Strategy Comparison: Real Experiments

### Experiment Setup

A team at a Series B AI startup ran systematic experiments on their customer support knowledge base (8,400 articles, avg 1,200 words each). They measured answer quality using human evaluators (3 raters per question, 200 test questions).

### Results

| Strategy | Chunk Size | Overlap | Retrieval Recall@5 | Answer Quality (1-5) | Latency (p50) | Cost/query |
|---|---|---|---|---|---|---|
| Fixed-size | 128 tokens | 0 | 0.62 | 3.1 | 180ms | $0.0003 |
| Fixed-size | 256 tokens | 25 | 0.71 | 3.6 | 195ms | $0.0004 |
| Fixed-size | 512 tokens | 50 | 0.74 | 3.9 | 210ms | $0.0005 |
| Fixed-size | 1024 tokens | 100 | 0.69 | 3.7 | 240ms | $0.0008 |
| Sentence-based | ~3-5 sentences | — | 0.68 | 3.4 | 185ms | $0.0003 |
| Paragraph-based | natural ¶ | — | 0.76 | 4.0 | 205ms | $0.0005 |
| Semantic (embedding similarity threshold) | variable | — | 0.79 | 4.2 | 350ms | $0.0012 |
| Hierarchical (parent-child) | 256 child / 1024 parent | — | 0.82 | 4.4 | 280ms | $0.0009 |

### Key Findings

**1. The "U-curve" of chunk size:**
```
Answer Quality
    │
4.5 │              ╭───╮
4.0 │         ╭────╯   ╰────╮
3.5 │    ╭────╯              ╰────╮
3.0 │────╯                        ╰────
2.5 │
    └─────────────────────────────────────
    64   128   256   512   1024  2048
              Chunk Size (tokens)

Sweet spot: 256-512 tokens for most use cases
Too small: loses context, retrieves noise
Too large: dilutes relevance, wastes context window
```

**2. Overlap matters more than expected:**
- 10-20% overlap: +8% recall vs no overlap
- Reason: key information often spans chunk boundaries
- Diminishing returns above 25% overlap

**3. Semantic chunking wins on quality but costs more:**
- 2x embedding cost (need to embed sentences individually to find split points)
- 1.7x latency (extra computation step)
- Worth it for high-value use cases (legal, medical)

**4. Hierarchical chunking is the production winner:**
- Retrieve on small chunks (precision)
- Return parent chunks to LLM (context)
- Best quality-to-cost ratio for production systems

---

## Embedding Model Selection: Real Benchmarks

### Benchmark: MTEB Retrieval Subset + Custom Domain Evaluation

Tested on 3 datasets: (1) general knowledge Q&A, (2) technical documentation, (3) customer support tickets.

| Model | Dimensions | MTEB Retrieval (nDCG@10) | Tech Docs (nDCG@10) | Support Tickets | Latency (1K docs) | Cost per 1M tokens | Notes |
|---|---|---|---|---|---|---|---|
| OpenAI text-embedding-ada-002 | 1536 | 0.498 | 0.52 | 0.61 | 3.2s | $0.10 | Legacy, still widely used |
| OpenAI text-embedding-3-small | 1536 | 0.531 | 0.55 | 0.64 | 2.8s | $0.02 | 5x cheaper than ada-002 |
| OpenAI text-embedding-3-large | 3072 | 0.588 | 0.61 | 0.68 | 4.1s | $0.13 | Best OpenAI option |
| Cohere embed-v3 (english) | 1024 | 0.572 | 0.59 | 0.67 | 3.5s | $0.10 | Strong multilingual variant |
| Voyage AI voyage-large-2 | 1536 | 0.601 | 0.63 | 0.66 | 3.8s | $0.12 | Top on code retrieval |
| BGE-large-en-v1.5 (open source) | 1024 | 0.541 | 0.56 | 0.58 | 1.2s* | $0 (self-host) | *On A100 GPU |
| E5-mistral-7b-instruct | 4096 | 0.613 | 0.64 | 0.69 | 8.5s* | $0 (self-host) | Best open-source, but huge |
| Nomic embed-text-v1.5 | 768 | 0.529 | 0.54 | 0.60 | 1.0s* | $0 (self-host) | Best cost/performance ratio |

*Self-hosted latency on single A100 40GB GPU

### Decision Framework

```
Decision Tree for Embedding Model Selection:
─────────────────────────────────────────────

Q: Is data sovereignty required? (no data leaves your infra)
├── YES → Self-hosted options:
│   ├── Budget for GPU? → E5-mistral-7b (best quality)
│   ├── Limited GPU? → BGE-large or Nomic (good quality, smaller)
│   └── CPU only? → all-MiniLM-L6-v2 (acceptable quality)
│
└── NO → API options:
    ├── Cost-sensitive (>1M docs)? → text-embedding-3-small ($0.02/1M tok)
    ├── Best quality needed? → text-embedding-3-large or Voyage
    ├── Multilingual? → Cohere embed-v3 multilingual
    └── Code/technical? → Voyage-code-2
```

### Real-World Cost Comparison (1M document corpus, avg 500 tokens/doc)

```
Embedding 1M documents (500M total tokens):
─────────────────────────────────────────────
text-embedding-3-small: 500M × $0.02/1M = $10.00
text-embedding-3-large: 500M × $0.13/1M = $65.00
Cohere embed-v3:        500M × $0.10/1M = $50.00
Self-hosted BGE-large:  ~4 hours on A100 = $8.00 (spot pricing)
Self-hosted E5-mistral: ~18 hours on A100 = $36.00

Monthly re-embedding (10% corpus changes):
text-embedding-3-small: $1.00/month
text-embedding-3-large: $6.50/month
Self-hosted BGE-large:  $0.80/month (amortized GPU)
```

---

## Hybrid Search in Practice: Elasticsearch + Vector Search

### Company: Mid-size e-commerce platform (2M products, 500K support articles)

### Problem
Pure vector search failed on:
- Exact product SKUs ("Find policy for SKU-X7829-BL")
- Specific error codes ("Error E-4401 troubleshooting")
- Boolean queries ("return policy AND international AND electronics")

Pure keyword search failed on:
- Semantic queries ("how to fix a printer that makes grinding noises")
- Paraphrased questions ("refund timeline" vs. "how long to get money back")

### Implementation: Elasticsearch 8.x with kNN + BM25

```json
// Elasticsearch query combining vector + keyword search
{
  "query": {
    "bool": {
      "should": [
        {
          // BM25 keyword component
          "multi_match": {
            "query": "return policy international electronics",
            "fields": ["title^3", "content", "tags^2"],
            "type": "best_fields",
            "boost": 0.4
          }
        }
      ]
    }
  },
  "knn": {
    // Vector component
    "field": "content_embedding",
    "query_vector": [0.012, -0.034, ...],  // 1536 dims
    "k": 20,
    "num_candidates": 100,
    "boost": 0.6
  },
  "size": 10
}
```

### Results (A/B test over 4 weeks, 50K queries)

| Metric | Keyword Only | Vector Only | Hybrid (0.4/0.6) | Hybrid + Rerank |
|---|---|---|---|---|
| Recall@10 | 0.58 | 0.71 | 0.81 | 0.87 |
| MRR@10 | 0.42 | 0.55 | 0.64 | 0.72 |
| Exact match (SKU queries) | 0.95 | 0.31 | 0.93 | 0.94 |
| Semantic queries | 0.29 | 0.73 | 0.74 | 0.81 |
| User satisfaction (thumbs up) | 61% | 68% | 79% | 84% |
| p95 latency | 45ms | 120ms | 155ms | 320ms |

**The 23% recall improvement**: From 0.58 (keyword only) to 0.81 (hybrid) — a 23 percentage point improvement that directly translated to 18% fewer "contact support" escalations.

### Tuning the Hybrid Weight

```
They tested weights from 0.0 (keyword only) to 1.0 (vector only):

Recall@10
    │
0.85│                    ╭──────╮
0.80│               ╭────╯      ╰──╮
0.75│          ╭────╯               ╰──╮
0.70│     ╭────╯                       ╰──
0.65│╭────╯
0.60│╯
    └──────────────────────────────────────
   0.0   0.2   0.4   0.6   0.8   1.0
         Vector weight (keyword = 1 - x)

Optimal: 0.55-0.65 vector weight for this dataset
But varies by query type — they added a classifier:
  - Exact lookup queries → weight shifts to 0.2 (more keyword)
  - Semantic questions → weight shifts to 0.8 (more vector)
```

---

## Reranking ROI: Before/After Metrics

### Company: B2B SaaS with 15K knowledge base articles, serving 2000 support agents

### Setup
- Base retrieval: Pinecone (cosine similarity), top-20 candidates
- Reranker: Cohere Rerank v3 (cross-encoder), narrowing to top-5
- LLM: GPT-4-turbo for answer generation

### Before Reranking (vector retrieval only → LLM)

```
Pipeline: Query → Embed → Pinecone top-5 → GPT-4 → Answer

Metrics (measured over 10K queries, 2 weeks):
- Answer correctness (human eval): 71%
- Answer contains hallucination: 12%
- "Relevant doc in top-5": 68%
- "Relevant doc in top-20": 89%  ← Gap shows retrieval has it but ranking is wrong
- Avg tokens in context: 2,800
- Cost per query: $0.038
```

### After Adding Reranking

```
Pipeline: Query → Embed → Pinecone top-20 → Cohere Rerank → top-5 → GPT-4 → Answer

Metrics (same 10K queries):
- Answer correctness (human eval): 84% (+13 points)
- Answer contains hallucination: 5% (-7 points)
- "Relevant doc in top-5": 86% (+18 points)
- Avg tokens in context: 2,400 (better chunks = less noise)
- Cost per query: $0.041 (+$0.003 for reranking)
- Latency added: +180ms (p50)
```

### ROI Calculation

```
Investment:
- Cohere Rerank cost: $0.003/query × 50K queries/day = $150/day = $4,500/month
- Engineering time: 2 weeks to integrate and test = ~$15K one-time

Returns:
- 13% improvement in answer correctness
- Support ticket deflection improved from 45% to 58%
- 58% - 45% = 13% more tickets deflected
- 50K queries/day × 13% = 6,500 fewer human-handled tickets/day
- At $5/ticket average cost = $32,500/day saved = $975K/month saved

ROI: $975K saved / $4.5K cost = 216x monthly return
Payback period: < 1 day
```

### When Reranking Doesn't Help

They found reranking added minimal value for:
- Exact lookup queries (SKU, error code) — keyword match is already precise
- Queries where the correct doc isn't in top-20 — reranking can't surface what wasn't retrieved
- Very short queries (1-2 words) — not enough signal for cross-encoder

---

## RAG Failure Postmortem: "Lost in the Middle" Problem

### Incident: AI Research Assistant at a Biotech Company

**Date:** March 2024  
**System:** RAG-powered research assistant for drug discovery scientists  
**Impact:** Researchers reported that the AI "ignored" critical information from retrieved papers, leading to an incorrect safety assessment that was caught in peer review.

### Root Cause Analysis

The system retrieved 10 relevant paper excerpts and stuffed them all into the context window. The critical safety data was in position 6 out of 10. The LLM (GPT-4-turbo at the time) exhibited the well-documented "lost in the middle" phenomenon — strong attention to positions 1-3 and 9-10, weak attention to positions 4-7.

```
Attention Distribution (measured empirically on their queries):
──────────────────────────────────────────────────────────────

Position:  1    2    3    4    5    6    7    8    9    10
           │    │    │    │    │    │    │    │    │    │
Attention: ████ ███  ██   █    █    █    █    █    ██   ███
           High ─────────── Low ──────────────── Medium ──

Critical safety data was HERE (position 6) ──────────^
LLM effectively "skipped" it in 34% of test cases.
```

### Solution: Multi-Stage Approach

**1. Reduce context to top-5 (with reranking):**
```
Before: Retrieve 10 → all to LLM (noisy, lost-in-middle risk)
After:  Retrieve 20 → Rerank → top-5 to LLM (precise, concentrated)
```

**2. Relevance-ordered positioning:**
```
Position the most relevant chunk FIRST and LAST (primacy + recency bias):
[Most relevant] [3rd] [4th] [5th] [2nd most relevant]
```

**3. Iterative retrieval for complex queries:**
```
Step 1: Initial retrieval → Generate preliminary answer
Step 2: Identify gaps → Targeted follow-up retrieval
Step 3: Synthesize final answer with all evidence

This "RAG-then-verify" pattern caught the safety data that was 
previously missed 94% of the time (vs 66% before).
```

**4. Citation verification:**
```python
# Post-generation check: does the answer actually cite the safety-critical chunks?
def verify_critical_coverage(answer: str, critical_chunks: list) -> bool:
    """Ensure safety-relevant retrieved content is reflected in the answer."""
    for chunk in critical_chunks:
        if chunk.metadata.get("safety_relevant"):
            # Use NLI model to check if answer's claims align with chunk
            entailment = nli_model.check(premise=chunk.text, hypothesis=answer)
            if entailment.label == "contradiction" or entailment.label == "neutral":
                flag_for_human_review(answer, chunk)
                return False
    return True
```

### Metrics After Fix

| Metric | Before | After |
|---|---|---|
| Critical info reflected in answer | 66% | 94% |
| Hallucination rate | 8% | 2% |
| Average context tokens used | 4,200 | 2,100 |
| Cost per query | $0.052 | $0.034 |
| Researcher trust score (survey) | 3.2/5 | 4.5/5 |

---

## Cost Analysis: Running RAG at 1M Queries/Day

### Scenario: Enterprise knowledge assistant (50K documents, serving 10K employees)

```
Daily volume: 1,000,000 queries
Document corpus: 50,000 documents (~25M tokens total)
Average query: 25 tokens
Average retrieved context: 2,000 tokens (5 chunks × 400 tokens)
LLM: GPT-4-turbo (input: $10/1M tokens, output: $30/1M tokens)
Average answer length: 300 tokens
```

### Cost Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│  DAILY COST BREAKDOWN — 1M queries/day                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. EMBEDDING QUERIES                                       │
│     1M queries × 25 tokens = 25M tokens/day                │
│     text-embedding-3-small: 25M × $0.02/1M = $0.50/day     │
│     text-embedding-3-large: 25M × $0.13/1M = $3.25/day     │
│                                                             │
│  2. VECTOR DATABASE (Pinecone Serverless)                   │
│     50K docs × 5 chunks avg = 250K vectors                  │
│     Storage: ~$7/day (250K vectors × 1536 dims)             │
│     Queries: 1M reads/day = ~$8/day                         │
│     Total Pinecone: ~$15/day                                │
│                                                             │
│  3. RERANKING (Cohere Rerank)                               │
│     1M queries × 20 candidates × 400 tokens = 8B tokens     │
│     At $1/1K searches: 1M × $0.001 = $1,000/day            │
│     (This is the second largest cost!)                      │
│                                                             │
│  4. LLM GENERATION (GPT-4-turbo)                            │
│     Input: 1M × (system_prompt[500] + context[2000] +       │
│            query[25]) = 2.525B input tokens/day             │
│     Output: 1M × 300 = 300M output tokens/day              │
│                                                             │
│     Input cost: 2,525M × $10/1M = $25,250/day              │
│     Output cost: 300M × $30/1M = $9,000/day                │
│     Total LLM: $34,250/day                                  │
│                                                             │
│  5. INFRASTRUCTURE                                          │
│     API gateway, caching, monitoring: ~$200/day             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  TOTAL DAILY COST: ~$35,466/day                             │
│  COST PER QUERY: $0.0355                                    │
│  MONTHLY COST: ~$1,064,000/month                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  COST BREAKDOWN PIE:                                        │
│  ┌──────────────────────────────────┐                      │
│  │ LLM Generation:    96.6%  ██████████████████████████│   │
│  │ Reranking:          2.8%  █                         │   │
│  │ Vector DB:          0.4%  ▏                         │   │
│  │ Embeddings:         0.01% ▏                         │   │
│  │ Infrastructure:     0.6%  ▏                         │   │
│  └──────────────────────────────────┘                      │
│                                                             │
│  KEY INSIGHT: LLM is 96%+ of cost.                         │
│  Optimizing retrieval saves money by reducing context.      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies Applied

```
Optimization 1: Switch to GPT-4o-mini for simple queries (60% of traffic)
  - Classify query complexity → route simple to mini, complex to GPT-4-turbo
  - Savings: 60% × $34,250 × 0.9 (mini is 90% cheaper) = $18,495/day saved

Optimization 2: Semantic caching (identical/similar queries)
  - Cache hit rate: 23% (many employees ask similar questions)
  - Savings: 23% × $35,466 = $8,157/day saved

Optimization 3: Reduce context via better retrieval
  - Better reranking → 3 chunks instead of 5 (same quality)
  - Input tokens: 2,525M → 1,525M = $10,000/day saved

After all optimizations:
  Original: $35,466/day ($0.0355/query)
  Optimized: $12,800/day ($0.0128/query)
  Savings: 64%
```

---

## Production RAG Pipeline: Healthcare Company Architecture

### Company: Digital health platform serving 500 hospitals, 200K clinicians

### Requirements
- HIPAA compliant (PHI never in prompts, only de-identified medical knowledge)
- Sub-3-second response time for clinical decision support
- Must cite clinical guidelines (UpToDate, PubMed, hospital protocols)
- 99.9% uptime (clinicians depend on it during patient encounters)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION RAG - HEALTHCARE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌──────────────────────────────────────────┐  │
│  │  Clinician  │────▶│  API Gateway (Kong)                       │  │
│  │  (EHR embed)│     │  • Rate limiting per hospital             │  │
│  └─────────────┘     │  • JWT auth (hospital SSO)                │  │
│                      │  • PHI detection & blocking                │  │
│                      └──────────────┬───────────────────────────┘  │
│                                     │                               │
│                                     ▼                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Query Processing Service (Kubernetes, 12 replicas)           │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │ 1. PHI Scrubber: Remove any patient identifiers        │  │  │
│  │  │ 2. Medical NER: Detect drugs, conditions, procedures   │  │  │
│  │  │ 3. Query Expansion: SNOMED-CT synonyms                 │  │  │
│  │  │ 4. Intent Classification: diagnosis/treatment/dosing   │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                              │                                       │
│                 ┌────────────┼────────────┐                         │
│                 ▼            ▼            ▼                          │
│  ┌──────────────────┐ ┌───────────┐ ┌────────────────┐            │
│  │ Clinical         │ │ Drug DB   │ │ Hospital-      │            │
│  │ Guidelines Index │ │ (structured│ │ Specific       │            │
│  │ (Qdrant cluster) │ │ lookup)   │ │ Protocols      │            │
│  │                  │ │           │ │ (per-tenant)   │            │
│  │ • UpToDate       │ │ • FDA     │ │ • Formulary    │            │
│  │ • PubMed (curated│ │ • DrugBank│ │ • Order sets   │            │
│  │ • AHA/ACC/IDSA   │ │ • Interax │ │ • Care paths   │            │
│  │ • Cochrane       │ │           │ │                │            │
│  │ 2.5M chunks      │ │ 45K drugs │ │ 50K docs       │            │
│  └────────┬─────────┘ └─────┬─────┘ └───────┬────────┘            │
│           │                  │               │                      │
│           └──────────────────┼───────────────┘                      │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Evidence Assembly & Ranking                                  │  │
│  │  • Reranker (biomedical fine-tuned cross-encoder)            │  │
│  │  • Evidence grading (Level A/B/C based on source)            │  │
│  │  • Conflict detection (contradictory guidelines flagged)     │  │
│  │  • Select top-5 evidence chunks                              │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Answer Generation (Azure OpenAI, GPT-4, HIPAA BAA)          │  │
│  │  • System prompt: "You are a clinical decision support tool.  │  │
│  │    Cite evidence levels. Flag when evidence is limited.       │  │
│  │    Never recommend off-label without explicit flag."          │  │
│  │  • Structured output: {answer, citations[], confidence,       │  │
│  │    evidence_level, contraindications[], warnings[]}           │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Safety Layer (post-generation)                               │  │
│  │  • Hallucination detector (NLI against retrieved evidence)   │  │
│  │  • Dosage range checker (structured DB lookup)               │  │
│  │  • Contraindication cross-check                              │  │
│  │  • If confidence < 0.7 → prepend disclaimer                  │  │
│  │  • Audit log → compliance DB                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  OFFLINE PIPELINE (runs nightly + on-demand)                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • UpToDate sync: daily delta via API                        │  │
│  │  • PubMed: weekly batch + real-time for flagged topics       │  │
│  │  • Hospital protocols: webhook on update → re-chunk + embed  │  │
│  │  • Quality checks: embedding drift detection, coverage gaps  │  │
│  │  • A/B evaluation: sample 1% of queries for human review     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  SLAs:                                                               │
│  • p50 latency: 1.8s | p99: 4.2s                                   │
│  • Availability: 99.95% (multi-region Azure)                        │
│  • Freshness: guidelines updated within 24 hours of publication     │
│  • Citation accuracy: >98% (verified weekly)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Production Decisions

**1. Why Qdrant over Pinecone:**
- HIPAA requirement: data must stay in their Azure subscription
- Qdrant runs on their own AKS cluster within their VNet
- No data ever leaves their Azure tenant

**2. Biomedical reranker:**
- Standard Cohere Rerank performed 11% worse on medical queries vs general
- Fine-tuned a cross-encoder on PubMed Q&A pairs → +15% nDCG@5 on clinical queries
- Model: ms-marco-MiniLM fine-tuned on 50K medical Q&A pairs

**3. Evidence grading in prompts:**
```
Each retrieved chunk is tagged:
[Level A - RCT evidence] "Metformin reduces HbA1c by 1-1.5%..."
[Level B - Observational] "Long-term use associated with B12 deficiency..."
[Level C - Expert opinion] "Consider starting at 500mg for GI tolerance..."

The LLM is instructed to weight Level A > B > C and explicitly state evidence quality.
```

**4. Failure modes and mitigations:**

| Failure Mode | Detection | Mitigation |
|---|---|---|
| No relevant docs retrieved | Retrieval score < threshold | "Insufficient evidence" response + suggest specialist |
| Contradictory evidence | Conflict detection model | Present both sides with evidence levels |
| Outdated guideline | Freshness metadata check | Flag "guideline from [year], check for updates" |
| LLM hallucination | NLI verification | Block response, fallback to direct quotes |
| System overload | p99 > 5s | Degrade to cached frequent answers |

---

## Summary: Patterns Across All Case Studies

```
Universal RAG Production Patterns:
───────────────────────────────────
1. Hybrid search always beats single-mode (vector OR keyword)
2. Reranking is the highest-ROI addition to any RAG pipeline
3. LLM cost dominates — optimize retrieval to minimize context
4. Chunk size 256-512 tokens is the safe default
5. Hierarchical chunking (child retrieve, parent return) wins
6. Post-retrieval permission checks are non-negotiable for enterprise
7. "Lost in the middle" is real — limit to 5 chunks, order by relevance
8. Semantic caching saves 20-30% of costs at scale
9. Always have a safety/verification layer before user-facing output
10. Monitor retrieval quality separately from generation quality
```
