# Transformers and Attention

## 1. The Revolution: "Attention Is All You Need" (Vaswani et al., 2017)

Key insight: Discard recurrence entirely. Use only attention to capture dependencies regardless of distance.

### Why Transformers Won

| Aspect | RNN | Transformer |
|--------|-----|-------------|
| Parallelization | Sequential (O(T)) | Fully parallel |
| Long-range deps | Degrades with distance | Constant path length |
| Training speed | Slow | Fast (GPU-friendly) |
| Scalability | Plateaus | Scales with compute |

## 2. Self-Attention Mechanism (Complete Math)

### Intuition
Each token "attends" to every other token in the sequence to compute a contextualized representation.

### Step-by-Step Computation

Given input X ∈ ℝⁿˣᵈ (n tokens, d dimensions):

```
Step 1: Project to Q, K, V
    Q = X · W_Q    [n × d_k]   (Queries: "what am I looking for?")
    K = X · W_K    [n × d_k]   (Keys: "what do I contain?")
    V = X · W_V    [n × d_v]   (Values: "what do I output?")

Step 2: Compute attention scores
    Scores = Q · Kᵀ    [n × n]   (dot product similarity)

Step 3: Scale
    Scaled = Scores / √d_k       (prevent softmax saturation)

Step 4: Softmax (row-wise)
    Attention_weights = softmax(Scaled)    [n × n]

Step 5: Weighted sum of values
    Output = Attention_weights · V    [n × d_v]
```

### Compact Formula

```
Attention(Q, K, V) = softmax(QKᵀ / √d_k) · V
```

### Worked Example

```
Sentence: "The cat sat"  (3 tokens, d=4, d_k=d_v=2)

X = [[1,0,1,0],   ← "The"
     [0,1,0,1],   ← "cat"
     [1,1,0,0]]   ← "sat"

W_Q = [[1,0],     W_K = [[0,1],    W_V = [[1,0],
       [0,1],            [1,0],           [0,1],
       [1,0],            [0,1],           [1,1],
       [0,1]]            [1,0]]           [0,0]]

Q = X·W_Q = [[2,0], [0,2], [1,1]]
K = X·W_K = [[0,2], [2,0], [1,1]]
V = X·W_V = [[2,1], [0,1], [1,1]]

Scores = Q·Kᵀ = [[0, 4, 2],
                  [4, 0, 2],
                  [2, 2, 2]]

Scaled = Scores/√2 = [[0, 2.83, 1.41],
                       [2.83, 0, 1.41],
                       [1.41, 1.41, 1.41]]

Attention = softmax(Scaled, dim=-1) ≈ [[0.05, 0.78, 0.17],  ← "The" attends mostly to "cat"
                                        [0.78, 0.05, 0.17],  ← "cat" attends mostly to "The"
                                        [0.33, 0.33, 0.33]]  ← "sat" attends equally

Output = Attention · V ≈ [[0.17, 1.0], [1.59, 0.95], [1.0, 1.0]]
```

### Why Scale by √d_k?

Without scaling, for large d_k, dot products grow large → softmax becomes very peaked (near one-hot) → gradients vanish. Scaling keeps variance ≈ 1.

## 3. Multi-Head Attention

Instead of one attention function, use h parallel "heads" with different projections:

```
MultiHead(Q, K, V) = Concat(head₁, ..., headₕ) · W_O

where headᵢ = Attention(Q·W_Q^i, K·W_K^i, V·W_V^i)
```

```
          Q    K    V
          │    │    │
    ┌─────┼────┼────┼─────┐
    │  ┌──┴──┐ │    │     │
    │  │head₁│ ...  │     │  h heads in parallel
    │  └──┬──┘      │     │
    │     │    ┌──┴──┐    │
    │     │    │headₕ│    │
    │     │    └──┬──┘    │
    │     └───┬───┘       │
    │      Concat         │
    │         │           │
    │      [W_O]          │
    │         │           │
    └─────────┼───────────┘
              ↓
           Output
```

**Why multiple heads?** Different heads learn different types of relationships:
- Head 1: syntactic (subject-verb)
- Head 2: positional (adjacent words)
- Head 3: semantic (related concepts)

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.d_k = d_model // n_heads
        self.n_heads = n_heads
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)
    
    def forward(self, q, k, v, mask=None):
        B, T, D = q.shape
        # Project and reshape: [B, T, D] → [B, h, T, d_k]
        Q = self.W_q(q).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        K = self.W_k(k).view(B, -1, self.n_heads, self.d_k).transpose(1, 2)
        V = self.W_v(v).view(B, -1, self.n_heads, self.d_k).transpose(1, 2)
        
        # Scaled dot-product attention
        scores = (Q @ K.transpose(-2, -1)) / (self.d_k ** 0.5)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))
        attn = torch.softmax(scores, dim=-1)
        
        # Apply to values and reshape back
        out = (attn @ V).transpose(1, 2).contiguous().view(B, T, D)
        return self.W_o(out)
```

## 4. Positional Encoding

Transformers have no inherent notion of order. Positional encoding injects position information.

### Sinusoidal (Original Paper)

```
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
```

Properties:
- Each position gets a unique encoding
- PE(pos+k) can be expressed as a linear function of PE(pos) → model can learn relative positions
- No learnable parameters, generalizes to longer sequences

### Learned Positional Embeddings

```python
self.pos_embedding = nn.Embedding(max_seq_len, d_model)
# Simply add: token_embed + pos_embed
```

### Rotary Position Embedding (RoPE) — Used in LLaMA, modern LLMs

Encodes relative position directly in the attention computation by rotating Q and K vectors:
```
RoPE(xₘ, m) = xₘ · e^(imθ)   (complex rotation based on position m)
```

## 5. Full Transformer Architecture (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRANSFORMER                               │
│                                                                  │
│   ENCODER (×N)                        DECODER (×N)              │
│   ┌───────────────────┐              ┌───────────────────┐     │
│   │                   │              │                   │     │
│   │  ┌─────────────┐  │              │  ┌─────────────┐  │     │
│   │  │ Feed Forward │  │              │  │ Feed Forward │  │     │
│   │  └──────┬──────┘  │              │  └──────┬──────┘  │     │
│   │     Add & Norm    │              │     Add & Norm    │     │
│   │         │         │              │         │         │     │
│   │  ┌──────┴──────┐  │    ┌────→   │  ┌──────┴──────┐  │     │
│   │  │  Self-Attn   │  │    │ K,V    │  │Cross-Attention│  │     │
│   │  └──────┬──────┘  │    │        │  └──────┬──────┘  │     │
│   │     Add & Norm    │    │        │     Add & Norm    │     │
│   │         │         │    │        │         │         │     │
│   │  ┌──────┴──────┐  │────┘        │  ┌──────┴──────┐  │     │
│   │  │  Self-Attn   │  │              │  │Masked Self- │  │     │
│   │  └──────┬──────┘  │              │  │  Attention   │  │     │
│   │     Add & Norm    │              │  └──────┬──────┘  │     │
│   │         │         │              │     Add & Norm    │     │
│   └─────────┼─────────┘              └─────────┼─────────┘     │
│             │                                  │               │
│      Input Embed +                      Output Embed +         │
│      Positional Enc                     Positional Enc         │
│             │                                  │               │
│         [Inputs]                          [Outputs]            │
│                                          (shifted right)       │
└─────────────────────────────────────────────────────────────────┘
```

