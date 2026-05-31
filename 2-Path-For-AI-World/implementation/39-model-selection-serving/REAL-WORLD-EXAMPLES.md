# Model Selection and Serving: Real-World Examples

## Case Study 1: Startup Model Stack Selection

### Company Profile
- **Company**: Series A fintech startup, 50 employees
- **Product**: AI-powered financial document analyzer (contracts, invoices, compliance docs)
- **Scale**: 5,000 documents/day, growing 20%/month
- **Budget**: $8,000/month for AI infrastructure
- **Team**: 2 backend engineers, 0 dedicated ML engineers

### The Challenge
They needed to handle three distinct AI tasks:
1. **Document classification** (15 categories): Which type of document is this?
2. **Information extraction**: Pull structured data from documents
3. **Semantic search**: Find relevant documents by meaning
4. **Quality summarization**: Generate executive summaries for long contracts

### Evaluation Process

**Week 1: Build eval sets**
```
Classification eval: 500 labeled documents (balanced across 15 categories)
Extraction eval: 200 documents with gold-standard extracted fields
Search eval: 100 query-document relevance pairs (NDCG@10)
Summarization eval: 50 documents with expert-written summaries (human eval)
```

**Week 2: Run evaluations**

Classification results:
| Model | Accuracy | F1 Macro | Latency P95 | Cost/1000 docs |
|-------|----------|----------|-------------|----------------|
| GPT-4o | 96.2% | 0.954 | 1.2s | $4.80 |
| GPT-4o-mini | 94.1% | 0.932 | 0.4s | $0.38 |
| Claude Haiku | 93.8% | 0.928 | 0.35s | $0.45 |
| Gemini Flash | 92.5% | 0.915 | 0.25s | $0.22 |

Extraction results:
| Model | Field Accuracy | Schema Compliance | Latency P95 | Cost/1000 docs |
|-------|---------------|-------------------|-------------|----------------|
| GPT-4o | 94.5% | 99.2% | 2.8s | $12.50 |
| Claude Sonnet | 95.1% | 99.5% | 2.5s | $14.00 |
| GPT-4o-mini | 88.3% | 96.1% | 0.9s | $1.20 |

### Final Architecture Chosen

```
Document Input
    │
    ▼
[Classification: GPT-4o-mini]  ← $0.38/1000 docs, 94.1% accuracy
    │
    ├── Simple docs → [Extraction: GPT-4o-mini] ← $1.20/1000
    └── Complex docs → [Extraction: GPT-4o] ← $12.50/1000
    
[Search: text-embedding-3-large] ← $0.13/1000 docs to embed
    │
    └── Pinecone for vector storage ($70/month)

[Summarization: GPT-4o] ← $18/1000 docs (only for contracts, ~500/day)
```

### Monthly Cost Breakdown
```
Classification: 5,000/day × 30 × $0.38/1000 = $57
Extraction (simple, 70%): 3,500/day × 30 × $1.20/1000 = $126
Extraction (complex, 30%): 1,500/day × 30 × $12.50/1000 = $562
Search embeddings: 5,000/day × 30 × $0.13/1000 = $19.50
Summarization: 500/day × 30 × $18/1000 = $270
Vector DB: $70

TOTAL: $1,104/month (well under $8K budget)
```

### Key Decision Rationale
- **Why not all GPT-4o**: Would cost $5,400/month for extraction alone
- **Why not open-source**: No ML engineer to manage infrastructure
- **Why GPT-4o-mini over Claude Haiku for classification**: Marginally better accuracy, similar cost
- **Why GPT-4o for summarization over Claude Sonnet**: Better structured output for their format

---

## Case Study 2: Regulated Company - Open Source vs Managed API

### Company Profile
- **Company**: European healthcare data platform (200 employees)
- **Regulation**: GDPR, HIPAA (US clients), MDR (Medical Device Regulation)
- **Requirement**: Process patient clinical notes to extract diagnoses and medications
- **Data sensitivity**: Contains PII, PHI (Protected Health Information)
- **Volume**: 50,000 clinical notes/day

### Compliance Requirements Matrix

