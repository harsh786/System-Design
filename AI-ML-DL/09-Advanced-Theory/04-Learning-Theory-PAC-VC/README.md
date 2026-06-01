# Learning Theory: PAC, VC Dimension, and Beyond

## Why Learning Theory Matters

```
Without theory, ML is alchemy. Theory answers:
  - How much data do I NEED?
  - Will my model generalize?
  - Is this problem even learnable?
  - Why does overparameterization work?
```

## PAC Learning Framework

**Probably Approximately Correct** (Valiant, 1984):

```
Setup:
  - Instance space X, label space Y = {0, 1}
  - Unknown distribution D over X
  - Unknown target concept c: X → Y
  - Hypothesis class H
  - Learner receives m samples S = {(xᵢ, c(xᵢ))} drawn i.i.d. from D

Definition: H is PAC-learnable if there exists algorithm A such that:
  For all ε > 0 (accuracy), δ > 0 (confidence), distributions D, targets c ∈ H:
  
  Given m ≥ m₀(ε, δ) samples, A outputs h ∈ H satisfying:
    P[error(h) ≤ ε] ≥ 1 - δ

  where error(h) = P_{x~D}[h(x) ≠ c(x)]

Sample complexity for finite H:
  m ≥ (1/ε)(ln|H| + ln(1/δ))
```

### Intuition

```
"With high probability (1-δ), the learned hypothesis has 
low error (≤ε), given enough samples."

More complex H (larger |H|) → need more samples
Want smaller ε (more accurate) → need more samples
Want smaller δ (more confident) → need more samples
```

## VC Dimension

For infinite hypothesis classes, |H| is infinite. We need a better measure of complexity.

### Shattering

```
A set S = {x₁, ..., x_m} is shattered by H if:
  For every possible labeling of S, there exists h ∈ H that realizes it.
  → H can achieve ALL 2^m labelings on S.
```

### Definition

```
VC(H) = largest m such that there EXISTS a set of size m shattered by H

Examples:
  - Linear classifiers in ℝ²: VC = 3
    (can shatter 3 points, cannot shatter 4 in general position)
    
      ●       ○        ●       ○
        ○   ●        ○       ●
      All 8 labelings of 3 points achievable with lines
      
  - Linear classifiers in ℝ^d: VC = d + 1
  - Intervals on ℝ: VC = 2
  - k-nearest neighbors: VC = ∞ (can memorize anything)
  - Neural network with W weights: VC = O(W log W)
```

### VC Generalization Bound

```
With probability ≥ 1-δ:

  error_true(h) ≤ error_train(h) + √((VC(H)(ln(2m/VC(H)) + 1) + ln(4/δ)) / m)
                                     └────────────── complexity term ──────────────┘

Sample complexity: m = O((VC/ε²) × log(VC/ε))

Higher VC → need more data to generalize
```

## Rademacher Complexity

A tighter, data-dependent complexity measure:

```
Empirical Rademacher Complexity:
  R̂_m(H) = E_σ[sup_{h∈H} (1/m) Σᵢ σᵢ h(xᵢ)]

Where σᵢ ∈ {-1, +1} are random (Rademacher) variables.

Intuition: How well can H fit RANDOM noise on the training data?
  - If H fits random labels well → too complex → poor generalization
  - If H cannot fit random noise → well-constrained

Generalization bound:
  error_true(h) ≤ error_train(h) + 2R̂_m(H) + 3√(ln(2/δ)/(2m))
```

## Bias-Complexity Tradeoff (Theoretical View)

```
error_true(h) = error_approx(H) + error_estimation(h, m)
               └──── bias ────┘   └──── variance ────────┘

error_approx = inf_{h∈H} error_true(h)  (best possible in H)
error_estimation = error_true(ĥ) - error_approx  (due to finite samples)

Larger H → lower bias, higher variance (need more data)
Smaller H → higher bias, lower variance

┌─────────────────────────────────────────────┐
│  Error                                       │
│  │ \                                         │
│  │  \  Total                                 │
│  │   \    /                                  │
│  │    \/─/   ← Optimal complexity            │
│  │    /\                                     │
│  │   /  \__  Estimation (variance)           │
│  │  /                                        │
│  │ /__________  Approximation (bias)         │
│  └──────────────── Model Complexity          │
└─────────────────────────────────────────────┘
```

## No Free Lunch Theorem

```
Theorem (Wolpert & Macready, 1997):
  Averaged over ALL possible target functions, every learning 
  algorithm has the same expected performance.

Implication:
  - No universally best algorithm
  - Every algorithm that excels on some problems MUST fail on others
  - We need inductive biases matched to our problem domain

Practical meaning:
  "Random forests aren't better than linear regression in general —
   they're better for YOUR specific class of problems."
```

## Regularization Theory

```
Regularized risk minimization:
  ĥ = argmin_{h∈H} [(1/m)Σᵢ L(h(xᵢ), yᵢ) + λ Ω(h)]
                     └─── empirical risk ───┘   └ complexity penalty ┘

Structural Risk Minimization (SRM):
  Choose H that minimizes: empirical risk + VC confidence
  (Automatically trades off bias and variance)

Common regularizers and their effect:
  L2 (Ridge):    Ω(w) = ||w||²     → small weights, smooth functions
  L1 (Lasso):    Ω(w) = ||w||₁     → sparse weights, feature selection
  Dropout:       Random zeroing     → ensemble of subnetworks
  Early stopping: Implicit L2        → limits effective complexity
```

