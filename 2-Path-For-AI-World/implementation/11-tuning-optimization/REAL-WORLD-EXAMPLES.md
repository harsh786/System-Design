# Real-World Examples: Tuning & Optimization

## Case Study 1: Reducing AI Spend from $180K/month to $45K/month

**Company:** Series C B2B SaaS platform (contract analysis + customer support + code generation)

**Starting State (Month 0):**
| Feature | Model | Monthly Tokens | Monthly Cost |
|---------|-------|---------------|--------------|
| Contract Analysis | GPT-4-32K | 890M tokens | $78,000 |
| Customer Support Bot | GPT-4 | 1.2B tokens | $62,000 |
| Code Generation | GPT-4 | 480M tokens | $28,000 |
| Summarization | GPT-4 | 210M tokens | $12,000 |
| **Total** | | **2.78B tokens** | **$180,000** |

### Optimization 1: Model Routing (Saved $52K/month)

Analysis showed 68% of customer support queries were simple FAQ-type questions. They implemented a complexity classifier:

```python
# Production routing logic (simplified from their actual code)
class QueryComplexityRouter:
    def __init__(self):
        self.classifier = load_model("complexity_classifier_v3.pkl")  # Trained on 15K labeled queries
        self.thresholds = {
            "simple": 0.3,    # FAQ, status checks, simple lookups
            "medium": 0.7,    # Multi-step reasoning, comparisons
            "complex": 1.0    # Novel analysis, creative problem-solving
        }
    
    def route(self, query: str, context: dict) -> str:
        features = self.extract_features(query, context)
        complexity_score = self.classifier.predict_proba(features)[0][1]
        
        # Override rules (always use GPT-4 for these)
        if context.get("user_tier") == "enterprise":
            if complexity_score > 0.2:
                return "gpt-4"
        if context.get("involves_pii"):
            return "gpt-4"  # Better instruction following for guardrails
        
        if complexity_score < self.thresholds["simple"]:
            return "gpt-3.5-turbo"
        elif complexity_score < self.thresholds["medium"]:
            return "gpt-3.5-turbo-16k"
        else:
            return "gpt-4"
    
    def extract_features(self, query, context):
        return {
            "token_count": len(query.split()),
            "question_depth": self.count_sub_questions(query),
            "requires_reasoning": self.detect_reasoning_need(query),
            "domain_specificity": self.domain_score(query),
            "conversation_turns": context.get("turn_count", 0),
            "has_code": bool(re.search(r'```|def |class |function', query)),
            "comparison_request": bool(re.search(r'compare|versus|difference|better', query)),
        }
```

**Results:** 
- 62% of support queries routed to GPT-3.5-turbo
- Quality degradation: 2.1% (measured via user thumbs-up rate)
- Cost reduction: Support went from $62K to $18K/month

### Optimization 2: Prompt Compression for Contracts (Saved $41K/month)

Contract analysis was sending entire 30-page contracts as context. They switched to a two-stage approach:

```python
# Before: Sending full contract (avg 28,000 tokens per call)
# After: Extract relevant sections first, then analyze (avg 6,200 tokens per call)

class ContractAnalysisPipeline:
    def analyze(self, contract_text: str, question: str):
        # Stage 1: Cheap extraction with GPT-3.5 (cost: ~$0.002)
        relevant_sections = self.extract_relevant_sections(contract_text, question)
        
        # Stage 2: Deep analysis with GPT-4 on only relevant text (cost: ~$0.08 vs $0.84)
        analysis = self.deep_analyze(relevant_sections, question)
        return analysis
    
    def extract_relevant_sections(self, contract: str, question: str):
        # Chunk contract into sections by headers/paragraphs
        chunks = self.chunk_by_structure(contract)
        
        # Embed question and chunks, retrieve top-5 relevant
        question_embedding = self.embed(question)
        scored_chunks = [
            (chunk, cosine_similarity(question_embedding, self.embed(chunk)))
            for chunk in chunks
        ]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Take top chunks until we hit 5000 token budget
        selected = []
        token_count = 0
        for chunk, score in scored_chunks:
            chunk_tokens = self.count_tokens(chunk)
            if token_count + chunk_tokens > 5000:
                break
            if score > 0.72:  # Relevance threshold
                selected.append(chunk)
                token_count += chunk_tokens
        
        return "\n---\n".join(selected)
