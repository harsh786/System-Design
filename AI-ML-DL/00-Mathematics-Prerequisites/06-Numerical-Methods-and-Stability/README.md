# Numerical Methods and Stability for ML/DL Practitioners

> This is what separates people who can debug NaN errors at 3 AM from those who can't.

---

## 1. Floating Point Representation

### IEEE 754 Standard

Every floating point number is stored as: **(-1)^sign × 2^(exponent - bias) × 1.mantissa**

```
Float32 (single precision) - 32 bits:
┌───┬──────────┬───────────────────────────┐
│ S │ Exponent │        Mantissa           │
│1b │   8 bits │        23 bits            │
└───┴──────────┴───────────────────────────┘
 31   30    23   22                       0

Float16 (half precision) - 16 bits:
┌───┬───────┬────────────┐
│ S │ Exp   │  Mantissa  │
│1b │ 5 bits│  10 bits   │
└───┴───────┴────────────┘

BFloat16 (Brain Float) - 16 bits:
┌───┬──────────┬─────────┐
│ S │ Exponent │Mantissa │
│1b │  8 bits  │ 7 bits  │
└───┴──────────┴─────────┘

Float64 (double precision) - 64 bits:
┌───┬───────────┬──────────────────────────────────────────────────┐
│ S │ Exponent  │                  Mantissa                        │
│1b │  11 bits  │                  52 bits                         │
└───┴───────────┴──────────────────────────────────────────────────┘
```

### Comparison Table

| Type    | Bits | Exponent | Mantissa | Range (approx)      | Precision (decimal) | Machine Epsilon |
|---------|------|----------|----------|----------------------|---------------------|-----------------|
| float16 | 16   | 5        | 10       | ±6.5 × 10^4         | ~3.3 digits         | 9.77 × 10^-4   |
| bfloat16| 16   | 8        | 7        | ±3.4 × 10^38        | ~2.4 digits         | 3.91 × 10^-3   |
| float32 | 32   | 8        | 23       | ±3.4 × 10^38        | ~7.2 digits         | 1.19 × 10^-7   |
| float64 | 64   | 11       | 52       | ±1.8 × 10^308       | ~15.9 digits        | 2.22 × 10^-16  |

### Why 0.1 + 0.2 != 0.3

```python
>>> 0.1 + 0.2
0.30000000000000004

# 0.1 in binary is 0.0001100110011... (repeating)
# Just like 1/3 = 0.333... in decimal, some decimals are infinite in binary.
# The finite representation introduces rounding error.

import struct
def show_float_bits(f):
    """Show the actual bits stored for a float32."""
    packed = struct.pack('!f', f)
    bits = ''.join(f'{byte:08b}' for byte in packed)
    return f"Sign:{bits[0]} Exp:{bits[1:9]} Mantissa:{bits[9:]}"

print(show_float_bits(0.1))
# Sign:0 Exp:01111011 Mantissa:10011001100110011001101
print(show_float_bits(0.3))
# Sign:0 Exp:01111101 Mantissa:00110011001100110011010
```

### Machine Epsilon

The smallest number ε such that `1.0 + ε != 1.0` in floating point.

```python
import numpy as np

print(np.finfo(np.float16).eps)   # 0.000977 (~10^-3)
print(np.finfo(np.float32).eps)   # 1.1920929e-07 (~10^-7)
print(np.finfo(np.float64).eps)   # 2.220446e-16 (~10^-16)

# Practical implication: if you add 1e-8 to a float32 value of 1.0, NOTHING HAPPENS
x = np.float32(1.0)
y = x + np.float32(1e-8)
print(x == y)  # True! The addition was lost.
```

### Why ML Uses float32 (and When to Use Others)

- **float64**: Overkill for ML. Weights don't need 15 digits of precision. 2x memory cost.
- **float32**: Default. Good range, sufficient precision for gradient updates.
- **float16**: 2x faster on GPUs with Tensor Cores, but tiny range (max 65504) causes overflow in loss/gradients.
- **bfloat16**: Same range as float32 (8-bit exponent!) but less precision. Ideal for training — overflow-safe.

### Subnormal (Denormalized) Numbers

When exponent bits are all zero, the implicit leading 1 becomes 0, allowing representation of numbers closer to zero (at reduced precision). This prevents a "gap" between zero and the smallest normal number.

```python
import numpy as np
# Smallest normal float32: ~1.18e-38
# Smallest subnormal float32: ~1.4e-45
print(np.nextafter(np.float32(0), np.float32(1)))  # 1e-45 (subnormal)
```