### Encoder Block Details

```python
class TransformerEncoderBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff, dropout=0.1):
        super().__init__()
        self.attn = MultiHeadAttention(d_model, n_heads)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Linear(d_ff, d_model),
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, mask=None):
        # Pre-norm variant (used in modern transformers)
        x = x + self.dropout(self.attn(self.norm1(x), self.norm1(x), self.norm1(x), mask))
        x = x + self.dropout(self.ff(self.norm2(x)))
        return x
```

### Causal Mask (Decoder Self-Attention)

```
For decoder: prevent attending to future tokens

Mask (for sequence length 4):
[[1, 0, 0, 0],     Token 1 can only see token 1
 [1, 1, 0, 0],     Token 2 can see tokens 1-2
 [1, 1, 1, 0],     Token 3 can see tokens 1-3
 [1, 1, 1, 1]]     Token 4 can see all tokens 1-4

Implemented by setting masked positions to -inf before softmax.
```

```python
def causal_mask(size):
    return torch.tril(torch.ones(size, size)).bool()
```

## 6. Key Model Families

### BERT (Encoder-only, Bidirectional)

```
Architecture: Stack of encoder blocks
Pre-training:
  1. Masked Language Model (MLM): mask 15% of tokens, predict them
  2. Next Sentence Prediction (NSP): binary classification
Fine-tuning: Add task head on top of [CLS] token

BERT-base: 12 layers, 768 dim, 12 heads, 110M params
BERT-large: 24 layers, 1024 dim, 16 heads, 340M params
```

### GPT Family (Decoder-only, Autoregressive)

```
Architecture: Stack of decoder blocks (masked self-attention only, no cross-attention)
Pre-training: Next token prediction (causal LM)
  P(w₁, w₂, ..., wₙ) = Π P(wᵢ | w₁, ..., wᵢ₋₁)

GPT-2:  1.5B params, 48 layers, 1600 dim
GPT-3:  175B params, 96 layers, 12288 dim
GPT-4:  Rumored MoE, ~1.8T total params
```

### T5 (Encoder-Decoder, Text-to-Text)

All tasks framed as text-to-text:
- Translation: "translate English to French: The house is wonderful"
- Summarization: "summarize: <article>"
- Classification: "classify: <text>" → "positive"

### Comparison

| | BERT | GPT | T5 |
|---|------|-----|-----|
| Architecture | Encoder | Decoder | Encoder-Decoder |
| Attention | Bidirectional | Causal (left-to-right) | Both |
| Pre-training | MLM + NSP | Causal LM | Span corruption |
| Best for | Understanding (NER, QA) | Generation | Both |
| Input/Output | Embeddings | Text | Text-to-text |

## 7. Vision Transformer (ViT)

```
Image (224×224×3)
    ↓ Split into patches (16×16)
[P₁, P₂, ..., P₁₉₆]  (196 patches, each 16×16×3 = 768 dims)
    ↓ Linear projection (flatten + project)
[z₁, z₂, ..., z₁₉₆]  (196 patch embeddings, d=768)
    ↓ Prepend [CLS] token + add position embeddings
[CLS, z₁+PE₁, z₂+PE₂, ..., z₁₉₆+PE₁₉₆]
    ↓ Standard Transformer Encoder (12 layers)
[CLS_out, ...]
    ↓ MLP head on CLS_out
Classification
```

Key finding: ViT needs large datasets (ImageNet-21K or JFT-300M) to beat CNNs. With enough data, scales better.

## 8. Training at Scale

### Distributed Training

```
Data Parallelism:
  - Replicate model on N GPUs
  - Split batch across GPUs
  - All-reduce gradients
  - PyTorch: DistributedDataParallel (DDP)

Model Parallelism (for models too large for one GPU):
  - Tensor Parallelism: split individual layers across GPUs
  - Pipeline Parallelism: split layers across GPUs, microbatching
  - ZeRO (DeepSpeed): partition optimizer states, gradients, parameters

For LLMs: combine all three (3D parallelism)
```

### Mixed Precision Training

```python
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()
for batch in dataloader:
    optimizer.zero_grad()
    with autocast():  # FP16 forward pass
        output = model(batch)
        loss = criterion(output, targets)
    scaler.scale(loss).backward()  # Scale loss to prevent underflow
    scaler.step(optimizer)
    scaler.update()
```

### Flash Attention

Standard attention: O(n²) memory (store full attention matrix)
Flash Attention: O(n) memory by computing attention in tiles (IO-aware algorithm)

```python
# In PyTorch 2.0+
from torch.nn.functional import scaled_dot_product_attention
# Automatically uses Flash Attention when available
out = scaled_dot_product_attention(Q, K, V, attn_mask=mask)
```

## 9. Fine-Tuning Strategies

### Full Fine-Tuning
Update all parameters. Expensive for large models.

### LoRA (Low-Rank Adaptation)

```
Idea: Weight update ΔW is low-rank. Instead of updating W directly:
W' = W + ΔW = W + B·A    where B ∈ ℝᵈˣʳ, A ∈ ℝʳˣᵈ, r << d

Original: W (frozen) ──→ output
LoRA:     W (frozen) ──→ (+) ──→ output
          B·A (trainable) ──↗

Trainable params: 2·d·r (vs d² for full)
For r=8, d=4096: 65K vs 16M params per layer
```

```python
# Using PEFT library
from peft import LoraConfig, get_peft_model

config = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.1,
    target_modules=["q_proj", "v_proj"]  # Which layers to adapt
)
model = get_peft_model(base_model, config)
model.print_trainable_parameters()  # ~0.1% of total
```

### QLoRA

Quantize base model to 4-bit, apply LoRA on top:
- 4-bit NormalFloat quantization
- Double quantization (quantize the quantization constants)
- Paged optimizers (handle memory spikes)

Result: Fine-tune 65B model on single 48GB GPU!

### Adapter Layers

