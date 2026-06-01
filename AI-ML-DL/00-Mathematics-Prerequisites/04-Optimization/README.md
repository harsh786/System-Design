# Optimization for AI/ML/Deep Learning

## Why Optimization Matters for ML

Training a model = solving an optimization problem. You have a loss function L(θ) that measures how bad your predictions are, and you need to find parameters θ that minimize it.

```
θ* = argmin_θ L(θ)

where L(θ) = (1/n) Σ Loss(model(xᵢ; θ), yᵢ)
```

For a neural network with millions of parameters, you can't solve this analytically. You need iterative optimization algorithms.

---

## 1. Convex vs Non-Convex Optimization

### Convex Functions

A function is convex if a line segment between any two points lies above the function.

```
Convex (one global minimum):     Non-convex (multiple local minima):

    │\      /│                   │\    .    /\    /│
    │ \    / │                   │ \  / \  /  \  / │
    │  \  /  │                   │  \/   \/    \/  │
    │   \/   │                   │                 │
    │   ★    │                   │  ★?  ★?   ★?   │
    └────────┘                   └─────────────────┘
   Easy to optimize!             Hard! Many local minima
```

**ML Context:**
- Linear regression, logistic regression → convex (guaranteed global optimum)
- Neural networks → non-convex (may get stuck in local minima or saddle points)
- Surprisingly, local minima in high-dimensional NNs are often "good enough"

### Why Deep Learning Works Despite Non-Convexity

In high dimensions, most critical points are **saddle points** (not local minima). SGD + momentum naturally escape saddle points because of noise.

---

## 2. Gradient Descent Variants

### Batch Gradient Descent

Use ALL training data to compute gradient at each step.

```
θ = θ - α · (1/n) Σᵢ ∇L(xᵢ, yᵢ; θ)
```

```
+ Stable convergence, low variance
- Very slow for large datasets (must process ALL data per step)
- Memory intensive
```

### Stochastic Gradient Descent (SGD)

Use ONE random sample to estimate gradient.

```
θ = θ - α · ∇L(xᵢ, yᵢ; θ)    (single random sample i)
```

```
+ Fast updates, can escape local minima (noise helps!)
- High variance, noisy path
- May never converge exactly (oscillates around minimum)
```

### Mini-Batch Gradient Descent (THE standard)

Use a small batch (32-512 samples) to estimate gradient.

```
θ = θ - α · (1/B) Σⱼ∈batch ∇L(xⱼ, yⱼ; θ)
```

```
+ Best of both worlds: stable enough, fast enough
+ Leverages GPU parallelism (batch matrix operations)
+ Standard in practice: batch_size = 32, 64, 128, 256
```

```
Convergence paths:

Batch GD:         SGD:              Mini-batch:
  ╲               ╲ ╱╲              ╲  ╱
   ╲               ╳  ╲              ╲╱
    ╲             ╱ ╲   ╲             ╲
     ★           ╱   ╲   ★            ★
 (smooth)      (noisy)         (balanced)
```

```python
def mini_batch_gd(X, y, model, lr=0.01, batch_size=32, epochs=100):
    n = len(X)
    for epoch in range(epochs):
        # Shuffle data each epoch
        indices = np.random.permutation(n)
        
        for i in range(0, n, batch_size):
            batch_idx = indices[i:i+batch_size]
            X_batch, y_batch = X[batch_idx], y[batch_idx]
            
            # Compute gradient on mini-batch
            grad = compute_gradient(model, X_batch, y_batch)
            
            # Update parameters
            model.params -= lr * grad
    
    return model
```

---

## 3. Learning Rate Schedules

The learning rate α is the most important hyperparameter. Too high → diverges. Too low → too slow.

```
Learning rate too high:      Too low:           Just right:
    ╱╲  ╱╲                     ╲                  ╲
   ╱  ╳  ╲╱╲                    ╲                  ╲
  ╱       ╲                      ╲                  ╲
 (diverges!)                      ╲                  ★
                               (too slow)        (converges)
```

### Common Schedules

