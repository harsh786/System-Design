# 12 — Code Examples & Implementations

## Production-Ready Python Snippets for Every Key Algorithm

> Every algorithm from files 08-11, now with runnable code.
> Copy-paste ready. Explained inline. Real datasets.

---

## Table of Contents

1. [ML Algorithms with scikit-learn](#1-ml-algorithms-with-scikit-learn)
2. [Gradient Boosting Frameworks](#2-gradient-boosting-frameworks)
3. [Deep Learning with PyTorch](#3-deep-learning-with-pytorch)
4. [Transformer from Scratch](#4-transformer-from-scratch)
5. [NLP with HuggingFace](#5-nlp-with-huggingface)
6. [Computer Vision](#6-computer-vision)
7. [RAG Pipeline](#7-rag-pipeline)
8. [MLOps Patterns](#8-mlops-patterns)
9. [Full End-to-End Pipeline](#9-full-end-to-end-pipeline)

---

## 1. ML Algorithms with scikit-learn

### 1.1 Linear Regression — From Scratch + sklearn

```python
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# === FROM SCRATCH ===
class LinearRegressionScratch:
    """OLS via Normal Equation: θ = (X^T X)^(-1) X^T y"""
    
    def fit(self, X, y):
        # Add bias column
        X_b = np.c_[np.ones((X.shape[0], 1)), X]
        # Normal equation
        self.theta = np.linalg.pinv(X_b.T @ X_b) @ X_b.T @ y
        return self
    
    def predict(self, X):
        X_b = np.c_[np.ones((X.shape[0], 1)), X]
        return X_b @ self.theta


# === WITH SKLEARN ===
from sklearn.datasets import fetch_california_housing

data = fetch_california_housing()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

model = LinearRegression()
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

print(f"R² Score: {r2_score(y_test, y_pred):.4f}")
print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
print(f"Coefficients: {model.coef_}")
print(f"Intercept: {model.intercept_:.4f}")
```

### 1.2 Logistic Regression — Binary Classification

```python
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import load_breast_cancer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42, stratify=data.target
)

# Pipeline: Scale → Logistic Regression
pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('clf', LogisticRegression(
        C=1.0,              # Inverse regularization strength
        penalty='l2',       # Ridge (L2) or 'l1' for Lasso
        solver='lbfgs',     # Best for small-medium datasets
        max_iter=1000,
        class_weight='balanced'  # Handle imbalanced classes
    ))
])

pipe.fit(X_train, y_train)
y_pred = pipe.predict(X_test)
y_proba = pipe.predict_proba(X_test)[:, 1]

print(classification_report(y_test, y_pred, target_names=data.target_names))
print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.4f}")
```

### 1.3 Decision Tree — with Visualization

```python
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
from sklearn.datasets import load_iris
import matplotlib.pyplot as plt

data = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

tree = DecisionTreeClassifier(
    max_depth=4,            # Prevent overfitting
    min_samples_split=5,    # Min samples to split a node
    min_samples_leaf=2,     # Min samples in leaf node
    criterion='gini',       # or 'entropy' for information gain
    random_state=42
)
tree.fit(X_train, y_train)

# Print text representation of the tree
print(export_text(tree, feature_names=data.feature_names))

# Feature importance
for name, importance in zip(data.feature_names, tree.feature_importances_):
    print(f"  {name}: {importance:.4f}")

# Visual plot
plt.figure(figsize=(20, 10))
plot_tree(tree, feature_names=data.feature_names, 
          class_names=data.target_names, filled=True, rounded=True)
plt.savefig('decision_tree.png', dpi=150, bbox_inches='tight')
```

### 1.4 Random Forest — with OOB Score and Feature Importance

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
import pandas as pd

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

rf = RandomForestClassifier(
    n_estimators=200,       # Number of trees
    max_depth=None,         # Grow full trees (RF handles overfitting via bagging)
    min_samples_leaf=2,
    max_features='sqrt',    # √(n_features) per split — key RF hyperparameter
    oob_score=True,         # Out-of-bag estimate (free validation!)
    n_jobs=-1,              # Use all cores
    random_state=42
)
rf.fit(X_train, y_train)

print(f"OOB Score: {rf.oob_score_:.4f}")
print(f"Test Accuracy: {rf.score(X_test, y_test):.4f}")

# Permutation importance (more reliable than .feature_importances_)
perm_imp = permutation_importance(rf, X_test, y_test, n_repeats=10, random_state=42)
imp_df = pd.DataFrame({
    'feature': data.feature_names,
    'importance_mean': perm_imp.importances_mean,
    'importance_std': perm_imp.importances_std
}).sort_values('importance_mean', ascending=False)

print("\nTop 10 Features (Permutation Importance):")
print(imp_df.head(10).to_string(index=False))
```

### 1.5 SVM — Linear and Kernel

```python
from sklearn.svm import SVC, LinearSVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

# Linear SVM (fast, good for high-dimensional)
linear_svm = make_pipeline(
    StandardScaler(),
    LinearSVC(C=1.0, max_iter=10000, dual=False)  # dual=False when n_samples > n_features
)
linear_svm.fit(X_train, y_train)
print(f"Linear SVM Accuracy: {linear_svm.score(X_test, y_test):.4f}")

# RBF Kernel SVM (captures non-linear boundaries)
rbf_svm = make_pipeline(
    StandardScaler(),
    SVC(
        C=10.0,             # Regularization (higher = less regularization)
        kernel='rbf',       # Radial basis function
        gamma='scale',      # 1 / (n_features * X.var()) — controls decision boundary smoothness
        probability=True    # Enable predict_proba (slower training)
    )
)
rbf_svm.fit(X_train, y_train)
print(f"RBF SVM Accuracy: {rbf_svm.score(X_test, y_test):.4f}")
```

### 1.6 KNN — with Distance Metrics

```python
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import cross_val_score

data = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

# Find optimal K
k_range = range(1, 31)
cv_scores = []
for k in k_range:
    knn = KNeighborsClassifier(
        n_neighbors=k,
        weights='distance',     # Weight by inverse distance (closer = more weight)
        metric='minkowski',     # p=2 is Euclidean, p=1 is Manhattan
        p=2
    )
    scores = cross_val_score(knn, X_train, y_train, cv=5, scoring='accuracy')
    cv_scores.append(scores.mean())

best_k = k_range[np.argmax(cv_scores)]
print(f"Best K: {best_k} (CV Accuracy: {max(cv_scores):.4f})")

# Final model
knn = KNeighborsClassifier(n_neighbors=best_k, weights='distance')
knn.fit(X_train, y_train)
print(f"Test Accuracy: {knn.score(X_test, y_test):.4f}")
```

### 1.7 Naive Bayes — Text Classification

```python
from sklearn.naive_bayes import MultinomialNB, GaussianNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.datasets import fetch_20newsgroups
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

# Load text dataset
categories = ['sci.space', 'comp.graphics', 'rec.sport.baseball', 'talk.politics.guns']
train = fetch_20newsgroups(subset='train', categories=categories)
test = fetch_20newsgroups(subset='test', categories=categories)

# TF-IDF + Naive Bayes pipeline
nb_pipeline = Pipeline([
    ('tfidf', TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 2),     # Unigrams + bigrams
        stop_words='english',
        sublinear_tf=True       # Apply log normalization to TF
    )),
    ('clf', MultinomialNB(alpha=0.1))  # Laplace smoothing
])

nb_pipeline.fit(train.data, train.target)
y_pred = nb_pipeline.predict(test.data)

print(classification_report(test.target, y_pred, target_names=categories))
```

### 1.8 K-Means Clustering

```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt

# Generate sample data
from sklearn.datasets import make_blobs
X, y_true = make_blobs(n_samples=500, centers=4, cluster_std=0.8, random_state=42)
X_scaled = StandardScaler().fit_transform(X)

# Elbow Method + Silhouette Score
inertias = []
silhouettes = []
K_range = range(2, 11)

for k in K_range:
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(X_scaled)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X_scaled, km.labels_))

best_k = K_range[np.argmax(silhouettes)]
print(f"Best K by Silhouette: {best_k} (score: {max(silhouettes):.4f})")

# Final clustering
km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
labels = km.fit_predict(X_scaled)

# Plot
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].plot(K_range, inertias, 'bo-')
axes[0].set_xlabel('K'); axes[0].set_ylabel('Inertia'); axes[0].set_title('Elbow Method')

axes[1].scatter(X_scaled[:, 0], X_scaled[:, 1], c=labels, cmap='viridis', alpha=0.6)
axes[1].scatter(km.cluster_centers_[:, 0], km.cluster_centers_[:, 1], 
                c='red', marker='X', s=200, label='Centroids')
axes[1].set_title(f'K-Means (K={best_k})'); axes[1].legend()
plt.savefig('kmeans_clustering.png', dpi=150, bbox_inches='tight')
```

### 1.9 DBSCAN — Density-Based Clustering

```python
from sklearn.cluster import DBSCAN
from sklearn.datasets import make_moons
from sklearn.preprocessing import StandardScaler

# Non-convex data (K-Means fails here, DBSCAN succeeds)
X, y = make_moons(n_samples=500, noise=0.1, random_state=42)
X_scaled = StandardScaler().fit_transform(X)

# DBSCAN
db = DBSCAN(
    eps=0.3,            # Neighborhood radius
    min_samples=5,      # Min points to form dense region
    metric='euclidean'
)
labels = db.fit_predict(X_scaled)

n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = (labels == -1).sum()
print(f"Clusters found: {n_clusters}")
print(f"Noise points: {n_noise}")
print(f"Silhouette (excl noise): {silhouette_score(X_scaled[labels != -1], labels[labels != -1]):.4f}")
```

### 1.10 PCA — Dimensionality Reduction

```python
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

data = load_breast_cancer()
X_scaled = StandardScaler().fit_transform(data.data)

# Full PCA to see explained variance
pca_full = PCA()
pca_full.fit(X_scaled)

# How many components explain 95% variance?
cumulative_var = np.cumsum(pca_full.explained_variance_ratio_)
n_components_95 = np.argmax(cumulative_var >= 0.95) + 1
print(f"Components for 95% variance: {n_components_95} (out of {data.data.shape[1]})")

# Reduce to 2D for visualization
pca_2d = PCA(n_components=2)
X_2d = pca_2d.fit_transform(X_scaled)

plt.figure(figsize=(8, 6))
scatter = plt.scatter(X_2d[:, 0], X_2d[:, 1], c=data.target, cmap='RdBu', alpha=0.7)
plt.xlabel(f'PC1 ({pca_2d.explained_variance_ratio_[0]:.1%} variance)')
plt.ylabel(f'PC2 ({pca_2d.explained_variance_ratio_[1]:.1%} variance)')
plt.colorbar(scatter, label='Target')
plt.title('PCA: Breast Cancer Dataset')
plt.savefig('pca_visualization.png', dpi=150, bbox_inches='tight')
```

### 1.11 Isolation Forest — Anomaly Detection

```python
from sklearn.ensemble import IsolationForest
import numpy as np

# Normal data + anomalies
np.random.seed(42)
X_normal = np.random.randn(1000, 2) * 0.5
X_anomalies = np.random.uniform(low=-4, high=4, size=(50, 2))
X = np.vstack([X_normal, X_anomalies])

iso_forest = IsolationForest(
    n_estimators=200,
    contamination=0.05,    # Expected fraction of anomalies
    max_samples='auto',    # Subsample size
    random_state=42
)
predictions = iso_forest.fit_predict(X)  # 1 = normal, -1 = anomaly
scores = iso_forest.decision_function(X)  # Lower = more anomalous

n_detected = (predictions == -1).sum()
print(f"Anomalies detected: {n_detected}")
print(f"Score range: [{scores.min():.3f}, {scores.max():.3f}]")
```

---

## 2. Gradient Boosting Frameworks

### 2.1 XGBoost — Full Production Setup

```python
import xgboost as xgb
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error
import numpy as np

data = fetch_california_housing()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

# DMatrix for optimal performance
dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=data.feature_names)
dtest = xgb.DMatrix(X_test, label=y_test, feature_names=data.feature_names)

params = {
    'objective': 'reg:squarederror',
    'eval_metric': 'rmse',
    'max_depth': 6,             # Tree depth (3-10 typical)
    'learning_rate': 0.1,       # Step size shrinkage
    'subsample': 0.8,           # Row sampling per tree
    'colsample_bytree': 0.8,   # Column sampling per tree
    'reg_alpha': 0.1,           # L1 regularization
    'reg_lambda': 1.0,          # L2 regularization
    'min_child_weight': 5,      # Min sum of instance weight in leaf
    'tree_method': 'hist',      # Fast histogram-based method
    'device': 'cpu',            # or 'cuda' for GPU
    'seed': 42
}

# Train with early stopping
model = xgb.train(
    params, dtrain,
    num_boost_round=1000,
    evals=[(dtrain, 'train'), (dtest, 'eval')],
    early_stopping_rounds=50,
    verbose_eval=100
)

y_pred = model.predict(dtest)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"\nFinal RMSE: {rmse:.4f}")
print(f"Best iteration: {model.best_iteration}")

# Feature importance
importance = model.get_score(importance_type='gain')
for feat, score in sorted(importance.items(), key=lambda x: -x[1])[:5]:
    print(f"  {feat}: {score:.2f}")
```

### 2.2 LightGBM — Faster Training, Categorical Support

```python
import lightgbm as lgb
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
import numpy as np

data = fetch_california_housing()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

train_data = lgb.Dataset(X_train, label=y_train, feature_name=list(data.feature_names))
valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

params = {
    'objective': 'regression',
    'metric': 'rmse',
    'boosting_type': 'gbdt',       # or 'dart', 'goss'
    'num_leaves': 63,              # Max leaves per tree (key param, NOT max_depth)
    'learning_rate': 0.05,
    'feature_fraction': 0.8,       # Column sampling
    'bagging_fraction': 0.8,       # Row sampling
    'bagging_freq': 5,             # Bagging every 5 iterations
    'min_child_samples': 20,       # Min data in leaf
    'lambda_l1': 0.1,
    'lambda_l2': 0.1,
    'verbose': -1,
    'seed': 42
}

model = lgb.train(
    params, train_data,
    num_boost_round=1000,
    valid_sets=[valid_data],
    callbacks=[
        lgb.early_stopping(50),
        lgb.log_evaluation(100)
    ]
)

y_pred = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"\nFinal RMSE: {rmse:.4f}")
```

### 2.3 CatBoost — Native Categorical Features

```python
from catboost import CatBoostClassifier, Pool
import pandas as pd
from sklearn.model_selection import train_test_split

# Example with categorical features (Titanic-style)
df = pd.DataFrame({
    'age': [22, 38, 26, 35, 28, 54, 2, 27, 14, 4],
    'sex': ['male', 'female', 'female', 'female', 'male', 'male', 'male', 'female', 'female', 'male'],
    'class': ['third', 'first', 'third', 'first', 'third', 'second', 'third', 'first', 'second', 'third'],
    'embarked': ['S', 'C', 'S', 'S', 'S', 'S', 'Q', 'S', 'C', 'S'],
    'survived': [0, 1, 1, 1, 0, 0, 0, 1, 1, 0]
})

cat_features = ['sex', 'class', 'embarked']  # CatBoost handles these natively!
X = df.drop('survived', axis=1)
y = df['survived']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

model = CatBoostClassifier(
    iterations=500,
    depth=6,
    learning_rate=0.1,
    cat_features=cat_features,  # No need to encode!
    auto_class_weights='Balanced',
    eval_metric='AUC',
    verbose=100,
    random_seed=42
)

model.fit(X_train, y_train, eval_set=(X_test, y_test), early_stopping_rounds=50)
print(f"\nTest Accuracy: {model.score(X_test, y_test):.4f}")
```

### 2.4 Hyperparameter Tuning with Optuna

```python
import optuna
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.datasets import load_breast_cancer

data = load_breast_cancer()
X, y = data.data, data.target

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 500),
        'max_depth': trial.suggest_int('max_depth', 2, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 20),
    }
    
    model = GradientBoostingClassifier(**params, random_state=42)
    scores = cross_val_score(model, X, y, cv=5, scoring='roc_auc')
    return scores.mean()

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100, show_progress_bar=True)

