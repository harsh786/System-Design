# Calculus for AI/ML/Deep Learning

## Why Calculus Matters for ML

Calculus is how neural networks **learn**. The entire training process — backpropagation, gradient descent, optimization — is calculus. When you "train" a model, you're computing derivatives of a loss function with respect to millions of parameters and updating them to minimize error.

```
Training Loop = Calculus in Action:
1. Forward pass      → compute loss (function evaluation)
2. Backward pass     → compute gradients (derivatives via chain rule)
3. Parameter update  → move opposite to gradient (gradient descent)
```

---

## 1. Limits and Continuity

### Limits

The foundation of calculus. A limit describes what happens to f(x) as x approaches a value.

```
lim(x→a) f(x) = L

"As x gets arbitrarily close to a, f(x) gets arbitrarily close to L"
```

**ML Relevance:** Limits appear in:
- Defining derivatives
- Understanding asymptotic behavior of loss functions
- Softmax stability (as logits → ∞)

### Continuity

A function is continuous if there are no "jumps." Most ML functions are continuous (and differentiable), which is why gradient-based optimization works.

```
Continuous:          Discontinuous (ReLU derivative at 0):
     /                    /
    /                    /
   /                ────/
  /                     │
                        /
```

---

## 2. Derivatives (Single Variable)

### Definition

The derivative measures the **rate of change** — the slope of the tangent line.

```
f'(x) = lim(h→0) [f(x+h) - f(x)] / h
```

### Geometric Intuition

```
    f(x)
    │        .
    │      .   .          f'(x) = slope of tangent at x
    │    .       .
    │   /─────────  ← tangent line (slope = derivative)
    │  .           .
    │ .
    └──────────────── x
```

### Key Derivative Rules

```
Power rule:     d/dx [xⁿ] = n·xⁿ⁻¹
Product rule:   d/dx [f·g] = f'g + fg'
Quotient rule:  d/dx [f/g] = (f'g - fg') / g²
Chain rule:     d/dx [f(g(x))] = f'(g(x)) · g'(x)
```

### Derivatives of Common ML Functions

```python
import numpy as np

# Sigmoid: σ(x) = 1/(1+e⁻ˣ)
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

# Derivative: σ'(x) = σ(x)(1 - σ(x))
def sigmoid_derivative(x):
    s = sigmoid(x)
    return s * (1 - s)

# ReLU: max(0, x)
def relu(x):
    return np.maximum(0, x)

# Derivative: 1 if x > 0, else 0
def relu_derivative(x):
    return (x > 0).astype(float)

# Tanh: derivative is 1 - tanh²(x)
def tanh_derivative(x):
    return 1 - np.tanh(x)**2
```

```
Sigmoid and its derivative:
σ(x)                    σ'(x)
1 ──────────.           0.25 ─────.─────
           /│                   /   \
          / │                  /     \
         /  │                 /       \
0 ──────/   │           0 ──/─────────\──
      -5  0  5              -5   0    5
```

---

## 3. Partial Derivatives (Multivariate Calculus)

### Definition

When f depends on multiple variables, the partial derivative measures change with respect to ONE variable while holding others constant.

```
∂f/∂x = rate of change of f in the x-direction (y held constant)
∂f/∂y = rate of change of f in the y-direction (x held constant)
```

### Example

```
f(x, y) = x² + 3xy + y²

∂f/∂x = 2x + 3y    (treat y as constant)
∂f/∂y = 3x + 2y    (treat x as constant)
```

**ML Context:** Loss function depends on ALL weights. Partial derivatives tell us how loss changes w.r.t. each individual weight.

```python
# Loss depends on weights w1, w2
# L(w1, w2) = (w1*x1 + w2*x2 - y)²
# ∂L/∂w1 = 2(w1*x1 + w2*x2 - y) * x1
# ∂L/∂w2 = 2(w1*x1 + w2*x2 - y) * x2
```

---

## 4. Gradient, Jacobian, and Hessian

### Gradient (∇f)

The gradient is the vector of ALL partial derivatives. It points in the direction of steepest ascent.

```
∇f = [∂f/∂x₁, ∂f/∂x₂, ..., ∂f/∂xₙ]ᵀ
```

```
Gradient on a 2D surface (contour plot):

    y ▲
      │    ╭───╮
      │   ╭│   │╮    ∇f points outward
      │  ╭─┤ ● ├─╮   (toward steeper ascent)
      │   ╰│ → │╯    
      │    ╰───╯     Arrow = gradient direction
      └──────────▶ x

    To MINIMIZE: move OPPOSITE to gradient (-∇f)
```

```python
# Gradient descent update rule:
# θ_new = θ_old - α * ∇L(θ)

def gradient_descent(gradient_fn, theta, lr=0.01, steps=100):
    for _ in range(steps):
        grad = gradient_fn(theta)
        theta = theta - lr * grad
    return theta
```

### Jacobian Matrix