**What happens if you ignore this:** Your model silently loses precision in small gradient updates, weight decay terms approach zero and vanish, and you wonder why training "stalls" after many epochs.

---

## 2. Numerical Stability

### What Numerical Instability Means

An algorithm is **numerically unstable** if small perturbations in input produce disproportionately large changes in output.

```
Stable:   input ± ε  →  output ± O(ε)
Unstable: input ± ε  →  output ± O(1/ε)  or worse
```

### Condition Number

The condition number κ(A) measures how sensitive Ax = b is to perturbations:

```
κ(A) = ||A|| · ||A^(-1)|| = σ_max / σ_min
```

```python
import numpy as np

# Well-conditioned matrix
A_good = np.array([[2, 1], [1, 3]], dtype=np.float64)
print(f"Condition number: {np.linalg.cond(A_good):.2f}")  # ~2.6

# Ill-conditioned matrix (nearly singular)
A_bad = np.array([[1, 1], [1, 1.0001]], dtype=np.float64)
print(f"Condition number: {np.linalg.cond(A_bad):.2f}")  # ~40000

# Solving with ill-conditioned matrix:
b = np.array([2, 2.0001])
x = np.linalg.solve(A_bad, b)  # Solution is very sensitive to noise in b
```

**Rule of thumb:** If κ(A) ≈ 10^k, you lose about k digits of accuracy.

### Log-Sum-Exp Trick (Critical for Softmax)

**Problem:** Softmax of large numbers overflows.

```python
import numpy as np

# UNSTABLE softmax
def softmax_unstable(x):
    return np.exp(x) / np.sum(np.exp(x))

logits = np.array([1000, 1001, 1002])
print(softmax_unstable(logits))  # [nan, nan, nan] - OVERFLOW!

# STABLE softmax: subtract max
def softmax_stable(x):
    x_max = np.max(x)
    exp_x = np.exp(x - x_max)  # Now largest exponent is 0
    return exp_x / np.sum(exp_x)

print(softmax_stable(logits))  # [0.09, 0.245, 0.665] - correct!
```

**Why it works:** softmax(x) = softmax(x - c) for any constant c. Subtracting max ensures no exp() argument exceeds 0.

### Numerically Stable Log-Sigmoid

```python
import numpy as np

# UNSTABLE: log(sigmoid(x))
def log_sigmoid_unstable(x):
    return np.log(1 / (1 + np.exp(-x)))

# For large negative x: sigmoid → 0, log(0) → -inf
# For large positive x: exp(-x) underflows (but log(1) = 0, so actually OK)
print(log_sigmoid_unstable(-1000))  # -inf (wrong, should be ≈ -1000)

# STABLE: log_sigmoid(x) = -softplus(-x) = -log(1 + exp(-x))
def log_sigmoid_stable(x):
    # Use: log(sigmoid(x)) = x - softplus(x) = -softplus(-x)
    return -np.logaddexp(0, -x)  # numpy's logaddexp is numerically stable

print(log_sigmoid_stable(-1000))   # -1000.0 (correct!)
print(log_sigmoid_stable(1000))    # 0.0 (correct!)
```

### Numerically Stable Cross-Entropy Loss

```python
import numpy as np

# UNSTABLE binary cross-entropy
def bce_unstable(y_true, y_pred):
    return -(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

# If y_pred = 0 or 1 exactly → log(0) = -inf → NaN in gradients
print(bce_unstable(1, 0.0))  # inf!

# STABLE: work with logits directly, never compute probabilities
def bce_with_logits(y_true, logits):
    # -[y*log(σ(z)) + (1-y)*log(1-σ(z))]
    # = max(z,0) - y*z + log(1 + exp(-|z|))
    return np.maximum(logits, 0) - y_true * logits + np.log(1 + np.exp(-np.abs(logits)))

print(bce_with_logits(1, -100.0))  # 100.0 (correct!)
print(bce_with_logits(0, 100.0))   # 100.0 (correct!)
```

**This is why PyTorch has `F.binary_cross_entropy_with_logits` — ALWAYS use it over manual implementations.**

### Why Batch Normalization Helps Stability

```
BatchNorm normalizes activations to ~N(0,1) at each layer:
  x̂ = (x - μ_batch) / √(σ²_batch + ε)

This keeps values in the "well-behaved" range where:
- Sigmoid/tanh don't saturate
- Gradients don't vanish or explode
- Float arithmetic has good relative precision near 0-1
```

**What happens if you ignore stability:** Training produces NaN after a few hundred iterations. Loss goes to infinity. You waste hours before finding that one log(0) buried in a custom loss function.