```

**Results:**
- Average tokens per contract query: 28,000 → 6,200
- Contract analysis cost: $78K → $37K/month
- Quality (measured by legal team spot-checks): 94.2% → 93.8% accuracy (acceptable)

### Optimization 3: Semantic Caching for Support (Saved $18K/month)

```python
# Cache similar questions — 40% of support queries are near-duplicates
class SemanticCache:
    def __init__(self, similarity_threshold=0.94):
        self.redis = Redis(host="cache-cluster.internal")
        self.index = FaissIndex(dimension=1536)
        self.threshold = similarity_threshold
    
    def get_or_compute(self, query: str, compute_fn):
        query_embedding = embed(query)
        
        # Search for similar cached queries
        distances, indices = self.index.search(query_embedding, k=3)
        
        if distances[0][0] < (1 - self.threshold):  # Cosine distance
            cached_key = self.index_to_key[indices[0][0]]
            cached_response = self.redis.get(cached_key)
            if cached_response:
                return json.loads(cached_response), {"cache_hit": True}
        
        # Cache miss — compute and store
        response = compute_fn(query)
        cache_key = f"response:{hash(query)}"
        self.redis.setex(cache_key, 3600, json.dumps(response))  # 1hr TTL
        self.index.add(query_embedding)
        self.index_to_key[len(self.index) - 1] = cache_key
        
        return response, {"cache_hit": False}
```

**Results:**
- Cache hit rate: 38-42% depending on time of day
- Support cost: $18K → $11K/month (after routing optimization already applied)

### Optimization 4: Fine-tuned GPT-3.5 for Code Generation (Saved $14K/month)

Replaced GPT-4 for 70% of code generation tasks with a fine-tuned GPT-3.5:

- Training data: 8,200 (prompt, GPT-4-response) pairs from production logs
- Fine-tuning cost: $1,200 one-time
- Ongoing inference: 70% cheaper per token

### Final State (Month 4):
| Feature | Model(s) | Monthly Cost |
|---------|-----------|--------------|
| Contract Analysis | GPT-3.5 extract + GPT-4 analyze | $37,000 |
| Customer Support | Routed: GPT-3.5/GPT-4 + cache | $11,000 |
| Code Generation | Fine-tuned GPT-3.5 + GPT-4 fallback | $14,000 |
| Summarization | GPT-3.5-turbo (swapped entirely) | $2,800 |
| **Total** | | **$45,200** |

**ROI:** $134K/month savings × 12 = $1.6M/year saved. Implementation cost: ~$85K (engineering time + fine-tuning).

---

## Case Study 2: Fine-tuning GPT-3.5 to Match GPT-4 for Medical Coding

**Company:** Healthcare tech startup automating ICD-10 medical coding from clinical notes.

**Problem:** GPT-4 achieved 91.3% accuracy on ICD-10 code assignment but cost $0.12/note. At 500K notes/month, that's $60K/month. GPT-3.5 baseline: 72.8% accuracy (unacceptable).

### Training Data Generation

```python
# Step 1: Generate high-quality training pairs using GPT-4
class TrainingDataGenerator:
    def generate_training_pair(self, clinical_note: str):
        prompt = f"""You are an expert medical coder. Given this clinical note, provide:
1. The primary ICD-10 code
2. Up to 3 secondary codes
3. Your reasoning chain (step by step)
4. Confidence level (high/medium/low)
5. Key clinical indicators that led to your coding decision

Clinical Note:
{clinical_note}

Respond in this exact JSON format:
{{
    "primary_code": "X00.0",
    "primary_description": "...",
    "secondary_codes": [...],
    "reasoning": "Step 1: ... Step 2: ...",
    "confidence": "high",
    "key_indicators": [...]
}}"""
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response

# Step 2: Quality filter — only keep high-confidence, verified examples
def filter_training_data(pairs):
    filtered = []
    for note, gpt4_response in pairs:
        parsed = json.loads(gpt4_response)
        
        # Only keep high-confidence responses
        if parsed["confidence"] != "high":
            continue
        
        # Verify against known code database
        if not valid_icd10_code(parsed["primary_code"]):
            continue
        
        # Check reasoning has at least 3 steps
        if parsed["reasoning"].count("Step") < 3:
            continue
        
        filtered.append((note, gpt4_response))
    
    return filtered  # Kept 6,800 of 10,000 generated pairs
