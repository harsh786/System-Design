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

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** Calculate the output of a single neuron with inputs x=[2, 3], weights w=[0.5, -1], bias b=1, using ReLU activation.
**Hint:** z = wᵀx + b, then apply ReLU.

<details><summary>Solution</summary>

z = w₁x₁ + w₂x₂ + b = (0.5)(2) + (-1)(3) + 1 = 1 - 3 + 1 = -1

ReLU(-1) = max(0, -1) = 0

Output = 0

</details>

### Exercise 2 (Beginner)
**Problem:** A network has input layer (784 neurons), hidden layer (128 neurons), output layer (10 neurons). How many trainable parameters are there (including biases)?
**Hint:** Parameters = weights + biases for each layer connection.

<details><summary>Solution</summary>

Layer 1→2: 784 × 128 weights + 128 biases = 100,480
Layer 2→3: 128 × 10 weights + 10 biases = 1,290

Total: 100,480 + 1,290 = **101,770** parameters

</details>

### Exercise 3 (Beginner)
**Problem:** Why can't we use a linear activation function in all layers? What would happen?
**Hint:** Compose multiple linear functions.

<details><summary>Solution</summary>

If all activations are linear: f(x) = ax + b

Layer 1: h₁ = W₁x + b₁
Layer 2: h₂ = W₂h₁ + b₂ = W₂(W₁x + b₁) + b₂ = (W₂W₁)x + (W₂b₁ + b₂)

This is just another linear transformation! Multiple linear layers collapse to a single linear layer.

The network cannot learn non-linear decision boundaries, making it equivalent to logistic/linear regression regardless of depth. Non-linear activations are essential for learning complex functions.

</details>

### Exercise 4 (Intermediate)
**Problem:** Perform one step of backpropagation for a simple 2-layer network. Given: input x=1, target y=0, weights w₁=0.5, w₂=0.8, no bias, sigmoid activations, MSE loss. Compute gradients ∂L/∂w₁ and ∂L/∂w₂.
**Hint:** Forward pass first, then chain rule backward.

<details><summary>Solution</summary>

**Forward pass:**
- h = σ(w₁·x) = σ(0.5) = 0.622
- ŷ = σ(w₂·h) = σ(0.8 × 0.622) = σ(0.498) = 0.622

**Loss:** L = ½(ŷ - y)² = ½(0.622)² = 0.193

**Backward pass:**
- ∂L/∂ŷ = ŷ - y = 0.622
- ∂ŷ/∂z₂ = ŷ(1-ŷ) = 0.622 × 0.378 = 0.235 (sigmoid derivative)
- ∂z₂/∂w₂ = h = 0.622

∂L/∂w₂ = 0.622 × 0.235 × 0.622 = **0.091**

- ∂z₂/∂h = w₂ = 0.8
- ∂h/∂z₁ = h(1-h) = 0.622 × 0.378 = 0.235
- ∂z₁/∂w₁ = x = 1

∂L/∂w₁ = 0.622 × 0.235 × 0.8 × 0.235 × 1 = **0.027**

</details>

### Exercise 5 (Intermediate)
**Problem:** Compare and contrast ReLU, Leaky ReLU, ELU, and GELU activations. When would you use each?
**Hint:** Consider the "dying ReLU" problem and smoothness.

<details><summary>Solution</summary>

| Activation | Formula | Pros | Cons | Use When |
|-----------|---------|------|------|----------|
| ReLU | max(0,x) | Simple, fast, no vanishing gradient for x>0 | Dying neurons (gradient=0 for x<0) | Default for most CNNs |
| Leaky ReLU | max(αx, x), α=0.01 | No dying neurons | Extra hyperparameter | When dying ReLU is a problem |
| ELU | x if x>0, α(eˣ-1) if x≤0 | Smooth, pushes mean toward 0 | Slower (exp), not zero-centered output | When batch norm isn't used |
| GELU | x·Φ(x) | Smooth, used in transformers | Slightly more compute | Transformers, BERT, GPT |