---

## 3. Overflow and Underflow

### Common ML Scenarios

```python
import numpy as np

# === OVERFLOW ===

# 1. Softmax with large logits
logits = np.float32([100, 200, 500])
print(np.exp(logits))  # [inf, inf, inf] - float32 max is ~3.4e38, exp(500) ≈ 1.4e217

# 2. Exploding gradients → NaN weights
# Simulating gradient explosion in RNN
gradient = np.float32(1.0)
for step in range(200):
    gradient *= 1.1  # Each step multiplies by slightly > 1
print(f"After 200 steps: {gradient}")  # inf!

# === UNDERFLOW ===

# 3. Product of many small probabilities
probs = np.float32([0.01] * 200)
product = np.prod(probs)
print(f"Product of 200 × 0.01: {product}")  # 0.0 (should be 1e-400)

# 4. Vanishing gradients through sigmoid
def sigmoid(x): return 1 / (1 + np.exp(-x))
def sigmoid_grad(x): return sigmoid(x) * (1 - sigmoid(x))

# sigmoid'(x) < 0.25 always. After 50 layers:
grad = np.float32(1.0)
for _ in range(50):
    grad *= 0.25  # max sigmoid gradient
print(f"Gradient after 50 sigmoid layers: {grad}")  # 0.0 (underflow!)
```

### Solutions

```python
import numpy as np

# === Solution 1: Log-space computation ===
# Instead of multiplying probabilities, add log-probabilities
log_probs = np.float32([-4.605] * 200)  # log(0.01)
log_product = np.sum(log_probs)
print(f"Log of product: {log_product}")  # -921.0 (exact! no underflow)

# === Solution 2: Gradient clipping ===
def clip_gradients(gradients, max_norm=1.0):
    total_norm = np.sqrt(sum(np.sum(g**2) for g in gradients))
    clip_coef = max_norm / (total_norm + 1e-6)
    if clip_coef < 1:
        gradients = [g * clip_coef for g in gradients]
    return gradients

# PyTorch: torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

# === Solution 3: Loss scaling (for mixed precision) ===
# Scale loss up before backward to prevent gradient underflow in float16
loss_scale = 1024.0
scaled_loss = loss * loss_scale  # Prevent underflow in float16 gradients
# After backward:
# gradients /= loss_scale  # Unscale before optimizer step
```

### The Log-Space Pattern

```
RULE: If you're multiplying many small numbers, ALWAYS work in log-space.

Instead of: p = p1 * p2 * ... * pn         (underflows)
Do:         log_p = log_p1 + log_p2 + ... + log_pn  (stable)

Instead of: p = exp(a) / sum(exp(ai))       (overflows)
Do:         log_p = a - logsumexp(a)         (stable)
```

**What happens if you ignore this:** Your language model outputs all zeros for long sequences. Your VAE's KL divergence is always 0. Your reward model in RLHF produces NaN after one episode.

---

## 4. Numerical Differentiation

### Finite Differences

```
Forward:   f'(x) ≈ [f(x+h) - f(x)] / h              Error: O(h)
Backward:  f'(x) ≈ [f(x) - f(x-h)] / h              Error: O(h)
Central:   f'(x) ≈ [f(x+h) - f(x-h)] / (2h)         Error: O(h²)
```

### Error Analysis: The Step Size Dilemma

```
Total error = Truncation error + Rounding error
            = O(h^p)           + O(ε/h)

For central differences:
  Total ≈ h²/6 · |f'''| + ε_mach / h

Optimal h ≈ (ε_mach)^(1/3) ≈ 5×10^-6 for float64
                              ≈ 5×10^-3 for float32
```

```python
import numpy as np

def f(x): return np.sin(x)
def f_prime(x): return np.cos(x)  # Analytical derivative

x = 1.0
true_deriv = f_prime(x)

# Show error vs step size
print(f"{'h':<12} {'Forward':<15} {'Central':<15}")
for k in range(1, 17):
    h = 10**(-k)
    forward = (f(x + h) - f(x)) / h
    central = (f(x + h) - f(x - h)) / (2 * h)
    print(f"1e-{k:<3}     {abs(forward-true_deriv):.2e}       {abs(central-true_deriv):.2e}")

# Output shows sweet spot around h=1e-8 for central differences (float64)
# Too small: rounding error dominates. Too large: truncation error dominates.
```

### Gradient Checking

