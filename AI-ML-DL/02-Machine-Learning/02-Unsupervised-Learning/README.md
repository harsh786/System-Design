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

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** You run K-Means with K=3 on a dataset and get different results each time. Why does this happen and how do you fix it?
**Hint:** Think about the initialization step.

<details><summary>Solution</summary>

K-Means uses random initialization of centroids. Different starting positions can converge to different local minima of the objective function.

Fixes:
1. **K-Means++:** Smart initialization that spreads centroids apart
2. **Multiple restarts:** Run K-Means n times (e.g., n=10), pick the result with lowest inertia (within-cluster sum of squares)
3. sklearn's default: `n_init=10` already does multiple restarts

</details>

### Exercise 2 (Beginner)
**Problem:** How do you choose the number of clusters K for K-Means?
**Hint:** There are visual and quantitative methods.

<details><summary>Solution</summary>

1. **Elbow Method:** Plot inertia vs K. Look for the "elbow" where adding more clusters gives diminishing returns.
2. **Silhouette Score:** Measures how similar a point is to its own cluster vs nearest cluster. Range [-1, 1], higher is better.
3. **Gap Statistic:** Compares inertia to that expected under null reference distribution.
4. **Domain knowledge:** Sometimes K is given by the problem (e.g., customer segments).

</details>

### Exercise 3 (Beginner)
**Problem:** Explain why K-Means struggles with clusters of different sizes, densities, or non-spherical shapes.
**Hint:** Think about what the algorithm optimizes.

<details><summary>Solution</summary>

K-Means minimizes within-cluster sum of squares, which implicitly assumes:
- Clusters are spherical (uses Euclidean distance from centroid)
- Clusters are similar in size (assigns roughly equal points)
- Clusters have similar density

For non-spherical: Use DBSCAN or spectral clustering
For different sizes/densities: Use GMM or DBSCAN
For varying densities: Use HDBSCAN

</details>

### Exercise 4 (Intermediate)
**Problem:** Explain PCA as both a variance maximization problem and a reconstruction error minimization problem. Show they're equivalent.
**Hint:** Consider what the projection matrix does.

<details><summary>Solution</summary>

**Variance maximization:** Find direction w that maximizes variance of projected data:
max wᵀΣw subject to ||w||=1
Solution: w = eigenvector of Σ with largest eigenvalue.

**Reconstruction minimization:** Find w that minimizes ||x - (xᵀw)w||²
= ||x||² - (xᵀw)² = const - wᵀΣw

Minimizing reconstruction error = maximizing wᵀΣw = maximizing projected variance.

They're equivalent! Both solved by top eigenvectors of covariance matrix Σ.

</details>

### Exercise 5 (Intermediate)
**Problem:** DBSCAN has parameters ε (epsilon) and MinPts. A user sets ε=0.001 and gets all points labeled as noise. Another sets ε=100 and gets one giant cluster. How do you choose ε properly?
**Hint:** Consider the k-distance graph.

<details><summary>Solution</summary>

**k-distance graph method:**
1. For each point, compute distance to its k-th nearest neighbor (k=MinPts)
2. Sort these distances in ascending order
3. Plot them — look for the "knee" point
4. The knee corresponds to optimal ε

**Intuition:** Points within clusters have small k-distances. The knee separates cluster points from noise points.

Also consider:
- Domain knowledge about expected cluster separation
- MinPts ≥ dimensions + 1 (rule of thumb: 2*dimensions)
- Scale features first (DBSCAN is sensitive to feature scales)

</details>

### Exercise 6 (Intermediate)
**Problem:** Compare t-SNE and UMAP for dimensionality reduction. When would you use each?
**Hint:** Consider computational cost, global structure preservation, and use cases.

<details><summary>Solution</summary>

| Aspect | t-SNE | UMAP |
|--------|-------|------|
| Speed | Slow O(n²) | Faster O(n log n) |
| Global structure | Poor (distances between clusters meaningless) | Better preserved |
| Reproducibility | Stochastic, varies between runs | More stable |
| New data | Cannot embed new points | Can transform new data |
| Hyperparameters | perplexity | n_neighbors, min_dist |

Use t-SNE: Visualization of small-medium datasets, when local structure matters most
Use UMAP: Larger datasets, when you need speed, when global structure matters, when you need to embed new points