print(f"Best AUC: {study.best_value:.4f}")
print(f"Best params: {study.best_params}")
```

---

## 3. Deep Learning with PyTorch

### 3.1 Neural Network from Scratch (NumPy only)

```python
import numpy as np

class NeuralNetworkFromScratch:
    """2-layer NN with ReLU + Sigmoid. Trained with SGD."""
    
    def __init__(self, input_dim, hidden_dim, output_dim, lr=0.01):
        # Xavier initialization
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros((1, hidden_dim))
        self.W2 = np.random.randn(hidden_dim, output_dim) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros((1, output_dim))
        self.lr = lr
    
    def relu(self, x):
        return np.maximum(0, x)
    
    def relu_derivative(self, x):
        return (x > 0).astype(float)
    
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def forward(self, X):
        self.z1 = X @ self.W1 + self.b1
        self.a1 = self.relu(self.z1)
        self.z2 = self.a1 @ self.W2 + self.b2
        self.a2 = self.sigmoid(self.z2)
        return self.a2
    
    def backward(self, X, y):
        m = X.shape[0]
        
        # Output layer gradient
        dz2 = self.a2 - y.reshape(-1, 1)  # BCE derivative
        dW2 = (self.a1.T @ dz2) / m
        db2 = np.sum(dz2, axis=0, keepdims=True) / m
        
        # Hidden layer gradient
        da1 = dz2 @ self.W2.T
        dz1 = da1 * self.relu_derivative(self.z1)
        dW1 = (X.T @ dz1) / m
        db1 = np.sum(dz1, axis=0, keepdims=True) / m
        
        # Update weights
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1
    
    def train(self, X, y, epochs=1000):
        for epoch in range(epochs):
            output = self.forward(X)
            self.backward(X, y)
            if epoch % 100 == 0:
                loss = -np.mean(y * np.log(output + 1e-8) + (1 - y) * np.log(1 - output + 1e-8))
                print(f"Epoch {epoch}, Loss: {loss:.4f}")