```python
import numpy as np

def gradient_check(f, x, analytic_grad, eps=1e-5):
    """
    Verify backprop implementation by comparing with finite differences.
    Use this EVERY TIME you implement a custom backward pass.
    """
    numeric_grad = np.zeros_like(x)
    for i in range(len(x)):
        x_plus = x.copy()
        x_minus = x.copy()
        x_plus[i] += eps
        x_minus[i] -= eps
        numeric_grad[i] = (f(x_plus) - f(x_minus)) / (2 * eps)
    
    # Relative error (handles gradients near zero)
    diff = np.linalg.norm(numeric_grad - analytic_grad)
    norm_sum = np.linalg.norm(numeric_grad) + np.linalg.norm(analytic_grad)
    
    if norm_sum == 0:
        rel_error = 0
    else:
        rel_error = diff / norm_sum
    
    # Thresholds:
    # < 1e-7: excellent (float64)
    # < 1e-5: acceptable
    # > 1e-3: BUG in your backward pass
    print(f"Relative error: {rel_error:.2e}", end=" ")
    if rel_error < 1e-5:
        print("PASS")
    else:
        print("FAIL - check your gradients!")
    
    return rel_error

# Example: checking gradient of f(x) = x^T A x
A = np.random.randn(5, 5)
A = A + A.T  # Symmetric
x = np.random.randn(5)

f = lambda x: x @ A @ x
analytic_grad = 2 * A @ x  # Known gradient

gradient_check(f, x, analytic_grad)
```

**What happens if you ignore this:** You implement a custom attention layer, the loss decreases slowly, you think it's a hyperparameter issue, spend 3 days tuning, then realize your backward pass had a transpose error.

---

## 5. Matrix Computations in Practice

### Never Invert Matrices

```python
import numpy as np
import time

n = 1000
A = np.random.randn(n, n) + n * np.eye(n)  # Well-conditioned
b = np.random.randn(n)

# BAD: Computing A^(-1) then multiplying
start = time.time()
x_bad = np.linalg.inv(A) @ b
t_bad = time.time() - start

# GOOD: Solve directly
start = time.time()
x_good = np.linalg.solve(A, b)
t_good = time.time() - start

print(f"Inverse: {t_bad*1000:.1f}ms, error: {np.linalg.norm(A @ x_bad - b):.2e}")
print(f"Solve:   {t_good*1000:.1f}ms, error: {np.linalg.norm(A @ x_good - b):.2e}")
# Solve is ~2x faster AND more accurate
```

### Cholesky Decomposition

For positive definite matrices (covariance matrices, kernel matrices):

```python
import numpy as np

# Sampling from multivariate Gaussian N(μ, Σ)
n = 3
Sigma = np.array([[2, 1, 0.5], [1, 3, 1], [0.5, 1, 2]])  # Positive definite
mu = np.zeros(n)

# BAD: np.random.multivariate_normal does Σ = UDU^T internally each call
# GOOD: Precompute Cholesky L where Σ = LL^T
L = np.linalg.cholesky(Sigma)

# Generate samples: x = μ + L @ z, where z ~ N(0, I)
z = np.random.randn(n)
sample = mu + L @ z  # Much faster for repeated sampling

# Also for solving Σx = b:
b = np.array([1, 2, 3])
# Solve Ly = b (forward substitution), then L^T x = y (back substitution)
from scipy.linalg import cho_solve, cho_factor
c, low = cho_factor(Sigma)
x = cho_solve((c, low), b)
```

### SVD for Numerical Rank

```python
import numpy as np

# Rank-deficient matrix (common in feature matrices with correlated features)
A = np.random.randn(100, 10)
A = np.column_stack([A, A[:, 0] + 1e-10 * np.random.randn(100)])  # Near-duplicate column

U, s, Vt = np.linalg.svd(A, full_matrices=False)
print("Singular values:", s)
# Last singular value will be ≈ 0, indicating rank deficiency

# Truncated SVD for stable pseudo-inverse
tol = 1e-6
rank = np.sum(s > tol * s[0])
print(f"Numerical rank: {rank} (matrix shape: {A.shape})")
```

### Sparse Matrix Operations

```python
from scipy import sparse
import numpy as np

# Dense: O(n²) memory, O(n²) for matrix-vector multiply
# Sparse: O(nnz) memory, O(nnz) for matrix-vector multiply

n = 10000
# Adjacency matrix of a graph (typically <1% non-zero)
density = 0.01
A_dense = np.random.rand(n, n) * (np.random.rand(n, n) < density)

# CSR (Compressed Sparse Row) - fast row slicing, matrix-vector products
A_sparse = sparse.csr_matrix(A_dense)

print(f"Dense memory:  {A_dense.nbytes / 1e6:.1f} MB")
print(f"Sparse memory: {A_sparse.data.nbytes / 1e6:.1f} MB")  # ~100x less
```

