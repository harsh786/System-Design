# Data Preparation for Clustering

## Why This Matters

Unsupervised methods have **no labels to compensate for bad input**. In supervised learning, the model can learn to ignore irrelevant features. In clustering, every feature directly affects distance calculations. Garbage in = garbage out.

---

## Feature Scaling (CRITICAL)

### Why Scale?

Distance-based methods (K-Means, DBSCAN, Hierarchical, PCA) are dominated by features with larger numeric ranges.

```
Example: Age (20-70) vs Income (20000-200000)
Without scaling: Income dominates all distances
Euclidean distance ≈ income difference (age is negligible)
```

### Scaling Methods

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

# StandardScaler: z = (x - mean) / std → mean=0, std=1
# Best for: K-Means, PCA, GMM (assumes Gaussian-ish)
X_scaled = StandardScaler().fit_transform(X)

# MinMaxScaler: z = (x - min) / (max - min) → [0, 1]
# Best for: bounded algorithms, neural networks
X_scaled = MinMaxScaler().fit_transform(X)

# RobustScaler: z = (x - median) / IQR
# Best for: data with outliers (median/IQR are robust)
X_scaled = RobustScaler().fit_transform(X)
```

### Which Scaler to Use?

| Scaler | When to Use |
|--------|-------------|
| StandardScaler | Default choice, approximately normal data |
| RobustScaler | Data has outliers you want to keep |
| MinMaxScaler | Need bounded range, no strong outliers |
| No scaling | Tree-based methods only (Isolation Forest) |

---

## Handling Mixed Data Types

### The Problem

Most clustering algorithms use Euclidean distance — meaningless for categorical features.

### Gower Distance

Handles mixed types by computing per-feature distances and averaging:
- Numeric: |xᵢ - xⱼ| / range
- Categorical: 0 if same, 1 if different
- Binary: simple matching

```python
import gower

# Computes Gower distance matrix
distance_matrix = gower.gower_matrix(df)

# Use with algorithms that accept distance matrices:
from sklearn.cluster import AgglomerativeClustering
agg = AgglomerativeClustering(n_clusters=3, metric='precomputed', linkage='average')
labels = agg.fit_predict(distance_matrix)
```

### Other Approaches for Mixed Data

- **K-Prototypes:** Extension of K-Means for mixed types
- **One-hot encode categoricals + scale numerics** — simple but high-dimensional
- **Entity embeddings** — learn dense representations of categoricals (needs labels or autoencoder)

---

## Dimensionality Reduction BEFORE Clustering

### When to Reduce First

- **Curse of dimensionality:** > 50 features → distances become meaningless
- **Noise reduction:** Low-variance dimensions add noise to distance calculations
- **Speed:** K-Means on 500D is slow; on 20D is fast
- **Visualization:** Can't inspect clusters in > 3D

### How

```python
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans

# Reduce to retain 95% variance
pca = PCA(n_components=0.95)
X_reduced = pca.fit_transform(X_scaled)
print(f"Reduced: {X_scaled.shape[1]} → {X_reduced.shape[1]} dims")

# Then cluster
kmeans = KMeans(n_clusters=5).fit(X_reduced)
```

### When NOT to Reduce

- Few features (< 20) — clustering directly is fine
- All features are meaningful and you need interpretability
- You're using tree-based methods (Isolation Forest handles high-D natively)

---

## Evaluating Clusters Without Labels

### Internal Metrics

| Metric | Formula Intuition | Range | Better |
|--------|-------------------|-------|--------|
| Silhouette | (separation - cohesion) / max | [-1, 1] | Higher |
| Davies-Bouldin | avg(max cluster similarity) | [0, ∞) | Lower |
| Calinski-Harabasz | between-var / within-var | [0, ∞) | Higher |

```python
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score

sil = silhouette_score(X, labels)           # [-1, 1], higher better
db = davies_bouldin_score(X, labels)         # [0, ∞), lower better
ch = calinski_harabasz_score(X, labels)      # [0, ∞), higher better

print(f"Silhouette: {sil:.3f}")
print(f"Davies-Bouldin: {db:.3f}")
print(f"Calinski-Harabasz: {ch:.1f}")
```

### Per-Point Silhouette Analysis

```python
from sklearn.metrics import silhouette_samples
import numpy as np

sample_silhouettes = silhouette_samples(X, labels)

# Points with negative silhouette are likely misassigned
misassigned = np.where(sample_silhouettes < 0)[0]
print(f"{len(misassigned)} potentially misassigned points")
```

### Which Metric to Trust?

- **Silhouette:** Most general, works for any shape assumption
- **Calinski-Harabasz:** Favors convex, well-separated clusters (biased toward K-Means-like results)
- **Davies-Bouldin:** Good for comparing same algorithm with different K
- **Use multiple metrics** — if they agree, you have confidence

---

## Interpreting and Naming Clusters (Cluster Profiling)

After clustering, you need to **understand what each cluster represents**.

```python
import pandas as pd

