# Deep Learning Architectures — Complete Internals Deep Dive

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║           EVERY DL ARCHITECTURE — MATH, INTERNALS, AND TRAINING DETAILS              ║
║       Backpropagation • Optimizers • Loss Functions • Architectures • Modern DL      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 1. BACKPROPAGATION — THE FOUNDATION

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    BACKPROPAGATION — HOW NEURAL NETS LEARN                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  CHAIN RULE: The mathematical foundation                                             │
│  ═══════════════════════════════════════                                              │
│                                                                                      │
│  For: Loss L, output y = f(g(x))                                                    │
│  ∂L/∂x = ∂L/∂y × ∂y/∂g × ∂g/∂x                                                   │
│                                                                                      │
│  Example with 3-layer network:                                                       │
│  ┌─────┐     ┌─────┐     ┌─────┐     ┌──────┐                                     │
│  │  x  │──w₁─│ h₁  │──w₂─│ h₂  │──w₃─│  ŷ   │──── L(ŷ, y)                       │
│  └─────┘     └─────┘     └─────┘     └──────┘                                     │
│                                                                                      │
│  Forward Pass:                                                                       │
│  z₁ = w₁x + b₁;  h₁ = ReLU(z₁)                                                   │
│  z₂ = w₂h₁ + b₂; h₂ = ReLU(z₂)                                                   │
│  z₃ = w₃h₂ + b₃; ŷ = σ(z₃)                                                       │
│  L = -[y log(ŷ) + (1-y) log(1-ŷ)]                                                  │
│                                                                                      │
│  Backward Pass (compute gradients):                                                  │
│  ∂L/∂w₃ = ∂L/∂ŷ × ∂ŷ/∂z₃ × ∂z₃/∂w₃                                             │
│  ∂L/∂w₂ = ∂L/∂ŷ × ∂ŷ/∂z₃ × ∂z₃/∂h₂ × ∂h₂/∂z₂ × ∂z₂/∂w₂                      │
│  ∂L/∂w₁ = ... (chain gets longer for earlier layers)                                │
│                                                                                      │
│  Update:                                                                             │
│  w = w - lr × ∂L/∂w  (for each weight in the network)                              │
│                                                                                      │
│  WHY VANISHING GRADIENTS:                                                            │
│  • Sigmoid: ∂σ/∂z = σ(z)(1-σ(z)), max = 0.25                                      │
│  • Multiply many values < 1 → gradient → 0 for early layers                        │
│  • FIX: ReLU (gradient = 1 for positive), skip connections                         │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. OPTIMIZERS — COMPLETE GUIDE

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    OPTIMIZERS — HOW WEIGHTS ARE UPDATED                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─── SGD (Stochastic Gradient Descent) ─────────────────────────────────────────┐  │
│  │  w = w - lr × g  (where g = ∂L/∂w on a mini-batch)                           │  │
│  │  • Simple but slow convergence, oscillates in ravines                          │  │
│  │  • Learning rate must be carefully tuned                                       │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── SGD + Momentum ────────────────────────────────────────────────────────────┐  │
│  │  v = β×v + g           (accumulate velocity, β=0.9 typically)                 │  │
│  │  w = w - lr × v                                                                │  │
│  │  • Accelerates in consistent direction, dampens oscillations                   │  │
│  │  • Like a ball rolling downhill (builds momentum)                              │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── Nesterov Momentum ─────────────────────────────────────────────────────────┐  │
│  │  v = β×v + ∇L(w - β×v)  (look ahead before computing gradient)               │  │
│  │  w = w - lr × v                                                                │  │
│  │  • "Look before you leap" — corrects overshooting                             │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── AdaGrad ───────────────────────────────────────────────────────────────────┐  │
│  │  s = s + g²           (accumulate squared gradients)                           │  │
│  │  w = w - lr × g / (√s + ε)                                                    │  │
│  │  • Per-parameter learning rates (adapts!)                                      │  │
│  │  • Problem: s grows forever → lr → 0 (learning stops)                         │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── RMSProp ───────────────────────────────────────────────────────────────────┐  │
│  │  s = β×s + (1-β)×g²   (exponential moving average of squared gradients)       │  │
│  │  w = w - lr × g / (√s + ε)                                                    │  │
│  │  • Fixes AdaGrad's dying learning rate problem                                 │  │
│  │  • Works well for RNNs                                                         │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── Adam (Adaptive Moment Estimation) ─── DEFAULT CHOICE ──────────────────────┐  │
│  │  m = β₁×m + (1-β₁)×g        (1st moment: mean of gradients)                  │  │
│  │  v = β₂×v + (1-β₂)×g²       (2nd moment: variance of gradients)              │  │
│  │  m̂ = m/(1-β₁ᵗ)              (bias correction)                                │  │
│  │  v̂ = v/(1-β₂ᵗ)              (bias correction)                                │  │
│  │  w = w - lr × m̂/(√v̂ + ε)                                                     │  │
│  │                                                                                │  │
│  │  Defaults: β₁=0.9, β₂=0.999, ε=1e-8, lr=0.001                               │  │
│  │  • Combines momentum + per-parameter adaptation                               │  │
│  │  • Works well out-of-the-box for most problems                                │  │
│  │  • DEFAULT for most DL training                                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── AdamW (Adam with Weight Decay) ────────────────────────────────────────────┐  │
│  │  Same as Adam but DECOUPLES weight decay from gradient update                  │  │
│  │  w = w - lr × m̂/(√v̂ + ε) - lr × λ × w                                       │  │
│  │  • Fixes a bug in Adam's L2 regularization                                    │  │
│  │  • DEFAULT for Transformers (BERT, GPT, ViT)                                  │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── LAMB / LARS ───────────────────────────────────────────────────────────────┐  │
│  │  Layer-wise Adaptive learning rates                                            │  │
│  │  Scale lr per layer based on ||w|| / ||∇w||                                   │  │
│  │  • Used for LARGE BATCH training (BERT pre-training)                          │  │
│  │  • Enables batch size 64K+ without accuracy loss                              │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  SUMMARY: Which optimizer to use?                                                    │
│  • General DL: Adam or AdamW (start here)                                           │
│  • Transformers: AdamW with warmup + cosine decay                                   │
│  • Vision (CNNs): SGD + Momentum + cosine LR (often better than Adam!)             │
│  • Large batch: LAMB or LARS                                                        │
│  • Fine-tuning: AdamW with very low lr (1e-5 to 5e-5)                              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. LOSS FUNCTIONS — COMPLETE REFERENCE

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    LOSS FUNCTIONS                                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  CLASSIFICATION:                                                                     │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Loss            │ Formula                    │ Use Case            │              │
│  │─────────────────│────────────────────────────│─────────────────────│              │
│  │ Binary CE       │ -[y log(ŷ)+(1-y)log(1-ŷ)]│ Binary classification│             │
│  │ Categorical CE  │ -Σ yₖ log(ŷₖ)            │ Multi-class          │              │
│  │ Focal Loss      │ -αₜ(1-pₜ)^γ log(pₜ)      │ Class imbalance      │              │
│  │ Label Smoothing │ CE with soft targets      │ Prevent overconfidence│              │
│  │ Hinge Loss      │ max(0, 1 - y×ŷ)          │ SVM-style margin     │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  REGRESSION:                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Loss            │ Formula                    │ Use Case            │              │
│  │─────────────────│────────────────────────────│─────────────────────│              │
│  │ MSE (L2)        │ (1/n) Σ(y-ŷ)²            │ Standard regression  │              │
│  │ MAE (L1)        │ (1/n) Σ|y-ŷ|             │ Robust to outliers   │              │
│  │ Huber           │ L2 if |err|<δ, L1 otherwise│ Best of both worlds │              │
│  │ Log-Cosh        │ log(cosh(y-ŷ))            │ Smooth Huber approx  │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  DETECTION / SEGMENTATION:                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Loss            │ Formula                    │ Use Case            │              │
│  │─────────────────│────────────────────────────│─────────────────────│              │
│  │ IoU Loss        │ 1 - IoU(pred, target)      │ Bounding box         │              │
│  │ GIoU / CIoU     │ IoU + penalty terms        │ Better box regression│              │
│  │ Dice Loss       │ 1 - 2|A∩B|/(|A|+|B|)     │ Segmentation         │              │
│  │ Focal Loss      │ Down-weight easy examples  │ Dense detection      │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  GENERATIVE / CONTRASTIVE:                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Loss            │ Use Case                                         │              │
│  │─────────────────│─────────────────────────────────────────────────│              │
│  │ GAN Loss        │ Generator vs Discriminator adversarial           │              │
│  │ KL Divergence   │ VAE (match latent to prior distribution)        │              │
│  │ Contrastive     │ Siamese networks (same/different pairs)         │              │
│  │ Triplet Loss    │ Anchor, positive, negative (embeddings)         │              │
│  │ InfoNCE / NT-Xent│ CLIP, SimCLR (contrastive learning)           │              │
│  │ Diffusion Loss  │ Predict noise added at each timestep            │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  NLP / LANGUAGE MODELING:                                                            │
│  • Cross-Entropy over vocabulary (next token prediction)                            │
│  • CTC Loss (Connectionist Temporal Classification — ASR)                          │
│  • RLHF: PPO loss on reward model scores                                           │
│  • DPO (Direct Preference Optimization): No reward model needed                    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. LEARNING RATE SCHEDULES

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    LEARNING RATE SCHEDULES                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHY? Fixed LR is suboptimal: need HIGH lr early (explore), LOW lr late (converge)  │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐                │
│  │ Schedule          │ Formula / Behavior           │ Use Case     │                │
│  │───────────────────│──────────────────────────────│──────────────│                │
│  │ Step Decay        │ lr × γ every N epochs        │ Simple CNNs  │                │
│  │ Exponential Decay │ lr × γᵗ                      │ General      │                │
│  │ Cosine Annealing  │ lr × ½(1+cos(πt/T))         │ Transformers │                │
│  │ Warmup + Cosine   │ Linear 0→lr, then cosine    │ BERT, ViT    │                │
│  │ OneCycleLR        │ Ramp up → Ramp down          │ Fast training│                │
│  │ ReduceOnPlateau   │ Reduce when val loss stalls  │ Adaptive     │                │
│  │ Cyclic LR         │ Oscillate between min/max    │ Explore more │                │
│  └─────────────────────────────────────────────────────────────────┘                │
│                                                                                      │
│  WARMUP (Critical for Transformers):                                                 │
│  • Start LR from ~0, linearly increase to target over N steps                      │
│  • WHY: Random weights produce wild gradients early; warmup stabilizes              │
│  • Typical: 1000-10000 warmup steps for BERT-scale models                          │
│                                                                                      │
│  COSINE ANNEALING (Most Popular for modern DL):                                      │
│  lr(t) = lr_min + ½(lr_max - lr_min)(1 + cos(π × t/T_max))                        │
│  • Smooth decay, no sudden drops                                                    │
│  • Often with warmup: Warmup(1K steps) → Cosine(rest of training)                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. CNN — COMPLETE INTERNALS

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    CNN — HOW CONVOLUTION ACTUALLY WORKS                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  CONVOLUTION OPERATION:                                                              │
│  ═══════════════════════                                                             │
│  Input: 5×5 image,  Kernel: 3×3 filter                                              │
│                                                                                      │
│  [1 0 1 0 1]     [1 0 1]                                                            │
│  [0 1 0 1 0]  ×  [0 1 0]  → slide and multiply-sum → Feature Map                  │
│  [1 0 1 0 1]     [1 0 1]                                                            │
│  [0 1 0 1 0]                                                                        │
│  [1 0 1 0 1]                                                                        │
│                                                                                      │
│  Output size = (input - kernel + 2×padding) / stride + 1                            │
│  = (5 - 3 + 0) / 1 + 1 = 3×3 feature map                                          │
│                                                                                      │
│  KEY CONCEPTS:                                                                       │
│  • Stride: How many pixels to move the kernel (1=overlap, 2=skip)                   │
│  • Padding: Add zeros around border ('same'=output same size)                       │
│  • Channels: RGB=3 input channels, kernels are 3D (k×k×c_in)                       │
│  • Multiple filters = multiple output feature maps                                  │
│                                                                                      │
│  PARAMETERS:                                                                         │
│  Conv layer with 64 filters of 3×3 on 32-channel input:                             │
│  Parameters = 64 × (3 × 3 × 32 + 1) = 18,496                                      │
│  (Much less than fully-connected: 64×H×W×32 = millions)                             │
│                                                                                      │
│  WHY CNNs WORK:                                                                      │
│  1. TRANSLATION INVARIANCE: Same filter everywhere = same feature detected          │
│  2. LOCAL CONNECTIVITY: Each neuron sees only a small region                        │
│  3. PARAMETER SHARING: One filter used across entire image = fewer params           │
│  4. HIERARCHICAL FEATURES: Early layers=edges, deeper=objects                       │
│                                                                                      │
│  POOLING:                                                                            │
│  • Max Pool (2×2, stride 2): Take max of each 2×2 region → halve size             │
│  • Avg Pool: Average of each region                                                 │
│  • Global Average Pool: One value per channel (before final FC layer)               │
│  • Purpose: Reduce spatial dimensions, add translation invariance                   │
│                                                                                      │
│  MODERN CNN BLOCKS:                                                                  │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Block          │ Innovation                  │ Used In            │              │
│  │────────────────│─────────────────────────────│────────────────────│              │
│  │ Residual       │ x + F(x) skip connection   │ ResNet             │              │
│  │ Inception      │ Multiple kernel sizes        │ GoogLeNet          │              │
│  │ Depthwise Sep. │ Spatial + channel separate  │ MobileNet          │              │
│  │ Squeeze-Excite │ Channel attention           │ SENet, EfficientNet│              │
│  │ Inverted Res.  │ Expand→Depthwise→Project    │ MobileNetV2        │              │
│  │ Dense          │ Connect all previous layers │ DenseNet           │              │
│  │ ConvNeXt       │ Modernized CNN (like ViT)   │ ConvNeXt           │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  RESNET SKIP CONNECTION (Most important innovation):                                 │
│  ────────────────────────────────────────────────────                                │
│       x ──────────────────┐                                                          │
│       │                    │ (identity shortcut)                                      │
│       ▼                    │                                                          │
│  [Conv → BN → ReLU]      │                                                          │
│       │                    │                                                          │
│       ▼                    │                                                          │
│  [Conv → BN]              │                                                          │
│       │                    │                                                          │
│       ▼                    ▼                                                          │
│      (+) ← element-wise add                                                         │
│       │                                                                              │
│       ▼                                                                              │
│     [ReLU]                                                                           │
│                                                                                      │
│  WHY: Gradients flow directly through identity path → train 100+ layers            │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. TRANSFORMER — COMPLETE INTERNALS

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    TRANSFORMER — EVERY COMPONENT EXPLAINED                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  SELF-ATTENTION MECHANISM (in detail):                                               │
│  ═════════════════════════════════════                                                │
│                                                                                      │
│  Input: Sequence of token embeddings [x₁, x₂, ..., xₙ] ∈ R^(n×d)                  │
│                                                                                      │
│  Step 1: Project to Q, K, V                                                         │
│  Q = X × Wq  (Query: "what am I looking for?")                                     │
│  K = X × Wk  (Key: "what do I contain?")                                           │
│  V = X × Wv  (Value: "what info do I provide?")                                    │
│                                                                                      │
│  Step 2: Compute attention scores                                                    │
│  Scores = Q × Kᵀ / √d_k                                                            │
│  (√d_k scaling prevents softmax saturation for large d)                             │
│                                                                                      │
│  Step 3: Apply softmax (per row)                                                    │
│  Attention_weights = softmax(Scores)  → each row sums to 1                         │
│                                                                                      │
│  Step 4: Weighted sum of values                                                      │
│  Output = Attention_weights × V                                                      │
│                                                                                      │
│  FULL FORMULA:                                                                       │
│  Attention(Q,K,V) = softmax(QKᵀ/√d_k) × V                                         │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────                   │
│                                                                                      │
│  MULTI-HEAD ATTENTION:                                                               │
│  ═════════════════════                                                               │
│  Instead of one attention, use h parallel "heads" (h=8 or 12 typically):            │
│  • Split d_model into h heads: d_k = d_model/h                                     │
│  • Each head learns different attention patterns                                    │
│  • Head 1 might attend to syntax, Head 2 to semantics, etc.                        │
│  • Concat all heads → linear projection                                            │
│                                                                                      │
│  MultiHead(Q,K,V) = Concat(head₁,...,headₕ) × W_O                                  │
│  Where headᵢ = Attention(QWᵢQ, KWᵢK, VWᵢV)                                        │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────                   │
│                                                                                      │
│  POSITIONAL ENCODING:                                                                │
│  ═════════════════════                                                               │
│  Problem: Attention is permutation-invariant (no notion of ORDER)                   │
│  Solution: Add position information to embeddings                                    │
│                                                                                      │
│  Sinusoidal (original):                                                              │
│  PE(pos, 2i) = sin(pos / 10000^(2i/d))                                             │
│  PE(pos, 2i+1) = cos(pos / 10000^(2i/d))                                           │
│                                                                                      │
│  Learned (BERT, GPT): Trainable embedding per position                              │
│  RoPE (LLaMA, modern): Rotary Position Embedding (relative + extrapolates)         │
│  ALiBi (BLOOM): Attention bias based on distance                                    │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────                   │
│                                                                                      │
│  FEED-FORWARD NETWORK (per position):                                                │
│  FFN(x) = GELU(x × W₁ + b₁) × W₂ + b₂                                            │
│  Typically: d_model → 4×d_model → d_model                                          │
│  (Expand and compress — like a bottleneck in reverse)                               │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────                   │
│                                                                                      │
│  LAYER NORMALIZATION:                                                                │
│  LayerNorm(x) = γ × (x - μ) / (σ + ε) + β                                         │
│  • Normalizes across features (not batch)                                            │
│  • Pre-LN (modern): Norm BEFORE attention (more stable training)                    │
│  • Post-LN (original): Norm AFTER attention                                         │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────                   │
│                                                                                      │
│  COMPLETE TRANSFORMER BLOCK:                                                         │
│  x = x + MultiHeadAttention(LayerNorm(x))    ← Pre-LN variant                     │
│  x = x + FFN(LayerNorm(x))                                                         │
│                                                                                      │
│  ─────────────────────────────────────────────────────────────────                   │
│                                                                                      │
│  ATTENTION VARIANTS (Modern):                                                        │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Variant              │ Innovation                    │ Used In    │              │
│  │──────────────────────│───────────────────────────────│────────────│              │
│  │ Multi-Head (MHA)     │ Original parallel heads       │ BERT, GPT-2│              │
│  │ Multi-Query (MQA)    │ Shared K,V across heads       │ PaLM       │              │
│  │ Grouped-Query (GQA)  │ Groups of heads share K,V     │ LLaMA-2    │              │
│  │ Flash Attention      │ IO-aware, tiled computation   │ All modern │              │
│  │ Sparse Attention     │ Only attend to subset         │ BigBird    │              │
│  │ Sliding Window       │ Local attention + global      │ Mistral    │              │
│  │ Linear Attention     │ Approximate with kernel       │ Performer  │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  CAUSAL MASKING (for generation/decoder-only):                                       │
│  Token at position i can only attend to positions ≤ i                               │
│  Implemented via mask matrix: upper triangle = -∞ before softmax                   │
│                                                                                      │
│  KV-CACHE (Inference optimization):                                                  │
│  • Cache K,V from previous tokens during autoregressive generation                  │
│  • Only compute Q for new token → O(n) not O(n²) per step                          │
│  • But memory grows linearly with sequence length                                   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. BATCH NORMALIZATION vs LAYER NORMALIZATION

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    NORMALIZATION TECHNIQUES                                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  Batch Norm (BatchNorm):                                                             │
│  • Normalize across BATCH dimension for each feature                                │
│  • μ, σ computed from mini-batch during training                                    │
│  • Running stats used during inference                                               │
│  • Used in: CNNs (ResNet, EfficientNet)                                             │
│  • Problem: Depends on batch size; fails with small batches                         │
│                                                                                      │
│  Layer Norm (LayerNorm):                                                             │
│  • Normalize across FEATURE dimension for each sample                               │
│  • Independent of batch size                                                        │
│  • Used in: Transformers (BERT, GPT, ViT)                                          │
│                                                                                      │
│  Group Norm:                                                                         │
│  • Normalize within GROUPS of channels                                              │
│  • Used in: Object detection, small batch training                                  │
│                                                                                      │
│  RMSNorm:                                                                            │
│  • Simplified LayerNorm without mean subtraction                                    │
│  • RMSNorm(x) = x / RMS(x) × γ                                                    │
│  • Faster, used in: LLaMA, Mistral                                                 │
│                                                                                      │
│         BatchNorm    LayerNorm    GroupNorm    InstanceNorm                          │
│         (across N)   (across C)   (groups of C) (per channel)                       │
│  Tensor: [N, C, H, W]                                                               │
│  BatchNorm normalizes along N (batch)                                                │
│  LayerNorm normalizes along C, H, W (all features)                                  │
│  GroupNorm normalizes along subsets of C                                             │
│  InstanceNorm normalizes along H, W (per sample, per channel)                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. MODERN ARCHITECTURES — STATE SPACE MODELS & MoE

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    BEYOND TRANSFORMERS — EMERGING ARCHITECTURES                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─── MAMBA / STATE SPACE MODELS (SSMs) ─────────────────────────────────────────┐  │
│  │                                                                                │  │
│  │  Problem with Transformers: O(n²) attention for sequence length n              │  │
│  │                                                                                │  │
│  │  SSM Solution: Model sequence as continuous dynamical system                   │  │
│  │  x'(t) = Ax(t) + Bu(t)                                                       │  │
│  │  y(t) = Cx(t) + Du(t)                                                        │  │
│  │                                                                                │  │
│  │  Mamba (2023) adds:                                                            │  │
│  │  • Selective mechanism (input-dependent parameters)                            │  │
│  │  • Hardware-aware implementation                                               │  │
│  │  • LINEAR complexity O(n) instead of O(n²)!                                   │  │
│  │                                                                                │  │
│  │  Status: Competitive with Transformers on some benchmarks                     │  │
│  │  Used in: Mamba-2, Jamba (hybrid), some vision models                         │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── MIXTURE OF EXPERTS (MoE) ──────────────────────────────────────────────────┐  │
│  │                                                                                │  │
│  │  Problem: Larger models = better but slower & costlier                         │  │
│  │  Solution: Many expert sub-networks, activate only a FEW per token            │  │
│  │                                                                                │  │
│  │  Architecture:                                                                 │  │
│  │  Input → [Router/Gate] → selects top-K experts (out of N)                     │  │
│  │              │                                                                 │  │
│  │     ┌────── ┼ ──────┐                                                         │  │
│  │     ▼       ▼       ▼                                                         │  │
│  │  [Expert1][Expert2]...[Expert N]  (only K are activated)                      │  │
│  │     │       │                                                                  │  │
│  │     └───────┘                                                                  │  │
│  │         ▼                                                                      │  │
│  │  Weighted sum of active expert outputs                                        │  │
│  │                                                                                │  │
│  │  Benefits:                                                                     │  │
│  │  • Total params: 1.8T (GPT-4 rumored) but active: ~200B per token            │  │
│  │  • 6-12x compute savings at inference                                         │  │
│  │  • Better quality for same compute budget                                     │  │
│  │                                                                                │  │
│  │  Used in: GPT-4 (rumored), Mixtral 8x7B, Switch Transformer, GShard          │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. TRAINING TECHNIQUES — DISTRIBUTED & EFFICIENT

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED & EFFICIENT TRAINING                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  DATA PARALLELISM (DDP):                                                             │
│  • Same model on every GPU, different data per GPU                                  │
│  • Gradients averaged across GPUs (AllReduce)                                       │
│  • Effective batch size = per_GPU_batch × num_GPUs                                  │
│  • Simplest distributed strategy                                                    │
│                                                                                      │
│  MODEL PARALLELISM:                                                                  │
│  • Model too large for one GPU → split across GPUs                                 │
│  • Tensor Parallelism: Split individual layers (Megatron-LM)                       │
│  • Pipeline Parallelism: Different layers on different GPUs                         │
│                                                                                      │
│  FSDP (Fully Sharded Data Parallelism):                                              │
│  • Shard model parameters, gradients, and optimizer states                          │
│  • Each GPU holds only 1/N of the model                                            │
│  • AllGather before compute, ReduceScatter after                                    │
│  • Used in: PyTorch FSDP, DeepSpeed ZeRO                                           │
│                                                                                      │
│  MIXED PRECISION TRAINING:                                                           │
│  • Forward pass: FP16 (half precision) — 2x memory savings                        │
│  • Loss scaling: Multiply loss before backward to prevent underflow                 │
│  • Master weights: Kept in FP32 for stability                                      │
│  • 1.5-2x speedup on modern GPUs (Tensor Cores)                                   │
│                                                                                      │
│  GRADIENT ACCUMULATION:                                                              │
│  • Can't fit large batch? Accumulate gradients over N mini-batches                 │
│  • Update weights only every N steps                                                │
│  • Effective batch = mini_batch × accumulation_steps                                │
│                                                                                      │
│  GRADIENT CHECKPOINTING:                                                             │
│  • Don't store all activations (memory expensive)                                   │
│  • Recompute during backward pass (trade compute for memory)                        │
│  • Reduces memory by ~60% with ~20% compute overhead                               │
│                                                                                      │
│  PARAMETER-EFFICIENT FINE-TUNING (PEFT):                                             │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Method          │ Params Trained │ How it works                    │              │
│  │─────────────────│───────────────│─────────────────────────────────│              │
│  │ Full Fine-tune  │ 100% (all)    │ Update all model weights        │              │
│  │ LoRA            │ 0.1-1%        │ Low-rank adapters on Q,V,K     │              │
│  │ QLoRA           │ 0.1-1%        │ LoRA + 4-bit quantized base    │              │
│  │ Prefix Tuning   │ <1%           │ Learnable prefix tokens        │              │
│  │ Adapters        │ 1-5%          │ Small modules inserted in layers│              │
│  │ Prompt Tuning   │ <0.01%        │ Learn soft prompt embeddings   │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  LoRA DETAILS:                                                                       │
│  • Original: W (d×d matrix, e.g., 4096×4096)                                       │
│  • LoRA: W + ΔW where ΔW = A×B (A is d×r, B is r×d, rank r=8-64)                 │
│  • Only train A and B: r×d + r×d << d×d parameters                                │
│  • At inference: Merge W+AB → no extra latency                                     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. MODEL COMPRESSION — QUANTIZATION, PRUNING, DISTILLATION

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    MODEL COMPRESSION TECHNIQUES                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  QUANTIZATION (Reduce precision):                                                    │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Type              │ Precision │ Size Reduction │ Quality Impact    │              │
│  │───────────────────│───────────│────────────────│───────────────────│              │
│  │ FP32 (baseline)   │ 32 bit   │ 1x             │ Full quality      │              │
│  │ FP16 / BF16       │ 16 bit   │ 2x             │ Minimal loss      │              │
│  │ INT8 (PTQ)        │ 8 bit    │ 4x             │ Small loss        │              │
│  │ INT4 (GPTQ/AWQ)   │ 4 bit    │ 8x             │ Moderate loss     │              │
│  │ INT2/3 (research) │ 2-3 bit  │ 10-16x         │ Noticeable loss   │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  Methods:                                                                            │
│  • Post-Training Quantization (PTQ): Quantize after training                        │
│  • Quantization-Aware Training (QAT): Simulate quantization during training         │
│  • GPTQ: Weight-only quantization for LLMs                                         │
│  • AWQ: Activation-aware weight quantization                                        │
│  • GGML/GGUF: Quantized format for running LLMs on CPU                             │
│                                                                                      │
│  PRUNING (Remove unnecessary weights):                                               │
│  • Unstructured: Zero out individual weights (hard to accelerate)                   │
│  • Structured: Remove entire channels/heads (GPU-friendly)                          │
│  • Magnitude pruning: Remove smallest weights                                       │
│  • Movement pruning: Remove weights moving toward zero during training              │
│  • Typical: 80-90% weights can be pruned with <1% accuracy loss                   │
│                                                                                      │
│  KNOWLEDGE DISTILLATION:                                                             │
│  • Teacher: Large model (e.g., BERT-large)                                         │
│  • Student: Small model (e.g., DistilBERT — 60% of BERT, 97% performance)         │
│  • Train student to match teacher's soft predictions (not just labels)              │
│  • Loss = α×CE(student, labels) + (1-α)×KL(student_logits, teacher_logits)        │
│  • Examples: DistilBERT, TinyBERT, MobileNet (from ResNet)                         │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. SELF-SUPERVISED LEARNING — PRE-TRAINING METHODS

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    SELF-SUPERVISED LEARNING METHODS                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  KEY IDEA: Learn representations from UNLABELED data by creating pretext tasks       │
│                                                                                      │
│  FOR NLP:                                                                            │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Method                  │ Task                     │ Model        │              │
│  │─────────────────────────│──────────────────────────│──────────────│              │
│  │ Masked Language Model   │ Predict masked tokens    │ BERT         │              │
│  │ Causal Language Model   │ Predict next token       │ GPT          │              │
│  │ Denoising               │ Reconstruct corrupted text│ T5, BART    │              │
│  │ Contrastive             │ Distinguish similar pairs │ SimCSE      │              │
│  │ Span Corruption         │ Predict removed spans    │ T5           │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  FOR VISION:                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Method                  │ Task                     │ Model        │              │
│  │─────────────────────────│──────────────────────────│──────────────│              │
│  │ Contrastive (SimCLR)    │ Same image, diff augments│ SimCLR       │              │
│  │ Momentum Contrast       │ Slow-updating target net │ MoCo v1/v2/v3│              │
│  │ Self-Distillation       │ Student matches teacher  │ BYOL, DINO   │              │
│  │ Masked Image Modeling   │ Predict masked patches   │ MAE, BEiT    │              │
│  │ CLIP (multimodal)       │ Match image↔text pairs   │ CLIP, ALIGN  │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  CONTRASTIVE LEARNING (SimCLR):                                                      │
│  1. Take image x                                                                    │
│  2. Create two augmented views: x₁, x₂ (crop, flip, color jitter)                 │
│  3. Encode both: z₁ = f(x₁), z₂ = f(x₂)                                          │
│  4. Loss: Pull z₁, z₂ together; push apart from other images' views               │
│  5. NT-Xent loss: -log(exp(sim(z₁,z₂)/τ) / Σⱼ exp(sim(z₁,zⱼ)/τ))               │
│                                                                                      │
│  MASKED AUTOENCODERS (MAE):                                                         │
│  1. Split image into patches                                                        │
│  2. Mask 75% of patches randomly                                                    │
│  3. Encode visible patches with Transformer                                         │
│  4. Decode to reconstruct original image                                            │
│  5. Loss: MSE on masked patches only                                                │
│  → Learns incredible visual representations WITHOUT labels                          │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. DIFFUSION MODELS — INTERNALS

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    DIFFUSION MODELS — HOW THEY WORK                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  KEY IDEA: Learn to gradually denoise images                                         │
│                                                                                      │
│  FORWARD PROCESS (add noise, T steps):                                               │
│  x₀ (clean) → x₁ (little noise) → ... → xₜ (pure Gaussian noise)                  │
│  q(xₜ|xₜ₋₁) = N(xₜ; √(1-βₜ)xₜ₋₁, βₜI)                                          │
│                                                                                      │
│  REVERSE PROCESS (denoise, learned):                                                 │
│  xₜ (noise) → xₜ₋₁ (less noise) → ... → x₀ (clean image!)                        │
│  pθ(xₜ₋₁|xₜ) = N(xₜ₋₁; μθ(xₜ,t), Σθ(xₜ,t))                                    │
│                                                                                      │
│  TRAINING:                                                                           │
│  1. Sample clean image x₀                                                           │
│  2. Sample random timestep t                                                         │
│  3. Add noise: xₜ = √ᾱₜx₀ + √(1-ᾱₜ)ε  (where ε ~ N(0,I))                       │
│  4. Train model to predict the noise: L = ||ε - εθ(xₜ, t)||²                       │
│                                                                                      │
│  INFERENCE (Generate image):                                                         │
│  1. Start with pure noise xₜ ~ N(0,I)                                              │
│  2. For t = T, T-1, ..., 1:                                                         │
│     Predict noise εθ(xₜ, t), compute xₜ₋₁                                         │
│  3. Output x₀ (generated image!)                                                    │
│                                                                                      │
│  CONDITIONAL GENERATION (Text→Image):                                                │
│  • Classifier-free guidance: Train with/without text condition                      │
│  • ε_guided = ε_unconditional + w×(ε_conditional - ε_unconditional)                │
│  • w > 1: More adherent to text (guidance scale)                                   │
│                                                                                      │
│  ARCHITECTURES:                                                                      │
│  • U-Net with attention: Stable Diffusion, DALL-E 2                                │
│  • DiT (Diffusion Transformer): Newer, scales better                               │
│  • Latent Diffusion: Work in compressed latent space (faster!)                      │
│    Image → [VAE Encode] → Latent → [Diffuse here] → [VAE Decode] → Image         │
│                                                                                      │
│  Used in: Stable Diffusion, DALL-E 3, Midjourney, Sora (video)                     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. GAN — INTERNALS

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    GANs — HOW ADVERSARIAL TRAINING WORKS                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  TWO-PLAYER GAME:                                                                    │
│  • Generator G: Creates fake data to fool Discriminator                             │
│  • Discriminator D: Distinguishes real from fake                                    │
│                                                                                      │
│  TRAINING LOOP:                                                                      │
│  1. Train D: max log(D(real)) + log(1-D(G(z)))                                     │
│     (D wants to correctly classify real as 1, fake as 0)                            │
│  2. Train G: max log(D(G(z)))                                                       │
│     (G wants D to classify its fakes as 1)                                          │
│                                                                                      │
│  min_G max_D  E[log D(x)] + E[log(1-D(G(z)))]                                     │
│                                                                                      │
│  TRAINING CHALLENGES:                                                                │
│  • Mode collapse: G produces limited variety                                        │
│  • Training instability: G and D oscillate                                          │
│  • Vanishing gradients: D too good → G can't learn                                 │
│                                                                                      │
│  VARIANTS:                                                                           │
│  • DCGAN: Conv/deconv architecture (stable training)                                │
│  • WGAN: Wasserstein distance (better gradients)                                    │
│  • StyleGAN: Style-based, progressive growing (high-quality faces)                  │
│  • CycleGAN: Unpaired image-to-image translation                                   │
│  • Pix2Pix: Paired image-to-image (edges→photo)                                    │
│  • ProGAN: Progressive resolution increase during training                          │
│                                                                                      │
│  Status: Largely REPLACED by Diffusion models for generation (2022+)                │
│  Still used: Super-resolution, style transfer, domain adaptation                    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. GRAPH NEURAL NETWORKS (GNN)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    GRAPH NEURAL NETWORKS                                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT: Neural networks for GRAPH-structured data (nodes + edges)                    │
│  WHERE: Social networks, molecules, knowledge graphs, maps                          │
│                                                                                      │
│  CORE IDEA — Message Passing:                                                        │
│  For each node v:                                                                    │
│  1. AGGREGATE messages from neighbors: m_v = AGG({h_u : u ∈ N(v)})                 │
│  2. UPDATE node representation: h_v = UPDATE(h_v, m_v)                              │
│  3. Repeat for K layers (K-hop neighborhood)                                        │
│                                                                                      │
│  VARIANTS:                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Model        │ Aggregation            │ Key Feature               │              │
│  │──────────────│────────────────────────│───────────────────────────│              │
│  │ GCN          │ Mean of neighbors      │ Spectral theory based     │              │
│  │ GraphSAGE    │ Sample + aggregate     │ Inductive (new nodes)     │              │
│  │ GAT          │ Attention-weighted     │ Learn edge importance     │              │
│  │ GIN          │ Sum (most expressive)  │ WL-test equivalent        │              │
│  │ MPNN         │ General framework      │ Unifies many GNNs        │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  USE CASES:                                                                          │
│  • Drug discovery (molecular property prediction)                                   │
│  • Social network analysis (community detection)                                    │
│  • Recommendation (user-item graph)                                                  │
│  • Traffic prediction (road network graph)                                          │
│  • Fraud detection (transaction graph)                                              │
│  • Knowledge graph completion                                                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 15. RLHF & DPO — LLM ALIGNMENT

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    RLHF & DPO — ALIGNING LLMs                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  RLHF (Reinforcement Learning from Human Feedback):                                  │
│  ═══════════════════════════════════════════════════                                  │
│  Step 1: Supervised Fine-Tuning (SFT)                                                │
│    Pre-trained LLM → Fine-tune on instruction-response pairs                        │
│                                                                                      │
│  Step 2: Train Reward Model                                                          │
│    • Show humans pairs of responses: (response_A, response_B)                       │
│    • Humans say which is better                                                      │
│    • Train model to predict human preference                                        │
│    • Loss: -log(σ(r(chosen) - r(rejected)))  (Bradley-Terry model)                 │
│                                                                                      │
│  Step 3: PPO Optimization                                                            │
│    • Generate responses from policy                                                  │
│    • Score with reward model                                                        │
│    • Update policy to maximize reward while staying close to SFT model              │
│    • KL penalty: reward - β × KL(policy || reference)                               │
│                                                                                      │
│  DPO (Direct Preference Optimization):                                               │
│  ══════════════════════════════════════                                               │
│  • Skip reward model entirely!                                                       │
│  • Directly optimize policy from preference data                                    │
│  • Loss: -log σ(β × (log π(chosen)/π_ref(chosen) - log π(rejected)/π_ref(rejected)))│
│  • Simpler, more stable, no RL needed                                                │
│  • Used in: Many modern LLMs (Zephyr, etc.)                                        │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SUMMARY: DL ARCHITECTURE CHEAT SHEET

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Architecture    │ Best For                │ Key Innovation              │ Era        │
│  ════════════════│═════════════════════════│═════════════════════════════│══════════ │
│  MLP             │ Tabular (small)         │ Universal approximation     │ 1980s     │
│  CNN             │ Images, spatial data    │ Local connectivity, sharing │ 1998-2020 │
│  ResNet          │ Deep image models       │ Skip connections            │ 2015      │
│  RNN/LSTM        │ Sequences (legacy)      │ Memory, gating              │ 1997-2017 │
│  Transformer     │ EVERYTHING (dominant)   │ Self-attention, parallel    │ 2017+     │
│  GAN             │ Image generation        │ Adversarial training        │ 2014-2022 │
│  Diffusion       │ Image/video generation  │ Gradual denoising           │ 2020+     │
│  ViT             │ Image classification    │ Patches as tokens           │ 2020+     │
│  GNN             │ Graph data              │ Message passing             │ 2016+     │
│  Mamba/SSM       │ Long sequences          │ Linear complexity           │ 2023+     │
│  MoE             │ Scale efficiently       │ Sparse activation           │ 2022+     │
│                                                                                      │
│  THE TREND: Transformers + MoE + Flash Attention = scale to trillions of params     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

*Next: [10-Frameworks-and-Tools-Ecosystem.md](./10-Frameworks-and-Tools-Ecosystem.md) — Complete tools guide →*
