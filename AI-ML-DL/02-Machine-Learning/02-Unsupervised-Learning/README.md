# Unsupervised Learning - Complete Guide

## Overview

Unsupervised learning finds hidden patterns in data without labeled outputs. The goal is to model the underlying structure or distribution.

```
┌─────────────────────────────────────────────────────────┐
│              UNSUPERVISED LEARNING                        │
├───────────────┬───────────────┬──────────────┬──────────┤
│  Clustering   │ Dim Reduction │ Anomaly Det. │ Assoc.   │
├───────────────┼───────────────┼──────────────┼──────────┤
│ K-Means       │ PCA           │ Isolation F. │ Apriori  │
│ Hierarchical  │ t-SNE         │ One-Class SVM│ FP-Growth│
│ DBSCAN        │ UMAP          │ LOF          │          │
│ GMM           │ Autoencoders  │ DBSCAN       │          │
└───────────────┴───────────────┴──────────────┴──────────┘
```

---

## 1. K-Means Clustering

### Algorithm

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

### Objective Function

```
J = Σₖ Σ_{x∈Cₖ} ||x - μₖ||²    (Within-Cluster Sum of Squares)

K-Means minimizes this via coordinate descent:
- Fix μ, optimize assignments → Step 2a
- Fix assignments, optimize μ → Step 2b
```

### K-Means++ Initialization

```
1. Choose first centroid uniformly at random
2. For each remaining centroid:
   - Compute D(x) = distance to nearest existing centroid
   - Choose next centroid with probability ∝ D(x)²
   
This ensures centroids are spread out, giving O(log K)-competitive solution.
```

### Visualization of K-Means Steps

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

### Choosing K: The Elbow Method

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

Also use: Silhouette Score, Gap Statistic

### Python Implementation

```python
class KMeans:
    def __init__(self, k=3, max_iters=100):
        self.k = k
        self.max_iters = max_iters
    
    def fit(self, X):
        # K-Means++ initialization
        idx = np.random.randint(len(X))
        self.centroids = [X[idx]]
        
        for _ in range(1, self.k):
            dists = np.min([np.sum((X - c)**2, axis=1) for c in self.centroids], axis=0)
            probs = dists / dists.sum()
            idx = np.random.choice(len(X), p=probs)
            self.centroids.append(X[idx])
        
        self.centroids = np.array(self.centroids)
        
        for _ in range(self.max_iters):
            # Assign
            labels = self._assign(X)
            # Update
            new_centroids = np.array([X[labels == k].mean(axis=0) for k in range(self.k)])
            if np.allclose(self.centroids, new_centroids):
                break
            self.centroids = new_centroids
        
        self.labels_ = labels
        return self
    
    def _assign(self, X):
        dists = np.array([np.sum((X - c)**2, axis=1) for c in self.centroids])
        return np.argmin(dists, axis=0)
```

### Limitations
- Assumes spherical, equally-sized clusters
- Must specify K in advance
- Sensitive to initialization (mitigated by K-Means++)
- Sensitive to outliers (consider K-Medoids)
- Only finds convex clusters

---

## 2. Hierarchical Clustering

### Two Approaches

```
Agglomerative (Bottom-up):          Divisive (Top-down):
Start with n clusters (1 per point)  Start with 1 cluster (all points)
Merge closest pairs iteratively      Split clusters iteratively

     ┌───┬───┐                            ┌───────┐
     │ ┌─┼─┐ │                       ┌────┤       ├────┐
     │ │ │ │ │                       │    │       │    │
     ● ● ● ● ●                      ● ●  │       │  ● ● ●
                                           └───────┘
```

### Linkage Methods

```
Single Linkage:    min distance between any two points
Complete Linkage:  max distance between any two points
Average Linkage:   average distance between all pairs
Ward's Method:     minimizes increase in total WCSS

Single → elongated clusters (chaining effect)
Complete → compact, spherical clusters
Ward's → similar-sized clusters (most popular)
```

### Dendrogram

```
Height
  │
5 ┤         ┌───────────────┐
  │         │               │
4 ┤     ┌───┤           ┌───┤
  │     │   │           │   │
3 ┤  ┌──┤   │        ┌──┤   │
  │  │  │   │        │  │   │
2 ┤  │  │   │     ┌──┤  │   │
  │  │  │   │     │  │  │   │
1 ┤──┤  │   │     │  │  │   │
  │  │  │   │     │  │  │   │
  └──┴──┴───┴─────┴──┴──┴───┴──
     A  B   C     D  E  F   G

Cut at height 4 → 2 clusters: {A,B,C} and {D,E,F,G}
```

---

## 3. DBSCAN (Density-Based Spatial Clustering)

### Core Concepts

```
Parameters: ε (epsilon/radius), MinPts (minimum points)

Point Types:
- Core Point:    ≥ MinPts neighbors within ε radius
- Border Point:  < MinPts neighbors, but in ε-neighborhood of a core point
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

### Algorithm

```
DBSCAN(D, ε, MinPts):
    label = 0
    for each point P in D:
        if P is already classified: continue
        neighbors = range_query(P, ε)
        if |neighbors| < MinPts:
            mark P as Noise
        else:
            label += 1
            expand_cluster(P, neighbors, label, ε, MinPts)

