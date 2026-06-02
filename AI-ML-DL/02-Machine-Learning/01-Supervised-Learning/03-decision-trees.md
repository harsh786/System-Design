# Decision Trees

## Intuition

Recursively split the feature space into rectangular regions using if-then rules. At each node, pick the feature and threshold that best separates the classes.

```
              [Age > 30?]
             /           \
          Yes             No
          /                \
   [Income > 50K?]     [Student?]
    /         \          /      \
  Yes         No       Yes      No
   ↓           ↓        ↓       ↓
 Buy=Yes    Buy=No   Buy=Yes  Buy=No
```

## Information Theory Foundations

### Entropy (measure of impurity)

```
H(S) = -Σ pᵢ log₂(pᵢ)

H = 0  → pure (all one class)
H = 1  → maximum impurity (binary, 50/50)

     1 ┤     ·····
       │   ··     ··
       │  ·         ·
       │ ·           ·
     0 ┤·─────────────·
       0     0.5      1
             P(+)
```

### Gini Impurity (used by CART)

```
Gini(S) = 1 - Σ pᵢ²
For binary: Gini = 2p(1-p)
Gini = 0 → pure, Gini = 0.5 → max impurity
```

### Information Gain

```
IG(S, feature) = H(S) - Σᵥ (|Sᵥ|/|S|) · H(Sᵥ)

Choose feature with highest IG (largest entropy reduction)
```

## Algorithm Variants

| Algorithm | Split Criterion | Feature Types | Pruning |
|-----------|----------------|---------------|---------|
| ID3 | Information Gain | Categorical only | None |
| C4.5 | Gain Ratio | Both | Error-based |
| CART | Gini Impurity | Both (binary splits) | Cost-complexity |

**Gain Ratio** (C4.5): Corrects IG's bias toward high-cardinality features:
```
GainRatio = IG(S, A) / SplitInfo(A)
SplitInfo = -Σ (|Sᵥ|/|S|) log₂(|Sᵥ|/|S|)
```

## Splitting on Continuous Features

Sort values, evaluate midpoints between consecutive distinct values:
```
Feature values: [1, 3, 5, 7, 9]
Candidate thresholds: [2, 4, 6, 8]
Pick threshold with best IG/Gini reduction
```

## Pruning

**Pre-pruning (stop early):**
- max_depth, min_samples_split, min_samples_leaf, max_leaf_nodes

**Post-pruning (grow then cut):**
- Cost-complexity: minimize Rα(T) = R(T) + α|T| where |T| = number of leaves
- Use cross-validation to find optimal α

## From-Scratch Implementation

```python
import numpy as np

class DecisionTree:
    def __init__(self, max_depth=10, min_samples=2):
        self.max_depth = max_depth
        self.min_samples = min_samples
    
    def _gini(self, y):
        counts = np.bincount(y)
        probs = counts / len(y)
        return 1 - np.sum(probs**2)
    
    def _best_split(self, X, y):
        best_gain, best_feat, best_thresh = -1, None, None
        parent_gini = self._gini(y)
        
        for feat in range(X.shape[1]):
            thresholds = np.unique(X[:, feat])
            for thresh in thresholds:
                left = y[X[:, feat] <= thresh]
                right = y[X[:, feat] > thresh]
                if len(left) == 0 or len(right) == 0:
                    continue
                gain = parent_gini - (len(left)*self._gini(left) + len(right)*self._gini(right)) / len(y)
                if gain > best_gain:
                    best_gain, best_feat, best_thresh = gain, feat, thresh
        return best_feat, best_thresh
    
    def _build(self, X, y, depth):
        if depth >= self.max_depth or len(y) < self.min_samples or len(np.unique(y)) == 1:
            return {'leaf': True, 'class': np.bincount(y).argmax()}
        
        feat, thresh = self._best_split(X, y)
        if feat is None:
            return {'leaf': True, 'class': np.bincount(y).argmax()}
        
        left_mask = X[:, feat] <= thresh
        return {
            'leaf': False, 'feature': feat, 'threshold': thresh,
            'left': self._build(X[left_mask], y[left_mask], depth+1),
            'right': self._build(X[~left_mask], y[~left_mask], depth+1)
        }
    
    def fit(self, X, y):
        self.tree = self._build(X, y.astype(int), 0)
    
    def _predict_one(self, x, node):
        if node['leaf']:
            return node['class']
        if x[node['feature']] <= node['threshold']:
            return self._predict_one(x, node['left'])
        return self._predict_one(x, node['right'])
    
    def predict(self, X):
        return np.array([self._predict_one(x, self.tree) for x in X])
```