| Requirement | Managed API (OpenAI) | Managed API (Azure OpenAI) | Self-Hosted (Llama 3.1) |
|-------------|---------------------|---------------------------|------------------------|
| Data residency (EU) | FAIL (US processing) | PASS (EU regions) | PASS (your servers) |
| HIPAA BAA | PASS (available) | PASS (available) | N/A (you control) |
| No data retention | Requires opt-out | PASS (zero retention) | PASS (you control) |
| GDPR Article 28 DPA | Available | Available | N/A |
| Audit trail | Limited | Available | Full control |
| Model interpretability | None | None | Full (weight access) |
| Vulnerability to provider breach | HIGH | MEDIUM | LOW |

### Risk Assessment

```
Risk 1: Data breach at provider
  - OpenAI direct: Data processed in US, subject to CLOUD Act
  - Azure OpenAI EU: Data stays in EU, Microsoft BAA covers HIPAA
  - Self-hosted: Data never leaves your infrastructure
  - Decision: Eliminate OpenAI direct API

Risk 2: Model output used for medical decisions (MDR)
  - All options: Model is "software as medical device" if used for diagnosis
  - Requirement: Need full audit trail of model version, inputs, outputs
  - Self-hosted advantage: Can freeze exact model version indefinitely
  - Azure advantage: Can pin model version (but Microsoft controls deprecation)

Risk 3: Vendor discontinuation
  - Azure: Could change terms, deprecate models
  - Self-hosted: Complete control, but responsible for security patches
  
Risk 4: Quality for medical NLP
  - GPT-4o: Excellent medical knowledge
  - Llama 3.1 70B: Good but requires fine-tuning for medical terminology
  - Fine-tuned Llama 3.1 70B: Matches GPT-4o on their specific task
```

### Final Decision: Hybrid Architecture

```
Architecture chosen:
┌────────────────────────────────────┐
│  Self-hosted (EU data center)       │
│                                     │
│  Llama 3.1 70B (fine-tuned)        │
│  - Clinical note processing         │
│  - PHI/PII extraction               │
│  - Diagnosis coding                 │
│  4x A100 80GB, vLLM                │
│  All patient data stays here        │
└────────────────────────────────────┘
              │
              │ De-identified data only
              ▼
┌────────────────────────────────────┐
│  Azure OpenAI (EU West region)      │
│                                     │
│  GPT-4o                             │
│  - Research summarization           │
│  - Report generation (no PHI)       │
│  - Model evaluation (synthetic)     │
└────────────────────────────────────┘
```

### Cost Comparison (Final)
```
Self-hosted (4x A100, EU cloud):
  Compute: €22,000/month (reserved 1yr)
  Engineering (0.5 FTE MLOps): €5,000/month
  Fine-tuning (quarterly): €2,000/quarter = €667/month
  Total: €27,667/month

Azure OpenAI (if they could use it for everything):
  50,000 notes/day × ~2000 tokens × 30 days = 3B tokens/month
  Cost: 3B × $6.25/1M = €18,750/month
  
  BUT: Cannot use for PHI without extensive compliance work
  Additional compliance cost: €15,000 one-time + €3,000/month ongoing

Decision driver: NOT cost — it was compliance and control
```

---

## Case Study 3: Model Comparison Experiment

### Setup
- **Task 1**: Customer email response generation (B2B SaaS)
- **Task 2**: Code review comment generation
- **Task 3**: Legal clause extraction from contracts

### Methodology
- 200 test samples per task
- Blind human evaluation (3 raters per sample)
- Automated metrics + human preference scoring
- Statistical significance testing (paired t-test, p<0.05)

### Task 1: Customer Email Response

```
Prompt: Generate a professional, empathetic response to this customer complaint.
Include: acknowledgment, explanation, resolution, next steps.

Metrics: Human preference (1-5), tone appropriateness, resolution quality
```

| Model | Human Pref (1-5) | Tone Score | Resolution | Latency | Cost/100 |
|-------|------------------|------------|------------|---------|----------|
| GPT-4o | 4.2 ± 0.3 | 4.5 | 4.1 | 1.8s | $1.25 |
| Claude 3.5 Sonnet | **4.4 ± 0.2** | **4.7** | 4.2 | 2.1s | $1.50 |
| Gemini 1.5 Pro | 3.9 ± 0.4 | 4.1 | **4.3** | 1.5s | $0.65 |

**Winner**: Claude 3.5 Sonnet (statistically significant over GPT-4o, p=0.02)
**Why**: Better empathy, more natural tone, customers rated it as "more human"

