# Anomaly Detection

## Overview

Anomaly detection identifies data points that deviate significantly from normal patterns. Unlike supervised classification, we often have **few or no labeled anomalies** — models learn what "normal" looks like and flag deviations.

```
┌────────────────────┬────────────────────┬─────────────────────┐
│ Statistical        │ Distance/Density   │ Model-Based          │
├────────────────────┼────────────────────┼─────────────────────┤
│ Z-score (>3σ)      │ LOF                │ Isolation Forest     │
│ IQR method         │ KNN distance       │ One-Class SVM        │
│ Mahalanobis dist.  │ DBSCAN (noise pts) │ Autoencoders         │
└────────────────────┴────────────────────┴─────────────────────┘
```

---

## Statistical Methods

### Z-Score

```python
# Flag points > 3 standard deviations from mean
z_scores = (X - X.mean()) / X.std()
anomalies = np.abs(z_scores) > 3

# Limitation: assumes Gaussian, univariate, sensitive to outliers in mean/std
```

### IQR Method

```python
Q1, Q3 = np.percentile(X, [25, 75])
IQR = Q3 - Q1
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR
anomalies = (X < lower) | (X > upper)

# More robust than Z-score, doesn't assume Gaussian
```

### Mahalanobis Distance

Accounts for correlations between features (multivariate):

```python
from scipy.spatial.distance import mahalanobis

mean = X.mean(axis=0)
cov_inv = np.linalg.inv(np.cov(X.T))
distances = [mahalanobis(x, mean, cov_inv) for x in X]
# High distance = anomaly. Threshold via chi-squared distribution.
```

---

## Isolation Forest

### Key Insight

**Anomalies are easy to isolate** — they need fewer random splits to separate from the rest.

```
Normal point (many splits):     Anomaly (few splits):
        ┌─┐                          ┌─────────┐
      ┌─┤ ├─┐                        │    ×    │  ← isolated quickly!
    ┌─┤ └─┘ ├─┐                      └─────────┘
   ●  │     │  │                      
      └─────┘  │                     
               │

Anomaly score based on average path length across many random trees.
Shorter path → more anomalous.
```

### Algorithm

1. Build an ensemble of random trees:
   - Randomly select a feature
   - Randomly select a split value between min/max
   - Recurse until isolated or max depth
2. Score each point by average path length
3. Anomaly score: s(x) = 2^(-E[h(x)]/c(n))
   - s → 1: anomaly
   - s → 0.5: normal
   - s → 0: very dense

### Sklearn Code

```python
from sklearn.ensemble import IsolationForest

iso = IsolationForest(
    n_estimators=100,
    contamination=0.05,  # expected fraction of anomalies
    random_state=42
)
# -1 = anomaly, 1 = normal
predictions = iso.fit_predict(X)
scores = iso.decision_function(X)  # lower = more anomalous
```

---

## Local Outlier Factor (LOF)

### Idea

Compare local density of a point to its neighbors. If a point's density is much lower than its neighbors', it's an outlier.

```
LOF(p) = avg(local_density(neighbors)) / local_density(p)

LOF ≈ 1: similar density to neighbors (normal)
LOF >> 1: much lower density than neighbors (outlier)
```

### Advantage

Detects **local** anomalies — points that are outliers relative to their neighborhood, even if globally they're not extreme.

```python
from sklearn.neighbors import LocalOutlierFactor

lof = LocalOutlierFactor(n_neighbors=20, contamination=0.05)
predictions = lof.fit_predict(X)  # -1 = outlier
scores = lof.negative_outlier_factor_  # more negative = more anomalous
```

---

## One-Class SVM

### Idea

Learn a boundary around normal data in kernel space. Points outside the boundary are anomalies.

```python
from sklearn.svm import OneClassSVM

oc_svm = OneClassSVM(kernel='rbf', gamma='scale', nu=0.05)
# nu ≈ upper bound on fraction of outliers
predictions = oc_svm.fit_predict(X)  # -1 = outlier
```

**When to use:** Clean training data (no anomalies), clear decision boundary expected, moderate dimensions.

---

## Autoencoders for Anomaly Detection

### Idea

