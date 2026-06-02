# Unsupervised Learning

## What Is It?

Unsupervised learning finds hidden patterns in data **without labeled outputs**. The goal is to model the underlying structure or distribution in the data.

Key difference from supervised learning: no target variable `y` — only input features `X`.

## Taxonomy

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

## When to Use Unsupervised Learning

- **Exploratory analysis** — understand data structure before modeling
- **No labels available** — labeling is expensive or impossible
- **Preprocessing** — dimensionality reduction before supervised learning
- **Anomaly detection** — find rare events without labeled examples
- **Customer segmentation** — group users by behavior

## File Index

| # | File | Topic |
|---|------|-------|
| 1 | [01-k-means-clustering.md](./01-k-means-clustering.md) | K-Means, K-Means++, Mini-Batch |
| 2 | [02-hierarchical-clustering.md](./02-hierarchical-clustering.md) | Agglomerative, linkage methods, dendrograms |
| 3 | [03-dbscan.md](./03-dbscan.md) | Density-based clustering, HDBSCAN |
| 4 | [04-pca-dimensionality-reduction.md](./04-pca-dimensionality-reduction.md) | PCA, eigendecomposition, kernel PCA |
| 5 | [05-t-sne-and-umap.md](./05-t-sne-and-umap.md) | t-SNE, UMAP, visualization |
| 6 | [06-gaussian-mixture-models.md](./06-gaussian-mixture-models.md) | GMM, EM algorithm, soft clustering |
| 7 | [07-anomaly-detection.md](./07-anomaly-detection.md) | Isolation Forest, LOF, One-Class SVM |
| 8 | [08-data-preparation-for-clustering.md](./08-data-preparation-for-clustering.md) | Scaling, evaluation, cluster profiling |

## Quick Decision Guide

```
Need clusters?
├── Know K? → K-Means (spherical) or GMM (elliptical)
├── Don't know K? → DBSCAN or Hierarchical
├── Arbitrary shapes? → DBSCAN
├── Need probabilities? → GMM
└── Need hierarchy? → Agglomerative

Need dimensionality reduction?
├── Linear, for ML pipeline? → PCA
├── Non-linear, for visualization? → t-SNE (small data) or UMAP (large data)
└── Feature selection (not extraction)? → NOT PCA — use L1/mutual info

Need anomaly detection?
├── High-dimensional? → Isolation Forest
├── Local density matters? → LOF
└── Known boundary? → One-Class SVM
```

## Key Principle

> Always scale your features before applying distance-based unsupervised methods (K-Means, DBSCAN, Hierarchical, PCA). Without scaling, features with larger ranges dominate the distance computation.
