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

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** For f(x) = x² - 4x + 5, find the minimum using calculus. Then simulate 10 steps of gradient descent starting at x=0 with learning rate η=0.3.

**Hint:** f'(x) = 0 for analytical min. GD update: x ← x - η·f'(x).

<details><summary>Solution</summary>

```
Analytical: f'(x) = 2x - 4 = 0 → x* = 2, f(2) = 1

Gradient descent (x₀=0, η=0.3):
f'(x) = 2x - 4
Step 1: x = 0 - 0.3(−4) = 1.2
Step 2: x = 1.2 - 0.3(−1.6) = 1.68
Step 3: x = 1.68 - 0.3(−0.64) = 1.872
Step 4: x = 1.872 - 0.3(−0.256) = 1.949
...converges to x=2 ✓
```
</details>

### Exercise 2 (Beginner)
**Problem:** Compare Batch GD, SGD, and Mini-batch GD on the update rule. What are the trade-offs of each?

**Hint:** Think about computation cost, convergence stability, and memory.

<details><summary>Solution</summary>

```
Batch GD:    θ ← θ - η·(1/n)Σ∇L(xᵢ,θ)  (use ALL data)
  + Stable convergence, accurate gradient
  − Slow per step, high memory, can't escape local minima

SGD:         θ ← θ - η·∇L(xᵢ,θ)  (use 1 sample)
  + Fast per step, low memory, noise helps escape local minima
  − High variance, noisy convergence

Mini-batch:  θ ← θ - η·(1/B)Σ∇L(xᵢ,θ)  (use B samples)
  + Best of both: GPU parallelism, moderate noise
  − Need to tune batch size (typically 32-256)
```
</details>

### Exercise 3 (Beginner)
**Problem:** Given f(x,y) = x² + 4y², compute the gradient at (2,1). What direction does gradient descent move? After one step with η=0.1, what's the new point?

**Hint:** ∇f = [∂f/∂x, ∂f/∂y]. GD moves in -∇f direction.

<details><summary>Solution</summary>

```
∇f = [2x, 8y]
At (2,1): ∇f = [4, 8]
GD direction: -∇f = [-4, -8]

New point: (2,1) - 0.1×(4,8) = (2-0.4, 1-0.8) = (1.6, 0.2)
f(2,1) = 4+4 = 8 → f(1.6, 0.2) = 2.56+0.16 = 2.72 (decreased ✓)
```
</details>

### Exercise 4 (Intermediate)
**Problem:** Implement momentum-based gradient descent. Show why momentum helps with narrow valleys (high condition number problems).

**Hint:** v ← βv + ∇f(x); x ← x - ηv. The velocity accumulates past gradients.

<details><summary>Solution</summary>

```
Without momentum on f(x,y) = x² + 100y² (condition number = 100):
- Oscillates wildly in y-direction (high curvature)
- Moves slowly in x-direction (low curvature)

With momentum (β=0.9):
- Velocity in y oscillates → dampened by averaging
- Velocity in x accumulates → accelerated
- Net effect: smoother, faster convergence

v = 0
For each step:
  v = 0.9×v + ∇f(x)     # velocity builds up in consistent direction
  x = x - η×v            # oscillations cancel, consistent motion amplified
```
</details>

### Exercise 5 (Intermediate)
**Problem:** Derive the Adam optimizer update rule from first principles. What problem does bias correction solve?

**Hint:** Adam combines momentum (first moment) and RMSProp (second moment) with bias correction.

<details><summary>Solution</summary>

```
Adam update at step t:
m_t = β₁·m_{t-1} + (1-β₁)·g_t        # first moment (mean of gradients)
v_t = β₂·v_{t-1} + (1-β₂)·g_t²       # second moment (mean of squared gradients)

Problem: m₀=0, v₀=0, so early estimates are biased toward 0.
At step 1: m₁ = (1-β₁)g₁ ≈ 0.1×g₁ (too small!)

Bias correction:
m̂_t = m_t / (1-β₁ᵗ)    # at t=1: m̂₁ = m₁/(1-0.9) = m₁/0.1 = g₁ ✓
v̂_t = v_t / (1-β₂ᵗ)    # similarly corrects v

Update: θ_t = θ_{t-1} - η·m̂_t/(√v̂_t + ε)

Default: β₁=0.9, β₂=0.999, η=0.001, ε=1e-8
```
</details>