When you have a vector-valued function f: Rⁿ → Rᵐ, the Jacobian is the matrix of all partial derivatives.

```
       ┌ ∂f₁/∂x₁  ∂f₁/∂x₂  ...  ∂f₁/∂xₙ ┐
J  =   │ ∂f₂/∂x₁  ∂f₂/∂x₂  ...  ∂f₂/∂xₙ │
       │    ⋮         ⋮              ⋮       │
       └ ∂fₘ/∂x₁  ∂fₘ/∂x₂  ...  ∂fₘ/∂xₙ ┘
```

**ML Application:** The Jacobian appears when computing gradients through layers with vector inputs and vector outputs. Backpropagation multiplies Jacobians.

### Hessian Matrix

The matrix of second-order partial derivatives. Captures curvature information.

```
       ┌ ∂²f/∂x₁²     ∂²f/∂x₁∂x₂  ...  ∂²f/∂x₁∂xₙ ┐
H  =   │ ∂²f/∂x₂∂x₁   ∂²f/∂x₂²   ...  ∂²f/∂x₂∂xₙ │
       │    ⋮              ⋮                  ⋮        │
       └ ∂²f/∂xₙ∂x₁  ∂²f/∂xₙ∂x₂  ...   ∂²f/∂xₙ²  ┘
```

