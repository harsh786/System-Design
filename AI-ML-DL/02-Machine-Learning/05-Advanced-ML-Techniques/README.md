# Advanced ML Techniques - Complete Guide

## 1. Feature Selection Methods

### Why Feature Selection?
- Reduces overfitting (fewer parameters)
- Improves speed (less computation)
- Improves interpretability
- Avoids curse of dimensionality

### Three Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE SELECTION                              │
├────────────────────┬─────────────────────┬──────────────────────┤
│   Filter Methods   │  Wrapper Methods    │  Embedded Methods    │
│   (Independent of  │  (Uses model perf)  │  (Part of training)  │
│    model)          │                     │                      │
├────────────────────┼─────────────────────┼──────────────────────┤
│ • Correlation      │ • Forward Selection │ • L1 (Lasso)         │
│ • Mutual Info      │ • Backward Elim.    │ • Tree importance    │
│ • Chi-squared      │ • Recursive (RFE)   │ • Elastic Net        │
│ • Variance thresh  │                     │ • Built-in (XGBoost) │
│ • ANOVA F-test     │                     │                      │
├────────────────────┼─────────────────────┼──────────────────────┤
│ Fast, scalable     │ Slow, best subset   │ Balanced             │
│ May miss interact. │ Computationally exp │ Model-specific       │
└────────────────────┴─────────────────────┴──────────────────────┘
```

### Recursive Feature Elimination (RFE)

```
Algorithm:
1. Train model on all features
2. Rank features by importance
3. Remove least important feature(s)
4. Repeat until desired number of features

Python:
from sklearn.feature_selection import RFECV
selector = RFECV(estimator=RandomForestClassifier(), step=1, cv=5)
selector.fit(X, y)
selected_features = X.columns[selector.support_]
```

### Mutual Information

```
MI(X; Y) = Σ Σ p(x,y) · log[p(x,y) / (p(x)·p(y))]

- MI = 0: X and Y are independent
- MI > 0: Captures non-linear dependencies (unlike correlation!)

from sklearn.feature_selection import mutual_info_classif
mi_scores = mutual_info_classif(X, y)
```

---

## 2. Dimensionality Reduction

### PCA vs Feature Selection

```
Feature Selection:  Keep original features {x₁, x₃, x₇}
PCA:                Create new features z₁ = 0.5x₁ + 0.3x₂ + ... (linear combos)

Feature Selection → Interpretable
PCA → Better variance capture, but less interpretable
```

### When to Reduce Dimensions
- Number of features >> number of samples
- Multicollinearity among features
- Visualization (reduce to 2-3D)
- Noise reduction
- Speed improvement for downstream models

### Kernel PCA (Non-linear)
```python
from sklearn.decomposition import KernelPCA
kpca = KernelPCA(n_components=2, kernel='rbf', gamma=0.04)
X_reduced = kpca.fit_transform(X)
```

---

## 3. Handling Imbalanced Classes

### The Problem
```
Real-world: Fraud (0.1%), Disease (2%), Churn (5%)

Training on imbalanced data:
- Model ignores minority class
- High accuracy but useless predictions
```

### Solutions

```
┌─────────────────────────────────────────────────────────────┐
│              IMBALANCED CLASS STRATEGIES                      │
├─────────────────┬──────────────────┬────────────────────────┤
│  Data Level     │  Algorithm Level │  Evaluation Level      │
├─────────────────┼──────────────────┼────────────────────────┤
│ Oversampling    │ Class weights    │ Use PR-AUC, not acc.   │
│ • Random        │ • sample_weight  │ Focus on recall        │
│ • SMOTE         │ • class_weight   │ Use F-beta score       │
│ • ADASYN        │                  │ Precision@K            │
│                 │ Cost-sensitive   │                        │
│ Undersampling   │ • Higher penalty │ Stratified CV          │
│ • Random        │   for minority   │                        │
│ • Tomek Links   │   misclass.      │                        │
│ • NearMiss      │                  │                        │
│                 │ Anomaly detect.  │                        │
│ Hybrid          │ • One-class SVM  │                        │
│ • SMOTE + ENN   │ • Isolation For. │                        │
└─────────────────┴──────────────────┴────────────────────────┘
```

### SMOTE (Synthetic Minority Oversampling Technique)

```
Algorithm:
1. For each minority sample xᵢ:
   a. Find k nearest minority neighbors
   b. Randomly pick one neighbor xₙₙ
   c. Create synthetic sample: x_new = xᵢ + rand(0,1) · (xₙₙ - xᵢ)

Visualization:
   Before SMOTE:              After SMOTE:
   
   ○ ○ ○ ○ ○ ○ ○            ○ ○ ○ ○ ○ ○ ○
   ○ ○ ○ ○ ○ ○ ○            ○ ○ ○ ○ ○ ○ ○
   ○ ○ ○ ○ ○ ○ ○            ○ ○ ○ ○ ○ ○ ○
   ● ●                      ● ● ★ ★ ● ★ ●
                             ★ = synthetic samples
