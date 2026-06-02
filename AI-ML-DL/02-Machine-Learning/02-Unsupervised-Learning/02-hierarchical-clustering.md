# Hierarchical Clustering

## Intuition

Builds a tree (dendrogram) of clusters by either merging small clusters bottom-up (agglomerative) or splitting large clusters top-down (divisive). You choose the number of clusters by "cutting" the tree at a height.

**Key advantage:** Don't need to specify K upfront — explore the full hierarchy.

## Two Approaches

```
Agglomerative (Bottom-up):          Divisive (Top-down):
Start with n clusters (1 per point)  Start with 1 cluster (all points)
Merge closest pairs iteratively      Split clusters iteratively

     ┌───┬───┐                            ┌───────┐
     │ ┌─┼─┐ │                       ┌────┤       ├────┐
     │ │ │ │ │                       │    │       │    │
     ● ● ● ● ●                      ● ●  │       │  ● ● ●
                                           └───────┘

Agglomerative is far more common (O(n²) vs O(2ⁿ) for divisive).
```

## Linkage Methods

```
┌──────────────────┬────────────────────────────────────────────────┐
│ Linkage          │ Distance between clusters A and B               │
├──────────────────┼────────────────────────────────────────────────┤
│ Single           │ min d(a,b) for a∈A, b∈B                        │
│ Complete         │ max d(a,b) for a∈A, b∈B                        │
│ Average (UPGMA)  │ mean d(a,b) for all a∈A, b∈B                   │
│ Ward's           │ Increase in total WCSS after merge              │
└──────────────────┴────────────────────────────────────────────────┘

Behavior:
- Single   → elongated clusters (chaining effect) — sensitive to noise
- Complete → compact, spherical clusters — sensitive to outliers
- Average  → compromise between single and complete
- Ward's   → similar-sized, compact clusters — MOST POPULAR
```

## Dendrogram

```
Height
  │
5 ┤         ┌───────────────┐
  │         │               │
4 ┤     ┌───┤           ┌───┤          ← Cut here → 2 clusters
  │     │   │           │   │
3 ┤  ┌──┤   │        ┌──┤   │
  │  │  │   │        │  │   │
2 ┤  │  │   │     ┌──┤  │   │
  │  │  │   │     │  │  │   │
1 ┤──┤  │   │     │  │  │   │
  │  │  │   │     │  │  │   │
  └──┴──┴───┴─────┴──┴──┴───┴──
     A  B   C     D  E  F   G

Reading: Height = distance at which clusters merge.
Tall bars = well-separated clusters. Cut where bars are tallest.
```

## How to Cut the Dendrogram

1. **Fixed K:** Cut to get exactly K clusters
2. **Distance threshold:** Cut at a specific height
3. **Inconsistency:** Cut where merge distance suddenly jumps (largest gap)

## From-Scratch Implementation

```python
import numpy as np

class AgglomerativeClustering:
    def __init__(self, n_clusters=3, linkage='ward'):
        self.n_clusters = n_clusters
        self.linkage = linkage

    def fit(self, X):
        n = len(X)
        clusters = {i: [i] for i in range(n)}
        dist_matrix = np.sqrt(((X[:, None] - X[None, :])**2).sum(axis=2))
        np.fill_diagonal(dist_matrix, np.inf)
        self.merge_history = []

        while len(clusters) > self.n_clusters:
            active = list(clusters.keys())
            min_dist, merge_pair = np.inf, None
            for i, ci in enumerate(active):
                for cj in active[i+1:]:
                    d = self._linkage_dist(clusters[ci], clusters[cj], dist_matrix)
                    if d < min_dist:
                        min_dist, merge_pair = d, (ci, cj)
            ci, cj = merge_pair
            new_id = max(clusters.keys()) + 1
            clusters[new_id] = clusters.pop(ci) + clusters.pop(cj)
            self.merge_history.append((ci, cj, min_dist))

        self.labels_ = np.zeros(n, dtype=int)
        for label, members in enumerate(clusters.values()):
            for idx in members:
                self.labels_[idx] = label
        return self

    def _linkage_dist(self, c1, c2, D):
        dists = D[np.ix_(c1, c2)]
        if self.linkage == 'single': return dists.min()
        elif self.linkage == 'complete': return dists.max()
        elif self.linkage == 'average': return dists.mean()
        elif self.linkage == 'ward':
            # Simplified: use average as proxy
            return dists.mean()
```

## Scipy Code

```python
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from sklearn.cluster import AgglomerativeClustering
import matplotlib.pyplot as plt

# Build linkage matrix
Z = linkage(X, method='ward', metric='euclidean')

# Plot dendrogram
plt.figure(figsize=(10, 5))
dendrogram(Z, truncate_mode='level', p=5)
plt.xlabel('Sample index')
plt.ylabel('Distance')
plt.title('Dendrogram')
plt.show()

# Cut at K clusters
labels = fcluster(Z, t=3, criterion='maxclust')

# Or use sklearn
agg = AgglomerativeClustering(n_clusters=3, linkage='ward')
labels = agg.fit_predict(X)
```

## Hyperparameter Guide

| Parameter | Guidance |
|-----------|----------|
| `n_clusters` | Inspect dendrogram for natural cuts |
| `linkage` | Ward (default, best general), Complete (compact), Single (avoid unless chain-like) |
| `metric` | Euclidean (default). Ward REQUIRES Euclidean. |

## When to Use

- **Don't know K** — explore dendrogram to discover natural groupings
- **Need hierarchy** — taxonomy, organizational structure, phylogenetics
- **Small-medium data** — O(n²) memory, O(n³) time (or O(n² log n) with efficient implementations)
- **Want deterministic results** — no randomness (unlike K-Means)

## When NOT to Use

- **Large datasets** (n > 10K) — doesn't scale
- **Need to predict new points** — no `predict()` method (must refit)
- **High dimensions** — distance metrics degrade

## Common Mistakes

1. **Using single linkage** without understanding chaining effect
2. **Not scaling features** — same issue as K-Means
3. **Trying on large data** — O(n²) memory will kill you at n > 50K
4. **Using Ward with non-Euclidean distance** — Ward assumes Euclidean

## Interview Questions

**Q1: When would you use hierarchical clustering over K-Means?**
When you don't know K, need to explore cluster structure at multiple granularities, want a deterministic result, or the problem has natural hierarchy (e.g., biological taxonomy).

**Q2: Explain the chaining effect in single linkage.**
Single linkage merges clusters based on their closest points. A chain of intermediate points can bridge two otherwise distinct clusters, causing them to merge prematurely. This produces elongated, unnatural clusters.

**Q3: How do you decide where to cut the dendrogram?**
Look for the largest vertical gap (biggest jump in merge distance). This indicates well-separated clusters. Also: domain knowledge, silhouette scores at different cuts, or inconsistency coefficient.

**Q4: What is Ward's linkage optimizing?**
Ward minimizes the increase in total within-cluster variance (WCSS) at each merge. It's equivalent to choosing the merge that least increases the K-Means objective. This tends to produce compact, similarly-sized clusters.

**Q5: Can hierarchical clustering handle non-spherical clusters?**
With single linkage, yes — it can find elongated/arbitrary shapes (but with chaining risk). With Ward/complete, no — they prefer compact spherical clusters. For arbitrary shapes, DBSCAN is better.