# Test on XOR problem
X = np.array([[0,0], [0,1], [1,0], [1,1]])
y = np.array([0, 1, 1, 0])

nn = NeuralNetworkFromScratch(input_dim=2, hidden_dim=8, output_dim=1, lr=0.5)
nn.train(X, y, epochs=5000)
print(f"Predictions: {nn.forward(X).flatten().round(2)}")
```

### 3.2 PyTorch — Complete Training Loop

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import numpy as np

# Data preparation
data = load_breast_cancer()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

# Convert to tensors
X_train_t = torch.FloatTensor(X_train)
y_train_t = torch.FloatTensor(y_train)
X_test_t = torch.FloatTensor(X_test)
y_test_t = torch.FloatTensor(y_test)

train_ds = TensorDataset(X_train_t, y_train_t)
train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)

# Model definition
class BinaryClassifier(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        return self.network(x).squeeze()

# Training setup
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = BinaryClassifier(X_train.shape[1]).to(device)
criterion = nn.BCELoss()
optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

# Training loop
best_acc = 0
for epoch in range(100):
    model.train()
    epoch_loss = 0
    for X_batch, y_batch in train_loader:
        X_batch, y_batch = X_batch.to(device), y_batch.to(device)
        
        optimizer.zero_grad()
        output = model(X_batch)
        loss = criterion(output, y_batch)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item()
    
    # Validation
    model.eval()
    with torch.no_grad():
        test_output = model(X_test_t.to(device))
        test_preds = (test_output > 0.5).float()
        acc = (test_preds == y_test_t.to(device)).float().mean()
        scheduler.step(1 - acc)
        
        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), 'best_model.pt')
    
    if (epoch + 1) % 20 == 0:
        print(f"Epoch {epoch+1}: Loss={epoch_loss/len(train_loader):.4f}, Acc={acc:.4f}")

print(f"\nBest Test Accuracy: {best_acc:.4f}")
```

### 3.3 CNN — Image Classification (CIFAR-10)

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# Data augmentation + normalization
transform_train = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomCrop(32, padding=4),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616))
])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616))
])

train_ds = datasets.CIFAR10('./data', train=True, download=True, transform=transform_train)
test_ds = datasets.CIFAR10('./data', train=False, transform=transform_test)
train_loader = DataLoader(train_ds, batch_size=128, shuffle=True, num_workers=4)
test_loader = DataLoader(test_ds, batch_size=256, num_workers=4)

# Modern CNN with residual connections
class ResBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
        )
        self.relu = nn.ReLU(inplace=True)
    
    def forward(self, x):
        return self.relu(self.conv(x) + x)  # Skip connection!