### Exercise 6 (Intermediate)
**Problem:** Explain learning rate warmup and cosine annealing. Why do modern transformers use both?

**Hint:** Consider what happens at initialization when Adam's moment estimates are unreliable.

<details><summary>Solution</summary>

```
Learning rate warmup (linear, first ~1000 steps):
- At start: parameters are random, gradients are large and unreliable
- Large lr + unreliable gradients = catastrophic updates
- Warmup: lr goes 0 → target_lr gradually
- Allows Adam's moment estimates to stabilize

Cosine annealing (after warmup):
- lr(t) = lr_min + 0.5(lr_max - lr_min)(1 + cos(πt/T))
- Smoothly decreases lr over training
- Early: large lr for exploration
- Late: small lr for fine-grained convergence

Why transformers need both:
- Self-attention gradients can be very large early on
- Layer normalization + residuals make landscape sensitive
- Without warmup: training diverges in first few steps
```
</details>

### Exercise 7 (Intermediate)
**Problem:** L1 vs L2 regularization: minimize f(w) = ||y-Xw||² + λ||w||₁ vs f(w) = ||y-Xw||² + λ||w||². Why does L1 produce sparse solutions?

**Hint:** Consider the geometry of the constraint region (diamond vs circle) and where the loss contours touch.

<details><summary>Solution</summary>

```
L2 (Ridge): gradient of penalty = 2λw → shrinks all weights uniformly
  - Constraint region is a sphere: w₁²+w₂²≤t
  - Loss contours (ellipses) touch sphere at non-zero values

L1 (Lasso): subgradient of penalty = λ·sign(w) → constant push toward 0
  - Constraint region is a diamond: |w₁|+|w₂|≤t
  - Loss contours touch diamond at CORNERS (axis-aligned points)
  - Corners have some wᵢ = 0 → SPARSITY!

Why L1 is sparse:
  - The corners of the diamond are on coordinate axes
  - Probability of touching exactly at a corner is high
  - This zeros out irrelevant features → automatic feature selection
```
</details>

### Exercise 8 (Intermediate)
**Problem:** You're training a model and observe: training loss decreasing but validation loss increasing after epoch 10. Diagnose and list 5 solutions.

**Hint:** This is classic overfitting. Think regularization, data, and architecture.

<details><summary>Solution</summary>

```
Diagnosis: Overfitting — model memorizes training data after epoch 10.

Solutions:
1. Early stopping: stop training at epoch 10 (use validation loss as criterion)
2. Dropout: randomly zero out neurons (p=0.1-0.5) during training
3. Weight decay (L2 regularization): add λ||w||² to loss
4. Data augmentation: artificially expand training set
5. Reduce model capacity: fewer layers/units
6. Batch normalization: implicit regularization
7. More training data: collect/synthesize more examples
```
</details>

### Exercise 9 (Advanced)
**Problem:** Prove that gradient descent with step size η = 1/L on an L-smooth convex function converges at rate O(1/T), i.e., f(x_T) - f(x*) ≤ L||x₀-x*||²/(2T).

**Hint:** Use the descent lemma: f(y) ≤ f(x) + ∇f(x)ᵀ(y-x) + (L/2)||y-x||² for L-smooth f.

<details><summary>Solution</summary>

```
For x_{t+1} = x_t - (1/L)∇f(x_t):

By descent lemma with y = x_{t+1}:
f(x_{t+1}) ≤ f(x_t) + ∇f(x_t)ᵀ(x_{t+1}-x_t) + (L/2)||x_{t+1}-x_t||²
           = f(x_t) - (1/L)||∇f(x_t)||² + (L/2)(1/L²)||∇f(x_t)||²
           = f(x_t) - (1/2L)||∇f(x_t)||²

So: f(x_t) - f(x_{t+1}) ≥ (1/2L)||∇f(x_t)||²

By convexity: f(x*) ≥ f(x_t) + ∇f(x_t)ᵀ(x*-x_t)
→ f(x_t) - f(x*) ≤ ∇f(x_t)ᵀ(x_t-x*)  ≤ ||∇f(x_t)||·||x_t-x*||

Combining and telescoping over T steps:
f(x_T) - f(x*) ≤ L||x₀-x*||²/(2T) = O(1/T) ✓
```
</details>

