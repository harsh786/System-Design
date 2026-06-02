# Gaussian Mixture Models (GMM)

## Intuition

Data is generated from a **mixture of K Gaussian distributions**. Each point belongs to each cluster with some **probability** (soft clustering), unlike K-Means which makes hard assignments.

**Key advantage:** Can model elliptical, overlapping clusters with different sizes and orientations.

## Mathematical Model

```
P(x) = Σₖ πₖ · N(x | μₖ, Σₖ)

where:
  πₖ = mixing coefficient (prior probability of cluster k, Σπₖ = 1)
  μₖ = mean of component k
  Σₖ = covariance matrix of component k (controls shape/orientation)
  K  = number of components
```

## EM Algorithm (Expectation-Maximization)

```
┌─────────────────────────────────────────────────────────┐
│  Initialize: random μₖ, Σₖ = I, πₖ = 1/K              │
│                                                          │
│  Repeat until convergence:                               │
│                                                          │
│  E-Step: Compute responsibilities (soft assignments)     │
│    γₙₖ = πₖ·N(xₙ|μₖ,Σₖ) / Σⱼ πⱼ·N(xₙ|μⱼ,Σⱼ)        │
│    "How much does component k explain point n?"          │
│                                                          │
│  M-Step: Update parameters using responsibilities        │
│    Nₖ = Σₙ γₙₖ         (effective cluster size)        │
│    μₖ = (1/Nₖ) Σₙ γₙₖ·xₙ       (weighted mean)       │
│    Σₖ = (1/Nₖ) Σₙ γₙₖ·(xₙ-μₖ)(xₙ-μₖ)ᵀ  (weighted cov)│
│    πₖ = Nₖ / N                   (mixing weight)       │
│                                                          │
│  Check: log-likelihood converged?                        │
└─────────────────────────────────────────────────────────┘
```

## GMM vs K-Means

```
K-Means (Hard):              GMM (Soft):
Point belongs to 1 cluster   Point has probability for each cluster

   ○○○○ | ×××               P(A)=0.9  P(A)=0.6
   ○○○○ | ×××               P(B)=0.1  P(B)=0.4
   ○○○○ | ×××               
                             Handles overlapping clusters
Hard boundary               Soft/probabilistic boundary
Spherical only              Any covariance structure (elliptical)
```

**K-Means is a special case of GMM** with:
- Σₖ = σ²I (spherical, equal) and σ² → 0
- πₖ = 1/K (equal priors)
- Hard assignments (argmax of responsibilities)

## Model Selection: BIC and AIC

How to choose K (number of components)?

```
BIC = -2·log(L) + p·log(n)    (penalizes complexity more)
AIC = -2·log(L) + 2·p          (less penalty)

where p = number of parameters, n = samples
Lower BIC/AIC = better model

Choose K that minimizes BIC (preferred for clustering).
```

## From-Scratch Implementation

```python
import numpy as np
from scipy.stats import multivariate_normal

class GMM:
    def __init__(self, k=3, max_iters=100, tol=1e-6):
        self.k = k
        self.max_iters = max_iters
        self.tol = tol

    def fit(self, X):
        n, d = X.shape
        # Initialize
        self.means = X[np.random.choice(n, self.k, replace=False)]
        self.covs = [np.eye(d) for _ in range(self.k)]
        self.weights = np.ones(self.k) / self.k

        prev_ll = -np.inf
        for _ in range(self.max_iters):
            # E-step
            resp = self._e_step(X)
            # M-step
            self._m_step(X, resp)
            # Convergence check
            ll = self._log_likelihood(X)
            if ll - prev_ll < self.tol:
                break
            prev_ll = ll

        self.labels_ = resp.argmax(axis=1)
        self.responsibilities_ = resp
        return self

    def _e_step(self, X):
        resp = np.zeros((len(X), self.k))
        for k in range(self.k):
            resp[:, k] = self.weights[k] * multivariate_normal.pdf(
                X, self.means[k], self.covs[k]
            )
        resp /= resp.sum(axis=1, keepdims=True)
        return resp

    def _m_step(self, X, resp):
        n = len(X)
        for k in range(self.k):
            Nk = resp[:, k].sum()
            self.means[k] = (resp[:, k] @ X) / Nk
            diff = X - self.means[k]
            self.covs[k] = (resp[:, k][:, None] * diff).T @ diff / Nk
            self.covs[k] += 1e-6 * np.eye(X.shape[1])  # regularization
            self.weights[k] = Nk / n

    def _log_likelihood(self, X):
        ll = np.zeros(len(X))
        for k in range(self.k):
            ll += self.weights[k] * multivariate_normal.pdf(
                X, self.means[k], self.covs[k]
            )
        return np.log(ll).sum()

    def bic(self, X):
        n, d = X.shape
        n_params = self.k * (d + d*(d+1)//2 + 1) - 1
        return -2 * self._log_likelihood(X) + n_params * np.log(n)
```