**What happens if you ignore this:** Your GP regression on 10K points takes 10 minutes instead of 10 seconds. Your GNN runs out of memory on a modest graph.

---

## 6. Common NaN/Inf Debugging in ML

### The NaN Debugging Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│                  NaN DEBUGGING CHECKLIST                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. □ Check input data: any NaN/Inf in features or labels?       │
│ 2. □ Check learning rate: reduce by 10x, does NaN disappear?    │
│ 3. □ Check loss function: log(0)? division by zero?             │
│ 4. □ Print gradient norms per layer: are they exploding?        │
│ 5. □ Check weight init: too large? zeros where shouldn't be?    │
│ 6. □ Check for 0/0 or inf-inf in custom operations              │
│ 7. □ If using mixed precision: is loss scaling configured?      │
│ 8. □ Add epsilon to ALL denominators: / (x + 1e-8)             │
│ 9. □ Check batch norm with batch_size=1 (variance=0!)           │
│10. □ Run with torch.autograd.set_detect_anomaly(True)           │
└─────────────────────────────────────────────────────────────────┘
```

### Production Debugging Example

```python
import torch
import torch.nn as nn

# Scenario: NaN appears after ~500 training steps

# Step 1: Detect WHERE the NaN first appears
def check_nan_hook(module, input, output):
    if isinstance(output, torch.Tensor) and torch.isnan(output).any():
        print(f"NaN detected in {module.__class__.__name__}")
        print(f"  Input stats: min={input[0].min():.4f}, max={input[0].max():.4f}")
        raise RuntimeError(f"NaN in {module}")

model = nn.Sequential(nn.Linear(10, 50), nn.ReLU(), nn.Linear(50, 1))
for module in model.modules():
    module.register_forward_hook(check_nan_hook)

# Step 2: Monitor gradient norms
def log_gradient_norms(model):
    total_norm = 0
    for name, p in model.named_parameters():
        if p.grad is not None:
            param_norm = p.grad.data.norm(2).item()
            total_norm += param_norm ** 2
            if param_norm > 100:
                print(f"  WARNING: {name} grad norm = {param_norm:.2f}")
    total_norm = total_norm ** 0.5
    return total_norm

# Step 3: Use anomaly detection (SLOW - only for debugging)
# torch.autograd.set_detect_anomaly(True)
```

### PyTorch Debugging Tools

```python
# Detect which operation produces NaN
with torch.autograd.detect_anomaly():
    output = model(input)
    loss = criterion(output, target)
    loss.backward()  # Will print the exact operation that produced NaN

# Check for NaN in model parameters
def has_nan_params(model):
    for name, p in model.named_parameters():
        if torch.isnan(p).any():
            return f"NaN in parameter: {name}"
        if p.grad is not None and torch.isnan(p.grad).any():
            return f"NaN in gradient: {name}"
    return None
```

**What happens if you ignore this:** You spend 6 hours rerunning training with different seeds, hoping the NaN "goes away." It doesn't.

---

## 7. Mixed Precision Training

### Why Mixed Precision

```
Standard (float32):     Memory: 100%    Speed: 1x
Mixed (float16/float32): Memory: ~60%   Speed: 2-3x on Tensor Cores
```

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│              MIXED PRECISION TRAINING FLOW                   │
│                                                             │
│  Master Weights (float32)                                   │
│       │                                                     │
│       ▼ cast to float16                                     │
│  Forward Pass (float16) ──→ Loss (float32)                  │
│                                    │                        │
│                                    ▼ × loss_scale           │
│                              Scaled Loss                    │
│                                    │                        │
│                                    ▼ backward               │
│                           Gradients (float16)               │
│                                    │                        │
│                                    ▼ ÷ loss_scale           │
│                           Unscaled Gradients                │
│                                    │                        │
│                                    ▼ cast to float32        │
│  Master Weights (float32) ◄── Optimizer Step (float32)     │
└─────────────────────────────────────────────────────────────┘
```

### bfloat16 vs float16

```
float16:  range ±65504,      precision ~3.3 digits
bfloat16: range ±3.4×10^38,  precision ~2.4 digits

bfloat16 advantages:
- Same range as float32 → almost never overflows → no loss scaling needed!
- Supported on A100, H100, TPUs
- Simpler training code (no GradScaler)

float16 advantages:
- Better precision (10 mantissa bits vs 7)
- Wider hardware support (V100, older GPUs)
- Requires loss scaling to prevent gradient underflow
```