### Task 2: Code Review Comments

```
Prompt: Review this code diff and provide actionable comments on bugs, 
performance issues, and style violations.

Metrics: Issues found (recall), false positives, actionability score
```

| Model | Recall | Precision | Actionability | False Pos Rate | Cost/100 |
|-------|--------|-----------|---------------|----------------|----------|
| GPT-4o | 0.78 | 0.85 | 4.0 | 15% | $2.80 |
| Claude 3.5 Sonnet | **0.88** | **0.91** | **4.6** | **9%** | $3.20 |
| Gemini 1.5 Pro | 0.72 | 0.80 | 3.7 | 20% | $1.40 |

**Winner**: Claude 3.5 Sonnet (decisively, p<0.001)
**Why**: Found more real bugs, fewer false alarms, better explanations

### Task 3: Legal Clause Extraction

```
Prompt: Extract all indemnification clauses from this contract. For each:
- Quote the exact text
- Classify type (mutual, one-way, carve-out)
- Identify the indemnifying party

Metrics: Extraction recall, classification accuracy, exact match
```

| Model | Recall | Classification | Exact Match | Latency | Cost/100 |
|-------|--------|---------------|-------------|---------|----------|
| GPT-4o | **0.94** | **0.96** | 0.89 | 3.2s | $4.50 |
| Claude 3.5 Sonnet | 0.92 | 0.94 | **0.91** | 3.8s | $5.20 |
| Gemini 1.5 Pro | 0.91 | 0.92 | 0.85 | 2.1s | $2.10 |

**Winner**: Tie between GPT-4o and Claude (not statistically significant, p=0.31)
**Practical choice**: GPT-4o (slightly cheaper, slightly faster for same quality)

### Conclusions
```
1. No single model wins everything
2. Claude 3.5 Sonnet: Best for empathetic writing and code tasks
3. GPT-4o: Best for structured extraction and following complex schemas
4. Gemini 1.5 Pro: Best cost/performance when quality gap is acceptable
5. Always run YOUR eval on YOUR data — general benchmarks don't predict task performance
```

---

## Case Study 4: Model Routing in Production

### Company Profile
- **Product**: AI customer support chatbot for e-commerce
- **Volume**: 200,000 conversations/day
- **Goal**: Reduce costs without sacrificing quality on complex queries

### Router Architecture

```python
class ProductionRouter:
    """
    Deployed router that saves 55% cost by routing simple queries
    to GPT-4o-mini and only sending complex ones to GPT-4o.
    """
    
    def __init__(self):
        # Fine-tuned classifier (Llama 8B, <10ms inference)
        self.complexity_classifier = load_model("complexity-router-v3")
        
        # Routing rules based on classifier + heuristics
        self.rules = {
            "simple": {  # 70% of traffic
                "model": "gpt-4o-mini",
                "examples": [
                    "Where is my order?",
                    "What's your return policy?",
                    "Change my shipping address",
                ],
            },
            "complex": {  # 30% of traffic
                "model": "gpt-4o",
                "examples": [
                    "I received a damaged item and also want to change my subscription",
                    "Compare these three products for my specific use case",
                    "I'm having a billing issue that spans multiple orders",
                ],
            },
        }
    
    def classify(self, query: str, conversation_history: list) -> str:
        features = {
            "query_length": len(query.split()),
            "turn_count": len(conversation_history),
            "has_multiple_intents": self.detect_multi_intent(query),
            "requires_reasoning": self.detect_reasoning_need(query),
            "sentiment": self.detect_sentiment(query),  # Angry → complex
        }
        
        # Classifier output + business rules
        model_prediction = self.complexity_classifier.predict(features)
        
        # Override rules:
        # - VIP customers always get GPT-4o
        # - Negative sentiment → GPT-4o (better empathy = fewer escalations)
        # - Conversation > 5 turns → GPT-4o (something went wrong)
        
        return model_prediction
```

### Results After 3 Months

