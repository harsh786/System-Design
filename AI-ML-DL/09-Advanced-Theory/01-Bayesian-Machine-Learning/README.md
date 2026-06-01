# Bayesian Machine Learning

## Frequentist vs Bayesian Philosophy

| Aspect | Frequentist | Bayesian |
|--------|-------------|----------|
| Probability | Long-run frequency | Degree of belief |
| Parameters | Fixed but unknown | Random variables with distributions |
| Data | Random (from sampling) | Fixed (observed) |
| Inference | Point estimates (MLE) | Posterior distributions |
| Uncertainty | Confidence intervals | Credible intervals |
| Prior knowledge | Not formally incorporated | Encoded as prior |

```
Frequentist: P(data | θ_fixed) → point estimate θ̂
Bayesian:    P(θ | data) ∝ P(data | θ) × P(θ) → full distribution
```

## Bayes' Theorem Deep Dive

### The Formula

```
              P(D | θ) × P(θ)
P(θ | D) = ─────────────────────
                  P(D)

Where:
  P(θ | D)  = Posterior (what we want)
  P(D | θ)  = Likelihood (how well θ explains data)
  P(θ)      = Prior (what we believed before seeing data)
  P(D)      = Evidence/Marginal likelihood = ∫ P(D|θ)P(θ)dθ
```

### Intuition

```
┌──────────┐      ┌────────────┐      ┌───────────┐
│  Prior   │  ×   │ Likelihood │  =   │ Posterior │
│ (belief) │      │  (data)    │      │ (updated) │
└──────────┘      └────────────┘      └───────────┘
   wide              peaked              narrower
   uncertain         informative         more certain
```

As more data arrives, the posterior concentrates regardless of prior (asymptotically).

## Conjugate Priors

A prior is **conjugate** to a likelihood if the posterior belongs to the same family.

| Likelihood | Conjugate Prior | Posterior |
|-----------|-----------------|-----------|
| Bernoulli | Beta(α, β) | Beta(α + successes, β + failures) |
| Multinomial | Dirichlet(α) | Dirichlet(α + counts) |
| Gaussian (known σ) | Gaussian(μ₀, σ₀²) | Gaussian(updated μ, updated σ²) |
| Poisson | Gamma(α, β) | Gamma(α + Σxᵢ, β + n) |
| Exponential | Gamma(α, β) | Gamma(α + n, β + Σxᵢ) |

```python
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Beta-Binomial conjugate example
# Prior: Beta(2, 2) - mild belief coin is fair
alpha_prior, beta_prior = 2, 2

# Data: 7 heads out of 10 flips
heads, tails = 7, 3

# Posterior: Beta(2+7, 2+3) = Beta(9, 5)
alpha_post = alpha_prior + heads
beta_post = beta_prior + tails

x = np.linspace(0, 1, 200)
plt.plot(x, stats.beta.pdf(x, alpha_prior, beta_prior), label='Prior')
plt.plot(x, stats.beta.pdf(x, alpha_post, beta_post), label='Posterior')
plt.axvline(heads/(heads+tails), color='r', linestyle='--', label='MLE')
plt.legend()
```

## Bayesian Linear Regression

### Model

```
y = Xw + ε,  ε ~ N(0, σ²I)
Prior: w ~ N(0, τ²I)

Posterior: P(w | X, y) = N(w | μ_n, Σ_n)
  Σ_n = (1/σ² × XᵀX + 1/τ² × I)⁻¹
  μ_n = Σ_n × (1/σ² × Xᵀy)
```

### Predictive Distribution

```
P(y* | x*, X, y) = N(y* | μ_n᙮x*, x*ᵀΣ_n x* + σ²)
                                      ↑
                    Uncertainty grows far from training data
```

```python
import numpy as np

class BayesianLinearRegression:
    def __init__(self, alpha=1.0, beta=1.0):
        """alpha = 1/τ² (prior precision), beta = 1/σ² (noise precision)"""
        self.alpha = alpha
        self.beta = beta
    
    def fit(self, X, y):
        # Posterior covariance
        self.Sigma = np.linalg.inv(
            self.alpha * np.eye(X.shape[1]) + self.beta * X.T @ X
        )
        # Posterior mean
        self.mu = self.beta * self.Sigma @ X.T @ y
        return self
    
    def predict(self, X_new):
        y_mean = X_new @ self.mu
        # Predictive variance (includes both epistemic + aleatoric)
        y_var = 1/self.beta + np.sum(X_new @ self.Sigma * X_new, axis=1)
        return y_mean, y_var
```

## Markov Chain Monte Carlo (MCMC)

When posteriors are intractable (no conjugacy), we **sample** from them.

### Core Idea

Build a Markov chain whose **stationary distribution** equals the target posterior.

