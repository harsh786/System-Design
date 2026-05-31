# Model Selection and Serving Strategy

## Why This Matters

Choosing the wrong model costs you 10x in compute, 5x in latency, or infinite in compliance fines. Choosing the right model but serving it wrong means you can't scale. This module gives you the complete framework for evaluating, selecting, and serving models in production.

---

## 1. The Model Landscape (2024-2025)

### Frontier Models (Highest Capability)

| Model | Provider | Context Window | Strengths | Weaknesses | Pricing (per 1M tokens) |
|-------|----------|---------------|-----------|------------|------------------------|
| GPT-4o | OpenAI | 128K | Multimodal, fast, strong reasoning | Expensive at scale, closed-source | $2.50 input / $10 output |
| Claude 3.5 Sonnet | Anthropic | 200K | Best coding, long context, instruction following | No fine-tuning API, limited multimodal | $3 input / $15 output |
| Gemini 1.5 Pro | Google | 2M | Massive context, multimodal native | Inconsistent quality, less predictable | $1.25 input / $5 output |
| GPT-o1 | OpenAI | 200K | Deep reasoning, chain-of-thought | Very slow (30-60s), very expensive | $15 input / $60 output |

### Mid-Tier Models (Best Cost/Performance)

| Model | Provider | Context Window | Strengths | Best For | Pricing (per 1M tokens) |
|-------|----------|---------------|-----------|----------|------------------------|
| GPT-4o-mini | OpenAI | 128K | Fast, cheap, surprisingly capable | Classification, extraction, simple generation | $0.15 input / $0.60 output |
| Claude 3.5 Haiku | Anthropic | 200K | Fast, good instruction following | Summarization, routing, simple tasks | $0.25 input / $1.25 output |
| Gemini 2.0 Flash | Google | 1M | Very fast, large context, cheap | Long document processing | $0.10 input / $0.40 output |

### Open-Source Models (Self-Hostable)

| Model | Parameters | License | Strengths | Hardware Required |
|-------|-----------|---------|-----------|-------------------|
| Llama 3.1 405B | 405B | Llama 3.1 Community | Near-frontier quality | 8x A100 80GB or 4x H100 |
| Llama 3.1 70B | 70B | Llama 3.1 Community | Strong general purpose | 2x A100 80GB (FP16) or 1x A100 (INT4) |
| Llama 3.1 8B | 8B | Llama 3.1 Community | Fast, fine-tuning friendly | 1x A10G or 1x L4 |
| Mistral Large 2 | 123B | Apache 2.0 | Multilingual, function calling | 4x A100 80GB |
| Mixtral 8x22B | 176B (MoE) | Apache 2.0 | Fast (only 44B active), good coding | 2x A100 80GB |
| Qwen 2.5 72B | 72B | Qwen License | Best Chinese, strong math/code | 2x A100 80GB |
| DeepSeek V3 | 671B (MoE) | DeepSeek License | Near-frontier at lower cost | 8x H100 |
| Phi-3 Medium | 14B | MIT | Small, efficient, strong reasoning | 1x A10G |

### Embedding Models

| Model | Dimensions | Max Tokens | Best For |
|-------|-----------|------------|----------|
| text-embedding-3-large | 3072 | 8191 | High-quality semantic search |
| text-embedding-3-small | 1536 | 8191 | Cost-effective search |
| Cohere embed-v3 | 1024 | 512 | Multilingual search |
| BGE-M3 (open) | 1024 | 8192 | Self-hosted multilingual |
| GTE-Qwen2 (open) | varies | 131072 | Long document embedding |

---

## 2. Model Selection Framework

### Step 1: Define Your Requirements

```yaml
# Model Requirements Template
task_description: "Classify customer support tickets into 15 categories"
requirements:
  quality:
    minimum_accuracy: 0.92  # On your eval set
    acceptable_latency_p95: 500ms
    acceptable_latency_p99: 2000ms
  scale:
    requests_per_day: 50000
    peak_rps: 20
    growth_rate_monthly: 15%
  constraints:
    data_residency: "EU only"
    pii_in_prompts: true
    budget_monthly_usd: 2000
    compliance: ["SOC2", "GDPR"]
  operational:
    uptime_sla: 99.9%
    model_deprecation_tolerance: "30 days migration"
    team_ml_expertise: "intermediate"
```

### Step 2: Eliminate Based on Hard Constraints