Insert small bottleneck layers into frozen model:
```
x → [Frozen Layer] → [Down-project → ReLU → Up-project] → (+x) → next
                      └───── Adapter (trainable) ─────────┘
```

## 10. Prompt Engineering

### Key Techniques

| Technique | Example |
|-----------|---------|
| Zero-shot | "Classify: 'Great movie!' → Sentiment:" |
| Few-shot | "Positive: 'loved it'. Negative: 'hated it'. Classify: 'Great!' →" |
| Chain-of-thought | "Think step by step..." |
| System prompts | Set role, constraints, format |

### In-Context Learning

LLMs can "learn" new tasks from examples in the prompt without weight updates:
```
Translate English to French:
sea otter => loutre de mer
peppermint => menthe poivrée
cheese => 
```

## 11. Modern Optimizations

### KV-Cache (for autoregressive generation)

```
Without cache: At step T, recompute attention for ALL T tokens
With cache:    Store K,V for positions 1..T-1, only compute new token's Q

Reduces generation from O(T²) to O(T) per token
Memory tradeoff: cache grows with sequence length
```

### Grouped Query Attention (GQA) — LLaMA 2, Mistral

```
Multi-Head:           Every head has its own K,V  (expensive KV-cache)
Multi-Query:          All heads share one K,V    (too much quality loss)
Grouped-Query (GQA):  Groups of heads share K,V  (good tradeoff)

Example: 32 heads, 8 KV groups → 4 heads per KV group
```

### Mixture of Experts (MoE)

```
Each token routed to top-k experts (out of N total):
  x → Router → softmax → top-2 experts
  output = Σ gate_i · Expert_i(x)

Benefits: Total params huge (sparse), but active params per token small
Example: Mixtral 8×7B: 47B total params, 13B active per token
```

## Production Considerations

1. **Inference optimization**: vLLM (PagedAttention), TensorRT-LLM, GGML/llama.cpp
2. **Quantization**: GPTQ, AWQ, bitsandbytes for 4-bit inference
3. **Serving**: Continuous batching, speculative decoding, prefix caching
4. **Cost**: Prompt caching, shorter prompts, smaller models where possible
5. **Latency**: Time-to-first-token vs tokens-per-second tradeoff

## Interview Questions

1. **Why scale by √d_k?** Dot products grow with dimension → softmax saturates → vanishing gradients. Scaling keeps variance ≈ 1.

2. **Why multi-head > single head with same params?** Multiple heads learn different relationship types. Single large head mixes everything into one subspace.

3. **Why does GPT use causal masking?** Autoregressive generation: at inference, future tokens don't exist. Training must match inference (can't peek ahead).

4. **How does LoRA reduce memory?** Freezes original weights (no optimizer states needed for them). Only stores/updates small low-rank matrices.

5. **Self-attention complexity?** O(n²·d) compute, O(n²) memory. This is why context length is limited and Flash Attention matters.

6. **Pre-norm vs Post-norm?** Pre-norm (normalize before attention/FFN) is more stable for deep networks. Post-norm (original paper) can be unstable but sometimes performs slightly better with careful training.

7. **Why do LLMs use decoder-only?** Simpler, scales better with compute, unifies all tasks as text generation. Encoder-decoder better for specific seq2seq tasks but less flexible.

8. **Explain KV-cache.** During autoregressive generation, Keys and Values for past tokens don't change. Cache them to avoid redundant computation. Trades memory for speed.

9. **What is the difference between fine-tuning and prompting?** Fine-tuning updates weights (permanent, task-specific). Prompting conditions the model via input (no weight change, flexible, limited by context window).

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** Given a sequence of 4 tokens with embedding dimension d=8 and d_k=4, what are the dimensions of Q, K, V, and the attention weight matrix?
**Hint:** Q=XW_Q, attention_weights = softmax(QK^T/√d_k)

<details><summary>Solution</summary>

- X: [4 × 8] (4 tokens, 8-dim embeddings)
- W_Q, W_K: [8 × 4], W_V: [8 × 4]
- Q: [4 × 4], K: [4 × 4], V: [4 × 4]
- QKᵀ: [4 × 4] (each token attends to every other token)
- Attention weights: [4 × 4] (after softmax, rows sum to 1)
- Output: [4 × 4] (attention_weights @ V)

The attention matrix is n×n where n = sequence length. This is why transformers are O(n²) in memory!

</details>

### Exercise 2 (Beginner)
**Problem:** Why do we scale the dot product by √d_k in attention? What happens without scaling?
**Hint:** Think about the variance of the dot product.

<details><summary>Solution</summary>

If Q and K have entries with mean 0, variance 1, then:
- qᵀk = Σᵢ qᵢkᵢ has variance = d_k (sum of d_k independent terms with variance 1)

Without scaling, for large d_k:
- Dot products have large magnitude → softmax saturates
- Saturated softmax → gradients near zero → vanishing gradients
- Attention becomes nearly one-hot (loses soft weighting)

Dividing by √d_k normalizes variance to 1, keeping softmax in its sensitive region where gradients flow well.

</details>

### Exercise 3 (Beginner)
**Problem:** Explain the purpose of positional encoding. Why do transformers need it but RNNs don't?
**Hint:** What does self-attention know about word order without positional encoding?

<details><summary>Solution</summary>

Self-attention is **permutation equivariant** — it treats input as a SET, not a sequence. "Dog bites man" and "Man bites dog" produce the same attention pattern without positional information.

RNNs inherently encode position through sequential processing (hidden state carries temporal information).

**Positional encoding solutions:**
1. Sinusoidal (original): PE(pos, 2i) = sin(pos/10000^(2i/d))
2. Learned embeddings: trainable vector per position
3. Relative positional encoding (T5, ALiBi): encode distance between tokens
4. RoPE (Rotary): rotates embedding vectors by position-dependent angle

</details>

### Exercise 4 (Intermediate)
**Problem:** Multi-head attention uses h=8 heads with d_model=512. What is d_k for each head? Why use multiple heads instead of one large attention?
**Hint:** d_k = d_model / h

<details><summary>Solution</summary>

d_k = d_v = d_model / h = 512 / 8 = 64 per head

**Why multiple heads:**
1. Each head can attend to different aspects (syntactic, semantic, positional)
2. Different heads learn different relationship patterns
3. Multiple low-rank attention projections are more expressive than one full-rank
4. Allows the model to jointly attend to information from different representation subspaces

**Cost:** Multi-head with h heads of dimension d/h has SAME computational cost as single-head with dimension d (same total parameters).

Empirically, heads specialize: some attend locally, some long-range, some to specific syntactic roles.

</details>

