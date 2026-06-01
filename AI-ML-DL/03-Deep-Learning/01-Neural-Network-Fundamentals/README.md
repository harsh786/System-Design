# Neural Network Fundamentals

## 1. Biological Neuron vs Artificial Neuron

### Biological Neuron
```
    Dendrites          Cell Body          Axon          Synapse
    (inputs)           (processing)       (output)      (connection)
    
     ╲  │  ╱          ┌────────┐         ─────────────○
      ╲ │ ╱           │        │        /
       ╲│╱            │  Soma  │───────/
        ●─────────────│        │
       ╱│╲            │        │───────\
      ╱ │ ╲           └────────┘        \
     ╱  │  ╲                             ─────────────○
```

### Artificial Neuron
```
    x₁ ──w₁──╲
                ╲
    x₂ ──w₂────→ Σ + b ──→ f(z) ──→ output (ŷ)
                ╱
    x₃ ──w₃──╱

    z = w₁x₁ + w₂x₂ + w₃x₃ + b = wᵀx + b
    ŷ = f(z)    where f is the activation function
```

| Biological | Artificial |
|-----------|-----------|
| Dendrites | Input features (x) |
| Synaptic weights | Learnable weights (w) |
| Cell body | Weighted sum + bias |
| Activation potential | Activation function |
| Axon output | Neuron output |

## 2. Perceptron and Multi-Layer Perceptron

### Single Perceptron (Rosenblatt, 1958)

```python
# Perceptron: binary classifier
class Perceptron:
    def __init__(self, n_features, lr=0.01):
        self.weights = np.zeros(n_features)
        self.bias = 0
        self.lr = lr
    
    def predict(self, x):
        z = np.dot(self.weights, x) + self.bias
        return 1 if z >= 0 else 0
    
    def train(self, X, y, epochs=100):
        for _ in range(epochs):
            for xi, yi in zip(X, y):
                pred = self.predict(xi)
                error = yi - pred
                self.weights += self.lr * error * xi
                self.bias += self.lr * error
```

**Limitation**: Can only learn linearly separable functions (cannot learn XOR).

### Multi-Layer Perceptron (MLP)

```
Input Layer      Hidden Layer 1     Hidden Layer 2     Output Layer
(features)       (learned repr)     (learned repr)     (prediction)

  x₁ ○──────────○ h₁⁽¹⁾──────────○ h₁⁽²⁾──────────○ ŷ₁
       ╲        ╱╲              ╱╲              ╱
        ╲      ╱  ╲            ╱  ╲            ╱
  x₂ ○──╲────╱────╲──────────╱────╲──────────╱───○ ŷ₂
        ╲╲  ╱╱    ╲╲        ╱╱    ╲╲        ╱╱
         ╲╲╱╱      ╲╲      ╱╱      ╲╲      ╱╱
  x₃ ○───╳╳────────○ h₂⁽¹⁾──────────○ h₂⁽²⁾──────────○ ŷ₃
         ╱╱╲╲      ╱╱      ╲╲      ╱╱      ╲╲
        ╱╱  ╲╲    ╱╱        ╲╲    ╱╱        ╲╲
  x₄ ○──╱────╲────╱──────────╲────╱──────────╲───
       ╱        ╲              ╲              ╲
      ╱          ╲              ╲              ╲
  x₅ ○──────────○ h₃⁽¹⁾──────────○ h₃⁽²⁾
```

```python
import torch
import torch.nn as nn

class MLP(nn.Module):
    def __init__(self, input_dim, hidden_dims, output_dim):
        super().__init__()
        layers = []
        prev_dim = input_dim
        for h_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, h_dim))
            layers.append(nn.ReLU())
            layers.append(nn.BatchNorm1d(h_dim))
            layers.append(nn.Dropout(0.3))
            prev_dim = h_dim
        layers.append(nn.Linear(prev_dim, output_dim))
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)

# Usage
model = MLP(input_dim=784, hidden_dims=[512, 256, 128], output_dim=10)
```

## 3. Activation Functions

### Comparison Table

