# DBSCAN (Density-Based Spatial Clustering of Applications with Noise)

## Intuition

Clusters are dense regions separated by sparse regions. Points in low-density regions are noise/outliers.

**Key insight:** Unlike K-Means, DBSCAN doesn't assume any cluster shape — it finds clusters of arbitrary geometry by following density-connected regions.

## Core Concepts

```
Parameters: ε (epsilon/radius), MinPts (minimum points)

Point Types:
- Core Point:    ≥ MinPts neighbors within ε radius
- Border Point:  < MinPts neighbors, but within ε of a core point
- Noise Point:   Neither core nor border

    ε radius
    ┌───╮
    │ · │  · ·    Core point (≥ MinPts=3 neighbors in ε)
    │ ●─┼──●──●
    │ · │  · ·    
    └───╯
         ·        Border point (near a core point)
    
              ×   Noise point (isolated)
```

## Algorithm

```
DBSCAN(D, ε, MinPts):
    label = 0
    for each unvisited point P:
        neighbors = points within ε of P
        if |neighbors| < MinPts:
            mark P as Noise (may later become Border)
        else:
            label += 1
            expand_cluster(P, neighbors, label)

expand_cluster(P, neighbors, label):
    assign P to cluster label
    queue = neighbors
    while queue not empty:
        Q = queue.pop()
        if Q is Noise: reassign to label (now Border)
        if Q already assigned: skip
        assign Q to label
        Q_neighbors = points within ε of Q
        if |Q_neighbors| ≥ MinPts:
            queue.add(Q_neighbors)  # Q is also Core
```

## Why DBSCAN Beats K-Means on Non-Convex Data

```
K-Means fails here:          DBSCAN succeeds:

   ○○○○○○○                    1111111
  ○○○  ·  ○○○               1111 × 1111     (× = noise)
 ○○○ ·  · ○○○              111 ×  × 111
  ○○○  ·  ○○○               1111 × 1111
   ○○○○○○○                    1111111
                                         
       ×××                       2222
      ×××××                     22222
       ×××                       2222

K-Means: splits ring into wrong clusters
DBSCAN: finds ring + blob + marks noise
```

## Choosing ε and MinPts

### k-Distance Graph (for ε)

```
1. For each point, compute distance to its k-th nearest neighbor (k = MinPts)
2. Sort distances ascending and plot
3. Find the "knee" — that's your ε

k-distance
    │          ╱
    │        ╱
    │      ╱   ← knee = optimal ε
    │   ──╱
    │──── 
    └───────────── points (sorted)
```

### MinPts Rule of Thumb

- MinPts ≥ dimensions + 1 (minimum)
- MinPts ≥ 2 × dimensions (recommended)
- Larger MinPts = smoother clusters, fewer noise points
- For 2D data: MinPts = 4 is common starting point

## Sklearn Code

```python
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import numpy as np
import matplotlib.pyplot as plt

# CRITICAL: Scale features first
X_scaled = StandardScaler().fit_transform(X)

# Determine eps using k-distance graph
k = 5  # MinPts
nn = NearestNeighbors(n_neighbors=k)
nn.fit(X_scaled)
distances, _ = nn.kneighbors(X_scaled)
k_distances = np.sort(distances[:, -1])

plt.plot(k_distances)
plt.xlabel('Points (sorted)')
plt.ylabel(f'{k}-distance')
plt.title('k-Distance Graph — find the knee')
plt.show()

# Run DBSCAN
db = DBSCAN(eps=0.5, min_samples=5)
labels = db.fit_predict(X_scaled)

n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = (labels == -1).sum()
print(f"Clusters: {n_clusters}, Noise points: {n_noise}")
```

## Advantages

- **No K needed** — discovers number of clusters automatically
- **Arbitrary shapes** — follows density, not geometry
- **Outlier detection built-in** — noise points are flagged
- **Few parameters** — just ε and MinPts
- **Deterministic** — for core points (border points may vary)

## Limitations

- **Varying density fails** — single ε can't handle clusters of different densities
- **High dimensions** — distance metrics degrade (curse of dimensionality)
- **Parameter sensitivity** — wrong ε gives all-noise or one-giant-cluster
- **Not scalable** — O(n²) without spatial index, O(n log n) with KD-tree
- **No predict()** — can't easily assign new points

## HDBSCAN: The Fix for Varying Density

HDBSCAN (Hierarchical DBSCAN) removes the ε parameter entirely:
- Builds a hierarchy over all density levels
- Extracts the most stable clusters automatically
- Handles varying-density clusters
- Only parameter: `min_cluster_size`

```python
import hdbscan

clusterer = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5)
labels = clusterer.fit_predict(X_scaled)
# Also provides: clusterer.probabilities_ (soft membership)
```

## Hyperparameter Guide

| Parameter | Effect of increasing |
|-----------|---------------------|
| `eps` | Larger clusters, fewer noise points, may merge distinct clusters |
| `min_samples` | Smoother clusters, more noise points, fewer clusters |

## Common Mistakes

1. **Not scaling features** — ε is distance-based; unscaled features make it meaningless
2. **Using default eps=0.5** without checking k-distance graph
3. **Expecting it to work on high-dim data** — reduce dimensions first
4. **Expecting equal-sized clusters** — DBSCAN finds natural density regions
5. **Comparing cluster labels across runs** — label numbers are arbitrary

## Interview Questions

**Q1: DBSCAN vs K-Means — when to use which?**
K-Means: know K, spherical clusters, large data (fast), need predict(). DBSCAN: unknown K, arbitrary shapes, want outlier detection, can afford O(n²).

**Q2: What happens if ε is too small? Too large?**
Too small: all points are noise (no core points). Too large: everything is one cluster. Use k-distance graph to find the sweet spot.

**Q3: Is DBSCAN deterministic?**
Core point assignments are deterministic. Border points may be assigned to different clusters depending on processing order (they're reachable from multiple cores). In practice, this rarely matters.

**Q4: How does DBSCAN handle varying-density clusters?**
It doesn't — a single ε value can't capture both dense and sparse clusters. Solution: HDBSCAN, which adapts to local density by considering all ε values hierarchically.

**Q5: Can DBSCAN be used for anomaly detection?**
Yes — noise points (label = -1) are natural anomaly candidates. Set MinPts and ε based on what "normal density" means in your domain. However, dedicated methods (Isolation Forest, LOF) are usually better for anomaly detection.