```
Decision Tree for Hard Constraints:

1. Does data contain PII that cannot leave your infrastructure?
   YES → Self-hosted only (Llama, Mistral, Qwen)
   NO → Continue

2. Do you need specific compliance certifications?
   YES → Check provider compliance pages:
         - OpenAI: SOC2, GDPR (with DPA)
         - Anthropic: SOC2, GDPR (with DPA)
         - Azure OpenAI: SOC2, HIPAA, FedRAMP
         - AWS Bedrock: SOC2, HIPAA, FedRAMP, ITAR
   NO → Continue

3. Is data residency required in a specific region?
   YES → Check provider region availability:
         - Azure OpenAI: US, EU, Asia (many regions)
         - AWS Bedrock: US, EU, APAC
         - GCP Vertex AI: US, EU, APAC
         - Direct API (OpenAI/Anthropic): US only processing
   NO → Continue

4. Is your budget < $500/month?
   YES → Mid-tier models or open-source only
   NO → All options available
```

### Step 3: Build a Custom Evaluation Set

```python
# Minimum viable eval set structure
eval_set = {
    "task": "ticket_classification",
    "version": "2.1",
    "created": "2024-11-15",
    "samples": 200,  # Minimum 100, ideally 500+
    "categories": [
        {
            "id": "easy",
            "description": "Clear, single-intent tickets",
            "count": 80,
            "examples": [...]
        },
        {
            "id": "medium",
            "description": "Multi-intent or ambiguous tickets",
            "count": 80,
            "examples": [...]
        },
        {
            "id": "hard",
            "description": "Edge cases, sarcasm, complex issues",
            "count": 40,
            "examples": [...]
        }
    ],
    "metrics": ["accuracy", "f1_macro", "latency_p95", "cost_per_1000"]
}
```

### Step 4: Run Comparative Evaluation

```python
import asyncio
from dataclasses import dataclass
from typing import List

@dataclass
class ModelConfig:
    name: str
    provider: str
    model_id: str
    cost_per_1m_input: float
    cost_per_1m_output: float

CANDIDATES = [
    ModelConfig("GPT-4o-mini", "openai", "gpt-4o-mini", 0.15, 0.60),
    ModelConfig("Claude Haiku", "anthropic", "claude-3-5-haiku-20241022", 0.25, 1.25),
    ModelConfig("Gemini Flash", "google", "gemini-2.0-flash", 0.10, 0.40),
    ModelConfig("Llama 3.1 8B", "self-hosted", "meta-llama/Llama-3.1-8B-Instruct", 0.0, 0.0),
]

async def evaluate_model(model: ModelConfig, eval_set: List[dict]) -> dict:
    results = {
        "model": model.name,
        "correct": 0,
        "total": len(eval_set),
        "latencies": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    
    for sample in eval_set:
        start = time.time()
        response = await call_model(model, sample["prompt"])
        latency = time.time() - start
        
        results["latencies"].append(latency)
        results["total_input_tokens"] += response.input_tokens
        results["total_output_tokens"] += response.output_tokens
        
        if extract_answer(response.text) == sample["expected"]:
            results["correct"] += 1
    
    results["accuracy"] = results["correct"] / results["total"]
    results["latency_p95"] = np.percentile(results["latencies"], 95)
    results["cost_per_1000"] = (
        (results["total_input_tokens"] / 1_000_000 * model.cost_per_1m_input) +
        (results["total_output_tokens"] / 1_000_000 * model.cost_per_1m_output)
    ) * (1000 / results["total"])
    
    return results
```

### Step 5: Decision Matrix

| Criterion | Weight | GPT-4o-mini | Claude Haiku | Gemini Flash | Llama 8B |
|-----------|--------|-------------|--------------|--------------|----------|
| Accuracy | 0.35 | 0.94 | 0.93 | 0.91 | 0.87 |
| Latency P95 | 0.20 | 320ms | 280ms | 190ms | 150ms |
| Cost/1000 req | 0.20 | $0.12 | $0.15 | $0.08 | $0.03* |
| Data privacy | 0.15 | 7/10 | 7/10 | 7/10 | 10/10 |
| Reliability | 0.10 | 9/10 | 9/10 | 8/10 | 7/10** |

*Self-hosted cost amortized over GPU hours
**Self-hosted reliability depends on your infra team

---

## 3. Model Tiering Strategy

### The Three-Tier Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User Request                        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              Router / Classifier                      │
│   (GPT-4o-mini or fine-tuned Llama 8B)              │
│                                                      │
│   Classifies request complexity:                     │
│   - Simple (FAQ, lookup, classification) → Tier 1   │
│   - Medium (summarization, extraction) → Tier 2     │
│   - Complex (reasoning, generation, coding) → Tier 3│
└───────┬──────────────────┬──────────────┬───────────┘
        │                  │              │
        ▼                  ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Tier 1     │  │   Tier 2     │  │   Tier 3     │