```
┌─────────────────────────────────────────────────────────┐
│  θ₁ → θ₂ → θ₃ → ... → θ_N                             │
│  (burn-in)    (mixing)     (samples from posterior)     │
└─────────────────────────────────────────────────────────┘
```

### Metropolis-Hastings

```
Algorithm:
1. Initialize θ₀
2. For t = 1, 2, ..., N:
   a. Propose θ* ~ q(θ* | θₜ₋₁)  (e.g., Gaussian centered at current)
   b. Compute acceptance ratio:
      α = min(1, [P(θ*|D) × q(θₜ₋₁|θ*)] / [P(θₜ₋₁|D) × q(θ*|θₜ₋₁)])
   c. Accept θₜ = θ* with probability α, else θₜ = θₜ₋₁
```

```python
def metropolis_hastings(log_posterior, initial, n_samples, proposal_std=0.5):
    samples = [initial]
    current = initial
    accepted = 0
    
    for _ in range(n_samples):
        proposed = current + np.random.normal(0, proposal_std, size=current.shape)
        log_ratio = log_posterior(proposed) - log_posterior(current)
        
        if np.log(np.random.uniform()) < log_ratio:
            current = proposed
            accepted += 1
        samples.append(current.copy())
    
    print(f"Acceptance rate: {accepted/n_samples:.2%}")
    return np.array(samples)
```

### Gibbs Sampling

Sample each dimension conditionally on all others:

```
For each dimension i:
  θᵢ ~ P(θᵢ | θ₋ᵢ, D)

Works when conditional distributions are tractable
(e.g., LDA topic model, Gaussian mixtures)
```

### Hamiltonian Monte Carlo (HMC)

Uses gradient information to make distant proposals with high acceptance:

```
Physics analogy:
  θ = position,  r = momentum
  H(θ, r) = U(θ) + K(r)  (Hamiltonian = potential + kinetic)
  U(θ) = -log P(θ|D)      (negative log posterior)
  K(r) = r᙮r / 2

Leapfrog integration:
  r ← r - (ε/2) × ∇U(θ)
  θ ← θ + ε × r
  r ← r - (ε/2) × ∇U(θ)
  (repeat L steps)
```

HMC is what Stan and PyMC use internally. Much more efficient than random-walk MH.

## Variational Inference

### Idea

Approximate the intractable posterior P(θ|D) with a simpler distribution q(θ)
by minimizing KL divergence.

```
KL(q(θ) || P(θ|D)) = E_q[log q(θ)] - E_q[log P(θ|D)]

Since P(θ|D) is intractable, maximize the ELBO instead:

ELBO = E_q[log P(D|θ)] - KL(q(θ) || P(θ))
     = (expected log-likelihood) - (complexity penalty)

Maximizing ELBO ≡ Minimizing KL(q || posterior)
```

### Mean-Field Approximation

```
q(θ) = ∏ᵢ qᵢ(θᵢ)   (fully factorized)

Each factor: log qᵢ(θᵢ) = E_{q₋ᵢ}[log P(θ, D)] + const

Coordinate ascent: update each qᵢ holding others fixed
```

### VI vs MCMC

| | MCMC | Variational Inference |
|---|------|----------------------|
| Accuracy | Exact (asymptotically) | Approximate |
| Speed | Slow | Fast |
| Scalability | Poor (sequential) | Good (SGD, mini-batch) |
| Diagnostics | Well-understood | Harder |
| Use case | Gold standard, small data | Large-scale, production |

## Bayesian Neural Networks

Replace point weights with distributions:

```
Standard NN: y = f(x; w)        where w is fixed
Bayesian NN: y = f(x; w)        where w ~ P(w|D)

Prediction: P(y*|x*) = ∫ P(y*|x*, w) P(w|D) dw
                        ≈ (1/T) Σₜ P(y*|x*, wₜ)  where wₜ ~ P(w|D)
```

### Practical Approximations

1. **MC Dropout**: Use dropout at test time as approximate variational inference
2. **Bayes by Backprop**: Learn μ and σ for each weight, sample w = μ + σ⊙ε
3. **Deep Ensembles**: Train K independent networks (not Bayesian but captures uncertainty)

```python
# MC Dropout for uncertainty estimation
class MCDropoutModel(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, dropout=0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        x = F.relu(self.dropout(self.fc1(x)))
        return self.dropout(self.fc2(x))
    
    def predict_with_uncertainty(self, x, n_samples=100):
        self.train()  # Keep dropout active!
        preds = torch.stack([self(x) for _ in range(n_samples)])
        return preds.mean(0), preds.var(0)  # mean, uncertainty
```

## Gaussian Processes

### Definition

A GP is a collection of random variables, any finite subset of which is jointly Gaussian.

```
f(x) ~ GP(m(x), k(x, x'))

m(x) = E[f(x)]                    (mean function, often 0)
k(x, x') = E[(f(x)-m(x))(f(x')-m(x'))]  (covariance/kernel function)
```