### Exercise 10 (Advanced)
**Problem:** Explain why SGD generalizes better than full-batch GD, even when both reach similar training loss. Connect to implicit regularization and flat minima.

**Hint:** Consider the noise in SGD gradients and its effect on the minima found.

<details><summary>Solution</summary>

```
SGD's noise acts as implicit regularization:

1. Flat vs Sharp Minima:
   - SGD noise bounces out of sharp minima (high curvature, small basin)
   - Settles in flat minima (low curvature, large basin)
   - Flat minima generalize better (robust to input perturbation)

2. Implicit Regularization:
   - SGD with small batch size ≈ GD + Gaussian noise N(0, σ²)
   - σ² ∝ η/B (learning rate / batch size)
   - This noise penalizes sharp directions in parameter space
   - Equivalent to implicit L2-like regularization

3. PAC-Bayes Bound Perspective:
   - Flat minima have low description complexity
   - Generalization bound depends on "sharpness" of minimum
   - SGD biases toward solutions with low complexity

4. Evidence: Large batch training generalizes worse without tuning
   (need to increase lr proportionally, use warmup, etc.)
```
</details>

### Exercise 11 (Advanced)
**Problem:** Derive the KKT conditions for constrained optimization: minimize f(x) subject to g(x) ≤ 0 and h(x) = 0. Apply to SVM's dual formulation.

**Hint:** Lagrangian L = f(x) + λᵀg(x) + νᵀh(x). KKT = stationarity + primal feasibility + dual feasibility + complementary slackness.

<details><summary>Solution</summary>

```
KKT Conditions:
1. Stationarity: ∇f(x*) + Σλᵢ∇gᵢ(x*) + Σνⱼ∇hⱼ(x*) = 0
2. Primal feasibility: gᵢ(x*) ≤ 0, hⱼ(x*) = 0
3. Dual feasibility: λᵢ ≥ 0
4. Complementary slackness: λᵢ·gᵢ(x*) = 0 for all i

SVM Application:
minimize (1/2)||w||² subject to yᵢ(wᵀxᵢ+b) ≥ 1

Lagrangian: L = (1/2)||w||² - Σαᵢ[yᵢ(wᵀxᵢ+b) - 1]

KKT:
∂L/∂w = 0: w = Σαᵢyᵢxᵢ
∂L/∂b = 0: Σαᵢyᵢ = 0
αᵢ ≥ 0
αᵢ[yᵢ(wᵀxᵢ+b) - 1] = 0 → support vectors have αᵢ > 0
```
</details>