# Add cluster labels to dataframe
df['cluster'] = labels

# Profile: compare cluster means to overall means
profile = df.groupby('cluster').mean()
overall = df.mean()

# Relative profile (how each cluster differs from average)
relative = (profile - overall) / overall * 100
print(relative.round(1))

# Example output:
#          age    income    purchases   recency
# cluster
# 0        +15%   +80%      +120%       -40%    → "High-value loyalists"
# 1        -20%   -30%      -50%        +200%   → "At-risk/churned"
# 2        +5%    -10%      +30%        -10%    → "Regular shoppers"
```

### Full Profiling Code

```python
def profile_clusters(df, labels, numeric_cols, categorical_cols=None):
    df = df.copy()
    df['cluster'] = labels
    
    # Numeric profiles
    print("=== Numeric Feature Means by Cluster ===")
    print(df.groupby('cluster')[numeric_cols].mean().round(2))
    print(f"\nOverall: {df[numeric_cols].mean().round(2).to_dict()}")
    
    # Cluster sizes
    print(f"\n=== Cluster Sizes ===")
    print(df['cluster'].value_counts().sort_index())
    
    # Categorical modes (if applicable)
    if categorical_cols:
        print("\n=== Categorical Modes by Cluster ===")
        for col in categorical_cols:
            print(f"\n{col}:")
            print(df.groupby('cluster')[col].apply(lambda x: x.mode()[0]))

profile_clusters(df, labels, ['age', 'income', 'purchases'], ['region'])
```

---

## Visualization Strategies for High-Dimensional Clusters

### Strategy 1: PCA Projection (Fast, Linear)

```python
pca = PCA(n_components=2)
X_2d = pca.fit_transform(X_scaled)
plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels, cmap='tab10', s=10)
plt.title(f"PCA (explains {pca.explained_variance_ratio_.sum():.0%} variance)")
```

### Strategy 2: UMAP Projection (Better Separation)

```python
import umap
X_2d = umap.UMAP(n_neighbors=15, random_state=42).fit_transform(X_scaled)
plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels, cmap='tab10', s=10)
```

### Strategy 3: Parallel Coordinates (See Feature Patterns)

```python
from pandas.plotting import parallel_coordinates
# Standardize for visual comparison
df_plot = pd.DataFrame(X_scaled, columns=feature_names)
df_plot['cluster'] = labels
parallel_coordinates(df_plot, 'cluster', colormap='tab10', alpha=0.3)
```

### Strategy 4: Radar/Spider Charts (Cluster Profiles)

```python
# Show mean feature values per cluster on a radar chart
# Good for comparing 5-10 features across clusters
```

---

## Complete Pipeline Example

```python
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np

# 1. Scale
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 2. Reduce (if high-dim)
if X_scaled.shape[1] > 50:
    pca = PCA(n_components=0.95)
    X_reduced = pca.fit_transform(X_scaled)
else:
    X_reduced = X_scaled

# 3. Find optimal K
scores = {}
for k in range(2, 11):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = km.fit_predict(X_reduced)
    scores[k] = silhouette_score(X_reduced, labels)

best_k = max(scores, key=scores.get)
print(f"Best K={best_k} (silhouette={scores[best_k]:.3f})")

# 4. Final clustering
km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
final_labels = km.fit_predict(X_reduced)

# 5. Profile and interpret
profile_clusters(df, final_labels, numeric_cols)
```

---

## Common Mistakes

1. **Clustering without scaling** — the #1 error in practice
2. **Using all features blindly** — irrelevant features add noise to distances
3. **Not profiling clusters** — clusters are useless if you can't explain them
4. **Over-relying on one metric** — use silhouette AND domain validation
5. **Forgetting to apply same transform to new data** — save scaler/PCA, use `transform()` not `fit_transform()`

## Interview Questions

**Q1: Why is feature scaling critical for K-Means but not for Random Forest?**
K-Means uses Euclidean distance directly — features with larger ranges dominate. Random Forest splits on individual features independently (scale-invariant). Any distance-based method needs scaling.

**Q2: You cluster customers and get 5 clusters. How do you validate they're meaningful?**
(a) Internal metrics (silhouette > 0.5 is good), (b) stability (subsample data, re-cluster — do you get similar groups?), (c) domain validation (do cluster profiles make business sense?), (d) actionability (can marketing do something different for each segment?).

**Q3: Should you always do PCA before clustering?**
No. PCA removes dimensions with low variance, but low-variance features might be important for separating clusters. Use PCA when: high-D data, speed matters, want noise reduction. Don't use when: few features, all features are domain-important, need interpretability.
