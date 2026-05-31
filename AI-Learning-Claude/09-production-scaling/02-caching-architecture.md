# Caching Architecture for AI Systems

## The Library Analogy

Imagine you're a librarian answering questions:
- **No cache:** Every question requires walking to the stacks, finding the book, reading it, then answering. Every. Single. Time.
- **Exact cache:** You keep a notebook of previous Q&A. Same question? Read from notebook instantly.
- **Semantic cache:** You recognize "What's the capital of France?" and "Tell me France's capital city" are the same question — one notebook entry serves both.

Caching in AI systems saves **money** (fewer API calls), **time** (milliseconds vs seconds), and **capacity** (serve more users with same resources).

---

## Why Caching is Critical for AI

| Without Cache | With Cache |
|--------------|------------|
| Every request costs $0.01-$0.10 | Repeated requests cost ~$0 |
| 500ms-5s latency per request | <50ms for cache hits |
| Limited throughput by model capacity | Cache hits don't use model at all |
| 100% GPU utilization at peak | GPU handles only unique requests |

**Real example:** A customer support bot gets asked "What are your hours?" 500 times/day. Without caching: 500 × $0.03 = $15/day on one question. With caching: $0.03 once, then free.

---

## The 9 Cache Types for AI Systems

```mermaid
flowchart TB
    Request[User Request] --> Auth[8. Auth Decision Cache]
    Auth --> Prompt[1. Prompt/Prefix Cache]
    Prompt --> Semantic[2. Semantic Response Cache]
    Semantic -->|Miss| Embed[5. Embedding Cache]
    Embed --> Retrieval[3. Retrieval Cache]
    Retrieval --> Rerank[4. Reranker Cache]
    Rerank --> Tool[6. Tool Result Cache]
    Tool --> Doc[7. Document Parse Cache]
    Doc --> LLM[LLM Inference]
    LLM --> Eval[9. Eval Cache]
    LLM --> Response[Response]
    
    Semantic -->|Hit| Response
    
    style Semantic fill:#90EE90
    style Response fill:#87CEEB
```

---

### 1. Prompt/Prefix Cache (KV Cache)

**What:** When many requests share the same system prompt or prefix, cache the computed attention states.

**Analogy:** Like pre-reading the introduction of a textbook once, then jumping straight to the relevant chapter for each student's question.

```
System prompt (2000 tokens) + User message (50 tokens)
                ↓
First request:  Compute all 2050 tokens        (slow)
Second request: Reuse 2000 cached + compute 50  (fast!)
```

**Savings:** 30-80% latency reduction for long system prompts. OpenAI and Anthropic offer this natively.

### 2. Semantic Response Cache

**What:** If a new question is semantically similar to a previously answered question, return the cached answer.

```python
# Cache stores: (embedding, question, answer)
cached = [
    (embed("What are your hours?"), "What are your hours?", "We're open 9-5 M-F"),
]

new_query = "When are you open?"
new_embed = embed(new_query)
similarity = cosine(new_embed, cached[0].embedding)  # 0.95
if similarity > 0.92:  # threshold
    return cached[0].answer  # Cache hit!
```

### 3. Retrieval Cache

**What:** Same RAG query → same retrieved chunks. Skip the vector search.

**Key:** Cache key = hash(query_embedding + filters + top_k)

**Savings:** Vector DB queries cost 10-50ms each. At 1000 req/s, that's significant.

### 4. Reranker Cache

**What:** Same set of chunks + same query → same reranking order.

**Key:** Cache key = hash(query + sorted(chunk_ids))

**Savings:** Reranking models (like Cohere Rerank) add 100-300ms. Cache eliminates this.

### 5. Embedding Cache

**What:** Same text → same embedding vector. Never embed the same string twice.

```python
cache = {}
def cached_embed(text: str) -> list[float]:
    key = hash(text)
    if key not in cache:
        cache[key] = openai.embeddings.create(input=text)
    return cache[key]
```

**Savings:** Embedding API calls cost money and add latency. Documents rarely change.

### 6. Tool Result Cache

**What:** Same tool call with same parameters → same result (for a TTL period).

```python
# Weather API result valid for 30 minutes
@cache(ttl=1800)
def get_weather(city: str) -> dict:
    return weather_api.get(city)
```

**Savings:** External API calls are slow (100-2000ms) and often rate-limited.

### 7. Document Parse Cache

**What:** Same PDF/document → same extracted text. Parsing is expensive.

**Key:** Cache key = hash(file_content) or hash(file_path + last_modified)