| Function | Formula | Range | Derivative | Use Case |
|----------|---------|-------|-----------|----------|
| Sigmoid | σ(z) = 1/(1+e⁻ᶻ) | (0,1) | σ(z)(1-σ(z)) | Binary output, gates |
| Tanh | tanh(z) = (eᶻ-e⁻ᶻ)/(eᶻ+e⁻ᶻ) | (-1,1) | 1-tanh²(z) | Hidden layers (legacy) |
| ReLU | max(0,z) | [0,∞) | 0 if z<0, 1 if z>0 | Default hidden layers |
| Leaky ReLU | max(αz,z), α=0.01 | (-∞,∞) | α if z<0, 1 if z>0 | Avoid dead neurons |
| GELU | z·Φ(z) | (-0.17,∞) | Complex | Transformers |
| Swish | z·σ(z) | (-0.28,∞) | σ(z)+z·σ(z)(1-σ(z)) | EfficientNet |
| Softmax | eᶻⁱ/Σeᶻʲ | (0,1), sum=1 | - | Multi-class output |

### Visualization (ASCII)

```
Sigmoid                  ReLU                    Leaky ReLU
  1 ┤      ╭────         │      ╱               │      ╱
    │     ╱              │     ╱                │     ╱
    │    ╱               │    ╱                 │    ╱
0.5 ┤───╱───             │   ╱                  │   ╱
    │  ╱                 │  ╱                   │  ╱
    │ ╱                  │ ╱                   ╱│ ╱
  0 ┤╱                   │╱                  ╱  │╱
    ────────────         ────────────        ────────────
       -4  0  4             -4  0  4           -4  0  4

GELU                     Swish                   Tanh
    │      ╱             │      ╱              1 ┤      ╭────
    │     ╱              │     ╱                 │     ╱
    │    ╱               │    ╱                  │    ╱
    │   ╱                │   ╱               0 ──┤───╱───
    │  ╱                 │  ╱                    │  ╱
    │╱_                  │╱_                     │ ╱
    │  ╲_slight dip      │  ╲_slight dip    -1 ┤╱
    ────────────         ────────────           ────────────
```

### Implementation

```python
import torch
import torch.nn.functional as F

# All activation functions
def sigmoid(z):     return 1 / (1 + torch.exp(-z))
def tanh(z):        return torch.tanh(z)
def relu(z):        return torch.clamp(z, min=0)
def leaky_relu(z):  return torch.where(z > 0, z, 0.01 * z)
def gelu(z):        return z * 0.5 * (1 + torch.erf(z / math.sqrt(2)))
def swish(z):       return z * torch.sigmoid(z)

# Choosing activation: Use ReLU by default, GELU for transformers
```

## 4. Forward Propagation

### Step-by-Step for a 2-Layer Network

Given: Input x ∈ ℝⁿ, weights W⁽¹⁾ ∈ ℝʰˣⁿ, W⁽²⁾ ∈ ℝᵐˣʰ, biases b⁽¹⁾, b⁽²⁾

```
Step 1: Linear transform (layer 1)
    z⁽¹⁾ = W⁽¹⁾x + b⁽¹⁾              [h × 1]

Step 2: Activation (layer 1)
    a⁽¹⁾ = f(z⁽¹⁾)                    [h × 1]

Step 3: Linear transform (layer 2)
    z⁽²⁾ = W⁽²⁾a⁽¹⁾ + b⁽²⁾            [m × 1]

Step 4: Output activation (layer 2)
    ŷ = g(z⁽²⁾)                       [m × 1]
    (g = softmax for classification, identity for regression)

Step 5: Loss computation
    L = CrossEntropy(y, ŷ) = -Σ yᵢ log(ŷᵢ)
```

### Computational Graph

```
x ──→ [W⁽¹⁾x+b⁽¹⁾] ──→ z⁽¹⁾ ──→ [ReLU] ──→ a⁽¹⁾ ──→ [W⁽²⁾a⁽¹⁾+b⁽²⁾] ──→ z⁽²⁾ ──→ [Softmax] ──→ ŷ ──→ [Loss] ──→ L
         ↑                                              ↑                                    ↑
        W⁽¹⁾,b⁽¹⁾                                     W⁽²⁾,b⁽²⁾                              y (target)
```

## 5. Backpropagation (Complete Derivation)

### Chain Rule Foundation

For composite function f(g(x)):  df/dx = df/dg · dg/dx

### Full Derivation for 2-Layer Network

**Goal**: Compute ∂L/∂W⁽¹⁾, ∂L/∂b⁽¹⁾, ∂L/∂W⁽²⁾, ∂L/∂b⁽²⁾