GELU = Gaussian Error Linear Unit ≈ 0.5x(1 + tanh(√(2/π)(x + 0.044715x³)))

Modern defaults: ReLU for CNNs, GELU for Transformers, SiLU/Swish for efficient nets.

</details>

### Exercise 6 (Intermediate)
**Problem:** Explain the vanishing gradient problem. Which architectures and techniques solve it?
**Hint:** What happens when you multiply many small numbers together?

<details><summary>Solution</summary>

**Problem:** In deep networks with sigmoid/tanh, gradients are multiplied through layers:
∂L/∂w₁ = ∂L/∂hₙ × ∂hₙ/∂hₙ₋₁ × ... × ∂h₂/∂h₁ × ∂h₁/∂w₁

Sigmoid derivative max = 0.25. After 10 layers: 0.25¹⁰ ≈ 10⁻⁶. Gradients vanish!

**Solutions:**
1. **ReLU activation:** Gradient = 1 for positive inputs (no shrinking)
2. **Residual connections:** y = F(x) + x. Gradient flows through shortcut (at least 1)
3. **Batch normalization:** Keeps activations in good range
4. **LSTM/GRU:** Gating mechanisms for RNNs (additive gradient flow)
5. **Proper initialization:** He (ReLU), Xavier (sigmoid/tanh)
6. **Gradient clipping:** Prevents explosion (related problem)

</details>

### Exercise 7 (Intermediate)
**Problem:** You're training a network and the loss oscillates wildly. The gradients are very large. Diagnose and fix.
**Hint:** Think about learning rate and gradient magnitude.

<details><summary>Solution</summary>

**Diagnosis:** Exploding gradients or learning rate too high.

**Fixes:**
1. **Reduce learning rate** — most common cause of oscillation
2. **Gradient clipping:** `torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)`
3. **Learning rate scheduler:** Start high, decay over time (cosine, step)
4. **Batch normalization:** Stabilizes internal activations
5. **Better initialization:** He/Xavier instead of random
6. **Adam optimizer:** Adaptive learning rates per parameter
7. **Smaller batch size:** More noise can help regularize
8. **Check data:** Outliers or unnormalized inputs cause large gradients

</details>

### Exercise 8 (Advanced)
**Problem:** Derive the backpropagation equations for a network with softmax output and cross-entropy loss. Show that the gradient simplifies elegantly.
**Hint:** The gradient of CE loss w.r.t. logits has a beautiful form.

<details><summary>Solution</summary>

**Softmax:** pᵢ = exp(zᵢ) / Σⱼ exp(zⱼ)

**Cross-entropy loss:** L = -Σᵢ yᵢ log(pᵢ) where y is one-hot

**Gradient ∂L/∂zᵢ:**

∂L/∂zᵢ = -Σⱼ yⱼ · (1/pⱼ) · ∂pⱼ/∂zᵢ

Softmax Jacobian: ∂pⱼ/∂zᵢ = pⱼ(δᵢⱼ - pᵢ)

∂L/∂zᵢ = -Σⱼ yⱼ · (1/pⱼ) · pⱼ(δᵢⱼ - pᵢ)
        = -Σⱼ yⱼ(δᵢⱼ - pᵢ)
        = -(yᵢ - pᵢ·Σⱼyⱼ)
        = -(yᵢ - pᵢ·1)    [since Σyⱼ = 1 for one-hot]

**∂L/∂zᵢ = pᵢ - yᵢ**

Beautifully simple! The gradient is just (predicted probability - true label). Same form as sigmoid + BCE in binary case.

</details>

### Exercise 9 (Advanced)
**Problem:** Explain why batch normalization works. Discuss the training vs inference difference. What are the learnable parameters γ and β for?
**Hint:** Consider internal covariate shift and what normalization does to the representational power.

<details><summary>Solution</summary>

**Batch Norm operation (training):**
μ_B = (1/m) Σ xᵢ (batch mean)
σ²_B = (1/m) Σ (xᵢ - μ_B)² (batch variance)
x̂ᵢ = (xᵢ - μ_B) / √(σ²_B + ε) (normalize)
yᵢ = γx̂ᵢ + β (scale and shift) ← learnable!

