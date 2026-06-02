# PCA (Principal Component Analysis)

## Intuition

Find the directions (axes) along which data varies the most. Project data onto these directions to reduce dimensions while keeping maximum information.

**Analogy:** If you photograph a 3D object, PCA finds the best camera angle that captures the most shape — the angle where the shadow has maximum spread.

## Mathematical Formulation

```
Given centered data X (n×d), find direction w that maximizes variance:

Var(Xw) = wᵀΣw    where Σ = (1/n)XᵀX (covariance matrix)

Optimization:
  maximize  wᵀΣw
  subject to wᵀw = 1

Lagrangian: L = wᵀΣw - λ(wᵀw - 1)
∂L/∂w = 2Σw - 2λw = 0
→ Σw = λw    (eigenvalue equation!)

Solution: w = eigenvector of Σ, variance along w = eigenvalue λ
First PC = eigenvector with LARGEST eigenvalue
```

## Algorithm

```
PCA Algorithm:
1. Center data: X ← X - mean(X)
2. Compute covariance matrix: Σ = (1/n)XᵀX
3. Eigendecompose: Σ = VΛVᵀ  (or use SVD: X = UΣVᵀ)
4. Sort eigenvectors by eigenvalue (descending)
5. Select top k eigenvectors → projection matrix W (d×k)
6. Transform: Z = XW  (n×k reduced data)
```

## Choosing Number of Components

```
Cumulative Variance Explained:
100%┤                    ─────────────
    │              ─────
 95%┤·········────·····················  ← Common threshold
    │      ──
 80%┤    ─
    │  ─
 70%┤──
    └─────┬─────┬─────┬─────┬─────── Components
          1     2     3     4     5

Rules:
- Keep enough for ≥ 95% variance (conservative)
- Keep enough for ≥ 90% variance (ML pipeline)
- Elbow in scree plot (eigenvalues vs component #)
- Kaiser rule: keep components with eigenvalue > 1 (on correlation matrix)
```

## From-Scratch Implementation

```python
import numpy as np

class PCA:
    def __init__(self, n_components=2):
        self.n_components = n_components

    def fit(self, X):
        self.mean_ = X.mean(axis=0)
        X_centered = X - self.mean_

        # Covariance matrix
        cov = np.cov(X_centered, rowvar=False)

        # Eigendecomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov)

        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        self.eigenvalues_ = eigenvalues[idx]
        self.components_ = eigenvectors[:, idx[:self.n_components]].T  # (k×d)

        self.explained_variance_ = self.eigenvalues_[:self.n_components]
        self.explained_variance_ratio_ = (
            self.explained_variance_ / self.eigenvalues_.sum()
        )
        return self

    def transform(self, X):
        return (X - self.mean_) @ self.components_.T

    def inverse_transform(self, Z):
        return Z @ self.components_ + self.mean_

    def fit_transform(self, X):
        self.fit(X)
        return self.transform(X)
```

## Sklearn Code

```python
from sklearn.decomposition import PCA, KernelPCA
from sklearn.preprocessing import StandardScaler

# IMPORTANT: Standardize first (PCA is affected by scale)
X_scaled = StandardScaler().fit_transform(X)

# Fit PCA
pca = PCA(n_components=0.95)  # Keep 95% variance
X_reduced = pca.fit_transform(X_scaled)
print(f"Reduced {X.shape[1]} → {X_reduced.shape[1]} dimensions")
print(f"Explained variance: {pca.explained_variance_ratio_}")

# Visualization (2D)
pca_2d = PCA(n_components=2)
X_2d = pca_2d.fit_transform(X_scaled)

# Reconstruction
X_reconstructed = pca.inverse_transform(X_reduced)
reconstruction_error = np.mean((X_scaled - X_reconstructed)**2)
```

## Kernel PCA (Non-Linear)

Standard PCA only captures linear relationships. Kernel PCA applies the kernel trick:

```python
# For non-linear structure (e.g., concentric circles)
kpca = KernelPCA(n_components=2, kernel='rbf', gamma=0.1)
X_kpca = kpca.fit_transform(X_scaled)

# Kernels: 'rbf', 'poly', 'sigmoid', 'cosine'
```

## PCA Use Cases

### 1. Noise Reduction
Low-variance components often capture noise. Reconstruct using only top components:
```python
pca = PCA(n_components=50).fit(X_noisy)
X_denoised = pca.inverse_transform(pca.transform(X_noisy))
```

### 2. Preprocessing for ML
Reduce multicollinearity and dimensions before downstream models:
```python
pca = PCA(n_components=0.95)
X_train_pca = pca.fit_transform(X_train)
X_test_pca = pca.transform(X_test)  # Use SAME transform
```

### 3. Visualization
Project high-dimensional data to 2D/3D for exploration (though t-SNE/UMAP often better for this).

## Hyperparameter Guide

| Parameter | Guidance |
|-----------|----------|
| `n_components` | Float (0.95) for variance threshold, int for fixed dims |
| `svd_solver` | 'auto' (default), 'randomized' for large sparse data |
| `whiten` | True if feeding to algorithm sensitive to scale |

## PCA vs Feature Selection

| PCA (Extraction) | Feature Selection |
|------------------|-------------------|
| Creates NEW features (linear combos) | Keeps ORIGINAL features |
| All original features contribute | Subset of features |
| Less interpretable | More interpretable |
| Always reduces dimensionality | May keep many features |

## Common Mistakes

1. **Not centering/scaling** — PCA maximizes variance; unscaled features with large range dominate
2. **Using PCA on categorical data** — PCA assumes linear continuous relationships (use MCA instead)
3. **Confusing with feature selection** — PCA components are combos, not individual features
4. **Applying fit on test data** — always `fit` on train, `transform` on test
5. **Using too few components** — losing critical information; check reconstruction error

## Interview Questions

**Q1: Prove that maximizing variance = minimizing reconstruction error.**
Reconstruction error = ||x - (xᵀw)w||² = ||x||² - (xᵀw)². Since ||x||² is constant, minimizing reconstruction error = maximizing (xᵀw)² = maximizing projected variance wᵀΣw.

**Q2: Can PCA be used for feature selection?**
No. PCA creates new features (linear combinations of all originals). For feature selection, use L1 regularization, mutual information, or tree-based importance.

**Q3: What's the relationship between PCA and SVD?**
SVD of centered X = UΣVᵀ. The right singular vectors V are the principal components (eigenvectors of XᵀX). The singular values σᵢ relate to eigenvalues: λᵢ = σᵢ²/n. SVD is numerically more stable than eigendecomposition.

**Q4: When does PCA fail?**
When important structure is non-linear (use kernel PCA or autoencoders), when variance ≠ importance (high-variance features may be noise), or when features are categorical.

**Q5: PCA vs Autoencoders?**
PCA = linear, closed-form, fast, unique solution. Autoencoder = non-linear (with activations), trained via gradient descent, can capture manifolds. A linear autoencoder with MSE loss learns the same subspace as PCA.