**ML Application:**
- Determines if a critical point is a minimum, maximum, or saddle point
- Second-order optimization methods (Newton's method) use the Hessian
- Too expensive to compute for neural networks (millions of parameters²)

```python
# For f(x,y) = x² + y²:
# H = [[2, 0], [0, 2]]  → positive definite → minimum at (0,0)

# For f(x,y) = x² - y²:
# H = [[2, 0], [0, -2]]  → indefinite → saddle point at (0,0)
```

---

## 5. The Chain Rule — The Heart of Backpropagation

### Single Variable Chain Rule

```
If y = f(g(x)), then dy/dx = f'(g(x)) · g'(x)
```

### Multivariate Chain Rule

```
If L = f(g(h(x))), then:
∂L/∂x = (∂L/∂g) · (∂g/∂h) · (∂h/∂x)
```

### Backpropagation IS the Chain Rule

```
Neural Network:
x → [Layer 1] → h₁ → [Layer 2] → h₂ → [Layer 3] → ŷ → [Loss] → L

Backpropagation (chain rule applied right-to-left):
∂L/∂W₁ = (∂L/∂ŷ) · (∂ŷ/∂h₂) · (∂h₂/∂h₁) · (∂h₁/∂W₁)
```

```
Forward pass (left to right):
x ──→ W₁x+b₁ ──→ ReLU ──→ W₂h₁+b₂ ──→ σ ──→ Loss
        │                      │                  │
Backward pass (right to left):                    │
∂L/∂W₁ ←── ∂h₁/∂W₁ ←── ∂h₂/∂h₁ ←── ∂L/∂h₂ ←──┘
```

```python
# Manual backpropagation example
class SimpleNetwork:
    def __init__(self):
        self.W1 = np.random.randn(784, 128)
        self.W2 = np.random.randn(128, 10)
    
    def forward(self, x):
        self.x = x
        self.h = np.maximum(0, x @ self.W1)     # ReLU
        self.out = self.h @ self.W2              # Linear
        return self.out
    
    def backward(self, dL_dout):
        # Chain rule: propagate gradient backward
        # ∂L/∂W2 = hᵀ × ∂L/∂out
        dL_dW2 = self.h.T @ dL_dout
        
        # ∂L/∂h = ∂L/∂out × W2ᵀ
        dL_dh = dL_dout @ self.W2.T
        
        # ∂L/∂(pre-relu) = ∂L/∂h * relu_derivative
        dL_dpre = dL_dh * (self.h > 0)
        
        # ∂L/∂W1 = xᵀ × ∂L/∂(pre-relu)
        dL_dW1 = self.x.T @ dL_dpre
        
        return dL_dW1, dL_dW2
```

---

## 6. Integration Basics

### Why Integration Matters in ML

Integration computes areas, probabilities, and expected values.

```
P(a ≤ X ≤ b) = ∫[a to b] f(x) dx    (probability from PDF)
E[X] = ∫ x · f(x) dx                 (expected value)
```

**ML Applications:**
- Computing probabilities from continuous distributions
- Expected values in reinforcement learning
- Normalizing constants (evidence in Bayes' theorem)
- Computing areas under ROC curves (AUC)

```python
from scipy import integrate

# Normal distribution PDF
def normal_pdf(x, mu=0, sigma=1):
    return (1/(sigma*np.sqrt(2*np.pi))) * np.exp(-0.5*((x-mu)/sigma)**2)

# P(-1 ≤ X ≤ 1) for standard normal
prob, _ = integrate.quad(normal_pdf, -1, 1)
print(f"P(-1 ≤ X ≤ 1) = {prob:.4f}")  # ≈ 0.6827 (68% rule)
```

---

## 7. Taylor Series Approximation

### The Idea

Approximate any smooth function as a polynomial around a point:

```
f(x) ≈ f(a) + f'(a)(x-a) + f''(a)(x-a)²/2! + f'''(a)(x-a)³/3! + ...
```

### ML Applications

1. **First-order approximation** → Gradient descent assumes loss is locally linear
2. **Second-order approximation** → Newton's method uses curvature
3. **Understanding why gradient descent works:** locally, L(θ - α∇L) < L(θ)

```
f(x) ≈ f(a) + f'(a)(x-a)           ← gradient descent uses this
f(x) ≈ f(a) + f'(a)(x-a) + ½f''(a)(x-a)²  ← Newton's method uses this
```

```python
# Taylor approximation of e^x around x=0
# e^x ≈ 1 + x + x²/2 + x³/6 + ...

x = 0.5
true_val = np.exp(x)

# Successive Taylor approximations
order1 = 1 + x                        # 1.5
order2 = 1 + x + x**2/2              # 1.625
order3 = 1 + x + x**2/2 + x**3/6    # 1.6458

print(f"True: {true_val:.4f}")        # 1.6487
print(f"Order 3 approx: {order3:.4f}")  # Very close!
```

---

## 8. Applications in ML

### Gradient Descent Visualization

```
Loss Surface (2D cross-section):

L(θ)
│\
│ \
│  \        .  ← local minimum (saddle point)
│   \      / \
│    \    /   \
│     \  /     \________  ← global minimum ★
│      \/
└────────────────────────── θ

Gradient descent follows the slope downhill:
θₙₑₓₜ = θ - α · ∂L/∂θ
         └──────────────── step in direction of steepest descent
```

### Contour Plot of Gradient Descent

```
     ┌─────────────────────────────┐
     │         ╭─────╮             │
     │       ╭─┤     ├─╮          │
     │      │  │  ●  │  │         │  ● = minimum
     │       ╰─┤ ↙   ├─╯          │  ↙ = gradient steps
     │    ←←←  ╰──┼──╯            │
     │    start    │               │
     │             │               │
     └─────────────────────────────┘
     
     Each arrow: θ = θ - α∇L(θ)
```

### Loss Functions and Their Derivatives

```python
# Mean Squared Error
def mse_loss(y_pred, y_true):
    return np.mean((y_pred - y_true)**2)

def mse_gradient(y_pred, y_true):
    return 2 * (y_pred - y_true) / len(y_true)

# Cross-Entropy Loss
def cross_entropy(y_pred, y_true):
    return -np.mean(y_true * np.log(y_pred) + (1-y_true) * np.log(1-y_pred))

def cross_entropy_gradient(y_pred, y_true):
    return (y_pred - y_true) / (y_pred * (1 - y_pred))
```

### Automatic Differentiation (How PyTorch/TensorFlow work)

```python
import torch

# PyTorch autograd computes chain rule automatically
x = torch.tensor([2.0], requires_grad=True)
y = x**3 + 2*x**2 + x

y.backward()  # Compute dy/dx using chain rule
print(x.grad)  # dy/dx = 3x² + 4x + 1 = 12 + 8 + 1 = 21
```

---

## Summary: Calculus Concepts → ML Mapping

| Calculus Concept | ML Application |
|-----------------|----------------|
| Derivative | How loss changes w.r.t. one parameter |
| Partial derivative | Gradient of loss w.r.t. each weight |
| Gradient (∇) | Direction for parameter updates |
| Chain rule | Backpropagation algorithm |
| Hessian | Curvature (second-order optimizers) |
| Taylor series | Why gradient descent works locally |
| Integration | Probabilities, expected values |
| Jacobian | Layer-wise gradient computation |

---

## Key Takeaways

1. **Derivatives = sensitivity.** How much does output change when input changes?
2. **Gradient = direction of steepest ascent.** Negate it to descend.
3. **Chain rule = backpropagation.** The single most important calculus concept for deep learning.
4. **Every optimizer** (SGD, Adam, RMSProp) is a variation on: θ ← θ - α·∇L
5. **Automatic differentiation** (PyTorch/TensorFlow) applies the chain rule computationally — you don't compute derivatives by hand.

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** Find the derivative of f(x) = 3x⁴ - 2x³ + x - 7.

**Hint:** Apply the power rule: d/dx[xⁿ] = nxⁿ⁻¹.

<details><summary>Solution</summary>

```
f'(x) = 12x³ - 6x² + 1
```
</details>

### Exercise 2 (Beginner)
**Problem:** Find the partial derivatives ∂f/∂x and ∂f/∂y for f(x,y) = x²y + 3xy² - 2y.

**Hint:** When taking ∂f/∂x, treat y as a constant (and vice versa).

<details><summary>Solution</summary>

```
∂f/∂x = 2xy + 3y²
∂f/∂y = x² + 6xy - 2
```
</details>

### Exercise 3 (Beginner)
**Problem:** Compute the gradient of f(x,y,z) = x²+ y² + z² at the point (1, 2, 3). What direction does it point?

**Hint:** ∇f = [∂f/∂x, ∂f/∂y, ∂f/∂z]

<details><summary>Solution</summary>

```
∇f = [2x, 2y, 2z]
At (1,2,3): ∇f = [2, 4, 6]
Direction: points away from origin (direction of steepest increase)
||∇f|| = sqrt(4+16+36) = sqrt(56) ≈ 7.48
```
</details>

### Exercise 4 (Beginner)
**Problem:** Apply the chain rule: if y = (3x² + 1)⁵, find dy/dx.

**Hint:** Let u = 3x² + 1, then y = u⁵. dy/dx = dy/du × du/dx.

<details><summary>Solution</summary>

```
Let u = 3x² + 1
dy/du = 5u⁴ = 5(3x²+1)⁴
du/dx = 6x
dy/dx = 5(3x²+1)⁴ × 6x = 30x(3x²+1)⁴
```
</details>

### Exercise 5 (Intermediate)
**Problem:** For a simple neural network: output = σ(w₂ · σ(w₁ · x + b₁) + b₂) where σ is sigmoid. Derive ∂output/∂w₁ using the chain rule.

**Hint:** Work layer by layer. σ'(z) = σ(z)(1 - σ(z)).

<details><summary>Solution</summary>

```
Let z₁ = w₁·x + b₁, a₁ = σ(z₁), z₂ = w₂·a₁ + b₂, output = σ(z₂)

∂output/∂w₁ = ∂output/∂z₂ × ∂z₂/∂a₁ × ∂a₁/∂z₁ × ∂z₁/∂w₁
             = σ(z₂)(1-σ(z₂)) × w₂ × σ(z₁)(1-σ(z₁)) × x

This IS backpropagation — chain rule applied through layers.
```
</details>

### Exercise 6 (Intermediate)
**Problem:** Compute the Jacobian matrix of f: R² → R² where f(x,y) = [x²+y, xy²].

**Hint:** J[i,j] = ∂fᵢ/∂xⱼ

<details><summary>Solution</summary>

```
J = [[∂f₁/∂x, ∂f₁/∂y],
     [∂f₂/∂x, ∂f₂/∂y]]
  = [[2x, 1],
     [y², 2xy]]
```
</details>

### Exercise 7 (Intermediate)
**Problem:** Find the Hessian matrix of f(x,y) = x³ + 3x²y - y³. Is the function convex at (1,1)?

**Hint:** H[i,j] = ∂²f/∂xᵢ∂xⱼ. Convex if H is positive semi-definite.

<details><summary>Solution</summary>

```
∂f/∂x = 3x² + 6xy,  ∂f/∂y = 3x² - 3y²
∂²f/∂x² = 6x + 6y,  ∂²f/∂y² = -6y,  ∂²f/∂x∂y = 6x

H = [[6x+6y, 6x],
     [6x, -6y]]

At (1,1): H = [[12, 6],[6, -6]]
Eigenvalues: det(H-λI) = (12-λ)(-6-λ)-36 = λ²-6λ-108 = 0
λ = (6±√(36+432))/2 → one positive, one negative
H is indefinite → NOT convex at (1,1) (saddle point)
```
</details>

### Exercise 8 (Intermediate)
**Problem:** Derive the gradient of MSE loss L = (1/n)Σ(yᵢ - wᵀxᵢ)² with respect to w.

**Hint:** Expand using matrix notation: L = (1/n)||y - Xw||².

<details><summary>Solution</summary>

```
L = (1/n)(y - Xw)ᵀ(y - Xw)
∂L/∂w = (1/n) × 2Xᵀ(Xw - y) = (2/n)Xᵀ(Xw - y)

Setting to zero (closed-form solution):
Xᵀ(Xw - y) = 0
XᵀXw = Xᵀy
w* = (XᵀX)⁻¹Xᵀy  (Normal Equation)
```
</details>

### Exercise 9 (Advanced)
**Problem:** Derive the gradient of softmax cross-entropy loss. Given logits z, softmax p = softmax(z), and one-hot target y, show that ∂L/∂z = p - y.

**Hint:** L = -Σ yⱼ log(pⱼ), where pⱼ = exp(zⱼ)/Σexp(zₖ).

<details><summary>Solution</summary>

```
∂L/∂zᵢ = -Σⱼ yⱼ × (1/pⱼ) × ∂pⱼ/∂zᵢ

For softmax: ∂pⱼ/∂zᵢ = pⱼ(δᵢⱼ - pᵢ) where δᵢⱼ is Kronecker delta

∂L/∂zᵢ = -Σⱼ yⱼ × (1/pⱼ) × pⱼ(δᵢⱼ - pᵢ)
        = -Σⱼ yⱼ(δᵢⱼ - pᵢ)
        = -(yᵢ - pᵢ × Σⱼyⱼ)
        = -(yᵢ - pᵢ × 1)    [since Σyⱼ = 1 for one-hot]
        = pᵢ - yᵢ

Therefore: ∂L/∂z = p - y  (beautifully simple!)
```
</details>

### Exercise 10 (Advanced)
**Problem:** Use Taylor expansion to show why gradient descent with learning rate η converges when η < 2/L (where L is the Lipschitz constant of the gradient).

**Hint:** Expand f(x - η∇f(x)) around x using second-order Taylor approximation.

<details><summary>Solution</summary>

```
f(x - η∇f) ≈ f(x) - η||∇f||² + (η²/2)∇fᵀH∇f

For L-smooth function: ∇fᵀH∇f ≤ L||∇f||²

f(x - η∇f) ≤ f(x) - η||∇f||² + (η²L/2)||∇f||²
           = f(x) - η(1 - ηL/2)||∇f||²

For guaranteed decrease: 1 - ηL/2 > 0 → η < 2/L
Optimal step size: η = 1/L (maximizes decrease per step)
```
</details>

### Exercise 11 (Advanced)
**Problem:** Explain vanishing/exploding gradients using the chain rule. If a network has n layers each with weight W, what happens to ∂L/∂W₁ as n grows?

**Hint:** ∂L/∂W₁ involves products of n Jacobians.

<details><summary>Solution</summary>

```
By chain rule: ∂L/∂W₁ = ∂L/∂aₙ × ∂aₙ/∂aₙ₋₁ × ... × ∂a₂/∂a₁ × ∂a₁/∂W₁

Each ∂aᵢ/∂aᵢ₋₁ ≈ Wᵢ × diag(σ'(zᵢ))

If ||W × σ'|| < 1: product → 0 exponentially (vanishing gradients)
If ||W × σ'|| > 1: product → ∞ exponentially (exploding gradients)

Solutions:
- Careful initialization (Xavier/He)
- Residual connections: gradient flows through skip connections
- LSTM/GRU: gating mechanisms control gradient flow
- Gradient clipping (for exploding)
- Batch normalization
```
</details>

### Exercise 12 (Advanced)
**Problem:** Derive the update rule for batch normalization during backpropagation. Given x̂ = (x - μ)/σ, y = γx̂ + β, find ∂L/∂γ, ∂L/∂β, and ∂L/∂x.

**Hint:** μ and σ depend on x (they're batch statistics), making the derivative of ∂L/∂x non-trivial.

<details><summary>Solution</summary>

```
∂L/∂γ = Σᵢ (∂L/∂yᵢ) × x̂ᵢ
∂L/∂β = Σᵢ (∂L/∂yᵢ)

For ∂L/∂x (complex because μ, σ depend on all xᵢ):
∂L/∂x̂ᵢ = ∂L/∂yᵢ × γ
∂L/∂σ² = Σᵢ ∂L/∂x̂ᵢ × (xᵢ-μ) × (-1/2)(σ²+ε)⁻³/²
∂L/∂μ = Σᵢ ∂L/∂x̂ᵢ × (-1/σ) + ∂L/∂σ² × (-2/m)Σᵢ(xᵢ-μ)
∂L/∂xᵢ = ∂L/∂x̂ᵢ × (1/σ) + ∂L/∂σ² × 2(xᵢ-μ)/m + ∂L/∂μ × (1/m)
```
</details>

---

## Self-Assessment Quiz

**1. The chain rule states that d/dx[f(g(x))] equals:**
- (a) f'(x) × g'(x)
- (b) f'(g(x)) × g'(x)
- (c) f(g'(x))
- (d) f'(g(x)) + g'(x)

<details><summary>Answer</summary>(b) f'(g(x)) × g'(x). Evaluate outer derivative at inner function, multiply by inner derivative.</details>

**2. The gradient ∇f points in the direction of:**
- (a) Steepest descent
- (b) Steepest ascent
- (c) Zero change
- (d) Random direction

<details><summary>Answer</summary>(b) Steepest ascent. That's why gradient DESCENT moves in the -∇f direction.</details>

**3. If f(x) has a local minimum at x₀, then:**
- (a) f'(x₀) > 0
- (b) f'(x₀) = 0 and f''(x₀) > 0
- (c) f'(x₀) = 0 and f''(x₀) < 0
- (d) f''(x₀) = 0

<details><summary>Answer</summary>(b) f'(x₀) = 0 (critical point) and f''(x₀) > 0 (concave up, confirming minimum).</details>

**4. The Jacobian matrix generalizes derivatives for:**
- (a) Scalar → Scalar functions
- (b) Vector → Vector functions
- (c) Only 2D functions
- (d) Non-differentiable functions

<details><summary>Answer</summary>(b) Vector → Vector functions. It contains all partial derivatives ∂fᵢ/∂xⱼ.</details>

**5. In backpropagation, gradients are computed using:**
- (a) Forward mode differentiation
- (b) Numerical differentiation
- (c) Reverse mode automatic differentiation
- (d) Symbolic differentiation

<details><summary>Answer</summary>(c) Reverse mode AD. It's efficient when there are many inputs but one output (scalar loss).</details>

**6. The derivative of ReLU(x) = max(0,x) is:**
- (a) Always 1
- (b) 0 for x<0, 1 for x>0, undefined at x=0
- (c) x for x>0, 0 otherwise
- (d) sigmoid(x)

<details><summary>Answer</summary>(b) The derivative is the step function. At x=0, it's typically set to 0 or 0.5 by convention.</details>

**7. A saddle point has:**
- (a) f' = 0, f'' > 0
- (b) f' = 0, f'' < 0
- (c) f' = 0, Hessian has both positive and negative eigenvalues
- (d) f' ≠ 0

<details><summary>Answer</summary>(c) At a saddle point, it's a minimum in some directions and maximum in others.</details>

**8. The integral ∫₀^∞ e^(-x²) dx is important in ML because:**
- (a) It's the normalization constant for Gaussian distribution
- (b) It equals exactly 1
- (c) It defines ReLU
- (d) It's used in backpropagation

<details><summary>Answer</summary>(a) It equals √π/2, and the full integral from -∞ to ∞ equals √π, giving the normalization for Gaussians.</details>

**9. The derivative of sigmoid σ(x) = 1/(1+e⁻ˣ) is:**
- (a) σ(x)²
- (b) σ(x)(1-σ(x))
- (c) 1-σ(x)
- (d) e⁻ˣ/(1+e⁻ˣ)

<details><summary>Answer</summary>(b) σ(x)(1-σ(x)). Maximum value is 0.25 at x=0, which contributes to vanishing gradients.</details>

**10. Automatic differentiation differs from numerical differentiation because:**
- (a) It's less accurate
- (b) It computes exact derivatives using chain rule decomposition
- (c) It only works for linear functions
- (d) It requires symbolic simplification

<details><summary>Answer</summary>(b) AD computes exact (to machine precision) derivatives by decomposing computations into elementary operations and applying the chain rule. No approximation error like finite differences.</details>

---

## Coding Challenges

### Challenge 1: Implement Gradient Descent from Scratch
```python
"""
Minimize f(x,y) = (x-3)² + (y+1)² using gradient descent.
1. Compute the gradient analytically
2. Implement the update loop
3. Track and plot the path to the minimum
4. Experiment with different learning rates (0.01, 0.1, 0.5, 1.5)
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

def f(x, y):
    return (x-3)**2 + (y+1)**2

def grad_f(x, y):
    return np.array([2*(x-3), 2*(y+1)])

def gradient_descent(lr=0.1, n_iters=50):
    point = np.array([0.0, 0.0])
    path = [point.copy()]
    for _ in range(n_iters):
        point -= lr * grad_f(point[0], point[1])
        path.append(point.copy())
    return np.array(path)

fig, axes = plt.subplots(1, 4, figsize=(16, 4))
for ax, lr in zip(axes, [0.01, 0.1, 0.5, 1.5]):
    path = gradient_descent(lr=lr)
    x = np.linspace(-2, 6, 50)
    y = np.linspace(-4, 3, 50)
    X, Y = np.meshgrid(x, y)
    Z = f(X, Y)
    ax.contour(X, Y, Z, levels=20)
    ax.plot(path[:,0], path[:,1], 'r.-')
    ax.set_title(f'lr={lr}, final=({path[-1,0]:.2f},{path[-1,1]:.2f})')
plt.tight_layout()
plt.show()
```
</details>

### Challenge 2: Numerical vs Analytical Gradient Verification
```python
"""
Implement gradient checking:
1. Define a function f(W) where W is a matrix (e.g., f = ||W @ x - y||²)
2. Compute analytical gradient
3. Compute numerical gradient using (f(W+ε) - f(W-ε))/(2ε)
4. Compare — relative error should be < 1e-5
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

def f(W, x, y):
    return np.sum((W @ x - y)**2)

def analytical_grad(W, x, y):
    return 2 * np.outer(W @ x - y, x)

def numerical_grad(W, x, y, epsilon=1e-5):
    grad = np.zeros_like(W)
    for i in range(W.shape[0]):
        for j in range(W.shape[1]):
            W_plus = W.copy(); W_plus[i,j] += epsilon
            W_minus = W.copy(); W_minus[i,j] -= epsilon
            grad[i,j] = (f(W_plus, x, y) - f(W_minus, x, y)) / (2*epsilon)
    return grad

np.random.seed(42)
W = np.random.randn(3, 4)
x = np.random.randn(4)
y = np.random.randn(3)

ag = analytical_grad(W, x, y)
ng = numerical_grad(W, x, y)
relative_error = np.linalg.norm(ag - ng) / (np.linalg.norm(ag) + np.linalg.norm(ng))
print(f"Relative error: {relative_error:.2e}")  # Should be < 1e-5
```
</details>

### Challenge 3: Implement Backpropagation for a 2-Layer Network
```python
"""
Build a 2-layer neural network (input→hidden→output) and implement:
1. Forward pass
2. Loss computation (MSE)
3. Backward pass (manual gradient computation)
4. Parameter update
Train on XOR problem: inputs=[[0,0],[0,1],[1,0],[1,1]], targets=[0,1,1,0]
"""
```

<details><summary>Solution</summary>

```python
import numpy as np

def sigmoid(x): return 1 / (1 + np.exp(-x))
def sigmoid_deriv(x): return sigmoid(x) * (1 - sigmoid(x))

np.random.seed(42)
X = np.array([[0,0],[0,1],[1,0],[1,1]], dtype=float)
y = np.array([[0],[1],[1],[0]], dtype=float)

# Initialize weights
W1 = np.random.randn(2, 4) * 0.5
b1 = np.zeros((1, 4))
W2 = np.random.randn(4, 1) * 0.5
b2 = np.zeros((1, 1))
lr = 1.0

losses = []
for epoch in range(10000):
    # Forward
    z1 = X @ W1 + b1
    a1 = sigmoid(z1)
    z2 = a1 @ W2 + b2
    a2 = sigmoid(z2)
    
    # Loss
    loss = np.mean((a2 - y)**2)
    losses.append(loss)
    
    # Backward
    dL_da2 = 2*(a2 - y)/4
    da2_dz2 = sigmoid_deriv(z2)
    dz2 = dL_da2 * da2_dz2
    
    dW2 = a1.T @ dz2
    db2 = np.sum(dz2, axis=0, keepdims=True)
    
    da1 = dz2 @ W2.T
    dz1 = da1 * sigmoid_deriv(z1)
    dW1 = X.T @ dz1
    db1 = np.sum(dz1, axis=0, keepdims=True)
    
    # Update
    W2 -= lr * dW2; b2 -= lr * db2
    W1 -= lr * dW1; b1 -= lr * db1

print(f"Final loss: {losses[-1]:.6f}")
print(f"Predictions: {a2.flatten().round(2)}")  # Should be close to [0,1,1,0]
```
</details>

### Challenge 4: Visualize Gradient Flow in Deep Networks
```python
"""
Create a deep network (10 layers) and visualize:
1. Gradient magnitudes at each layer during backprop
2. Compare: sigmoid activations vs ReLU activations
3. Show vanishing gradient problem visually
"""
```

<details><summary>Solution</summary>

```python
import numpy as np
import matplotlib.pyplot as plt

def forward_and_backward(activation='sigmoid', n_layers=10, hidden_size=50):
    np.random.seed(42)
    x = np.random.randn(32, hidden_size)
    y = np.random.randn(32, hidden_size)
    
    if activation == 'sigmoid':
        act = lambda x: 1/(1+np.exp(-np.clip(x,-500,500)))
        act_deriv = lambda x: act(x)*(1-act(x))
    else:  # relu
        act = lambda x: np.maximum(0, x)
        act_deriv = lambda x: (x > 0).astype(float)
    
    # Initialize weights
    weights = [np.random.randn(hidden_size, hidden_size)*0.5 for _ in range(n_layers)]
    
    # Forward pass - store activations
    activations = [x]
    pre_activations = []
    for W in weights:
        z = activations[-1] @ W
        pre_activations.append(z)
        activations.append(act(z))
    
    # Loss and backward
    loss_grad = 2*(activations[-1] - y)
    grad_norms = []
    
    grad = loss_grad
    for i in range(n_layers-1, -1, -1):
        grad = grad * act_deriv(pre_activations[i])
        grad_norms.append(np.linalg.norm(grad))
        grad = grad @ weights[i].T
    
    return list(reversed(grad_norms))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
sigmoid_grads = forward_and_backward('sigmoid')
relu_grads = forward_and_backward('relu')

ax1.plot(sigmoid_grads, 'b-o'); ax1.set_title('Sigmoid: Vanishing Gradients')
ax1.set_xlabel('Layer'); ax1.set_ylabel('Gradient Norm'); ax1.set_yscale('log')
ax2.plot(relu_grads, 'r-o'); ax2.set_title('ReLU: Better Gradient Flow')
ax2.set_xlabel('Layer'); ax2.set_ylabel('Gradient Norm'); ax2.set_yscale('log')
plt.tight_layout(); plt.show()
```
</details>

### Challenge 5: Implement Automatic Differentiation (Simple)
```python
"""
Build a minimal autodiff system:
1. Create a Value class that tracks computation graph
2. Implement forward operations (+, *, power, relu)
3. Implement backward() that computes gradients via reverse-mode AD
4. Verify against PyTorch autograd
"""
```

<details><summary>Solution</summary>

```python
class Value:
    def __init__(self, data, children=(), op=''):
        self.data = data
        self.grad = 0.0
        self._backward = lambda: None
        self._children = set(children)
        self._op = op
    
    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), '+')
        def _backward():
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward
        return out
    
    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), '*')
        def _backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad
        out._backward = _backward
        return out
    
    def __pow__(self, n):
        out = Value(self.data**n, (self,), f'**{n}')
        def _backward():
            self.grad += n * self.data**(n-1) * out.grad
        out._backward = _backward
        return out
    
    def relu(self):
        out = Value(max(0, self.data), (self,), 'relu')
        def _backward():
            self.grad += (self.data > 0) * out.grad
        out._backward = _backward
        return out
    
    def backward(self):
        topo = []
        visited = set()
        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for child in v._children:
                    build_topo(child)
                topo.append(v)
        build_topo(self)
        self.grad = 1.0
        for v in reversed(topo):
            v._backward()

# Test
x = Value(2.0)
y = Value(3.0)
z = x**2 + x*y + y**2  # 4 + 6 + 9 = 19
z.backward()
print(f"z={z.data}, dz/dx={x.grad}, dz/dy={y.grad}")  # dz/dx=2x+y=7, dz/dy=x+2y=8
```
</details>

---

## Interview Questions

### 1. What is backpropagation and why does it work?
<details><summary>Answer</summary>

Backpropagation is reverse-mode automatic differentiation applied to compute gradients of a scalar loss with respect to all parameters. It works by:
1. Forward pass: compute loss
2. Backward pass: apply chain rule from output to input, reusing intermediate results

Key insight: For a computation graph with n parameters and 1 scalar output, reverse mode computes ALL gradients in O(1) backward passes (vs O(n) for forward mode). This makes it practical for networks with millions of parameters.
</details>

### 2. Explain vanishing and exploding gradients. How are they solved?
<details><summary>Answer</summary>

When gradients flow through many layers via chain rule, they're multiplied at each step:
- **Vanishing**: Repeated multiplication by values < 1 (e.g., sigmoid derivative max = 0.25) → gradients → 0 → early layers don't learn
- **Exploding**: Repeated multiplication by values > 1 → gradients → ∞ → unstable training

Solutions:
- ReLU activation (gradient = 1 for positive inputs)
- Residual connections (gradient highway)
- Proper initialization (Xavier/He)
- Gradient clipping (for exploding)
- LSTM gates (for RNNs)
- Batch normalization
</details>

### 3. Why is the learning rate the most important hyperparameter?
<details><summary>Answer</summary>

Learning rate η controls step size in gradient descent: θ ← θ - η∇L.
- Too large: overshoots minima, diverges
- Too small: extremely slow convergence, gets stuck
- Must be < 2/L (L = smoothness constant) for convergence

Optimal η varies during training → use schedules (warmup, cosine decay) or adaptive methods (Adam adapts per-parameter). Unlike other hyperparameters, wrong η causes complete training failure.
</details>

### 4. What's the difference between convex and non-convex optimization in deep learning?
<details><summary>Answer</summary>

- **Convex** (linear/logistic regression): one global minimum, guaranteed convergence
- **Non-convex** (neural networks): many local minima, saddle points, plateaus

Surprisingly, deep learning works because:
1. In high dimensions, most critical points are saddle points, not local minima
2. Local minima tend to have similar loss values (loss landscape is "benign")
3. SGD noise helps escape bad regions
4. Overparameterization creates many good solutions
</details>

### 5. Explain the intuition behind Adam optimizer.
<details><summary>Answer</summary>

Adam combines momentum (first moment) and RMSProp (second moment):
- **First moment** m = β₁m + (1-β₁)g: smoothed gradient direction (reduces noise)
- **Second moment** v = β₂v + (1-β₂)g²: per-parameter learning rate (adapts to gradient magnitude)
- Update: θ -= η × m/(√v + ε)

Intuition: For parameters with consistently large gradients → large v → smaller effective lr (prevents overshooting). For sparse/noisy gradients → momentum smooths the path. Bias correction handles initialization.
</details>

### 6. How does batch normalization help training from a calculus perspective?
<details><summary>Answer</summary>

Batch normalization smooths the loss landscape:
1. Reduces internal covariate shift (input distributions to each layer change less)
2. Makes the loss landscape more Lipschitz smooth (bounded gradients)
3. Allows higher learning rates (smoother landscape → larger safe step sizes)
4. Provides implicit regularization via batch noise

From a gradient flow perspective: normalizing activations prevents them from growing unboundedly, keeping gradients in a reasonable range throughout the network.
</details>

### 7. What is the relationship between the Hessian and learning rate selection?
<details><summary>Answer</summary>

The Hessian H captures curvature of the loss landscape:
- Eigenvalues of H = curvature in each direction
- Max eigenvalue λ_max determines the maximum safe learning rate: η < 2/λ_max
- Condition number κ = λ_max/λ_min determines convergence speed
- High κ → elongated valleys → slow convergence with fixed lr

Second-order methods (Newton's method: θ -= H⁻¹∇L) account for curvature but are O(n²) memory for n parameters. Approximations: L-BFGS, natural gradient, K-FAC.
</details>