```
Before (all GPT-4o):
  200,000 conv/day × avg 4 messages × ~1000 tokens × $6.25/1M
  = $5,000/day = $150,000/month

After (routed):
  Simple (140,000 conv): 140K × 4 × 1000 × $0.375/1M = $210/day
  Complex (60,000 conv): 60K × 4 × 1000 × $6.25/1M = $1,500/day
  Router cost: 200K × $0.02/1000 = $4/day
  Total: $1,714/day = $51,420/month

Savings: $98,580/month (65.7% reduction)

Quality metrics:
  CSAT (simple queries): 4.3 → 4.2 (statistically insignificant, p=0.15)
  CSAT (complex queries): 4.3 → 4.3 (unchanged, still using GPT-4o)
  Resolution rate: 78% → 76% (minor decrease, within tolerance)
  Escalation rate: 12% → 13% (acceptable)
  
  Net: 65% cost reduction with <2% quality impact
```

### Monitoring and Continuous Improvement

```python
# Weekly quality audit
def weekly_router_audit():
    # Sample 100 "simple" routed conversations
    simple_samples = sample_conversations(tier="simple", n=100)
    
    # Run them through GPT-4o to see if quality would be better
    for sample in simple_samples:
        mini_response = sample["actual_response"]
        gpt4o_response = call_gpt4o(sample["query"])
        
        # Human eval: was the mini response adequate?
        # If >5% of simple-routed queries would significantly benefit
        # from GPT-4o, adjust routing threshold
    
    # Track routing accuracy over time
    # Retrain router classifier monthly with new labeled data
```

---

## Case Study 5: Migration from GPT-4 to Claude 3.5 Sonnet

### Context
- **Company**: Legal tech platform
- **Use case**: Contract analysis and clause generation
- **Reason for migration**: Claude 3.5 Sonnet showed better instruction following in evals, longer context window (200K vs 128K), and better handling of long legal documents

### Migration Timeline

```
Week 1: Evaluation
  - Ran existing eval suite (400 samples) against Claude 3.5 Sonnet
  - Results: Claude scored 3.2% higher on extraction, 5.1% higher on generation
  - Identified 12 prompts that needed modification

Week 2: Prompt Adaptation
  Key changes needed:
  1. Claude handles system prompts differently (prefers XML tags)
  2. Claude is more literal with instructions (less "helpful" guessing)
  3. JSON mode works differently (no json_object response_format)
  4. Token counting uses different tokenizer (need to adjust limits)

Week 3: Shadow Deployment
  - Both models receive same requests
  - Claude responses logged but not served to users
  - Compared outputs side-by-side for 50,000 requests
  
  Findings:
  - Claude 2.1% better on long documents (>50K tokens)
  - GPT-4 slightly better on ambiguous edge cases
  - Claude's refusal rate was higher (needed prompt adjustments)

Week 4: Canary Release
  - 5% of traffic → Claude
  - Monitored: error rate, latency, user feedback, output quality
  - Issue found: Claude's different stop sequences caused parsing errors
  - Fix deployed in 2 hours

Week 5-6: Gradual Rollout
  - 5% → 25% → 50% → 75% → 100%
  - At 50%: discovered Claude handles multi-turn context differently
  - Added explicit conversation summarization at turn 10
  - Final rollout at 100% after 2 weeks of 75%
```

### Prompt Changes Required

```python
# BEFORE (GPT-4 optimized):
system_prompt_gpt4 = """You are a legal document analyst. Extract all 
indemnification clauses. Return JSON with the following schema..."""

# AFTER (Claude optimized):
system_prompt_claude = """You are a legal document analyst.

<task>
Extract all indemnification clauses from the provided contract.
</task>

<output_format>
Return a JSON array where each element has:
- "text": exact quoted text of the clause
- "type": one of ["mutual", "one_way_company", "one_way_counterparty", "carve_out"]
- "party": the indemnifying party name
- "section": section number where found

Return ONLY the JSON array, no other text.
</output_format>

<rules>
- Include only indemnification clauses, not limitation of liability
- If a clause is ambiguous, include it with type "uncertain"
- Quote text exactly as written, including typos
</rules>"""
```

### Results Post-Migration

```
Quality:
  Extraction accuracy: 94.2% → 96.1% (+1.9%)
  Generation quality (human eval): 4.1 → 4.4 (+0.3)
  Long document handling: significantly better (200K context)
  
Cost:
  GPT-4: $3.50/1M input, $10.50/1M output (old pricing)
  Claude 3.5 Sonnet: $3.00/1M input, $15.00/1M output
  Net cost change: +8% (Claude is slightly more expensive for output-heavy tasks)
  But: Fewer retries needed (-15%), so effective cost was -7%

Latency:
  GPT-4 P95: 4.2s
  Claude P95: 3.8s (-9.5%)
  
Operational:
  Error rate: 0.3% → 0.1% (Claude more reliable)
  Rate limiting incidents: 12/month → 3/month
```