**Step 1: Output layer gradients**

With softmax + cross-entropy (combined gradient is elegant):
```
∂L/∂z⁽²⁾ = ŷ - y = δ⁽²⁾              [m × 1]
```

Therefore:
```
∂L/∂W⁽²⁾ = δ⁽²⁾ · (a⁽¹⁾)ᵀ           [m × h]
∂L/∂b⁽²⁾ = δ⁽²⁾                       [m × 1]
```

**Step 2: Hidden layer gradients (chain rule)**
```
∂L/∂a⁽¹⁾ = (W⁽²⁾)ᵀ · δ⁽²⁾            [h × 1]

∂L/∂z⁽¹⁾ = ∂L/∂a⁽¹⁾ ⊙ f'(z⁽¹⁾) = δ⁽¹⁾   [h × 1]
    (⊙ is element-wise multiplication)
    For ReLU: f'(z) = 1 if z > 0, else 0

∂L/∂W⁽¹⁾ = δ⁽¹⁾ · xᵀ                 [h × n]
∂L/∂b⁽¹⁾ = δ⁽¹⁾                       [h × 1]
```

**Step 3: Weight update (SGD)**
```
W⁽ˡ⁾ ← W⁽ˡ⁾ - η · ∂L/∂W⁽ˡ⁾
b⁽ˡ⁾ ← b⁽ˡ⁾ - η · ∂L/∂b⁽ˡ⁾
```

### Worked Example: XOR Network

```
Network: 2 inputs → 2 hidden (ReLU) → 1 output (sigmoid)
Training point: x = [1, 0], y = 1 (XOR: 1⊕0 = 1)

Initial weights:
W⁽¹⁾ = [[0.5, -0.3],    b⁽¹⁾ = [0.1, 0.2]
         [0.8,  0.4]]
W⁽²⁾ = [0.6, -0.2]      b⁽²⁾ = [0.1]

--- FORWARD PASS ---
z⁽¹⁾ = W⁽¹⁾·x + b⁽¹⁾ = [0.5·1 + (-0.3)·0 + 0.1, 0.8·1 + 0.4·0 + 0.2]
     = [0.6, 1.0]

a⁽¹⁾ = ReLU(z⁽¹⁾) = [0.6, 1.0]  (both positive, so unchanged)

z⁽²⁾ = W⁽²⁾·a⁽¹⁾ + b⁽²⁾ = 0.6·0.6 + (-0.2)·1.0 + 0.1 = 0.36 - 0.2 + 0.1 = 0.26

ŷ = σ(0.26) = 1/(1+e⁻⁰·²⁶) = 0.5646

Loss = -[y·log(ŷ) + (1-y)·log(1-ŷ)] = -log(0.5646) = 0.5717

--- BACKWARD PASS ---
δ⁽²⁾ = ŷ - y = 0.5646 - 1 = -0.4354

∂L/∂W⁽²⁾ = δ⁽²⁾ · (a⁽¹⁾)ᵀ = -0.4354 · [0.6, 1.0] = [-0.2612, -0.4354]
∂L/∂b⁽²⁾ = -0.4354

∂L/∂a⁽¹⁾ = (W⁽²⁾)ᵀ · δ⁽²⁾ = [0.6, -0.2]ᵀ · (-0.4354) = [-0.2612, 0.0871]

δ⁽¹⁾ = ∂L/∂a⁽¹⁾ ⊙ ReLU'(z⁽¹⁾) = [-0.2612, 0.0871] ⊙ [1, 1] = [-0.2612, 0.0871]
    (Both z⁽¹⁾ values were > 0, so ReLU derivative = 1)

∂L/∂W⁽¹⁾ = δ⁽¹⁾ · xᵀ = [[-0.2612·1, -0.2612·0],
                          [ 0.0871·1,  0.0871·0]]
           = [[-0.2612, 0], [0.0871, 0]]

--- UPDATE (lr = 0.1) ---
W⁽²⁾ = [0.6, -0.2] - 0.1·[-0.2612, -0.4354] = [0.6261, -0.1565]
b⁽²⁾ = 0.1 - 0.1·(-0.4354) = 0.1435
W⁽¹⁾ = [[0.5261, -0.3], [0.7913, 0.4]]
b⁽¹⁾ = [0.1261, 0.1913]
```