```python
# Step decay: reduce LR by factor every N epochs
def step_decay(epoch, initial_lr=0.1, drop=0.5, epochs_drop=10):
    return initial_lr * (drop ** (epoch // epochs_drop))

# Cosine annealing: smooth decay following cosine curve
def cosine_annealing(epoch, total_epochs, initial_lr=0.1, min_lr=1e-6):
    return min_lr + 0.5 * (initial_lr - min_lr) * (1 + np.cos(np.pi * epoch / total_epochs))

# Warmup + decay (used in Transformers)
def warmup_cosine(step, warmup_steps=1000, total_steps=10000, max_lr=1e-3):
    if step < warmup_steps:
        return max_lr * step / warmup_steps  # Linear warmup
    else:
        progress = (step - warmup_steps) / (total_steps - warmup_steps)
        return max_lr * 0.5 * (1 + np.cos(np.pi * progress))
```

```
Warmup + Cosine Decay:

LR │     ╭────╮
   │    ╱      ╲
   │   ╱        ╲
   │  ╱          ╲
   │ ╱            ╲
   │╱              ╲____
   └────────────────────── steps
   warmup    cosine decay
```

---

## 4. Optimizers

### SGD with Momentum

Accumulates a "velocity" to accelerate in consistent directions and dampen oscillations.

```
v = β·v + ∇L(θ)        (accumulate gradient)
θ = θ - α·v            (update with velocity)

β = 0.9 typically (momentum coefficient)
```

**Analogy:** A ball rolling downhill. It builds up speed in the consistent direction and smooths out bumps.

```
Without momentum:        With momentum:
   ╱╲╱╲╱╲               ╲
  ╱      ╲               ╲
 ╱        ╲               ╲
 (oscillates)             (smooth, faster)
```

### AdaGrad

Adapts learning rate per-parameter. Parameters with large gradients get smaller LR.

```
G = G + (∇L)²                    (accumulate squared gradients)
θ = θ - (α / √(G + ε)) · ∇L     (scale LR by inverse of accumulated gradient)
```

```
+ Good for sparse features (NLP embeddings)
- Learning rate monotonically decreases → can stop learning
```

### RMSProp

Fix AdaGrad's decaying LR by using exponential moving average.

```
E[g²] = β · E[g²] + (1-β) · (∇L)²
θ = θ - (α / √(E[g²] + ε)) · ∇L
```

### Adam (Adaptive Moment Estimation)

Combines momentum + RMSProp. THE default optimizer for deep learning.

```
m = β₁·m + (1-β₁)·∇L             (1st moment: mean of gradients)
v = β₂·v + (1-β₂)·(∇L)²          (2nd moment: variance of gradients)
m̂ = m / (1-β₁ᵗ)                   (bias correction)
v̂ = v / (1-β₂ᵗ)                   (bias correction)
θ = θ - α · m̂ / (√v̂ + ε)         (update)

Default: β₁=0.9, β₂=0.999, ε=1e-8, α=0.001
```

```python
class Adam:
    def __init__(self, lr=0.001, beta1=0.9, beta2=0.999, eps=1e-8):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.m = 0  # First moment
        self.v = 0  # Second moment
        self.t = 0  # Timestep
    
    def step(self, params, grads):
        self.t += 1
        self.m = self.beta1 * self.m + (1 - self.beta1) * grads
        self.v = self.beta2 * self.v + (1 - self.beta2) * grads**2
        
        # Bias correction
        m_hat = self.m / (1 - self.beta1**self.t)
        v_hat = self.v / (1 - self.beta2**self.t)
        
        params -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
        return params
```

### AdamW (Adam with Weight Decay)

Decouples weight decay from gradient-based update. Preferred for Transformers.

```
θ = θ - α · (m̂ / (√v̂ + ε) + λ·θ)
                                 ↑ weight decay applied directly
```

### Optimizer Comparison

```
┌────────────┬──────────────────┬────────────────────────────┐
│ Optimizer  │ Best For         │ Key Property               │
├────────────┼──────────────────┼────────────────────────────┤
│ SGD+Mom    │ Vision (CNNs)    │ Better generalization      │
│ Adam       │ Default choice   │ Fast convergence           │
│ AdamW      │ Transformers/NLP │ Proper weight decay        │
│ RMSProp    │ RNNs             │ Handles non-stationary     │
│ AdaGrad    │ Sparse data      │ Per-param adaptive LR      │
└────────────┴──────────────────┴────────────────────────────┘
```