class SimpleCNN(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            # Block 1: 32x32 → 16x16
            nn.Conv2d(3, 64, 3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            ResBlock(64),
            nn.MaxPool2d(2),
            
            # Block 2: 16x16 → 8x8
            nn.Conv2d(64, 128, 3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            ResBlock(128),
            nn.MaxPool2d(2),
            
            # Block 3: 8x8 → 4x4
            nn.Conv2d(128, 256, 3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            ResBlock(256),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),  # Global average pooling
            nn.Flatten(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )
    
    def forward(self, x):
        return self.classifier(self.features(x))

# Training
device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
model = SimpleCNN().to(device)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=5e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=50)

for epoch in range(50):
    model.train()
    correct = total = 0
    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
    
    scheduler.step()
    
    if (epoch + 1) % 10 == 0:
        # Evaluate
        model.eval()
        test_correct = test_total = 0
        with torch.no_grad():
            for images, labels in test_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = outputs.max(1)
                test_total += labels.size(0)
                test_correct += predicted.eq(labels).sum().item()
        
        print(f"Epoch {epoch+1}: Train Acc={100*correct/total:.1f}%, Test Acc={100*test_correct/test_total:.1f}%")
```

### 3.4 Transfer Learning — Fine-tuning ResNet

```python
import torch
import torch.nn as nn
from torchvision import models, transforms, datasets
from torch.utils.data import DataLoader

# Load pretrained ResNet-18
model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

# Freeze all layers except last
for param in model.parameters():
    param.requires_grad = False

# Replace classifier head for your task (e.g., 5 classes)
num_classes = 5
model.fc = nn.Sequential(
    nn.Dropout(0.3),
    nn.Linear(model.fc.in_features, 256),
    nn.ReLU(),
    nn.Dropout(0.2),
    nn.Linear(256, num_classes)
)

# Only train the new head
optimizer = torch.optim.Adam(model.fc.parameters(), lr=1e-3)

# After a few epochs, unfreeze backbone for fine-tuning
for param in model.parameters():
    param.requires_grad = True

# Use much lower LR for pretrained layers
optimizer = torch.optim.Adam([
    {'params': model.fc.parameters(), 'lr': 1e-3},
    {'params': [p for n, p in model.named_parameters() if 'fc' not in n], 'lr': 1e-5}
])

print(f"Total parameters: {sum(p.numel() for p in model.parameters()):,}")
print(f"Trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
```

---

## 4. Transformer from Scratch

### 4.1 Complete Multi-Head Self-Attention

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class MultiHeadSelfAttention(nn.Module):
    """
    Multi-Head Self-Attention from "Attention is All You Need"
    
    Attention(Q, K, V) = softmax(QK^T / √d_k) V
    """
    
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"
        
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads  # Dimension per head
        
        # Q, K, V projections (combined for efficiency)
        self.W_qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.W_out = nn.Linear(d_model, d_model, bias=False)
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_k)
    
    def forward(self, x, mask=None):
        """
        x: (batch_size, seq_len, d_model)
        mask: (batch_size, 1, 1, seq_len) or (1, 1, seq_len, seq_len) for causal
        """
        B, T, C = x.shape
        
        # Project to Q, K, V
        qkv = self.W_qkv(x)  # (B, T, 3*d_model)
        qkv = qkv.reshape(B, T, 3, self.n_heads, self.d_k)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # (3, B, n_heads, T, d_k)
        Q, K, V = qkv[0], qkv[1], qkv[2]
        
        # Scaled dot-product attention
        attn_scores = (Q @ K.transpose(-2, -1)) / self.scale  # (B, n_heads, T, T)
        
        if mask is not None:
            attn_scores = attn_scores.masked_fill(mask == 0, float('-inf'))
        
        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        # Weighted sum of values
        context = attn_weights @ V  # (B, n_heads, T, d_k)
        context = context.transpose(1, 2).contiguous().reshape(B, T, C)
        
        return self.W_out(context)


class TransformerBlock(nn.Module):
    """Pre-norm Transformer block (GPT-style)"""
    
    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = MultiHeadSelfAttention(d_model, n_heads, dropout)
        self.ln2 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout)
        )
    
    def forward(self, x, mask=None):
        # Pre-norm residual connections
        x = x + self.attn(self.ln1(x), mask)
        x = x + self.ff(self.ln2(x))
        return x


class GPTModel(nn.Module):
    """Minimal GPT-style language model"""
    
    def __init__(self, vocab_size, d_model=512, n_heads=8, n_layers=6, 
                 max_seq_len=512, d_ff=2048, dropout=0.1):
        super().__init__()
        self.d_model = d_model
        
        # Embeddings
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(d_model, n_heads, d_ff, dropout)
            for _ in range(n_layers)
        ])
        
        self.ln_final = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        
        # Weight tying
        self.lm_head.weight = self.token_emb.weight
        
        self._init_weights()
    
    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)
    
    def forward(self, idx, targets=None):
        B, T = idx.shape
        device = idx.device
        
        # Create causal mask
        causal_mask = torch.tril(torch.ones(T, T, device=device)).unsqueeze(0).unsqueeze(0)
        
        # Embeddings
        tok_emb = self.token_emb(idx)  # (B, T, d_model)
        pos = torch.arange(T, device=device).unsqueeze(0)
        pos_emb = self.pos_emb(pos)
        x = self.dropout(tok_emb + pos_emb)
        
        # Transformer blocks
        for block in self.blocks:
            x = block(x, causal_mask)
        
        x = self.ln_final(x)
        logits = self.lm_head(x)  # (B, T, vocab_size)
        
        # Compute loss if targets provided
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        
        return logits, loss
    
    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=50):
        """Autoregressive generation with top-k sampling"""
        for _ in range(max_new_tokens):
            # Crop to max sequence length
            idx_crop = idx[:, -512:]
            logits, _ = self(idx_crop)
            logits = logits[:, -1, :] / temperature
            
            # Top-k filtering
            if top_k > 0:
                v, _ = torch.topk(logits, top_k)
                logits[logits < v[:, [-1]]] = float('-inf')
            
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            idx = torch.cat([idx, next_token], dim=1)
        
        return idx


# Usage
model = GPTModel(vocab_size=50257, d_model=768, n_heads=12, n_layers=12)
total_params = sum(p.numel() for p in model.parameters())
print(f"GPT Model: {total_params/1e6:.1f}M parameters")

# Dummy forward pass
x = torch.randint(0, 50257, (2, 128))
logits, loss = model(x, targets=x)
print(f"Output shape: {logits.shape}")  # (2, 128, 50257)
```

### 4.2 Rotary Positional Encoding (RoPE)

```python
import torch

def precompute_rope_frequencies(dim: int, max_seq_len: int, base: float = 10000.0):
    """Precompute the rotary position embedding frequencies"""
    # θ_i = 1 / (base^(2i/dim)) for i = 0, 1, ..., dim/2 - 1
    freqs = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
    
    # Positions: 0, 1, 2, ..., max_seq_len - 1
    t = torch.arange(max_seq_len).float()
    
    # Outer product: (max_seq_len, dim/2)
    freqs = torch.outer(t, freqs)
    
    # Complex exponentials: e^(i*θ)
    freqs_complex = torch.polar(torch.ones_like(freqs), freqs)
    return freqs_complex


def apply_rope(x: torch.Tensor, freqs_complex: torch.Tensor):
    """Apply RoPE to query/key tensors
    
    x: (batch, n_heads, seq_len, head_dim)
    """
    # Reshape to pairs: (batch, n_heads, seq_len, head_dim/2, 2)
    x_reshape = x.float().reshape(*x.shape[:-1], -1, 2)
    
    # Convert to complex: (batch, n_heads, seq_len, head_dim/2)
    x_complex = torch.view_as_complex(x_reshape)
    
    # Apply rotation (broadcast over batch and heads)
    freqs = freqs_complex[:x.shape[2], :]  # Slice to actual seq_len
    x_rotated = x_complex * freqs.unsqueeze(0).unsqueeze(0)
    
    # Back to real: (batch, n_heads, seq_len, head_dim)
    x_out = torch.view_as_real(x_rotated).reshape(*x.shape)
    return x_out.type_as(x)


# Example
dim = 64
freqs = precompute_rope_frequencies(dim, max_seq_len=2048)
q = torch.randn(2, 8, 128, dim)  # (batch=2, heads=8, seq=128, dim=64)
q_rotated = apply_rope(q, freqs)
print(f"RoPE applied: {q_rotated.shape}")
```

---

## 5. NLP with HuggingFace

### 5.1 Text Classification — Fine-tuning BERT

```python
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer
)
from datasets import load_dataset
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

# Load dataset
dataset = load_dataset("imdb")
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

# Tokenize
def tokenize_fn(examples):
    return tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=256
    )

tokenized = dataset.map(tokenize_fn, batched=True, remove_columns=["text"])
tokenized = tokenized.rename_column("label", "labels")
tokenized.set_format("torch")

# Model
model = AutoModelForSequenceClassification.from_pretrained(
    "bert-base-uncased",
    num_labels=2
)

# Metrics
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, average="weighted")
    }

# Training
training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    learning_rate=2e-5,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    fp16=True,  # Mixed precision
    dataloader_num_workers=4,
    warmup_ratio=0.1,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized["train"].select(range(5000)),  # Subset for demo
    eval_dataset=tokenized["test"].select(range(1000)),
    compute_metrics=compute_metrics,
)

trainer.train()
results = trainer.evaluate()
print(f"Final F1: {results['eval_f1']:.4f}")
```

### 5.2 Text Generation — Using GPT-2 / LLaMA

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch

# Load model
model_name = "gpt2"  # Or "meta-llama/Llama-2-7b-hf" with access token
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Simple generation
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
result = generator(
    "The future of artificial intelligence is",
    max_new_tokens=100,
    temperature=0.7,
    top_k=50,
    top_p=0.95,
    do_sample=True,
    num_return_sequences=1
)
print(result[0]["generated_text"])

# Manual generation with more control
def generate_text(prompt, max_tokens=50, temperature=0.8):
    inputs = tokenizer(prompt, return_tensors="pt")
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_k=50,
            top_p=0.9,
            do_sample=True,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
            pad_token_id=tokenizer.eos_token_id
        )
    
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

print(generate_text("Machine learning algorithms can be categorized into"))
```

### 5.3 Named Entity Recognition (NER)

```python
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
import torch

# Option 1: Pipeline (easiest)
ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

text = "Apple Inc. was founded by Steve Jobs in Cupertino, California in 1976."
entities = ner_pipeline(text)
for entity in entities:
    print(f"  {entity['word']:20s} | {entity['entity_group']:10s} | score: {entity['score']:.3f}")

# Option 2: Manual token classification
tokenizer = AutoTokenizer.from_pretrained("dslim/bert-base-NER")
model = AutoModelForTokenClassification.from_pretrained("dslim/bert-base-NER")

inputs = tokenizer(text, return_tensors="pt", return_offsets_mapping=True)
offset_mapping = inputs.pop("offset_mapping")

with torch.no_grad():
    outputs = model(**inputs)
    predictions = torch.argmax(outputs.logits, dim=-1)[0]

# Map predictions back to tokens
tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
labels = [model.config.id2label[p.item()] for p in predictions]

for token, label in zip(tokens, labels):
    if label != "O":
        print(f"  {token:15s} → {label}")
```

### 5.4 Semantic Similarity & Embeddings

```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, good quality

# Encode sentences
sentences = [
    "The cat sits on the mat",
    "A feline is resting on the rug",
    "Dogs are great pets",
    "The stock market crashed today",
    "Financial markets experienced a downturn"
]

embeddings = model.encode(sentences, normalize_embeddings=True)
print(f"Embedding shape: {embeddings.shape}")  # (5, 384)

# Compute similarity matrix
sim_matrix = cosine_similarity(embeddings)
print("\nSimilarity Matrix:")
for i, sent in enumerate(sentences):
    print(f"\n'{sent[:40]}...'")
    for j, other in enumerate(sentences):
        if i != j:
            print(f"  vs '{other[:30]}...': {sim_matrix[i][j]:.3f}")

# Semantic search
query = "What happened in the financial world?"
query_emb = model.encode([query], normalize_embeddings=True)
scores = cosine_similarity(query_emb, embeddings)[0]
ranked = np.argsort(scores)[::-1]

print(f"\nQuery: '{query}'")
for idx in ranked:
    print(f"  Score {scores[idx]:.3f}: {sentences[idx]}")
```

### 5.5 Summarization

```python
from transformers import pipeline

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

article = """
Artificial intelligence has made remarkable progress in recent years, 
with large language models like GPT-4 demonstrating capabilities that 
were previously thought to be decades away. These models can write code, 
analyze data, create content, and engage in complex reasoning tasks. 
However, experts warn that current AI systems still lack true understanding 
and common sense reasoning. The debate continues about whether scaling 
existing architectures will lead to artificial general intelligence or 
whether fundamentally new approaches are needed. Meanwhile, companies 
are racing to deploy AI in production, with applications ranging from 
customer service chatbots to drug discovery and autonomous vehicles.
"""

summary = summarizer(
    article,
    max_length=80,
    min_length=30,
    do_sample=False,  # Deterministic (beam search)
    num_beams=4
)
print(f"Summary: {summary[0]['summary_text']}")
```

---

## 6. Computer Vision

### 6.1 Image Classification — Transfer Learning (Production)

```python
import torch
import torch.nn as nn
from torchvision import models, transforms, datasets
from torch.utils.data import DataLoader
from pathlib import Path

# Production-ready image transforms
train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    transforms.RandomErasing(p=0.2)  # Cutout augmentation
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# Assume data organized as: data/train/class_name/img.jpg
# train_ds = datasets.ImageFolder('data/train', transform=train_transform)
# val_ds = datasets.ImageFolder('data/val', transform=val_transform)

# EfficientNet-B0 (best accuracy/speed tradeoff)
model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)

# Replace classifier
num_classes = 10
model.classifier = nn.Sequential(
    nn.Dropout(0.3),
    nn.Linear(model.classifier[1].in_features, num_classes)
)

# Progressive unfreezing strategy
def freeze_except_classifier(model):
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True

def unfreeze_all(model):
    for param in model.parameters():
        param.requires_grad = True

# Phase 1: Train classifier only
freeze_except_classifier(model)
optimizer = torch.optim.Adam(model.classifier.parameters(), lr=1e-3)

# Phase 2: Unfreeze all, lower LR
unfreeze_all(model)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=10)