**Savings:** PDF parsing can take 1-10 seconds per document.

### 8. Auth Decision Cache

**What:** Same user + same resource → same permission decision (short TTL!).

**DANGER:** This cache must have very short TTL (30-60 seconds) or be invalidated on permission changes. Stale auth = security vulnerability.

### 9. Eval Cache

**What:** Same model + same input → same evaluation score. Useful during development.

**Savings:** Running evals repeatedly during development wastes tokens.

---

## Cache Key Design

Good cache keys are the difference between useful caching and cache pollution:

```python
# BAD: Too specific (low hit rate)
key = hash(full_request_json_including_timestamp)

# BAD: Too broad (returns wrong answers)
key = hash(first_3_words_of_query)

# GOOD: Captures semantic intent
key = hash(normalized_query + model_version + relevant_filters)

# For semantic cache:
key = embedding_vector  # Use ANN search, not exact match
```

**Normalization tricks:**
- Lowercase
- Remove extra whitespace
- Strip punctuation
- Remove stop words (for retrieval cache)
- Canonicalize dates/numbers

---

## Cache Invalidation Strategies

The two hardest problems in computer science: cache invalidation, naming things, and off-by-one errors.

| Strategy | How It Works | Best For |
|----------|-------------|----------|
| **Time-based (TTL)** | Expire after N seconds | Tool results, weather, stock prices |
| **Event-based** | Invalidate when source changes | Document updates, permission changes |
| **Version-based** | New model version = new cache | Model upgrades, prompt changes |
| **Capacity-based (LRU)** | Evict least-recently-used when full | General purpose |
| **Manual** | Admin purges specific entries | Emergency corrections |

```python
# Version-based example
CACHE_VERSION = "v3"  # Bump when prompt changes
CACHE_PREFIX = f"response_cache:{CACHE_VERSION}:"

def get_cache_key(query: str) -> str:
    return f"{CACHE_PREFIX}{hash(query)}"
```

---

## Cache Safety Rules

1. **NEVER cache auth decisions for more than 60 seconds**
2. **NEVER serve cached responses after a model version change** (old answers may be wrong)
3. **ALWAYS cache with the model version in the key**
4. **NEVER cache error responses** (transient failures should be retried)
5. **Tag cached responses** so users know it's cached (for debugging)

---

## Semantic Caching Deep Dive

The key question: "How similar is similar enough?"

```
Threshold = 0.92: Very strict, fewer hits, always accurate
Threshold = 0.85: Moderate, more hits, occasional mismatches
Threshold = 0.78: Loose, many hits, risky for nuanced queries
```

**Recommended:** Start at 0.95 and lower gradually while monitoring quality.

**Failure modes:**
- "How do I delete my account?" vs "How do I create an account?" → Similarity: 0.89! Too close despite opposite intent.
- Solution: Also check for negation words, key entity differences.

---

## Cache Hit Rate Optimization

Target hit rates by cache type:

| Cache Type | Target Hit Rate | If Below Target |
|------------|----------------|-----------------|
| Embedding cache | >90% | Your corpus is too dynamic |
| Document parse cache | >95% | Documents changing too often |
| Retrieval cache | 30-60% | Normal — queries are diverse |
| Semantic response cache | 20-50% | Normal for varied user base |
| Tool result cache | 40-70% | Depends on tool diversity |

**Improving hit rates:**
- Normalize queries before cache lookup
- Increase TTL where safe
- Pre-warm cache with common queries
- Use tiered caching (L1 in-memory, L2 in Redis, L3 in disk)

---

## Caching Layers Architecture

```mermaid
flowchart LR
    subgraph "L1: In-Process (μs)"
        LRU[LRU Cache<br/>100 entries<br/>TTL: 60s]
    end
    
    subgraph "L2: Redis (ms)"
        Redis[Redis Cluster<br/>100K entries<br/>TTL: 1 hour]
    end
    
    subgraph "L3: Persistent (10ms)"
        DB[(PostgreSQL/S3<br/>Unlimited<br/>TTL: 24 hours)]
    end
    
    Request[Request] --> LRU
    LRU -->|Miss| Redis
    Redis -->|Miss| DB
    DB -->|Miss| Model[Model Inference]
    
    Model -->|Store| DB
    DB -->|Promote| Redis
    Redis -->|Promote| LRU
```

---

## Cost Savings Example

For a RAG chatbot handling 100K requests/day:

