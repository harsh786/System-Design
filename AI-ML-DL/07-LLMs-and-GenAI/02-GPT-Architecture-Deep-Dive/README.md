# GPT Architecture Deep Dive

## Autoregressive Language Modeling

The core idea behind GPT: predict the next token given all previous tokens.

```
P(token_n | token_1, token_2, ..., token_{n-1})

"The cat sat on the" → P(next_token)
                        "mat": 0.15
                        "floor": 0.08
                        "chair": 0.06
                        "dog": 0.001
                        ...
```

Training objective: maximize the probability of the actual next token across the entire training corpus. This is called **Causal Language Modeling (CLM)**.

```
Loss = -∑ log P(token_t | token_1, ..., token_{t-1})
```

## GPT Architecture Layer by Layer

```
┌─────────────────────────────────────────────┐
│              LM Head (Linear)                │  → Vocab-sized logits
│         [d_model → vocab_size]               │
├─────────────────────────────────────────────┤
│              Layer Norm                       │
├─────────────────────────────────────────────┤
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │      Transformer Block × N           │    │  N = 96 for GPT-3
│  │  ┌─────────────────────────────┐    │    │
│  │  │  Layer Norm                  │    │    │
│  │  │  Masked Multi-Head Attention │    │    │
│  │  │  Residual Connection         │    │    │
│  │  │  Layer Norm                  │    │    │
│  │  │  Feed-Forward Network (MLP)  │    │    │
│  │  │  Residual Connection         │    │    │
│  │  └─────────────────────────────┘    │    │
│  └─────────────────────────────────────┘    │
│                                              │
├─────────────────────────────────────────────┤
│     Token Embeddings + Positional Embeddings │
├─────────────────────────────────────────────┤
│              Input Token IDs                 │
└─────────────────────────────────────────────┘
```

### Detailed Forward Pass

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class GPTConfig:
    vocab_size: int = 50257
    n_layers: int = 12
    n_heads: int = 12
    d_model: int = 768
    d_ff: int = 3072      # 4 × d_model
    max_seq_len: int = 1024
    dropout: float = 0.1