**Why it works:**
1. Reduces internal covariate shift (debated — may not be primary reason)
2. Smooths the loss landscape (proven: makes optimization easier)
3. Acts as regularization (batch statistics add noise)
4. Allows higher learning rates (more stable gradients)

**γ and β:** Without them, normalization forces zero mean, unit variance — this constrains representational power. γ and β allow the network to UNDO normalization if needed (γ=σ, β=μ recovers original).

**Training vs Inference:**
- Training: use batch statistics (μ_B, σ²_B)
- Inference: use running averages of μ and σ² computed during training (no batch dependency)
- `model.eval()` switches behavior

</details>

### Exercise 10 (Advanced)
**Problem:** Compare SGD with momentum, Adam, and AdamW. When does each optimizer shine? Why has AdamW become the default for transformers?
**Hint:** Consider the interaction between adaptive learning rates and weight decay.

<details><summary>Solution</summary>

**SGD + Momentum:**
- v_t = βv_{t-1} + ∇L
- θ_t = θ_{t-1} - α·v_t
- Pros: Good generalization, simple
- Cons: Sensitive to learning rate, slow convergence
- Shines: CNNs, when tuning budget exists, better final performance

**Adam (Adaptive Moment Estimation):**
- m_t = β₁m_{t-1} + (1-β₁)g_t (first moment)
- v_t = β₂v_{t-1} + (1-β₂)g_t² (second moment)
- θ_t = θ_{t-1} - α·m̂_t/√(v̂_t + ε)
- Pros: Fast convergence, works with minimal tuning
- Cons: May generalize worse than SGD, L2 ≠ weight decay

**AdamW (Adam with decoupled Weight Decay):**
- Same as Adam but: θ_t = θ_{t-1} - α·(m̂_t/√(v̂_t + ε) + λ·θ_{t-1})
- Decouples weight decay from gradient-based update
- In Adam, L2 regularization is scaled by adaptive learning rate (unintended!)
- AdamW applies weight decay uniformly

**Why AdamW for Transformers:**
- Transformers have many parameters with different gradient scales
- Adam's adaptivity handles this well
- Proper weight decay (decoupled) is crucial for generalization
- Combined with warmup + cosine schedule = robust training

</details>

### Exercise 11 (Advanced)
**Problem:** A neural network with 10M parameters achieves 0 training loss but poor test performance. Explain 5 regularization techniques to fix this, ordered by effectiveness.
**Hint:** Consider data, architecture, and training modifications.

<details><summary>Solution</summary>

**Most effective regularization techniques:**

1. **Data augmentation:** More effective than any explicit regularizer. Generates synthetic training data (flips, rotations, cutout, mixup). Dramatically reduces overfitting.

2. **Dropout (p=0.1-0.5):** Randomly zero activations during training. Equivalent to ensemble of subnetworks. Place after dense/attention layers. p=0.1 for transformers, 0.5 for large MLPs.

3. **Weight decay (AdamW, λ=0.01-0.1):** Penalizes large weights. Prevents memorization by constraining model capacity. Essential for transformers.

4. **Early stopping:** Monitor validation loss, stop when it stops improving. Simple and effective. Equivalent to L2 regularization for linear models.

5. **Architecture changes:**
   - Reduce model size (fewer layers/neurons)
   - Batch normalization (implicit regularization from batch noise)
   - Label smoothing (soft targets: 0.9 instead of 1.0)
   - Stochastic depth (randomly drop entire layers)

</details>

---

## Self-Assessment Quiz

**1. The universal approximation theorem states that a neural network can approximate any function if:**
- A) It has enough layers
- B) It has one hidden layer with enough neurons and a non-linear activation
- C) It uses ReLU activation
- D) It is trained with backpropagation

<details><summary>Answer</summary>B) A single hidden layer with sufficient width and non-linear activation can approximate any continuous function on a compact set (but may need exponentially many neurons).</details>

