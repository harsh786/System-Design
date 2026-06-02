# Matrix Calculus Deep Dive for ML

## 1. Why Matrix Calculus for ML

Every ML algorithm optimizes parameters via gradients. Parameters are matrices and vectors:
- Linear layer weights: W ∈ ℝ^(m×n)
- Embedding tables: E ∈ ℝ^(V×d)
- Attention projections: W_Q, W_K, W_V ∈ ℝ^(d×d_k)

You cannot just differentiate element-by-element blindly. You need systematic rules for:
- What shape is ∂L/∂W?
- How does the chain rule work for matrix expressions?
- How to derive backprop for custom layers?

---

## 2. Denominator Layout vs Numerator Layout

Two conventions exist (source of endless confusion):

| | Numerator layout | Denominator layout (we use this) |
|--|--|--|
| ∂y/∂x where y=scalar, x∈ℝⁿ | row vector (1×n) | column vector (n×1) |
| ∂y/∂x where y∈ℝᵐ, x∈ℝⁿ | Jacobian (m×n) | Jacobian^T (n×m) |

**Convention in this guide**: Denominator layout.
- ∂(scalar)/∂(vector of shape n×1) → column vector of shape n×1
- The gradient has the SAME SHAPE as the variable (convenient for SGD: θ ← θ - α∇θ)

---

## 3. Vector Derivatives

### ∂(scalar)/∂(vector) → gradient vector

```
If f: ℝⁿ → ℝ, x ∈ ℝⁿ:
∂f/∂x = [∂f/∂x₁, ∂f/∂x₂, ..., ∂f/∂xₙ]^T   (same shape as x)
```

### Key Results

| Expression | Derivative w.r.t. x | Notes |
|-----------|---------------------|-------|
| a^T x | a | Linear function |
| x^T x = ‖x‖² | 2x | L2 norm squared |
| x^T A x | (A + A^T)x | Quadratic form; = 2Ax if A symmetric |
| ‖Ax - b‖² | 2A^T(Ax - b) | Least squares gradient! |

### ∂(vector)/∂(vector) → Jacobian matrix

If f: ℝⁿ → ℝᵐ, the Jacobian J ∈ ℝ^(m×n):
```
J_ij = ∂f_i/∂x_j

For f(x) = Ax where A ∈ ℝ^(m×n):
∂(Ax)/∂x = A    (Jacobian is just A)
```

### Derivative of Wx w.r.t. W

This is tricky! If y = Wx where W ∈ ℝ^(m×n), x ∈ ℝⁿ, y ∈ ℝᵐ:
- ∂y/∂W is a 3D tensor (or use vectorization, see Section 7)
- In practice for backprop, we want ∂L/∂W where L is scalar:
  - If ∂L/∂y = δ (upstream gradient, m×1), then **∂L/∂W = δ x^T** (outer product, m×n)
  - This is the key formula for linear layer backprop!

---

## 4. Matrix Derivatives

### ∂(scalar)/∂(matrix) → matrix of same shape

If f: ℝ^(m×n) → ℝ, then ∂f/∂A ∈ ℝ^(m×n) where (∂f/∂A)_ij = ∂f/∂A_ij

### Key Results

| Expression | Derivative w.r.t. A | Condition |
|-----------|---------------------|-----------|
| tr(AB) | B^T | |
| tr(A^T B) | B | |
| tr(A) | I | |
| det(A) | det(A) · A^(-T) | A invertible |
| x^T A x | xx^T | scalar result |
| tr(ABA^T) | AB + A^T B^T (if B sym: 2AB) | |
| ‖A‖²_F = tr(A^T A) | 2A | Frobenius norm |

### Chain Rule for Matrices

If L = f(g(W)):
```
∂L/∂W = ∂L/∂g · ∂g/∂W
```
In practice, this is computed via the chain of Jacobians (backpropagation).

---

## 5. Backpropagation Derived with Matrix Calculus

### Linear Layer: y = Wx + b

```
Given: x ∈ ℝⁿ (input), W ∈ ℝ^(m×n), b ∈ ℝᵐ, y ∈ ℝᵐ
Upstream gradient: ∂L/∂y = δ ∈ ℝᵐ

∂L/∂W = δ x^T          ∈ ℝ^(m×n)  ← same shape as W ✓
∂L/∂b = δ              ∈ ℝᵐ       ← same shape as b ✓
∂L/∂x = W^T δ          ∈ ℝⁿ       ← same shape as x ✓
```