```

### Training Configuration

```python
# Fine-tuning configuration
training_config = {
    "model": "gpt-3.5-turbo-0613",
    "training_file": "file-abc123",  # 6,800 examples
    "validation_file": "file-def456",  # 800 held-out examples
    "hyperparameters": {
        "n_epochs": 3,
        "batch_size": 4,
        "learning_rate_multiplier": 0.8
    },
    "suffix": "medical-coder-v2"
}

# Training data format (JSONL)
# Each line:
{
    "messages": [
        {"role": "system", "content": "You are an expert ICD-10 medical coder. Analyze clinical notes and assign accurate codes with reasoning."},
        {"role": "user", "content": "<clinical_note>"},
        {"role": "assistant", "content": "<gpt4_generated_response>"}
    ]
}
```

### Results After Fine-tuning

| Metric | GPT-4 | GPT-3.5 (base) | GPT-3.5 (fine-tuned) |
|--------|-------|-----------------|---------------------|
| Primary code accuracy | 91.3% | 72.8% | 89.7% |
| Secondary code recall | 84.1% | 61.2% | 82.3% |
| Cost per note | $0.12 | $0.008 | $0.009 |
| Latency (p50) | 4.2s | 0.8s | 0.9s |
| Monthly cost (500K notes) | $60,000 | $4,000 | $4,500 |

**Key insight:** Including the reasoning chain in training data was critical. Without it, fine-tuned accuracy was only 83.1%. The chain-of-thought in training examples improved accuracy by 6.6 percentage points.

---

## Case Study 3: Model Routing at Scale (Vercel-style Architecture)

Real routing logic used in production by a developer tools company:

```python
class ProductionModelRouter:
    """
    Routes requests across GPT-4, GPT-3.5-turbo, and Claude based on:
    - Query complexity analysis
    - Token budget constraints
    - Latency requirements
    - Model-specific strengths
    """
    
    ROUTING_RULES = {
        "code_generation": {
            "simple_completion": {"model": "gpt-3.5-turbo", "reason": "fast, cheap, good for boilerplate"},
            "complex_algorithm": {"model": "gpt-4", "reason": "better reasoning for novel algorithms"},
            "code_review": {"model": "claude-3-sonnet", "reason": "better at nuanced feedback"},
            "refactoring": {"model": "gpt-4", "reason": "understands architectural patterns"},
        },
        "content": {
            "short_summary": {"model": "gpt-3.5-turbo", "reason": "simple extraction task"},
            "long_form_writing": {"model": "claude-3-sonnet", "reason": "better coherence in long output"},
            "creative": {"model": "gpt-4", "reason": "better creative capabilities"},
            "translation": {"model": "gpt-3.5-turbo", "reason": "good enough, 10x cheaper"},
        },
        "reasoning": {
            "math": {"model": "gpt-4", "reason": "superior math reasoning"},
            "logic_puzzle": {"model": "gpt-4", "reason": "multi-step reasoning"},
            "classification": {"model": "gpt-3.5-turbo", "reason": "simple pattern matching"},
            "extraction": {"model": "gpt-3.5-turbo", "reason": "structured output, doesn't need reasoning"},
        }
    }
    
    def route(self, request: dict) -> RoutingDecision:
        # Step 1: Classify the task type
        task_category = self.classify_task(request["messages"])
        task_subcategory = self.classify_subtask(request["messages"], task_category)
        
        # Step 2: Check token constraints
        input_tokens = self.count_tokens(request["messages"])
        estimated_output = self.estimate_output_tokens(request)
        
        # Step 3: Apply latency constraints
        max_latency = request.get("max_latency_ms", 30000)
        
        # Step 4: Get base model recommendation
        base_model = self.ROUTING_RULES.get(task_category, {}).get(
            task_subcategory, {"model": "gpt-3.5-turbo"}
        )["model"]
        
        # Step 5: Override rules
        if input_tokens > 14000 and base_model == "gpt-3.5-turbo":
            base_model = "gpt-3.5-turbo-16k"
        
        if max_latency < 3000 and base_model == "gpt-4":
            base_model = "gpt-3.5-turbo"  # Latency override
            
        if input_tokens > 30000:
            base_model = "claude-3-sonnet"  # 200K context window
        
        # Step 6: A/B test allocation (5% traffic to challenger model)
        if self.in_experiment_group(request):
            base_model = self.get_experiment_model(request, base_model)
        
        return RoutingDecision(
            model=base_model,
            task_category=task_category,
            task_subcategory=task_subcategory,
            estimated_cost=self.estimate_cost(base_model, input_tokens, estimated_output),
            estimated_latency=self.estimate_latency(base_model, input_tokens, estimated_output)
        )
    
    def classify_task(self, messages: list) -> str:
        """Lightweight classifier — runs in <5ms using a small BERT model."""
        last_message = messages[-1]["content"]
        # Fast heuristics first
        if any(kw in last_message.lower() for kw in ["```", "code", "function", "implement", "debug"]):
            return "code_generation"
        if any(kw in last_message.lower() for kw in ["calculate", "solve", "prove", "logic"]):
            return "reasoning"
        return "content"
