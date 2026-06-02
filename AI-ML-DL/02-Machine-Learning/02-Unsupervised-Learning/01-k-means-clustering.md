# K-Means Clustering

## Intuition

K-Means partitions data into K groups by iteratively assigning points to the nearest centroid and updating centroids to be the mean of assigned points.

**Core idea:** Minimize the total distance between each point and its cluster center.

## Algorithm (Lloyd's Algorithm)

```
K-Means Algorithm:
─────────────────
1. Initialize K centroids (randomly or K-Means++)
2. Repeat until convergence:
   a. ASSIGN: Each point → nearest centroid
      cᵢ = argmin_k ||xᵢ - μₖ||²
   b. UPDATE: Each centroid → mean of assigned points
      μₖ = (1/|Cₖ|) Σ_{x∈Cₖ} x
3. Converged when assignments don't change
```

### Objective Function (WCSS)

```
J = Σₖ Σ_{x∈Cₖ} ||x - μₖ||²    (Within-Cluster Sum of Squares)

K-Means minimizes this via coordinate descent:
- Fix μ, optimize assignments → Step 2a
- Fix assignments, optimize μ → Step 2b

Guaranteed to converge (J decreases monotonically), but to LOCAL minimum.
```

## Visualization

```
Step 0 (Init):     Step 1 (Assign):    Step 2 (Update):    Converged:

  · · ·  · ·       ●·····  ▲···        ●····  ▲···        ●····  ▲···
  · · ·  · ·       ●·····  ▲···         ●···   ▲··         ●···   ▲··
  · · ·  ·         ●·····  ▲·           ●···   ▲·          ●···   ▲·
  ●                ■····               ■···               ■···
  · · ▲  ·         ■····               ■···               ■···
  · ·    ■         ■····                ■··                ■··

● ▲ ■ = centroids    · = data points assigned to nearest centroid
```

## K-Means++ Initialization

```
1. Choose first centroid uniformly at random
2. For each remaining centroid:
   - Compute D(x) = distance to nearest existing centroid
   - Choose next centroid with probability ∝ D(x)²

This ensures centroids are spread out, giving O(log K)-competitive solution.
```

**Why it matters:** Random init can lead to poor local minima. K-Means++ gives much better starting point.

## Choosing K

### Elbow Method

```
WCSS
  │╲
  │ ╲
  │  ╲
  │   ╲___
  │       ╲_____  ← Elbow (optimal K)
  │              ────────────
  └────────────────────────── K
  1  2  3  4  5  6  7  8  9
```

### Silhouette Score

For each point i:
- a(i) = average distance to points in same cluster
- b(i) = average distance to points in nearest other cluster
- s(i) = (b(i) - a(i)) / max(a(i), b(i))

Range: [-1, 1]. Higher = better separated clusters.

### Gap Statistic

Compare log(WCSS) to expected log(WCSS) under uniform null distribution. Choose K where gap is largest.

## From-Scratch Implementation

```python
import numpy as np

class KMeans:
    def __init__(self, k=3, max_iters=100, n_init=10):
        self.k = k
        self.max_iters = max_iters
        self.n_init = n_init

    def _kmeans_plus_plus(self, X):
        centroids = [X[np.random.randint(len(X))]]
        for _ in range(1, self.k):
            distances = np.min([np.sum((X - c)**2, axis=1) for c in centroids], axis=0)
            probs = distances / distances.sum()
            centroids.append(X[np.random.choice(len(X), p=probs)])
        return np.array(centroids)

    def fit(self, X):
        best_inertia = float('inf')
        for _ in range(self.n_init):
            centroids = self._kmeans_plus_plus(X)
            for _ in range(self.max_iters):
                # Assign
                distances = np.array([np.sum((X - c)**2, axis=1) for c in centroids])
                labels = np.argmin(distances, axis=0)
                # Update
                new_centroids = np.array([X[labels == i].mean(axis=0) for i in range(self.k)])
                if np.allclose(centroids, new_centroids):
                    break
                centroids = new_centroids
            inertia = sum(np.sum((X[labels == i] - centroids[i])**2) for i in range(self.k))
            if inertia < best_inertia:
                best_inertia = inertia
                self.centroids_ = centroids
                self.labels_ = labels
        self.inertia_ = best_inertia
        return self

    def predict(self, X):
        distances = np.array([np.sum((X - c)**2, axis=1) for c in self.centroids_])
        return np.argmin(distances, axis=0)
```

