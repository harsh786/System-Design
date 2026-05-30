# Tuning and Optimization - Deep Concepts

## 1. The Tuning Order Principle

The single most important concept in AI system optimization is **tuning order**. Most teams waste months fine-tuning models when the real problem is bad data or missing retrieval. The correct order:

```
1. PRODUCT   → Fix the UX, scope, and task definition first
2. DATA      → Clean, deduplicate, enrich your knowledge base
3. RETRIEVAL → Better chunking, indexing, hybrid search
4. PROMPT    → Better instructions, examples, formatting
5. AGENT     → Better tool use, planning, orchestration
6. MODEL     → Fine-tuning, distillation, model selection
7. PLATFORM  → Infrastructure, caching, batching, routing
```

### Why This Order Matters

Each level has dramatically different cost-to-impact ratios:

| Level | Cost to Change | Impact Potential | Time to Deploy | Risk |
|-------|---------------|-----------------|----------------|------|
| Product | Low | Massive | Hours | Low |
| Data | Medium | Very High | Days | Low |
| Retrieval | Medium | High | Days | Low |
| Prompt | Low | High | Minutes | Low |
| Agent | Medium | Medium-High | Days | Medium |
| Model | High | Medium | Weeks | High |
| Platform | High | Medium | Weeks | Medium |

### Product-Level Fixes (Do First!)

Before touching any ML:
- **Narrow the scope**: "Answer any question" → "Answer questions about our billing docs"
- **Add constraints**: Let users select category before asking
- **Show confidence**: Display "I'm not sure" instead of hallucinating
- **Add human fallback**: Route uncertain cases to humans
- **Improve feedback loops**: Add thumbs up/down, copy button tracking

### Data-Level Fixes (Do Second!)

- Remove duplicate documents (causes retrieval confusion)
- Fix formatting (tables rendered as text, broken markdown)
- Add metadata (dates, authors, categories, freshness scores)
- Fill knowledge gaps (find what users ask that has no source doc)
- Version documents (remove outdated contradictory info)

---

## 2. RAG vs Fine-Tuning Decision Framework

This is the most common architectural decision in AI systems.

### When to Use RAG

| Signal | Why RAG Works |
|--------|--------------|
| Knowledge changes frequently | No retraining needed |
| Need citations/sources | RAG naturally provides source docs |
| Large knowledge base (>100 pages) | Can't fit in fine-tuning examples |
| Multi-tenant with different data | Same model, different retrieval |
| Need to control access (ACLs) | Filter at retrieval time |
| Factual accuracy is critical | Grounded in source documents |
| Cold start (no training data yet) | Works immediately with docs |

### When to Fine-Tune

| Signal | Why Fine-Tuning Works |
|--------|---------------------|
| Consistent style/tone needed | Bakes behavior into weights |
| Complex reasoning patterns | Teaches multi-step logic |
| Domain-specific language | Learns terminology and conventions |
| Structured output format | Learns to always output JSON/XML |
| Latency-critical (no retrieval) | Single model call, no RAG pipeline |
| Cost-critical (reduce prompt size) | Behavior in weights, not instructions |
| Classification/routing tasks | High accuracy with small model |

### The Hybrid Approach (Most Production Systems)

```
Fine-tuned small model (routing/classification)
    ↓
RAG pipeline (knowledge retrieval)
    ↓
Fine-tuned generation model (style + format)
    ↓
Output validation
```

### Decision Matrix

```
                    Knowledge is Static    Knowledge Changes Often
                    ──────────────────    ───────────────────────
Need Citations  →   RAG                   RAG
No Citations    →   Fine-tune             RAG + Fine-tune style
Simple Tasks    →   Few-shot prompting    RAG
Complex Tasks   →   Fine-tune             RAG + Fine-tune reasoning
```

---

## 3. Model and Agent Training Options

### 3.1 Prompt/Program Optimization

**What**: Automatically optimize prompts using DSPy-style optimizers or manual A/B testing.

**Techniques**:
- **DSPy optimizers**: BootstrapFewShot, MIPRO, SignatureOptimizer
- **Prompt mutation**: Generate variations, evaluate on test set, keep winners
- **Few-shot selection**: Dynamically select most relevant examples per query
- **Chain-of-thought optimization**: Find minimal reasoning that maintains accuracy

**When to use**: Always start here. Zero cost, immediate results.

```
Before: "You are a helpful assistant. Please answer the user's question accurately."
After:  "Answer the billing question using ONLY the provided context. Format: 
         1. Direct answer (1 sentence)
         2. Relevant details (bullet points)
         3. Source reference"
```