```

### Routing Performance Metrics (30-day window):

```
Total requests routed: 4.2M
Routing breakdown:
  GPT-3.5-turbo:     58.3% (2.45M requests) — avg cost $0.003/req
  GPT-4:             24.1% (1.01M requests) — avg cost $0.089/req
  Claude-3-sonnet:   12.8% (538K requests)  — avg cost $0.024/req
  GPT-3.5-16K:        4.8% (202K requests)  — avg cost $0.007/req

Quality metrics (human eval on 2000 sample):
  Routing accuracy: 91.4% (model matched ideal choice)
  User satisfaction: 4.2/5.0 (vs 4.3/5.0 with always-GPT-4)
  Cost savings vs always-GPT-4: 73%
```

---

## Case Study 4: Token Optimization — Before and After

**Scenario:** Enterprise knowledge base Q&A system. Average prompt was 4,200 tokens. After optimization: 1,800 tokens.

### Before (4,200 tokens average):

```
System prompt: 680 tokens (verbose instructions, 12 examples)
Retrieved context: 2,900 tokens (top-5 chunks, 580 tokens each)
User query + conversation history: 620 tokens (last 8 turns)
```

### Optimization 1: System Prompt Compression (680 → 280 tokens)

**Before:**
```
You are a helpful AI assistant that works for Acme Corporation. Your job is to
answer questions about our products, services, and policies. You should always
be polite and professional. If you don't know the answer, say so honestly.
Don't make up information. Always cite your sources when possible.

Here are some examples of good responses:
[12 few-shot examples, each ~40 tokens]

Important rules:
1. Never discuss competitor products
2. Always recommend contacting support for billing issues
3. Use bullet points for lists
4. Keep responses under 200 words unless the user asks for detail
...
```

**After:**
```
Role: Acme Corp product assistant. Cite sources. If unsure, say so.
Rules: No competitor mentions. Billing→support. Bullets for lists. <200 words default.
Format: [source_id] after claims.
```

**Why it works:** Fine-tuned models internalize behavior from training. Few-shot examples are unnecessary. Rules compressed to keywords that the model still follows.

### Optimization 2: Smarter Retrieval (2,900 → 1,200 tokens)

```python
# Before: Top-5 chunks, fixed 580 tokens each
chunks = retriever.get_top_k(query, k=5)

# After: Adaptive retrieval with deduplication and compression
class OptimizedRetriever:
    def retrieve(self, query: str, token_budget: int = 1200):
        # Get more candidates, then filter aggressively
        candidates = self.retriever.get_top_k(query, k=15)
        
        # Remove near-duplicate chunks (>0.85 similarity to each other)
        deduplicated = self.deduplicate(candidates, threshold=0.85)
        
        # Score by marginal information gain, not just relevance
        scored = self.score_marginal_gain(deduplicated, query)
        
        # Pack chunks into budget, preferring shorter high-relevance chunks
        selected = []
        remaining_budget = token_budget
        for chunk in scored:
            # Compress chunk: remove boilerplate, keep key sentences
            compressed = self.compress_chunk(chunk)
            chunk_tokens = count_tokens(compressed)
            if chunk_tokens <= remaining_budget:
                selected.append(compressed)
                remaining_budget -= chunk_tokens
        
        return selected
    
    def compress_chunk(self, chunk: str) -> str:
        """Remove low-information sentences from retrieved chunks."""
        sentences = sent_tokenize(chunk)
        # Keep sentences with entities, numbers, or direct answers
        important = [s for s in sentences if self.is_informative(s)]
        return " ".join(important)
```

### Optimization 3: Conversation History (620 → 320 tokens)

```python
# Before: Last 8 turns verbatim
# After: Summarize older turns, keep last 2 verbatim