### Exercise 12 (Advanced)
**Problem:** Compare first-order (gradient descent) and second-order (Newton's method) optimization. Why isn't Newton's method used for training neural networks?

**Hint:** Newton: x ← x - H⁻¹∇f. Consider computational and memory costs.

<details><summary>Solution</summary>

```
First-order (GD):          Second-order (Newton):
Update: x -= η∇f          Update: x -= H⁻¹∇f
Memory: O(n)               Memory: O(n²) for Hessian
Compute: O(n)              Compute: O(n³) for inverse
Convergence: linear        Convergence: quadratic (near optimum)
Step choice: need η        Step: automatically scaled by curvature

Why not Newton for NNs (n = millions of params):
1. Storing H: n² = 10¹² entries (terabytes!)
2. Inverting H: O(n³) = 10¹⁸ ops (impossible)
3. H may not be PSD (non-convex) → Newton step may ascend

Approximations used instead:
- L-BFGS: approximate H⁻¹ with rank-k updates (O(nk))
- Adam: diagonal approximation of H
- K-FAC: Kronecker-factored approximation
- Hessian-free: compute H·v without forming H (Pearlmutter trick)
```
</details>

---

## Self-Assessment Quiz

**1. Gradient descent converges to the global minimum guaranteed for:**
- (a) Any differentiable function
- (b) Convex functions with appropriate learning rate
- (c) Neural networks
- (d) All continuous functions

<details><summary>Answer</summary>(b) Only for convex functions (with appropriate learning rate). Non-convex functions may converge to local minima or saddle points.</details>

**2. The learning rate in Adam is effectively:**
- (a) Fixed at the initial value
- (b) Adapted per-parameter based on gradient history
- (c) Always decreasing
- (d) The same as SGD

<details><summary>Answer</summary>(b) Adam adapts the effective learning rate per parameter: η/√(v̂+ε), where v̂ tracks squared gradient magnitudes.</details>

**3. L1 regularization produces sparse solutions because:**
- (a) It penalizes large weights more
- (b) The diamond-shaped constraint touches loss contours at axis-aligned corners
- (c) It's computationally faster
- (d) It increases the learning rate

<details><summary>Answer</summary>(b) The L1 ball (diamond) has corners on axes where some coordinates are exactly zero.</details>

**4. Batch normalization helps optimization by:**
- (a) Reducing the learning rate
- (b) Making the loss landscape smoother (more Lipschitz)
- (c) Removing all regularization
- (d) Increasing batch size

<details><summary>Answer</summary>(b) BN smooths the loss landscape, allowing larger learning rates and faster convergence.</details>

**5. A saddle point in high dimensions is:**
- (a) A local minimum
- (b) A point where the gradient is zero but it's a minimum in some directions and maximum in others
- (c) The global minimum
- (d) Always unstable

<details><summary>Answer</summary>(b) Saddle points have ∇f=0 but mixed curvature. In high dimensions, they're far more common than local minima.</details>

**6. Weight decay (L2 regularization) is equivalent to:**
- (a) Dropout
- (b) A Gaussian prior on weights in Bayesian inference
- (c) Batch normalization
- (d) Gradient clipping

<details><summary>Answer</summary>(b) L2 regularization λ||w||² corresponds to a Gaussian prior w ~ N(0, 1/(2λ)I) via MAP estimation.</details>

**7. The condition number of a matrix affects GD because:**
- (a) It determines the batch size
- (b) High condition number → elongated valleys → oscillation and slow convergence
- (c) It controls the learning rate schedule
- (d) It's irrelevant to optimization

<details><summary>Answer</summary>(b) Condition number κ = λ_max/λ_min. Large κ means very different curvatures in different directions, causing zigzag convergence.</details>

**8. Learning rate warmup is used because:**
- (a) GPUs need time to warm up
- (b) Early gradients are unreliable and large steps can cause divergence
- (c) It speeds up training
- (d) It reduces memory usage

<details><summary>Answer</summary>(b) At initialization, parameters are random, gradients are noisy/large, and Adam's moment estimates haven't stabilized yet.</details>

**9. Gradient clipping prevents:**
- (a) Vanishing gradients
- (b) Exploding gradients from causing NaN/divergence
- (c) Overfitting
- (d) Underfitting

<details><summary>Answer</summary>(b) Clipping caps gradient norm: if ||g|| > threshold, g = g × threshold/||g||. Prevents catastrophically large updates.</details>

**10. The main advantage of mini-batch SGD over full-batch GD is:**
- (a) It always finds better minima
- (b) Better GPU utilization + noise for escaping local optima + faster wall-clock time
- (c) It uses less total compute
- (d) It doesn't need a learning rate

<details><summary>Answer</summary>(b) Mini-batch balances: parallel computation (GPU), beneficial noise, and fast per-step updates.</details>

---

## Coding Challenges

### Challenge 1: Implement and Compare Optimizers
```python
"""
Implement from scratch: SGD, SGD+Momentum, RMSProp, Adam
Test all on the Rosenbrock function: f(x,y) = (1-x)² + 100(y-x²)²
Visualize convergence paths on a contour plot.
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

def rosenbrock(x, y):
    return (1-x)**2 + 100*(y-x**2)**2

def rosenbrock_grad(x, y):
    dx = -2*(1-x) - 400*x*(y-x**2)
    dy = 200*(y-x**2)
    return np.array([dx, dy])

class SGD:
    def __init__(self, lr=0.001):
        self.lr = lr
    def step(self, params, grads):
        return params - self.lr * grads

class MomentumSGD:
    def __init__(self, lr=0.001, beta=0.9):
        self.lr, self.beta = lr, beta
        self.v = 0
    def step(self, params, grads):
        self.v = self.beta * self.v + grads
        return params - self.lr * self.v

class RMSProp:
    def __init__(self, lr=0.001, beta=0.999, eps=1e-8):
        self.lr, self.beta, self.eps = lr, beta, eps
        self.v = 0
    def step(self, params, grads):
        self.v = self.beta * self.v + (1-self.beta) * grads**2
        return params - self.lr * grads / (np.sqrt(self.v) + self.eps)

class Adam:
    def __init__(self, lr=0.01, beta1=0.9, beta2=0.999, eps=1e-8):
        self.lr, self.beta1, self.beta2, self.eps = lr, beta1, beta2, eps
        self.m, self.v, self.t = 0, 0, 0
    def step(self, params, grads):
        self.t += 1
        self.m = self.beta1*self.m + (1-self.beta1)*grads
        self.v = self.beta2*self.v + (1-self.beta2)*grads**2
        m_hat = self.m / (1-self.beta1**self.t)
        v_hat = self.v / (1-self.beta2**self.t)
        return params - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)

# Run optimization
optimizers = {'SGD': SGD(0.001), 'Momentum': MomentumSGD(0.001), 
              'RMSProp': RMSProp(0.001), 'Adam': Adam(0.01)}
paths = {}

for name, opt in optimizers.items():
    point = np.array([-1.0, 1.0])
    path = [point.copy()]
    for _ in range(5000):
        grad = rosenbrock_grad(point[0], point[1])
        grad = np.clip(grad, -10, 10)
        point = opt.step(point, grad)
        path.append(point.copy())
    paths[name] = np.array(path)

# Plot
fig, ax = plt.subplots(figsize=(10, 8))
x = np.linspace(-2, 2, 200)
y = np.linspace(-1, 3, 200)
X, Y = np.meshgrid(x, y)
Z = rosenbrock(X, Y)
ax.contour(X, Y, Z, levels=np.logspace(-1, 3, 20), cmap='gray', alpha=0.5)
for name, path in paths.items():
    ax.plot(path[:500, 0], path[:500, 1], label=name, linewidth=1.5)
ax.plot(1, 1, 'r*', markersize=15)
ax.legend(); ax.set_title('Optimizer Comparison on Rosenbrock')
plt.show()
```
</details>

### Challenge 2: Learning Rate Finder
```python
"""
Implement the learning rate range test (Smith 2017):
1. Start with a very small lr (1e-7)
2. Exponentially increase lr each batch
3. Record loss at each lr
4. Plot loss vs lr — optimal lr is where loss decreases fastest
Apply to a simple regression problem.
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

# Generate regression data
np.random.seed(42)
X = np.random.randn(1000, 10)
w_true = np.random.randn(10)
y = X @ w_true + 0.1*np.random.randn(1000)

def lr_range_test(X, y, lr_min=1e-7, lr_max=10, n_steps=200, batch_size=32):
    w = np.zeros(X.shape[1])
    lr_mult = (lr_max/lr_min)**(1/n_steps)
    
    lrs, losses = [], []
    lr = lr_min
    
    for step in range(n_steps):
        # Mini-batch
        idx = np.random.choice(len(X), batch_size)
        X_b, y_b = X[idx], y[idx]
        
        # Forward + loss
        pred = X_b @ w
        loss = np.mean((pred - y_b)**2)
        
        # Backward
        grad = (2/batch_size) * X_b.T @ (pred - y_b)
        w -= lr * grad
        
        lrs.append(lr)
        losses.append(loss)
        lr *= lr_mult
        
        if loss > 4 * losses[0]:  # Diverging
            break
    
    return lrs, losses

lrs, losses = lr_range_test(X, y)

plt.figure(figsize=(10, 5))
plt.semilogx(lrs, losses)
plt.xlabel('Learning Rate')
plt.ylabel('Loss')
plt.title('Learning Rate Range Test')
# Find steepest descent
smoothed = np.convolve(losses, np.ones(5)/5, mode='valid')
best_idx = np.argmin(np.diff(smoothed))
plt.axvline(x=lrs[best_idx], color='r', linestyle='--', label=f'Suggested lr: {lrs[best_idx]:.4f}')
plt.legend()
plt.show()
```
</details>

### Challenge 3: Implement Gradient Descent with Constraints (Projected GD)
```python
"""
Minimize f(x,y) = (x-3)² + (y-3)² subject to x+y ≤ 4 (and x,y ≥ 0).
1. Implement projected gradient descent
2. Project infeasible points onto the constraint set
3. Visualize the optimization path with constraint boundaries
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import linprog

def f(x, y): return (x-3)**2 + (y-3)**2
def grad_f(x, y): return np.array([2*(x-3), 2*(y-3)])

def project(point):
    """Project onto feasible set: x+y≤4, x≥0, y≥0"""
    x, y = point
    x, y = max(0, x), max(0, y)  # Non-negativity
    if x + y > 4:  # Project onto x+y=4 line
        # Closest point on x+y=4 to (x,y): minimize ||p-(x,y)||² s.t. p1+p2=4
        x_new = (x - y + 4) / 2
        y_new = (y - x + 4) / 2
        x, y = max(0, x_new), max(0, y_new)
        if x + y > 4:
            if x > y: x, y = 4, 0
            else: x, y = 0, 4
    return np.array([x, y])

# Projected gradient descent
point = np.array([0.0, 0.0])
path = [point.copy()]
lr = 0.1

for _ in range(100):
    grad = grad_f(point[0], point[1])
    point = point - lr * grad
    point = project(point)
    path.append(point.copy())

path = np.array(path)

# Visualize
fig, ax = plt.subplots(figsize=(8, 8))
x = np.linspace(-0.5, 5, 100)
y = np.linspace(-0.5, 5, 100)
X, Y = np.meshgrid(x, y)
Z = f(X, Y)
ax.contour(X, Y, Z, levels=20, alpha=0.5)
ax.fill([0,4,0], [0,0,4], alpha=0.1, color='green', label='Feasible region')
ax.plot([0,4], [4,0], 'g-', linewidth=2)
ax.plot(path[:,0], path[:,1], 'r.-', label='Projected GD')
ax.plot(path[-1,0], path[-1,1], 'r*', markersize=15)
ax.set_xlim(-0.5, 5); ax.set_ylim(-0.5, 5)
ax.legend(); ax.set_title(f'Solution: ({path[-1,0]:.2f}, {path[-1,1]:.2f})')
plt.show()
```
</details>

### Challenge 4: Early Stopping Implementation
```python
"""
Implement training with early stopping:
1. Train a polynomial regression model (degree 15) on noisy sine data
2. Track training and validation loss each epoch
3. Stop when validation loss hasn't improved for 'patience' epochs
4. Compare: no regularization vs early stopping vs L2 regularization
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)
X = np.sort(np.random.uniform(0, 2*np.pi, 50))
y = np.sin(X) + 0.2*np.random.randn(50)
X_val = np.sort(np.random.uniform(0, 2*np.pi, 20))
y_val = np.sin(X_val) + 0.2*np.random.randn(20)

def poly_features(X, degree=15):
    return np.column_stack([X**i for i in range(degree+1)])

def train_with_early_stopping(X, y, X_val, y_val, lr=0.0001, patience=50, l2=0.0):
    Phi = poly_features(X)
    Phi_val = poly_features(X_val)
    w = np.zeros(Phi.shape[1])
    
    train_losses, val_losses = [], []
    best_val_loss, best_w, wait = float('inf'), w.copy(), 0
    
    for epoch in range(5000):
        pred = Phi @ w
        loss = np.mean((pred - y)**2) + l2*np.sum(w**2)
        val_loss = np.mean((Phi_val @ w - y_val)**2)
        train_losses.append(loss)
        val_losses.append(val_loss)
        
        grad = (2/len(X)) * Phi.T @ (pred - y) + 2*l2*w
        w -= lr * grad
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_w = w.copy()
            wait = 0
        else:
            wait += 1
            if patience and wait >= patience:
                break
    
    return best_w, train_losses, val_losses

# Compare approaches
w_no_reg, tl1, vl1 = train_with_early_stopping(X, y, X_val, y_val, patience=None, l2=0)
w_early, tl2, vl2 = train_with_early_stopping(X, y, X_val, y_val, patience=50, l2=0)
w_l2, tl3, vl3 = train_with_early_stopping(X, y, X_val, y_val, patience=None, l2=0.01)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].plot(vl1[:500], label='No reg'); axes[0].plot(vl2[:500], label='Early stop')
axes[0].plot(vl3[:500], label='L2'); axes[0].legend(); axes[0].set_title('Validation Loss')

X_plot = np.linspace(0, 2*np.pi, 200)
Phi_plot = poly_features(X_plot)
axes[1].scatter(X, y, alpha=0.5)
axes[1].plot(X_plot, np.sin(X_plot), 'k--', label='True')
axes[1].plot(X_plot, Phi_plot@w_early, label='Early stop')
axes[1].plot(X_plot, Phi_plot@w_l2, label='L2')
axes[1].set_ylim(-2, 2); axes[1].legend(); axes[1].set_title('Predictions')
plt.tight_layout(); plt.show()
```
</details>

### Challenge 5: Implement Learning Rate Scheduling
```python
"""
Implement and compare these schedules:
1. Step decay (halve every 30 epochs)
2. Exponential decay
3. Cosine annealing
4. Warmup + cosine
5. One-cycle policy
Train a simple model and plot lr vs epoch and loss vs epoch for each.
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

def step_decay(epoch, lr0=0.1, drop=0.5, period=30):
    return lr0 * drop**(epoch // period)

def exponential_decay(epoch, lr0=0.1, decay=0.95):
    return lr0 * decay**epoch

def cosine_annealing(epoch, lr0=0.1, T=100):
    return lr0 * 0.5 * (1 + np.cos(np.pi * epoch / T))

def warmup_cosine(epoch, lr0=0.1, warmup=10, T=100):
    if epoch < warmup:
        return lr0 * epoch / warmup
    return lr0 * 0.5 * (1 + np.cos(np.pi * (epoch-warmup) / (T-warmup)))

def one_cycle(epoch, lr_max=0.1, T=100):
    if epoch < T//2:
        return lr_max * epoch / (T//2)
    else:
        return lr_max * (1 - (epoch - T//2) / (T//2))

# Visualize schedules
epochs = np.arange(100)
schedules = {
    'Step': [step_decay(e) for e in epochs],
    'Exponential': [exponential_decay(e) for e in epochs],
    'Cosine': [cosine_annealing(e) for e in epochs],
    'Warmup+Cosine': [warmup_cosine(e) for e in epochs],
    'One-Cycle': [one_cycle(e) for e in epochs],
}

# Train with each schedule on quadratic
def train(schedule_fn, n_epochs=100):
    x = np.array([5.0])
    losses = []
    for epoch in range(n_epochs):
        lr = schedule_fn(epoch)
        grad = 2*x  # f(x) = x², f'(x) = 2x
        x = x - lr * grad
        losses.append(float(x**2))
    return losses

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
for name, lrs in schedules.items():
    ax1.plot(lrs, label=name)
    losses = train(lambda e, n=name: schedules[n][min(e, 99)])
    ax2.plot(losses, label=name)

ax1.set_xlabel('Epoch'); ax1.set_ylabel('Learning Rate'); ax1.legend()
ax2.set_xlabel('Epoch'); ax2.set_ylabel('Loss'); ax2.set_yscale('log'); ax2.legend()
plt.tight_layout(); plt.show()
```
</details>

---

## Interview Questions

### 1. Why does Adam sometimes generalize worse than SGD with momentum?
<details><summary>Answer</summary>

Adam can generalize worse because:
1. **Adaptive lr reduces noise**: The per-parameter scaling (dividing by √v) reduces the effective noise, making Adam behave more like full-batch GD → less implicit regularization
2. **Sharp minima**: Adam can converge to sharp minima that SGD's noise would escape
3. **Non-convergence issues**: Adam can diverge in certain cases (addressed by AMSGrad/AdamW)
4. **Weight decay interaction**: L2 regularization in Adam is not equivalent to weight decay (AdamW fixes this)

Practice: Use AdamW for transformers, SGD+momentum for CNNs/ResNets where generalization matters most.
</details>

### 2. Explain the difference between model parallelism and data parallelism in distributed training.
<details><summary>Answer</summary>

**Data parallelism**: Same model on multiple GPUs, different data batches. Average gradients across devices. Simple but limited by model size fitting in one GPU.

**Model parallelism**: Split model across GPUs (e.g., different layers on different devices). Necessary for huge models but has communication overhead and pipeline bubbles.

**Modern approaches**: 
- ZeRO (DeepSpeed): partitions optimizer states, gradients, and parameters
- Pipeline parallelism: split layers + micro-batching to reduce bubbles
- Tensor parallelism: split individual layers (attention heads) across GPUs
</details>

### 3. How do you choose the right optimizer for a new task?
<details><summary>Answer</summary>

Rules of thumb:
- **NLP/Transformers**: AdamW (lr ~1e-4 to 3e-4, warmup, cosine decay)
- **Computer Vision (CNNs)**: SGD+momentum (lr ~0.1, step decay) often generalizes better
- **GANs**: Adam with low β₁ (0.0-0.5), careful lr balancing
- **Fine-tuning**: Lower lr (10-100x smaller), AdamW, short warmup
- **Few parameters/convex**: L-BFGS or Adam converge fast
- **Reinforcement learning**: Adam with small lr, gradient clipping

Always: start with Adam (it's robust), then try SGD+momentum if generalization matters.
</details>

### 4. What is gradient accumulation and when would you use it?
<details><summary>Answer</summary>

Gradient accumulation simulates larger batch sizes when GPU memory is limited:
```
for i in range(accumulation_steps):
    loss = model(mini_batch[i]) / accumulation_steps
    loss.backward()  # gradients accumulate
optimizer.step()  # update once with accumulated gradients
optimizer.zero_grad()
```

Effective batch size = mini_batch_size × accumulation_steps

Use when:
- Model barely fits in memory (no room for large batches)
- Task benefits from large batch (contrastive learning, batch norm stability)
- Multi-GPU training isn't available
</details>

### 5. Explain the loss landscape of neural networks and why optimization works despite non-convexity.
<details><summary>Answer</summary>

Key insights about NN loss landscapes:
1. **Saddle points dominate**: In d dimensions, random critical points are almost certainly saddle points (probability of all d eigenvalues being positive ≈ 2⁻ᵈ)
2. **Local minima quality**: Local minima tend to have similar loss values (connected by low-loss paths)
3. **Overparameterization**: More parameters than data → many global minima → easier to find one
4. **Loss surface is "flat enough"**: Sharp barriers between good solutions are rare in practice
5. **Mode connectivity**: Good solutions are connected by simple curves in parameter space

Why SGD works: noise from mini-batches + momentum navigates the landscape effectively, preferring flat regions that generalize well.
</details>

### 6. What is mixed-precision training and how does it speed up training?
<details><summary>Answer</summary>

Mixed-precision uses FP16 for most computations and FP32 for critical ones:
- Forward/backward: FP16 (2x less memory, faster on tensor cores)
- Weight master copy: FP32 (maintains precision for small updates)
- Loss scaling: multiply loss by large factor before backward (prevents gradient underflow in FP16)

Benefits:
- 2x less GPU memory → larger batches or models
- 2-3x faster computation (tensor cores optimized for FP16)
- Nearly identical accuracy

Key: loss scaling prevents gradients < 2⁻²⁴ (FP16 min) from becoming zero.
</details>