---

## Case Study 6: Self-Hosted Llama 3.1 70B with vLLM

### Infrastructure Setup

```yaml
# Hardware: 4x NVIDIA A100 80GB (p4de.24xlarge on AWS)
# Or: 2x A100 80GB with INT4 quantization (AWQ)
# Chosen: 2x A100 with AWQ quantization (cost-optimized)

# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llama-70b-vllm
spec:
  replicas: 2  # HA
  template:
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:v0.6.0
        args:
          - "--model"
          - "TheBloke/Llama-3.1-70B-Instruct-AWQ"
          - "--quantization"
          - "awq"
          - "--tensor-parallel-size"
          - "2"
          - "--max-model-len"
          - "8192"
          - "--gpu-memory-utilization"
          - "0.92"
          - "--max-num-seqs"
          - "128"
          - "--enable-prefix-caching"
          - "--port"
          - "8000"
        resources:
          limits:
            nvidia.com/gpu: 2
        ports:
        - containerPort: 8000
```

### Performance Benchmarks

```
Model: Llama 3.1 70B Instruct (AWQ INT4)
Hardware: 2x A100 80GB per replica, 2 replicas
Framework: vLLM 0.6.0

Throughput (continuous batching):
  Input length 512, output length 256:
    Single replica: 1,850 tokens/second
    Both replicas: 3,700 tokens/second
    
  Input length 2048, output length 512:
    Single replica: 1,200 tokens/second
    Both replicas: 2,400 tokens/second

Latency (single request):
  Time to first token (TTFT): 180ms (512 input)
  Token generation speed: 45 tokens/second
  Full response (256 tokens): ~5.9 seconds
  
  With batching (32 concurrent):
  TTFT: 350ms
  Effective per-request time: ~8.2 seconds

Daily capacity:
  3,700 tok/s × 86,400 seconds = 319M tokens/day
  At avg 768 tokens per request = 415,000 requests/day
```

### Cost Comparison vs API

```
Self-hosted (monthly):
  4x A100 80GB (2 replicas × 2 GPUs): 2x p4d.24xlarge reserved 1yr
  Cost: 2 × $7,200/month = $14,400/month
  Capacity: 9.6B tokens/month
  Effective cost: $1.50/1M tokens

API equivalent quality (GPT-4o-mini, roughly comparable to Llama 70B):
  9.6B tokens × $0.375/1M = $3,600/month
  
  Wait — API is CHEAPER?
  
  YES, for this volume. Self-hosted only wins when:
  1. Volume > 25B tokens/month (crossover point)
  2. OR data privacy requires it
  3. OR you need guaranteed latency (no rate limits)
  4. OR you need fine-tuning that API doesn't support

For THIS company (50,000 clinical notes, ~3B tokens/month):
  API would be: $1,125/month
  Self-hosted is: $14,400/month
  
  They chose self-hosted anyway because: PHI cannot leave infrastructure
  The $13,275/month premium is the "compliance tax"
```

### Operational Lessons Learned

```
1. GPU memory fragmentation
   - After 72 hours, vLLM memory efficiency drops ~5%
   - Solution: Rolling restart every 48 hours during low traffic

2. Model loading time
   - 70B AWQ takes ~4 minutes to load into GPU memory
   - Impact: Rolling deployments need careful orchestration
   - Solution: Blue-green deployment with pre-warmed replicas

3. Prefix caching effectiveness
   - 60% of their requests share a 2000-token system prompt
   - Prefix caching gave 35% throughput improvement
   - Must ensure system prompt is EXACTLY identical (byte-level)

4. Monitoring critical metrics
   - GPU utilization (target: 70-85%)
   - KV cache utilization (alert at >90%)
   - Request queue depth (alert at >100)
   - Generation speed (alert if <30 tok/s)
```

---

## Case Study 7: Fine-Tuning ROI Analysis

### Experiment: Customer Intent Classification