class MultiHeadAttention(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.n_heads = config.n_heads
        self.d_model = config.d_model
        self.d_k = config.d_model // config.n_heads
        
        self.W_q = nn.Linear(config.d_model, config.d_model)
        self.W_k = nn.Linear(config.d_model, config.d_model)
        self.W_v = nn.Linear(config.d_model, config.d_model)
        self.W_o = nn.Linear(config.d_model, config.d_model)
    
    def forward(self, x):
        B, T, C = x.shape
        
        # Project to Q, K, V
        q = self.W_q(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        k = self.W_k(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        v = self.W_v(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        
        # Scaled dot-product attention with causal mask
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.d_k)
        
        # Causal mask: prevent attending to future tokens
        mask = torch.triu(torch.ones(T, T), diagonal=1).bool()
        scores.masked_fill_(mask, float('-inf'))
        
        attn = F.softmax(scores, dim=-1)
        out = attn @ v
        
        # Concatenate heads and project
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.W_o(out)

class TransformerBlock(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model)
        self.attn = MultiHeadAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model)
        self.mlp = nn.Sequential(
            nn.Linear(config.d_model, config.d_ff),
            nn.GELU(),
            nn.Linear(config.d_ff, config.d_model),
            nn.Dropout(config.dropout),
        )
    
    def forward(self, x):
        x = x + self.attn(self.ln1(x))   # Pre-norm + residual
        x = x + self.mlp(self.ln2(x))    # Pre-norm + residual
        return x

class GPT(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.token_emb = nn.Embedding(config.vocab_size, config.d_model)
        self.pos_emb = nn.Embedding(config.max_seq_len, config.d_model)
        self.blocks = nn.ModuleList([TransformerBlock(config) for _ in range(config.n_layers)])
        self.ln_f = nn.LayerNorm(config.d_model)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
    
    def forward(self, token_ids):
        B, T = token_ids.shape
        
        # Embeddings
        tok_emb = self.token_emb(token_ids)
        pos_emb = self.pos_emb(torch.arange(T, device=token_ids.device))
        x = tok_emb + pos_emb
        
        # Transformer blocks
        for block in self.blocks:
            x = block(x)
        
        # Final layer norm + project to vocabulary
        x = self.ln_f(x)
        logits = self.lm_head(x)  # [B, T, vocab_size]
        
        return logits
```

## Decoder-Only vs Encoder-Only vs Encoder-Decoder

```
┌─────────────────────────────────────────────────────────────────────┐
│ Architecture        │ Attention    │ Models          │ Best For      │
├─────────────────────┼──────────────┼─────────────────┼───────────────┤
│ Decoder-only        │ Causal       │ GPT, Llama,     │ Generation,   │
│ (autoregressive)    │ (left→right) │ Claude, Mistral │ chat, code    │
├─────────────────────┼──────────────┼─────────────────┼───────────────┤
│ Encoder-only        │ Bidirectional│ BERT, RoBERTa,  │ Classification│
│                     │ (full)       │ DeBERTa         │ NER, search   │
├─────────────────────┼──────────────┼─────────────────┼───────────────┤
│ Encoder-Decoder     │ Both         │ T5, BART,       │ Translation,  │
│                     │              │ Flan-T5         │ summarization │
└─────────────────────┴──────────────┴─────────────────┴───────────────┘
```

**Why decoder-only won**: With sufficient scale, autoregressive models can do everything. The "predict next token" objective is universal — any task can be framed as text generation.

## Scaling Laws

### Kaplan et al. (2020) - OpenAI

Found that model performance (loss) follows power laws with respect to:
- **N** (number of parameters)
- **D** (dataset size)
- **C** (compute budget)

```
L(N) ∝ N^{-0.076}     (loss scales with parameters)
L(D) ∝ D^{-0.095}     (loss scales with data)
L(C) ∝ C^{-0.050}     (loss scales with compute)
```

Key finding: It's better to train a **larger model for fewer steps** than a smaller model for more steps.

### Chinchilla (2022) - DeepMind

Corrected the scaling laws. Found that most models were **undertrained** — not enough data for their size.

```
Optimal ratio: ~20 tokens per parameter

Model Params    Optimal Training Tokens
──────────────────────────────────────
1B              20B tokens
7B              140B tokens
70B             1.4T tokens
175B            3.5T tokens

Chinchilla (70B params, 1.4T tokens) matched
Gopher (280B params, 300B tokens) — 4x smaller!
```

**Impact**: Shifted industry toward smaller, better-trained models. Llama 2 7B trained on 2T tokens (much more than "optimal") — overtrained for inference efficiency.

## Training Data and Curation

```
Typical pre-training data mix:
┌─────────────────────────────────────────┐
│ Source            │ % │ Quality         │
├───────────────────┼───┼─────────────────┤
│ Web crawl (C4)   │40%│ Filtered HTML   │
│ Books            │15%│ High quality    │
│ Wikipedia        │ 5%│ Factual         │
│ Code (GitHub)    │15%│ Structured      │
│ Academic papers  │10%│ Technical       │
│ Social media     │ 5%│ Conversational  │
│ Other            │10%│ Mixed           │
└───────────────────┴───┴─────────────────┘

Key data quality steps:
1. Deduplication (exact + fuzzy)
2. Quality filtering (perplexity, heuristics)
3. Toxic content removal
4. PII removal
5. Domain balancing (upsample underrepresented)
```

## From Base Model to Chat Model

```
┌──────────┐     ┌───────────────────┐     ┌──────────┐     ┌──────────┐
│Pre-train │ →   │Supervised Fine-   │ →   │  RLHF /  │ →   │  Chat    │
│(base     │     │Tuning (SFT)       │     │  DPO     │     │  Model   │
│model)    │     │(instruction data) │     │          │     │          │
└──────────┘     └───────────────────┘     └──────────┘     └──────────┘
   Llama 2          Llama 2-Chat               ↑
   base             (follows instructions)     Human preferences
```

### Supervised Fine-Tuning (SFT)

Train on high-quality (instruction, response) pairs:

```json
{"instruction": "Explain quantum computing to a 5-year-old",
 "response": "Imagine you have a magic coin that can be heads AND tails at the same time..."}
```

Typically 10K-100K examples, curated by humans.

## RLHF (Reinforcement Learning from Human Feedback)

The breakthrough that made ChatGPT possible.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RLHF Pipeline                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: Collect Comparison Data                                     │
│  ┌─────────────────────────────────────────┐                        │
│  │ Prompt: "Explain gravity"                │                        │
│  │ Response A: [detailed, accurate]         │  Human: A > B          │
│  │ Response B: [vague, incorrect]           │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                      │
│  Step 2: Train Reward Model (RM)                                     │
│  ┌─────────────────────────────────────────┐                        │
│  │ Input: (prompt, response) → Score        │                        │
│  │ Trained on: human preference pairs       │                        │
│  │ Output: scalar reward                    │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                      │
│  Step 3: Optimize Policy with PPO                                    │
│  ┌─────────────────────────────────────────┐                        │
│  │ Generate response → Get reward score     │                        │
│  │ Update model to maximize reward          │                        │
│  │ KL penalty to stay close to SFT model    │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Simplified RLHF training loop
for batch in dataloader:
    prompts = batch["prompts"]
    
    # Generate responses from current policy
    responses = policy_model.generate(prompts)
    
    # Score with reward model
    rewards = reward_model(prompts, responses)
    
    # KL divergence penalty (don't drift too far from SFT)
    kl_penalty = compute_kl(policy_model, reference_model, prompts, responses)
    
    # Final reward
    final_reward = rewards - beta * kl_penalty
    
    # PPO update
    ppo_update(policy_model, prompts, responses, final_reward)
```

## DPO (Direct Preference Optimization)

Simpler alternative to RLHF — no reward model, no RL training.

```
Key insight: The optimal RLHF policy has a closed-form solution.
We can directly optimize the policy using preference pairs.

Loss_DPO = -log σ(β × (log π(y_w|x)/π_ref(y_w|x) - log π(y_l|x)/π_ref(y_l|x)))

Where:
  y_w = preferred response (winner)
  y_l = dispreferred response (loser)
  π = current policy
  π_ref = reference (SFT) policy
  β = temperature parameter
```

**DPO vs RLHF:**
| | RLHF | DPO |
|---|---|---|
| Complexity | High (RM + PPO) | Low (single loss) |
| Stability | Tricky to tune | More stable |
| Performance | Slightly better at scale | Comparable |
| Used by | ChatGPT, Claude | Llama 2, Zephyr |

## Constitutional AI (Anthropic)

```
Instead of human feedback for every response:
1. Generate response
2. Ask model to critique its own response against principles
3. Ask model to revise based on critique
4. Use revised responses as training data

Principles (constitution):
- "Be helpful, harmless, and honest"
- "Don't help with illegal activities"
- "Acknowledge uncertainty"
```

## Context Windows and Attention Complexity

Standard attention is O(n²) in sequence length — the fundamental bottleneck.

```
Sequence Length    Memory (attention matrix)    Time
───────────────────────────────────────────────────
512               1 MB                          Fast
2048              16 MB                         OK
8192              256 MB                        Expensive
32768             4 GB                          Very expensive
131072            64 GB                         Extreme
1000000           ~4 TB                         Impossible (naive)
```

### Flash Attention

Doesn't change the math — same exact attention — but uses GPU memory hierarchy efficiently.

```
Standard attention:
  1. Compute full S = QK^T (n×n matrix in HBM — slow memory)
  2. Compute softmax(S)
  3. Compute output = softmax(S) × V

Flash Attention:
  1. Tile Q, K, V into blocks that fit in SRAM (fast memory)
  2. Compute attention block by block (never materialize full n×n)
  3. Use online softmax trick to accumulate correctly
  
Result: 2-4x faster, O(n) memory instead of O(n²)
```

### Grouped Query Attention (GQA)

```
Multi-Head Attention (MHA):    Every head has its own K, V
                               Heads: Q₁K₁V₁, Q₂K₂V₂, Q₃K₃V₃, Q₄K₄V₄

Grouped Query Attention (GQA): Groups of heads share K, V
                               Groups: Q₁Q₂→K₁V₁, Q₃Q₄→K₂V₂

Multi-Query Attention (MQA):   ALL heads share one K, V
                               Q₁Q₂Q₃Q₄ → K₁V₁

GQA = sweet spot between quality (MHA) and speed (MQA)
Used by: Llama 2 70B, Mistral, GPT-4
```

## KV Cache and Inference Optimization

During autoregressive generation, each new token needs to attend to ALL previous tokens. Without caching, we'd recompute K, V for all previous positions every step.

```
Without KV Cache (wasteful):
  Step 1: Compute K,V for [token1]              → generate token2
  Step 2: Compute K,V for [token1, token2]      → generate token3
  Step 3: Compute K,V for [token1, token2, token3] → generate token4
  ... redundant computation!

With KV Cache:
  Step 1: Compute K₁,V₁                        → cache, generate token2
  Step 2: Compute K₂,V₂, use cached K₁,V₁     → cache, generate token3
  Step 3: Compute K₃,V₃, use cached K₁₂,V₁₂   → cache, generate token4
  ... only compute new token's K,V each step!
```

**KV Cache memory** = 2 × n_layers × n_heads × d_head × seq_len × batch_size × dtype_bytes

For Llama 2 70B with 4K context: ~2GB per request just for KV cache.

## Model Parallelism

Training models with hundreds of billions of parameters requires distributing across many GPUs.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Parallelism Strategy         │ What's split         │ Used When     │
├──────────────────────────────┼──────────────────────┼───────────────┤
│ Data Parallel (DP)           │ Batch across GPUs    │ Always        │
│ Tensor Parallel (TP)         │ Single layer across  │ Large layers  │
│                              │ GPUs (column/row)    │               │
│ Pipeline Parallel (PP)       │ Layers across GPUs   │ Many layers   │
│ Expert Parallel (EP)         │ Experts across GPUs  │ MoE models    │
│ Sequence Parallel (SP)       │ Sequence dimension   │ Long contexts │
│ ZeRO (DeepSpeed)            │ Optimizer states,    │ Memory savings │
│                              │ gradients, params    │               │
└──────────────────────────────┴──────────────────────┴───────────────┘
```

### Tensor Parallelism Example

```
GPU 0:                         GPU 1:
┌──────────────┐              ┌──────────────┐
│ W_q[:, :d/2] │              │ W_q[:, d/2:] │
│ W_k[:, :d/2] │              │ W_k[:, d/2:] │
│ W_v[:, :d/2] │              │ W_v[:, d/2:] │
└──────────────┘              └──────────────┘
       │                             │
       └──────── AllReduce ──────────┘
                     │
              Combined output
```

## Mixture of Experts (MoE)

How GPT-4 and Mixtral achieve massive capacity with efficient inference.

```
┌─────────────────────────────────────────────────────────────┐
│                    MoE Transformer Block                      │
│                                                              │
│  Input → Attention → ┌─────────────────────────────┐        │
│                       │         Router              │        │
│                       │   (selects top-K experts)    │        │
│                       └──────┬──────┬──────┬────────┘        │
│                              │      │      │                 │
│                       ┌──────┐┌─────┐┌─────┐┌─────┐        │
│                       │Expert││Exp. ││Exp. ││Exp. │ ...     │
│                       │  1   ││  2  ││  3  ││  4  │         │
│                       └──┬───┘└──┬──┘└──┬──┘└──┬──┘        │
│                          │       │      │      │            │
│                       ┌──┴───────┴──────┴──────┴──┐        │
│                       │  Weighted sum (top-K only) │        │
│                       └───────────────────────────┘        │
│                              │                              │
│                           Output                            │
└─────────────────────────────────────────────────────────────┘
```

```
Mixtral 8x7B:
- 8 experts, each ~7B parameters
- Router selects top-2 experts per token
- Total params: ~47B
- Active params per token: ~13B (only 2 experts fire)
- Inference cost ≈ 13B model, knowledge of 47B model

GPT-4 (rumored):
- ~16 experts, each ~110B
- Top-2 routing
- Total params: ~1.8T
- Active params: ~220B per token
```

```python
class MoELayer(nn.Module):
    def __init__(self, d_model, n_experts, top_k, d_ff):
        super().__init__()
        self.router = nn.Linear(d_model, n_experts)
        self.experts = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, d_ff),
                nn.GELU(),
                nn.Linear(d_ff, d_model)
            ) for _ in range(n_experts)
        ])
        self.top_k = top_k
    
    def forward(self, x):
        # x: [batch, seq_len, d_model]
        router_logits = self.router(x)  # [batch, seq, n_experts]
        weights, indices = torch.topk(router_logits, self.top_k, dim=-1)
        weights = F.softmax(weights, dim=-1)
        
        # Dispatch tokens to experts and combine
        output = torch.zeros_like(x)
        for k in range(self.top_k):
            expert_idx = indices[..., k]  # which expert for each token
            expert_weight = weights[..., k:k+1]
            for e in range(len(self.experts)):
                mask = (expert_idx == e)
                if mask.any():
                    expert_input = x[mask]
                    expert_output = self.experts[e](expert_input)
                    output[mask] += expert_weight[mask] * expert_output
        
        return output