### Exercise 5 (Intermediate)
**Problem:** In the decoder, why do we need a causal mask? How is it implemented?
**Hint:** During generation, token i shouldn't "see" tokens i+1, i+2, ...

<details><summary>Solution</summary>

**Why:** During training, the decoder sees all tokens simultaneously (teacher forcing). Without masking, position i could "cheat" by looking at the answer at position i+1. At inference, future tokens don't exist yet.

**Implementation:**
```python
# Upper triangular mask (True = positions to mask)
mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()

# Apply before softmax:
scores = Q @ K.T / sqrt(d_k)
scores.masked_fill_(mask, float('-inf'))  # -inf → 0 after softmax
attention_weights = softmax(scores)
```

Result: attention_weights[i][j] = 0 for all j > i (can't attend to future).

This makes training autoregressive: predict each token given only previous tokens, enabling parallel training.

</details>

### Exercise 6 (Intermediate)
**Problem:** Compare the original Transformer (encoder-decoder) with GPT (decoder-only) and BERT (encoder-only). When would you use each architecture?
**Hint:** Consider the task type: generation, understanding, or sequence-to-sequence.

<details><summary>Solution</summary>

| Architecture | Attention Type | Pre-training | Best For |
|---|---|---|---|
| Encoder-decoder (T5) | Bidirectional enc + causal dec | Span corruption | Translation, summarization, any seq2seq |
| Decoder-only (GPT) | Causal (left-to-right) | Next token prediction | Text generation, few-shot, chat |
| Encoder-only (BERT) | Bidirectional | Masked LM + NSP | Classification, NER, QA (extractive) |

**Use encoder-decoder:** Structured output different from input (translation, summarization)
**Use decoder-only:** Generation, when you want one model for many tasks (GPT-4, Claude)
**Use encoder-only:** Understanding/classification tasks, when you need bidirectional context

Modern trend: Decoder-only dominates due to scaling properties and versatility (can do classification via generation).

</details>

### Exercise 7 (Intermediate)
**Problem:** Calculate the number of parameters in a single transformer layer with d_model=768, h=12, d_ff=3072. Include all sub-layers.
**Hint:** Count: self-attention (Q,K,V,O projections), FFN (2 linear layers), layer norms.

<details><summary>Solution</summary>

**Self-Attention:**
- W_Q: 768×768 + 768 bias = 590,592
- W_K: 768×768 + 768 = 590,592
- W_V: 768×768 + 768 = 590,592
- W_O: 768×768 + 768 = 590,592
- Subtotal: 2,362,368

**Feed-Forward Network:**
- Linear1: 768×3072 + 3072 = 2,362,368
- Linear2: 3072×768 + 768 = 2,360,064
- Subtotal: 4,722,432

**Layer Norms (×2):**
- 2 × (768 + 768) = 3,072 (γ and β for each)

**Total per layer: ~7.1M parameters**

For BERT-base (12 layers): 12 × 7.1M ≈ 85M + embeddings ≈ 110M total.

</details>

### Exercise 8 (Advanced)
**Problem:** Explain FlashAttention. Why is it faster despite doing the same computation? What is the IO-awareness insight?
**Hint:** Think about GPU memory hierarchy (SRAM vs HBM) and memory-bound vs compute-bound.

<details><summary>Solution</summary>

**Standard attention bottleneck:**
1. Compute S = QKᵀ → write n×n matrix to HBM (GPU global memory)
2. Read S, apply softmax → write back to HBM
3. Read attention weights, multiply by V → write output to HBM

For n=2048, d=64: S is 2048×2048 = 16MB. HBM bandwidth is the bottleneck, not compute!

**FlashAttention insight:** Never materialize the full n×n attention matrix.

**Algorithm:**
1. Tile Q, K, V into blocks that fit in SRAM (fast on-chip memory)
2. For each block: compute local attention, accumulate using online softmax
3. Never write the full n×n matrix to HBM

**Online softmax trick:** Can compute softmax incrementally:
- Process blocks of K, track running max and sum
- Rescale previous results when new max found

**Result:** 
- 2-4x faster (memory-bound → compute-bound)
- O(n) memory instead of O(n²) for the attention matrix
- Exact same output (not approximate!)
- Enables training on much longer sequences

</details>

### Exercise 9 (Advanced)
**Problem:** Explain the KV-cache optimization during autoregressive generation. Why is it necessary and what are its memory implications?
**Hint:** Without caching, generating token N requires recomputing attention for all N-1 previous tokens.

<details><summary>Solution</summary>

**Problem without KV-cache:**
Generating token t requires attending to tokens 1..t-1. Naive implementation recomputes K and V for all previous tokens at every step → O(n²) total computation for n tokens.

**KV-cache solution:**
- Cache K and V matrices from all previous tokens
- For new token t: only compute Q_t, K_t, V_t for the new token
- Attention: Q_t (1×d) attends to cached K (t×d), V (t×d)
- Append new K_t, V_t to cache

**Complexity improvement:**
- Without cache: generating n tokens = O(n³d) (recompute all at each step)
- With cache: O(n²d) total (linear compute per step)

**Memory implications:**
- Cache size per layer: 2 × batch × n × d_k × n_heads × 2 bytes (FP16)
- For GPT-3 (96 layers, d=12288, n=2048): ~3GB per sequence!
- This is why max context length is limited
- Solutions: Multi-Query Attention (share K,V across heads), Grouped-Query Attention, quantized cache

</details>

### Exercise 10 (Advanced)
**Problem:** Compare and contrast RoPE (Rotary Position Embedding), ALiBi (Attention with Linear Biases), and learned positional embeddings. How does each handle extrapolation to longer sequences than seen during training?
**Hint:** Consider what happens at position 2048 if trained with max position 1024.

<details><summary>Solution</summary>

**Learned Positional Embeddings (GPT-2):**
- Trainable vector per position: PE = Embedding(position)
- Cannot extrapolate: position 1025 has no trained embedding
- Simple but rigid
- Length limit fixed at training time

**Sinusoidal (original Transformer):**
- PE(pos, 2i) = sin(pos/10000^(2i/d))
- Mathematically can represent any position
- Limited extrapolation in practice (model hasn't seen those patterns)

**RoPE (Rotary Position Embedding) - LLaMA, GPT-NeoX:**
- Rotates Q and K vectors by position-dependent angle
- f(q,m) = q·e^(imθ) — position m rotates by angle mθ
- Relative position encoded in dot product: f(q,m)ᵀf(k,n) depends on m-n
- Extrapolation: degrades gracefully, can be extended with NTK-scaling or YaRN
- Most popular modern choice

**ALiBi (Attention with Linear Biases) - BLOOM:**
- No positional embedding at all
- Add linear bias to attention scores: score -= m·|i-j| (m is head-specific slope)
- Penalizes attending to distant tokens linearly
- Excellent extrapolation (bias formula works at any distance)
- Simpler, no extra parameters
- Less expressive than RoPE for complex positional patterns

**Extrapolation ranking:** ALiBi > RoPE (with scaling) > Sinusoidal > Learned

</details>

### Exercise 11 (Advanced)
**Problem:** Explain how LoRA (Low-Rank Adaptation) works for fine-tuning large transformers. What is the mathematical insight and why does it work?
**Hint:** Weight updates during fine-tuning tend to be low-rank.

<details><summary>Solution</summary>

**Core insight:** The weight change ΔW during fine-tuning has low intrinsic rank.

**Method:**
- Freeze original weights W₀ (d×d)
- Add trainable decomposition: ΔW = BA where B∈ℝ^(d×r), A∈ℝ^(r×d), r << d
- Forward: h = (W₀ + BA)x = W₀x + BAx
- Only train A and B (r×d + d×r = 2rd parameters vs d² full fine-tuning)

**Example:** d=4096, r=8
- Full fine-tuning: 16.7M parameters per matrix
- LoRA: 2 × 4096 × 8 = 65K parameters per matrix (256x reduction!)

**Why it works:**
1. Aghajanyan et al. showed pre-trained models have low "intrinsic dimensionality"
2. Fine-tuning updates live in a low-rank subspace
3. r=4-64 is sufficient for most tasks (vs d=4096+)

**Practical details:**
- Apply to Q, V projections (most effective)
- α/r scaling factor for stable training
- Can merge BA into W₀ at inference (zero overhead!)
- QLoRA: quantize base model to 4-bit + LoRA for extreme efficiency

</details>

---

## Self-Assessment Quiz

**1. The computational complexity of self-attention with respect to sequence length n is:**
- A) O(n)
- B) O(n log n)
- C) O(n²)
- D) O(n³)