print(f"Model params: {sum(p.numel() for p in model.parameters()):,}")
```

### 6.2 Object Detection — YOLOv8

```python
from ultralytics import YOLO
import cv2
from pathlib import Path

# Load pretrained YOLOv8
model = YOLO('yolov8n.pt')  # nano (fast) | s | m | l | x (accurate)

# Inference on image
results = model('path/to/image.jpg', conf=0.5)

# Process results
for result in results:
    boxes = result.boxes
    for box in boxes:
        # Bounding box coordinates
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        confidence = box.conf[0].item()
        class_id = int(box.cls[0].item())
        class_name = model.names[class_id]
        print(f"  {class_name}: {confidence:.2f} at [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]")

# Inference on video
results = model('path/to/video.mp4', stream=True)
for frame_result in results:
    annotated = frame_result.plot()  # Draw boxes on frame
    cv2.imshow('YOLO', annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Fine-tune on custom dataset (YOLO format)
"""
Dataset structure:
  dataset/
    train/
      images/
      labels/  (txt files: class_id x_center y_center width height)
    val/
      images/
      labels/
    data.yaml
"""

# Train custom model
model = YOLO('yolov8s.pt')
results = model.train(
    data='dataset/data.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    patience=20,
    device='0',  # GPU
    augment=True,
    mosaic=1.0,
    mixup=0.1,
)

# Export for deployment
model.export(format='onnx')  # or 'tensorrt', 'coreml', 'tflite'
```

### 6.3 Image Segmentation — SAM (Segment Anything)

```python
from segment_anything import sam_model_registry, SamPredictor, SamAutomaticMaskGenerator
import cv2
import numpy as np

# Load SAM
sam = sam_model_registry["vit_h"](checkpoint="sam_vit_h_4b8939.pth")
sam.to(device="cuda")

# === Point-based prompting ===
predictor = SamPredictor(sam)

image = cv2.imread("image.jpg")
image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
predictor.set_image(image_rgb)

# Provide point prompts (x, y coordinates)
input_points = np.array([[500, 375], [600, 400]])  # Positive points
input_labels = np.array([1, 1])  # 1 = foreground, 0 = background

masks, scores, logits = predictor.predict(
    point_coords=input_points,
    point_labels=input_labels,
    multimask_output=True  # Returns 3 masks at different granularities
)

# Best mask
best_mask = masks[np.argmax(scores)]
print(f"Best mask score: {scores.max():.3f}")
print(f"Mask shape: {best_mask.shape}")  # (H, W) boolean

# === Automatic mask generation (segment everything) ===
mask_generator = SamAutomaticMaskGenerator(
    model=sam,
    points_per_side=32,
    pred_iou_thresh=0.88,
    stability_score_thresh=0.95,
    min_mask_region_area=100,
)

masks = mask_generator.generate(image_rgb)
print(f"Found {len(masks)} masks")
for mask in sorted(masks, key=lambda x: x['area'], reverse=True)[:5]:
    print(f"  Area: {mask['area']}, Score: {mask['predicted_iou']:.3f}")
```

### 6.4 OpenCV — Classical Computer Vision

```python
import cv2
import numpy as np

# === Edge Detection ===
img = cv2.imread('image.jpg', cv2.IMREAD_GRAYSCALE)

# Canny edge detection
edges = cv2.Canny(img, threshold1=50, threshold2=150)

# Sobel gradients
sobel_x = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
sobel_y = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
gradient_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)