**Batched version** (X ∈ ℝ^(n×B), B = batch size):
```
Y = WX + b1^T          ∈ ℝ^(m×B)
∂L/∂W = Δ X^T / B      (average over batch)
∂L/∂X = W^T Δ
```

### Softmax Layer

```
Input: z ∈ ℝᵏ, Output: s_i = exp(z_i) / Σ_j exp(z_j)

Jacobian of softmax:
∂s_i/∂z_j = s_i(δ_ij - s_j)    where δ_ij = Kronecker delta

In matrix form: ∂s/∂z = diag(s) - ss^T

If upstream gradient is ∂L/∂s = δ:
∂L/∂z = s ⊙ (δ - (δ^T s)1)    (element-wise, efficient!)
```

### Cross-Entropy Loss

```
L = -Σᵢ yᵢ log(sᵢ)    where y = one-hot target, s = softmax output

∂L/∂s_i = -y_i/s_i

Combined softmax + cross-entropy (the common case):
∂L/∂z = s - y          ← beautifully simple!

Shape check: z ∈ ℝᵏ, s ∈ ℝᵏ, y ∈ ℝᵏ → ∂L/∂z ∈ ℝᵏ ✓
```

### Batch Normalization

```
Input: x ∈ ℝⁿ (one sample, n features)
μ = (1/n)Σx_i,  σ² = (1/n)Σ(x_i - μ)²
x̂ = (x - μ)/√(σ² + ε)
y = γ ⊙ x̂ + β

Gradients (given ∂L/∂y = δ):
∂L/∂γ = Σ δ ⊙ x̂        (over batch)
∂L/∂β = Σ δ              (over batch)
∂L/∂x̂ = δ ⊙ γ
∂L/∂x = (1/√(σ²+ε)) · (∂L/∂x̂ - mean(∂L/∂x̂) - x̂·mean(∂L/∂x̂ ⊙ x̂))
```

### Multi-Head Attention (Simplified Single Head)

```
Q = XW_Q ∈ ℝ^(T×d_k),  K = XW_K,  V = XW_V ∈ ℝ^(T×d_v)
A = softmax(QK^T / √d_k) ∈ ℝ^(T×T)
O = AV ∈ ℝ^(T×d_v)

Given ∂L/∂O:
∂L/∂V = A^T (∂L/∂O)                    ∈ ℝ^(T×d_v)
∂L/∂A = (∂L/∂O) V^T                    ∈ ℝ^(T×T)
∂L/∂(QK^T/√d_k) = softmax_backward(∂L/∂A, A)
∂L/∂Q = [∂L/∂(scores)] K / √d_k       ∈ ℝ^(T×d_k)
∂L/∂K = [∂L/∂(scores)]^T Q / √d_k     ∈ ℝ^(T×d_k)
∂L/∂W_Q = X^T (∂L/∂Q)                  ∈ ℝ^(d×d_k)
```

---

## 6. The Chain Rule for Matrices

### Forward Mode vs Reverse Mode

```
f(x) = h(g(x))    where x ∈ ℝⁿ, g: ℝⁿ→ℝᵐ, h: ℝᵐ→ℝ

Forward mode: compute ∂g/∂xᵢ first, then ∂h/∂g · ∂g/∂xᵢ
  - Cost: O(n) passes (one per input dimension)
  - Good when n << m (few inputs, many outputs)

Reverse mode: compute ∂h/∂g first, then ∂h/∂g · ∂g/∂x
  - Cost: O(1) passes (one backward pass)
  - Good when m << n (one loss, many parameters) ← THIS IS ML!
```

**Why backprop uses reverse mode**: We have 1 scalar loss but millions of parameters. Reverse mode computes all gradients in ONE backward pass.

### JVP vs VJP

```
Jacobian J ∈ ℝ^(m×n) for f: ℝⁿ → ℝᵐ

JVP (Jacobian-Vector Product): J · v where v ∈ ℝⁿ  → result ∈ ℝᵐ
  - Forward mode: "how does output change if input changes by v?"
  - Cost: O(1) evaluation per direction v

VJP (Vector-Jacobian Product): u^T · J where u ∈ ℝᵐ  → result ∈ ℝⁿ
  - Reverse mode: "backpropagate gradient u through this layer"
  - This is what PyTorch .backward() computes!
```