<details><summary>Answer</summary>C) O(n²) — due to QKᵀ matrix multiplication [n×d] × [d×n] = [n×n]. This is why long sequences are expensive.</details>

**2. In multi-head attention with h heads, the total computation compared to single-head attention is:**
- A) h times more
- B) The same
- C) h times less
- D) h² times more

<details><summary>Answer</summary>B) The same — each head uses d/h dimensions, so h heads of size d/h = total computation equivalent to 1 head of size d.</details>

**3. The feed-forward network in a transformer layer typically expands the dimension by:**
- A) 2x
- B) 4x
- C) 8x
- D) 16x

<details><summary>Answer</summary>B) 4x — d_ff = 4 × d_model is the standard ratio (e.g., 768 → 3072 in BERT-base).</details>

**4. BERT's [MASK] token is used for:**
- A) Padding
- B) Masked Language Model pre-training (predict masked tokens)
- C) Separating sentences
- D) End of sequence

<details><summary>Answer</summary>B) MLM pre-training — randomly mask 15% of tokens, train model to predict them using bidirectional context.</details>

**5. The key difference between GPT and BERT is:**
- A) GPT uses attention, BERT doesn't
- B) GPT uses causal (left-to-right) attention, BERT uses bidirectional
- C) GPT is larger
- D) BERT can generate text

<details><summary>Answer</summary>B) GPT: causal masking (each token sees only left context). BERT: no masking (each token sees full sequence).</details>

**6. Layer normalization in transformers normalizes across:**
- A) The batch dimension
- B) The feature/embedding dimension
- C) The sequence length dimension
- D) All dimensions

<details><summary>Answer</summary>B) The feature dimension — for each token independently, normalize across the d_model dimensions. Unlike batch norm, independent of batch size.</details>

**7. The residual connection in transformers computes:**
- A) output = LayerNorm(x + Sublayer(x))
- B) output = x × Sublayer(x)
- C) output = max(x, Sublayer(x))
- D) output = x - Sublayer(x)

<details><summary>Answer</summary>A) Pre-norm: x + Sublayer(LayerNorm(x)) or Post-norm: LayerNorm(x + Sublayer(x)). The additive residual allows gradients to flow directly.</details>

**8. Cross-attention in the decoder differs from self-attention because:**
- A) Q comes from decoder, K and V come from encoder
- B) It uses different activation functions
- C) It doesn't use softmax
- D) It only attends to adjacent tokens

<details><summary>Answer</summary>A) Q from decoder (what am I looking for?), K and V from encoder (what's available in the source?). This is how the decoder "reads" the encoder's output.</details>

**9. GPT-3 has 175B parameters. Approximately how much GPU memory is needed to load it in FP16?**
- A) 35 GB
- B) 175 GB
- C) 350 GB
- D) 700 GB

<details><summary>Answer</summary>C) 350 GB — 175B params × 2 bytes (FP16) = 350 GB. This is why it requires multiple A100 GPUs (80GB each) just for inference.</details>

**10. The "attention is all you need" paper's key contribution was:**
- A) Inventing attention
- B) Showing attention alone (without RNN/CNN) can achieve SOTA on NLP tasks
- C) Creating BERT
- D) Inventing positional encoding

<details><summary>Answer</summary>B) Demonstrating that a pure attention architecture (no recurrence, no convolution) achieves state-of-the-art, with better parallelization and scalability.</details>

---

## Coding Challenges

### Challenge 1: Implement Scaled Dot-Product Attention from Scratch
```python
"""
Implement the core attention mechanism: softmax(QK^T/√d_k)V
Include optional causal mask for decoder.
"""
import numpy as np

def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Q: (batch, n_q, d_k)
    K: (batch, n_k, d_k)
    V: (batch, n_k, d_v)
    mask: (n_q, n_k) boolean mask (True = mask out)
    Returns: output (batch, n_q, d_v), attention_weights (batch, n_q, n_k)
    """
    d_k = Q.shape[-1]
    
    # Compute attention scores
    scores = Q @ K.transpose(0, 2, 1) / np.sqrt(d_k)  # (batch, n_q, n_k)
    
    # Apply mask
    if mask is not None:
        scores = np.where(mask, -1e9, scores)
    
    # Softmax
    exp_scores = np.exp(scores - scores.max(axis=-1, keepdims=True))
    attention_weights = exp_scores / exp_scores.sum(axis=-1, keepdims=True)
    
    # Weighted sum of values
    output = attention_weights @ V  # (batch, n_q, d_v)
    
    return output, attention_weights

def causal_mask(seq_len):
    """Create upper triangular mask for autoregressive attention."""
    return np.triu(np.ones((seq_len, seq_len), dtype=bool), k=1)
```