### Complete PyTorch Mixed Precision Pattern

```python
import torch
from torch.cuda.amp import autocast, GradScaler

model = MyModel().cuda()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
scaler = GradScaler()  # Handles loss scaling for float16

for batch in dataloader:
    inputs, targets = batch[0].cuda(), batch[1].cuda()
    optimizer.zero_grad()
    
    # Forward pass in float16
    with autocast(dtype=torch.float16):
        outputs = model(inputs)
        loss = criterion(outputs, targets)
    
    # Backward pass: scale loss to prevent gradient underflow
    scaler.scale(loss).backward()
    
    # Unscale gradients for clipping
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    
    # Optimizer step (skipped if gradients contain inf/nan)
    scaler.step(optimizer)
    scaler.update()

# With bfloat16 (simpler - no scaler needed):
for batch in dataloader:
    inputs, targets = batch[0].cuda(), batch[1].cuda()
    optimizer.zero_grad()
    
    with autocast(dtype=torch.bfloat16):
        outputs = model(inputs)
        loss = criterion(outputs, targets)
    
    loss.backward()
    optimizer.step()
```

### When Mixed Precision Fails

- Small models (overhead of casting > compute savings)
- Tasks requiring high precision (scientific computing, some RL)
- Operations with large reductions (sum of millions of small numbers)
- Custom CUDA kernels not written for mixed precision

**What happens if you ignore this:** Your A100 GPU runs at 30% utilization because you're using float32 everywhere. Training that could take 1 day takes 3.

---

## 8. Numerical Issues Specific to Deep Learning

### Vanishing Gradients

```python
import numpy as np

# Sigmoid saturates: σ'(x) → 0 for |x| > 5
x = np.linspace(-10, 10, 100)
sigmoid = 1 / (1 + np.exp(-x))
sigmoid_grad = sigmoid * (1 - sigmoid)
# At x=10: sigmoid_grad ≈ 4.5e-5
# 10 layers: (4.5e-5)^10 ≈ 10^-43 → gradient is ZERO

# Solution: ReLU (gradient = 1 for x > 0)
# Solution: Residual connections (gradient flows through skip)
# Solution: LSTM/GRU gates (for sequential models)
```

### Exploding Gradients

```python
import numpy as np

# RNN unrolled for T steps: gradient ∝ W^T
# If largest eigenvalue of W > 1, gradients explode exponentially
W = np.random.randn(100, 100) * 0.5  # Seems small...
eigenvalues = np.linalg.eigvals(W)
max_eigval = np.max(np.abs(eigenvalues))
print(f"Max |eigenvalue|: {max_eigval:.2f}")  # Often > 1 even with small init

# After T=100 steps: gradient ∝ max_eigval^100
# If max_eigval = 1.1: 1.1^100 ≈ 13780
# If max_eigval = 1.5: 1.5^100 ≈ 4×10^17 → overflow!

# Solution: Gradient clipping
# torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
```

### Dead ReLU Problem

```python
# If a ReLU neuron gets a large negative bias, it NEVER activates:
#   output = max(0, Wx + b) = 0 for all x
#   gradient w.r.t. W = 0 (since output region is flat)
#   → neuron can never recover! It's "dead."

# How many neurons die? Depends on learning rate:
# - High LR → large weight updates → neurons overshoot into negative → die
# - Common: 10-40% of ReLU neurons die during training

# Solutions:
# - Leaky ReLU: max(0.01x, x) — always has gradient
# - PReLU: max(αx, x) — learnable α
# - ELU/GELU: smooth, no dead zone
# - Lower learning rate + careful initialization
```

### Weight Initialization: Xavier and He

```python
import torch.nn as nn
import numpy as np

# Goal: keep variance of activations ≈ 1 across layers
# If Var(output) grows → exploding activations → overflow
# If Var(output) shrinks → vanishing activations → underflow

# Xavier (for tanh/sigmoid): Var(W) = 2 / (fan_in + fan_out)
# He (for ReLU):             Var(W) = 2 / fan_in

# PyTorch defaults:
linear = nn.Linear(512, 256)
# Uses Kaiming uniform by default

# Manual He initialization:
nn.init.kaiming_normal_(linear.weight, mode='fan_in', nonlinearity='relu')
```

### Residual Connections Prevent Gradient Vanishing