Train autoencoder to reconstruct NORMAL data. Anomalies will have high reconstruction error (model hasn't learned to reconstruct them).

```python
import torch.nn as nn

class AnomalyAutoencoder(nn.Module):
    def __init__(self, input_dim, encoding_dim=32):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64), nn.ReLU(),
            nn.Linear(64, encoding_dim), nn.ReLU()
        )
        self.decoder = nn.Sequential(
            nn.Linear(encoding_dim, 64), nn.ReLU(),
            nn.Linear(64, input_dim)
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))

# Train on NORMAL data only
# At inference: reconstruction_error = ||x - autoencoder(x)||²
# High error → anomaly
```

---

## Evaluation Without Labels

This is the hardest part of anomaly detection. Strategies:

1. **Inject synthetic anomalies** — add known outliers, measure detection rate
2. **Domain expert review** — sample flagged anomalies, get expert judgment
3. **Stability analysis** — consistent anomaly scores across methods = more confidence
4. **Downstream impact** — does removing flagged anomalies improve a downstream model?
5. **If some labels exist** — precision@k, recall@k, AUROC on contaminated set

## Real-World Applications

| Domain | Normal | Anomaly |
|--------|--------|---------|
| Fraud detection | Legitimate transactions | Fraudulent transactions |
| Manufacturing | Good products | Defective products |
| Cybersecurity | Normal network traffic | Intrusions/attacks |
| Healthcare | Healthy patterns | Disease indicators |
| Infrastructure | Normal metrics | System failures |

## Method Selection Guide

```
Have labeled anomalies?
├── Yes, many → Supervised classification (not this page)
├── Yes, few → Semi-supervised (train on normal, validate on labeled)
└── No → Unsupervised anomaly detection:
    ├── High-dimensional, no assumptions? → Isolation Forest
    ├── Need local density context? → LOF
    ├── Clean training data, clear boundary? → One-Class SVM
    ├── Very high-D, complex patterns? → Autoencoder
    └── Simple univariate check? → Z-score / IQR
```

## Hyperparameter Guide

| Method | Key Param | Guidance |
|--------|-----------|----------|
| Isolation Forest | `contamination` | Expected anomaly rate (0.01-0.1) |
| LOF | `n_neighbors` | 20 default; higher = smoother |
| One-Class SVM | `nu` | Upper bound on outlier fraction |
| Autoencoder | threshold | Set at 95th/99th percentile of train error |

## Common Mistakes

1. **Training on contaminated data** — if anomalies are in training set, model learns to reconstruct them too
2. **Using accuracy as metric** — with 1% anomalies, 99% accuracy means predicting all-normal
3. **Ignoring feature scaling** — distance-based methods (LOF, One-Class SVM) require it
4. **Single threshold for all time** — normal behavior drifts; retrain/recalibrate regularly
5. **Not considering business cost** — false positive vs false negative costs are rarely equal

## Interview Questions

**Q1: Why is Isolation Forest effective for anomaly detection?**
Anomalies are "few and different" — they live in sparse regions and are easily separated by random splits. Normal points are in dense regions requiring many splits. Average path length in random trees directly measures this isolation ease.

**Q2: LOF vs Isolation Forest — when to use which?**
LOF detects local anomalies (point is outlier relative to its neighborhood). Isolation Forest is global. Use LOF when normal data has varying densities; use Isolation Forest for general-purpose, high-dimensional anomaly detection.

**Q3: How do you set the anomaly threshold?**
Domain-dependent. Options: (a) use known contamination rate, (b) set at 95th/99th percentile of scores on validation normal data, (c) optimize for business cost (missed anomaly vs false alarm), (d) use precision-recall curve if some labels exist.

**Q4: Can you use clustering for anomaly detection?**
Yes — points far from any cluster center (K-Means), noise points (DBSCAN), or points with low GMM probability are anomaly candidates. However, dedicated methods are usually better calibrated.

**Q5: How do autoencoders detect anomalies vs Isolation Forest?**
Autoencoders learn a compressed representation of normal data. Anomalies can't be well-reconstructed → high error. Better for complex patterns/sequences. Isolation Forest is simpler, faster, needs no training, works out-of-box. Use autoencoders for image/sequence anomalies; Isolation Forest for tabular data.