### 3.2 Retrieval Tuning

**What**: Optimize the retrieval pipeline independent of the model.

**Techniques**:
- **Chunk size optimization**: Test 256/512/1024/2048 tokens
- **Overlap tuning**: 10-25% overlap between chunks
- **Embedding model selection**: Test multiple models on your data
- **Hybrid search weights**: Balance BM25 vs vector (e.g., 0.3/0.7)
- **Reranker selection**: Cross-encoder reranking top-k results
- **Query expansion**: Generate sub-queries, HyDE
- **Metadata filtering**: Pre-filter by date, category, tenant

**Evaluation**: Measure retrieval quality SEPARATELY from generation quality:
- Recall@k: Are relevant docs in top-k?
- MRR: Is the best doc ranked first?
- Context relevance: Are retrieved chunks actually useful?

### 3.3 Supervised Fine-Tuning (SFT)

**What**: Train model on (input, desired_output) pairs.

**When**: You have 100+ high-quality examples of ideal behavior.

**Process**:
```
1. Collect examples from production (human-verified good responses)
2. Format as instruction-following pairs
3. Split: 80% train, 10% validation, 10% test
4. Fine-tune with low learning rate (1e-5 to 5e-5)
5. Evaluate on held-out test set
6. Compare to base model on same test set
7. Deploy with A/B test against base model
```

**Pitfalls**:
- Catastrophic forgetting (loses general capabilities)
- Overfitting on small datasets
- Distribution shift (training data ≠ production queries)
- Evaluation is hard (need diverse test set)

### 3.4 LoRA/Adapters

**What**: Train small adapter layers instead of full model weights. Much cheaper.

**Benefits**:
- 10-100x less compute than full fine-tuning
- Can swap adapters per tenant/task
- Base model stays frozen (no catastrophic forgetting)
- Can merge multiple adapters

**Architecture**:
```
Base Model (frozen) → LoRA Adapter A (billing style)
                    → LoRA Adapter B (technical support)
                    → LoRA Adapter C (sales tone)
```

**Hyperparameters**:
- Rank (r): 8-64 typical. Higher = more capacity, more compute
- Alpha: Usually 2x rank
- Target modules: Usually attention layers (q_proj, v_proj)
- Learning rate: 1e-4 to 3e-4 (higher than full fine-tuning)

### 3.5 DPO/Preference Tuning

**What**: Train model to prefer good outputs over bad outputs using pairs.

**Data format**:
```json
{
  "prompt": "Explain our refund policy",
  "chosen": "Our refund policy allows returns within 30 days...",
  "rejected": "I think maybe you can return stuff, not sure about the details..."
}
```

**When to use**:
- You have human preference data (thumbs up/down from production)
- SFT alone produces technically correct but stylistically wrong outputs
- You want to reduce specific failure modes (hallucination, verbosity)

**Variants**:
- **DPO**: Direct Preference Optimization (no reward model needed)
- **RLHF**: Full RL pipeline with reward model (more complex, higher quality)
- **KTO**: Kahneman-Tversky Optimization (only needs good/bad labels, no pairs)
- **ORPO**: Odds Ratio Preference Optimization (combines SFT + preference)

### 3.6 Distillation

**What**: Train a small "student" model to mimic a large "teacher" model.

**Strategy**:
```
1. Run teacher (GPT-4/Claude) on your production queries
2. Collect high-quality (query, response) pairs
3. Fine-tune student (GPT-4o-mini/Llama-8B) on these pairs
4. Student learns teacher's behavior at 10-50x lower cost
5. Deploy student for routine queries, teacher for hard ones
```

**Distillation Pipeline**:
```
Production Queries (1000s)
    ↓
Teacher Model (expensive, high quality)
    ↓
Filter: Keep only high-scoring outputs (eval > 0.8)
    ↓
Training Data for Student
    ↓
Fine-tune Student Model
    ↓
Evaluate: Student vs Teacher on held-out set
    ↓
Deploy: Student handles 80% of traffic
```

**Key Insight**: You don't need the student to match the teacher on everything. Focus distillation on your specific use case. A distilled model that handles 80% of queries at 95% teacher quality saves enormous cost.

### 3.7 Synthetic Data Generation

**What**: Use LLMs to generate training data for fine-tuning.

**Techniques**:
- **Query generation**: Given a document, generate questions it answers
- **Response generation**: Given a query, generate ideal responses
- **Adversarial generation**: Generate hard/edge cases
- **Style transfer**: Rewrite responses in desired tone
- **Augmentation**: Rephrase existing examples in different ways