```
Without residual:  y = F(x)
  Gradient: dy/dx = dF/dx  (can vanish if F has many layers)

With residual:     y = F(x) + x
  Gradient: dy/dx = dF/dx + I  (identity guarantees gradient ≥ 1)

For a network with L residual blocks:
  ∂Loss/∂x_l = ∂Loss/∂x_L · (1 + ∂/∂x_l Σ F_i)

The "1" term means gradients can flow DIRECTLY from loss to any layer,
regardless of how many layers are in between.
```

**What happens if you ignore initialization and architecture:** Your 50-layer network without skip connections produces random outputs after 1000 epochs. BatchNorm masks the problem until you try to deploy without it.

---

## Exercises

### Exercise 1: Float Precision
What is the output of `np.float32(1.0) + np.float32(1e-8) == np.float32(1.0)`?

**Solution:** `True`. Machine epsilon for float32 is ~1.19e-7. Since 1e-8 < eps * 1.0, the addition is lost.

### Exercise 2: Stable Softmax
Implement softmax that works for `x = [10000, 10001, 10002]` without overflow.

**Solution:** Subtract max before exp: `exp(x - max(x)) / sum(exp(x - max(x)))`.

### Exercise 3: Log Probability Sum
You have 1000 log-probabilities. Compute `log(sum(exp(log_probs)))` stably.

**Solution:** Use `scipy.special.logsumexp(log_probs)` which internally does: `max_lp + log(sum(exp(log_probs - max_lp)))`.

### Exercise 4: Gradient Explosion Detection
Write code to detect if gradients are exploding during training.

**Solution:**
```python
def detect_explosion(model, threshold=100):
    for name, p in model.named_parameters():
        if p.grad is not None:
            norm = p.grad.norm().item()
            if norm > threshold or not np.isfinite(norm):
                return True, name, norm
    return False, None, None
```

### Exercise 5: Condition Number
Matrix A has condition number 10^12. You're solving Ax=b in float32. How many digits of accuracy do you expect?

**Solution:** float32 has ~7 digits. κ(A) = 10^12 means you lose 12 digits. 7 - 12 = negative → **zero reliable digits**. The solution is meaningless. Use float64 (15 digits → 3 reliable) or precondition the matrix.

### Exercise 6: Step Size for Gradient Checking
What's the optimal step size for central difference gradient checking in float64?

**Solution:** Optimal h ≈ ε^(1/3) where ε = 2.2e-16 for float64. h ≈ (2.2e-16)^(1/3) ≈ 6e-6. In practice, h = 1e-5 to 1e-7 works well.

### Exercise 7: Loss Scaling
Your float16 training produces NaN. Gradient norms before NaN are ~1e-6. What's happening?

**Solution:** Gradients are underflowing in float16 (min positive normal = 6e-8, subnormal = 6e-8). float16 can't represent 1e-6 accurately when multiplied/added. Apply loss scaling (multiply loss by 1024 before backward, divide gradients by 1024 after).

### Exercise 8: Dead ReLU
After training, 60% of neurons have zero output for all inputs. Diagnose and fix.

**Solution:** Dead ReLU. Causes: learning rate too high, or bias initialized too negative. Fix: use Leaky ReLU, reduce LR, or use He initialization.

### Exercise 9: Cholesky Failure
`np.linalg.cholesky(K)` throws `LinAlgError`. K is a kernel matrix. Why and fix?

**Solution:** K is not positive definite (likely due to floating point making it slightly non-PD). Fix: add jitter `K + 1e-6 * I`. This is standard practice in GP implementations.

### Exercise 10: NaN in Attention
Your transformer produces NaN in attention weights. The input sequence has padding tokens. Why?

**Solution:** Attention mask is -inf for padding positions. If ALL positions are masked (empty sequence), softmax gets all -inf inputs → exp(-inf) = 0 everywhere → 0/0 = NaN. Fix: ensure at least one position is unmasked, or add epsilon to softmax denominator.

---

## Interview Questions

### Q1: Why does PyTorch use `F.cross_entropy` with logits instead of `F.nll_loss(F.log_softmax(...))`?
**A:** `F.cross_entropy` fuses log-softmax and NLL into a single numerically stable operation. Computing softmax then log separately can overflow (exp of large logits) or underflow (log of near-zero probabilities). The fused version uses the log-sum-exp trick internally.

### Q2: You're training a model and loss becomes NaN at step 1000. What's your debugging process?
**A:** (1) Reproduce deterministically with fixed seed. (2) Enable `detect_anomaly()`. (3) Print gradient norms per layer — look for explosion. (4) Check if input batch at step 1000 has NaN/Inf. (5) Reduce LR by 10x — if NaN disappears, it was gradient explosion. (6) Add gradient clipping. (7) Check custom loss for log(0) or 0/0.