Neither is for downstream ML — use PCA for that.

</details>

### Exercise 7 (Intermediate)
**Problem:** Gaussian Mixture Models use the EM algorithm. Explain the E-step and M-step intuitively and mathematically.
**Hint:** E = assign responsibilities, M = update parameters.

<details><summary>Solution</summary>

**E-step (Expectation):** Compute "soft assignments" — probability each point belongs to each cluster:
γ(zₙₖ) = P(zₙ=k|xₙ) = [πₖ·N(xₙ|μₖ,Σₖ)] / [Σⱼ πⱼ·N(xₙ|μⱼ,Σⱼ)]

Intuition: "Given current parameters, how likely is each point to belong to each Gaussian?"

**M-step (Maximization):** Update parameters using weighted data:
- Nₖ = Σₙ γ(zₙₖ) (effective number of points in cluster k)
- μₖ = (1/Nₖ) Σₙ γ(zₙₖ)·xₙ (weighted mean)
- Σₖ = (1/Nₖ) Σₙ γ(zₙₖ)·(xₙ-μₖ)(xₙ-μₖ)ᵀ (weighted covariance)
- πₖ = Nₖ/N (mixing coefficient)

Intuition: "Given assignments, what parameters best explain the data?"

EM is guaranteed to increase (or maintain) the log-likelihood each iteration.

</details>

### Exercise 8 (Advanced)
**Problem:** Prove that K-Means is a special case of GMM with specific assumptions.
**Hint:** What happens when covariance matrices are spherical and variance approaches zero?

<details><summary>Solution</summary>

GMM with constraints:
1. All Σₖ = σ²I (spherical, equal covariance)
2. Equal mixing coefficients: πₖ = 1/K

As σ² → 0, the soft assignments γ(zₙₖ) become hard assignments (0 or 1):
- γ(zₙₖ) → 1 for nearest centroid, 0 otherwise
- This is exactly K-Means assignment step

The M-step becomes: μₖ = mean of assigned points = K-Means update step

Therefore K-Means = GMM with:
- Isotropic equal covariance
- Hard (argmax) assignments
- Equal priors

K-Means is "hard EM" on a restricted GMM.

</details>

### Exercise 9 (Advanced)
**Problem:** Implement the Isolation Forest intuition. Why do anomalies have shorter path lengths in random trees?
**Hint:** Think about how random splits partition space.

<details><summary>Solution</summary>

**Intuition:** Anomalies are "few and different" — they exist in sparse regions.

Random splitting process:
1. Pick a random feature
2. Pick a random split value between min and max of that feature
3. Repeat recursively

Anomalies are isolated quickly because:
- They're in low-density regions → fewer points share their subspace
- Random splits easily separate them from the majority
- Normal points are in dense clusters → need many splits to isolate one point

Path length h(x):
- Anomaly: short path (isolated in few splits)
- Normal: long path (needs many splits to separate from cluster)

Anomaly score: s(x) = 2^(-E[h(x)]/c(n)) where c(n) is average path length in BST
- s → 1: anomaly
- s → 0.5: normal
- s → 0: very dense (not anomaly)

</details>

### Exercise 10 (Advanced)
**Problem:** Explain the spectral clustering algorithm. Why does it work better than K-Means for non-convex clusters?
**Hint:** Think about graph Laplacian and its eigenvectors.

<details><summary>Solution</summary>

**Algorithm:**
1. Build similarity graph (k-NN or ε-neighborhood)
2. Compute graph Laplacian: L = D - W (D=degree matrix, W=adjacency/similarity)
3. Find bottom k eigenvectors of L (or normalized Laplacian)
4. Stack eigenvectors as columns → new representation
5. Run K-Means on this new representation

**Why it works for non-convex clusters:**
- The eigenvectors of L encode graph connectivity
- Points in the same connected component get similar eigenvector values
- Even if clusters are interleaved in original space, they're separated in spectral space
- K-Means on spectral embedding finds graph-based clusters, not geometric ones

**Intuition:** It's like finding natural "cuts" in a graph that minimize edges cut while balancing cluster sizes (normalized cut).

</details>

---

## Self-Assessment Quiz