### Common Kernels

```
RBF (Squared Exponential):
  k(x, x') = σ² exp(-||x - x'||² / (2ℓ²))
  → smooth, infinitely differentiable functions

Matérn:
  k(x, x') = σ² (2^(1-ν)/Γ(ν)) (√(2ν)r/ℓ)^ν K_ν(√(2ν)r/ℓ)
  → controls smoothness via ν (ν=1/2: Ornstein-Uhlenbeck, ν→∞: RBF)

Periodic:
  k(x, x') = σ² exp(-2sin²(π|x-x'|/p) / ℓ²)

Linear:
  k(x, x') = σ² x᙮x'  → Bayesian linear regression
```

### GP Regression

```
Given: Training (X, y), test X*
Joint distribution:
  [y ]     [K(X,X)+σ²I   K(X,X*) ]
  [f*] ~ N([K(X*,X)      K(X*,X*)])

Posterior predictive:
  μ* = K(X*,X)[K(X,X)+σ²I]⁻¹ y
  Σ* = K(X*,X*) - K(X*,X)[K(X,X)+σ²I]⁻¹ K(X,X*)
```

```python
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel

kernel = RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)
gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=10)
gp.fit(X_train, y_train)

y_mean, y_std = gp.predict(X_test, return_std=True)
# y_std gives calibrated uncertainty estimates!
```

### Scalability: Sparse GPs

Problem: GP regression is O(n³) due to matrix inversion.

```
Sparse GP with M inducing points (M << N):
  - Select M pseudo-inputs Z
  - Approximate: P(f|X,y) ≈ P(f|Z, u) where u = f(Z)
  - Complexity: O(NM²) instead of O(N³)

Methods: FITC, VFE (Titsias 2009), SVGP (Hensman 2013)
```

## Bayesian Optimization

For expensive black-box function optimization (e.g., hyperparameter tuning):

```
┌──────────────────────────────────────────┐
│ 1. Fit GP surrogate to observed (x, y)   │
│ 2. Compute acquisition function          │
│ 3. Select next x* = argmax acquisition   │
│ 4. Evaluate expensive f(x*)              │
│ 5. Add to observations, repeat           │
└──────────────────────────────────────────┘

Acquisition functions:
  - Expected Improvement: EI(x) = E[max(f(x) - f_best, 0)]
  - Upper Confidence Bound: UCB(x) = μ(x) + κσ(x)
  - Probability of Improvement: PI(x) = P(f(x) > f_best)
```

```python
from skopt import gp_minimize

def objective(params):
    lr, n_layers = params
    # Train model, return negative validation accuracy
    return -train_and_evaluate(lr, n_layers)

result = gp_minimize(
    objective,
    dimensions=[(1e-5, 1e-1, "log-uniform"), (1, 10)],
    n_calls=50, n_initial_points=10
)
```

## Uncertainty Quantification

```
Total Uncertainty = Aleatoric + Epistemic

Aleatoric (data uncertainty):
  - Irreducible noise in data
  - Does NOT decrease with more data
  - Example: sensor noise, ambiguous labels

Epistemic (model uncertainty):
  - Uncertainty due to limited data/knowledge
  - DECREASES with more data
  - Example: predictions far from training data

┌─────────────────────────────────────────────────┐
│  Far from data: HIGH epistemic, low aleatoric   │
│  Noisy region:  low epistemic, HIGH aleatoric   │
│  Sparse+noisy:  HIGH both                       │
└─────────────────────────────────────────────────┘
```

## When Bayesian Methods Are Essential

1. **Small data** — priors prevent overfitting
2. **Safety-critical** — need calibrated uncertainty (medical, autonomous driving)
3. **Active learning** — need to know where model is uncertain
4. **Hyperparameter optimization** — Bayesian optimization
5. **Online learning** — posterior becomes next prior
6. **Model comparison** — Bayes factors

## Interview Questions

1. When would you prefer Bayesian over frequentist methods?
2. Explain the ELBO and why we maximize it.
3. How does MC Dropout approximate Bayesian inference?
4. What is the computational complexity of GP regression and how do you scale it?
5. Explain aleatoric vs epistemic uncertainty with a real example.
6. Why is HMC more efficient than Metropolis-Hastings?
7. How would you use Bayesian optimization to tune a production model?

## Key Papers

- Blei et al., "Variational Inference: A Review for Statisticians" (2017)
- Gal & Ghahramani, "Dropout as a Bayesian Approximation" (2016)
- Rasmussen & Williams, "Gaussian Processes for Machine Learning" (2006)
- Neal, "Bayesian Learning for Neural Networks" (1996)
- Hoffman et al., "Stochastic Variational Inference" (2013)
- Snoek et al., "Practical Bayesian Optimization" (2012)