```

```python
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

pipeline = ImbPipeline([
    ('smote', SMOTE(random_state=42)),
    ('classifier', XGBClassifier(scale_pos_weight=ratio))
])
# IMPORTANT: Only apply SMOTE to training data, never test/validation!
```

### Class Weights Approach
```python
# Automatically compute weights inversely proportional to class frequency
model = LogisticRegression(class_weight='balanced')

# Or manually:
# weight = n_samples / (n_classes * n_samples_per_class)
model = XGBClassifier(scale_pos_weight=neg_count/pos_count)
```

---

## 4. Multi-Label and Multi-Output Learning

### Multi-Label Classification
Each sample can belong to multiple classes simultaneously.

```
Example: Image tagging → {beach, sunset, people}

Approaches:
1. Binary Relevance: Train one binary classifier per label (ignores correlations)
2. Classifier Chains: Chain classifiers, each uses previous predictions as features
3. Label Powerset: Treat each unique label combination as a single class

from sklearn.multioutput import ClassifierChain
chain = ClassifierChain(LogisticRegression(), order='random', random_state=42)
```

### Multi-Output Regression
Predict multiple continuous targets simultaneously.

```python
from sklearn.multioutput import MultiOutputRegressor
multi_reg = MultiOutputRegressor(GradientBoostingRegressor())
multi_reg.fit(X, Y_multi)  # Y_multi shape: (n_samples, n_targets)
```

---

## 5. Online Learning and Incremental Learning

### When to Use
- Data arrives in streams (can't store all)
- Data too large for memory
- Distribution changes over time (concept drift)
- Need real-time model updates

### Algorithms Supporting Incremental Learning

```
┌─────────────────────────────────────────┐
│ Algorithm          │ Method             │
├─────────────────────────────────────────┤
│ SGDClassifier      │ partial_fit()      │
│ SGDRegressor       │ partial_fit()      │
│ MultinomialNB      │ partial_fit()      │
│ Perceptron         │ partial_fit()      │
│ PassiveAggressive  │ partial_fit()      │
│ MiniBatchKMeans    │ partial_fit()      │
│ River library      │ learn_one()        │
└─────────────────────────────────────────┘
```

```python
from sklearn.linear_model import SGDClassifier

model = SGDClassifier(loss='log_loss')

# Process data in chunks
for X_batch, y_batch in data_stream:
    model.partial_fit(X_batch, y_batch, classes=[0, 1])
```

### Concept Drift Detection
```
Types:
- Sudden drift:  Distribution changes abruptly
- Gradual drift: Slow transition between concepts
- Recurring:     Old concepts reappear

Detection methods:
- DDM (Drift Detection Method): Monitor error rate statistics
- ADWIN: Adaptive windowing on accuracy
- Page-Hinkley: Sequential change detection
```

---

## 6. Transfer Learning Basics

### Core Idea
Use knowledge from a source task to improve learning on a target task.

```
Traditional ML:          Transfer Learning:
                         
Task A → Model A         Task A → Model A ──┐
Task B → Model B                             ├─→ Model B (better!)
                         Task B (less data) ─┘

Especially useful when target task has limited labeled data.
```

### Types
```
1. Feature-based: Use features from pre-trained model
   - Image: CNN features from ImageNet model
   - Text: Word embeddings (Word2Vec, BERT)

2. Fine-tuning: Start with pre-trained weights, fine-tune on target
   - Freeze early layers, train later layers
   - Use small learning rate

3. Domain adaptation: Adapt model from source domain to target domain
   - Different distributions but same task
```

---

## 7. AutoML Concepts

### What AutoML Automates

```
┌─────────────────────────────────────────────────────────┐
│                   AutoML Pipeline                         │
├──────────┬───────────┬──────────┬──────────┬────────────┤
│  Data    │ Feature   │Algorithm │  Hyper-  │  Ensemble  │
│  Prep    │Engineering│Selection │  param   │  Selection │
│          │           │          │  Tuning  │            │
├──────────┼───────────┼──────────┼──────────┼────────────┤
│ Impute   │ Transform │ Try many │ Bayesian │ Stack best │
│ Encode   │ Generate  │ models   │ Optim.   │ models     │
│ Scale    │ Select    │          │          │            │
└──────────┴───────────┴──────────┴──────────┴────────────┘
```

### Popular AutoML Tools

| Tool | Approach | Strengths |
|------|----------|-----------|
| Auto-sklearn | Bayesian + Meta-learning | Robust, ensemble |
| TPOT | Genetic programming | Flexible pipeline |
| H2O AutoML | Sequential model training | Fast, production-ready |
| Google AutoML | Neural Architecture Search | Cloud-based, easy |
| AutoGluon | Multi-layer stacking | Best accuracy OOB |
| FLAML | Cost-effective search | Fast, low resource |

### Neural Architecture Search (NAS)
```
Search Space × Search Strategy × Evaluation Strategy