**Quality Control**:
```
Generate 10x more data than needed
    ↓
Filter with quality model (score each example)
    ↓
Deduplicate (semantic similarity)
    ↓
Human review sample (10-20%)
    ↓
Final training set
```

### 3.8 Human Feedback Mining

**What**: Extract training signal from production interactions.

**Sources**:
- Thumbs up/down on responses
- User edits to AI-generated content
- Retry patterns (user asks again = bad response)
- Copy/share actions (= good response)
- Conversation length (long = possibly struggling)
- Task completion (did user achieve goal?)
- Escalation to human (= AI failed)

**Pipeline**:
```
Production Logs
    ↓
Extract (query, response, signal) triples
    ↓
Signal = positive: Add to "chosen" set
Signal = negative: Add to "rejected" set
    ↓
Create preference pairs for DPO
    ↓
Fine-tune periodically (weekly/monthly)
    ↓
A/B test new model vs current
```

---

## 4. Token Reduction Techniques

Every token costs money and adds latency. Aggressive token reduction is often the highest-ROI optimization.

### 4.1 Compact Prompts

```
Before (847 tokens):
"You are a helpful, knowledgeable, and friendly customer support assistant 
for Acme Corp. You should always be polite and professional. When answering 
questions, make sure to provide accurate information based on our knowledge 
base. If you don't know the answer, please let the customer know that you 
will escalate their question to a human agent..."

After (156 tokens):
"Acme Corp support agent. Answer from provided context only. 
Unknown → say 'Let me connect you with a specialist.'
Format: brief answer, then details if needed."
```

### 4.2 Context Budget Management

Allocate your context window like a budget:

```
Total Budget: 8192 tokens (example)
─────────────────────────────────
System prompt:     500 tokens (6%)
Retrieved context: 3000 tokens (37%)
Conversation history: 2000 tokens (24%)
Current query:     200 tokens (2%)
Tool schemas:      500 tokens (6%)
Output budget:     2000 tokens (24%)
─────────────────────────────────
```

Dynamic allocation: Simple queries get less context, complex queries get more.

### 4.3 Retrieve Fewer, Better Chunks

```
Naive: Retrieve top-20 chunks (8000 tokens of context)
Better: Retrieve top-50, rerank to top-3 (1200 tokens of context)
```

The reranker costs ~$0.001 per query but saves ~$0.05 in token costs.

### 4.4 Contextual Compression

After retrieval, compress chunks to only the relevant sentences:

```
Original chunk (500 tokens):
"Acme Corp was founded in 1985 by John Smith. The company started as a 
hardware manufacturer but pivoted to software in 2001. Our refund policy 
allows returns within 30 days of purchase with original receipt. The policy 
was updated in January 2024. We have offices in..."

Compressed for query "What is your refund policy?" (50 tokens):
"Refund policy: Returns within 30 days with original receipt. Updated Jan 2024."
```

### 4.5 History Summarization

```
Instead of keeping full conversation (2000 tokens):
User: "Hi, I need help with my account"
Assistant: "I'd be happy to help! What's your account issue?"
User: "I can't log in, I've tried resetting my password 3 times"
Assistant: "I'm sorry to hear that. Let me look into this..."
[... 15 more turns ...]

Summarize to (100 tokens):
"Context: User cannot log in despite 3 password resets. Agent verified 
email is correct. Account is not locked. Issue escalated to engineering. 
Waiting for response on ticket #4521."
```

### 4.6 Prompt Caching

Most providers now support prefix caching:
- OpenAI: Automatic for repeated prefixes (50% discount on cached tokens)
- Anthropic: Explicit cache_control markers (90% discount on cached tokens)
- Design system prompts to be stable prefixes that cache well

### 4.7 Semantic Caching

```
Query: "How do I reset my password?"
Cache hit: Similar query "password reset process" was answered 5 min ago
→ Return cached answer (cost: $0.0001 for embedding vs $0.03 for generation)
```

Similarity threshold: 0.92-0.95 (tune per use case)

### 4.8 Model Routing

```
Simple query ("What are your hours?") → GPT-4o-mini ($0.15/1M tokens)
Complex query ("Compare plans and recommend") → GPT-4o ($2.50/1M tokens)
Safety-critical ("Process my payment") → GPT-4o + guardrails

Savings: 60-80% cost reduction with <5% quality drop
```

### 4.9 Output Limits

```
# Don't let the model ramble
response = client.chat.completions.create(
    max_tokens=500,  # Cap output
    messages=[{
        "role": "system",
        "content": "Answer in 2-3 sentences maximum."
    }]
)
```

### 4.10 Batch Embeddings