## 6. Weight Initialization

### Why It Matters

Bad initialization → vanishing/exploding activations → training fails.

### Methods

| Method | Formula | Use With |
|--------|---------|----------|
| Xavier/Glorot | W ~ N(0, 2/(nᵢₙ+nₒᵤₜ)) | Sigmoid, Tanh |
| He/Kaiming | W ~ N(0, 2/nᵢₙ) | ReLU family |
| LeCun | W ~ N(0, 1/nᵢₙ) | SELU |

```python
# PyTorch initialization
nn.init.xavier_uniform_(layer.weight)    # Glorot uniform
nn.init.kaiming_normal_(layer.weight, mode='fan_in', nonlinearity='relu')  # He
nn.init.zeros_(layer.bias)               # Bias typically zero
```

### Intuition
- Goal: Keep variance of activations ≈ 1 across layers
- If variance grows → exploding gradients
- If variance shrinks → vanishing gradients

## 7. Batch Normalization and Layer Normalization

### Batch Normalization (Ioffe & Szegedy, 2015)

Normalizes across the **batch dimension** for each feature.

```
For a mini-batch B = {x₁, ..., xₘ}:

μ_B = (1/m) Σᵢ xᵢ                    (batch mean)
σ²_B = (1/m) Σᵢ (xᵢ - μ_B)²         (batch variance)
x̂ᵢ = (xᵢ - μ_B) / √(σ²_B + ε)      (normalize)
yᵢ = γ · x̂ᵢ + β                      (scale and shift - learnable!)
```

```python
# Typically placed AFTER linear/conv, BEFORE activation
self.bn = nn.BatchNorm1d(num_features)
# or nn.BatchNorm2d for conv layers

# During inference: uses running mean/var (exponential moving average)
```

### Layer Normalization (Ba et al., 2016)

Normalizes across the **feature dimension** for each sample. No batch dependency.

```
For a single sample x with features {x₁, ..., xₕ}:

μ = (1/H) Σⱼ xⱼ                       (feature mean)
σ² = (1/H) Σⱼ (xⱼ - μ)²              (feature variance)
x̂ⱼ = (xⱼ - μ) / √(σ² + ε)
yⱼ = γⱼ · x̂ⱼ + βⱼ
```

| | BatchNorm | LayerNorm |
|---|-----------|-----------|
| Normalizes over | Batch | Features |
| Batch dependency | Yes | No |
| Best for | CNNs | Transformers, RNNs |
| Inference | Needs running stats | Same as training |

## 8. Dropout and Regularization

### Dropout (Srivastava et al., 2014)

During training, randomly zero out neurons with probability p:
```
mask ~ Bernoulli(1-p)
h_drop = mask ⊙ h / (1-p)     ← inverted dropout (scale at train time)
```

During inference: use all neurons (no dropout).

```python
# In PyTorch
self.dropout = nn.Dropout(p=0.5)  # 50% dropout
# model.train()  → dropout active
# model.eval()   → dropout inactive
```

### Other Regularization Techniques
- **L2 (Weight Decay)**: Add λ||w||² to loss → `optimizer = Adam(params, weight_decay=1e-4)`
- **L1**: Encourages sparsity
- **Early Stopping**: Stop when validation loss stops improving
- **Data Augmentation**: Artificially expand training set
- **Label Smoothing**: Soften one-hot targets: y = (1-ε)·one_hot + ε/K

## 9. Universal Approximation Theorem

**Statement**: A feedforward neural network with a single hidden layer containing a finite number of neurons can approximate any continuous function on compact subsets of ℝⁿ, given a non-polynomial activation function.

**Implication**: MLPs are theoretically powerful enough to represent any function. BUT:
- Doesn't say how MANY neurons you need (could be exponentially many)
- Doesn't say the network is LEARNABLE via gradient descent
- Deep networks can represent same functions with exponentially fewer parameters than shallow ones

## 10. Vanishing and Exploding Gradient Problem

### The Problem

In a deep network with L layers, gradients flow back through multiplication:
```
∂L/∂W⁽¹⁾ = ∂L/∂z⁽ᴸ⁾ · ∂z⁽ᴸ⁾/∂a⁽ᴸ⁻¹⁾ · ... · ∂z⁽²⁾/∂a⁽¹⁾ · ∂a⁽¹⁾/∂z⁽¹⁾ · ∂z⁽¹⁾/∂W⁽¹⁾
```