**Hypothesis**: Fine-tuned GPT-4o-mini will match GPT-4o quality at 1/17th the cost.

### Setup

```
Training data: 2,500 labeled examples (15 intent categories)
Validation set: 500 examples
Test set: 500 examples (held out, never seen during development)
```

### Results

| Approach | Accuracy | F1 Macro | Cost/1000 | Latency P95 |
|----------|----------|----------|-----------|-------------|
| GPT-4o (zero-shot) | 93.8% | 0.931 | $5.20 | 1.1s |
| GPT-4o (5-shot) | 95.2% | 0.946 | $8.40 | 1.4s |
| GPT-4o-mini (zero-shot) | 89.4% | 0.882 | $0.32 | 0.3s |
| GPT-4o-mini (5-shot) | 91.6% | 0.908 | $0.58 | 0.4s |
| **GPT-4o-mini (fine-tuned)** | **95.8%** | **0.952** | **$0.32** | **0.3s** |
| Llama 8B (fine-tuned) | 94.1% | 0.933 | $0.05* | 0.15s |

*Self-hosted cost amortized

### Fine-Tuning Cost

```
Training cost (OpenAI):
  2,500 examples × ~300 tokens each = 750K tokens
  Fine-tuning cost: $0.008/1K tokens × 750 = $6.00
  3 epochs: $18.00 total
  
  Experimentation (5 runs with different hyperparameters): $90
  
  Total fine-tuning investment: ~$100

ROI calculation:
  Without fine-tuning (GPT-4o 5-shot): $8.40/1000 requests
  With fine-tuning (GPT-4o-mini FT): $0.32/1000 requests
  
  Savings per 1000 requests: $8.08
  Break-even: $100 / $8.08 = 12.4K requests (less than 1 day of traffic)
  
  At 50,000 requests/day:
  Monthly savings: 50K × 30 × $8.08 / 1000 = $12,120/month
  Annual ROI: $145,440 saved for $100 investment = 145,340% ROI
```

### When Fine-Tuning DIDN'T Work

```
Experiment 2: Contract summarization
  - Fine-tuned GPT-4o-mini on 500 contract summaries
  - Result: Fine-tuned model was WORSE than GPT-4o zero-shot
  - Why: Summarization requires deep reasoning, not pattern matching
  - Lesson: Fine-tuning works for classification/extraction, not complex generation

Experiment 3: Code generation
  - Fine-tuned Llama 8B on 3,000 code examples
  - Result: Better at specific patterns, worse at novel problems
  - Why: Overfitted to training distribution, lost generality
  - Lesson: Fine-tuning narrows capability — good for specific, bad for general
```

---

## Case Study 8: Model Deprecation Incident

### Timeline

```
Day 0 (Monday 9:00 AM):
  Email from OpenAI: "gpt-4-0613 will be deprecated in 14 days"
  Impact: Primary model for 3 production services
  Team: 4 engineers, 1 PM

Day 0 (11:00 AM):
  Emergency meeting. Inventory:
  - Service A (contract analysis): 100% on gpt-4-0613
  - Service B (chatbot): 80% gpt-4-0613, 20% gpt-3.5-turbo
  - Service C (data extraction): 100% on gpt-4-0613
  - Total: ~2M API calls/day on this model

Day 0 (2:00 PM):
  Decision: Migrate to gpt-4o-2024-08-06
  Rationale: Most compatible, OpenAI's recommended replacement
  Risk: Need to validate that outputs are equivalent
  
Day 1-2:
  Ran full eval suite (1,200 test cases across 3 services)
  Results:
  - Service A: 94.2% → 95.1% (improved!)
  - Service B: 91.5% → 92.8% (improved!)
  - Service C: 96.1% → 93.4% (REGRESSION - 2.7% drop)
  
  Investigation: Service C relied on specific gpt-4-0613 JSON formatting quirks
  Fix: Updated output parser + added 2 examples to prompt

Day 3-4:
  Service C re-evaluated after prompt fix: 93.4% → 96.5% (better than before)
  Shadow deployment: All 3 services running both models in parallel
  
Day 5:
  Canary release: 10% traffic to new model
  Monitoring: No issues detected
  
Day 7:
  50% traffic to new model
  One issue: New model occasionally adds markdown formatting
  Fix: Strip markdown from responses in post-processing
  
Day 10:
  100% traffic on new model
  Old model kept as fallback (API still works)
  
Day 14:
  Old model officially deprecated
  All systems stable
  Total engineering time: ~40 person-hours
```