```
# Bad: Embed one at a time (high overhead per request)
for doc in documents:
    embedding = embed(doc)  # 1000 API calls

# Good: Batch embed (amortize overhead)
embeddings = embed_batch(documents, batch_size=100)  # 10 API calls
```

### 4.11 Reduce Tool Schemas

```
# Before: Full OpenAPI spec in every request (2000 tokens)
tools = [{"name": "search", "description": "Search the knowledge base for...", 
          "parameters": {"type": "object", "properties": {"query": {"type": "string", 
          "description": "The search query to find relevant documents in our..."}}}}]

# After: Minimal schema (200 tokens)  
tools = [{"name": "search", "parameters": {"query": "string"}}]
```

### 4.12 Use Smaller Models for Subtasks

```
# Route subtasks to appropriate models
classify_intent → GPT-4o-mini (fast, cheap)
extract_entities → GPT-4o-mini
generate_response → GPT-4o (quality matters here)
summarize_for_log → GPT-4o-mini
```

---

## 5. Cost Tracking

### Cost Components

```
Total Cost Per Request:
├── Input tokens (prompt + context + history)
├── Output tokens (generated response)
├── Embedding cost (query embedding + any re-embedding)
├── Reranker cost (cross-encoder scoring)
├── Tool execution cost (API calls, compute)
├── Infrastructure cost (GPU time, vector DB queries)
└── Human review cost (if escalated)
```

### Key Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Cost per request | Total cost / total requests | Track trend |
| Cost per successful task | Total cost / tasks completed | Minimize |
| Cost per tenant | Sum of tenant's request costs | Budget cap |
| Token burn rate | Tokens used / hour | Capacity planning |
| Cache hit rate | Cached responses / total requests | >30% |
| Model cost split | Cost by model tier | Optimize routing |
| Retrieval cost | Embedding + vector DB + reranker | Track trend |
| Eval cost | Evaluation pipeline cost | <5% of prod cost |
| Human review cost | Escalations × human time cost | Minimize |

### Cost Per Successful Task

This is the **most important metric**. Raw per-request cost is misleading:

```
Scenario A: $0.05/request, 40% task success rate → $0.125/successful task
Scenario B: $0.10/request, 90% task success rate → $0.111/successful task

Scenario B is CHEAPER despite 2x per-request cost!
```

### Budget Enforcement

```
Levels:
1. WARN: Tenant at 80% of monthly budget
2. THROTTLE: Tenant at 95%, degrade to cheaper model
3. BLOCK: Tenant at 100%, queue requests for next period
4. ALERT: Sudden spike (3x normal rate), possible abuse
```

---

## 6. Quality-Cost Frontier

The goal is to find the optimal point on the quality-cost curve:

```
Quality
  │      ╭──── GPT-4 + full RAG + reranker
  │     ╱
  │    ╱ ← Diminishing returns above here
  │   ╱
  │  ╱ ← Sweet spot (GPT-4o-mini + RAG + cache)
  │ ╱
  │╱ ← Cheap but inadequate (GPT-4o-mini, no RAG)
  └────────────────────── Cost →
```

### Finding Your Sweet Spot

1. **Establish baseline**: Measure current quality and cost
2. **Map the frontier**: Test configurations at different cost points
3. **Find the knee**: Where does quality plateau despite more spend?
4. **Optimize at your budget**: Get max quality at your cost constraint

### Configuration Points to Test

```
Config 1 ($0.01/req): Small model, no RAG, cached responses
Config 2 ($0.03/req): Small model + RAG (3 chunks)
Config 3 ($0.05/req): Small model + RAG + reranker
Config 4 ($0.08/req): Large model + RAG (3 chunks)
Config 5 ($0.12/req): Large model + RAG + reranker + 5 chunks
Config 6 ($0.20/req): Large model + full RAG + multi-step reasoning
```

---

## 7. The "Change One Lever at a Time" Rule

**Critical discipline**: Never change multiple things simultaneously.

### Why

If you change the prompt AND the model AND the retrieval AND deploy:
- Quality improves 15%
- Which change caused it? Unknown.
- One change might have hurt quality while another compensated
- You can't learn what works

### Correct Process

```
Week 1: Change prompt → Measure → +5% quality, no cost change
Week 2: Add reranker → Measure → +8% quality, +$0.001 cost
Week 3: Route simple queries to small model → Measure → -2% quality, -40% cost
Week 4: Increase chunk overlap → Measure → +3% quality, no cost change
```

### What Counts as "One Lever"

- Changing prompt wording = 1 lever
- Changing model = 1 lever  
- Changing retrieval top-k = 1 lever
- Changing chunk size = 1 lever
- Adding a reranker = 1 lever
- Changing temperature = 1 lever