Each term ∂z⁽ˡ⁺¹⁾/∂a⁽ˡ⁾ = W⁽ˡ⁺¹⁾, and ∂a⁽ˡ⁾/∂z⁽ˡ⁾ = f'(z⁽ˡ⁾)

- **Sigmoid**: f'(z) ∈ (0, 0.25) → multiplying many small numbers → gradients vanish
- **Large weights**: ||W|| > 1 → gradients explode

### Solutions

| Problem | Solution |
|---------|----------|
| Vanishing | ReLU activation, skip connections, LSTM gates |
| Exploding | Gradient clipping, proper initialization |
| Both | BatchNorm, ResNet architecture |

```python
# Gradient clipping
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
```

## 11. Optimizers

### SGD with Momentum
```
v_t = β·v_{t-1} + η·∇L(θ)
θ_t = θ_{t-1} - v_t
```

### Adam (Kingma & Ba, 2015) — Most Popular
```
m_t = β₁·m_{t-1} + (1-β₁)·∇L        (1st moment - mean)
v_t = β₂·v_{t-1} + (1-β₂)·(∇L)²     (2nd moment - variance)
m̂_t = m_t / (1 - β₁ᵗ)                (bias correction)
v̂_t = v_t / (1 - β₂ᵗ)
θ_t = θ_{t-1} - η · m̂_t / (√v̂_t + ε)
```

```python
# Common optimizer choices
optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)        # Default go-to
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)  # With decoupled weight decay
optimizer = torch.optim.SGD(model.parameters(), lr=0.1, momentum=0.9)  # For CNNs sometimes
```

### Learning Rate Schedules

```python
# Cosine annealing (popular for transformers)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

# Warmup + decay (for transformers)
# Linear warmup for first N steps, then cosine decay
```

## 12. Complete Training Loop

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Setup
model = MLP(784, [512, 256], 10).cuda()
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=50)
criterion = nn.CrossEntropyLoss()

# Training loop
for epoch in range(50):
    model.train()
    total_loss = 0
    for batch_x, batch_y in train_loader:
        batch_x, batch_y = batch_x.cuda(), batch_y.cuda()
        
        optimizer.zero_grad()
        output = model(batch_x)
        loss = criterion(output, batch_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item()
    
    scheduler.step()
    
    # Validation
    model.eval()
    with torch.no_grad():
        val_acc = evaluate(model, val_loader)
    
    print(f"Epoch {epoch}: Loss={total_loss/len(train_loader):.4f}, Val Acc={val_acc:.4f}")
```

## Training Tips and Common Pitfalls

1. **Start with a small model** that overfits, then scale up
2. **Sanity check**: Can the model overfit a single batch? If not, bug in code
3. **Learning rate**: Most important hyperparameter. Use LR finder or start with 3e-4 for Adam
4. **Batch size**: Larger = faster training, potentially worse generalization. 32-256 typical
5. **Gradient accumulation**: Simulate large batches on limited GPU memory
6. **Mixed precision**: `torch.cuda.amp` for 2x speedup with minimal accuracy loss
7. **Don't forget `model.eval()`** during validation (affects BN and Dropout)

## Interview Questions

1. **Why can't a single perceptron learn XOR?** XOR is not linearly separable. Need at least one hidden layer.

2. **Why ReLU over Sigmoid?** No vanishing gradient for positive inputs, computationally cheap, sparse activation.

3. **What happens if you initialize all weights to zero?** All neurons compute the same function → symmetry never breaks → network can't learn.

4. **BatchNorm before or after activation?** Debated. Original paper: before. Practice: both work; after ReLU is slightly more common now.

5. **Why does Adam have bias correction?** m₀=0, v₀=0 → early estimates biased toward zero. Correction compensates for this.

6. **Derive the gradient of softmax + cross-entropy.** Result: ŷ - y (elegant!). This is why they're paired.

7. **How does dropout act as regularization?** Forces redundancy—network can't rely on any single neuron. Approximates ensemble of 2ⁿ sub-networks.

8. **Universal Approximation—so why go deep?** Deep networks represent functions with exponentially fewer parameters than shallow ones. Depth enables compositional feature learning.