## Sklearn Code

```python
from sklearn.mixture import GaussianMixture
import numpy as np

# Fit GMM
gmm = GaussianMixture(n_components=3, covariance_type='full', random_state=42)
gmm.fit(X)

# Hard labels
labels = gmm.predict(X)

# Soft probabilities
probs = gmm.predict_proba(X)  # shape: (n, K)

# Model selection
bics = []
for k in range(1, 10):
    gm = GaussianMixture(n_components=k, random_state=42).fit(X)
    bics.append(gm.bic(X))
best_k = np.argmin(bics) + 1

# Covariance types: 'full', 'tied', 'diag', 'spherical'
# 'full' = each component has own full covariance (most flexible)
# 'diag' = diagonal only (axis-aligned ellipses, fewer params)
# 'spherical' = σ²I (equivalent to K-Means with soft assignments)
```

## When to Use GMM

**Use when:**
- Clusters overlap and you need probability of membership
- Clusters are elliptical with different orientations
- You need a generative model (can sample new data)
- Downstream task benefits from soft assignments (e.g., uncertainty-aware)

**Don't use when:**
- Clusters are non-convex (use DBSCAN)
- Data is very high-dimensional (covariance estimation unstable)
- You have very little data relative to dimensions
- You just need hard labels and clusters are spherical (K-Means is simpler/faster)

## Common Mistakes

1. **Singular covariance** — too few points for a component. Fix: add regularization (`reg_covar=1e-6`) or use 'diag' covariance
2. **Too many components for data size** — need enough data to estimate full covariance matrices (d(d+1)/2 params per component)
3. **Sensitive to initialization** — use `n_init=10` to run multiple times
4. **Ignoring BIC** — always compare models with different K using BIC

## Interview Questions

**Q1: Explain EM intuitively.**
E-step: "Given current cluster parameters, how much does each cluster explain each point?" (compute soft assignments). M-step: "Given soft assignments, what are the best cluster parameters?" (weighted MLE). Repeat until stable.

**Q2: Why does EM converge? Can it get stuck?**
EM is guaranteed to increase (or maintain) log-likelihood each iteration. It converges to a LOCAL maximum — not necessarily global. Multiple restarts help.

**Q3: K-Means is a special case of GMM. Prove it.**
Set all Σₖ = σ²I, all πₖ = 1/K. As σ² → 0, responsibilities γₙₖ → 1 for nearest centroid, 0 otherwise (hard assignment). M-step becomes μₖ = mean of assigned points. This IS K-Means.

**Q4: When would GMM give different results than K-Means?**
When clusters are elliptical (different covariances), overlapping, or different sizes. GMM captures shape/orientation; K-Means assumes spherical equal-size clusters.

**Q5: How do you handle high-dimensional data with GMM?**
Use `covariance_type='diag'` (reduces params from d² to d per component), apply PCA first to reduce dimensions, or use regularization. Full covariance with d > 50 is usually problematic.