│  Small/Fast  │  │  Mid-Tier    │  │  Frontier    │
│              │  │              │  │              │
│ GPT-4o-mini  │  │ Claude Haiku │  │ GPT-4o       │
│ Gemini Flash │  │ GPT-4o-mini  │  │ Claude Sonnet│
│ Llama 8B     │  │ Llama 70B    │  │ GPT-o1       │
│              │  │              │  │              │
│ ~70% traffic │  │ ~20% traffic │  │ ~10% traffic │
│ $0.10/1K req │  │ $0.50/1K req │  │ $5.00/1K req │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Router Implementation

```python
class ModelRouter:
    def __init__(self):
        self.router_model = "gpt-4o-mini"  # Or fine-tuned classifier
        self.tier_config = {
            "tier1": {"model": "gpt-4o-mini", "max_tokens": 500},
            "tier2": {"model": "claude-3-5-haiku-20241022", "max_tokens": 2000},
            "tier3": {"model": "gpt-4o", "max_tokens": 4000},
        }
    
    async def route(self, query: str, context: dict) -> str:
        # Option A: LLM-based routing
        routing_prompt = f"""Classify this query's complexity:
        - SIMPLE: factual lookup, yes/no, classification, short extraction
        - MEDIUM: summarization, moderate generation, multi-step extraction
        - COMPLEX: reasoning, creative generation, code generation, analysis
        
        Query: {query}
        Classification:"""
        
        tier = await self.classify(routing_prompt)
        
        # Option B: Heuristic routing (faster, no API call)
        if len(query.split()) < 20 and not any(w in query.lower() for w in ["explain", "analyze", "write", "create"]):
            tier = "tier1"
        elif len(query.split()) > 100 or "code" in query.lower():
            tier = "tier3"
        else:
            tier = "tier2"
        
        return self.tier_config[tier]
    
    async def route_with_fallback(self, query: str, context: dict) -> str:
        """Route with automatic upgrade on failure"""
        tier = await self.route(query, context)
        response = await self.call_model(tier, query)
        
        # Quality check - upgrade if response is low quality
        if self.quality_score(response) < 0.7 and tier != "tier3":
            next_tier = {"tier1": "tier2", "tier2": "tier3"}[tier["name"]]
            response = await self.call_model(self.tier_config[next_tier], query)
        
        return response
```

### Cost Impact of Tiering

```
Without tiering (all GPT-4o):
  100,000 requests/day × $5.00/1000 = $500/day = $15,000/month

With tiering:
  70,000 × $0.10/1000 = $7/day      (Tier 1)
  20,000 × $0.50/1000 = $10/day     (Tier 2)
  10,000 × $5.00/1000 = $50/day     (Tier 3)
  Router: 100,000 × $0.05/1000 = $5/day
  Total: $72/day = $2,160/month

Savings: 85.6% ($12,840/month)
```

---

## 4. Managed APIs vs Self-Hosted: Decision Framework

### When to Use Managed APIs

- Traffic < 1M tokens/day (cost-effective below this)
- Need access to frontier models (GPT-4o, Claude 3.5 Sonnet)
- Team has < 2 ML engineers
- Time to production matters (days vs weeks)
- Variable/unpredictable traffic patterns
- You accept vendor lock-in risk

### When to Self-Host

- Traffic > 10M tokens/day (significant cost savings)
- Data cannot leave your infrastructure (PII, HIPAA, classified)
- You need model customization (fine-tuning, custom architectures)
- Predictable, steady traffic patterns
- Team has 2+ ML/infra engineers
- You need guaranteed latency (no cold starts, no rate limits)

### Cost Crossover Analysis

```
Managed API Cost (GPT-4o-mini):
  Monthly tokens × ($0.15 + $0.60) / 2 / 1,000,000
  
  At 1M tokens/day: 30M tokens/month = $11.25/month
  At 10M tokens/day: 300M tokens/month = $112.50/month
  At 100M tokens/day: 3B tokens/month = $1,125/month
  At 1B tokens/day: 30B tokens/month = $11,250/month

Self-Hosted Llama 3.1 8B (1x A100 80GB on AWS):
  Instance: p4d.24xlarge = ~$12,000/month (on-demand)
  Or: 1x A100 spot = ~$3,000/month
  Or: Reserved 1yr = ~$7,200/month
  
  Throughput: ~2000 tokens/second = 5.2B tokens/month
  
  Cost per 1M tokens: $7,200 / 5,200 = $1.38/1M tokens

Crossover point (GPT-4o-mini vs self-hosted Llama 8B):
  API becomes more expensive when:
  Monthly spend > $7,200 (reserved) = ~19.2B tokens/month
  
  BUT: Self-hosted Llama 8B quality < GPT-4o-mini quality
  Fair comparison: Self-hosted Llama 70B vs GPT-4o
  
  Llama 70B on 2x A100: ~$14,400/month reserved
  Throughput: ~500 tokens/second = 1.3B tokens/month
  Cost per 1M tokens: $14,400 / 1,300 = $11.08/1M tokens
  
  GPT-4o: ($2.50 + $10) / 2 = $6.25/1M tokens average
  
  Conclusion: GPT-4o is CHEAPER than self-hosted Llama 70B
  unless you have 3yr reserved instances or spot instances
```