## Double Descent Phenomenon

Classical theory predicts U-shaped test error. Reality is different:

```
Test Error
  │
  │\        Classical           Modern (overparameterized)
  │ \      /                   
  │  \    /                    
  │   \  /    │  ╲             
  │    \/     │   ╲  ─────── 
  │           │    ╲/         decreasing again!
  │           │               
  └───────────┼──────────── Model Size / Epochs
         Interpolation
           Threshold
           (train error = 0)

Three regimes:
  1. Underfitting: too few parameters
  2. Interpolation threshold: just enough to memorize → worst generalization
  3. Overparameterized: MORE parameters → BETTER generalization

Why? Overparameterized models find simpler interpolating solutions
(implicit regularization via SGD + architecture)
```

## Neural Tangent Kernel (NTK)

```
Key insight: Infinitely wide neural networks behave as LINEAR models
in a fixed feature space (the NTK regime).

For f(x; θ), the Neural Tangent Kernel is:
  K(x, x') = ⟨∇_θ f(x; θ), ∇_θ f(x'; θ)⟩

At initialization with infinite width:
  - K converges to a deterministic kernel K∞
  - Training dynamics become linear: f_t = f_0 + K∞(K∞ + λI)⁻¹(y - f_0)
  - Equivalent to kernel regression with K∞!

Implications:
  - Explains why overparameterized networks generalize
  - Training is convex in the infinite-width limit
  - But: real networks operate in "rich/feature learning" regime, not NTK
```

## Lottery Ticket Hypothesis

```
Frankle & Carlin (2019):
  "A randomly-initialized dense network contains a subnetwork (the 
  'winning ticket') that, when trained in isolation, can match the 
  full network's accuracy in at most the same number of iterations."

Algorithm (Iterative Magnitude Pruning):
  1. Initialize network with weights θ₀
  2. Train to get θ_T
  3. Prune smallest-magnitude weights (e.g., 20%)
  4. Reset remaining weights to their ORIGINAL values θ₀
  5. Repeat from step 2

Finding: 90%+ of weights can be removed without accuracy loss!

Implications for practice:
  - Train large, deploy small
  - Structured pruning for actual speedup
  - Suggests we need large networks for FINDING good subnetworks
```

## Scaling Laws

```
Kaplan et al. (2020), Hoffmann et al. (2022 - Chinchilla):

Loss scales as power law with:
  L(N) ~ N^(-α_N)     N = number of parameters
  L(D) ~ D^(-α_D)     D = dataset size (tokens)
  L(C) ~ C^(-α_C)     C = compute (FLOPs)

Chinchilla optimal: N and D should scale equally with compute
  N_opt ∝ C^0.5
  D_opt ∝ C^0.5
  → "Most large models are undertrained"

Practical implications:
  - Can predict performance before training
  - Guides compute budget allocation
  - 10× more compute → specific predictable improvement
  - Diminishing returns but no plateau observed yet

┌──────────────────────────────────────────────┐
│ log(Loss)                                     │
│  │ ╲                                          │
│  │  ╲                                         │
│  │   ╲                                        │
│  │    ╲                                       │
│  │     ╲╲                                     │
│  │       ╲╲___                                │
│  │            ╲___                             │
│  └──────────────── log(Compute)               │
│  Straight line on log-log = power law         │
└──────────────────────────────────────────────┘
```

## Summary: Connecting Theory to Practice

| Theory | Practical Implication |
|--------|----------------------|
| PAC bounds | Minimum dataset size estimation |
| VC dimension | Model complexity selection |
| No Free Lunch | Must encode domain knowledge |
| Double descent | Don't fear overparameterization |
| NTK | Why wide networks train easily |
| Lottery Ticket | Pruning strategy |
| Scaling Laws | Compute budget planning |

## Interview Questions

1. Explain VC dimension intuitively and give examples.
2. Why can a neural network with millions of parameters generalize well despite classical theory saying it shouldn't?
3. What does the No Free Lunch theorem mean for AutoML?
4. Explain double descent. When does it occur?
5. How would you use scaling laws to plan a training run?
6. What is the relationship between regularization and generalization bounds?
7. Can you explain PAC learning to a product manager?

## Key Papers

- Valiant, "A Theory of the Learnable" (1984)
- Vapnik & Chervonenkis, "On the Uniform Convergence" (1971)
- Zhang et al., "Understanding Deep Learning Requires Rethinking Generalization" (2017)
- Belkin et al., "Reconciling Modern ML Practice and the Bias-Variance Trade-off" (2019)
- Jacot et al., "Neural Tangent Kernel" (2018)
- Frankle & Carlin, "The Lottery Ticket Hypothesis" (2019)
- Kaplan et al., "Scaling Laws for Neural Language Models" (2020)
- Hoffmann et al., "Training Compute-Optimal Large Language Models" (Chinchilla, 2022)