## Sklearn Code

```python
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics import silhouette_score

# Standard K-Means
kmeans = KMeans(n_clusters=5, init='k-means++', n_init=10, random_state=42)
labels = kmeans.fit_predict(X)

# Elbow method
inertias = []
for k in range(1, 11):
    km = KMeans(n_clusters=k, random_state=42).fit(X)
    inertias.append(km.inertia_)

# Silhouette analysis
for k in range(2, 11):
    km = KMeans(n_clusters=k, random_state=42).fit(X)
    score = silhouette_score(X, km.labels_)
    print(f"K={k}: silhouette={score:.3f}")

# Mini-Batch K-Means for large data (>100K samples)
mbk = MiniBatchKMeans(n_clusters=5, batch_size=1024, random_state=42)
labels = mbk.fit_predict(X_large)
```

## Mini-Batch K-Means

For datasets too large to fit in memory or when speed is critical:
- Randomly samples a batch each iteration
- Updates centroids using only the batch
- Much faster, slightly worse inertia (~1% worse)
- Use when n > 100K

## Hyperparameter Guide

| Parameter | Default | Guidance |
|-----------|---------|----------|
| `n_clusters` | 8 | Use elbow/silhouette to determine |
| `init` | 'k-means++' | Always use k-means++ |
| `n_init` | 10 | More = more robust, slower |
| `max_iter` | 300 | Increase if not converging |

## Limitations

- **Spherical clusters only** — uses Euclidean distance, assumes equal-radius clusters
- **Must specify K** in advance
- **Sensitive to outliers** — mean is pulled toward outliers (use K-Medoids)
- **Only convex clusters** — cannot find ring/crescent shapes
- **Feature scale dependent** — MUST standardize features first

## When to Use / Not Use

**Use K-Means when:**
- You know (or can estimate) K
- Clusters are roughly spherical and similar size
- Dataset is large (scales well: O(nKd) per iteration)
- You need a fast baseline

**Don't use when:**
- Clusters are non-convex (use DBSCAN)
- Clusters have very different sizes/densities (use GMM)
- You don't know K and can't estimate it (use DBSCAN/hierarchical)
- Data has many outliers (use K-Medoids or DBSCAN)

## Common Mistakes

1. **Not scaling features** — K-Means uses Euclidean distance; unscaled features dominate
2. **Ignoring n_init** — single run may find bad local minimum
3. **Using K-Means on categorical data** — use K-Modes instead
4. **Interpreting WCSS as "goodness"** — always decreases with K, use relative methods
5. **Assuming clusters found are "real"** — K-Means ALWAYS finds K clusters, even in random data

## Interview Questions

**Q1: Why does K-Means always converge?**
Because WCSS decreases (or stays same) at each step. It's bounded below by 0. Monotone bounded sequences converge. But convergence is to LOCAL minimum.

**Q2: K-Means vs K-Medoids — when to use which?**
K-Medoids uses actual data points as centers (medoids) and minimizes sum of distances (not squared). More robust to outliers. Use when: outliers present, need interpretable centers, or using non-Euclidean distances. Downside: O(n²) complexity.

**Q3: What happens if a cluster becomes empty during K-Means?**
Options: (a) reinitialize that centroid randomly, (b) assign it the farthest point from its nearest centroid, (c) reduce K by 1. Sklearn handles this automatically.

**Q4: Can K-Means handle high-dimensional data?**
Technically yes, but distance metrics become less meaningful in high dimensions (curse of dimensionality). Best practice: run PCA first to reduce to meaningful dimensions, then cluster.

**Q5: Prove that K-Means is equivalent to EM on a restricted GMM.**
K-Means = GMM with isotropic equal covariance (Σₖ = σ²I), equal priors (πₖ = 1/K), and hard assignments (σ² → 0 makes responsibilities become 0/1). The M-step becomes centroid = mean of assigned points.