## Sklearn Usage

```python
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
import matplotlib.pyplot as plt

clf = DecisionTreeClassifier(
    max_depth=5,
    min_samples_split=10,
    min_samples_leaf=5,
    criterion='gini',  # or 'entropy'
    random_state=42
)
clf.fit(X_train, y_train)

# Visualize
print(export_text(clf, feature_names=feature_names))
plt.figure(figsize=(20, 10))
plot_tree(clf, feature_names=feature_names, class_names=class_names, filled=True)

# Feature importance (based on total impurity reduction)
importances = pd.Series(clf.feature_importances_, index=feature_names).sort_values(ascending=False)
```

## Hyperparameter Guide

| Parameter | Values to Try | Effect |
|-----------|---------------|--------|
| max_depth | [3, 5, 7, 10, None] | Main regularizer |
| min_samples_split | [2, 5, 10, 20] | Min samples to split a node |
| min_samples_leaf | [1, 2, 5, 10] | Min samples in leaf |
| criterion | gini, entropy | Split quality measure |
| max_features | None, 'sqrt', 'log2' | Randomness (useful in ensembles) |
| ccp_alpha | [0, 0.01, 0.02, 0.05] | Cost-complexity pruning |

## When to Use / When NOT to Use

**Use when:**
- Interpretability is critical (can show decision rules to stakeholders)
- Mixed feature types (numerical + categorical)
- Non-linear relationships with interactions
- No need for feature scaling
- Quick baseline model

**Don't use when:**
- Smooth decision boundaries needed (trees make axis-aligned cuts)
- Stability matters (small data changes → very different tree)
- High accuracy needed without ensembling
- Extrapolation is required (trees can't predict beyond training range)

## Common Mistakes

1. **Not pruning** → severe overfitting (100% train acc, poor test)
2. **Using single tree for production** → use Random Forest or XGBoost instead
3. **High-cardinality categoricals** → tree biases toward them (use target encoding)
4. **Ignoring class imbalance** → set `class_weight='balanced'`

## Advantages & Disadvantages

| Advantages | Disadvantages |
|------------|---------------|
| Interpretable (white box) | Prone to overfitting |
| No scaling needed | Unstable (high variance) |
| Handles non-linearity | Axis-aligned boundaries only |
| Fast training & prediction | Greedy (not globally optimal) |
| Handles missing values (some impl) | Cannot extrapolate |

## Interview Questions

**Q1: Gini vs Entropy — when does it matter?**
In practice, they produce very similar trees. Entropy is slightly more computationally expensive (log). Gini tends to isolate the most frequent class in its own branch; entropy produces more balanced trees. Usually doesn't significantly affect performance.

**Q2: How does a tree handle continuous features?**
Sorts unique values, evaluates all midpoint thresholds, picks the one maximizing information gain. Time complexity: O(n·log(n)·d) per split.

**Q3: Why are decision trees unstable?**
Small changes in data can lead to completely different splits at the root, cascading through the entire tree. This is why ensembles (Random Forest, Boosting) average many trees to reduce variance.

**Q4: What's cost-complexity pruning?**
Grow the full tree, then find the subtree minimizing Rα(T) = R(T) + α·|T|. Use cross-validation to select optimal α. In sklearn: `ccp_alpha` parameter.

**Q5: Can decision trees do regression?**
Yes (CART). Split to minimize MSE in each region. Leaf prediction = mean of samples in that leaf. Same algorithm, different impurity criterion.