### Connection to PyTorch Autograd

```python
import torch

# PyTorch builds computation graph, then computes VJPs in reverse
x = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
y = x ** 2        # Forward: builds graph
z = y.sum()       # Forward: builds graph
z.backward()      # Reverse: VJP chain
# x.grad = [2.0, 4.0, 6.0]  (∂z/∂x = 2x)
```

---

## 7. Kronecker Products and Vectorization

### The vec() Operator

Stacks columns of a matrix into a single vector:
```
A = [a b]  →  vec(A) = [a, c, b, d]^T
    [c d]
```

### Kronecker Product

```
A ⊗ B: if A ∈ ℝ^(m×n), B ∈ ℝ^(p×q), then A⊗B ∈ ℝ^(mp×nq)

[a b] ⊗ B = [aB  bB]
[c d]       [cB  dB]
```

### The Key Identity

```
vec(AXB) = (B^T ⊗ A) vec(X)
```

**Application**: For Y = WX (linear layer), L scalar:
```
vec(∂L/∂W) can be expressed using Kronecker products
∂L/∂vec(W) = (X ⊗ I) vec(∂L/∂Y)   (relates to ∂L/∂W = δx^T)
```

This identity is crucial for:
- Deriving Fisher Information Matrix structure
- Understanding K-FAC approximation
- Matrix-valued optimization

---

## 8. Hessians and Second-Order Methods

### Hessian Matrix

```
H_ij = ∂²L/∂θ_i∂θ_j    ∈ ℝ^(p×p) where p = number of parameters

For quadratic: L = (1/2)θ^T H θ → ∇L = Hθ
Newton's method: θ ← θ - H⁻¹ ∇L  (one step to minimum for quadratic!)
```

### Fisher Information Matrix

```
F = E[∇log p(x|θ) · ∇log p(x|θ)^T]

Properties:
- F ≈ H for well-specified models near optimum
- Defines the natural gradient: θ ← θ - α F⁻¹ ∇L
- Accounts for geometry of parameter space (not all directions equal)
```

### Natural Gradient Descent

Standard gradient descent treats parameter space as Euclidean.
Natural gradient accounts for the statistical manifold structure:

```
θ ← θ - α F⁻¹ ∇L

Intuition: F⁻¹ rescales gradient so that equal-KL-divergence
steps are equal-length, regardless of parameterization.
```

### Why Second-Order Methods Are Rarely Used in DL

| Issue | Impact |
|-------|--------|
| Hessian size | p² entries; p=10⁸ → 10¹⁶ entries (impossible) |
| Hessian inverse | O(p³) computation |
| Non-convexity | Hessian has negative eigenvalues → not PSD |
| Saddle points | Negative curvature directions cause divergence |

### Practical Approximations

**K-FAC** (Kronecker-Factored Approximate Curvature):
```
For layer with Y = WX:
F_layer ≈ E[xx^T] ⊗ E[δδ^T]   (Kronecker factored!)
Inverse: (A⊗B)⁻¹ = A⁻¹ ⊗ B⁻¹  (cheap to invert factors separately)
```

**Diagonal Hessian**: Only keep H_ii terms. Used in Adam (second moment ≈ diagonal Fisher).

---

## 9. Cheat Sheet: Common Matrix Derivatives

```
┌─────────────────────────────┬──────────────────────────┬───────────────┐
│ Expression                  │ ∂/∂x or ∂/∂A            │ Condition     │
├─────────────────────────────┼──────────────────────────┼───────────────┤
│ a^T x                       │ a                        │               │
│ x^T A x                     │ (A + A^T)x              │               │
│ ‖x‖² = x^T x               │ 2x                      │               │
│ ‖Ax - b‖²                   │ 2A^T(Ax - b)            │               │
│ log(1 + exp(w^T x))        │ σ(w^T x) · w            │ sigmoid σ     │
│ σ(z)                        │ σ(z)(1-σ(z))            │ scalar z      │
├─────────────────────────────┼──────────────────────────┼───────────────┤
│ tr(AB)                      │ B^T (w.r.t. A)          │               │
│ tr(A^T B)                   │ B (w.r.t. A)            │               │
│ det(A)                      │ det(A) · A^{-T}         │ A invertible  │
│ log det(A)                  │ A^{-T}                  │ A invertible  │
│ tr(ABA^T C)                 │ CAB + C^T AB^T          │               │
│ ‖A‖²_F                      │ 2A                      │               │
└─────────────────────────────┴──────────────────────────┴───────────────┘
```