class ConversationCompressor:
    def compress_history(self, turns: list, keep_recent: int = 2):
        if len(turns) <= keep_recent:
            return turns
        
        old_turns = turns[:-keep_recent]
        recent_turns = turns[-keep_recent:]
        
        # Summarize old turns into a single context line
        summary = self.summarize_turns(old_turns)  # ~80 tokens
        
        return [{"role": "system", "content": f"Previous context: {summary}"}] + recent_turns
```

### Final Results:

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| System prompt | 680 | 280 | 59% |
| Retrieved context | 2,900 | 1,200 | 59% |
| History + query | 620 | 320 | 48% |
| **Total** | **4,200** | **1,800** | **57%** |

**Quality impact:** Evaluated on 500 test queries with human judges.
- Answer quality score: 4.1/5.0 → 4.0/5.0 (statistically insignificant drop)
- Answer completeness: 88% → 85% (minor, acceptable)
- Cost reduction: 57% fewer input tokens = 57% cost reduction on input

---

## Case Study 5: Semantic Caching for High-Traffic Support Bot

**Company:** E-commerce platform, 2.3M support queries/month.

### Architecture:

```python
class ProductionSemanticCache:
    def __init__(self):
        self.embedding_model = "text-embedding-3-small"  # $0.02/1M tokens
        self.vector_store = Qdrant(collection="cache_embeddings")
        self.response_store = Redis(cluster_mode=True)
        self.similarity_threshold = 0.95  # High threshold = fewer false positives
        self.ttl_config = {
            "product_info": 3600,       # 1 hour (prices change)
            "policy": 86400,            # 24 hours (policies stable)
            "order_status": 0,          # Never cache (dynamic)
            "general_faq": 604800,      # 7 days
        }
    
    async def get_response(self, query: str, context: dict) -> CacheResult:
        # Never cache personalized queries
        if self.is_personalized(query, context):
            return CacheResult(hit=False, reason="personalized_query")
        
        # Generate embedding
        query_embedding = await self.embed(query)
        
        # Search vector store
        results = self.vector_store.search(
            query_embedding, 
            limit=1,
            score_threshold=self.similarity_threshold
        )
        
        if results:
            cached = self.response_store.get(results[0].payload["response_key"])
            if cached:
                # Validate cache is still fresh
                category = results[0].payload["category"]
                created_at = results[0].payload["created_at"]
                if time.time() - created_at < self.ttl_config.get(category, 3600):
                    return CacheResult(
                        hit=True, 
                        response=json.loads(cached),
                        similarity=results[0].score
                    )
        
        return CacheResult(hit=False, reason="no_match")
    
    def is_personalized(self, query: str, context: dict) -> bool:
        """Don't cache queries that reference specific user data."""
        personal_signals = [
            context.get("references_order_id"),
            context.get("mentions_account"),
            "my order" in query.lower(),
            "my account" in query.lower(),
            bool(re.search(r'#\d{6,}', query)),  # Order numbers
        ]
        return any(personal_signals)
```

### Performance Metrics (30-day):

```
Total queries: 2,310,000
Cache hits: 924,000 (40.0%)
Cache misses: 1,386,000

Breakdown by category:
  FAQ/General:     78% hit rate (890K queries in category)
  Product info:    42% hit rate (620K queries)
  Policy questions: 61% hit rate (340K queries)
  Order-related:   0% hit rate (460K queries, never cached)

Cost savings:
  Average LLM cost per query: $0.038
  Queries served from cache: 924,000
  Monthly savings: 924,000 × $0.038 = $35,112/month
  Cache infrastructure cost: $1,800/month (Qdrant + Redis)
  Net savings: $33,312/month
```

### Invalidation Strategy:

```python
# When product catalog updates, invalidate related cache entries
@event_handler("catalog.product.updated")
async def invalidate_product_cache(event):
    product_id = event["product_id"]
    # Find all cache entries mentioning this product
    entries = await vector_store.scroll(
        filter={"product_ids": {"$contains": product_id}},
        limit=1000
    )
    for entry in entries:
        await vector_store.delete(entry.id)
        await redis.delete(entry.payload["response_key"])