### Q3: Explain why bfloat16 is preferred over float16 for training large models.
**A:** bfloat16 has the same 8-bit exponent as float32, giving it the same numerical range (±3.4×10^38 vs float16's ±65504). This means loss values, gradients, and activations almost never overflow, eliminating the need for loss scaling. The tradeoff is lower precision (7 vs 10 mantissa bits), but this rarely matters for gradient descent which is inherently noisy.

### Q4: What's the relationship between condition number and training convergence?
**A:** The condition number of the Hessian determines the ratio between the largest and smallest learning rates that would be optimal for different directions. High condition number → SGD oscillates in steep directions while crawling in flat directions. Solutions: Adam (adapts per-parameter), preconditioning, batch normalization (reduces condition number of loss landscape).

### Q5: Why do we add epsilon inside square roots (e.g., in Adam, LayerNorm) rather than outside?
**A:** `1/sqrt(v + eps)` vs `1/(sqrt(v) + eps)`. If v = 0: first gives `1/sqrt(eps)` (finite), second gives `1/eps` (much larger). More importantly, the gradient of `sqrt(v)` at v=0 is infinite (`0.5/sqrt(v)`), so adding eps inside prevents NaN in the backward pass.

### Q6: A colleague says "just use float64 everywhere to avoid numerical issues." Why is this wrong for ML?
**A:** (1) 2x memory → half the batch size → worse generalization. (2) 2-4x slower on GPUs (Tensor Cores don't support float64). (3) Doesn't fix algorithmic instability (a bad algorithm is bad at any precision). (4) Most numerical issues in ML come from exp/log overflow, not precision — float64 doesn't help with exp(1000). The right fix is stable algorithms (log-sum-exp, fused operations).

### Q7: How does gradient checkpointing interact with numerical stability?
**A:** Gradient checkpointing recomputes forward activations during backward instead of storing them. Since floating point operations aren't perfectly associative, recomputed values might differ slightly from original values (due to different operation ordering/fusions by the compiler). This is usually negligible but can matter in ill-conditioned networks. Always verify training curves match with and without checkpointing.

---

## Quick Reference: NaN Debugging Checklist

```
IMMEDIATE ACTIONS (do these first):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. torch.autograd.set_detect_anomaly(True) → find the op
2. Print loss value every step → when does it diverge?
3. Reduce LR by 100x → does NaN disappear?

COMMON CAUSES (ordered by frequency):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Learning rate too high → gradient explosion → NaN
• log(0) in loss function → -inf → NaN in backward
• Division by zero (missing epsilon in denominators)
• Mixed precision without loss scaling
• NaN in input data (check your data pipeline!)
• Batch size 1 with BatchNorm (zero variance)

FIXES (apply in order):
━━━━━━━━━━━━━━━━━━━━━━━━
• Add gradient clipping: clip_grad_norm_(params, 1.0)
• Use *_with_logits loss variants
• Add eps=1e-8 to all denominators and sqrt()
• Reduce learning rate
• Use gradient scaling for mixed precision
• Check and sanitize input data

PREVENTION (do this from the start):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Always use numerically stable loss functions (with_logits)
• Always clip gradients in RNNs/Transformers
• Always add eps to LayerNorm/BatchNorm/Adam denominators
• Use He init for ReLU, Xavier for tanh
• Monitor gradient norms during training
• Use bfloat16 instead of float16 when hardware supports it
```

---

## Summary

| Problem | Symptom | Fix |
|---------|---------|-----|
| Overflow in softmax | NaN loss | Subtract max (log-sum-exp trick) |
| Underflow in log-probs | -inf, then NaN | Work in log-space throughout |
| Vanishing gradients | Training stalls, early layers don't learn | ResNets, LSTM, ReLU, proper init |
| Exploding gradients | NaN after few steps | Gradient clipping, lower LR |
| Dead ReLU | Many zero activations | Leaky ReLU, He init, lower LR |
| Ill-conditioned Hessian | Slow convergence | Adam, BatchNorm, preconditioning |
| Mixed precision underflow | NaN with fp16 | Loss scaling, or use bfloat16 |
| Division by zero | NaN in normalization | Add epsilon everywhere |

> "If your model produces NaN, the bug is almost always one of: log(0), exp(big), 0/0, or learning rate too high. Check these four things first." — Every ML engineer who's debugged production models.