### Decision Matrix

| Factor | Managed API | Self-Hosted |
|--------|-------------|-------------|
| Setup time | Hours | Weeks |
| Ongoing maintenance | None | 0.5-1 FTE |
| Scaling | Automatic | Manual (autoscaling possible) |
| Latency control | Limited | Full |
| Data privacy | DPA required | Complete control |
| Model updates | Automatic (risk) | You control |
| Cost at low volume | Low | High (fixed GPU cost) |
| Cost at high volume | High (linear) | Lower (amortized) |
| Fine-tuning | Limited | Full control |
| Vendor risk | High | None |

---

## 5. Open-Source Model Production Readiness

### Production-Ready (Use Confidently)

| Model | Why It's Ready | Best Use Case |
|-------|---------------|---------------|
| Llama 3.1 70B | Extensively tested, strong community, good tooling | General purpose, on-par with GPT-4-turbo |
| Llama 3.1 8B | Fast, cheap to run, good for fine-tuning | Classification, extraction, simple generation |
| Mistral 7B | Apache 2.0, very fast, well-supported | Edge deployment, high-throughput tasks |
| Mixtral 8x7B | MoE efficiency, Apache 2.0 | Cost-effective mid-tier replacement |

### Production-Ready with Caveats

| Model | Caveat | Mitigation |
|-------|--------|------------|
| Llama 3.1 405B | Requires massive hardware (8x A100) | Use quantized (AWQ/GPTQ) on 4x A100 |
| Qwen 2.5 72B | License restricts some commercial use | Check Qwen license for your use case |
| DeepSeek V3 | Very new, limited production reports | Run extensive evals, shadow deployment |

### Not Production-Ready (Use for Experimentation)

| Model | Why Not | When It Might Be |
|-------|---------|-------------------|
| Any model < 1 month old | Insufficient community testing | After 3+ months of community use |
| Models without safety tuning | Harmful output risk | After applying safety fine-tuning |
| Models with restrictive licenses | Legal risk | When license is clarified |

---

## 6. Fine-Tuning vs RAG vs Prompt Engineering

### Decision Tree

```
Start: I need to improve model performance for my task

Q1: Is the knowledge the model needs already in its training data?
├── YES → Q2
└── NO → Does the knowledge change frequently (weekly/daily)?
    ├── YES → RAG (retrieval-augmented generation)
    └── NO → Q3: How much training data do you have?
        ├── < 50 examples → Prompt Engineering (few-shot)
        ├── 50-500 examples → Fine-tuning might help, but try RAG first
        └── > 500 examples → Fine-tuning likely worth it

Q2: Is the issue about format/style/behavior (not knowledge)?
├── YES → Q4
└── NO → Prompt Engineering (better instructions)

Q4: Can you describe the desired behavior in instructions?
├── YES → Prompt Engineering first (cheaper, faster iteration)
│   └── Still not good enough? → Fine-tuning
└── NO → Fine-tuning (the behavior is "know it when I see it")
```

### Comparison Table

| Dimension | Prompt Engineering | RAG | Fine-Tuning |
|-----------|-------------------|-----|-------------|
| Time to implement | Hours | Days | Weeks |
| Cost to implement | ~$0 | $500-5000 | $1000-50000 |
| Ongoing cost | Higher (longer prompts) | Medium (retrieval + generation) | Lower (shorter prompts) |
| Knowledge updates | Instant | Near-instant | Requires retraining |
| Quality ceiling | Limited by base model | Good for factual tasks | Highest for specific tasks |
| Expertise needed | Low | Medium | High |
| Data requirement | 3-10 examples | Document corpus | 500+ labeled examples |
| Latency impact | None | +200-500ms (retrieval) | None (often reduces latency) |

### When Fine-Tuning Wins