```

## Training Pipeline (Sequence Diagram)

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Data    │  │Pre-train │  │   SFT    │  │   RLHF   │  │  Deploy  │
│Collection│→ │(months)  │→ │(days)    │→ │(weeks)   │→ │& Monitor │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘

Data Collection:        Pre-training:          SFT:
- Web crawl             - Causal LM loss       - Instruction pairs
- Books, papers         - 1000s of GPUs        - 10K-100K examples
- Code repos            - Weeks to months      - Chat format
- Quality filtering     - $1M-$100M cost       - Domain data

RLHF/DPO:             Deployment:
- Human comparisons    - Quantization
- Reward model         - Serving infra
- PPO/DPO training     - Safety filters
- Red-teaming          - Monitoring
```

## Interview Questions

1. **Why is GPT decoder-only? Why not encoder-decoder?**
   - Simpler architecture, scales better, and with sufficient scale the causal model can do any task.

2. **Explain the causal mask in self-attention.**
   - Upper-triangular matrix of -inf prevents tokens from attending to future positions, enabling autoregressive generation.

3. **What are scaling laws and how do they guide training decisions?**
   - Power-law relationships between compute/data/params and loss. Help decide optimal model size for a given compute budget.

4. **How does Flash Attention achieve speedup without changing the math?**
   - Tiles computation to use fast SRAM instead of slow HBM, avoids materializing the full N×N attention matrix.