---

## 5. Constrained Optimization (Lagrange Multipliers)

### Problem

Minimize f(x) subject to g(x) = 0.

### Solution: Lagrangian

```
L(x, λ) = f(x) + λ·g(x)

Set ∇L = 0:
∂L/∂x = 0  and  ∂L/∂λ = 0
```

**ML Applications:**
- SVM: Maximize margin subject to correct classification constraints
- Regularization can be viewed as constrained optimization
- KKT conditions for inequality constraints

```python
# SVM dual problem (simplified concept):
# Maximize: Σαᵢ - ½ΣΣ αᵢαⱼyᵢyⱼ(xᵢ·xⱼ)
# Subject to: αᵢ ≥ 0, Σαᵢyᵢ = 0
```

---

## 6. Convergence Theory

### Conditions for Convergence

For convex functions with gradient descent:
- **Lipschitz continuous gradient:** guarantees convergence with α < 1/L
- **Strong convexity:** guarantees linear convergence rate

### Convergence Rates

```
Gradient Descent:    O(1/T)         (sublinear for convex)
                     O(e⁻ᵀ)        (linear for strongly convex)
Newton's Method:     O(e⁻²ᵀ)       (quadratic near optimum)
SGD:                 O(1/√T)        (slower due to variance)
```

### Learning Rate and Convergence

```
For convex f with L-Lipschitz gradient:
- α < 2/L guarantees convergence
- α = 1/L is optimal (fastest convergence)
- α > 2/L diverges

In practice for neural nets:
- Start with lr=0.001 (Adam) or lr=0.1 (SGD)
- Use warmup for Transformers
- Decay over training
```

---

## 7. Applications in ML

### Training Neural Networks

```python
import torch
import torch.nn as nn
import torch.optim as optim

model = nn.Sequential(
    nn.Linear(784, 256),
    nn.ReLU(),
    nn.Linear(256, 10)
)

# Adam optimizer with learning rate schedule
optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

for epoch in range(100):
    for X_batch, y_batch in dataloader:
        optimizer.zero_grad()
        loss = nn.CrossEntropyLoss()(model(X_batch), y_batch)
        loss.backward()           # Compute gradients (chain rule)
        optimizer.step()          # Update params (Adam step)
    scheduler.step()              # Decay learning rate
```

### Hyperparameter Tuning

Optimization is also used for finding good hyperparameters:
- **Grid search:** Exhaustive (exponential cost)
- **Random search:** Often better than grid
- **Bayesian optimization:** Model the objective function, sample intelligently
- **Population-based training:** Evolutionary approach

### Gradient Clipping (Preventing Exploding Gradients)

```python
# Clip gradients to prevent explosion in RNNs/Transformers
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
```

---

## Convergence Diagram

```
Loss vs Training Steps:

Loss│╲
    │ ╲
    │  ╲  ← fast initial progress
    │   ╲
    │    ╲___
    │        ╲___
    │            ╲______  ← diminishing returns
    │                   ╲_________  ← plateau
    └──────────────────────────────── Steps

Common patterns:
- Initial rapid descent
- Possible plateau (learning rate may be too small)
- Sudden drops after LR schedule steps
- Final convergence to local minimum
```

---

## Summary

| Method | Update Rule | When to Use |
|--------|------------|-------------|
| SGD | θ -= α·∇L | Simple, good generalization |
| Momentum | v = βv + ∇L; θ -= αv | Accelerate convergence |
| Adam | Adaptive per-param LR + momentum | Default for most tasks |
| AdamW | Adam + decoupled weight decay | Transformers |

---

## Key Takeaways

1. **Mini-batch SGD** is the foundation — all optimizers build on it
2. **Adam** is the safe default. SGD+momentum can generalize better with tuning.
3. **Learning rate** is the most important hyperparameter. Use warmup + decay.
4. **Non-convexity** isn't as bad as theory suggests — SGD noise helps escape bad minima
5. **Gradient clipping** prevents training instability in deep networks