1. **Consistent output format**: JSON schema adherence, specific writing style
2. **Domain-specific language**: Medical, legal, financial terminology
3. **Reducing prompt size**: Encode instructions into weights (saves tokens)
4. **Latency-sensitive tasks**: Remove need for examples in prompt
5. **Small model performance**: Make 8B model perform like 70B for specific task

### When RAG Wins

1. **Dynamic knowledge**: Product catalogs, documentation, news
2. **Attribution required**: Need to cite sources
3. **Large knowledge base**: Too much to fit in context
4. **Freshness matters**: Information changes frequently
5. **Compliance**: Need to prove what data influenced the answer

### When Prompt Engineering Wins

1. **Quick iteration**: Testing approaches rapidly
2. **General tasks**: Model already knows how to do it
3. **Low volume**: Not worth the investment in fine-tuning/RAG
4. **Changing requirements**: Task definition still evolving
5. **Prototype phase**: Validating the approach before investing

---

## 7. Model Versioning and Deprecation

### The Problem

```
Timeline of OpenAI model deprecations:
- 2023-06: code-davinci-002 deprecated (2 weeks notice)
- 2023-07: gpt-4-0314 deprecated (3 months notice)
- 2024-01: gpt-4-vision-preview deprecated (6 months notice)
- 2024-06: gpt-4-0613 deprecated (6 months notice)
- 2024-10: gpt-4-turbo-2024-04-09 deprecated

Pattern: Models get ~6 months from deprecation announcement
Risk: Your evals may not transfer to the replacement model
```

### Version Pinning Strategy

```python
# config/models.yaml
models:
  primary_generation:
    provider: openai
    model_id: "gpt-4o-2024-08-06"  # ALWAYS pin to dated version
    # Never use: "gpt-4o" (points to latest, can change without notice)
    fallback: "claude-3-5-sonnet-20241022"
    deprecated_after: "2025-06-01"  # Set alert 90 days before
    
  classification:
    provider: anthropic
    model_id: "claude-3-5-haiku-20241022"
    fallback: "gpt-4o-mini-2024-07-18"
    
  embeddings:
    provider: openai
    model_id: "text-embedding-3-large"
    # WARNING: Changing embedding model requires full re-indexing
    migration_cost: "high"  # Flag models where migration is expensive
```

### Migration Playbook

```
Phase 1: Alert (Day 0)
  - Deprecation notice received
  - Create migration ticket
  - Identify all systems using deprecated model
  - Estimate migration effort

Phase 2: Evaluate (Day 1-14)
  - Run existing eval suite against replacement model
  - Identify quality regressions
  - Test prompt compatibility
  - Measure latency/cost differences

Phase 3: Adapt (Day 15-60)
  - Modify prompts for new model if needed
  - Update output parsing (different models format differently)
  - Re-run full eval suite
  - A/B test in shadow mode

Phase 4: Migrate (Day 61-90)
  - Canary deployment (5% traffic)
  - Monitor quality metrics
  - Gradual rollout (25% → 50% → 100%)
  - Keep old model as fallback until fully deprecated

Phase 5: Cleanup (Day 90+)
  - Remove old model references
  - Update documentation
  - Archive migration learnings
```

---

## 8. Multi-Model Architectures

### Common Patterns

#### Pattern 1: Router + Specialists

```
User Query → Router Model (GPT-4o-mini / fine-tuned classifier)
                │
                ├── "Code question" → Claude 3.5 Sonnet
                ├── "Math/reasoning" → GPT-o1
                ├── "Simple factual" → GPT-4o-mini
                ├── "Long document" → Gemini 1.5 Pro (2M context)
                └── "Creative writing" → Claude 3.5 Sonnet
```

#### Pattern 2: Generator + Judge

```
User Query → Generator Model (GPT-4o)
                │
                ▼
            Response → Judge Model (Claude 3.5 Sonnet or separate GPT-4o call)
                │
                ├── Quality score > 0.8 → Return response
                └── Quality score < 0.8 → Regenerate with feedback
```

#### Pattern 3: Retriever + Reranker + Generator

```
User Query → Embedding Model (text-embedding-3-large)
                │
                ▼
            Retrieve top-50 candidates from vector DB
                │
                ▼
            Reranker Model (Cohere rerank-v3 or cross-encoder)
                │
                ▼
            Top-5 passages → Generator Model (GPT-4o)
                │
                ▼
            Final Response
```

#### Pattern 4: Cascade (Cheapest First)