### Lessons and Prevention Measures

```python
# Post-incident improvements:

# 1. Model abstraction layer
class ModelClient:
    def __init__(self, config: ModelConfig):
        self.primary = config.primary_model
        self.fallback = config.fallback_model
        self.version_pinned = True  # Always use dated versions
    
    async def call(self, prompt: str) -> str:
        try:
            return await self._call_model(self.primary, prompt)
        except ModelDeprecatedError:
            alert_team("Primary model deprecated, using fallback")
            return await self._call_model(self.fallback, prompt)

# 2. Automated eval pipeline (runs weekly against latest models)
# 3. Calendar alerts set 90 days before known deprecation dates
# 4. Always maintain a tested fallback model
# 5. Never use un-dated model aliases in production
```

---

## Case Study 9: Building a Domain-Specific Benchmark Suite

### Context
- **Company**: E-commerce product search and recommendation
- **Need**: Evaluate models for product description generation, search relevance, and recommendation explanations
- **Challenge**: Public benchmarks (MMLU, HellaSwag) don't predict task performance

### Benchmark Design

```python
# Benchmark suite structure
benchmark = {
    "name": "ecommerce-ai-bench-v2",
    "version": "2.3",
    "tasks": [
        {
            "name": "product_description_generation",
            "samples": 300,
            "metrics": ["human_quality_1_5", "factual_accuracy", "seo_keyword_coverage"],
            "difficulty_tiers": ["simple_product", "technical_product", "fashion_product"],
        },
        {
            "name": "search_query_understanding",
            "samples": 500,
            "metrics": ["intent_accuracy", "entity_extraction_f1", "facet_prediction"],
            "difficulty_tiers": ["exact_match", "semantic", "ambiguous"],
        },
        {
            "name": "review_summarization",
            "samples": 200,
            "metrics": ["coverage", "faithfulness", "conciseness"],
            "difficulty_tiers": ["few_reviews", "contradicting_reviews", "multilingual"],
        },
    ],
    "evaluation_protocol": {
        "human_eval_samples": 50,  # Per task, for calibrating automated metrics
        "automated_judge": "gpt-4o",  # LLM-as-judge for scalable eval
        "statistical_test": "paired_t_test",
        "significance_level": 0.05,
        "minimum_effect_size": 0.03,  # Don't switch models for <3% improvement
    }
}
```

### Quarterly Evaluation Results

```
Q3 2024 Results:

Product Description Generation:
  GPT-4o:           Quality=4.3, Factual=96%, SEO=82%
  Claude 3.5 Sonnet: Quality=4.5, Factual=97%, SEO=78%
  Gemini 1.5 Pro:   Quality=4.0, Factual=94%, SEO=85%
  Llama 3.1 70B:    Quality=3.8, Factual=91%, SEO=79%

Search Query Understanding:
  GPT-4o:           Intent=94%, Entity=91%, Facet=87%
  Claude 3.5 Sonnet: Intent=93%, Entity=89%, Facet=85%
  Gemini 1.5 Pro:   Intent=91%, Entity=88%, Facet=84%
  Llama 3.1 70B:    Intent=89%, Entity=86%, Facet=80%

Decision: Use GPT-4o for search (best entity extraction),
         Claude for product descriptions (best quality)
```

### Ongoing Monitoring

```python
# Automated weekly regression detection
def weekly_model_check():
    """Run every Monday at 6 AM"""
    current_results = run_benchmark(
        models=["gpt-4o-2024-08-06", "claude-3-5-sonnet-20241022"],
        sample_size=100,  # Subset for weekly (full 500 monthly)
    )
    
    # Compare to last month's full benchmark
    baseline = load_results("2024-10-benchmark")
    
    for task in current_results:
        for metric in task.metrics:
            diff = current_results[task][metric] - baseline[task][metric]
            if abs(diff) > 0.05:  # >5% change
                alert(f"Model drift detected: {task}.{metric} changed by {diff:.1%}")
                trigger_full_benchmark()
```

---

## Case Study 10: Quantization Optimization (FP16 to INT4 AWQ)