```

---

## Case Study 6: Distillation — Training a 7B Model from GPT-4 Outputs

**Task:** Customer intent classification + response generation for a telecom company.
**Goal:** Replace GPT-4 ($48K/month) with a self-hosted 7B model.

### Step 1: Data Generation from GPT-4

```python
# Generate 50,000 training examples over 2 weeks
class DistillationDataGenerator:
    def __init__(self):
        self.categories = [
            "billing_inquiry", "technical_support", "plan_change",
            "cancellation", "new_service", "complaint", "general"
        ]
    
    def generate_batch(self, real_queries: list):
        """Use real production queries + GPT-4 to generate training pairs."""
        training_pairs = []
        
        for query in real_queries:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": TELECOM_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": query}
                ],
                temperature=0.3,
                # Request structured output for easier training
                functions=[{
                    "name": "respond_to_customer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {"type": "string", "enum": self.categories},
                            "confidence": {"type": "number"},
                            "response": {"type": "string"},
                            "requires_escalation": {"type": "boolean"},
                            "suggested_actions": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }]
            )
            
            training_pairs.append({
                "input": query,
                "output": response.choices[0].message.function_call.arguments
            })
        
        return training_pairs
```

### Step 2: Training the 7B Model

```python
# Using Mistral-7B as base, trained with QLoRA
training_config = {
    "base_model": "mistralai/Mistral-7B-Instruct-v0.2",
    "method": "qlora",
    "lora_config": {
        "r": 64,
        "lora_alpha": 128,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "lora_dropout": 0.05,
    },
    "training_args": {
        "num_train_epochs": 3,
        "per_device_train_batch_size": 4,
        "gradient_accumulation_steps": 8,
        "learning_rate": 2e-4,
        "warmup_ratio": 0.05,
        "bf16": True,
    },
    "dataset_size": 50000,
    "validation_size": 5000,
    "hardware": "4x A100 80GB",
    "training_time": "6.5 hours",
    "training_cost": "$180 (Lambda Labs)"
}
```

### Step 3: Evaluation Results

| Metric | GPT-4 | Distilled 7B | GPT-3.5 (baseline) |
|--------|-------|--------------|---------------------|
| Intent accuracy | 96.2% | 94.8% | 88.1% |
| Response quality (human eval) | 4.4/5 | 4.1/5 | 3.6/5 |
| Escalation precision | 93.7% | 91.2% | 82.4% |
| Latency (p50) | 3.8s | 0.4s | 0.9s |
| Cost per query | $0.042 | $0.003 | $0.004 |
| Monthly cost (1.1M queries) | $48,000 | $3,300 | $4,400 |

**Infrastructure for self-hosted 7B:**
- 2x A10G GPUs (inference): $2,400/month
- vLLM serving infrastructure: $900/month
- Total: $3,300/month vs $48,000/month

---

## Case Study 7: Prompt Caching Economics (Break-Even Analysis)

### OpenAI Prompt Caching (automatic for >1024 token prefixes)

```
Pricing (GPT-4-turbo):
  Standard input:  $10.00 / 1M tokens
  Cached input:    $5.00 / 1M tokens (50% discount)
  
Break-even calculation:
  Cache is FREE (automatic). It always saves money when prefix matches.
  
  Scenario: System prompt = 2000 tokens, called 10,000 times/day
  Without cache: 2000 × 10,000 × $10/1M = $200/day
  With cache:    2000 × 10,000 × $5/1M  = $100/day
  Savings: $100/day = $3,000/month
```

### Anthropic Prompt Caching (explicit, with write cost)

```
Pricing (Claude 3.5 Sonnet):
  Standard input:       $3.00 / 1M tokens
  Cache write:          $3.75 / 1M tokens (25% premium to write)
  Cache read:           $0.30 / 1M tokens (90% discount to read)
  Cache TTL:            5 minutes
  
Break-even formula:
  write_cost = tokens × $3.75/1M
  read_savings_per_hit = tokens × ($3.00 - $0.30)/1M = tokens × $2.70/1M
  
  Break-even hits = write_cost / read_savings_per_hit
                  = $3.75 / $2.70
                  = 1.39 hits per write
  
  → You need at least 2 cache reads per write to profit.
  
Real scenario: RAG system with 4000-token system prompt + examples
  Cache write cost: 4000 × $3.75/1M = $0.015
  Per-read savings: 4000 × $2.70/1M = $0.0108
  
  At 100 requests/minute (same prompt prefix):
    Writes per 5-min window: 1
    Reads per 5-min window: 499
    Cost without cache: 500 × 4000 × $3.00/1M = $6.00
    Cost with cache: $0.015 + (499 × 4000 × $0.30/1M) = $0.015 + $0.599 = $0.614
    Savings per 5-min window: $5.39 (89.8% reduction)
    Monthly savings: $5.39 × 12 × 24 × 30 = $46,500/month