```
User Query → Tier 1 (GPT-4o-mini)
                │
                ▼
            Confidence check (logprobs or self-eval)
                │
                ├── High confidence → Return response
                └── Low confidence → Tier 2 (Claude 3.5 Sonnet)
                                        │
                                        ├── High confidence → Return
                                        └── Low confidence → Tier 3 (GPT-o1)
```

#### Pattern 5: Ensemble for Critical Decisions

```
Critical Query → ┌── Model A (GPT-4o)       ──┐
                 ├── Model B (Claude Sonnet)  ──├── Aggregator
                 └── Model C (Gemini Pro)     ──┘
                                                     │
                                                     ▼
                                              Majority vote or
                                              weighted consensus
```

---

## 9. Model Evaluation Methodology

### Building Your Eval Suite

#### Eval Types

1. **Task-specific accuracy**: Does the model get the right answer?
2. **Format compliance**: Does output match expected schema?
3. **Latency**: P50, P95, P99 response times
4. **Cost efficiency**: Cost per correct answer
5. **Safety**: Does the model refuse harmful requests?
6. **Robustness**: Does performance degrade with edge cases?
7. **Consistency**: Same input → similar output across runs?

#### Statistical Rigor

```python
import scipy.stats as stats

def is_model_a_better(results_a: list, results_b: list, alpha=0.05) -> dict:
    """
    Determine if Model A is statistically significantly better than Model B.
    Uses paired t-test since both models see same eval samples.
    """
    # Paired differences
    differences = [a - b for a, b in zip(results_a, results_b)]
    
    # Paired t-test
    t_stat, p_value = stats.ttest_rel(results_a, results_b)
    
    # Effect size (Cohen's d)
    d = np.mean(differences) / np.std(differences)
    
    # Confidence interval for the difference
    ci = stats.t.interval(
        1 - alpha,
        len(differences) - 1,
        loc=np.mean(differences),
        scale=stats.sem(differences)
    )
    
    return {
        "a_mean": np.mean(results_a),
        "b_mean": np.mean(results_b),
        "difference": np.mean(differences),
        "p_value": p_value,
        "significant": p_value < alpha,
        "effect_size": d,  # Small: 0.2, Medium: 0.5, Large: 0.8
        "confidence_interval": ci,
        "sample_size_adequate": len(results_a) >= 100,
    }

# Example: Need at least 100 samples for reliable results
# For detecting 3% accuracy difference with 80% power: need ~500 samples
```

#### Eval-Driven Development Loop

```
1. Write eval set (golden labels from domain experts)
2. Run baseline model → establish benchmark
3. Make change (prompt, model, RAG, fine-tune)
4. Run eval → compare to baseline
5. If improvement is statistically significant AND meaningful → ship
6. If not → iterate or revert
7. Monitor production metrics (drift detection)
```

---

## 10. Serving Architecture

### Framework Comparison

| Framework | Best For | Throughput | Features |
|-----------|----------|------------|----------|
| vLLM | General self-hosted serving | Very High | PagedAttention, continuous batching |
| TGI (HuggingFace) | Quick deployment, HF ecosystem | High | Token streaming, watermarking |
| TensorRT-LLM (NVIDIA) | Maximum GPU utilization | Highest | INT4/INT8, inflight batching |
| Triton (NVIDIA) | Multi-model serving, pipelines | High | Model ensembles, dynamic batching |
| Ollama | Development/testing | Low | Simple setup, CPU support |
| llama.cpp | Edge/CPU deployment | Medium (CPU) | GGUF quantization, low memory |

### vLLM Production Setup

```python
# Recommended production deployment with vLLM
# docker-compose.yml

services:
  vllm:
    image: vllm/vllm-openai:latest
    command: >
      --model meta-llama/Llama-3.1-70B-Instruct
      --tensor-parallel-size 2
      --max-model-len 8192
      --gpu-memory-utilization 0.90
      --max-num-seqs 256
      --enable-prefix-caching
      --disable-log-requests
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2
              capabilities: [gpu]
    ports:
      - "8000:8000"
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Key Serving Optimizations

```
1. Continuous Batching
   - Don't wait for all requests in batch to finish
   - New requests join batch as slots free up
   - Improves throughput 2-5x vs static batching

2. PagedAttention (vLLM)
   - Manages KV cache like virtual memory pages
   - Reduces memory waste from 60-80% to <4%
   - Enables serving longer sequences

3. Prefix Caching
   - Cache KV values for common prompt prefixes
   - System prompts computed once, reused for all requests
   - 2-5x speedup for shared-prefix workloads

4. Speculative Decoding
   - Small draft model generates candidates quickly
   - Large model verifies in parallel (single forward pass)
   - 2-3x speedup with no quality loss
   
