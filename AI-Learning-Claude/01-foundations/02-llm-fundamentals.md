# 02 - LLM Fundamentals

## What is a Large Language Model?

### Explaining to a Smart 10-Year-Old

Imagine you've read every book in the world's biggest library — every novel, every textbook, every Wikipedia article, every Reddit comment. Now someone gives you the start of a sentence:

> "The capital of France is ___"

You'd guess "Paris" because you've seen that pattern thousands of times. That's essentially what an LLM does — it's a **very sophisticated pattern-completion machine** that has "read" most of the internet.

But here's the key: it doesn't *understand* Paris is a city. It knows that statistically, "Paris" is the most likely next word. This distinction matters enormously for architecture.

### The Formal Definition

A Large Language Model is a neural network with billions of parameters, trained on massive text datasets, that predicts the next token in a sequence. "Large" refers to parameter count (7B to 1T+) and training data (terabytes of text).

## How LLMs Work: The Three Phases

```mermaid
graph LR
    subgraph "Phase 1: Training"
        D[Internet-scale Data<br/>Books, Web, Code] --> T[Train Neural Network<br/>Weeks on 1000s of GPUs]
        T --> W[Weights / Parameters<br/>Billions of numbers]
    end

    subgraph "Phase 2: Alignment"
        W --> RLHF[RLHF / DPO<br/>Human feedback]
        RLHF --> AW[Aligned Weights<br/>Helpful, harmless, honest]
    end

    subgraph "Phase 3: Inference"
        AW --> API[API / Server]
        P[Your Prompt] --> API
        API --> R[Response<br/>Token by token]
    end
```

### Phase 1: Pre-Training
- Feed terabytes of text to the model
- The model learns to predict the next word
- Costs $10M-$100M+ in compute
- Takes weeks on thousands of GPUs
- Result: **base model** (knows language, not how to be helpful)

### Phase 2: Alignment (RLHF / DPO)
- Human raters rank model outputs
- Model learns to be helpful, harmless, and honest
- Transforms a text-completion engine into an assistant
- This is why ChatGPT answers questions instead of just completing text

### Phase 3: Inference (What You Use)
- Send a prompt, get a response
- Model generates tokens one at a time (auto-regressive)
- Each token takes ~10-50ms
- This is where your API costs come from

## The Transformer Architecture (Simplified)

The transformer is the architecture behind all modern LLMs. Published in 2017 as "Attention Is All You Need."

Think of it as an assembly line with three key stations:

### 1. Tokenizer (The Translator)
Converts text into numbers the model understands.
```
"Hello world" → [15496, 995]
```

### 2. Embedding Layer (The Meaning Mapper)
Converts each token into a rich vector that captures meaning.
```
[15496] → [0.23, -0.45, 0.12, ..., 0.67]  (768-4096 dimensions)
```
Words with similar meanings have similar vectors. "King" and "Queen" are close; "King" and "Bicycle" are far.

### 3. Attention Layers (The Relationship Builder)
This is the secret sauce. Multiple layers of attention blocks that figure out which words relate to which.

## Attention: The "Paying Attention in Class" Analogy

Imagine you're in a classroom reading this sentence:

> "The **cat** sat on the **mat** because **it** was tired."

What does "it" refer to? The cat or the mat? You know it's the cat because you **paid attention** to the right words.

The attention mechanism does exactly this — for every word, it computes how much to "look at" every other word:

```
"it" pays attention to:
  "cat"     → 0.72  (high - "it" probably means the cat)
  "sat"     → 0.08
  "mat"     → 0.15
  "tired"   → 0.05
```

**Multi-head attention** means the model has multiple "students" paying attention simultaneously — one might focus on grammar, another on meaning, another on sentiment. GPT-4 has 96+ attention heads.

## Pre-Training vs Fine-Tuning vs In-Context Learning