**1. K-Means converges when:**
- A) All points are equidistant from centroids
- B) Cluster assignments don't change between iterations
- C) The number of iterations reaches 100
- D) Centroids reach the dataset boundary

<details><summary>Answer</summary>B) Cluster assignments don't change (or equivalently, centroids stop moving)</details>

**2. PCA finds components that are:**
- A) Statistically independent
- B) Orthogonal and maximize variance
- C) Minimum distance to data points
- D) Non-linear combinations of features

<details><summary>Answer</summary>B) Orthogonal (uncorrelated) and ordered by variance explained</details>

**3. DBSCAN's main advantage over K-Means is:**
- A) Always faster
- B) Doesn't need to specify K and finds arbitrary-shaped clusters
- C) Works better in high dimensions
- D) Always produces better clusters

<details><summary>Answer</summary>B) No need to specify K, handles arbitrary shapes, identifies noise points</details>

**4. The silhouette score ranges from:**
- A) [0, 1]
- B) [-1, 1]
- C) [0, ∞)
- D) (-∞, ∞)

<details><summary>Answer</summary>B) [-1, 1] where 1=perfect clustering, 0=overlapping, -1=wrong cluster</details>

**5. In PCA, the first component explains:**
- A) 50% of variance always
- B) The maximum possible variance in one direction
- C) Equal variance as other components
- D) The minimum variance direction

<details><summary>Answer</summary>B) The maximum possible variance among all unit vectors</details>

**6. GMM differs from K-Means in that:**
- A) It uses hard assignments only
- B) It assigns probabilities (soft clustering) and models cluster shape
- C) It always converges to the global optimum
- D) It doesn't use centroids

<details><summary>Answer</summary>B) Soft probabilistic assignments and models full covariance (shape/orientation)</details>

**7. t-SNE is NOT suitable for:**
- A) Visualization
- B) Exploring cluster structure
- C) Preserving local neighborhoods
- D) Measuring distances between clusters

<details><summary>Answer</summary>D) Global distances/between-cluster distances are not meaningful in t-SNE</details>

**8. DBSCAN classifies a point as a core point when:**
- A) It's at the center of the dataset
- B) It has at least MinPts neighbors within ε radius
- C) It's the closest to a centroid
- D) It has the highest density in the dataset

<details><summary>Answer</summary>B) At least MinPts points (including itself) within its ε-neighborhood</details>

**9. Hierarchical clustering with single linkage tends to produce:**
- A) Compact spherical clusters
- B) Chain-like clusters (chaining effect)
- C) Equal-sized clusters
- D) Only two clusters

<details><summary>Answer</summary>B) Chain-like clusters due to the chaining effect (single link = min distance)</details>

**10. How many principal components are needed to perfectly reconstruct the data?**
- A) 2
- B) As many as the number of samples
- C) As many as the original features (or rank of data matrix)
- D) It's impossible to perfectly reconstruct

<details><summary>Answer</summary>C) min(n_features, n_samples) = rank of data matrix gives perfect reconstruction</details>

---

## Coding Challenges

### Challenge 1: Implement K-Means from Scratch
```python
"""
Implement K-Means with K-Means++ initialization.
Include: fit, predict, inertia calculation.
"""
import numpy as np

class KMeansScratch:
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
                self.centroids = centroids
                self.labels_ = labels
        self.inertia_ = best_inertia
        return self
```

### Challenge 2: Implement PCA from Scratch
```python
"""
Implement PCA using eigendecomposition.
Include: fit, transform, explained_variance_ratio, inverse_transform.
"""
import numpy as np

class PCAScratch:
    def __init__(self, n_components=2):
        self.n_components = n_components
    
    def fit(self, X):
        self.mean_ = X.mean(axis=0)
        X_centered = X - self.mean_
        
        # Covariance matrix
        cov_matrix = np.cov(X_centered, rowvar=False)
        
        # Eigendecomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # Sort by descending eigenvalue
        idx = np.argsort(eigenvalues)[::-1]
        self.eigenvalues_ = eigenvalues[idx]
        self.components_ = eigenvectors[:, idx[:self.n_components]].T
        
        self.explained_variance_ratio_ = self.eigenvalues_[:self.n_components] / self.eigenvalues_.sum()
        return self
    
    def transform(self, X):
        return (X - self.mean_) @ self.components_.T
    
    def inverse_transform(self, X_transformed):
        return X_transformed @ self.components_ + self.mean_
```