### Challenge 2: Implement Multi-Head Attention
```python
"""
Implement multi-head attention with linear projections.
Split d_model into h heads, apply attention, concatenate.
"""
import numpy as np

class MultiHeadAttention:
    def __init__(self, d_model, n_heads):
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        
        # Initialize projection matrices
        self.W_Q = np.random.randn(d_model, d_model) * 0.02
        self.W_K = np.random.randn(d_model, d_model) * 0.02
        self.W_V = np.random.randn(d_model, d_model) * 0.02
        self.W_O = np.random.randn(d_model, d_model) * 0.02
    
    def split_heads(self, x):
        """(batch, seq_len, d_model) -> (batch, n_heads, seq_len, d_k)"""
        batch, seq_len, _ = x.shape
        x = x.reshape(batch, seq_len, self.n_heads, self.d_k)
        return x.transpose(0, 2, 1, 3)
    
    def combine_heads(self, x):
        """(batch, n_heads, seq_len, d_k) -> (batch, seq_len, d_model)"""
        batch, _, seq_len, _ = x.shape
        x = x.transpose(0, 2, 1, 3)
        return x.reshape(batch, seq_len, self.d_model)
    
    def forward(self, Q, K, V, mask=None):
        # Project
        Q = Q @ self.W_Q  # (batch, seq, d_model)
        K = K @ self.W_K
        V = V @ self.W_V
        
        # Split into heads
        Q = self.split_heads(Q)  # (batch, heads, seq, d_k)
        K = self.split_heads(K)
        V = self.split_heads(V)
        
        # Attention per head
        d_k = Q.shape[-1]
        scores = Q @ K.transpose(0, 1, 3, 2) / np.sqrt(d_k)
        if mask is not None:
            scores = np.where(mask, -1e9, scores)
        
        weights = np.exp(scores - scores.max(axis=-1, keepdims=True))
        weights /= weights.sum(axis=-1, keepdims=True)
        
        output = weights @ V  # (batch, heads, seq, d_k)
        
        # Combine heads and project
        output = self.combine_heads(output)  # (batch, seq, d_model)
        output = output @ self.W_O
        
        return output
```

### Challenge 3: Implement a Complete Transformer Encoder Layer
```python
"""
Implement one transformer encoder layer with:
- Multi-head self-attention
- Feed-forward network
- Residual connections
- Layer normalization
"""
import numpy as np

class LayerNorm:
    def __init__(self, d_model, eps=1e-6):
        self.gamma = np.ones(d_model)
        self.beta = np.zeros(d_model)
        self.eps = eps
    
    def forward(self, x):
        mean = x.mean(axis=-1, keepdims=True)
        var = x.var(axis=-1, keepdims=True)
        return self.gamma * (x - mean) / np.sqrt(var + self.eps) + self.beta

class FeedForward:
    def __init__(self, d_model, d_ff):
        self.W1 = np.random.randn(d_model, d_ff) * 0.02
        self.b1 = np.zeros(d_ff)
        self.W2 = np.random.randn(d_ff, d_model) * 0.02
        self.b2 = np.zeros(d_model)
    
    def forward(self, x):
        # GELU approximation
        h = x @ self.W1 + self.b1
        h = h * 0.5 * (1 + np.tanh(np.sqrt(2/np.pi) * (h + 0.044715 * h**3)))
        return h @ self.W2 + self.b2

class TransformerEncoderLayer:
    def __init__(self, d_model=512, n_heads=8, d_ff=2048):
        self.attention = MultiHeadAttention(d_model, n_heads)
        self.ffn = FeedForward(d_model, d_ff)
        self.norm1 = LayerNorm(d_model)
        self.norm2 = LayerNorm(d_model)
    
    def forward(self, x, mask=None):
        # Self-attention with residual (Pre-norm)
        x_norm = self.norm1.forward(x)
        attn_out = self.attention.forward(x_norm, x_norm, x_norm, mask)
        x = x + attn_out
        
        # FFN with residual
        x_norm = self.norm2.forward(x)
        ffn_out = self.ffn.forward(x_norm)
        x = x + ffn_out
        
        return x
```

### Challenge 4: Implement Positional Encoding (Sinusoidal + RoPE)
```python
"""
Implement both sinusoidal positional encoding (original) and 
Rotary Position Embedding (RoPE) used in modern LLMs.
"""
import numpy as np

def sinusoidal_positional_encoding(max_len, d_model):
    """Original transformer positional encoding."""
    PE = np.zeros((max_len, d_model))
    position = np.arange(max_len)[:, np.newaxis]
    div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
    
    PE[:, 0::2] = np.sin(position * div_term)
    PE[:, 1::2] = np.cos(position * div_term)
    return PE

def apply_rope(x, positions):
    """
    Apply Rotary Position Embedding.
    x: (batch, seq_len, d) - query or key vectors
    positions: (seq_len,) - position indices
    """
    d = x.shape[-1]
    freqs = 1.0 / (10000 ** (np.arange(0, d, 2) / d))
    
    # Compute rotation angles
    angles = positions[:, np.newaxis] * freqs[np.newaxis, :]  # (seq_len, d/2)
    
    # Split x into pairs and apply rotation
    x_pairs = x.reshape(*x.shape[:-1], -1, 2)  # (..., d/2, 2)
    
    cos_angles = np.cos(angles)  # (seq_len, d/2)
    sin_angles = np.sin(angles)
    
    # Rotation: [cos θ, -sin θ; sin θ, cos θ] @ [x1, x2]
    x_rotated = np.stack([
        x_pairs[..., 0] * cos_angles - x_pairs[..., 1] * sin_angles,
        x_pairs[..., 0] * sin_angles + x_pairs[..., 1] * cos_angles
    ], axis=-1)
    
    return x_rotated.reshape(x.shape)

# Key property: dot(RoPE(q, m), RoPE(k, n)) depends only on (m-n)
# This gives RELATIVE positional information through the dot product!
```