# === Contour Detection ===
img_color = cv2.imread('image.jpg')
gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
cv2.drawContours(img_color, contours, -1, (0, 255, 0), 2)

# === Feature Matching (SIFT) ===
img1 = cv2.imread('image1.jpg', cv2.IMREAD_GRAYSCALE)
img2 = cv2.imread('image2.jpg', cv2.IMREAD_GRAYSCALE)

sift = cv2.SIFT_create()
kp1, des1 = sift.detectAndCompute(img1, None)
kp2, des2 = sift.detectAndCompute(img2, None)

# FLANN-based matcher
index_params = dict(algorithm=1, trees=5)  # FLANN_INDEX_KDTREE
search_params = dict(checks=50)
flann = cv2.FlannBasedMatcher(index_params, search_params)
matches = flann.knnMatch(des1, des2, k=2)

# Lowe's ratio test
good_matches = [m for m, n in matches if m.distance < 0.7 * n.distance]
print(f"Good matches: {len(good_matches)} / {len(matches)}")

# === Homography (Perspective Transform) ===
if len(good_matches) >= 4:
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    print(f"Homography matrix:\n{H}")

# === Optical Flow (Motion Detection) ===
cap = cv2.VideoCapture('video.mp4')
ret, prev_frame = cap.read()
prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Dense optical flow (Farneback)
    flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    
    prev_gray = gray
cap.release()
```

---

## 7. RAG Pipeline

### 7.1 Complete RAG with LangChain + ChromaDB

```python
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.llms import HuggingFacePipeline
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# === Step 1: Load Documents ===
loader = DirectoryLoader(
    './docs/',
    glob="**/*.md",
    loader_cls=TextLoader
)
documents = loader.load()
print(f"Loaded {len(documents)} documents")

# === Step 2: Chunk Documents ===
splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,           # Characters per chunk
    chunk_overlap=50,         # Overlap between chunks
    separators=["\n\n", "\n", ". ", " ", ""],  # Split hierarchy
    length_function=len,
)
chunks = splitter.split_documents(documents)
print(f"Created {len(chunks)} chunks")

# === Step 3: Create Embeddings & Vector Store ===
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db",
    collection_name="my_docs"
)
vectorstore.persist()

# === Step 4: Build RAG Chain ===
retriever = vectorstore.as_retriever(
    search_type="mmr",        # Maximal Marginal Relevance (diversity + relevance)
    search_kwargs={
        "k": 5,              # Top-K results
        "fetch_k": 20,       # Candidates before MMR reranking
        "lambda_mult": 0.7   # 1.0 = pure relevance, 0.0 = pure diversity
    }
)

# Custom prompt template
template = """Use the following context to answer the question. 
If you cannot answer from the context, say "I don't have enough information."

Context:
{context}

Question: {question}

Answer:"""

prompt = PromptTemplate(template=template, input_variables=["context", "question"])

# === Step 5: Query ===
# With OpenAI
from langchain.chat_models import ChatOpenAI
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",  # Stuff all chunks into context
    retriever=retriever,
    return_source_documents=True,
    chain_type_kwargs={"prompt": prompt}
)

result = qa_chain({"query": "How does attention mechanism work?"})
print(f"Answer: {result['result']}")
print(f"\nSources:")
for doc in result['source_documents']:
    print(f"  - {doc.metadata['source']}: {doc.page_content[:100]}...")
```

### 7.2 RAG from Scratch (No Framework)

```python
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from typing import List, Tuple

class SimpleRAG:
    """Minimal RAG pipeline without LangChain dependency"""
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.encoder = SentenceTransformer(embedding_model)
        self.index = None
        self.documents: List[str] = []
    
    def add_documents(self, texts: List[str], chunk_size: int = 500):
        """Chunk and index documents"""
        # Simple chunking
        chunks = []
        for text in texts:
            words = text.split()
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                chunks.append(chunk)
        
        self.documents = chunks
        
        # Encode all chunks
        embeddings = self.encoder.encode(chunks, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype='float32')
        
        # Build FAISS index (Inner Product = Cosine Similarity for normalized vectors)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)
        
        print(f"Indexed {len(chunks)} chunks ({dim}D embeddings)")
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Retrieve most relevant chunks"""
        query_emb = self.encoder.encode([query], normalize_embeddings=True)
        query_emb = np.array(query_emb, dtype='float32')
        
        scores, indices = self.index.search(query_emb, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.documents):
                results.append((self.documents[idx], float(score)))
        
        return results
    
    def query(self, question: str, top_k: int = 3) -> str:
        """Retrieve context and format for LLM"""
        results = self.retrieve(question, top_k)
        
        context = "\n\n".join([
            f"[Relevance: {score:.3f}]\n{text}" 
            for text, score in results
        ])
        
        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {question}

Answer:"""
        
        return prompt  # Send this to your LLM


# Usage
rag = SimpleRAG()
documents = [
    "Transformers use self-attention to process sequences in parallel...",
    "Convolutional neural networks apply filters to detect spatial patterns...",
    "Random forests combine multiple decision trees using bagging..."
]
rag.add_documents(documents)

prompt = rag.query("How do transformers process text?")
print(prompt)
```

---

## 8. MLOps Patterns

### 8.1 Experiment Tracking with MLflow

```python
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, f1_score

# Setup
mlflow.set_tracking_uri("http://localhost:5000")  # or "mlruns" for local
mlflow.set_experiment("iris-classification")

data = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    data.data, data.target, test_size=0.2, random_state=42
)

# Run experiment
with mlflow.start_run(run_name="random-forest-v1"):
    # Log parameters
    params = {
        "n_estimators": 100,
        "max_depth": 5,
        "min_samples_leaf": 2,
        "random_state": 42
    }
    mlflow.log_params(params)
    
    # Train
    model = RandomForestClassifier(**params)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1_weighted": f1_score(y_test, y_pred, average='weighted'),
        "cv_score_mean": cross_val_score(model, X_train, y_train, cv=5).mean()
    }
    mlflow.log_metrics(metrics)
    
    # Log model
    mlflow.sklearn.log_model(
        model, "model",
        registered_model_name="iris-classifier"
    )
    
    # Log artifacts (plots, configs, etc.)
    # mlflow.log_artifact("feature_importance.png")
    
    print(f"Run ID: {mlflow.active_run().info.run_id}")
    print(f"Metrics: {metrics}")

# Load model for inference
model_uri = "models:/iris-classifier/latest"
loaded_model = mlflow.sklearn.load_model(model_uri)
predictions = loaded_model.predict(X_test[:5])
```

### 8.2 Model Serving with FastAPI

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
import joblib
from typing import List
import logging

app = FastAPI(title="ML Model API", version="1.0.0")
logger = logging.getLogger(__name__)

# Load model at startup
model = None

@app.on_event("startup")
async def load_model():
    global model
    model = joblib.load("model.pkl")
    logger.info("Model loaded successfully")

# Request/Response schemas
class PredictionRequest(BaseModel):
    features: List[List[float]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "features": [[5.1, 3.5, 1.4, 0.2], [6.2, 2.8, 4.8, 1.8]]
            }
        }

class PredictionResponse(BaseModel):
    predictions: List[int]
    probabilities: List[List[float]]
    model_version: str = "1.0.0"

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    try:
        X = np.array(request.features)
        predictions = model.predict(X).tolist()
        probabilities = model.predict_proba(X).tolist()
        
        return PredictionResponse(
            predictions=predictions,
            probabilities=probabilities
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": model is not None}

# Run: uvicorn app:app --host 0.0.0.0 --port 8000
```