---

## 10. Python Verification

```python
import numpy as np

def numerical_gradient(f, x, eps=1e-5):
    """Verify analytical gradients numerically"""
    grad = np.zeros_like(x)
    for i in range(x.size):
        x_plus = x.copy(); x_plus.flat[i] += eps
        x_minus = x.copy(); x_minus.flat[i] -= eps
        grad.flat[i] = (f(x_plus) - f(x_minus)) / (2 * eps)
    return grad

# Verify: ∂(x^T A x)/∂x = (A + A^T)x
np.random.seed(42)
A = np.random.randn(3, 3)
x = np.random.randn(3)

f = lambda x: x @ A @ x
analytical = (A + A.T) @ x
numerical = numerical_gradient(f, x)
print(f"Max error: {np.max(np.abs(analytical - numerical)):.2e}")  # ~1e-10

# Verify: ∂‖Ax - b‖²/∂x = 2A^T(Ax - b)
A = np.random.randn(5, 3)
x = np.random.randn(3)
b = np.random.randn(5)

f = lambda x: np.sum((A @ x - b)**2)
analytical = 2 * A.T @ (A @ x - b)
numerical = numerical_gradient(f, x)
print(f"Max error: {np.max(np.abs(analytical - numerical)):.2e}")  # ~1e-10

# Verify: ∂L/∂W = δ x^T for linear layer
W = np.random.randn(4, 3)
x = np.random.randn(3)
target = np.random.randn(4)

def loss_wrt_W(W_flat):
    W = W_flat.reshape(4, 3)
    y = W @ x
    return np.sum((y - target)**2)

delta = 2 * (W @ x - target)  # ∂L/∂y
analytical_W = np.outer(delta, x)  # δ x^T
numerical_W = numerical_gradient(loss_wrt_W, W.flatten()).reshape(4, 3)
print(f"Max error: {np.max(np.abs(analytical_W - numerical_W)):.2e}")  # ~1e-10

# Verify: softmax + cross-entropy gradient = s - y
def softmax(z):
    e = np.exp(z - z.max())
    return e / e.sum()

z = np.random.randn(5)
y = np.zeros(5); y[2] = 1.0  # one-hot

def ce_loss(z):
    s = softmax(z)
    return -np.sum(y * np.log(s + 1e-12))

analytical_ce = softmax(z) - y
numerical_ce = numerical_gradient(ce_loss, z)
print(f"Max error: {np.max(np.abs(analytical_ce - numerical_ce)):.2e}")  # ~1e-7
```

---

## 11. Exercises

### Exercise 1
Derive ∂/∂x of f(x) = x^T A^T A x + 2b^T x + c.

**Solution**: ∂f/∂x = (A^T A + (A^T A)^T)x + 2b = 2A^T Ax + 2b (since A^T A is symmetric).

### Exercise 2
For the linear regression loss L = (1/2n)‖Xw - y‖², derive the closed-form solution.

**Solution**: ∂L/∂w = (1/n)X^T(Xw - y) = 0 → X^T Xw = X^T y → w* = (X^T X)⁻¹ X^T y.

### Exercise 3
Compute ∂L/∂W₁ for a two-layer network: L = ‖W₂σ(W₁x) - y‖².

**Solution**: Let h = W₁x, a = σ(h), ŷ = W₂a. δ₂ = 2(ŷ-y), ∂L/∂W₂ = δ₂a^T. δ₁ = W₂^T δ₂ ⊙ σ'(h). ∂L/∂W₁ = δ₁x^T.

### Exercise 4
Show that the Jacobian of softmax is diag(s) - ss^T.

**Solution**: ∂s_i/∂z_j. If i=j: ∂(e^z_i/Σ)/∂z_i = s_i - s_i² = s_i(1-s_i). If i≠j: ∂(e^z_i/Σ)/∂z_j = -s_i·s_j. Combined: s_i(δ_ij - s_j) = [diag(s) - ss^T]_ij.