### Challenge 5: Implement Autoregressive Text Generation with KV-Cache
```python
"""
Implement greedy and top-k/top-p (nucleus) sampling for text generation
with KV-cache for efficient autoregressive generation.
"""
import numpy as np

class GenerationWithKVCache:
    def __init__(self, model, vocab_size):
        self.model = model  # Transformer decoder
        self.vocab_size = vocab_size
    
    def generate(self, prompt_tokens, max_new_tokens, temperature=1.0, 
                 top_k=50, top_p=0.9, strategy='nucleus'):
        """Generate tokens autoregressively with KV-cache."""
        
        # Process prompt (prefill phase)
        kv_cache = {}  # {layer_idx: (K_cache, V_cache)}
        logits = self.model.forward(prompt_tokens, kv_cache=kv_cache, build_cache=True)
        
        generated = list(prompt_tokens)
        
        for _ in range(max_new_tokens):
            # Get next token logits (only process last token with cache)
            next_logits = logits[-1] / temperature  # (vocab_size,)
            
            # Sampling strategy
            if strategy == 'greedy':
                next_token = np.argmax(next_logits)
            elif strategy == 'top_k':
                next_token = self._top_k_sample(next_logits, top_k)
            elif strategy == 'nucleus':
                next_token = self._nucleus_sample(next_logits, top_p)
            
            generated.append(next_token)
            
            # Forward only the new token (using cache)
            logits = self.model.forward(
                np.array([next_token]), 
                kv_cache=kv_cache, 
                build_cache=True
            )
        
        return generated
    
    def _top_k_sample(self, logits, k):
        """Sample from top-k highest probability tokens."""
        top_k_idx = np.argsort(logits)[-k:]
        top_k_logits = logits[top_k_idx]
        
        # Softmax over top-k
        probs = np.exp(top_k_logits - top_k_logits.max())
        probs /= probs.sum()
        
        return top_k_idx[np.random.choice(len(top_k_idx), p=probs)]
    
    def _nucleus_sample(self, logits, p):
        """Sample from smallest set of tokens with cumulative probability >= p."""
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        
        sorted_idx = np.argsort(probs)[::-1]
        sorted_probs = probs[sorted_idx]
        cumsum = np.cumsum(sorted_probs)
        
        # Find cutoff
        cutoff = np.searchsorted(cumsum, p) + 1
        nucleus_idx = sorted_idx[:cutoff]
        nucleus_probs = probs[nucleus_idx]
        nucleus_probs /= nucleus_probs.sum()
        
        return nucleus_idx[np.random.choice(len(nucleus_idx), p=nucleus_probs)]
```

---

## Interview Questions

### 1. Why is self-attention O(n²) and what approaches reduce this?
<details><summary>Answer</summary>

O(n²) because every token attends to every other token (n×n attention matrix).

**Efficient attention variants:**
1. **FlashAttention:** Same computation but I/O-aware (2-4x faster, still O(n²) compute)
2. **Sparse attention (Longformer, BigBird):** Each token attends to local window + global tokens → O(n)
3. **Linear attention (Performer):** Approximate softmax with kernel trick → O(n)
4. **Multi-Query Attention:** Share K,V across heads (reduces memory, not compute)
5. **Grouped-Query Attention (GQA):** Groups of heads share K,V (LLaMA 2)
6. **Sliding window (Mistral):** Limited context per layer, stacked for longer effective context

</details>

### 2. Explain the difference between pre-training and fine-tuning for LLMs.
<details><summary>Answer</summary>

**Pre-training:**
- Train on massive unlabeled text (internet-scale)
- Objective: next token prediction (GPT) or masked LM (BERT)
- Learns general language understanding: grammar, facts, reasoning
- Extremely expensive (millions of GPU-hours)
- Done once by large labs

**Fine-tuning:**
- Adapt pre-trained model to specific task/domain
- Much smaller labeled dataset
- Methods: full fine-tuning, LoRA, prefix tuning, prompt tuning
- Relatively cheap (hours-days on single GPU with LoRA)
- Can be instruction tuning (teach to follow instructions) or task-specific

**Modern approach:** Pre-train → Instruction fine-tune → RLHF (alignment)

</details>

### 3. What is the difference between encoder-decoder attention (cross-attention) and self-attention?
<details><summary>Answer</summary>

**Self-attention:** Q, K, V all come from the same sequence.
- Each token attends to all other tokens in the same sequence
- Used in encoder (BERT) and decoder (GPT)

**Cross-attention:** Q from decoder, K and V from encoder output.
- Decoder tokens "query" the encoder's representation
- Allows decoder to attend to relevant parts of source sequence
- Used in encoder-decoder models (T5, translation)

Example in translation: Decoder generating "chat" → cross-attention highlights "cat" in English encoder output.

</details>

### 4. How does RLHF (Reinforcement Learning from Human Feedback) work?
<details><summary>Answer</summary>

Three phases:
1. **SFT (Supervised Fine-Tuning):** Fine-tune base LLM on high-quality demonstrations
2. **Reward Model:** Train a model to predict human preferences (given two responses, which is better?)
3. **PPO (Proximal Policy Optimization):** Optimize the LLM to maximize reward while staying close to the SFT model (KL penalty)

Objective: max E[R(x,y)] - β·KL(π_RL || π_SFT)

Why it works: Aligns model with human values (helpful, harmless, honest) that aren't captured by next-token prediction alone.

Alternatives: DPO (Direct Preference Optimization) — skips the reward model, directly optimizes from preferences.

</details>

### 5. Explain the concept of "scaling laws" for transformers.
<details><summary>Answer</summary>

**Kaplan et al. / Chinchilla findings:**
Loss follows power laws in three dimensions:
- L(N) ∝ N^(-0.076) — model parameters
- L(D) ∝ D^(-0.095) — dataset size  
- L(C) ∝ C^(-0.050) — compute budget

**Key insights:**
1. Performance improves predictably with scale (no diminishing returns yet)
2. Compute-optimal training (Chinchilla): tokens ≈ 20 × parameters
3. Larger models are more sample-efficient
4. Emergent abilities appear at certain scales (in-context learning, chain-of-thought)

**Practical implication:** Given a compute budget, you can predict the optimal model size and data amount before training.

</details>

### 6. What is the difference between token-level and sequence-level tasks? How do transformers handle each?
<details><summary>Answer</summary>

**Token-level tasks:** Predict for each token independently.
- NER: label each token (person, location, etc.)
- POS tagging: assign part-of-speech per token
- Approach: Use all encoder outputs, classify each

**Sequence-level tasks:** One prediction for entire sequence.
- Sentiment analysis: positive/negative for whole review
- Classification: topic of document
- Approach: Use [CLS] token representation or pool all outputs

**Generation tasks:** Produce output sequence.
- Translation, summarization, dialogue
- Approach: Autoregressive decoding token-by-token

</details>

### 7. How do you handle sequences longer than the model's context window?
<details><summary>Answer</summary>

1. **Truncation:** Simple but loses information (first/last N tokens)
2. **Sliding window:** Process overlapping chunks, aggregate (stride < window)
3. **Hierarchical:** Summarize chunks, then process summaries
4. **Retrieval-augmented generation (RAG):** Retrieve relevant chunks, fit in context
5. **Architecture solutions:**
   - Longformer/BigBird: sparse attention patterns
   - ALiBi/RoPE: better extrapolation to unseen lengths
   - Ring attention: distribute long sequences across GPUs
6. **Context extension:** Fine-tune with longer sequences + position interpolation