### 8.3 Data & Model Drift Detection

```python
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class DriftResult:
    feature_name: str
    statistic: float
    p_value: float
    is_drifted: bool
    drift_type: str

class DriftDetector:
    """Production drift detection for tabular data"""
    
    def __init__(self, reference_data: np.ndarray, feature_names: List[str], 
                 significance_level: float = 0.05):
        self.reference = reference_data
        self.feature_names = feature_names
        self.alpha = significance_level
    
    def detect_data_drift(self, current_data: np.ndarray) -> List[DriftResult]:
        """Kolmogorov-Smirnov test for each feature"""
        results = []
        
        for i, name in enumerate(self.feature_names):
            ref_col = self.reference[:, i]
            cur_col = current_data[:, i]
            
            # KS test (non-parametric, works for any distribution)
            statistic, p_value = stats.ks_2samp(ref_col, cur_col)
            
            results.append(DriftResult(
                feature_name=name,
                statistic=statistic,
                p_value=p_value,
                is_drifted=p_value < self.alpha,
                drift_type="data_drift"
            ))
        
        return results
    
    def detect_prediction_drift(self, reference_preds: np.ndarray, 
                                 current_preds: np.ndarray) -> DriftResult:
        """Chi-squared test for prediction distribution shift"""
        # Bin predictions
        bins = np.linspace(
            min(reference_preds.min(), current_preds.min()),
            max(reference_preds.max(), current_preds.max()),
            20
        )
        
        ref_hist, _ = np.histogram(reference_preds, bins=bins)
        cur_hist, _ = np.histogram(current_preds, bins=bins)
        
        # Add small constant to avoid division by zero
        ref_hist = ref_hist + 1
        cur_hist = cur_hist + 1
        
        statistic, p_value = stats.chisquare(cur_hist, ref_hist)
        
        return DriftResult(
            feature_name="predictions",
            statistic=statistic,
            p_value=p_value,
            is_drifted=p_value < self.alpha,
            drift_type="prediction_drift"
        )
    
    def compute_psi(self, reference: np.ndarray, current: np.ndarray, 
                    n_bins: int = 10) -> float:
        """
        Population Stability Index (PSI)
        PSI < 0.1: No shift
        0.1 < PSI < 0.2: Moderate shift
        PSI > 0.2: Significant shift
        """
        # Create bins from reference
        bins = np.percentile(reference, np.linspace(0, 100, n_bins + 1))
        bins[0] = -np.inf
        bins[-1] = np.inf
        
        ref_percents = np.histogram(reference, bins=bins)[0] / len(reference)
        cur_percents = np.histogram(current, bins=bins)[0] / len(current)
        
        # Avoid log(0)
        ref_percents = np.clip(ref_percents, 0.001, None)
        cur_percents = np.clip(cur_percents, 0.001, None)
        
        psi = np.sum((cur_percents - ref_percents) * np.log(cur_percents / ref_percents))
        return psi


# Usage
np.random.seed(42)
reference = np.random.randn(1000, 4)  # Training distribution
current = np.random.randn(500, 4) + 0.5  # Shifted distribution

detector = DriftDetector(reference, ['feat_1', 'feat_2', 'feat_3', 'feat_4'])
results = detector.detect_data_drift(current)

print("Data Drift Report:")
print("-" * 60)
for r in results:
    status = "⚠️  DRIFT" if r.is_drifted else "✓ OK"
    print(f"  {r.feature_name:15s} | KS={r.statistic:.4f} | p={r.p_value:.4f} | {status}")

# PSI
for i, name in enumerate(['feat_1', 'feat_2', 'feat_3', 'feat_4']):
    psi = detector.compute_psi(reference[:, i], current[:, i])
    print(f"  {name} PSI: {psi:.4f}")
```

---

## 9. Full End-to-End Pipeline

### 9.1 Complete ML Pipeline (Tabular Data)

```python
"""
Complete production ML pipeline: Data → Features → Model → Evaluation → Deploy
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectFromModel
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, roc_auc_score, confusion_matrix,
    precision_recall_curve, average_precision_score
)
import warnings
warnings.filterwarnings('ignore')

# === 1. LOAD & EXPLORE ===
# Using a synthetic dataset for demonstration
from sklearn.datasets import make_classification
X, y = make_classification(
    n_samples=5000, n_features=20, n_informative=10,
    n_redundant=5, n_classes=2, weights=[0.7, 0.3],  # Imbalanced!
    random_state=42
)
feature_names = [f'feat_{i}' for i in range(20)]
df = pd.DataFrame(X, columns=feature_names)
df['target'] = y

print(f"Dataset shape: {df.shape}")
print(f"Target distribution:\n{df['target'].value_counts(normalize=True)}")

# === 2. TRAIN/TEST SPLIT (stratified) ===
X = df.drop('target', axis=1)
y = df['target']
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# === 3. PREPROCESSING PIPELINE ===
# For this demo all features are numeric; in real data you'd have categorical too
numeric_features = feature_names
# categorical_features = ['cat_col1', 'cat_col2']

numeric_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

# If you have categorical features:
# categorical_transformer = Pipeline([
#     ('imputer', SimpleImputer(strategy='most_frequent')),
#     ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
# ])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        # ('cat', categorical_transformer, categorical_features),
    ],
    remainder='drop'
)

# === 4. MODEL COMPARISON ===
models = {
    'Logistic Regression': LogisticRegression(
        C=1.0, class_weight='balanced', max_iter=1000, random_state=42
    ),
    'Random Forest': RandomForestClassifier(
        n_estimators=200, max_depth=10, class_weight='balanced',
        n_jobs=-1, random_state=42
    ),
    'Gradient Boosting': GradientBoostingClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, random_state=42
    )
}

print("\n" + "=" * 70)
print("MODEL COMPARISON (5-Fold Stratified CV)")
print("=" * 70)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
best_model_name = None
best_score = 0

for name, model in models.items():
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', model)
    ])
    
    scores = cross_validate(
        pipeline, X_train, y_train, cv=cv,
        scoring=['accuracy', 'roc_auc', 'f1', 'precision', 'recall'],
        n_jobs=-1
    )
    
    roc_auc = scores['test_roc_auc'].mean()
    print(f"\n{name}:")
    print(f"  Accuracy:  {scores['test_accuracy'].mean():.4f} ± {scores['test_accuracy'].std():.4f}")
    print(f"  ROC-AUC:   {roc_auc:.4f} ± {scores['test_roc_auc'].std():.4f}")
    print(f"  F1:        {scores['test_f1'].mean():.4f} ± {scores['test_f1'].std():.4f}")
    print(f"  Precision: {scores['test_precision'].mean():.4f}")
    print(f"  Recall:    {scores['test_recall'].mean():.4f}")
    
    if roc_auc > best_score:
        best_score = roc_auc
        best_model_name = name

# === 5. FINAL MODEL TRAINING & EVALUATION ===
print(f"\n{'=' * 70}")
print(f"BEST MODEL: {best_model_name} (ROC-AUC: {best_score:.4f})")
print(f"{'=' * 70}")

final_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', models[best_model_name])
])
final_pipeline.fit(X_train, y_train)

# Test set evaluation
y_pred = final_pipeline.predict(X_test)
y_proba = final_pipeline.predict_proba(X_test)[:, 1]

print(f"\nTest Set Results:")
print(classification_report(y_test, y_pred, digits=4))
print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.4f}")
print(f"Average Precision: {average_precision_score(y_test, y_proba):.4f}")

# === 6. FEATURE IMPORTANCE ===
if hasattr(final_pipeline.named_steps['classifier'], 'feature_importances_'):
    importances = final_pipeline.named_steps['classifier'].feature_importances_
    feat_imp = pd.DataFrame({
        'feature': numeric_features,
        'importance': importances
    }).sort_values('importance', ascending=False)
    
    print(f"\nTop 10 Features:")
    print(feat_imp.head(10).to_string(index=False))

# === 7. SAVE MODEL ===
import joblib
joblib.dump(final_pipeline, 'production_model.pkl')
print(f"\nModel saved to production_model.pkl")

# === 8. INFERENCE FUNCTION ===
def predict_new_data(data: pd.DataFrame) -> dict:
    """Production inference function"""
    model = joblib.load('production_model.pkl')
    predictions = model.predict(data)
    probabilities = model.predict_proba(data)[:, 1]
    return {
        'predictions': predictions.tolist(),
        'probabilities': probabilities.tolist(),
        'threshold': 0.5
    }
```

