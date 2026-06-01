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