expand_cluster(P, neighbors, label, ε, MinPts):
    assign P to cluster label
    for each Q in neighbors:
        if Q is Noise: assign Q to label (border point)
        if Q is unvisited:
            mark Q as visited
            Q_neighbors = range_query(Q, ε)
            if |Q_neighbors| ≥ MinPts:
                neighbors = neighbors ∪ Q_neighbors
            assign Q to cluster label
```

### Advantages over K-Means
- No need to specify K
- Finds arbitrarily shaped clusters
- Robust to outliers (marks them as noise)
- Only two parameters (ε, MinPts)

### Visualization

```
K-Means fails here:          DBSCAN succeeds:

   ○○○○○○○                    1111111
  ○○○  ·  ○○○               1111 · 1111
 ○○○ ·  · ○○○              111 ·  · 111
  ○○○  ·  ○○○               1111 · 1111
   ○○○○○○○                    1111111
                                        
       ×××                       2222
      ×××××                     22222
       ×××                       2222

K-Means: splits ring           DBSCAN: finds ring + cluster
into 2 wrong clusters          correctly + marks noise (·)
```

---

## 4. Principal Component Analysis (PCA)

### Goal
Find directions of maximum variance in data, project onto lower-dimensional subspace.

### Derivation

```
Given data matrix X (centered: mean=0), find direction w that maximizes variance:

Var(Xw) = wᵀ(XᵀX)w = wᵀΣw    where Σ = covariance matrix

maximize  wᵀΣw
subject to wᵀw = 1

Lagrangian: L = wᵀΣw - λ(wᵀw - 1)
∂L/∂w = 2Σw - 2λw = 0
→ Σw = λw

Solution: w is an eigenvector of Σ, λ is the eigenvalue
Maximum variance = largest eigenvalue
```

### Algorithm

```
PCA Algorithm:
1. Center data: X ← X - mean(X)
2. Compute covariance matrix: Σ = (1/n)XᵀX
3. Eigendecompose: Σ = VΛVᵀ  (or use SVD: X = UΣVᵀ)
4. Sort eigenvectors by eigenvalue (descending)
5. Select top k eigenvectors → projection matrix W
6. Transform: Z = XW  (n×k matrix)
```

### Variance Explained

```
% Variance explained by component i = λᵢ / Σⱼλⱼ

Cumulative Variance:
100%┤                    ─────────────
    │              ─────
 90%┤         ────
    │      ──
 80%┤    ─
    │  ─
 70%┤──
    └─────┬─────┬─────┬─────┬─────── Components
          1     2     3     4     5