</details>

---

## Real-World Scenarios

### Scenario 1: Building a Retrieval-Augmented Generation (RAG) System
**Context:** You're building a customer support chatbot for a company with 10K documentation pages. The chatbot should answer questions using company-specific knowledge that isn't in the LLM's training data.

**Questions:**
1. Design the RAG pipeline architecture.
2. How do you chunk and embed documents?
3. How do you handle cases where retrieved context is irrelevant?
4. How do you evaluate the system's performance?

<details><summary>Solution</summary>

1. **Architecture:**
   - **Indexing:** Documents → Chunk → Embed → Store in vector DB (Pinecone/Weaviate)
   - **Retrieval:** User query → Embed → Find top-k similar chunks → Rerank
   - **Generation:** Prompt = "Context: {retrieved_chunks}\n\nQuestion: {query}\n\nAnswer:"
   - **Post-processing:** Citation extraction, hallucination detection

2. **Chunking strategy:**
   - Chunk size: 256-512 tokens (balance context vs specificity)
   - Overlap: 50-100 tokens (preserve context across boundaries)
   - Respect document structure (don't split mid-paragraph)
   - Include metadata (source, section title) in each chunk
   - Embedding model: text-embedding-ada-002 or open-source (E5, BGE)

3. **Handling irrelevant retrieval:**
   - **Reranker:** Cross-encoder to rerank top-20 → top-5 (more accurate than bi-encoder)
   - **Relevance threshold:** Don't include chunks below similarity score X
   - **"I don't know" instruction:** System prompt tells LLM to say "I don't have information about this" if context doesn't contain the answer
   - **Query expansion:** Rephrase query for better retrieval
   - **Hybrid search:** Combine dense (semantic) + sparse (BM25/keyword) retrieval

4. **Evaluation:**
   - **Retrieval:** Recall@k (are the right chunks in top-k?), MRR, NDCG
   - **Generation:** Factual correctness (vs ground truth), faithfulness (does answer match retrieved context?), relevance
   - **End-to-end:** Human evaluation, user satisfaction scores
   - **Automated:** RAGAS framework (faithfulness, relevance, context recall)
   - **Hallucination detection:** Check if claims in answer have support in retrieved context

</details>

### Scenario 2: Fine-Tuning an LLM for Domain-Specific Tasks
**Context:** You're a ML engineer at a legal tech company. You need to adapt a 7B parameter open-source LLM to summarize legal contracts and extract key clauses. You have 5K annotated contract-summary pairs and a budget of $10K for compute.

**Questions:**
1. Full fine-tuning vs LoRA vs prompt engineering — which approach?
2. How do you prepare the training data?
3. What is your training configuration?
4. How do you evaluate and prevent hallucination on legal text?

<details><summary>Solution</summary>

1. **Approach: LoRA fine-tuning (best for this scenario)**
   - Full fine-tuning of 7B: needs 8x A100 80GB, >$10K, overfits on 5K samples
   - LoRA: 1-2x A100, trains in hours, $500-2K compute, prevents overfitting
   - Prompt engineering alone: insufficient for structured extraction tasks
   - QLoRA (4-bit base + LoRA): can train on single GPU with 24GB

2. **Data preparation:**
   - Format: instruction-input-output triplets
   - Input: contract text (may need chunking for long contracts)
   - Output: structured summary + extracted clauses
   - Quality: Have lawyers validate 10% of annotations
   - Augmentation: Include different contract types, lengths
   - Decontamination: Ensure no test contracts in training

3. **Training configuration:**
   - Base model: LLaMA-2 7B or Mistral 7B
   - LoRA rank: r=16, alpha=32, applied to Q, K, V, O
   - Learning rate: 2e-4 with cosine schedule
   - Batch size: 4 (gradient accumulation=8 for effective=32)
   - Epochs: 3-5 (with early stopping on validation loss)
   - Max sequence length: 4096 tokens
   - Precision: bf16 mixed precision

4. **Evaluation & anti-hallucination:**
   - ROUGE scores for summary quality
   - Exact match for clause extraction (precision/recall per clause type)
   - Faithfulness: every claim must be traceable to source contract
   - Confidence calibration: output confidence scores
   - Human evaluation: lawyer review of 100 random outputs
   - Constrained decoding: limit outputs to content present in input
   - Citation requirement: model must reference paragraph numbers

</details>

### Scenario 3: Optimizing Transformer Inference for Production
**Context:** You're deploying a GPT-style model (13B parameters) as an API service. Requirements: p95 latency < 2 seconds for 500-token responses, 100 concurrent users, cost-effective (not unlimited budget for GPUs).

**Questions:**
1. What are the main bottlenecks for inference?
2. How do you optimize for throughput and latency?
3. What hardware and serving infrastructure would you choose?
4. How do you handle variable-length requests efficiently?

<details><summary>Solution</summary>

1. **Bottlenecks:**
   - **Prefill phase:** Compute-bound (processing full prompt, parallelizable)
   - **Decode phase:** Memory-bandwidth-bound (one token at a time, loading full model for each token)
   - **KV-cache memory:** Grows linearly with sequence length × batch size
   - **13B model in FP16 = 26GB** just for weights (plus KV-cache, activations)

2. **Optimizations:**
   - **Quantization:** INT8 or INT4 (AWQ/GPTQ): 2-4x smaller, faster inference
   - **KV-cache optimization:** GQA (model-level), paged attention (vLLM)
   - **Continuous batching:** Don't wait for all requests to finish — add new ones as slots free up
   - **Speculative decoding:** Draft model proposes tokens, main model verifies in parallel
   - **FlashAttention/FlashDecoding:** Memory-efficient attention kernels
   - **Tensor parallelism:** Split model across 2 GPUs for lower latency

3. **Infrastructure:**
   - **Hardware:** 2x A100 40GB (tensor parallel) or 1x A100 80GB with INT4
   - **Serving framework:** vLLM (PagedAttention, continuous batching) or TensorRT-LLM
   - **Autoscaling:** Scale GPU instances based on queue depth
   - **Caching:** Cache common prompt prefixes (system prompts)
   - **Load balancing:** Route requests to least-loaded instances

4. **Variable-length handling:**
   - **Continuous batching (vLLM):** Requests join/leave batch dynamically
   - **PagedAttention:** KV-cache allocated in pages (no fragmentation waste)
   - **Prompt caching:** Reuse KV-cache for shared prefixes (system prompt)
   - **Priority queuing:** Short requests get priority for latency SLA
   - **Max length limits:** Cap at reasonable length, stream tokens to client
   - **Budget:** Estimated 4x A100 for 100 concurrent users at 13B INT8 with vLLM

</details>