**2. Backpropagation is essentially:**
- A) Random search for optimal weights
- B) Repeated application of the chain rule to compute gradients
- C) A type of activation function
- D) Forward pass through the network

<details><summary>Answer</summary>B) Chain rule applied recursively from output to input layers to compute ∂L/∂w for all weights.</details>

**3. He initialization sets weights to:**
- A) All zeros
- B) Random from N(0, 2/n_in)
- C) Random from N(0, 1/n_in)
- D) All ones

<details><summary>Answer</summary>B) N(0, 2/n_in) — designed for ReLU to maintain variance through layers. Xavier uses 1/n_in for sigmoid/tanh.</details>

**4. Dropout with p=0.5 during training means:**
- A) 50% of weights are removed permanently
- B) Each neuron has 50% chance of being zeroed on each forward pass
- C) Learning rate is halved
- D) 50% of data is ignored

<details><summary>Answer</summary>B) Each neuron independently zeroed with probability p on each training iteration. At test time, multiply outputs by (1-p) or use inverted dropout.</details>

**5. The dying ReLU problem occurs when:**
- A) ReLU outputs become too large
- B) A neuron's input is always negative, so gradient is permanently 0
- C) The learning rate is too low
- D) Batch size is too small

<details><summary>Answer</summary>B) If weights push all inputs negative, ReLU gradient = 0, neuron never updates (dead forever).</details>

**6. Batch normalization is applied:**
- A) Only at the input layer
- B) After activation function
- C) Before activation function (most common) or after
- D) Only during inference

<details><summary>Answer</summary>C) Typically before activation (original paper), though after also works. Applied per layer during training.</details>

**7. Adam optimizer combines:**
- A) Momentum and RMSProp
- B) SGD and Newton's method
- C) L1 and L2 regularization
- D) Dropout and batch norm

<details><summary>Answer</summary>A) First moment (momentum) + second moment (RMSProp) with bias correction.</details>

**8. A network with 100 layers and sigmoid activation will likely suffer from:**
- A) Exploding gradients
- B) Vanishing gradients
- C) Overfitting
- D) Underfitting

<details><summary>Answer</summary>B) Vanishing gradients — sigmoid derivative max is 0.25, so gradients shrink exponentially: 0.25^100 ≈ 0.</details>

**9. Learning rate warmup is used to:**
- A) Speed up training
- B) Gradually increase LR at the start to stabilize early training
- C) Prevent overfitting
- D) Reduce memory usage

<details><summary>Answer</summary>B) Start with small LR, increase to target over first few hundred/thousand steps. Prevents early instability when Adam/momentum statistics are not yet accurate.</details>

**10. The number of FLOPs in a fully connected layer (n_in → n_out) is approximately:**
- A) n_in + n_out
- B) n_in × n_out (multiply-adds)
- C) n_in²
- D) 2^n_in

<details><summary>Answer</summary>B) ~2 × n_in × n_out FLOPs (one multiply + one add per weight, for each output neuron).</details>

---

## Coding Challenges