### Challenge 3: Implement DBSCAN from Scratch
```python
"""
Implement DBSCAN clustering algorithm.
Must correctly identify core, border, and noise points.
"""
import numpy as np

class DBSCANScratch:
    def __init__(self, eps=0.5, min_samples=5):
        self.eps = eps
        self.min_samples = min_samples
    
    def fit(self, X):
        n = len(X)
        self.labels_ = np.full(n, -1)  # -1 = noise
        cluster_id = 0
        
        for i in range(n):
            if self.labels_[i] != -1:
                continue
            neighbors = self._region_query(X, i)
            if len(neighbors) < self.min_samples:
                continue  # noise (may become border later)
            # Expand cluster
            self.labels_[i] = cluster_id
            seed_set = list(neighbors - {i})
            j = 0
            while j < len(seed_set):
                q = seed_set[j]
                if self.labels_[q] == -1:
                    self.labels_[q] = cluster_id  # border point
                if self.labels_[q] != -1:
                    j += 1
                    continue
                self.labels_[q] = cluster_id
                q_neighbors = self._region_query(X, q)
                if len(q_neighbors) >= self.min_samples:
                    seed_set.extend(q_neighbors - set(seed_set) - {q})
                j += 1
            cluster_id += 1
        return self
    
    def _region_query(self, X, idx):
        distances = np.sqrt(np.sum((X - X[idx])**2, axis=1))
        return set(np.where(distances <= self.eps)[0])
```

### Challenge 4: Implement Agglomerative Hierarchical Clustering
```python
"""
Implement agglomerative clustering with single, complete, and average linkage.
Build the dendrogram merge history.
"""
import numpy as np

class AgglomerativeScratch:
    def __init__(self, n_clusters=3, linkage='single'):
        self.n_clusters = n_clusters
        self.linkage = linkage
    
    def fit(self, X):
        n = len(X)
        clusters = {i: [i] for i in range(n)}
        self.merge_history = []
        
        # Distance matrix
        dist_matrix = np.sqrt(((X[:, None] - X[None, :])**2).sum(axis=2))
        np.fill_diagonal(dist_matrix, np.inf)
        
        while len(clusters) > self.n_clusters:
            # Find closest pair
            active = list(clusters.keys())
            min_dist = np.inf
            merge_pair = None
            for i, ci in enumerate(active):
                for j, cj in enumerate(active[i+1:], i+1):
                    d = self._linkage_distance(clusters[ci], clusters[cj], dist_matrix)
                    if d < min_dist:
                        min_dist = d
                        merge_pair = (ci, cj)
            # Merge
            ci, cj = merge_pair
            new_id = max(clusters.keys()) + 1
            clusters[new_id] = clusters.pop(ci) + clusters.pop(cj)
            self.merge_history.append((ci, cj, min_dist))
        
        # Assign labels
        self.labels_ = np.zeros(n, dtype=int)
        for label, (_, members) in enumerate(clusters.items()):
            for idx in members:
                self.labels_[idx] = label
        return self
    
    def _linkage_distance(self, c1, c2, dist_matrix):
        dists = dist_matrix[np.ix_(c1, c2)]
        if self.linkage == 'single':
            return dists.min()
        elif self.linkage == 'complete':
            return dists.max()
        elif self.linkage == 'average':
            return dists.mean()
```

### Challenge 5: Implement Gaussian Mixture Model with EM
```python
"""
Implement GMM with the EM algorithm.
Include: initialization, E-step, M-step, log-likelihood, BIC.
"""
import numpy as np
from scipy.stats import multivariate_normal

class GMMScratch:
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
            # Check convergence
            ll = self._log_likelihood(X)
            if ll - prev_ll < self.tol:
                break
            prev_ll = ll
        
        self.labels_ = resp.argmax(axis=1)
        return self
    
    def _e_step(self, X):
        resp = np.zeros((len(X), self.k))
        for k in range(self.k):
            resp[:, k] = self.weights[k] * multivariate_normal.pdf(X, self.means[k], self.covs[k])
        resp /= resp.sum(axis=1, keepdims=True)
        return resp
    
    def _m_step(self, X, resp):
        n = len(X)
        for k in range(self.k):
            Nk = resp[:, k].sum()
            self.means[k] = (resp[:, k] @ X) / Nk
            diff = X - self.means[k]
            self.covs[k] = (resp[:, k][:, None] * diff).T @ diff / Nk + 1e-6*np.eye(X.shape[1])
            self.weights[k] = Nk / n
    
    def _log_likelihood(self, X):
        ll = 0
        for k in range(self.k):
            ll += self.weights[k] * multivariate_normal.pdf(X, self.means[k], self.covs[k])
        return np.log(ll).sum()
    
    def bic(self, X):
        n, d = X.shape
        n_params = self.k * (d + d*(d+1)/2 + 1) - 1
        return -2 * self._log_likelihood(X) + n_params * np.log(n)
```

