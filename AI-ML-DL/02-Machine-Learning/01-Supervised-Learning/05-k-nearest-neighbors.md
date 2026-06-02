# K-Nearest Neighbors (KNN)

## Intuition

To classify a new point, find the K closest training points and take a majority vote. No model is learned — all computation happens at prediction time ("lazy learning").

```
Query point: ?

     ○  ○           K=3: 2 circles, 1 triangle → predict ○
       ○  ?         K=5: 3 circles, 2 triangles → predict ○
     △  △
       △

k=1: High variance     k=large: High bias (smoother)
```

## Algorithm

```
KNN_predict(x_query, K):
    1. Compute distance from x_query to ALL training points
    2. Sort and select K nearest neighbors
    3. Classification: majority vote (optionally weighted by 1/distance)
       Regression: mean (or weighted mean) of K neighbors' values
```

## Distance Metrics

```
Euclidean (L2):  d(x,z) = √(Σᵢ (xᵢ - zᵢ)²)       ← default, most common
Manhattan (L1):  d(x,z) = Σᵢ |xᵢ - zᵢ|              ← better for high-dim
Minkowski (Lp):  d(x,z) = (Σᵢ |xᵢ - zᵢ|ᵖ)^(1/p)   ← general form
Cosine:          d(x,z) = 1 - (x·z)/(||x||·||z||)   ← text/sparse data
```

**Choosing metrics:** Euclidean for low-dim continuous. Manhattan for high-dim or when features have different units. Cosine for text/sparse features.

## K Selection

```
K=1: Overfits (memorizes training data, noisy boundaries)
K=N: Underfits (always predicts majority class)
Rule of thumb: K = √n (n = number of training samples)
Always use odd K for binary classification (avoids ties)
Best: cross-validation
```

## Weighted KNN

Weight each neighbor's vote by inverse distance:
```
weight_i = 1 / d(x_query, x_i)

Closer neighbors have stronger influence.
Helps when K is large but nearby points should dominate.
```

## Curse of Dimensionality

In high dimensions:
1. All points become approximately equidistant
2. Nearest neighbor distance ≈ farthest neighbor distance
3. "Neighborhood" covers almost the entire space
4. Need exponentially more data: for density ρ in d dims, need n ~ ρ^d samples

**Rule:** KNN works well when d < 20. Beyond that, use dimensionality reduction first (PCA, UMAP).

## KD-Trees and Ball Trees

Brute force: O(n·d) per query. For large datasets:

| Structure | Build Time | Query Time | When to Use |
|-----------|-----------|------------|-------------|
| KD-Tree | O(n·log n) | O(log n) avg | d < 20 |
| Ball Tree | O(n·log n) | O(log n) avg | d > 20, metric spaces |
| Brute Force | O(1) | O(n·d) | Small n or very high d |

## From-Scratch Implementation

```python
import numpy as np
from collections import Counter

class KNN:
    def __init__(self, k=5, weighted=False):
        self.k = k
        self.weighted = weighted
    
    def fit(self, X, y):
        self.X_train = np.array(X)
        self.y_train = np.array(y)
    
    def _distances(self, x):
        return np.sqrt(np.sum((self.X_train - x)**2, axis=1))
    
    def predict(self, X):
        return np.array([self._predict_one(x) for x in X])
    
    def _predict_one(self, x):
        dists = self._distances(x)
        k_idx = np.argsort(dists)[:self.k]
        k_labels = self.y_train[k_idx]
        
        if self.weighted:
            k_dists = dists[k_idx]
            weights = 1 / (k_dists + 1e-8)
            # Weighted vote
            classes = np.unique(k_labels)
            weighted_votes = {c: np.sum(weights[k_labels == c]) for c in classes}
            return max(weighted_votes, key=weighted_votes.get)
        else:
            return Counter(k_labels).most_common(1)[0][0]
```

## Sklearn Usage

```python
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV

# MUST scale features (distance-based algorithm)
pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('knn', KNeighborsClassifier(n_neighbors=5, weights='distance'))
])

# Find optimal K
param_grid = {'knn__n_neighbors': range(1, 30, 2)}
grid = GridSearchCV(pipe, param_grid, cv=5, scoring='accuracy')
grid.fit(X_train, y_train)
print(f"Best K: {grid.best_params_['knn__n_neighbors']}")

# Use algorithm='auto' to let sklearn pick KD-tree vs Ball tree vs brute
```

## Hyperparameter Guide

| Parameter | Values to Try | Effect |
|-----------|---------------|--------|
| n_neighbors | [1, 3, 5, 7, 11, 15, 21] | Bias-variance trade-off |
| weights | uniform, distance | Whether closer points count more |
| metric | euclidean, manhattan, minkowski | Distance function |
| algorithm | auto, kd_tree, ball_tree, brute | Speed optimization |
| p (Minkowski) | [1, 2, 3] | L1, L2, L3 norm |

## When to Use / When NOT to Use

**Use when:**
- Small to medium datasets
- Low dimensionality (< 20 features)
- Non-linear decision boundaries needed without tuning
- Few training updates needed (just add points)
- Multi-class without extra effort

**Don't use when:**
- High-dimensional data (curse of dimensionality)
- Large datasets (slow prediction, O(n) per query)
- Features on different scales without preprocessing
- Imbalanced classes (majority class dominates votes)
- Need a compact model (KNN stores all training data)

## Common Mistakes

1. **Not scaling features** → distance dominated by large-scale features
2. **Even K for binary classification** → ties possible
3. **Using KNN on high-dim data without PCA** → distances become meaningless
4. **Ignoring class imbalance** → majority class always wins with large K
5. **Not considering prediction speed** → KNN is O(n) at inference, not suitable for low-latency production

## Interview Questions

**Q1: What's the time and space complexity of KNN?**
Training: O(1) (just stores data). Prediction: O(n·d) brute force, O(d·log n) with KD-tree. Space: O(n·d) — stores entire dataset. This makes it impractical for large datasets.

**Q2: How does the curse of dimensionality affect KNN?**
In high dims, distances converge: max_dist/min_dist → 1. The concept of "nearest" becomes meaningless. A "neighborhood" ball containing K points covers nearly the entire space, so local structure is lost.

**Q3: KNN vs Radius-based neighbors — when to use each?**
KNN: fixed K, works when density varies. Radius-NN: fixed radius, works when data has uniform density. KNN is more common since real data rarely has uniform density.

**Q4: How do you handle categorical features in KNN?**
Options: one-hot encode (increases dimensionality), use Hamming distance for categoricals, use Gower distance (mixed types), or use target encoding to convert to numeric.

**Q5: Can KNN be used for anomaly detection?**
Yes. Points whose K-nearest-neighbor distance is much larger than average are likely anomalies. The LOF (Local Outlier Factor) algorithm formalizes this idea using local density ratios.