### Challenge 1: Implement a Neural Network from Scratch (NumPy only)
```python
"""
Implement a 2-layer neural network with:
- Forward pass, backward pass
- ReLU hidden activation, softmax output
- Cross-entropy loss
- SGD optimizer
"""
import numpy as np

class NeuralNetwork:
    def __init__(self, input_dim, hidden_dim, output_dim, lr=0.01):
        # He initialization
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2/input_dim)
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(hidden_dim, output_dim) * np.sqrt(2/hidden_dim)
        self.b2 = np.zeros(output_dim)
        self.lr = lr
    
    def relu(self, x):
        return np.maximum(0, x)
    
    def softmax(self, x):
        exp_x = np.exp(x - x.max(axis=1, keepdims=True))
        return exp_x / exp_x.sum(axis=1, keepdims=True)
    
    def forward(self, X):
        self.z1 = X @ self.W1 + self.b1
        self.h1 = self.relu(self.z1)
        self.z2 = self.h1 @ self.W2 + self.b2
        self.output = self.softmax(self.z2)
        return self.output
    
    def backward(self, X, y_onehot):
        m = X.shape[0]
        
        # Output layer gradient (softmax + CE simplification)
        dz2 = self.output - y_onehot  # (m, output_dim)
        dW2 = (self.h1.T @ dz2) / m
        db2 = dz2.mean(axis=0)
        
        # Hidden layer gradient
        dh1 = dz2 @ self.W2.T
        dz1 = dh1 * (self.z1 > 0)  # ReLU derivative
        dW1 = (X.T @ dz1) / m
        db1 = dz1.mean(axis=0)
        
        # Update
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1
    
    def train(self, X, y, epochs=100):
        y_onehot = np.eye(self.W2.shape[1])[y]
        for epoch in range(epochs):
            output = self.forward(X)
            loss = -np.mean(np.sum(y_onehot * np.log(output + 1e-8), axis=1))
            self.backward(X, y_onehot)
            if epoch % 10 == 0:
                print(f"Epoch {epoch}, Loss: {loss:.4f}")
```

### Challenge 2: Implement Batch Normalization
```python
"""
Implement batch normalization layer with:
- Training mode (batch statistics)
- Eval mode (running statistics)
- Learnable gamma and beta
"""
import numpy as np

class BatchNorm:
    def __init__(self, num_features, momentum=0.1, eps=1e-5):
        self.gamma = np.ones(num_features)
        self.beta = np.zeros(num_features)
        self.eps = eps
        self.momentum = momentum
        self.running_mean = np.zeros(num_features)
        self.running_var = np.ones(num_features)
        self.training = True
    
    def forward(self, x):
        if self.training:
            self.mu = x.mean(axis=0)
            self.var = x.var(axis=0)
            self.x_norm = (x - self.mu) / np.sqrt(self.var + self.eps)
            
            # Update running stats
            self.running_mean = (1-self.momentum)*self.running_mean + self.momentum*self.mu
            self.running_var = (1-self.momentum)*self.running_var + self.momentum*self.var
        else:
            self.x_norm = (x - self.running_mean) / np.sqrt(self.running_var + self.eps)
        
        return self.gamma * self.x_norm + self.beta
    
    def backward(self, dout):
        m = dout.shape[0]
        
        dgamma = np.sum(dout * self.x_norm, axis=0)
        dbeta = np.sum(dout, axis=0)
        
        dx_norm = dout * self.gamma
        dvar = np.sum(dx_norm * (self.x_norm * -0.5 / (self.var + self.eps)), axis=0)
        dmu = np.sum(dx_norm * -1/np.sqrt(self.var + self.eps), axis=0)
        
        dx = dx_norm / np.sqrt(self.var + self.eps) + dvar * 2*(self.x_norm*np.sqrt(self.var+self.eps))/m + dmu/m
        
        self.gamma -= 0.01 * dgamma
        self.beta -= 0.01 * dbeta
        return dx
```

### Challenge 3: Implement Dropout Layer
```python
"""
Implement dropout with inverted dropout technique.
Must behave differently in train vs eval mode.
"""
import numpy as np

class Dropout:
    def __init__(self, p=0.5):
        self.p = p  # probability of dropping
        self.training = True
    
    def forward(self, x):
        if not self.training:
            return x
        
        # Inverted dropout: scale during training so no change needed at test time
        self.mask = (np.random.rand(*x.shape) > self.p) / (1 - self.p)
        return x * self.mask
    
    def backward(self, dout):
        if not self.training:
            return dout
        return dout * self.mask

# Usage example:
# Training: dropout.training = True; out = dropout.forward(hidden)
# Eval:     dropout.training = False; out = dropout.forward(hidden)
```