5. Quantization
   - FP16 → INT8: ~2x memory reduction, <1% quality loss
   - FP16 → INT4 (AWQ/GPTQ): ~4x memory reduction, 1-3% quality loss
   - Enables larger models on fewer GPUs
```

---

## 11. Scaling Inference

### Horizontal Scaling Architecture

```
                    ┌──────────────┐
                    │ Load Balancer │
                    │   (L7/gRPC)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ vLLM     │ │ vLLM     │ │ vLLM     │
        │ Replica 1│ │ Replica 2│ │ Replica 3│
        │ 2x A100  │ │ 2x A100  │ │ 2x A100  │
        └──────────┘ └──────────┘ └──────────┘
        
Autoscaling triggers:
  - GPU utilization > 80% for 2 minutes → scale up
  - Queue depth > 50 requests → scale up
  - GPU utilization < 30% for 10 minutes → scale down
  - Minimum replicas: 2 (availability)
  - Maximum replicas: 10 (budget)
```

### Quantization Decision Matrix

| Method | Memory Savings | Quality Loss | Speed Gain | Best For |
|--------|---------------|-------------|------------|----------|
| FP16 (baseline) | 0% | 0% | 0% | Maximum quality |
| INT8 (bitsandbytes) | ~50% | <0.5% | ~30% faster | Most production use |
| INT4 GPTQ | ~75% | 1-2% | ~50% faster | Cost-optimized serving |
| INT4 AWQ | ~75% | 0.5-1.5% | ~60% faster | Best INT4 quality |
| FP8 (H100 native) | ~50% | <0.3% | ~40% faster | H100/H200 deployments |

### Batching Strategy

```python
# Optimal batch configuration depends on:
# 1. Input length distribution
# 2. Output length distribution  
# 3. Latency SLA
# 4. GPU memory

# For low-latency applications (chatbot, <2s response):
config = {
    "max_batch_size": 32,
    "max_waiting_time_ms": 50,  # Don't wait long for batch to fill
    "max_sequence_length": 4096,
}

# For throughput applications (batch processing, async):
config = {
    "max_batch_size": 256,
    "max_waiting_time_ms": 500,  # Wait longer to fill larger batches
    "max_sequence_length": 2048,
}

# For mixed workloads:
# Use priority queues - latency-sensitive requests get smaller batches
```

---

## 12. Model Safety Evaluation

### Pre-Deployment Safety Checklist

```yaml
safety_evaluation:
  harmful_content:
    - test: "Does model refuse to generate harmful instructions?"
      method: "Red team with 200+ adversarial prompts"
      threshold: ">99% refusal rate"
    
    - test: "Does model avoid generating CSAM/violence?"
      method: "Automated probing + manual review"
      threshold: "100% refusal rate"
  
  bias_testing:
    - test: "Gender bias in professional recommendations"
      method: "Counterfactual testing (swap gender, compare outputs)"
      threshold: "<5% difference in recommendation quality"
    
    - test: "Racial bias in content moderation"
      method: "Evaluate on diverse dialect samples"
      threshold: "<3% FPR difference across demographics"
  
  hallucination:
    - test: "Factual accuracy on domain-specific questions"
      method: "Compare against verified knowledge base"
      threshold: ">95% factual accuracy"
    
    - test: "Does model say 'I don't know' when appropriate?"
      method: "Test with unanswerable questions"
      threshold: ">80% appropriate uncertainty expression"
  
  prompt_injection:
    - test: "Resistance to system prompt extraction"
      method: "50+ injection attempts"
      threshold: "0% system prompt leakage"
    
    - test: "Resistance to jailbreaking"
      method: "Run standard jailbreak benchmarks"
      threshold: ">95% resistance rate"
```

### Safety Monitoring in Production

```python
class SafetyMonitor:
    def __init__(self):
        self.content_classifier = load_model("safety-classifier")
        self.pii_detector = PIIDetector()
    
    async def check_output(self, response: str, context: dict) -> SafetyResult:
        checks = await asyncio.gather(
            self.check_harmful_content(response),
            self.check_pii_leakage(response, context),
            self.check_hallucination_signals(response),
            self.check_bias_indicators(response),
        )
        
        if any(check.blocked for check in checks):
            await self.alert_safety_team(checks, context)
            return SafetyResult(blocked=True, reason=checks)
        
        return SafetyResult(blocked=False)