When caching DOESN'T pay off:
  - Low traffic (<2 requests per 5-min TTL window)
  - Highly variable prompts (each user gets unique prefix)
  - Short system prompts (<1024 tokens) — not enough to cache
```

---

## Case Study 8: LoRA Fine-tuning for Financial Report Analysis

**Company:** Top-20 US bank. Requirement: Analyze 10-K SEC filings for risk factors.

### Compliance Requirements

```yaml
# Compliance constraints that shaped the architecture
data_handling:
  - No customer data leaves bank's VPC
  - Model weights must be stored in bank's cloud tenancy
  - All training data must be reviewed by compliance team
  - Model outputs must be auditable (full input/output logging)
  - No third-party API calls for inference

model_selection:
  base_model: "meta-llama/Llama-2-13b-chat-hf"
  reason: "Open weights, can be deployed on-prem, no data leaves network"
  
infrastructure:
  training: "8x A100 80GB (on-prem DGX cluster)"
  inference: "4x A100 (dedicated partition)"
  storage: "Bank's S3-compatible object store (encrypted at rest)"
```

### Training Data Preparation

```python
# 3,200 annotated examples from bank's analyst team
training_data_composition = {
    "risk_factor_extraction": 1200,     # Identify key risks from 10-K
    "financial_metric_analysis": 800,   # Extract and interpret key metrics  
    "comparative_analysis": 600,        # Compare across filings/years
    "regulatory_compliance_check": 400, # Flag potential compliance issues
    "summary_generation": 200,          # Executive summary of filing
}

# LoRA configuration optimized for financial domain
lora_config = {
    "r": 32,                    # Rank — lower than general-purpose to avoid overfitting
    "lora_alpha": 64,           # Alpha = 2*r is common starting point
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
        "gate_proj", "up_proj", "down_proj"        # MLP
    ],
    "lora_dropout": 0.1,       # Higher dropout for small dataset
    "bias": "none",
    "task_type": "CAUSAL_LM",
}

# Training arguments
training_args = {
    "num_train_epochs": 5,
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 16,
    "learning_rate": 1e-4,
    "lr_scheduler_type": "cosine",
    "warmup_steps": 100,
    "max_grad_norm": 0.3,
    "bf16": True,
    "logging_steps": 10,
    "evaluation_strategy": "steps",
    "eval_steps": 50,
    "save_strategy": "steps",
    "save_steps": 100,
}
```

### Results

| Metric | Base Llama-2-13B | LoRA Fine-tuned | GPT-4 (benchmark) |
|--------|-----------------|-----------------|-------------------|
| Risk factor F1 | 0.61 | 0.87 | 0.91 |
| Metric extraction accuracy | 68% | 89% | 93% |
| Regulatory flag precision | 0.52 | 0.84 | 0.88 |
| Hallucination rate | 12.3% | 3.1% | 2.4% |
| Processing time per filing | 45s | 48s | 180s (API) |
| Cost per filing | $0.08 | $0.09 | N/A (can't use) |

**Key outcome:** The LoRA adapter is only 52MB vs 26GB for full model. Multiple LoRA adapters are swapped at inference time for different analysis types.

---

## Case Study 9: Cost Tracking Dashboard

### Metrics to Track

```python
class AIcostTracker:
    """Production cost tracking system."""
    
    METRICS = {
        # Real-time metrics (updated per request)
        "cost_per_request": {"type": "histogram", "buckets": [0.001, 0.01, 0.05, 0.1, 0.5, 1.0]},
        "tokens_per_request": {"type": "histogram", "labels": ["model", "direction"]},
        "cost_per_user": {"type": "counter", "labels": ["user_id", "tier"]},
        "cost_per_feature": {"type": "counter", "labels": ["feature", "model"]},
        
        # Aggregated metrics (computed hourly)
        "hourly_spend": {"type": "gauge", "labels": ["model", "feature"]},
        "daily_budget_utilization": {"type": "gauge"},
        "cost_efficiency_score": {"type": "gauge"},  # quality / cost ratio
        
        # Anomaly detection
        "spend_rate_zscore": {"type": "gauge"},  # Z-score vs 7-day rolling average
    }
    
    ALERT_THRESHOLDS = {
        "hourly_spend_spike": {
            "condition": "hourly_spend > 2.5 * rolling_7day_avg_hourly",
            "severity": "warning",
            "action": "page_oncall + auto_enable_aggressive_caching"
        },
        "daily_budget_breach": {
            "condition": "daily_spend > daily_budget * 0.9",
            "severity": "critical",
            "action": "page_oncall + downgrade_all_to_cheapest_model"
        },
        "cost_per_request_drift": {
            "condition": "p95_cost_per_request > 1.5 * baseline_p95",
            "severity": "warning",
            "action": "notify_slack + investigate_prompt_length_growth"
        },
        "token_waste_detected": {
            "condition": "avg_output_tokens / avg_useful_output_tokens > 2.0",
            "severity": "info",
            "action": "notify_team + flag_for_prompt_optimization"
        }
    }