### Challenge 4: Implement Adam Optimizer
```python
"""
Implement Adam optimizer with bias correction.
Support weight decay (AdamW style).
"""
import numpy as np

class Adam:
    def __init__(self, params, lr=0.001, beta1=0.9, beta2=0.999, eps=1e-8, weight_decay=0):
        self.params = params  # list of (param_array, grad_array) tuples
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.weight_decay = weight_decay
        self.t = 0
        
        # Initialize moments
        self.m = [np.zeros_like(p) for p, _ in params]
        self.v = [np.zeros_like(p) for p, _ in params]
    
    def step(self):
        self.t += 1
        for i, (param, grad) in enumerate(self.params):
            # Weight decay (AdamW: decoupled)
            if self.weight_decay > 0:
                param -= self.lr * self.weight_decay * param
            
            # Update moments
            self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * grad
            self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * grad**2
            
            # Bias correction
            m_hat = self.m[i] / (1 - self.beta1**self.t)
            v_hat = self.v[i] / (1 - self.beta2**self.t)
            
            # Update parameters
            param -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
```

### Challenge 5: Implement Mini-Batch Training Loop with Learning Rate Schedule
```python
"""
Implement a complete training loop with:
- Mini-batch gradient descent
- Cosine annealing learning rate schedule
- Early stopping
- Training/validation loss tracking
"""
import numpy as np

class Trainer:
    def __init__(self, model, lr=0.001, batch_size=32, epochs=100, patience=10):
        self.model = model
        self.initial_lr = lr
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience
    
    def cosine_lr(self, epoch):
        """Cosine annealing schedule."""
        return self.initial_lr * 0.5 * (1 + np.cos(np.pi * epoch / self.epochs))
    
    def create_batches(self, X, y):
        indices = np.random.permutation(len(X))
        for i in range(0, len(X), self.batch_size):
            batch_idx = indices[i:i+self.batch_size]
            yield X[batch_idx], y[batch_idx]
    
    def train(self, X_train, y_train, X_val, y_val):
        history = {'train_loss': [], 'val_loss': []}
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.epochs):
            # Update learning rate
            self.model.lr = self.cosine_lr(epoch)
            
            # Training
            epoch_losses = []
            for X_batch, y_batch in self.create_batches(X_train, y_train):
                output = self.model.forward(X_batch)
                y_onehot = np.eye(output.shape[1])[y_batch]
                loss = -np.mean(np.sum(y_onehot * np.log(output + 1e-8), axis=1))
                self.model.backward(X_batch, y_onehot)
                epoch_losses.append(loss)
            
            # Validation
            val_output = self.model.forward(X_val)
            y_val_onehot = np.eye(val_output.shape[1])[y_val]
            val_loss = -np.mean(np.sum(y_val_onehot * np.log(val_output + 1e-8), axis=1))
            
            history['train_loss'].append(np.mean(epoch_losses))
            history['val_loss'].append(val_loss)
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_weights = (self.model.W1.copy(), self.model.W2.copy())
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    print(f"Early stopping at epoch {epoch}")
                    self.model.W1, self.model.W2 = best_weights
                    break
        
        return history
```

---

## Interview Questions

### 1. What is the difference between a parameter and a hyperparameter?
<details><summary>Answer</summary>

- **Parameters:** Learned during training (weights, biases). Set by optimization algorithm.
- **Hyperparameters:** Set before training (learning rate, batch size, number of layers, dropout rate). Tuned via validation performance.

Parameters define the model's function. Hyperparameters define the learning process and model architecture.

</details>

### 2. Why do we need non-linear activation functions?
<details><summary>Answer</summary>

Without non-linearity, any depth of network collapses to a single linear transformation (composition of linear functions is linear). Non-linear activations allow:
1. Learning non-linear decision boundaries
2. Universal function approximation
3. Representation of complex features (edges → textures → objects)

Even a single hidden layer with non-linear activation can approximate any continuous function (universal approximation theorem).

</details>

### 3. Explain the difference between batch, mini-batch, and stochastic gradient descent.
<details><summary>Answer</summary>