5. **Explain Mixture of Experts — why is it efficient?**
   - Only a subset of experts process each token, so inference cost equals a smaller model while total knowledge capacity is much larger.

6. **What is the KV cache and why does it matter for inference?**
   - Stores previously computed key/value tensors to avoid redundant computation during autoregressive generation.

7. **What's the difference between RLHF and DPO?**
   - RLHF trains a separate reward model + uses RL (PPO). DPO directly optimizes the policy on preference pairs with a simpler loss.

8. **Why is GQA used instead of standard multi-head attention in modern models?**
   - Reduces KV cache size by sharing keys/values across head groups, improving inference throughput with minimal quality loss.

9. **How does the router in MoE decide which experts to use?**
   - A learned linear layer produces logits over experts; top-K are selected and their outputs weighted by softmax probabilities.

10. **What is catastrophic forgetting in the context of fine-tuning LLMs?**
    - The model loses pre-trained knowledge when fine-tuned on narrow data. Mitigated by low learning rates, LoRA, or mixing pre-training data.

## Exercises

### Exercise 1: Build a Mini-GPT
Implement a small GPT (2 layers, 4 heads, d_model=128) and train it on Shakespeare text. Generate samples.

### Exercise 2: Attention Visualization
Implement attention and visualize the attention patterns for different input sequences. Observe how causal masking works.

### Exercise 3: Scaling Law Estimation
Given compute budget C, calculate the optimal model size and data size using Chinchilla scaling laws.

### Exercise 4: KV Cache Implementation
Implement generation with and without KV cache. Measure the speedup for sequences of different lengths.

## Common Pitfalls

1. **Confusing parameters with active parameters in MoE** — Mixtral 8x7B ≠ 56B active params
2. **Ignoring the quadratic attention cost** — doubling context length = 4x attention cost
3. **Thinking RLHF makes models "truthful"** — it makes them appear helpful/harmless, not necessarily factual
4. **Assuming bigger = better** — a well-trained 7B can beat a poorly-trained 70B (Chinchilla)
5. **Forgetting KV cache memory** — limits batch size during serving, often the real bottleneck
