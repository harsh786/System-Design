# Machine Learning Algorithms — Complete Internals Deep Dive

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║              EVERY ML ALGORITHM — HOW IT WORKS UNDER THE HOOD                         ║
║         Math Intuition • Internal Mechanics • When/Why • Hyperparameters              ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## TABLE OF CONTENTS
1. Linear Regression (+ Ridge, Lasso, ElasticNet)
2. Logistic Regression
3. Decision Trees
4. Random Forest
5. Gradient Boosting (XGBoost, LightGBM, CatBoost)
6. Support Vector Machines (SVM)
7. K-Nearest Neighbors (KNN)
8. Naive Bayes
9. K-Means Clustering
10. DBSCAN
11. Principal Component Analysis (PCA)
12. Isolation Forest
13. Ensemble Methods (Bagging, Boosting, Stacking)
14. AdaBoost
15. Gaussian Mixture Models (GMM)
16. Hidden Markov Models (HMM)

---

## 1. LINEAR REGRESSION

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    LINEAR REGRESSION — INTERNALS                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Find the best-fit line through data points                           │
│  EQUATION:     ŷ = w₁x₁ + w₂x₂ + ... + wₙxₙ + b                                  │
│                ŷ = Xw + b  (matrix form)                                            │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐                │
│  │  HOW IT LEARNS (Optimization):                                   │                │
│  │                                                                   │                │
│  │  Loss Function: MSE = (1/n) Σᵢ (yᵢ - ŷᵢ)²                      │                │
│  │                                                                   │                │
│  │  Method 1: Normal Equation (Closed-form)                         │                │
│  │  w = (XᵀX)⁻¹Xᵀy                                                │                │
│  │  • Pro: Exact solution, no iterations                            │                │
│  │  • Con: O(n³) matrix inversion, fails if XᵀX is singular       │                │
│  │  • Use when: n_features < 10,000                                │                │
│  │                                                                   │                │
│  │  Method 2: Gradient Descent (Iterative)                          │                │
│  │  w = w - α × ∂MSE/∂w                                            │                │
│  │  ∂MSE/∂w = (-2/n) Xᵀ(y - Xw)                                   │                │
│  │  • Pro: Scales to millions of features                           │                │
│  │  • Con: Need to choose learning rate α                           │                │
│  │  • Use when: n_features > 10,000 or online learning             │                │
│  └─────────────────────────────────────────────────────────────────┘                │
│                                                                                      │
│  ASSUMPTIONS:                                                                        │
│  1. Linear relationship between X and y                                              │
│  2. Independence of errors                                                           │
│  3. Homoscedasticity (constant variance of errors)                                  │
│  4. Normal distribution of errors                                                    │
│  5. No multicollinearity (features not highly correlated)                           │
│                                                                                      │
│  VARIANTS:                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Variant       │ Regularization        │ Effect                    │              │
│  │───────────────│───────────────────────│───────────────────────────│              │
│  │ Ridge (L2)    │ Loss + λ Σ wᵢ²        │ Shrinks ALL weights small│              │
│  │               │                       │ Never makes them zero     │              │
│  │               │                       │ Good: multicollinearity   │              │
│  │───────────────│───────────────────────│───────────────────────────│              │
│  │ Lasso (L1)    │ Loss + λ Σ |wᵢ|      │ Makes some weights = 0   │              │
│  │               │                       │ = FEATURE SELECTION       │              │
│  │               │                       │ Good: sparse solutions    │              │
│  │───────────────│───────────────────────│───────────────────────────│              │
│  │ ElasticNet    │ Loss + λ₁|w| + λ₂w²  │ Combines L1 + L2         │              │
│  │               │                       │ Best of both worlds       │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  HYPERPARAMETERS:                                                                    │
│  • α (learning rate): 0.001-0.1 typical                                             │
│  • λ (regularization): 0.01-100 (use cross-validation)                              │
│  • fit_intercept: True/False                                                        │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Relationship is approximately linear                                              │
│  ✓ Need interpretable coefficients                                                   │
│  ✓ Baseline model (always start here)                                                │
│  ✗ Non-linear data → use polynomial features or tree-based                          │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. LOGISTIC REGRESSION

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    LOGISTIC REGRESSION — INTERNALS                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Classification (NOT regression despite the name)                      │
│  KEY IDEA: Linear model + sigmoid to squash output to [0,1] probability              │
│                                                                                      │
│  EQUATION:                                                                           │
│  z = w₁x₁ + w₂x₂ + ... + wₙxₙ + b   (linear combination)                         │
│  P(y=1|x) = σ(z) = 1 / (1 + e⁻ᶻ)     (sigmoid squashes to 0-1)                    │
│                                                                                      │
│  Sigmoid Function:                                                                   │
│  1.0 ─────────────────────────────╭───────────                                      │
│                                  /                                                    │
│  0.5 ─────────────────────────/─────────────                                        │
│                              /                                                        │
│  0.0 ───────────────────╯───────────────────                                        │
│       -6    -4    -2    0     2     4    6                                           │
│                                                                                      │
│  LOSS FUNCTION: Binary Cross-Entropy (Log Loss)                                      │
│  L = -(1/n) Σ [yᵢ log(ŷᵢ) + (1-yᵢ) log(1-ŷᵢ)]                                   │
│                                                                                      │
│  WHY NOT MSE? Sigmoid makes MSE non-convex (many local minima)                      │
│  Log loss IS convex → guaranteed to find global minimum                              │
│                                                                                      │
│  OPTIMIZATION: Gradient Descent                                                      │
│  ∂L/∂w = (1/n) Xᵀ(σ(Xw) - y)                                                      │
│  Same form as linear regression! (Just with sigmoid applied)                        │
│                                                                                      │
│  DECISION BOUNDARY:                                                                  │
│  • Predict class 1 if P(y=1|x) > threshold (default 0.5)                           │
│  • Decision boundary is LINEAR (hyperplane in feature space)                        │
│  • Adjusting threshold trades off precision vs recall                                │
│                                                                                      │
│  MULTI-CLASS EXTENSION:                                                              │
│  • One-vs-Rest (OvR): K binary classifiers, pick highest confidence                │
│  • Multinomial (Softmax): Direct multi-class with softmax output                    │
│    P(y=k) = e^(zₖ) / Σⱼ e^(zⱼ)                                                    │
│                                                                                      │
│  HYPERPARAMETERS:                                                                    │
│  • C (inverse regularization): Higher = less regularization                         │
│  • penalty: 'l1', 'l2', 'elasticnet'                                               │
│  • solver: 'lbfgs' (default), 'liblinear' (small data), 'saga' (large)            │
│  • class_weight: 'balanced' for imbalanced data                                     │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Binary/multi-class classification                                                 │
│  ✓ Need PROBABILITIES (calibrated outputs)                                           │
│  ✓ Need INTERPRETABILITY (coefficients = feature importance)                         │
│  ✓ Baseline classifier (always start here)                                           │
│  ✓ High-dimensional sparse data (text with TF-IDF)                                  │
│  ✗ Non-linear decision boundaries → use SVM with RBF or trees                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. DECISION TREES

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    DECISION TREE — INTERNALS                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Recursively split data into subsets using feature thresholds          │
│                                                                                      │
│  TREE STRUCTURE:                                                                     │
│              [Is Age > 30?]                                                           │
│             /              \                                                          │
│           Yes              No                                                         │
│           /                  \                                                        │
│  [Income > 50K?]        [Student?]                                                   │
│     /       \              /     \                                                    │
│   Yes       No          Yes      No                                                  │
│    │         │            │       │                                                   │
│  [Buy]   [No Buy]     [Buy]   [No Buy]                                              │
│                                                                                      │
│  HOW IT SPLITS — Impurity Measures:                                                  │
│  ═══════════════════════════════════                                                  │
│                                                                                      │
│  For CLASSIFICATION:                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐                    │
│  │ Gini Impurity: G = 1 - Σᵢ pᵢ²                               │                    │
│  │ • G=0: Pure node (all same class)                            │                    │
│  │ • G=0.5: Maximum impurity (binary, 50-50 split)             │                    │
│  │ • DEFAULT in scikit-learn (slightly faster to compute)       │                    │
│  │                                                               │                    │
│  │ Entropy: H = -Σᵢ pᵢ log₂(pᵢ)                                │                    │
│  │ • H=0: Pure node                                             │                    │
│  │ • H=1: Maximum impurity (binary, 50-50)                      │                    │
│  │ • Information Gain = H(parent) - Σ(weighted H(children))    │                    │
│  │ • Tends to produce more balanced trees                       │                    │
│  └─────────────────────────────────────────────────────────────┘                    │
│                                                                                      │
│  For REGRESSION:                                                                     │
│  • MSE (Mean Squared Error) reduction                                                │
│  • MAE (Mean Absolute Error) reduction                                               │
│  • Split to minimize variance in each child node                                    │
│                                                                                      │
│  SPLITTING ALGORITHM (CART):                                                         │
│  1. For each feature f:                                                              │
│     2. For each possible threshold t:                                                │
│        3. Split data into left (f ≤ t) and right (f > t)                            │
│        4. Compute impurity reduction = parent - weighted(children)                   │
│  5. Pick split with MAXIMUM impurity reduction                                       │
│  6. Recurse on each child until stopping criteria met                               │
│                                                                                      │
│  STOPPING CRITERIA:                                                                  │
│  • max_depth reached                                                                 │
│  • min_samples_split (node too small to split)                                      │
│  • min_samples_leaf (leaf would be too small)                                       │
│  • max_leaf_nodes                                                                    │
│  • min_impurity_decrease (split doesn't help enough)                                │
│                                                                                      │
│  PRUNING (Prevent Overfitting):                                                      │
│  • Pre-pruning: Limit depth, min samples (set before training)                      │
│  • Post-pruning (Cost Complexity Pruning):                                           │
│    R_α(T) = R(T) + α|T|  where |T| = number of leaves                              │
│    Grow full tree → prune leaves that don't reduce error enough                     │
│                                                                                      │
│  HYPERPARAMETERS:                                                                    │
│  • max_depth: 3-20 (most important!)                                                │
│  • min_samples_split: 2-20                                                           │
│  • min_samples_leaf: 1-10                                                            │
│  • criterion: 'gini' or 'entropy'                                                   │
│  • max_features: None, 'sqrt', 'log2'                                               │
│                                                                                      │
│  STRENGTHS:                           WEAKNESSES:                                    │
│  ✓ Fully interpretable (visualize)    ✗ High variance (overfits easily)             │
│  ✓ Handles non-linear relationships   ✗ Unstable (small data change → new tree)     │
│  ✓ No feature scaling needed          ✗ Greedy (not globally optimal)                │
│  ✓ Handles mixed data types           ✗ Biased toward features with many values      │
│  ✓ Handles missing values             ✗ Single tree is usually weak                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. RANDOM FOREST

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    RANDOM FOREST — INTERNALS                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT IS: Ensemble of MANY decision trees trained on RANDOM subsets               │
│  KEY IDEA: "Wisdom of crowds" — many weak learners → one strong learner             │
│                                                                                      │
│  HOW IT WORKS:                                                                       │
│  ═══════════════                                                                     │
│  1. BOOTSTRAP SAMPLING (Bagging):                                                    │
│     • From N training samples, sample N WITH REPLACEMENT                            │
│     • Each tree gets a different ~63% of data (rest is OOB)                         │
│                                                                                      │
│  2. RANDOM FEATURE SUBSET:                                                           │
│     • At EACH SPLIT, consider only √p features (classification)                    │
│     • Or p/3 features (regression)                                                   │
│     • This DECORRELATES the trees!                                                   │
│                                                                                      │
│  3. GROW MANY TREES (typically 100-1000):                                            │
│     • Each tree grows to full depth (no pruning usually)                            │
│     • Each tree is HIGH VARIANCE but LOW BIAS                                        │
│                                                                                      │
│  4. AGGREGATE:                                                                       │
│     • Classification: MAJORITY VOTE across all trees                                │
│     • Regression: AVERAGE prediction across all trees                               │
│                                                                                      │
│  WHY IT WORKS (Mathematically):                                                      │
│  ═══════════════════════════════                                                     │
│  Variance of average = σ²/n + ρσ²(1 - 1/n)                                         │
│  Where ρ = correlation between trees                                                 │
│                                                                                      │
│  • More trees (n↑) → first term shrinks                                            │
│  • Random features (ρ↓) → second term shrinks                                      │
│  • Result: LOW VARIANCE while keeping LOW BIAS                                       │
│                                                                                      │
│  OUT-OF-BAG (OOB) ERROR:                                                             │
│  • Each sample appears in ~63% of bootstrap samples                                 │
│  • For each sample, predict using trees that DIDN'T see it                          │
│  • Free validation score — no need for separate val set!                            │
│                                                                                      │
│  FEATURE IMPORTANCE:                                                                 │
│  • Method 1: Mean Decrease in Impurity (MDI)                                        │
│    Sum up impurity reduction at each split using that feature                       │
│  • Method 2: Permutation Importance                                                  │
│    Shuffle one feature → measure accuracy drop                                      │
│                                                                                      │
│  HYPERPARAMETERS:                                                                    │
│  • n_estimators: 100-1000 (more = better until plateau)                             │
│  • max_depth: None (grow full) or limit (3-20)                                      │
│  • max_features: 'sqrt' (classification), 'log2', or 0.33                          │
│  • min_samples_leaf: 1-5                                                             │
│  • n_jobs: -1 (parallelize across CPU cores!)                                       │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Default "first try" for any classification/regression                            │
│  ✓ Tabular data with mixed feature types                                            │
│  ✓ Need feature importance                                                           │
│  ✓ Don't want to tune many hyperparameters                                          │
│  ✓ Can afford slightly more compute than single tree                                │
│  ✗ If you need maximum accuracy → try XGBoost/LightGBM                             │
│  ✗ If interpretability is critical → single Decision Tree                           │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. GRADIENT BOOSTING (XGBoost / LightGBM / CatBoost)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    GRADIENT BOOSTING — INTERNALS                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT IS: Build trees SEQUENTIALLY, each correcting errors of previous           │
│  KEY INSIGHT: Fit new tree to the RESIDUALS (errors) of current model               │
│                                                                                      │
│  ALGORITHM:                                                                          │
│  ═══════════                                                                         │
│  1. Initialize: F₀(x) = mean(y)  (or log-odds for classification)                  │
│  2. For m = 1, 2, ..., M:                                                           │
│     a. Compute residuals: rᵢ = yᵢ - Fₘ₋₁(xᵢ)                                     │
│        (Actually: negative gradient of loss w.r.t. prediction)                      │
│     b. Fit a new tree hₘ(x) to residuals rᵢ                                       │
│     c. Update: Fₘ(x) = Fₘ₋₁(x) + η × hₘ(x)                                      │
│                                         ↑ learning rate                             │
│  3. Final: F(x) = F₀ + η·h₁ + η·h₂ + ... + η·hₘ                                  │
│                                                                                      │
│  VISUAL:                                                                             │
│  ┌────────┐                                                                          │
│  │ Tree 1 │ → Predicts average (rough approximation)                                │
│  └───┬────┘                                                                          │
│      │ residuals                                                                     │
│  ┌───▼────┐                                                                          │
│  │ Tree 2 │ → Fixes errors of Tree 1                                                │
│  └───┬────┘                                                                          │
│      │ residuals                                                                     │
│  ┌───▼────┐                                                                          │
│  │ Tree 3 │ → Fixes errors of Trees 1+2                                             │
│  └───┬────┘                                                                          │
│      │  ...                                                                          │
│  ┌───▼────┐                                                                          │
│  │Tree 100│ → Fine-tunes remaining errors                                           │
│  └────────┘                                                                          │
│  Final = Sum of all trees' predictions                                               │
│                                                                                      │
│  ══════════════════════════════════════════════════                                   │
│  XGBoost INNOVATIONS:                                                                │
│  ══════════════════════════════════════════════════                                   │
│  • Regularized objective: L(θ) + Ω(tree)                                            │
│    Ω = γT + ½λΣw² (penalize #leaves + leaf weights)                                │
│  • Second-order Taylor expansion of loss (uses Hessian)                              │
│  • Column subsampling (like Random Forest)                                           │
│  • Weighted quantile sketch (approximate split finding)                             │
│  • Sparsity-aware (handles missing values natively)                                 │
│  • Cache-aware + out-of-core computation                                            │
│  • Parallel tree building (within a single tree, feature-level)                     │
│                                                                                      │
│  ══════════════════════════════════════════════════                                   │
│  LightGBM INNOVATIONS:                                                               │
│  ══════════════════════════════════════════════════                                   │
│  • Leaf-wise growth (vs level-wise in XGBoost)                                      │
│    → Finds better splits but needs max_depth to prevent overfit                     │
│  • GOSS (Gradient-based One-Side Sampling):                                          │
│    Keep all high-gradient samples, randomly sample low-gradient                     │
│  • EFB (Exclusive Feature Bundling):                                                │
│    Bundle mutually exclusive sparse features → reduce dimensions                    │
│  • Histogram-based splitting (bin continuous features)                               │
│  • Result: 5-10x FASTER than XGBoost with similar accuracy                         │
│                                                                                      │
│  ══════════════════════════════════════════════════                                   │
│  CatBoost INNOVATIONS:                                                               │
│  ══════════════════════════════════════════════════                                   │
│  • Ordered Target Encoding for categoricals                                          │
│    (No need to manually encode categorical features!)                               │
│  • Ordered Boosting (prevents target leakage)                                       │
│  • Symmetric trees (balanced, faster inference)                                     │
│  • Handles categorical features NATIVELY                                            │
│  • Best when: Many categorical features                                              │
│                                                                                      │
│  COMPARISON:                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Feature        │ XGBoost       │ LightGBM      │ CatBoost        │              │
│  │────────────────│───────────────│───────────────│─────────────────│              │
│  │ Speed          │ Moderate      │ FASTEST       │ Moderate         │              │
│  │ Accuracy       │ Excellent     │ Excellent     │ Excellent        │              │
│  │ Categoricals   │ Manual encode │ Manual encode │ NATIVE           │              │
│  │ GPU support    │ Yes           │ Yes           │ Yes              │              │
│  │ Overfitting    │ Moderate      │ Easy to overfit│ Most robust     │              │
│  │ Default params │ Need tuning   │ Need tuning   │ Good defaults    │              │
│  │ Tree growth    │ Level-wise    │ Leaf-wise     │ Symmetric        │              │
│  │ Missing values │ Native        │ Native        │ Native           │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  KEY HYPERPARAMETERS (XGBoost):                                                      │
│  • n_estimators: 100-3000 (use early stopping!)                                    │
│  • learning_rate (η): 0.01-0.3 (lower → more trees needed)                         │
│  • max_depth: 3-10 (6 default, controls complexity)                                 │
│  • subsample: 0.6-1.0 (row sampling per tree)                                      │
│  • colsample_bytree: 0.6-1.0 (column sampling per tree)                            │
│  • reg_lambda (L2): 0-10                                                             │
│  • reg_alpha (L1): 0-10                                                              │
│  • min_child_weight: 1-10 (minimum sum of Hessian in leaf)                          │
│                                                                                      │
│  WHEN TO USE GRADIENT BOOSTING:                                                      │
│  ✓ TABULAR DATA (almost always the best choice!)                                    │
│  ✓ Kaggle competitions (wins 80%+ of tabular competitions)                          │
│  ✓ Medium datasets (1K - 10M rows)                                                  │
│  ✓ Mixed feature types                                                               │
│  ✓ Need high accuracy                                                                │
│  ✗ Very small data (<100 rows) → overfit risk                                       │
│  ✗ Unstructured data (images, text) → use DL                                        │
│  ✗ Need online/incremental learning → limited support                                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. SUPPORT VECTOR MACHINES (SVM)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    SVM — INTERNALS                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Find the hyperplane that MAXIMIZES the margin between classes        │
│                                                                                      │
│  INTUITION:                                                                          │
│     Class B:   ○   ○                                                                 │
│                  ○     ← Support vectors (closest points)                           │
│  ─────────────────────────── Decision boundary (hyperplane)                         │
│           ←  MARGIN  →                                                               │
│                  ●     ← Support vectors                                             │
│     Class A: ●    ●                                                                  │
│                                                                                      │
│  MATHEMATICS:                                                                        │
│  ═══════════                                                                         │
│  Objective: Maximize margin = 2/||w||                                                │
│  Subject to: yᵢ(w·xᵢ + b) ≥ 1 for all i                                           │
│                                                                                      │
│  Equivalent to: Minimize ½||w||²                                                     │
│  Subject to: yᵢ(w·xᵢ + b) ≥ 1                                                      │
│                                                                                      │
│  SOFT MARGIN (Real-world data isn't perfectly separable):                            │
│  Minimize: ½||w||² + C Σᵢ ξᵢ                                                        │
│  Where ξᵢ = slack variables (allow some misclassification)                          │
│  C = regularization (high C = strict, low C = allow errors)                         │
│                                                                                      │
│  THE KERNEL TRICK:                                                                   │
│  ═════════════════                                                                   │
│  Problem: What if data is NOT linearly separable?                                   │
│  Solution: Map to higher dimension where it IS separable                            │
│                                                                                      │
│  2D (not separable):    →    3D (linearly separable!):                              │
│     ○ ● ○ ● ○               ○   ○   ○   (lifted)                                    │
│                                ● ● ●     (stayed low)                                │
│                                                                                      │
│  Kernels (compute similarity in high-D without explicitly mapping):                 │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Kernel     │ Formula                    │ Use Case                 │              │
│  │────────────│────────────────────────────│──────────────────────────│              │
│  │ Linear     │ K(x,y) = xᵀy              │ Linearly separable       │              │
│  │ RBF/Gauss  │ K(x,y) = exp(-γ||x-y||²)  │ DEFAULT: most problems   │              │
│  │ Polynomial │ K(x,y) = (γxᵀy + r)^d     │ Non-linear, known degree │              │
│  │ Sigmoid    │ K(x,y) = tanh(γxᵀy + r)   │ Neural network-like      │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  RBF KERNEL (Most Important):                                                        │
│  • γ HIGH → narrow Gaussian → complex boundary (overfit risk)                       │
│  • γ LOW → wide Gaussian → smooth boundary (underfit risk)                          │
│  • C HIGH → strict margin (overfit risk)                                            │
│  • C LOW → wide margin (underfit risk)                                              │
│                                                                                      │
│  HYPERPARAMETERS:                                                                    │
│  • C: 0.01-1000 (regularization)                                                    │
│  • kernel: 'rbf' (default), 'linear', 'poly'                                       │
│  • gamma: 'scale' (default), 'auto', or float                                      │
│  • degree: for polynomial kernel only                                                │
│                                                                                      │
│  COMPLEXITY:                                                                         │
│  • Training: O(n²) to O(n³) — SLOW for large datasets!                             │
│  • Prediction: O(n_sv × d) where n_sv = support vectors                            │
│  • Practically limited to ~100K samples                                              │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Small to medium datasets (<100K samples)                                         │
│  ✓ High-dimensional data (text, genomics)                                           │
│  ✓ Clear margin of separation exists                                                 │
│  ✓ Need non-linear boundaries (RBF kernel)                                          │
│  ✗ Large datasets (>100K) → too slow, use tree-based                                │
│  ✗ Need probability estimates (SVM doesn't natively — Platt scaling needed)         │
│  ✗ Need interpretability                                                             │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. K-NEAREST NEIGHBORS (KNN)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    KNN — INTERNALS                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT IS: "You are who your neighbors are"                                        │
│  NO TRAINING: Stores all data, predicts by finding K nearest points                 │
│                                                                                      │
│  ALGORITHM:                                                                          │
│  1. Store all training data (lazy learning)                                          │
│  2. For new point x:                                                                 │
│     a. Compute distance to ALL training points                                      │
│     b. Find K closest neighbors                                                     │
│     c. Classification: Majority vote of K neighbors' labels                         │
│     d. Regression: Average of K neighbors' values                                   │
│                                                                                      │
│  DISTANCE METRICS:                                                                   │
│  • Euclidean: d = √(Σ(xᵢ-yᵢ)²)  ← default                                        │
│  • Manhattan: d = Σ|xᵢ-yᵢ|        ← high-dimensional                              │
│  • Minkowski: d = (Σ|xᵢ-yᵢ|^p)^(1/p)  (generalizes both)                         │
│  • Cosine:   d = 1 - (x·y)/(||x||·||y||)  ← text/embeddings                      │
│                                                                                      │
│  CHOOSING K:                                                                         │
│  • K=1: Memorizes training data (overfits)                                          │
│  • K=N: Predicts majority class always (underfits)                                  │
│  • Sweet spot: √N or use cross-validation                                           │
│  • Use ODD K for binary classification (avoid ties)                                 │
│                                                                                      │
│  CRITICAL REQUIREMENT: FEATURE SCALING!                                              │
│  • Features on different scales dominate distance                                    │
│  • MUST StandardScale or MinMaxScale before KNN                                     │
│                                                                                      │
│  OPTIMIZATIONS:                                                                      │
│  • KD-Tree: O(log n) lookup (works for low dimensions)                              │
│  • Ball Tree: Works for high dimensions                                              │
│  • Approximate: FAISS, Annoy, HNSW (for millions of points)                        │
│                                                                                      │
│  COMPLEXITY:                                                                         │
│  • Training: O(1) — just store data!                                                │
│  • Prediction: O(n×d) brute force → O(log n) with tree                             │
│  • Memory: O(n×d) — stores entire dataset                                           │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Very small datasets                                                               │
│  ✓ Quick baseline                                                                    │
│  ✓ Recommendation systems (find similar items)                                      │
│  ✓ Anomaly detection (distance-based)                                               │
│  ✗ Large datasets (slow prediction)                                                  │
│  ✗ High-dimensional (curse of dimensionality)                                        │
│  ✗ Need a compact model                                                              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. NAIVE BAYES

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    NAIVE BAYES — INTERNALS                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT IS: Probabilistic classifier based on Bayes' Theorem                        │
│  "NAIVE" = assumes features are INDEPENDENT given the class                          │
│                                                                                      │
│  BAYES' THEOREM:                                                                     │
│  P(class|features) = P(features|class) × P(class) / P(features)                    │
│                                                                                      │
│  Posterior = Likelihood × Prior / Evidence                                           │
│                                                                                      │
│  NAIVE ASSUMPTION (simplification):                                                  │
│  P(x₁,x₂,...,xₙ|class) = P(x₁|class) × P(x₂|class) × ... × P(xₙ|class)         │
│  (Features are conditionally independent — RARELY true but works well!)             │
│                                                                                      │
│  PREDICTION:                                                                         │
│  ŷ = argmax_c  P(c) × Πᵢ P(xᵢ|c)                                                  │
│                                                                                      │
│  VARIANTS:                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Variant      │ P(xᵢ|c) assumption     │ Use Case                  │              │
│  │──────────────│────────────────────────│───────────────────────────│              │
│  │ Gaussian NB  │ Normal distribution     │ Continuous features       │              │
│  │ Multinomial  │ Multinomial distrib.    │ Text (word counts/TF-IDF)│              │
│  │ Bernoulli NB │ Binary (0/1)           │ Binary features, short text│              │
│  │ Complement NB│ Complement of class    │ Imbalanced text classes    │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  WHY IT WORKS DESPITE THE NAIVE ASSUMPTION:                                          │
│  • Even if probabilities are wrong, the RANKING is often correct                    │
│  • The classification decision only needs the RIGHT CLASS to win                    │
│  • Works especially well for text (high-dim, sparse)                                │
│                                                                                      │
│  LAPLACE SMOOTHING:                                                                  │
│  P(xᵢ|c) = (count(xᵢ, c) + α) / (count(c) + α × |vocabulary|)                    │
│  Prevents zero probabilities for unseen features (α=1 typically)                    │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Text classification (spam, sentiment) — first baseline!                          │
│  ✓ Very fast training and prediction                                                 │
│  ✓ Works well with small training data                                              │
│  ✓ Multi-class (natural extension)                                                   │
│  ✓ Real-time classification (O(1) prediction)                                       │
│  ✗ When features are NOT independent and you need accuracy                          │
│  ✗ When you need probability CALIBRATION                                            │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. K-MEANS CLUSTERING

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    K-MEANS — INTERNALS                                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Partition n points into K clusters by minimizing within-cluster       │
│  distance to centroid                                                                │
│                                                                                      │
│  ALGORITHM (Lloyd's):                                                                │
│  1. Initialize K centroids (random or K-Means++)                                    │
│  2. ASSIGN: Each point → nearest centroid                                           │
│  3. UPDATE: Move each centroid → mean of its assigned points                        │
│  4. Repeat 2-3 until convergence (centroids don't move)                             │
│                                                                                      │
│  OBJECTIVE (Inertia):                                                                │
│  Minimize: Σₖ Σᵢ∈Cₖ ||xᵢ - μₖ||²                                                  │
│  (Sum of squared distances from each point to its centroid)                          │
│                                                                                      │
│  K-MEANS++ INITIALIZATION (Better than random):                                     │
│  1. Pick first centroid randomly                                                     │
│  2. For each subsequent centroid:                                                    │
│     Pick point with probability proportional to D(x)²                               │
│     (distance to nearest existing centroid)                                          │
│  3. This spreads centroids apart → better convergence                               │
│                                                                                      │
│  CHOOSING K:                                                                         │
│  • Elbow Method: Plot inertia vs K, find the "elbow"                               │
│  • Silhouette Score: Average (b-a)/max(a,b) for each point                         │
│    a = avg distance to own cluster, b = avg distance to nearest other               │
│    Range: -1 to 1 (higher = better)                                                 │
│  • Gap Statistic: Compare to uniform reference                                      │
│  • Domain knowledge: "How many customer segments make sense?"                       │
│                                                                                      │
│  LIMITATIONS:                                                                        │
│  • Assumes SPHERICAL clusters (equal size/shape)                                    │
│  • Sensitive to initialization (run multiple times)                                  │
│  • Must specify K in advance                                                         │
│  • Sensitive to outliers                                                             │
│  • Doesn't handle non-convex shapes                                                  │
│                                                                                      │
│  VARIANTS:                                                                           │
│  • Mini-Batch K-Means: Faster, uses subsets per iteration                           │
│  • K-Medoids: Uses actual data points as centers (robust to outliers)               │
│  • K-Means++: Better initialization (default in scikit-learn)                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. DBSCAN

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    DBSCAN — INTERNALS                                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Density-Based Spatial Clustering of Applications with Noise           │
│  KEY ADVANTAGE: Finds clusters of ARBITRARY SHAPE, handles noise                    │
│                                                                                      │
│  CONCEPTS:                                                                           │
│  • ε (epsilon): Radius of neighborhood                                              │
│  • MinPts: Minimum points to form a dense region                                    │
│                                                                                      │
│  Point types:                                                                        │
│  • CORE point: Has ≥ MinPts neighbors within ε                                     │
│  • BORDER point: Within ε of a core point, but < MinPts neighbors                  │
│  • NOISE point: Neither core nor border (= outlier!)                                │
│                                                                                      │
│  ALGORITHM:                                                                          │
│  1. For each unvisited point p:                                                      │
│     a. Find all points within ε distance                                            │
│     b. If |neighbors| ≥ MinPts → p is CORE, start new cluster                     │
│     c. Add all density-reachable points to cluster                                  │
│     d. If |neighbors| < MinPts → mark as NOISE (may change later)                  │
│  2. Points not in any cluster = outliers                                             │
│                                                                                      │
│  ADVANTAGES over K-Means:                                                            │
│  ✓ No need to specify K                                                              │
│  ✓ Finds arbitrary-shaped clusters                                                   │
│  ✓ Identifies outliers/noise automatically                                           │
│  ✓ Robust to outliers                                                                │
│                                                                                      │
│  DISADVANTAGES:                                                                      │
│  ✗ Sensitive to ε and MinPts (hard to tune)                                         │
│  ✗ Struggles with varying density clusters                                           │
│  ✗ High-dimensional data (distances become meaningless)                              │
│  ✗ O(n²) without spatial index (O(n log n) with KD-Tree)                           │
│                                                                                      │
│  CHOOSING PARAMETERS:                                                                │
│  • MinPts: 2 × dimensions (rule of thumb), minimum 3                                │
│  • ε: Plot K-distance graph, find the "knee"                                       │
│                                                                                      │
│  VARIANTS:                                                                           │
│  • OPTICS: Handles varying density (ordered reachability)                           │
│  • HDBSCAN: Hierarchical DBSCAN (best general choice!)                              │
│    → Automatic ε selection, handles variable density                                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. PRINCIPAL COMPONENT ANALYSIS (PCA)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    PCA — INTERNALS                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Reduce dimensions by finding directions of MAXIMUM VARIANCE          │
│                                                                                      │
│  INTUITION: Find the "best angle" to view your data with fewest dimensions          │
│                                                                                      │
│  ALGORITHM:                                                                          │
│  1. Center data: X = X - mean(X)                                                    │
│  2. Compute covariance matrix: C = (1/n) XᵀX                                       │
│  3. Compute eigenvectors & eigenvalues of C                                         │
│  4. Sort by eigenvalue (largest = most variance)                                    │
│  5. Pick top-k eigenvectors as new axes                                             │
│  6. Project: X_new = X × W_k  (W_k = top-k eigenvectors)                          │
│                                                                                      │
│  MATH:                                                                               │
│  • Eigenvector v satisfies: Cv = λv                                                 │
│  • λ (eigenvalue) = variance explained by that component                            │
│  • Variance explained ratio: λᵢ / Σλⱼ                                              │
│                                                                                      │
│  HOW MANY COMPONENTS (k)?                                                            │
│  • Keep enough to explain 95% or 99% of variance                                   │
│  • Scree plot: Eigenvalues vs component number, find "elbow"                        │
│  • For visualization: k=2 or k=3                                                    │
│                                                                                      │
│  APPLICATIONS:                                                                       │
│  • Reduce 1000 features → 50 (before feeding to ML model)                          │
│  • Visualization (high-D → 2D/3D)                                                   │
│  • Noise reduction (drop low-variance components)                                   │
│  • Decorrelation (PCA components are uncorrelated)                                  │
│  • Compression (images, signals)                                                     │
│                                                                                      │
│  LIMITATIONS:                                                                        │
│  • Linear only (can't capture non-linear structure)                                 │
│  • Sensitive to scaling (MUST standardize first!)                                   │
│  • Destroyed interpretability (components are combinations)                         │
│  • For non-linear: use t-SNE, UMAP, Kernel PCA, Autoencoders                      │
│                                                                                      │
│  COMPARISON OF DIM REDUCTION METHODS:                                                │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Method       │ Linear? │ Preserves      │ Use Case                │              │
│  │──────────────│─────────│────────────────│─────────────────────────│              │
│  │ PCA          │ Yes     │ Global variance│ Feature reduction       │              │
│  │ t-SNE        │ No      │ Local structure│ Visualization only      │              │
│  │ UMAP         │ No      │ Local+global   │ Visualization + downstream│            │
│  │ Kernel PCA   │ No      │ Non-linear     │ When PCA fails           │              │
│  │ Autoencoder  │ No      │ Learned repr.  │ Complex non-linear       │              │
│  │ LDA (Fisher) │ Yes     │ Class separation│ Supervised reduction    │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. ISOLATION FOREST

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    ISOLATION FOREST — INTERNALS                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Anomaly detection by isolating outliers                               │
│  KEY INSIGHT: Anomalies are EASIER to isolate (fewer splits needed)                 │
│                                                                                      │
│  INTUITION:                                                                          │
│  • Normal points are clustered → need MANY random splits to isolate                │
│  • Anomalies are far from clusters → need FEW splits to isolate                    │
│  • Anomaly score ∝ 1/average_path_length                                            │
│                                                                                      │
│  ALGORITHM:                                                                          │
│  1. Build multiple random trees (isolation trees):                                   │
│     a. Randomly select a feature                                                    │
│     b. Randomly select a split value between min and max                            │
│     c. Recurse until each point is isolated or max depth                            │
│  2. For each point, compute average path length across all trees                    │
│  3. Anomaly score: s(x) = 2^(-E(h(x))/c(n))                                       │
│     Where h(x) = path length, c(n) = average path length in BST                    │
│                                                                                      │
│  SCORE INTERPRETATION:                                                               │
│  • s → 1: Definitely anomaly (very short path)                                     │
│  • s → 0: Definitely normal (very long path)                                       │
│  • s ≈ 0.5: Uncertain                                                               │
│                                                                                      │
│  HYPERPARAMETERS:                                                                    │
│  • n_estimators: 100-300 trees                                                      │
│  • contamination: Expected % of anomalies (0.01-0.1)                                │
│  • max_samples: 256 (default) — small subsample works!                              │
│                                                                                      │
│  ADVANTAGES:                                                                         │
│  ✓ Very fast (O(n log n))                                                           │
│  ✓ No need for labeled anomalies (unsupervised)                                    │
│  ✓ Works well in high dimensions                                                     │
│  ✓ Linear memory and time complexity                                                 │
│  ✓ Few hyperparameters                                                               │
│                                                                                      │
│  WHEN TO USE:                                                                        │
│  ✓ Fraud detection, intrusion detection                                             │
│  ✓ Manufacturing defect detection (sensor data)                                     │
│  ✓ Large datasets with low contamination                                            │
│  ✗ Very high contamination (>30%) → not ideal                                       │
│  ✗ Local anomalies (use LOF instead)                                                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. ENSEMBLE METHODS — COMPLETE GUIDE

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    ENSEMBLE METHODS                                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  THREE ENSEMBLE STRATEGIES:                                                          │
│                                                                                      │
│  ┌─── BAGGING (Bootstrap Aggregating) ───────────────────────────────────────────┐  │
│  │                                                                                │  │
│  │  Data ──┬──[Bootstrap sample 1]──▶ [Model 1] ──┐                              │  │
│  │         ├──[Bootstrap sample 2]──▶ [Model 2] ──├──▶ AVERAGE/VOTE ──▶ Output   │  │
│  │         ├──[Bootstrap sample 3]──▶ [Model 3] ──┤                              │  │
│  │         └──[Bootstrap sample N]──▶ [Model N] ──┘                              │  │
│  │                                                                                │  │
│  │  Effect: REDUCES VARIANCE (combats overfitting)                                │  │
│  │  Example: Random Forest                                                        │  │
│  │  Models trained: INDEPENDENTLY and in PARALLEL                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── BOOSTING ──────────────────────────────────────────────────────────────────┐  │
│  │                                                                                │  │
│  │  Data ──▶ [Model 1] ──▶ Errors ──▶ [Model 2] ──▶ Errors ──▶ [Model 3]...    │  │
│  │                                                                                │  │
│  │  Final = Σ αᵢ × Modelᵢ  (weighted sum)                                       │  │
│  │                                                                                │  │
│  │  Effect: REDUCES BIAS (combats underfitting)                                   │  │
│  │  Each model focuses on ERRORS of previous models                               │  │
│  │  Examples: AdaBoost, XGBoost, LightGBM, CatBoost                             │  │
│  │  Models trained: SEQUENTIALLY (each depends on previous)                       │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── STACKING ──────────────────────────────────────────────────────────────────┐  │
│  │                                                                                │  │
│  │  Data ──┬──▶ [Model A: RF]     ──┐                                            │  │
│  │         ├──▶ [Model B: SVM]    ──├──▶ [Meta-Model: LogReg] ──▶ Output         │  │
│  │         ├──▶ [Model C: XGB]    ──┤                                            │  │
│  │         └──▶ [Model D: KNN]    ──┘                                            │  │
│  │                                                                                │  │
│  │  Level 0: Multiple DIFFERENT algorithms                                        │  │
│  │  Level 1: Meta-learner trained on Level 0 PREDICTIONS                         │  │
│  │  Use cross-validation for Level 0 predictions (prevent leakage)               │  │
│  │                                                                                │  │
│  │  Effect: Combines DIVERSE model strengths                                      │  │
│  │  Typically gives 1-3% accuracy boost over best single model                   │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── BLENDING (Simplified Stacking) ────────────────────────────────────────────┐  │
│  │  Same as stacking but uses a holdout set instead of cross-validation           │  │
│  │  Simpler but wastes data (holdout not used for training)                       │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌─── VOTING ────────────────────────────────────────────────────────────────────┐  │
│  │  Hard Voting: Majority class wins                                              │  │
│  │  Soft Voting: Average probabilities, pick highest                             │  │
│  │  Weighted Voting: Give better models more weight                              │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. AdaBoost

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    ADABOOST — INTERNALS                                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Adaptive Boosting — focuses on hard examples                          │
│                                                                                      │
│  ALGORITHM:                                                                          │
│  1. Initialize weights: wᵢ = 1/N for all samples                                   │
│  2. For t = 1, ..., T:                                                               │
│     a. Train weak learner hₜ on WEIGHTED data                                      │
│     b. Compute weighted error: εₜ = Σᵢ wᵢ × I(hₜ(xᵢ) ≠ yᵢ)                      │
│     c. Compute model weight: αₜ = ½ ln((1-εₜ)/εₜ)                                 │
│        (Good models get HIGH α, bad models get LOW α)                               │
│     d. Update sample weights:                                                        │
│        wᵢ = wᵢ × exp(αₜ) if misclassified (INCREASE weight)                       │
│        wᵢ = wᵢ × exp(-αₜ) if correct (DECREASE weight)                            │
│     e. Normalize weights                                                             │
│  3. Final: H(x) = sign(Σₜ αₜ × hₜ(x))                                             │
│                                                                                      │
│  KEY INTUITION:                                                                      │
│  • Misclassified samples get HIGHER weights → next model focuses on them           │
│  • Each model is WEIGHTED by how good it is                                         │
│  • Turns many "weak" learners (barely better than random) into one STRONG learner   │
│                                                                                      │
│  COMPARISON WITH GRADIENT BOOSTING:                                                  │
│  • AdaBoost: Reweights SAMPLES                                                      │
│  • Gradient Boosting: Fits to RESIDUALS (gradients)                                 │
│  • Gradient Boosting is more general (any differentiable loss)                      │
│  • AdaBoost is a special case of GB with exponential loss                           │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 15. GAUSSIAN MIXTURE MODELS (GMM)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    GMM — INTERNALS                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  WHAT IT DOES: Soft clustering — each point belongs to MULTIPLE clusters            │
│  with different probabilities                                                        │
│                                                                                      │
│  MODEL: Data is generated from K Gaussian distributions                              │
│  P(x) = Σₖ πₖ × N(x | μₖ, Σₖ)                                                     │
│  Where:                                                                              │
│  • πₖ = mixing coefficient (prior probability of cluster k)                        │
│  • μₖ = mean of cluster k                                                           │
│  • Σₖ = covariance matrix of cluster k                                              │
│                                                                                      │
│  ALGORITHM (Expectation-Maximization):                                               │
│  E-step: Compute responsibility (soft assignment)                                    │
│    rₖ(xᵢ) = P(z=k|xᵢ) = πₖN(xᵢ|μₖ,Σₖ) / Σⱼ πⱼN(xᵢ|μⱼ,Σⱼ)                    │
│                                                                                      │
│  M-step: Update parameters                                                           │
│    μₖ = Σᵢ rₖ(xᵢ)xᵢ / Σᵢ rₖ(xᵢ)                                                 │
│    Σₖ = Σᵢ rₖ(xᵢ)(xᵢ-μₖ)(xᵢ-μₖ)ᵀ / Σᵢ rₖ(xᵢ)                                  │
│    πₖ = (1/N) Σᵢ rₖ(xᵢ)                                                            │
│                                                                                      │
│  Repeat E and M until convergence (log-likelihood stops increasing)                 │
│                                                                                      │
│  ADVANTAGES over K-Means:                                                            │
│  ✓ Soft assignments (probability of belonging)                                      │
│  ✓ Handles elliptical clusters (not just spherical)                                 │
│  ✓ Different cluster sizes and shapes                                                │
│  ✓ Probabilistic framework (can compute likelihood)                                 │
│                                                                                      │
│  CHOOSING K: BIC (Bayesian Information Criterion) or AIC                            │
│  BIC = -2 log L + k ln(n)  — penalizes complexity more                             │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 16. CROSS-VALIDATION & HYPERPARAMETER TUNING

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    CROSS-VALIDATION & TUNING                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  K-FOLD CROSS-VALIDATION:                                                            │
│  ═══════════════════════                                                             │
│  Split data into K folds (typically K=5 or K=10):                                   │
│                                                                                      │
│  Fold 1: [TEST] [train] [train] [train] [train]                                    │
│  Fold 2: [train] [TEST] [train] [train] [train]                                    │
│  Fold 3: [train] [train] [TEST] [train] [train]                                    │
│  Fold 4: [train] [train] [train] [TEST] [train]                                    │
│  Fold 5: [train] [train] [train] [train] [TEST]                                    │
│                                                                                      │
│  Final score = average of 5 test scores                                              │
│  Gives more reliable estimate than single train/test split                          │
│                                                                                      │
│  VARIANTS:                                                                           │
│  • Stratified K-Fold: Preserves class distribution in each fold                    │
│  • Leave-One-Out (LOO): K=N (expensive but low bias)                                │
│  • Time Series Split: Respect temporal order (no data leakage from future)          │
│  • Group K-Fold: Ensure same group doesn't appear in train AND test                 │
│                                                                                      │
│  HYPERPARAMETER TUNING METHODS:                                                      │
│  ┌───────────────────────────────────────────────────────────────────┐              │
│  │ Method          │ How it works                │ When to use       │              │
│  │─────────────────│─────────────────────────────│───────────────────│              │
│  │ Grid Search     │ Try all combinations        │ Few params, small │              │
│  │                 │                             │ search space       │              │
│  │ Random Search   │ Random samples from ranges  │ Many params, wider│              │
│  │                 │ (often BETTER than grid!)    │ is better than deep│             │
│  │ Bayesian (Optuna)│ Model the objective,       │ Expensive models,  │              │
│  │                 │ smart sampling              │ large search space │              │
│  │ Hyperband       │ Early stopping of bad       │ DL hyperparams     │              │
│  │                 │ configurations              │                    │              │
│  └───────────────────────────────────────────────────────────────────┘              │
│                                                                                      │
│  TOOLS: Optuna, Hyperopt, Ray Tune, scikit-learn GridSearchCV                       │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SUMMARY: THE ML ALGORITHM CHEAT SHEET

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Algorithm          │ Type         │ Best For                 │ Complexity           │
│  ═══════════════════│══════════════│══════════════════════════│═════════════════     │
│  Linear Regression  │ Regression   │ Baseline, interpretable  │ O(nd²) or O(nd)     │
│  Logistic Regression│ Classification│ Baseline, probabilities │ O(nd) per iter      │
│  Decision Tree      │ Both         │ Interpretability         │ O(n·d·log n)        │
│  Random Forest      │ Both         │ General tabular          │ O(T·n·d·log n)      │
│  XGBoost/LightGBM   │ Both         │ BEST for tabular         │ O(T·n·d)            │
│  SVM                │ Both         │ Small data, high-dim     │ O(n² to n³)         │
│  KNN                │ Both         │ Simple baseline          │ O(nd) per query     │
│  Naive Bayes        │ Classification│ Text, fast, small data  │ O(nd) training      │
│  K-Means            │ Clustering   │ Simple clustering        │ O(nkdi) per iter    │
│  DBSCAN             │ Clustering   │ Arbitrary shapes, noise  │ O(n²) or O(n log n) │
│  PCA                │ Dim Reduction│ Feature reduction        │ O(nd²)              │
│  Isolation Forest   │ Anomaly      │ Fraud, outlier detection │ O(tn log n)         │
│  GMM                │ Clustering   │ Soft clusters, ellipses  │ O(nkd²) per iter    │
│  AdaBoost           │ Both         │ Weak learner boosting    │ O(T·n·d)            │
│                                                                                      │
│  T=trees, n=samples, d=features, k=clusters, i=iterations                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

*Next: [09-DL-Architectures-Deep-Dive.md](./09-DL-Architectures-Deep-Dive.md) — Deep Learning internals →*