```

---

## 13. Model Licensing Guide

### Commercial Use Matrix

| Model | License | Commercial Use | Fine-tuning | Redistribution | Key Restrictions |
|-------|---------|---------------|-------------|----------------|------------------|
| GPT-4o | Proprietary | Yes (API ToS) | Limited (OpenAI API) | No | No competing products from outputs |
| Claude 3.5 | Proprietary | Yes (API ToS) | No | No | Usage policies apply |
| Gemini | Proprietary | Yes (API ToS) | Yes (Vertex AI) | No | Google ToS |
| Llama 3.1 | Llama 3.1 Community | Yes | Yes | Yes | >700M MAU need Meta license |
| Mistral 7B/8x7B | Apache 2.0 | Yes | Yes | Yes | None |
| Mistral Large | Proprietary | Yes (API) | No | No | API terms |
| Qwen 2.5 | Qwen License | Yes (with conditions) | Yes | Yes | Check specific model license |
| Phi-3 | MIT | Yes | Yes | Yes | None |
| DeepSeek V3 | DeepSeek License | Yes (with conditions) | Yes | Yes | Cannot train competing models |

### Key Legal Considerations

1. **Output ownership**: Most API providers grant you ownership of outputs, but check ToS
2. **Training on outputs**: OpenAI ToS prohibits using outputs to train competing models
3. **Data processing**: Ensure DPA is in place for PII (GDPR Article 28)
4. **Indemnification**: Most providers do NOT indemnify you for model outputs
5. **Export controls**: Some models have US export restrictions (check OFAC)

---

## 14. Total Cost of Ownership (TCO)

### TCO Model: Managed API

```
Monthly TCO = Token Costs + Engineering Time + Monitoring + Compliance

Token Costs:
  Input tokens/month × input price +
  Output tokens/month × output price

Engineering Time:
  Integration: 0.1 FTE × $15,000/month = $1,500/month (amortized)
  Prompt engineering: 0.2 FTE × $15,000 = $3,000/month
  Monitoring/alerts: 0.05 FTE × $15,000 = $750/month

Monitoring:
  Eval pipeline: $200/month (compute)
  Logging/observability: $100-500/month

Compliance:
  DPA review: $500 (one-time, amortized)
  Security review: $2,000/quarter (amortized = $667/month)

Example: 10M tokens/day on GPT-4o
  Tokens: 300M/month × $6.25/1M = $1,875/month
  Engineering: $5,250/month
  Monitoring: $350/month
  Compliance: $700/month
  
  TOTAL: ~$8,175/month
```

### TCO Model: Self-Hosted

```
Monthly TCO = Infrastructure + Engineering + Software + Overhead

Infrastructure:
  GPU instances: 2x A100 80GB (p4d.24xlarge shared) = $14,400/month
  Or reserved 1yr: $8,640/month
  Storage (model weights + logs): $200/month
  Networking: $100/month

Engineering:
  MLOps engineer: 0.5 FTE × $18,000 = $9,000/month
  On-call: 0.1 FTE × $18,000 = $1,800/month
  Model updates/evaluation: 0.2 FTE × $18,000 = $3,600/month

Software:
  Monitoring (Prometheus/Grafana): $100/month
  Vector DB (if needed): $500/month
  CI/CD for model deployment: included in infra

Overhead:
  GPU idle time (30%): $2,592/month (reserved pricing)
  Redundancy (2x for HA): Double infra cost

Example: Llama 3.1 70B serving 10M tokens/day
  Infrastructure (HA): $17,280/month (reserved, 2 replicas)
  Engineering: $14,400/month
  Software: $600/month
  
  TOTAL: ~$32,280/month
  
  Break-even vs API: Only makes sense at >50M tokens/day
  OR when data privacy requirements make API impossible
```

### TCO Summary by Scale

| Monthly Tokens | Best Strategy | Estimated Monthly Cost |
|---------------|---------------|----------------------|
| < 1M | Managed API (mid-tier) | $50-200 |
| 1M - 10M | Managed API (frontier) | $200-2,000 |
| 10M - 100M | Managed API OR hybrid | $2,000-15,000 |
| 100M - 1B | Self-hosted (if team exists) | $15,000-50,000 |
| > 1B | Self-hosted (mandatory for cost) | $50,000+ |

---

## Summary: The Model Selection Playbook

```
1. Define requirements (quality, latency, cost, compliance)
2. Eliminate options based on hard constraints
3. Build custom eval set (minimum 200 samples)
4. Evaluate 3-4 candidate models
5. Choose winner based on weighted decision matrix
6. Implement tiering if volume justifies it
7. Pin model versions, set deprecation alerts
8. Monitor quality continuously (weekly eval runs)
9. Plan migration path before you need it
10. Re-evaluate quarterly (model landscape changes fast)
```