| | Batch GD | Mini-batch GD | SGD (batch=1) |
|---|---|---|---|
| Uses | All data | Subset (32-512) | 1 sample |
| Gradient | Exact | Approximate | Very noisy |
| Speed/epoch | Slow | Fast | Fastest |
| Convergence | Smooth | Slightly noisy | Very noisy |
| Memory | High | Moderate | Low |
| GPU utilization | Good | Good | Poor |

**In practice:** Mini-batch (32-256) is almost always used. "SGD" in deep learning usually means mini-batch SGD.

</details>

### 4. How does a neural network learn features?
<details><summary>Answer</summary>

Through hierarchical composition:
- **Layer 1:** Learns simple features (edges, colors)
- **Layer 2:** Combines simple features into patterns (textures, shapes)
- **Layer 3+:** Combines patterns into objects (faces, cars)

Each layer applies: feature = activation(weighted_sum(previous_features) + bias)

The key insight: features are NOT hand-designed — they emerge from backpropagation optimizing the loss function. The network discovers what features are useful for the task.

</details>

### 5. What happens if you initialize all weights to zero?
<details><summary>Answer</summary>

**Symmetry problem:** All neurons in a layer compute identical outputs (same weights → same gradients → same updates forever).

The network effectively has one neuron per layer — can't learn diverse features.

**Fix:** Random initialization breaks symmetry. He initialization (for ReLU) or Xavier (for sigmoid/tanh) maintains appropriate variance across layers.