---

## Interview Questions

### 1. How does K-Means differ from K-Medoids?
<details><summary>Answer</summary>

- **K-Means:** Centroid = mean of cluster (may not be an actual data point). Sensitive to outliers.
- **K-Medoids (PAM):** Centroid = actual data point (medoid). More robust to outliers but O(n²) complexity.
- Use K-Medoids when: outliers present, need interpretable centers, non-Euclidean distances.

</details>

### 2. Explain the difference between hard and soft clustering.
<details><summary>Answer</summary>

- **Hard clustering (K-Means, DBSCAN):** Each point belongs to exactly one cluster.
- **Soft clustering (GMM, Fuzzy C-Means):** Each point has a probability/degree of belonging to each cluster.
- Soft clustering is useful when: clusters overlap, uncertainty matters, downstream tasks benefit from probabilities.

</details>

### 3. When would you use dimensionality reduction?
<details><summary>Answer</summary>

1. **Visualization:** Reduce to 2D/3D (t-SNE, UMAP)
2. **Curse of dimensionality:** Too many features relative to samples
3. **Speed:** Reduce computation cost for downstream algorithms
4. **Noise reduction:** Lower components often capture noise
5. **Multicollinearity:** PCA produces uncorrelated features
6. **Storage:** Compress data while retaining information

</details>

### 4. What is the difference between PCA and autoencoders?
<details><summary>Answer</summary>

- **PCA:** Linear dimensionality reduction. Closed-form solution. Components are orthogonal.
- **Autoencoders:** Non-linear (with non-linear activations). Learned via gradient descent. Can capture complex manifolds.
- Linear autoencoder with MSE loss = PCA (they find the same subspace).
- Use autoencoders when: relationships are non-linear, data lies on complex manifold.

</details>

### 5. How do you evaluate clustering when you don't have ground truth labels?
<details><summary>Answer</summary>

**Internal metrics (no labels needed):**
- Silhouette score: cohesion vs separation
- Calinski-Harabasz: ratio of between-cluster to within-cluster variance
- Davies-Bouldin: average similarity between clusters
- Inertia/WCSS: within-cluster sum of squares

**External metrics (if labels available):**
- Adjusted Rand Index (ARI)
- Normalized Mutual Information (NMI)
- V-measure (homogeneity + completeness)

Also: visual inspection, domain expert validation, downstream task performance.

</details>

### 6. Explain the difference between DBSCAN and HDBSCAN.
<details><summary>Answer</summary>

- **DBSCAN:** Fixed ε for all regions. Struggles with varying densities.
- **HDBSCAN:** Hierarchical extension. Adapts to local density by building a hierarchy and extracting stable clusters.
  - Doesn't require ε parameter
  - Handles varying density clusters
  - Provides cluster stability scores
  - More robust but slightly slower

</details>

### 7. Can PCA be applied to categorical data?
<details><summary>Answer</summary>

Standard PCA assumes continuous data and linear relationships. For categorical data:
1. **Multiple Correspondence Analysis (MCA):** PCA equivalent for categorical data
2. **One-hot encode + PCA:** Works but may be suboptimal
3. **Factor Analysis of Mixed Data (FAMD):** Handles mixed types
4. **Categorical PCA (CatPCA):** Optimal scaling + PCA

</details>

---

## Real-World Scenarios

### Scenario 1: Customer Segmentation for E-Commerce
**Context:** You're at an e-commerce company with 5M customers. You have features: purchase frequency, average order value, recency of last purchase, product categories browsed, time on site, returns rate.