```

### Real Anomaly Detection Example

```
ALERT FIRED: 2024-03-14 14:23 UTC
Type: hourly_spend_spike
Details:
  Current hourly spend: $847
  7-day avg hourly: $312
  Ratio: 2.72x (threshold: 2.5x)
  
Root cause investigation:
  1. Spike isolated to "contract_analysis" feature
  2. Average tokens/request jumped from 6,200 to 31,000
  3. Cause: New customer onboarded 4,200 contracts simultaneously
     via bulk upload API (no rate limiting on AI processing)
  
Resolution:
  - Added queue-based processing with max 50 concurrent AI calls
  - Implemented per-customer hourly budget caps
  - Added bulk upload detection that routes to batch API (50% cheaper)
  
Post-mortem cost: $2,100 extra spend before alert + response (12 minutes)
```

---

## Case Study 10: The Optimization Order — Why Retrieval First

**Company:** Legal research AI. Initial complaint: "GPT-4 is too expensive for our use case."

### Wrong approach (optimized model first):

```
Step 1: Switched from GPT-4 to GPT-3.5         → Quality dropped 31%
Step 2: Fine-tuned GPT-3.5 on legal data        → Quality recovered 18% (still -13%)
Step 3: Added more few-shot examples            → +5% quality, +800 tokens/request
Net result: 60% cost reduction, 8% quality loss. Unsatisfactory.
Total effort: 6 weeks engineering time.
```

### Right approach (optimized retrieval first):

```
Step 1: Analyzed what GPT-4 was actually receiving
  Finding: 40% of retrieved chunks were irrelevant or redundant
  Finding: Average 12,000 tokens of context, only 4,000 were useful
  
Step 2: Improved retrieval quality
  - Added reranker (Cohere rerank-v3) after initial retrieval
  - Implemented parent-document retrieval (retrieve chunk → expand to section)
  - Added metadata filtering (jurisdiction, date, document type)
  
  Result: 
    - Context tokens: 12,000 → 5,000 (58% reduction)
    - Answer quality: IMPROVED by 8% (less noise = better answers)
    - Cost: Reduced 55% (just from fewer input tokens)
    
Step 3: With better retrieval, GPT-3.5 now performs well
  - GPT-3.5 + good retrieval = equivalent to GPT-4 + bad retrieval
  - Switched to GPT-3.5 for 70% of queries
  - Additional 40% cost reduction
  
Step 4: Added semantic caching on top
  - 25% cache hit rate on legal research queries
  - Additional 20% cost reduction

Net result: 82% total cost reduction, 8% quality IMPROVEMENT.
Total effort: 4 weeks engineering time.
```

### The optimization priority stack:

```
Priority 1: Fix retrieval quality (biggest ROI, improves quality AND cost)
Priority 2: Reduce token waste (prompt compression, history summarization)
Priority 3: Add caching layers (semantic cache for repeated patterns)
Priority 4: Model routing (use cheaper models where quality allows)
Priority 5: Fine-tuning (only after you've optimized what goes INTO the model)
Priority 6: Distillation/self-hosting (only at extreme scale)

Rule of thumb: Every $1 spent on retrieval optimization saves $5 on model costs.
```

---

## Key Takeaways

1. **Measure before optimizing.** Most teams guess wrong about where cost comes from.
2. **Routing is the highest-leverage single optimization** — 60-70% of queries don't need the best model.
3. **Retrieval quality multiplies everything downstream** — garbage in, expensive garbage out.
4. **Fine-tuning is a scalpel, not a hammer** — use it for specific, well-defined domain tasks with clear training signal.
5. **Caching ROI depends on query distribution** — high-traffic, repetitive workloads benefit enormously.
6. **Set budget alerts from day one** — one bad deployment can cost $10K before anyone notices.