### 9.2 Complete DL Pipeline (Text Classification with BERT)

```python
"""
End-to-end deep learning pipeline with proper training practices
"""
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModel, get_linear_schedule_with_warmup
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import numpy as np
from tqdm import tqdm
from typing import List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Custom Dataset ===
class TextDataset(Dataset):
    def __init__(self, texts: List[str], labels: List[int], tokenizer, max_length: int = 128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'label': torch.tensor(self.labels[idx], dtype=torch.long)
        }

# === Model ===
class TextClassifier(nn.Module):
    def __init__(self, model_name: str, num_classes: int, dropout: float = 0.3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        hidden_size = self.bert.config.hidden_size
        
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
            nn.Linear(256, num_classes)
        )
    
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        # Use [CLS] token representation
        cls_output = outputs.last_hidden_state[:, 0, :]
        return self.classifier(cls_output)

# === Training ===
class Trainer:
    def __init__(self, model, device, num_classes):
        self.model = model.to(device)
        self.device = device
        self.num_classes = num_classes
    
    def train_epoch(self, dataloader, optimizer, scheduler, criterion):
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        for batch in tqdm(dataloader, desc="Training"):
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            labels = batch['label'].to(self.device)
            
            optimizer.zero_grad()
            outputs = self.model(input_ids, attention_mask)
            loss = criterion(outputs, labels)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            optimizer.step()
            scheduler.step()
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
        
        return total_loss / len(dataloader), correct / total
    
    @torch.no_grad()
    def evaluate(self, dataloader, criterion):
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []
        
        for batch in dataloader:
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            labels = batch['label'].to(self.device)
            
            outputs = self.model(input_ids, attention_mask)
            loss = criterion(outputs, labels)
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
        
        return total_loss / len(dataloader), np.array(all_preds), np.array(all_labels)


# === Main ===
def main():
    # Config
    MODEL_NAME = "bert-base-uncased"
    NUM_CLASSES = 3
    BATCH_SIZE = 32
    EPOCHS = 5
    LR = 2e-5
    MAX_LENGTH = 128
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {device}")
    
    # Sample data (replace with your dataset)
    texts = ["This is great!", "Terrible experience.", "It was okay."] * 100
    labels = [2, 0, 1] * 100  # positive=2, neutral=1, negative=0
    
    # Split
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=42
    )
    
    # Tokenizer and datasets
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_ds = TextDataset(train_texts, train_labels, tokenizer, MAX_LENGTH)
    val_ds = TextDataset(val_texts, val_labels, tokenizer, MAX_LENGTH)
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE * 2, num_workers=2)
    
    # Model
    model = TextClassifier(MODEL_NAME, NUM_CLASSES)
    
    # Optimizer with weight decay (AdamW)
    no_decay = ['bias', 'LayerNorm.weight']
    optimizer_params = [
        {'params': [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
         'weight_decay': 0.01},
        {'params': [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
         'weight_decay': 0.0}
    ]
    optimizer = torch.optim.AdamW(optimizer_params, lr=LR)
    
    # Scheduler with warmup
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    
    criterion = nn.CrossEntropyLoss()
    
    # Training loop
    trainer = Trainer(model, device, NUM_CLASSES)
    best_val_loss = float('inf')
    
    for epoch in range(EPOCHS):
        train_loss, train_acc = trainer.train_epoch(train_loader, optimizer, scheduler, criterion)
        val_loss, val_preds, val_labels_arr = trainer.evaluate(val_loader, criterion)
        
        logger.info(
            f"Epoch {epoch+1}/{EPOCHS} | "
            f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
            f"Val Loss: {val_loss:.4f}"
        )
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), 'best_model.pt')
            logger.info(f"  Saved best model (val_loss: {val_loss:.4f})")
    
    # Final evaluation
    model.load_state_dict(torch.load('best_model.pt'))
    _, preds, labels_arr = trainer.evaluate(val_loader, criterion)
    print("\nFinal Classification Report:")
    print(classification_report(labels_arr, preds, target_names=['Negative', 'Neutral', 'Positive']))

if __name__ == "__main__":
    main()
```

---

## Summary: Which Code to Use When

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CODE SELECTION GUIDE                                   │
├─────────────────────────────────────────┬───────────────────────────────────┤
│ Problem Type                             │ Go To Section                     │
├─────────────────────────────────────────┼───────────────────────────────────┤
│ Tabular classification/regression        │ §1 (sklearn) + §2 (boosting)     │
│ Hyperparameter tuning                    │ §2.4 (Optuna)                    │
│ Custom neural network                    │ §3.2 (PyTorch training loop)     │
│ Image classification                     │ §3.3 (CNN) or §3.4 (transfer)   │
│ Build a Transformer                      │ §4.1 (from scratch)              │
│ Text classification                      │ §5.1 (BERT fine-tune)            │
│ Text generation                          │ §5.2 (GPT-2/LLaMA)              │
│ Named entity recognition                 │ §5.3 (NER pipeline)             │
│ Semantic search / embeddings             │ §5.4 (SentenceTransformers)     │
│ Object detection                         │ §6.2 (YOLOv8)                   │
│ Image segmentation                       │ §6.3 (SAM)                      │
│ Classical CV (edges, features)           │ §6.4 (OpenCV)                   │
│ RAG / document Q&A                       │ §7 (LangChain + from scratch)   │
│ Experiment tracking                      │ §8.1 (MLflow)                   │
│ Model API serving                        │ §8.2 (FastAPI)                  │
│ Drift monitoring                         │ §8.3 (KS test + PSI)           │
│ Full production pipeline                 │ §9 (end-to-end)                 │
└─────────────────────────────────────────┴───────────────────────────────────┘
```

---

## Dependencies (pip install)

```bash
# Core ML
pip install numpy pandas scikit-learn matplotlib seaborn

# Boosting
pip install xgboost lightgbm catboost

# Deep Learning
pip install torch torchvision torchaudio

# NLP
pip install transformers datasets sentence-transformers tokenizers

# Computer Vision
pip install ultralytics opencv-python segment-anything

# RAG
pip install langchain chromadb faiss-cpu

# MLOps
pip install mlflow optuna fastapi uvicorn joblib

# Tuning
pip install optuna

# All-in-one (large install):
# pip install numpy pandas scikit-learn torch torchvision transformers datasets \
#     sentence-transformers xgboost lightgbm catboost ultralytics opencv-python \
#     langchain chromadb faiss-cpu mlflow optuna fastapi uvicorn
```