**Questions:**
1. Which clustering algorithm would you use and why?
2. How do you handle features on different scales?
3. How do you determine the optimal number of segments?
4. How would you make segments actionable for marketing?

<details><summary>Solution</summary>

1. **Algorithm choice:**
   - Start with K-Means (fast, scalable to 5M)
   - Try GMM if clusters overlap significantly
   - Consider Mini-Batch K-Means for speed at scale
   - NOT DBSCAN (doesn't scale well, hard to interpret segments)

2. **Feature scaling:**
   - StandardScaler (z-score normalization) — essential for K-Means
   - Consider log-transform for skewed features (purchase amount)
   - RFM features (Recency, Frequency, Monetary) are a proven framework

3. **Optimal K:**
   - Elbow method + Silhouette analysis
   - Business constraint: 4-7 segments (actionable by marketing team)
   - BIC if using GMM

4. **Actionable segments:**
   - Profile each segment: "High-value loyalists", "Bargain hunters", "At-risk churners"
   - Create persona descriptions with statistics
   - A/B test different marketing strategies per segment
   - Monitor segment migration over time

</details>

### Scenario 2: Anomaly Detection in Manufacturing
**Context:** You run a semiconductor fab. Sensors record 500 measurements per wafer (temperature, pressure, gas flow, etc.). 0.5% of wafers are defective. You want to catch defects early.

**Questions:**
1. Is this supervised or unsupervised? Justify.
2. Which algorithm would you choose?
3. How do you reduce the 500-dimensional feature space?
4. How do you set the anomaly threshold?

<details><summary>Solution</summary>

1. **Framing:** Semi-supervised or unsupervised:
   - Few labeled defects (0.5%) → not enough for supervised
   - Train on "normal" data, detect deviations
   - Use unsupervised anomaly detection

2. **Algorithm:**
   - **Isolation Forest:** Fast, handles high dimensions, no distribution assumptions
   - **Autoencoder:** Learn normal patterns, flag high reconstruction error
   - **One-Class SVM:** If normal data has clear boundary
   - **PCA + Hotelling's T²:** Classical approach for manufacturing

3. **Dimensionality reduction:**
   - PCA: Keep components explaining 95% variance (likely 500 → 20-50)
   - Autoencoder bottleneck: Learn compressed representation
   - Domain knowledge: Group sensors by physical subsystem

4. **Threshold setting:**
   - Use known defective wafers to calibrate (if available)
   - Set at percentile of anomaly scores on validation normal data (e.g., 99th percentile)
   - Optimize for business cost: cost(missed defect) vs cost(false alarm)
   - Monitor and adjust over time with operator feedback

</details>

### Scenario 3: Document Clustering for Legal Discovery
**Context:** A law firm has 2M documents for a case. They need to group related documents for review. Documents are in various formats (emails, contracts, memos) with varying lengths.

**Questions:**
1. How would you represent documents as vectors?
2. Which clustering approach suits this problem?
3. How do you handle the varying document lengths?
4. How do you evaluate cluster quality without labels?

<details><summary>Solution</summary>

1. **Document representation:**
   - TF-IDF vectors (baseline, sparse, interpretable)
   - Sentence-BERT embeddings (dense, semantic similarity)
   - For legal: combine TF-IDF on legal terms + BERT embeddings
   - Consider document metadata (date, sender, type) as additional features

2. **Clustering approach:**
   - Hierarchical clustering: natural for legal (topics → subtopics → specific issues)
   - K-Means on embeddings for initial grouping
   - Consider topic modeling (LDA) for interpretable topics
   - Two-stage: coarse clusters (K-Means) → fine-grained (hierarchical within)

3. **Varying lengths:**
   - TF-IDF naturally normalizes by document length
   - For embeddings: mean-pool sentence embeddings across document
   - Optionally truncate/chunk long documents and aggregate
   - Weight by document importance (e.g., email thread starters vs replies)

4. **Evaluation without labels:**
   - Silhouette score on embedding space
   - Topic coherence (for topic models)
   - Human evaluation: sample documents from each cluster, assess if cohesive
   - Downstream metric: reviewer efficiency (time to review reduced?)
   - Inter-annotator agreement on cluster quality

</details>