```
Without caching:
  100K × $0.03 (inference) = $3,000/day
  100K × $0.001 (embedding) = $100/day
  100K × $0.005 (retrieval) = $500/day
  Total: $3,600/day = $108,000/month

With caching (40% hit rate):
  60K × $0.03 + 40K × $0.0001 = $1,804/day
  Total: ~$54,000/month
  
  Savings: $54,000/month (50%!)
```

---

## Key Takeaways

1. **Layer your caches** — each stage of the AI pipeline can be cached
2. **Semantic cache is the biggest win** — similar questions are extremely common
3. **Cache keys are an art** — too specific = no hits, too broad = wrong answers
4. **Safety first** — never serve stale auth or outdated critical data
5. **Monitor hit rates** — if below target, investigate and optimize
6. **Version your caches** — model changes should invalidate response caches

---

## Staff-Level: Anti-Patterns

### 1. Exact-Match-Only Cache (Low Hit Rate for AI)
Users never ask the same question the same way twice. "What are your hours?" vs "When do you open?" vs "Are you open on weekends?" — all semantically similar but exact-match sees them as three cache misses. Without semantic caching, hit rates stay at 5-15% instead of 30-60%.

### 2. No Cache Invalidation Strategy
"We'll set TTL to 24 hours and forget about it." But what happens when:
- The underlying data changes (product prices updated)
- The model version changes (old cached answers may be wrong)
- A prompt injection was cached and is now being served to other users
- Regulatory information changes (compliance risk from stale answers)

### 3. Caching Non-Deterministic Outputs as If Deterministic
LLMs with temperature > 0 produce different outputs for identical inputs. Caching one response and serving it forever removes the variability users might expect. Worse: if the one cached response happens to be a bad generation, it's served repeatedly.

**Fix:** Cache with confidence scoring — only cache responses that pass quality checks. Or cache at temperature=0 and add variability at the response layer.

### 4. Caching Without TTL
"The answer is always valid." Nothing is always valid. Even "What is 2+2?" might get a different system prompt context next month. Every cache entry needs a TTL, even if it's long (7 days). Unbounded caches become ghost answers from dead system states.

---

## Staff-Level: Trade-offs

### Semantic Cache vs Exact Cache
| Dimension | Semantic Cache | Exact Cache |
|-----------|---------------|-------------|
| Hit rate | 30-60% | 5-15% |
| Complexity | High (needs embedding + ANN search) | Low (hash lookup) |
| Latency overhead | 10-50ms (embedding + search) | <1ms |
| Risk of wrong answer | Medium (similar ≠ same) | Zero |
| Storage | Large (embeddings + metadata) | Small (key-value) |
| Maintenance | Needs threshold tuning | Set and forget |

**Decision:** Use exact cache as L1 (free, zero risk), semantic cache as L2 (higher hit rate, some risk). Never use semantic cache alone.

### Cache Size vs Freshness
- **Large cache, long TTL:** Higher hit rate but stale answers. Good for static knowledge domains.
- **Small cache, short TTL:** Always fresh but low hit rate. Good for dynamic data (stock prices, news).
- **Sweet spot:** Tiered TTL by content type. FAQ answers: 7 days. Data-dependent answers: 1 hour. Real-time data: 5 minutes.

### Memory vs Latency
Every cache layer adds memory cost. A semantic cache with 1M entries at 1536 dimensions = ~6GB of embeddings alone. At scale, cache infrastructure can cost more than the inference it saves. Track: `cache_infrastructure_cost < (hit_rate × inference_cost_per_request × request_volume)`.

---

## Staff-Level: Real Numbers

### Achievable Cache Hit Rates with Semantic Caching
Based on production deployments across different domains:

| Domain | Exact-Match Hit Rate | Semantic Hit Rate | Threshold Used |
|--------|---------------------|-------------------|----------------|
| Customer support bot | 12% | 55% | 0.92 |
| Internal knowledge base | 8% | 42% | 0.90 |
| Code generation | 3% | 18% | 0.95 (strict) |
| E-commerce product Q&A | 15% | 61% | 0.91 |
| Healthcare triage | 5% | 28% | 0.96 (very strict) |

**Key insight:** Repetitive domains (support, FAQ) benefit enormously from semantic caching. Creative/generative tasks (code, writing) benefit less because queries are more unique.

**Cost impact at 50% semantic hit rate:**
```
100K requests/day × $0.03/request = $3,000/day without cache
50% hit rate → $1,500/day savings = $45,000/month
Semantic cache infrastructure cost: ~$2,000/month
Net savings: $43,000/month (28x ROI on cache infrastructure)
```