### Before: Llama 3.1 70B at FP16

```
Hardware: 4x A100 80GB (required for 140GB model weights)
Cost: $28,800/month (reserved)
Throughput: 800 tokens/second
Max concurrent users: ~50 (with 2s response target)
GPU memory usage: 140GB weights + 40GB KV cache = 180GB (56% utilization per GPU)
```

### After: Llama 3.1 70B at INT4 (AWQ)

```
Hardware: 2x A100 80GB (only 35GB for weights!)
Cost: $14,400/month (reserved)
Throughput: 1,400 tokens/second (+75%)
Max concurrent users: ~150 (with 2s response target)
GPU memory usage: 35GB weights + 80GB KV cache = 115GB
  More memory for KV cache = more concurrent requests!
```

### Quality Impact Measurement

```
Evaluation on 500-sample benchmark:

Task: Intent Classification (15 classes)
  FP16: 94.8% accuracy
  INT4 AWQ: 94.2% accuracy
  Difference: -0.6% (NOT statistically significant, p=0.21)

Task: Text Summarization (ROUGE-L)
  FP16: 0.412
  INT4 AWQ: 0.407
  Difference: -1.2% (NOT statistically significant, p=0.15)

Task: Code Generation (pass@1 on HumanEval)
  FP16: 68.3%
  INT4 AWQ: 66.5%
  Difference: -2.6% (marginally significant, p=0.048)
  Note: This is the task most sensitive to quantization

Task: Reasoning (GSM8K)
  FP16: 83.2%
  INT4 AWQ: 81.1%
  Difference: -2.5% (significant, p=0.03)

Conclusion: <1% loss for classification/extraction, 2-3% for reasoning
For their primary use case (classification + extraction): quantization is free lunch
```

### Quantization Process

```bash
# Step 1: Quantize model (one-time, ~4 hours on 1x A100)
python -m awq.entry \
  --model_path meta-llama/Llama-3.1-70B-Instruct \
  --w_bit 4 \
  --q_group_size 128 \
  --run_awq \
  --dump_awq awq_cache/llama-70b-awq.pt

python -m awq.entry \
  --model_path meta-llama/Llama-3.1-70B-Instruct \
  --w_bit 4 \
  --q_group_size 128 \
  --load_awq awq_cache/llama-70b-awq.pt \
  --q_backend autoawq \
  --dump_quant quant_models/Llama-3.1-70B-Instruct-AWQ

# Step 2: Deploy with vLLM (automatic AWQ detection)
python -m vllm.entrypoints.openai.api_server \
  --model quant_models/Llama-3.1-70B-Instruct-AWQ \
  --quantization awq \
  --tensor-parallel-size 2 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.92
```

### Business Impact Summary

```
Before quantization:
  Hardware: 4x A100 = $28,800/month
  Throughput: 800 tok/s → supports ~230K requests/day
  Cost per 1M tokens: $28,800 / (800 × 86400 / 1M) × 30 ≈ $13.89

After quantization:
  Hardware: 2x A100 = $14,400/month
  Throughput: 1,400 tok/s → supports ~400K requests/day
  Cost per 1M tokens: $14,400 / (1400 × 86400 / 1M) × 30 ≈ $3.97

Results:
  - 50% hardware cost reduction
  - 75% throughput increase
  - 71% cost-per-token reduction
  - 3x more concurrent users on same hardware
  - <1% quality loss for primary use cases

Payback period: Immediate (no additional investment needed)
The only cost was 2 days of engineering time for evaluation and deployment.
```

---

## Key Takeaways Across All Case Studies

1. **Always evaluate on YOUR data** — public benchmarks are misleading for specific tasks
2. **Model routing saves 50-70% cost** with minimal quality impact
3. **Self-hosting is rarely cheaper** — it's justified by compliance, not cost
4. **Fine-tuning has massive ROI** for classification/extraction, poor ROI for generation
5. **Quantization is nearly free** — INT4 AWQ loses <1% on most tasks
6. **Model migration is inevitable** — build abstraction layers from day 1
7. **No single model wins all tasks** — multi-model architectures are the norm
8. **Statistical significance matters** — don't switch models for noise
9. **Version pin everything** — un-dated model aliases are a production risk
10. **Budget for evaluation** — 10% of AI budget should go to eval infrastructure