Exception: Biases CAN be initialized to zero (don't cause symmetry issues).

</details>

### 6. Explain gradient clipping and when it's needed.
<details><summary>Answer</summary>

**Gradient clipping:** Limit gradient magnitude during training.

Two types:
1. **Clip by value:** g = clip(g, -threshold, threshold)
2. **Clip by norm:** if ||g|| > threshold, g = g × threshold/||g||

**When needed:**
- RNNs/LSTMs (long sequences cause gradient explosion)
- Deep networks without residual connections
- When loss spikes indicate exploding gradients
- Transformers (especially during training instability)

**Common values:** max_norm = 1.0 or 5.0

</details>

### 7. Compare CNNs vs MLPs for image data. Why do CNNs work better?
<details><summary>Answer</summary>

**MLP on images:**
- Treats each pixel as independent feature
- No spatial awareness (pixel 1,1 same as pixel 100,100)
- Full connectivity: 224×224×3 = 150K input neurons → huge parameter count
- Doesn't generalize to different image positions

**CNN advantages:**
1. **Local connectivity:** Filters see local patches (spatial structure)
2. **Parameter sharing:** Same filter applied everywhere (translation equivariance)
3. **Hierarchical features:** Low-level → mid-level → high-level
4. **Far fewer parameters:** 3×3×64 filter = 576 params regardless of image size
5. **Translation invariance** (via pooling)

</details>

---

## Real-World Scenarios

### Scenario 1: Building a Handwritten Digit Classifier
**Context:** You're building a digit recognition system (0-9) for a postal service. Input: 28×28 grayscale images. Training: 60K images. Must achieve >99% accuracy and run on embedded hardware.

**Questions:**
1. Design the network architecture.
2. What preprocessing and augmentation would you use?
3. How do you make it efficient for embedded deployment?
4. How do you handle ambiguous/unclear digits?

<details><summary>Solution</summary>

1. **Architecture:** Simple CNN sufficient for MNIST:
   - Conv(1→32, 3×3) → ReLU → Conv(32→64, 3×3) → ReLU → MaxPool
   - Conv(64→128, 3×3) → ReLU → MaxPool
   - Flatten → Dense(128) → ReLU → Dropout(0.5) → Dense(10) → Softmax
   - ~200K parameters (small enough for embedded)

2. **Preprocessing/Augmentation:**
   - Normalize to [0,1] or [-1,1]
   - Random rotation (±15°), translation (±2px), slight scaling
   - Elastic deformation (mimics handwriting variation)
   - No color augmentation (grayscale)

3. **Embedded efficiency:**
   - Quantization (INT8): 4x smaller, faster inference
   - Pruning: remove near-zero weights (50-80% sparsity)
   - Knowledge distillation: train small "student" from large "teacher"
   - ONNX/TFLite format for deployment
   - Target: <1MB model, <10ms inference

4. **Ambiguous digits:**
   - Output confidence scores (softmax probabilities)
   - Reject if max probability < threshold (e.g., 0.8)
   - Flag for human review
   - Monitor confusion pairs (4/9, 1/7, 3/8) — add training data for these

</details>

### Scenario 2: Training a Large Model with Limited GPU Memory
**Context:** You need to train a model with 500M parameters but only have a single GPU with 16GB VRAM. Batch size of 1 barely fits. You need effective batch size of 64 for good convergence.

**Questions:**
1. How do you fit the model in memory?
2. How do you achieve effective batch size of 64?
3. What optimizations reduce memory usage?
4. How does this affect training dynamics?

<details><summary>Solution</summary>

1. **Fitting the model:**
   - Mixed precision training (FP16): halves memory for activations and weights
   - Gradient checkpointing: trade compute for memory (recompute activations during backward)
   - Model parallelism: split layers across GPUs (if multiple available)
   - CPU offloading: keep optimizer states on CPU

2. **Effective batch size 64:**
   - **Gradient accumulation:** Forward/backward with batch=1, accumulate gradients for 64 steps, then update
   - Equivalent to batch=64 mathematically (same expected gradient)
   - `optimizer.step()` only every 64 mini-batches

3. **Memory optimizations:**
   - Mixed precision: ~40% memory reduction
   - Gradient checkpointing: up to 60% activation memory reduction (√N layers recomputed)
   - Delete intermediate activations aggressively
   - Use memory-efficient attention (FlashAttention)
   - 8-bit optimizers (bitsandbytes): reduce optimizer state memory

4. **Training dynamics:**
   - Gradient accumulation is mathematically equivalent to large batch (for SGD)
   - For batch norm: use small batch statistics (may differ slightly)
   - Learning rate should match effective batch size (linear scaling rule)
   - More steps per "effective batch" = slower wall-clock time
   - Mixed precision: may need loss scaling to prevent underflow

</details>

### Scenario 3: Debugging a Non-Converging Network
**Context:** You're training a 10-layer MLP for tabular data classification. The training loss stays flat at ~2.3 (≈ -ln(1/10) for 10 classes — random performance). Nothing seems to help.

**Questions:**
1. What does loss = 2.3 tell you?
2. Systematic debugging steps?
3. What architecture changes might help?
4. How do you verify each component works?

<details><summary>Solution</summary>

1. **Loss = 2.3 = -ln(0.1):** Model outputs uniform probabilities (random guessing for 10 classes). The network isn't learning AT ALL — not even overfitting. This is a bug, not a tuning issue.

2. **Systematic debugging:**
   - **Overfit one batch:** Can the model memorize 10 samples? If not, architecture/code is broken.
   - **Check gradients:** Are they zero? NaN? Exploding? Print gradient norms per layer.
   - **Check data pipeline:** Are labels shuffled? Correct? Try known dataset (MNIST).
   - **Check loss function:** Is the loss computed correctly? Softmax + CE or separate?
   - **Learning rate:** Try 10x smaller and 10x larger.
   - **Single layer first:** Can a 1-layer network beat random?

3. **Architecture fixes:**
   - Add residual connections (10 layers may have vanishing gradients)
   - Add batch normalization between layers
   - Use ReLU not sigmoid (10 layers of sigmoid = vanishing gradients guaranteed)
   - Reduce to 3-4 layers first, verify it works, then scale up
   - Proper He initialization

4. **Verification checklist:**
   - ✓ Random prediction gives loss ≈ 2.3? (confirms loss is correct)
   - ✓ Model can overfit 1 batch to loss ≈ 0? (confirms model works)
   - ✓ Gradients non-zero at all layers? (confirms no vanishing)
   - ✓ Weights changing after update? (confirms optimizer works)
   - ✓ Data labels match inputs? (visualize a few samples)

</details>