Search space: Operations (conv, pool, skip), connections
Strategy: RL, evolutionary, differentiable (DARTS)
Evaluation: Full training, weight sharing, early stopping
```

---

## 8. ML at Scale

### Distributed Training Strategies

```
Data Parallelism:
┌──────────────────────────────────────────┐
│  Full model on each worker               │
│                                          │
│  Worker 1: Data shard 1 → gradients₁    │
│  Worker 2: Data shard 2 → gradients₂  ──┤──→ Aggregate → Update
│  Worker 3: Data shard 3 → gradients₃    │
│                                          │
│  Each worker has full model copy         │
│  Gradients are averaged/summed           │
└──────────────────────────────────────────┘

Model Parallelism:
┌──────────────────────────────────────────┐
│  Model split across workers              │
│                                          │
│  Worker 1: Layers 1-4                    │
│  Worker 2: Layers 5-8    (pipeline)      │
│  Worker 3: Layers 9-12                   │
│                                          │
│  Used when model doesn't fit in 1 GPU    │
└──────────────────────────────────────────┘
```

### Scaling Tools

```
├── Spark MLlib: Distributed ML on Spark clusters
├── Dask-ML: Parallel scikit-learn on Dask
├── Ray: Distributed hyperparameter tuning + training
├── Horovod: Distributed deep learning training
└── Feature Stores: Feast, Tecton (feature engineering at scale)
```

### Large-Scale ML Patterns

```python
# Mini-batch processing for large datasets
from sklearn.linear_model import SGDClassifier

model = SGDClassifier()
for chunk in pd.read_csv('huge_file.csv', chunksize=10000):
    X_chunk = preprocess(chunk)
    model.partial_fit(X_chunk, y_chunk, classes=all_classes)

# Approximate algorithms for scale
from sklearn.cluster import MiniBatchKMeans  # O(n) vs O(n·k·iter)
from sklearn.decomposition import IncrementalPCA  # Streaming PCA
from sklearn.neighbors import BallTree  # O(log n) KNN queries
```

### Feature Store Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Raw Data     │────▶│ Feature      │────▶│ Feature      │
│ Sources      │     │ Pipelines    │     │ Store        │
└──────────────┘     └──────────────┘     ├──────────────┤
                                          │ Offline Store│──→ Training
                                          │ (batch)      │
                                          ├──────────────┤
                                          │ Online Store │──→ Serving
                                          │ (low latency)│
                                          └──────────────┘
```

---

## 9. Practical Tips and Production Checklist

### Before Training
- [ ] EDA: distributions, missing values, outliers
- [ ] Define success metric aligned with business goal
- [ ] Establish baseline (simple model or heuristic)
- [ ] Set up proper train/val/test split
- [ ] Check for data leakage

### During Training
- [ ] Start simple, increase complexity gradually
- [ ] Use cross-validation for model selection
- [ ] Monitor for overfitting (train vs val gap)
- [ ] Log experiments (MLflow, W&B)

### Before Production
- [ ] Test on truly held-out test set
- [ ] Measure latency and throughput
- [ ] Plan for model retraining
- [ ] Set up monitoring and alerts
- [ ] Document model card (what, why, limitations)
- [ ] A/B test against current system

---

## Interview Questions

**Q: How would you handle a dataset with 1000 features and 100 samples?**
- Use regularization (Lasso for feature selection)
- Apply PCA to reduce dimensions
- Use algorithms that handle high dimensions (SVM, Ridge)
- Avoid complex models (Random Forest would overfit)

**Q: Your model works great offline but poorly in production. Why?**
- Training-serving skew (different preprocessing)
- Data drift (production data differs from training)
- Feature pipeline bugs (missing features, stale data)
- Label leakage in training (using future info)

**Q: How do you detect and handle concept drift?**
- Monitor prediction distribution and model performance over time
- Use statistical tests (KS test, PSI) on feature distributions
- Implement windowed retraining or online learning
- Set up alerts when performance drops below threshold

**Q: SMOTE in cross-validation - what's the correct way?**
Apply SMOTE only inside each fold's training set, never before splitting. Using imblearn's Pipeline ensures this. Applying SMOTE before CV causes data leakage (synthetic samples from test fold's neighbors appear in training).

**Q: How do you scale ML to 1 billion rows?**
- Sampling: Train on representative subsample
- Distributed: Spark MLlib, Dask
- Incremental: partial_fit with mini-batches
- Approximate: MiniBatch K-Means, random projections
- Feature engineering: Pre-aggregate, use feature stores