### Exercise 5
Why is ∂L/∂W = δx^T an outer product? What are its rank and dimensions?

**Solution**: δ ∈ ℝᵐ, x ∈ ℝⁿ → δx^T ∈ ℝ^(m×n), same shape as W. It's rank-1 (outer product of two vectors). This means each SGD update is rank-1, motivating low-rank adaptation (LoRA!).

### Exercise 6
Derive the gradient of log-softmax: log s_i = z_i - log(Σ exp(z_j)).

**Solution**: ∂(log s_i)/∂z_j = δ_ij - s_j. For loss L = -log s_c (correct class c): ∂L/∂z_j = s_j - δ_cj = s_j - y_j (same as softmax+CE combined).

### Exercise 7
For batch norm x̂ = (x-μ)/σ, what makes the gradient w.r.t. x non-trivial?

**Solution**: μ and σ both depend on x (computed from the batch). So ∂x̂/∂x has terms from direct dependence AND indirect dependence through μ and σ. Must use chain rule through all paths.

### Exercise 8
Compute the Fisher Information Matrix for a Bernoulli distribution p(x|θ) = θ^x(1-θ)^(1-x).

**Solution**: log p = x log θ + (1-x)log(1-θ). ∂log p/∂θ = x/θ - (1-x)/(1-θ). F = E[(∂log p/∂θ)²] = E[x]/θ² + E[1-x]/(1-θ)² = 1/θ + 1/(1-θ) = 1/(θ(1-θ)).

### Exercise 9
Show that for MSE loss with linear model, the Hessian is constant (independent of parameters).

**Solution**: L = (1/2n)‖Xw-y‖². ∇L = (1/n)X^T(Xw-y). H = ∂²L/∂w² = (1/n)X^TX. This is constant (doesn't depend on w) → loss is quadratic, Newton's method converges in 1 step.

### Exercise 10
Why does Adam approximate the diagonal of the Fisher Information Matrix?

**Solution**: Adam's second moment: v_t = β₂v_{t-1} + (1-β₂)g_t². This estimates E[g²] elementwise. For the Fisher matrix, diagonal entries are E[(∂L/∂θ_i)²]. So v_t ≈ diag(F). Adam's update θ - α·g/√v ≈ θ - α·F_diag⁻¹·g (diagonal natural gradient).

---

## 12. Interview Questions

**Q1**: Derive the gradient of the attention mechanism softmax(QK^T/√d_k)V with respect to Q.

**A**: Let S = QK^T/√d_k, A = softmax(S) row-wise, O = AV. Given ∂L/∂O, we get ∂L/∂A = (∂L/∂O)V^T. Then ∂L/∂S uses softmax Jacobian per row. Finally ∂L/∂Q = (∂L/∂S)K/√d_k.

**Q2**: Why does reverse-mode AD (backprop) have complexity independent of the number of parameters?

**A**: One backward pass computes ALL gradients simultaneously by propagating a single scalar (loss) backward through the graph. Cost = O(forward pass). Forward mode would need one pass per parameter.

**Q3**: What is K-FAC and why is it more practical than full natural gradient?

**A**: K-FAC approximates the Fisher as a Kronecker product of two smaller matrices per layer: F ≈ A⊗G where A = E[aa^T] (input correlations) and G = E[δδ^T] (gradient correlations). Inverting is cheap: (A⊗G)⁻¹ = A⁻¹⊗G⁻¹.

**Q4**: Explain why ∂L/∂W being rank-1 motivates LoRA.

**A**: Each SGD step adds a rank-1 matrix (δx^T) to W. After k steps, the total update has rank ≤ k. LoRA directly parameterizes the update as W + BA where B∈ℝ^(m×r), A∈ℝ^(r×n) with r << min(m,n), capturing this low-rank structure efficiently.

**Q5**: How would you verify that your custom layer's backward pass is correct?

**A**: Numerical gradient checking. Perturb each parameter by ±ε, compute (L(θ+ε)-L(θ-ε))/(2ε), compare with analytical gradient. Check relative error: |analytical - numerical| / max(|analytical|, |numerical|) < 1e-5. Use double precision. PyTorch: `torch.autograd.gradcheck()`.
