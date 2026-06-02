# t-SNE and UMAP

## Overview

Both are **non-linear dimensionality reduction** methods primarily used for **visualization** of high-dimensional data in 2D/3D. They preserve local neighborhood structure.

```
High-D data → 2D visualization
Goal: Points close in high-D should remain close in 2D
```

---

## t-SNE (t-distributed Stochastic Neighbor Embedding)

### How It Works

```
1. HIGH-D: Model pairwise similarities as Gaussian probabilities
   p_{j|i} = exp(-||xᵢ-xⱼ||²/2σᵢ²) / Σ_{k≠i} exp(-||xᵢ-xₖ||²/2σᵢ²)
   (σᵢ chosen so perplexity matches user-specified value)

2. LOW-D: Model similarities using heavy-tailed Student-t distribution
   q_{ij} = (1 + ||yᵢ-yⱼ||²)⁻¹ / Σ_{k≠l} (1 + ||yₖ-yₗ||²)⁻¹

3. OPTIMIZE: Minimize KL(P||Q) via gradient descent
   Move low-D points until q matches p
```

### Why Student-t (Not Gaussian) in Low-D?

The **crowding problem**: In low-D, there isn't enough room for all moderate-distance neighbors. Heavy tails of Student-t allow moderate high-D distances to map to larger low-D distances, preventing clusters from collapsing together.

### Key Properties

- Preserves **local** structure (nearby points stay nearby)
- **Does NOT preserve** global structure (distances between clusters are meaningless)
- **Non-parametric** — cannot embed new points without refitting
- **Stochastic** — different runs give different layouts
- Complexity: O(n²), or O(n log n) with Barnes-Hut approximation

### Perplexity Parameter

- Controls effective number of neighbors considered
- Typical range: 5–50
- Low perplexity → tight local clusters, noisy
- High perplexity → smoother, more global structure
- **Rule of thumb:** Try 5, 30, 50 and compare

---

## UMAP (Uniform Manifold Approximation and Projection)

### How It Improves on t-SNE

Based on Riemannian geometry and algebraic topology:
1. Build a fuzzy simplicial complex (weighted k-NN graph) in high-D
2. Find a low-D layout that best preserves the topological structure
3. Optimize using cross-entropy (not KL divergence)

### Key Advantages over t-SNE

| Aspect | t-SNE | UMAP |
|--------|-------|------|
| Speed | O(n²) or O(n log n) | O(n) with NN approximation |
| Global structure | Poor | Better preserved |
| Reproducibility | Non-deterministic | More stable (with seed) |
| New data | Cannot project | `transform()` works |
| Scalability | ~10K-100K points | Millions of points |
| Use beyond viz | No | Yes (general DR) |

### UMAP Hyperparameters

| Parameter | Effect | Default |
|-----------|--------|---------|
| `n_neighbors` | Local vs global balance (like perplexity) | 15 |
| `min_dist` | How tightly points pack in low-D | 0.1 |
| `n_components` | Output dimensions | 2 |
| `metric` | Distance function | 'euclidean' |

- **n_neighbors low (5):** Very local structure, fragmented
- **n_neighbors high (200):** More global structure, less detail
- **min_dist low (0.0):** Tight clumps, good for cluster separation
- **min_dist high (0.99):** Spread out, good for continuous structure

---

## Visualization Code

```python
from sklearn.manifold import TSNE
import umap
import matplotlib.pyplot as plt

# t-SNE
tsne = TSNE(n_components=2, perplexity=30, random_state=42, n_iter=1000)
X_tsne = tsne.fit_transform(X)  # Cannot transform new data!

# UMAP
reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=42)
X_umap = reducer.fit_transform(X)
# Can transform new data:
X_new_umap = reducer.transform(X_new)

# Plot comparison
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
ax1.scatter(X_tsne[:, 0], X_tsne[:, 1], c=labels, cmap='tab10', s=5)
ax1.set_title('t-SNE')
ax2.scatter(X_umap[:, 0], X_umap[:, 1], c=labels, cmap='tab10', s=5)
ax2.set_title('UMAP')
plt.show()
```

## When to Use Which

| Scenario | Choice |
|----------|--------|
| Publication-quality 2D plots (small data) | t-SNE |
| Exploratory visualization (large data) | UMAP |
| Need to embed new points | UMAP |
| Dimensionality reduction for ML pipeline | UMAP or PCA (NOT t-SNE) |
| Data < 10K points | Either works |
| Data > 100K points | UMAP only |

## Common Mistakes

1. **Interpreting cluster distances** in t-SNE — distances between clusters are meaningless
2. **Interpreting cluster sizes** — t-SNE can artificially expand/compress clusters
3. **Using t-SNE output for ML** — it's for visualization only, non-parametric
4. **Not trying multiple perplexity/n_neighbors values** — results are sensitive
5. **Running t-SNE on raw high-D data** — first reduce with PCA to 50-100 dims for speed

## Interview Questions

**Q1: Why can't you use t-SNE output as features for a classifier?**
t-SNE is non-parametric (no transform function), non-deterministic, doesn't preserve global distances, and optimizes only for visualization. The mapping is specific to the training set. UMAP can be used as preprocessing since it has `transform()`.

**Q2: What does perplexity control in t-SNE?**
Perplexity ≈ effective number of local neighbors. It controls the balance between local and global structure. Low perplexity focuses on very local neighborhoods; high perplexity considers broader structure. It's related to the bandwidth σᵢ of the Gaussian kernels.

**Q3: Why is UMAP faster than t-SNE?**
UMAP uses approximate nearest neighbor search (Annoy/NN-Descent) and stochastic gradient descent with negative sampling, achieving O(n) effective complexity vs t-SNE's O(n log n) with Barnes-Hut.

**Q4: How do you validate t-SNE/UMAP results?**
Try multiple hyperparameter settings — structures that persist across settings are real. Compare with known labels if available. Use trustworthiness/continuity metrics. Never make claims based on a single plot.

**Q5: t-SNE shows two well-separated blobs. Does this mean the data has two clusters?**
Not necessarily. t-SNE can split a single continuous cluster into multiple blobs (especially with low perplexity). Always validate with other methods (K-Means, silhouette) on original high-D data.