| Method | What It Does | Cost | When to Use |
|---|---|---|---|
| **Pre-training** | Train from scratch | $10M-$100M | Never (you're not OpenAI) |
| **Fine-tuning** | Adapt existing model to your data | $100-$10K | Specific format/style needs |
| **In-context learning** | Put examples in the prompt | $0 (just tokens) | First approach, always try this first |

### Decision Flow

```mermaid
graph TD
    A[Need AI capability] --> B{Can prompt engineering solve it?}
    B -->|Yes| C[Use in-context learning<br/>Few-shot prompting]
    B -->|No| D{Need specific format/style<br/>consistently?}
    D -->|Yes| E[Fine-tune a model]
    D -->|No| F{Need domain knowledge<br/>model doesn't have?}
    F -->|Yes| G[Use RAG<br/>Retrieval Augmented Generation]
    F -->|No| H[Re-evaluate requirements]
```

**Architect's Rule**: Always start with prompting. Only fine-tune when prompting demonstrably fails and you have the data to prove it.

## Major Model Families

### Comparison Table (Mid-2025)

| Model Family | Provider | Top Model | Parameters | Context | Strengths |
|---|---|---|---|---|---|
| **GPT** | OpenAI | GPT-4o | Undisclosed | 128K | Reasoning, coding, multimodal |
| **Claude** | Anthropic | Claude 4 Sonnet | Undisclosed | 200K | Long context, safety, analysis |
| **Gemini** | Google | Gemini 2.5 Pro | Undisclosed | 1M | Multimodal, long context |
| **Llama** | Meta | Llama 4 | 405B (largest) | 128K | Open-source, self-hosting |
| **Mistral** | Mistral AI | Mistral Large | Undisclosed | 128K | Efficient, multilingual |
| **DeepSeek** | DeepSeek | DeepSeek-V3 | 685B (MoE) | 128K | Cost-efficient, open weights |

### Open-Source vs Closed-Source

| Factor | Open Source (Llama, Mistral) | Closed Source (GPT, Claude) |
|---|---|---|
| **Cost at scale** | Lower (self-host) | Higher (per-token) |
| **Initial setup** | Complex (GPUs, infra) | Simple (API key) |
| **Data privacy** | Full control | Data leaves your network |
| **Quality (top-tier)** | Slightly behind | Leading edge |
| **Customization** | Full (fine-tune, modify) | Limited (prompts, fine-tune API) |
| **Latency control** | Full control | Depends on provider |
| **Compliance** | Easier (on-premise) | Harder (third-party) |
| **Maintenance** | You own it | Provider handles it |

## When to Use Which Model

```mermaid
graph TD
    A[What's your task?] --> B{Complex reasoning<br/>or coding?}
    B -->|Yes| C[GPT-4o / Claude Sonnet / Gemini 2.5 Pro]
    B -->|No| D{Simple classification<br/>or extraction?}
    D -->|Yes| E[GPT-4o-mini / Claude Haiku / Gemini Flash]
    D -->|No| F{Data privacy<br/>critical?}
    F -->|Yes| G[Llama / Mistral<br/>Self-hosted]
    F -->|No| H{Long document<br/>processing?}
    H -->|Yes| I[Gemini 2.5 Pro / Claude Sonnet<br/>Large context]
    H -->|No| J[GPT-4o-mini<br/>Best cost/quality ratio]
```

### The Tiered Model Strategy

Production systems should use **multiple models** — this is a key architectural pattern:

| Tier | Model Class | Use Case | Cost |
|---|---|---|---|
| **Tier 1** | GPT-4o / Claude Sonnet | Complex reasoning, customer-facing | $$$ |
| **Tier 2** | GPT-4o-mini / Haiku | Classification, routing, simple tasks | $ |
| **Tier 3** | Embedding models | Search, similarity, clustering | ¢ |
| **Tier 4** | Self-hosted (Llama) | High-volume, privacy-sensitive | Fixed cost |

## Why This Matters for an Architect

1. **Model selection is an architectural decision** — it affects cost, latency, quality, and privacy
2. **No single model fits all tasks** — design for multi-model from day one
3. **Understand inference costs** — they scale linearly with usage (no "free" scaling)
4. **In-context learning first** — fine-tuning is expensive and hard to maintain
5. **Open vs closed is a spectrum** — most systems use both
6. **Models improve rapidly** — your architecture must be model-agnostic

## Key Takeaways

- LLMs are pattern-completion machines, not reasoning engines (though they can approximate reasoning)
- The transformer's attention mechanism is what makes context-aware generation possible
- Always start with prompting, graduate to fine-tuning only with evidence
- Use tiered model strategies: expensive models for hard tasks, cheap models for easy ones
- Build model-agnostic: today's best model is tomorrow's second-best

---
## Anti-Patterns
1. **Treating LLMs as deterministic** - Same input doesn't guarantee same output
2. **Ignoring token limits** - Not planning for context overflow
3. **Temperature = 0 means exact** - It's MORE deterministic, not perfectly deterministic
4. **One model for everything** - Using GPT-4 for tasks a 7B model handles fine
5. **No fallback plan** - What happens when OpenAI is down?
6. **Ignoring model updates** - GPT-4 behavior changes between versions silently

## Trade-Offs
| Decision | Tradeoff | Staff Guidance |
|----------|----------|---------------|
| Model size | Quality vs cost/latency | Start with smallest model that meets quality bar |
| Temperature | Creativity vs consistency | 0 for classification, 0.7 for creative, test your sweet spot |
| Max tokens | Completeness vs cost | Set to expected output + 20% buffer, never unlimited |
| Streaming | UX vs complexity | Always stream for user-facing, batch for backend |

## Real-World Examples
- **GitHub Copilot** uses specialized smaller models for code completion (latency-critical) and larger models for chat
- **ChatGPT** uses different model sizes for different subscription tiers
- **Perplexity** chains a fast model for query understanding with a powerful model for synthesis

---

## Model Selection Decision Framework

Choosing the right model is one of the highest-impact architectural decisions. Use this framework:

```mermaid
graph TD
    A[Define Requirements] --> B{Data Privacy?}
    B -->|Must stay on-prem| C[Open Source: Llama 4 / Mistral]
    B -->|Cloud OK| D{Quality Requirements?}
    D -->|Frontier needed| E{Budget?}
    D -->|Good enough is fine| F[GPT-4o-mini / Gemini Flash / Haiku]
    E -->|High budget| G[Claude Sonnet / GPT-4o / Gemini 2.5 Pro]
    E -->|Cost-sensitive| H[DeepSeek-V3 / Llama 4 70B]
    G --> I{Primary Task?}
    I -->|Coding| J[Claude Sonnet 4 > GPT-4o]
    I -->|Analysis/Long docs| K[Gemini 2.5 Pro > Claude Sonnet]
    I -->|General reasoning| L[GPT-4o ≈ Claude Sonnet]
    I -->|Multimodal| M[Gemini 2.5 Pro > GPT-4o]
```

### Model Capability Comparison (Mid-2025)

| Capability | GPT-4o | Claude Sonnet 4 | Gemini 2.5 Pro | Llama 4 405B | DeepSeek-V3 |
|-----------|--------|-----------------|----------------|--------------|-------------|
| **Code generation** | ★★★★☆ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| **Reasoning** | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★☆ |
| **Long document analysis** | ★★★★☆ | ★★★★★ | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Instruction following** | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| **Multilingual** | ★★★★☆ | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★★★ |
| **Safety/Refusals** | Medium | High | Medium | Low | Low |
| **Multimodal (vision)** | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★☆☆ |
| **Structured output** | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★★☆ |
| **Max context** | 128K | 200K | 1M | 128K | 128K |
| **Latency (TTFT)** | Fast | Medium | Medium | Self-host dependent | Fast |

### Cost-Per-Token Economics (Mid-2025)

| Model | Input $/1M | Output $/1M | Cost for 1K req/day (avg 5K in + 1K out) | Monthly Cost |
|-------|-----------|------------|------------------------------------------|-------------|
| GPT-4o | $2.50 | $10.00 | $22.50/day | **$675** |
| Claude Sonnet 4 | $3.00 | $15.00 | $30.00/day | **$900** |
| Gemini 2.5 Pro | $1.25 | $10.00 | $16.25/day | **$488** |
| GPT-4o-mini | $0.15 | $0.60 | $1.35/day | **$41** |
| Gemini 2.0 Flash | $0.10 | $0.40 | $0.90/day | **$27** |
| Claude Haiku 3.5 | $0.80 | $4.00 | $8.00/day | **$240** |
| Llama 4 70B (self-hosted) | ~$0.10 | ~$0.10 | ~$0.60/day | **$18** + infra |
| DeepSeek-V3 (API) | $0.27 | $1.10 | $2.45/day | **$74** |

### When to Use Which Model Family

| Scenario | Recommended Model | Why |
|----------|------------------|-----|
| High-volume customer support chatbot | GPT-4o-mini or Gemini Flash | Cost-effective, good enough quality |
| Legal document analysis | Claude Sonnet 4 | Best at long-form analysis, careful reasoning |
| Code assistant (IDE integration) | Claude Sonnet 4 or GPT-4o | Top-tier code quality, fast |
| Processing 500-page documents | Gemini 2.5 Pro | 1M context window handles full documents |
| Regulated industry (healthcare, finance) | Llama 4 self-hosted | Data stays on-prem, full audit trail |
| Multilingual customer-facing product | Gemini 2.5 Pro or DeepSeek-V3 | Best multilingual capabilities |
| Content generation (marketing) | GPT-4o | Creative, good style control |
| Simple classification/routing | GPT-4o-mini | Cheapest capable model, <100ms |
| Research prototype/experimentation | DeepSeek-V3 | Near-frontier quality at budget price |

### Staff Decision: When to Switch Models

Trigger a model evaluation when:
1. **Cost exceeds budget by 30%+** — time to evaluate cheaper alternatives
2. **New model release** — always benchmark against your eval suite within 2 weeks
3. **Quality metrics dropping** — provider may have silently updated the model
4. **New capability needed** — e.g., vision, longer context, better structured output
5. **Latency SLA violations** — may need a faster/smaller model

**Never switch models without running your eval suite.** "The new model seems better" is not evidence.

### Model Evaluation Template

When evaluating a new model for your use case, test across these dimensions:

| Dimension | How to Test | Minimum Sample |
|-----------|------------|:--------------:|
| Accuracy on your task | Run eval dataset | 100+ examples |
| Output format compliance | Parse success rate | 200+ outputs |
| Latency (p50, p95, p99) | Load test | 1,000+ requests |
| Cost at projected volume | Calculate from pricing | Spreadsheet |
| Edge case handling | Adversarial test set | 50+ examples |
| Regression vs current model | Side-by-side comparison | 100+ examples |

**Staff habit:** Maintain a model evaluation scorecard that lets you compare any new model against your current production model in under 4 hours. The teams that do this ship model upgrades confidently; the teams that don't are stuck on old models out of fear.