Choose k where cumulative variance ≥ 95% (or elbow)
```

### Python
```python
class PCA:
    def __init__(self, n_components):
        self.n_components = n_components
    
    def fit_transform(self, X):
        # Center
        self.mean = X.mean(axis=0)
        X_centered = X - self.mean
        
        # Covariance and eigen
        cov = np.cov(X_centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        self.components = eigenvectors[:, idx[:self.n_components]]
        self.explained_variance = eigenvalues[idx[:self.n_components]]
        
        return X_centered @ self.components
```

---

## 5. t-SNE and UMAP

### t-SNE (t-distributed Stochastic Neighbor Embedding)

**Goal:** Preserve local structure when projecting to 2D/3D for visualization.

```
Key Idea:
1. In high-D: model pairwise similarities as Gaussian probabilities
   p_{j|i} = exp(-||xᵢ-xⱼ||²/2σᵢ²) / Σ_{k≠i} exp(-||xᵢ-xₖ||²/2σᵢ²)

2. In low-D: model pairwise similarities using Student-t distribution
   q_{ij} = (1 + ||yᵢ-yⱼ||²)⁻¹ / Σ_{k≠l} (1 + ||yₖ-yₗ||²)⁻¹

3. Minimize KL divergence: KL(P||Q) = Σᵢ Σⱼ pᵢⱼ log(pᵢⱼ/qᵢⱼ)
```

**Why Student-t in low-D?** Heavier tails allow moderate distances in high-D to map to larger distances in low-D, avoiding "crowding problem."

### UMAP (Uniform Manifold Approximation and Projection)

- Based on Riemannian geometry and algebraic topology
- Faster than t-SNE (O(n) vs O(n²))
- Better preserves global structure
- Can be used for general dimensionality reduction (not just visualization)

### t-SNE vs UMAP Comparison

| Feature | t-SNE | UMAP |
|---------|-------|------|
| Speed | O(n²) or O(n log n) | O(n) |
| Global structure | Poor | Better |
| Reproducibility | Non-deterministic | More stable |
| New data points | Cannot project | Can transform new data |
| Use case | Publication figures | Exploration + DR |

---

## 6. Gaussian Mixture Models (GMM)

### Model
Data is generated from a mixture of K Gaussian distributions:

```
P(x) = Σₖ πₖ · N(x | μₖ, Σₖ)

where πₖ = mixing coefficient (Σπₖ = 1)
      μₖ = mean of component k
      Σₖ = covariance of component k
```

### EM Algorithm (Expectation-Maximization)

```
E-Step: Compute responsibilities (soft assignments)
   γ(zₖ) = πₖ · N(xᵢ|μₖ,Σₖ) / Σⱼ πⱼ · N(xᵢ|μⱼ,Σⱼ)

M-Step: Update parameters using responsibilities
   Nₖ = Σᵢ γ(zₖ)ᵢ
   μₖ = (1/Nₖ) Σᵢ γ(zₖ)ᵢ · xᵢ
   Σₖ = (1/Nₖ) Σᵢ γ(zₖ)ᵢ · (xᵢ-μₖ)(xᵢ-μₖ)ᵀ
   πₖ = Nₖ / N
```

### GMM vs K-Means

```
K-Means (Hard):              GMM (Soft):
Point belongs to 1 cluster   Point has probability for each cluster

   ○○○○    ×××              P(A)=0.9  P(A)=0.6
   ○○○○    ×××              P(B)=0.1  P(B)=0.4
   ○○○○    ×××              
                            Handles overlapping, elliptical clusters
Hard boundary               Soft/probabilistic boundary
Spherical only              Any covariance structure
```

---

## 7. Association Rules (Apriori Algorithm)

### Key Metrics
```
Support(A):     P(A) = count(A)/total_transactions
Confidence(A→B): P(B|A) = support(A∪B) / support(A)  
Lift(A→B):      P(B|A) / P(B) = confidence(A→B) / support(B)

Lift > 1: positive correlation
Lift = 1: independent
Lift < 1: negative correlation
```

### Apriori Algorithm
```
1. Find all itemsets with support ≥ min_support (frequent itemsets)
   - Key insight: If {A,B} is infrequent, {A,B,C} must also be infrequent
   - Generate candidates of size k+1 from frequent itemsets of size k
2. Generate rules from frequent itemsets where confidence ≥ min_confidence
```

### Example
```
Transactions: {milk, bread}, {milk, bread, butter}, {bread, butter}, {milk, butter}

Frequent 1-itemsets (min_support=50%): milk(75%), bread(75%), butter(75%)
Frequent 2-itemsets: {milk,bread}(50%), {milk,butter}(50%), {bread,butter}(50%)

Rule: {milk} → {bread}, confidence = 50%/75% = 67%, lift = 67%/75% = 0.89
```

---

## 8. Anomaly Detection

### Methods

```
┌────────────────────┬────────────────────┬─────────────────────┐
│ Statistical        │ Distance-Based     │ Model-Based          │
├────────────────────┼────────────────────┼─────────────────────┤
│ Z-score (>3σ)      │ KNN distance       │ Isolation Forest     │
│ IQR method         │ LOF                │ One-Class SVM        │
│ Grubbs' test       │ DBSCAN (noise)     │ Autoencoders         │
└────────────────────┴────────────────────┴─────────────────────┘
```

### Isolation Forest

```
Key Insight: Anomalies are easier to isolate (fewer splits needed)

Normal point (many splits):     Anomaly (few splits):
        ┌─┐                          ┌─────────┐
      ┌─┤ ├─┐                        │    ×    │  ← isolated quickly!
    ┌─┤ └─┘ ├─┐                      └─────────┘
   ●  │     │  │                      
      └─────┘  │                     
               │
               
Anomaly score = average path length in isolation trees
Shorter path → more anomalous
```

### Python: Isolation Forest
```python
from sklearn.ensemble import IsolationForest

clf = IsolationForest(contamination=0.05, random_state=42)
predictions = clf.fit_predict(X)  # -1 for anomalies, 1 for normal
```

---

## Production Considerations

- **Clustering validation:** Use silhouette score, Davies-Bouldin index, or domain expertise
- **Scalability:** Mini-batch K-Means for large datasets, HDBSCAN over DBSCAN
- **Feature engineering matters:** Garbage in, garbage out
- **Monitoring:** Cluster drift detection in production
- **PCA for preprocessing:** Reduce noise and computation before downstream tasks

---

## Interview Questions

**Q: K-Means vs DBSCAN - when to use which?**
- K-Means: Know K, spherical clusters, large data (fast)
- DBSCAN: Unknown K, arbitrary shapes, want outlier detection

**Q: How do you choose K in K-Means?**
Elbow method, silhouette score, gap statistic, domain knowledge.

**Q: Can PCA be used for feature selection?**
No - PCA creates new features (linear combinations). For feature selection, use L1 regularization or mutual information.

**Q: What are the limitations of t-SNE?**
- Non-parametric (can't project new data)
- Stochastic (different runs give different results)
- Perplexity parameter sensitive
- Distances between clusters are not meaningful
- O(n²) complexity (Barnes-Hut: O(n log n))

**Q: GMM vs K-Means?**
GMM is a generalization of K-Means. K-Means is equivalent to GMM with identity covariance matrices and hard assignments.