### Exception: Obvious Wins

If something is clearly broken (e.g., chunks are 4000 tokens each and quality is terrible), fix the obvious problem without full A/B testing. Use judgment.

---

## 8. Fine-Tuning vs Prompt Engineering Decision Matrix

| Factor | Prompt Engineering | Fine-Tuning |
|--------|-------------------|-------------|
| Time to deploy | Minutes | Days-Weeks |
| Data needed | 0-10 examples | 100-10000 examples |
| Cost to iterate | Free | $10-$10000 per run |
| Flexibility | Change anytime | Retrain to change |
| Token efficiency | Uses context window | Behavior in weights |
| Consistency | Variable | High |
| Complexity ceiling | Medium | High |
| Risk of regression | Low | Medium (catastrophic forgetting) |
| Multi-task | Easy (different prompts) | Hard (one model per task or adapters) |

### Decision Flow

```
Can you solve it with a better prompt? → YES → Do that
                                        → NO ↓
Do you have 100+ quality examples?     → NO → Collect more data first
                                        → YES ↓
Is the task narrow and well-defined?   → NO → RAG or better orchestration
                                        → YES ↓
Is latency/cost critical?             → YES → Fine-tune (reduce prompt size)
                                        → NO ↓
Is consistency critical?              → YES → Fine-tune
                                        → NO → Keep iterating on prompts
```

---

## 9. Distillation Strategies

### Large Teacher → Small Student

**Goal**: Get 90-95% of GPT-4's quality at GPT-4o-mini's cost.

### Strategy 1: Direct Distillation

```
1. Collect 5000 production queries
2. Run through GPT-4 with ideal system prompt
3. Grade outputs (keep score > 4/5)
4. Fine-tune GPT-4o-mini on graded outputs
5. Evaluate on held-out 500 queries
6. Deploy if student > 90% of teacher quality
```

### Strategy 2: Progressive Distillation

```
GPT-4 (teacher) → GPT-4o (intermediate) → GPT-4o-mini (student)

Each step loses ~5% quality but reduces cost significantly.
Use intermediate model as additional training signal.
```

### Strategy 3: Task-Specific Distillation

```
Don't distill everything. Identify your top-5 query types:
1. FAQ questions (40% of traffic) → Distill
2. Policy lookups (25% of traffic) → Distill  
3. Account issues (15% of traffic) → Distill
4. Complex complaints (10% of traffic) → Keep on teacher
5. Edge cases (10% of traffic) → Keep on teacher

Result: 80% of traffic on cheap student, 20% on expensive teacher
```

### Strategy 4: Chain-of-Thought Distillation

```
Teacher generates: reasoning + answer
Student trains on: reasoning + answer (learns the reasoning pattern)
At inference: Student generates reasoning + answer
Optional: Strip reasoning from final output to save output tokens
```

### Distillation Evaluation

```
Metrics to track:
- Quality gap: (teacher_score - student_score) / teacher_score
- Cost savings: 1 - (student_cost / teacher_cost)  
- Effective savings: cost_savings × (1 - quality_gap)
- Coverage: % of queries where student quality > threshold
```

### When Distillation Fails

- Task requires genuine reasoning (not pattern matching)
- High variance in query types (student can't specialize)
- Teacher itself is inconsistent (noisy training signal)
- Insufficient data for the task distribution
- Safety-critical tasks (don't risk quality loss)

---

## 10. Putting It All Together: The Optimization Loop

```
┌─────────────────────────────────────────────┐
│  1. MEASURE                                  │
│     - Quality metrics (accuracy, relevance)  │
│     - Cost metrics ($/request, $/task)       │
│     - Latency metrics (p50, p95, p99)        │
│     - User metrics (satisfaction, retention) │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│  2. IDENTIFY                                 │
│     - Biggest quality gaps                   │
│     - Highest cost components                │
│     - Slowest pipeline stages                │
│     - Most common failure modes              │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│  3. CHANGE (one lever)                       │
│     - Follow tuning order                    │
│     - Pick highest ROI intervention          │
│     - Implement with feature flag            │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│  4. EVALUATE                                 │
│     - A/B test or shadow mode                │
│     - Statistical significance               │
│     - Check for regressions                  │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│  5. DEPLOY (or rollback)                     │
│     - Gradual rollout (1% → 10% → 100%)     │
│     - Monitor for degradation                │
│     - Document what worked and why           │
└────────────────────┬────────────────────────┘
                     ↓
              (back to MEASURE)
```

This loop runs continuously. The best AI teams complete this loop weekly.
