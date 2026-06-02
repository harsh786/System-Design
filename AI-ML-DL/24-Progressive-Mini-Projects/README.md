# Progressive Mini-Projects: Build After Every Section

## Philosophy

```
AFTER EACH SECTION: Build something small (30-60 minutes)
WHY: Theory without practice decays. Building cements understanding.
RULE: No project should take more than 1 hour. If stuck > 15 min, read hints.

THE ANTI-PATTERN:
  ❌ Read 500 pages → Try to build → Forgot everything → Re-read

THE PATTERN:
  ✅ Read section → Build mini-project → Concepts STICK → Next section

EVIDENCE: Retention rates
  - Reading only: 10% after 1 week
  - Reading + immediate practice: 75% after 1 week
  - Reading + building + explaining: 90% after 1 week
```

## Ground Rules

```
1. TIMEBOX: Set a timer. 30-60 minutes MAX.
2. HINTS: If stuck > 15 minutes, read the hint. No shame.
3. COMPARE: After building, compare with reference solution.
4. STRETCH: Each project has a stretch goal. Do it ONLY if base is done.
5. DEPENDENCIES: Core = numpy, pandas, sklearn, matplotlib.
                  Optional = torch, transformers, gensim (clearly marked).
6. DATA: Use sklearn built-in datasets or generate synthetic data.
         No downloads, no API keys, no external dependencies.
```

---

## Mini-Projects by Section

---

### After 00-Mathematics-Prerequisites

#### MINI-PROJECT 1: PCA from Scratch on Iris Dataset

```
GOAL: Implement Principal Component Analysis using only NumPy

WHAT TO BUILD:
- Load Iris dataset (sklearn.datasets.load_iris)
- Center the data (subtract mean)
- Compute covariance matrix
- Eigendecomposition (numpy.linalg.eig)
- Select top-2 eigenvectors
- Project data: X_pca = X_centered @ eigenvectors
- Plot 2D result, color by species
- Compare with sklearn.decomposition.PCA

TIME: 30 minutes

STARTER HINT:
  from sklearn.datasets import load_iris
  import numpy as np
  X = load_iris().data  # (150, 4)
  X_centered = X - X.mean(axis=0)
  cov = np.cov(X_centered.T)  # (4, 4)
  eigenvalues, eigenvectors = np.linalg.eig(cov)
  # Sort by eigenvalue descending...

EXPECTED OUTPUT:
- Scatter plot showing 3 distinct clusters (setosa separates clearly)
- Your projection matches sklearn PCA output (maybe flipped sign — that's OK)
- Explained variance ratio: ~[0.73, 0.23] for first 2 components

YOU'LL LEARN: Eigen = directions of maximum variance.
  PCA is not magic — it's just finding the axes where data varies most.

STRETCH GOAL: Implement PCA with SVD instead (np.linalg.svd).
  Show they give the same result. SVD is what sklearn actually uses (numerically stable).
```

---

#### MINI-PROJECT 2: Gradient Descent Visualizer

```
GOAL: Watch gradient descent converge (or diverge!) in real-time

WHAT TO BUILD:
- Define f(x) = x² + 3x + 2 and f'(x) = 2x + 3
- Implement gradient descent: x_new = x_old - lr * gradient
- Run with learning_rate = 0.01, 0.1, 0.5, 1.0
- Plot: the function curve + descent path (dots showing each step)
- Create 4 subplots showing different LR behaviors

TIME: 30 minutes

STARTER HINT:
  def gradient_descent(lr, x_init=-5.0, steps=50):
      path = [x_init]
      x = x_init
      for _ in range(steps):
          grad = 2*x + 3  # derivative of x² + 3x + 2
          x = x - lr * grad
          path.append(x)
      return path

EXPECTED OUTPUT:
- LR=0.01: Slow crawl toward minimum (x = -1.5)
- LR=0.1:  Nice smooth convergence in ~15 steps
- LR=0.5:  Oscillates but converges
- LR=1.0:  DIVERGES (x goes to infinity!)

YOU'LL LEARN: LR too high = explode, too low = crawl.
  This exact behavior happens in neural network training.

STRETCH GOAL: Extend to 2D → f(x,y) = x² + y² (bowl shape).
  Visualize descent path on contour plot. Add momentum and compare.
```

---

#### MINI-PROJECT 3: Probability Simulator

```
GOAL: Prove probability theorems through brute-force simulation

WHAT TO BUILD:
Part A - Monty Hall Problem:
  - Simulate 10000 games
  - Strategy 1: Always stay (should win ~33%)
  - Strategy 2: Always switch (should win ~67%)
  - Print results

Part B - Central Limit Theorem:
  - Draw samples of size 30 from Uniform(0,1) — 5000 times
  - Compute mean of each sample
  - Plot histogram of sample means → should look Gaussian!
  - Overlay theoretical Normal distribution

TIME: 20 minutes

STARTER HINT:
  # Monty Hall
  import numpy as np
  def simulate_monty_hall(n=10000, switch=True):
      wins = 0
      for _ in range(n):
          car = np.random.randint(3)
          choice = np.random.randint(3)
          # Host opens a door (not car, not choice)
          if switch:
              # Player switches to the remaining door
              wins += (choice != car)  # switching wins when initial was wrong
          else:
              wins += (choice == car)
      return wins / n

EXPECTED OUTPUT:
- "Stay wins: 33.2%  |  Switch wins: 66.8%"
- Histogram of sample means: bell curve centered at 0.5

YOU'LL LEARN: Intuition for probability through simulation.
  When math is confusing, simulate 10000 times and COUNT.

STRETCH GOAL: Simulate the Birthday Problem.
  How many people needed for 50% chance of shared birthday? (Answer: ~23)
```

---

### After 01-Python-and-Data-Science-Foundations

#### MINI-PROJECT 4: EDA Report Generator

```
GOAL: Build a reusable EDA function that gives you instant data understanding

WHAT TO BUILD:
- Load Titanic dataset (seaborn.load_dataset('titanic') or sklearn)
- Create function: generate_eda_report(df)
  - Print: shape, dtypes, memory usage
  - Missing values: column name, count, percentage
  - Numeric: describe() + skewness
  - Categorical: value_counts for top categories
- Create 5 plots:
  1. Missing value heatmap (sns.heatmap on df.isnull())
  2. Distribution of numeric columns (histograms)
  3. Correlation heatmap
  4. Target variable distribution
  5. One bivariate relationship
- Write 3 insights as code comments

TIME: 45 minutes

STARTER HINT:
  import seaborn as sns
  import pandas as pd
  import matplotlib.pyplot as plt
  
  df = sns.load_dataset('titanic')
  
  def eda_report(df):
      print(f"Shape: {df.shape}")
      print(f"\nMissing Values:")
      missing = df.isnull().sum()
      print(missing[missing > 0])
      # Continue...

EXPECTED OUTPUT:
- Console output: shape (891,15), Age missing 19.9%, deck missing 77.2%
- 5 publication-quality plots
- Insights like: "Survival rate: 38.4%. Females survived at 74.2% vs males 18.9%"

YOU'LL LEARN: EDA workflow becomes automatic.
  After 5 datasets, you'll do this in your sleep.

STRETCH GOAL: Package as a class with .to_html() method that creates
  a self-contained HTML report (like pandas-profiling but yours).
```

---

#### MINI-PROJECT 5: Feature Engineering Pipeline

```
GOAL: Build a complete, leak-free preprocessing pipeline

WHAT TO BUILD:
- Load Titanic data
- Engineer features:
  - Age_Bin: (Child, Teen, Adult, Senior)
  - Family_Size: SibSp + Parch + 1
  - Is_Alone: Family_Size == 1
  - Title: extract from Name (Mr, Mrs, Miss, Master, Rare)
  - Cabin_Letter: first character of Cabin (or 'Unknown')
  - Fare_Per_Person: Fare / Family_Size
- Handle missing values (Age: median, Embarked: mode, Cabin: 'Unknown')
- Build sklearn Pipeline:
  - ColumnTransformer for numeric vs categorical
  - StandardScaler for numeric
  - OneHotEncoder for categorical
  - Train a model at the end

TIME: 45 minutes

STARTER HINT:
  from sklearn.pipeline import Pipeline
  from sklearn.compose import ColumnTransformer
  from sklearn.preprocessing import StandardScaler, OneHotEncoder
  from sklearn.impute import SimpleImputer
  
  numeric_features = ['Age', 'Fare', 'Family_Size']
  categorical_features = ['Sex', 'Embarked', 'Title']
  
  numeric_transformer = Pipeline([
      ('imputer', SimpleImputer(strategy='median')),
      ('scaler', StandardScaler())
  ])

EXPECTED OUTPUT:
- Pipeline that transforms raw data → model-ready features in one .fit_transform()
- No data leakage (all fitting happens on train only)
- Model accuracy: ~80-82% on Titanic

YOU'LL LEARN: Pipelines prevent data leakage.
  fit_transform(train) then transform(test) — never the other way.

STRETCH GOAL: Add custom transformer class (BaseEstimator, TransformerMixin)
  that creates Title feature inside the pipeline.
```

---

### After 02-Machine-Learning (Supervised)

#### MINI-PROJECT 6: Classifier Shootout

```
GOAL: Fairly compare 5 classifiers on the same data with cross-validation

WHAT TO BUILD:
- Load dataset (sklearn.datasets: breast_cancer, wine, or digits)
- Define 5 classifiers with default params:
  1. LogisticRegression
  2. SVC (support vector)
  3. RandomForestClassifier
  4. KNeighborsClassifier
  5. GaussianNB
- Cross-validate each (5-fold, scoring='accuracy')
- Collect mean ± std for each
- Plot bar chart with error bars
- Print winner

TIME: 30 minutes

STARTER HINT:
  from sklearn.model_selection import cross_val_score
  from sklearn.datasets import load_breast_cancer
  
  X, y = load_breast_cancer(return_X_y=True)
  
  classifiers = {
      'LogReg': LogisticRegression(max_iter=10000),
      'SVM': SVC(),
      'RF': RandomForestClassifier(n_estimators=100),
      'KNN': KNeighborsClassifier(),
      'NB': GaussianNB()
  }
  
  results = {}
  for name, clf in classifiers.items():
      scores = cross_val_score(clf, X, y, cv=5)
      results[name] = (scores.mean(), scores.std())

EXPECTED OUTPUT:
- Bar chart showing all 5 classifiers
- Typical results on breast_cancer: LogReg~0.95, SVM~0.92, RF~0.96, KNN~0.93, NB~0.94
- Winner: Random Forest (usually) or Logistic Regression (sometimes)

YOU'LL LEARN: Different algorithms suit different data.
  There's no universally best classifier — always benchmark.

STRETCH GOAL: Add preprocessing (StandardScaler) inside cross-validation
  using Pipeline. Watch SVM jump from 0.92 to 0.97!
```

---

#### MINI-PROJECT 7: From-Scratch Logistic Regression

```
GOAL: Implement logistic regression with gradient descent (NumPy only)

WHAT TO BUILD:
- Sigmoid function: σ(z) = 1 / (1 + exp(-z))
- Loss function: binary cross-entropy
- Gradient computation: ∂L/∂w = (1/n) * X.T @ (predictions - y)
- Training loop: for each epoch, compute loss, compute gradient, update weights
- Train on breast cancer dataset (standardize first!)
- Plot loss curve over epochs
- Compare accuracy with sklearn LogisticRegression

TIME: 45 minutes

STARTER HINT:
  class LogisticRegressionScratch:
      def __init__(self, lr=0.01, epochs=1000):
          self.lr = lr
          self.epochs = epochs
      
      def sigmoid(self, z):
          return 1 / (1 + np.exp(-np.clip(z, -500, 500)))
      
      def fit(self, X, y):
          n, d = X.shape
          self.w = np.zeros(d)
          self.b = 0
          self.losses = []
          
          for _ in range(self.epochs):
              z = X @ self.w + self.b
              pred = self.sigmoid(z)
              loss = -np.mean(y*np.log(pred+1e-8) + (1-y)*np.log(1-pred+1e-8))
              self.losses.append(loss)
              
              dw = (1/n) * X.T @ (pred - y)
              db = np.mean(pred - y)
              self.w -= self.lr * dw
              self.b -= self.lr * db

EXPECTED OUTPUT:
- Loss curve: starts ~0.7, drops to ~0.1 over 1000 epochs
- Your accuracy: ~96-97% (within 1-2% of sklearn)
- sklearn accuracy: ~97%

YOU'LL LEARN: How optimization actually finds the solution.
  Gradient descent is just "step in the direction that reduces loss."

STRETCH GOAL: Add L2 regularization. Compare coefficients with/without.
  Regularized weights should be smaller.
```

---

#### MINI-PROJECT 8: Hyperparameter Tuning Lab

```
GOAL: Compare 3 hyperparameter search strategies head-to-head

WHAT TO BUILD:
- Load breast_cancer or digits dataset
- Define Random Forest with tunable params:
  - n_estimators: [50, 100, 200, 300, 500]
  - max_depth: [5, 10, 15, 20, None]
  - min_samples_split: [2, 5, 10]
  - min_samples_leaf: [1, 2, 4]
- Run:
  1. GridSearchCV (exhaustive — will be slow!)
  2. RandomizedSearchCV (n_iter=20)
  3. Optuna (20 trials) [optional — install optuna]
- Compare: best score achieved, time taken
- Plot learning curve for the best model found

TIME: 45 minutes

STARTER HINT:
  from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
  import time
  
  param_grid = {
      'n_estimators': [50, 100, 200, 300, 500],
      'max_depth': [5, 10, 15, 20, None],
      'min_samples_split': [2, 5, 10],
      'min_samples_leaf': [1, 2, 4]
  }
  
  # Grid Search
  start = time.time()
  grid = GridSearchCV(RandomForestClassifier(), param_grid, cv=3, n_jobs=-1)
  grid.fit(X, y)
  grid_time = time.time() - start

EXPECTED OUTPUT:
- Grid: tries all 300 combos, takes ~60s, finds score 0.968
- Random: tries 20 combos, takes ~5s, finds score 0.965
- Optuna: tries 20 combos, takes ~6s, finds score 0.970
- LESSON: Random gets 99% of the benefit in 7% of the time

YOU'LL LEARN: Random > Grid (usually), Optuna > both (smart search).
  Grid is exponential; random samples the space efficiently.

STRETCH GOAL: Implement Bayesian optimization from scratch (Gaussian Process
  to model score as function of hyperparameters). Hard but illuminating.
```

---

### After 02-Machine-Learning (Unsupervised)

#### MINI-PROJECT 9: Customer Segmentation

```
GOAL: Cluster synthetic customers and make the clusters MEANINGFUL

WHAT TO BUILD:
- Generate synthetic data (300 customers):
  - Age: mix of distributions (young 20-30, middle 35-50, senior 55-70)
  - Income: correlated with age + noise
  - Spending_Score: random 1-100
- Standardize features
- Elbow method: plot inertia for K=2 to K=10
- Silhouette analysis for optimal K
- Apply K-Means with optimal K
- Profile clusters (mean age, income, spending per cluster)
- NAME your clusters (e.g., "Young High Spenders", "Wealthy Conservatives")
- Visualize with PCA → 2D colored by cluster

TIME: 45 minutes

STARTER HINT:
  from sklearn.cluster import KMeans
  from sklearn.preprocessing import StandardScaler
  
  # Generate data
  np.random.seed(42)
  n = 300
  age = np.concatenate([np.random.normal(25,3,100),
                        np.random.normal(42,5,100),
                        np.random.normal(60,5,100)])
  income = age * 1000 + np.random.normal(0, 5000, n)
  spending = np.random.randint(1, 100, n)
  
  X = np.column_stack([age, income, spending])
  X_scaled = StandardScaler().fit_transform(X)

EXPECTED OUTPUT:
- Elbow plot shows bend at K=3 or K=4
- Silhouette score: ~0.45-0.55 (good clustering)
- Cluster profiles:
  - Cluster 0: "Young Budget" (age~25, income~25k, spending~50)
  - Cluster 1: "Middle Affluent" (age~42, income~42k, spending~55)
  - Cluster 2: "Senior Wealthy" (age~60, income~60k, spending~45)

YOU'LL LEARN: Clustering is only useful if you can INTERPRET it.
  K-means gives numbers; YOU give meaning.

STRETCH GOAL: Apply DBSCAN and compare. Does it find the same clusters?
  Try adding outliers and see which algorithm handles them better.
```

---

#### MINI-PROJECT 10: Anomaly Detector

```
GOAL: Build and compare 3 anomaly detection methods

WHAT TO BUILD:
- Create synthetic "normal" data: 2D Gaussian (1000 points)
- Inject anomalies: 50 points scattered far from center
- Apply 3 methods:
  1. Z-score: flag if |z| > 3 on any dimension
  2. Isolation Forest (sklearn)
  3. Local Outlier Factor (sklearn)
- For each: compute precision, recall, F1 for anomaly detection
- Visualize: 2D scatter, anomalies highlighted in red

TIME: 30 minutes

STARTER HINT:
  from sklearn.ensemble import IsolationForest
  from sklearn.neighbors import LocalOutlierFactor
  
  # Generate data
  np.random.seed(42)
  normal = np.random.randn(1000, 2)  # cluster at origin
  anomalies = np.random.uniform(-6, 6, (50, 2))  # scattered
  X = np.vstack([normal, anomalies])
  y_true = np.array([0]*1000 + [1]*50)  # 0=normal, 1=anomaly
  
  # Isolation Forest
  iso = IsolationForest(contamination=0.05, random_state=42)
  y_pred_iso = iso.fit_predict(X)  # -1 = anomaly, 1 = normal

EXPECTED OUTPUT:
- Z-score: catches distant points but misses subtle ones (recall ~70%)
- Isolation Forest: good overall (F1 ~0.85)
- LOF: great for local anomalies (F1 ~0.80)
- Visualization clearly shows detected vs missed anomalies

YOU'LL LEARN: Different methods catch different anomaly types.
  Z-score = global outliers, LOF = local density deviations, IF = general.

STRETCH GOAL: Add a third cluster of data and inject anomalies BETWEEN clusters.
  Watch LOF outperform Isolation Forest in this scenario.
```

---

### After 03-Deep-Learning

#### MINI-PROJECT 11: Neural Network from Scratch (XOR)

```
GOAL: Implement a working neural network with ONLY NumPy

WHAT TO BUILD:
- 2-layer neural network: Input(2) → Hidden(4, ReLU) → Output(1, Sigmoid)
- Forward pass: compute activations layer by layer
- Loss: binary cross-entropy
- Backward pass: compute gradients via chain rule
- Update: SGD (w = w - lr * gradient)
- Train on XOR: [[0,0],[0,1],[1,0],[1,1]] → [0,1,1,0]
- Plot: loss curve + decision boundary

TIME: 60 minutes

STARTER HINT:
  class NeuralNetwork:
      def __init__(self):
          # Xavier initialization
          self.W1 = np.random.randn(2, 4) * 0.5
          self.b1 = np.zeros((1, 4))
          self.W2 = np.random.randn(4, 1) * 0.5
          self.b2 = np.zeros((1, 1))
      
      def forward(self, X):
          self.z1 = X @ self.W1 + self.b1
          self.a1 = np.maximum(0, self.z1)  # ReLU
          self.z2 = self.a1 @ self.W2 + self.b2
          self.a2 = 1 / (1 + np.exp(-self.z2))  # Sigmoid
          return self.a2
      
      def backward(self, X, y, output):
          m = X.shape[0]
          # Output layer gradient
          dz2 = output - y  # (4,1)
          dW2 = self.a1.T @ dz2 / m
          db2 = np.sum(dz2, axis=0, keepdims=True) / m
          # Hidden layer gradient
          dz1 = (dz2 @ self.W2.T) * (self.z1 > 0)  # ReLU derivative
          dW1 = X.T @ dz1 / m
          db1 = np.sum(dz1, axis=0, keepdims=True) / m
          return dW1, db1, dW2, db2

EXPECTED OUTPUT:
- Loss starts ~0.7, drops to ~0.01 within 1000 epochs
- Final predictions: [0.02, 0.98, 0.97, 0.03] (close to [0,1,1,0])
- Decision boundary shows non-linear separation!
- This CANNOT be solved by a single perceptron (no hidden layer)

YOU'LL LEARN: Backprop is just chain rule applied repeatedly.
  Hidden layers enable non-linear decision boundaries.

STRETCH GOAL: Replace ReLU with different activations (tanh, leaky ReLU).
  Compare convergence speed. Add a second hidden layer — does it help for XOR?
```

---

#### MINI-PROJECT 12: CNN on Fashion-MNIST

```
GOAL: Build and train a CNN that classifies clothing items

WHAT TO BUILD:
- Load Fashion-MNIST (torchvision.datasets.FashionMNIST)
- Architecture:
  - Conv2d(1, 32, 3, padding=1) → ReLU → MaxPool(2)
  - Conv2d(32, 64, 3, padding=1) → ReLU → MaxPool(2)
  - Flatten → Linear(64*7*7, 128) → ReLU → Linear(128, 10)
- Train for 5-10 epochs with Adam optimizer
- Target: >88% test accuracy
- Visualize:
  - First layer filters (what patterns does Conv1 detect?)
  - Confusion matrix
  - 10 misclassified examples (what went wrong?)

TIME: 45 minutes (requires PyTorch)

STARTER HINT:
  import torch
  import torch.nn as nn
  from torchvision import datasets, transforms
  
  transform = transforms.Compose([
      transforms.ToTensor(),
      transforms.Normalize((0.5,), (0.5,))
  ])
  
  train_data = datasets.FashionMNIST('./data', train=True, download=True, transform=transform)
  train_loader = torch.utils.data.DataLoader(train_data, batch_size=64, shuffle=True)
  
  class CNN(nn.Module):
      def __init__(self):
          super().__init__()
          self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
          self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
          self.pool = nn.MaxPool2d(2, 2)
          self.fc1 = nn.Linear(64 * 7 * 7, 128)
          self.fc2 = nn.Linear(128, 10)
          # ...

EXPECTED OUTPUT:
- Training: loss drops from ~2.3 to ~0.3 over 5 epochs
- Test accuracy: 88-91%
- Confusion matrix: Shirt/T-shirt/Coat often confused (they look similar!)
- Conv1 filters: edge detectors (horizontal, vertical, diagonal)

YOU'LL LEARN: CNNs learn hierarchical features automatically.
  Layer 1: edges. Layer 2: textures/shapes. FC: combines into categories.

STRETCH GOAL: Add BatchNorm after each conv layer. Add Dropout(0.25) before FC.
  Should push accuracy to 91-92%.
```

---

#### MINI-PROJECT 13: Attention Visualizer

```
GOAL: See what transformer attention actually looks at

WHAT TO BUILD:
- Use a pretrained model (e.g., bert-base-uncased from HuggingFace)
  OR implement simple self-attention from scratch
- Feed a sentence: "The cat sat on the mat because it was tired"
- Extract attention weights from one layer
- Visualize as heatmap: rows=query tokens, columns=key tokens
- Identify: what does "it" attend to? (should be "cat"!)

TIME: 30 minutes (with transformers library) / 45 minutes (from scratch)

STARTER HINT (with HuggingFace):
  from transformers import BertTokenizer, BertModel
  import torch
  
  tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
  model = BertModel.from_pretrained('bert-base-uncased', output_attentions=True)
  
  text = "The cat sat on the mat because it was tired"
  inputs = tokenizer(text, return_tensors='pt')
  outputs = model(**inputs)
  
  # attention shape: (batch, heads, seq_len, seq_len)
  attention = outputs.attentions[-1][0]  # last layer, first batch
  # Average across heads
  avg_attention = attention.mean(dim=0).detach().numpy()

STARTER HINT (from scratch):
  def self_attention(Q, K, V):
      d_k = Q.shape[-1]
      scores = Q @ K.T / np.sqrt(d_k)
      weights = softmax(scores)  # implement softmax
      return weights @ V, weights

EXPECTED OUTPUT:
- Heatmap where each row shows what that token "looks at"
- "it" token strongly attends to "cat" (coreference!)
- "tired" attends to "cat" and "it"
- [CLS] attends broadly (aggregates sentence meaning)

YOU'LL LEARN: Attention = learned relevance between positions.
  It's not magic — it's just scaled dot products determining importance.

STRETCH GOAL: Compare attention across layers (layer 1 vs layer 6 vs layer 12).
  Early layers: local/syntactic. Later layers: semantic/long-range.
```

---

### After 07-LLMs-and-GenAI

#### MINI-PROJECT 14: Build a RAG System (from Scratch)

```
GOAL: Build retrieval-augmented generation without any external APIs

WHAT TO BUILD:
- Prepare 5 "documents" (copy-paste 5 Wikipedia paragraphs on different topics)
- Chunk: split each into sentences or small paragraphs
- Embed: TF-IDF vectorization (sklearn TfidfVectorizer)
- Index: store TF-IDF matrix
- Retrieve: given a query, find top-3 most similar chunks (cosine similarity)
- Generate: format as "Context: [chunks]\nQuestion: [query]\nAnswer:"
- Print the formatted prompt (you'd send this to an LLM)

TIME: 45 minutes

STARTER HINT:
  from sklearn.feature_extraction.text import TfidfVectorizer
  from sklearn.metrics.pairwise import cosine_similarity
  
  # Your "knowledge base"
  documents = [
      "Python is a high-level programming language created by Guido van Rossum...",
      "The Eiffel Tower is a wrought-iron lattice tower in Paris...",
      "Photosynthesis is the process by which plants convert sunlight...",
      # ... more docs
  ]
  
  # Chunk (here docs are already small, but in practice you'd split)
  chunks = documents
  
  # Embed
  vectorizer = TfidfVectorizer()
  chunk_vectors = vectorizer.fit_transform(chunks)
  
  # Retrieve
  def retrieve(query, top_k=3):
      query_vec = vectorizer.transform([query])
      sims = cosine_similarity(query_vec, chunk_vectors)[0]
      top_indices = sims.argsort()[-top_k:][::-1]
      return [chunks[i] for i in top_indices]

EXPECTED OUTPUT:
- Query: "Who created Python?"
- Retrieved: chunk about Python (similarity ~0.45)
- Formatted prompt ready to send to any LLM
- Works WITHOUT any API keys or internet connection!

YOU'LL LEARN: RAG is just search + context formatting.
  The "magic" is in good chunking and good retrieval, not the LLM.

STRETCH GOAL: Replace TF-IDF with sentence-transformers embeddings.
  Compare retrieval quality. TF-IDF = keyword matching; embeddings = semantic.
```

---

#### MINI-PROJECT 15: Prompt Engineering Lab

```
GOAL: Systematically compare prompt strategies on the same task

WHAT TO BUILD:
- Pick a task: classify movie reviews as positive/negative
- Prepare 10 test reviews (5 positive, 5 negative)
- Write 5 prompt variants:
  1. Zero-shot: "Classify this review as positive or negative: {review}"
  2. Few-shot: provide 2 examples first, then ask
  3. Chain-of-thought: "First identify key sentiment words, then classify..."
  4. Role-based: "You are a senior film critic. Classify..."
  5. Structured: "Return JSON: {sentiment: pos/neg, confidence: 0-1, reason: str}"
- Run each prompt on all 10 reviews (requires LLM API or local model)
- Score: accuracy, consistency, output quality
- Create comparison table

TIME: 30 minutes (requires LLM access — API or local like Ollama)

STARTER HINT:
  prompts = {
      "zero_shot": "Classify as positive or negative:\n\n{review}\n\nSentiment:",
      "few_shot": """Examples:
  Review: "This movie was absolutely wonderful!" → positive
  Review: "Terrible waste of time." → negative
  
  Now classify:
  Review: "{review}" → """,
      "cot": """Analyze this review step by step:
  1. Identify sentiment words
  2. Determine overall tone
  3. Give final classification
  
  Review: {review}""",
  }
  
  # If no API available, manually evaluate by reading prompts
  # and predicting what an LLM would output

EXPECTED OUTPUT:
- Zero-shot: 7/10 correct, sometimes outputs extra text
- Few-shot: 9/10 correct, more consistent format
- CoT: 8/10 correct, provides reasoning (easier to debug)
- Role: 8/10 correct, more verbose answers
- Structured: 9/10 correct, perfect format for parsing

YOU'LL LEARN: Prompt format dramatically changes output quality.
  Few-shot + structured output = most reliable for production.

STRETCH GOAL: Test temperature sensitivity. Run same prompts at temp=0, 0.5, 1.0.
  Low temp = consistent but boring. High temp = creative but unreliable.
```

---

### After 04-Frameworks (PyTorch)

#### MINI-PROJECT 16: Custom Dataset + DataLoader

```
GOAL: Master the PyTorch data loading pattern you'll use in every project

WHAT TO BUILD:
- Create a CSV file with synthetic tabular data (or use Titanic)
- Implement custom Dataset class:
  - __init__: load CSV, store features and labels
  - __len__: return number of samples
  - __getitem__: return (feature_tensor, label_tensor) for index i
  - Optional: add transform parameter
- Create DataLoader: batch_size=32, shuffle=True, num_workers=2
- Iterate through one epoch: print batch shapes, verify shuffling
- Add: custom collate_fn for variable-length data (optional)

TIME: 30 minutes

STARTER HINT:
  import torch
  from torch.utils.data import Dataset, DataLoader
  import pandas as pd
  
  class TabularDataset(Dataset):
      def __init__(self, csv_path, target_col, transform=None):
          self.df = pd.read_csv(csv_path)
          self.features = self.df.drop(columns=[target_col]).values.astype('float32')
          self.labels = self.df[target_col].values.astype('float32')
          self.transform = transform
      
      def __len__(self):
          return len(self.df)
      
      def __getitem__(self, idx):
          x = torch.tensor(self.features[idx])
          y = torch.tensor(self.labels[idx])
          if self.transform:
              x = self.transform(x)
          return x, y

EXPECTED OUTPUT:
- DataLoader yields batches of shape (32, num_features) and (32,)
- Different order each epoch (shuffle=True verified)
- Total batches = ceil(n_samples / batch_size)
- No memory issues even with large datasets (lazy loading)

YOU'LL LEARN: The data pipeline pattern you'll use in every project.
  Dataset = how to get ONE sample. DataLoader = how to batch them efficiently.

STRETCH GOAL: Implement an ImageFolder-style dataset that loads images from
  directories. Support: lazy loading, augmentation transforms, caching.
```

---

#### MINI-PROJECT 17: Training Loop Template

```
GOAL: Build a reusable training loop you'll copy into every project

WHAT TO BUILD:
- train_one_epoch(model, loader, optimizer, criterion, device)
- evaluate(model, loader, criterion, device) → returns metrics dict
- save_checkpoint(model, optimizer, epoch, path)
- load_checkpoint(path) → model, optimizer, epoch
- Full training script with:
  - Progress bar (tqdm)
  - Metric logging (to dict/list)
  - Early stopping (patience=5)
  - Learning rate scheduling (ReduceLROnPlateau)
  - Best model saving
- Train a simple model (2-layer MLP on sklearn digits) to verify

TIME: 45 minutes

STARTER HINT:
  from tqdm import tqdm
  
  def train_one_epoch(model, loader, optimizer, criterion, device):
      model.train()
      total_loss = 0
      correct = 0
      total = 0
      
      for batch_x, batch_y in tqdm(loader, desc="Training"):
          batch_x, batch_y = batch_x.to(device), batch_y.to(device)
          optimizer.zero_grad()
          output = model(batch_x)
          loss = criterion(output, batch_y)
          loss.backward()
          optimizer.step()
          
          total_loss += loss.item() * batch_x.size(0)
          _, predicted = output.max(1)
          correct += predicted.eq(batch_y).sum().item()
          total += batch_y.size(0)
      
      return {'loss': total_loss/total, 'accuracy': correct/total}

EXPECTED OUTPUT:
- Training runs with nice progress bar
- Prints: "Epoch 1/20 | Train Loss: 0.45 | Train Acc: 87.3% | Val Acc: 85.1%"
- Early stopping triggers if val_loss doesn't improve for 5 epochs
- Checkpoint saved at best validation accuracy
- Can resume training from checkpoint

YOU'LL LEARN: This template becomes your starting point for everything.
  Modify model + data, keep everything else identical.

STRETCH GOAL: Add gradient clipping, mixed precision (torch.cuda.amp),
  and TensorBoard logging. This is what production training looks like.
```

---

### After 05-Production-Architecture

#### MINI-PROJECT 18: Model as API

```
GOAL: Serve an ML model prediction via HTTP endpoint

WHAT TO BUILD:
- Train a simple model (sklearn iris classifier)
- Save with joblib: joblib.dump(model, 'model.pkl')
- Create FastAPI app (or Flask):
  - GET /health → {"status": "healthy", "model_version": "1.0"}
  - POST /predict → accepts features, returns prediction
  - Input validation (check feature count, numeric values)
  - Error handling (try/except → meaningful error messages)
- Test with curl or requests library

TIME: 45 minutes

STARTER HINT:
  # train_and_save.py
  from sklearn.datasets import load_iris
  from sklearn.ensemble import RandomForestClassifier
  import joblib
  
  X, y = load_iris(return_X_y=True)
  model = RandomForestClassifier().fit(X, y)
  joblib.dump(model, 'model.pkl')
  
  # app.py
  from fastapi import FastAPI, HTTPException
  from pydantic import BaseModel
  import joblib
  import numpy as np
  
  app = FastAPI()
  model = joblib.load('model.pkl')
  
  class PredictRequest(BaseModel):
      features: list[float]
  
  @app.get("/health")
  def health():
      return {"status": "healthy"}
  
  @app.post("/predict")
  def predict(req: PredictRequest):
      if len(req.features) != 4:
          raise HTTPException(400, "Expected 4 features")
      X = np.array(req.features).reshape(1, -1)
      pred = model.predict(X)[0]
      proba = model.predict_proba(X)[0].tolist()
      return {"prediction": int(pred), "probabilities": proba}

EXPECTED OUTPUT:
  $ curl localhost:8000/health
  {"status": "healthy"}
  
  $ curl -X POST localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"features": [5.1, 3.5, 1.4, 0.2]}'
  {"prediction": 0, "probabilities": [0.97, 0.02, 0.01]}

YOU'LL LEARN: Serving is just: load model + parse input + predict + format output.
  Everything else (scaling, monitoring, auth) builds on this foundation.

STRETCH GOAL: Add request logging (timestamp, input, output, latency).
  Add batch prediction endpoint: POST /predict/batch.
```

---

#### MINI-PROJECT 19: Model Monitoring Dashboard

```
GOAL: Detect when your model starts behaving differently in production

WHAT TO BUILD:
- Simulate production: generate 1000 "baseline" predictions (from training dist)
- Simulate drift: generate 200 "new" predictions (shifted distribution)
- Monitoring checks:
  1. Prediction distribution: compare histograms (KS test)
  2. Confidence distribution: are confidence scores dropping?
  3. Feature drift: compare input feature distributions
  4. Alert logic: if KS p-value < 0.05 → "DRIFT DETECTED!"
- Output monitoring report

TIME: 30 minutes

STARTER HINT:
  from scipy.stats import ks_2samp
  import numpy as np
  
  # Simulate baseline predictions
  np.random.seed(42)
  baseline_preds = np.random.choice([0,1,2], size=1000, p=[0.5, 0.3, 0.2])
  baseline_confidence = np.random.beta(5, 2, 1000)  # high confidence
  
  # Simulate drifted predictions (distribution changed!)
  new_preds = np.random.choice([0,1,2], size=200, p=[0.2, 0.3, 0.5])  # class 2 now dominant
  new_confidence = np.random.beta(2, 5, 200)  # LOW confidence (model uncertain)
  
  # KS test for drift detection
  stat, p_value = ks_2samp(baseline_confidence, new_confidence)
  if p_value < 0.05:
      print(f"⚠️ CONFIDENCE DRIFT DETECTED! (p={p_value:.4f})")

EXPECTED OUTPUT:
- "Prediction distribution: DRIFT DETECTED (class 2: 20% → 50%)"
- "Confidence scores: DROPPED (mean 0.71 → 0.29)"
- "ALERT: Model may need retraining!"
- Histogram plots showing the shift visually

YOU'LL LEARN: Monitoring = compare current vs baseline distributions.
  Statistical tests (KS, chi-squared) formalize "does this look different?"

STRETCH GOAL: Build a simple "drift dashboard" that reads from a CSV log
  and auto-generates a monitoring report with plots every N minutes.
```

---

### After 08-NLP-Deep-Dive

#### MINI-PROJECT 20: Word2Vec Explorer

```
GOAL: Explore word relationships captured by embeddings

WHAT TO BUILD:
- Load pretrained embeddings: gensim KeyedVectors (word2vec-google-news-300)
  OR use gensim's smaller model: glove-wiki-gigaword-50
- Explore relationships:
  - most_similar("king") → queen, monarch, prince...
  - Analogy: king - man + woman = ? (should be queen)
  - Find odd-one-out: doesnt_match(["breakfast", "lunch", "dinner", "python"])
- Visualize:
  - Pick 50 words from 5 categories (animals, colors, countries, etc.)
  - Reduce to 2D with t-SNE
  - Plot — words in same category should cluster!

TIME: 30 minutes

STARTER HINT:
  import gensim.downloader as api
  
  # Load pretrained (downloads ~66MB for glove-wiki-gigaword-50)
  model = api.load("glove-wiki-gigaword-50")
  
  # Explore
  print(model.most_similar("king", topn=5))
  print(model.most_similar(positive=["king", "woman"], negative=["man"]))
  
  # Visualize
  from sklearn.manifold import TSNE
  words = ["cat", "dog", "fish", "red", "blue", "green", "france", "germany", "japan"]
  vectors = np.array([model[w] for w in words])
  tsne = TSNE(n_components=2, random_state=42)
  coords = tsne.fit_transform(vectors)

EXPECTED OUTPUT:
- king - man + woman ≈ queen (cosine similarity ~0.7)
- Odd one out: "python" (others are meals)
- t-SNE plot: clear clusters for animals, colors, countries
- Similar words are CLOSE in vector space!

YOU'LL LEARN: Word embeddings capture semantic relationships.
  Directions in vector space encode meaning (gender, tense, category).

STRETCH GOAL: Train your own Word2Vec on a custom corpus (e.g., movie plots).
  Compare: pretrained knows "king→queen"; yours knows domain-specific analogies.
```

---

#### MINI-PROJECT 21: Text Classifier (TF-IDF + Logistic Regression)

```
GOAL: Build a surprisingly strong text classifier in 20 lines

WHAT TO BUILD:
- Load 20newsgroups dataset (sklearn.datasets.fetch_20newsgroups)
- TF-IDF vectorization (max_features=10000)
- Logistic Regression (multi-class)
- Evaluate: accuracy, classification report, confusion matrix
- Show top features (most informative words) per category

TIME: 20 minutes

STARTER HINT:
  from sklearn.datasets import fetch_20newsgroups
  from sklearn.feature_extraction.text import TfidfVectorizer
  from sklearn.linear_model import LogisticRegression
  from sklearn.metrics import classification_report
  
  # Load
  train = fetch_20newsgroups(subset='train')
  test = fetch_20newsgroups(subset='test')
  
  # Vectorize
  tfidf = TfidfVectorizer(max_features=10000, stop_words='english')
  X_train = tfidf.fit_transform(train.data)
  X_test = tfidf.transform(test.data)
  
  # Train
  clf = LogisticRegression(max_iter=1000)
  clf.fit(X_train, train.target)
  
  # Evaluate
  y_pred = clf.predict(X_test)
  print(classification_report(y_pred, test.target, target_names=test.target_names))

EXPECTED OUTPUT:
- Accuracy: 82-85% on 20 categories!
- Best categories: sci.space (F1 ~0.95), talk.politics.guns (F1 ~0.92)
- Worst: comp.sys.ibm.pc.hardware vs comp.sys.mac.hardware (confused)
- Top words for sci.space: "nasa", "orbit", "launch", "shuttle"

YOU'LL LEARN: TF-IDF + simple model = surprisingly strong baseline.
  Always start here before using BERT/transformers. Sometimes this is enough.

STRETCH GOAL: Try with different vectorizers (CountVectorizer, HashingVectorizer).
  Add bigrams (ngram_range=(1,2)). Does it improve?
```

---

### After 11-Data-Engineering

#### MINI-PROJECT 22: SQL Challenge Set

```
GOAL: Build SQL fluency with 10 progressively harder queries

WHAT TO BUILD:
- Create SQLite database with tables:
  - employees(id, name, department, salary, hire_date, manager_id)
  - orders(id, employee_id, customer_id, amount, order_date)
  - customers(id, name, city, segment)
- Insert synthetic data (50 employees, 500 orders, 100 customers)
- Solve 10 challenges:

  1. (Easy) Top 5 highest-paid employees
  2. (Easy) Total revenue per department
  3. (Medium) Employees earning above their department average
  4. (Medium) Running total of orders by date (window function)
  5. (Medium) Customers with no orders (LEFT JOIN + NULL)
  6. (Hard) Rank employees by salary within department (RANK/DENSE_RANK)
  7. (Hard) Month-over-month revenue growth (LAG window function)
  8. (Hard) Recursive CTE: find all reports under a manager
  9. (Expert) Moving 3-month average revenue
  10. (Expert) Pivot: revenue by department × quarter

TIME: 60 minutes

STARTER HINT:
  import sqlite3
  import pandas as pd
  
  conn = sqlite3.connect(':memory:')
  
  # Create tables
  conn.execute('''CREATE TABLE employees (
      id INTEGER PRIMARY KEY,
      name TEXT,
      department TEXT,
      salary REAL,
      hire_date TEXT,
      manager_id INTEGER
  )''')
  
  # Challenge 3: Employees above department average
  query_3 = """
  SELECT e.name, e.salary, e.department, dept_avg.avg_salary
  FROM employees e
  JOIN (
      SELECT department, AVG(salary) as avg_salary
      FROM employees GROUP BY department
  ) dept_avg ON e.department = dept_avg.department
  WHERE e.salary > dept_avg.avg_salary
  """

EXPECTED OUTPUT:
- All 10 queries return correct results
- Window functions feel natural
- CTEs replace ugly subqueries
- Recursive queries handle tree structures

YOU'LL LEARN: Fluent SQL = 10x faster data exploration.
  Window functions and CTEs cover 90% of complex analytical queries.

STRETCH GOAL: Rewrite queries 6-10 using only basic SQL (no window functions).
  Feel the pain. Then appreciate window functions forever.
```

---

### After 17-AWS-ML-Deployment

#### MINI-PROJECT 23: Dockerize an ML Model

```
GOAL: Package model + server into a portable container

WHAT TO BUILD:
- Create project structure:
  - model/train.py (trains and saves model)
  - app/main.py (FastAPI app that loads model and serves predictions)
  - requirements.txt
  - Dockerfile (multi-stage build)
- Dockerfile:
  - Stage 1 (builder): install deps, train model
  - Stage 2 (runtime): copy model + app, minimal deps
  - HEALTHCHECK instruction
  - Non-root user
- Build image, run container, test with curl

TIME: 30 minutes

STARTER HINT:
  # Dockerfile
  FROM python:3.10-slim AS builder
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY model/ model/
  RUN python model/train.py  # saves model.pkl
  
  FROM python:3.10-slim
  WORKDIR /app
  COPY --from=builder /app/model.pkl .
  COPY requirements-runtime.txt requirements.txt
  RUN pip install --no-cache-dir -r requirements.txt
  COPY app/ app/
  RUN useradd -m appuser && chown -R appuser /app
  USER appuser
  EXPOSE 8000
  HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

EXPECTED OUTPUT:
  $ docker build -t ml-model:v1 .
  $ docker run -p 8000:8000 ml-model:v1
  $ curl localhost:8000/health
  {"status": "healthy"}
  $ curl -X POST localhost:8000/predict -d '{"features":[5.1,3.5,1.4,0.2]}'
  {"prediction": 0}

YOU'LL LEARN: Container = reproducible, deployable unit.
  "Works on my machine" → "Works on ANY machine."

STRETCH GOAL: Push to Docker Hub. Pull on a different machine. Verify it works
  identically. Add docker-compose.yml with model + monitoring sidecar.
```

---

#### MINI-PROJECT 24: SageMaker Local Mode

```
GOAL: Experience the SageMaker workflow without spending a cent

WHAT TO BUILD:
- Install: pip install sagemaker[local] boto3
- Create training script (train.py) following SageMaker conventions:
  - Read data from /opt/ml/input/data/
  - Save model to /opt/ml/model/
  - Parse hyperparameters from command line
- Train locally using SageMaker's Local Mode:
  - Estimator with instance_type='local'
  - Trains in a Docker container on YOUR machine
- Deploy to local endpoint (instance_type='local')
- Invoke endpoint with test data

TIME: 30 minutes

STARTER HINT:
  # train.py (SageMaker convention)
  import argparse, os, joblib
  import pandas as pd
  from sklearn.ensemble import RandomForestClassifier
  
  if __name__ == '__main__':
      parser = argparse.ArgumentParser()
      parser.add_argument('--n-estimators', type=int, default=100)
      args = parser.parse_args()
      
      # SageMaker puts data here
      train_path = os.path.join(os.environ.get('SM_CHANNEL_TRAIN', './data'), 'train.csv')
      df = pd.read_csv(train_path)
      X = df.drop('target', axis=1)
      y = df['target']
      
      model = RandomForestClassifier(n_estimators=args.n_estimators)
      model.fit(X, y)
      
      # SageMaker looks for model here
      model_dir = os.environ.get('SM_MODEL_DIR', './model')
      os.makedirs(model_dir, exist_ok=True)
      joblib.dump(model, os.path.join(model_dir, 'model.pkl'))

  # run_local.py
  from sagemaker.sklearn import SKLearn
  
  sklearn_estimator = SKLearn(
      entry_point='train.py',
      role='arn:aws:iam::111111111111:role/dummy',  # dummy for local
      instance_type='local',
      framework_version='1.0-1',
      hyperparameters={'n-estimators': 200}
  )
  sklearn_estimator.fit({'train': 'file://./data'})

EXPECTED OUTPUT:
- Training runs in Docker container locally
- Model artifacts saved
- Local endpoint responds to predictions
- Same code works on real AWS (just change instance_type='ml.m5.large')

YOU'LL LEARN: SageMaker workflow without cloud costs.
  Develop locally, deploy to cloud by changing ONE parameter.

STRETCH GOAL: Add SageMaker Processing job (local mode) for data preprocessing.
  Chain: Processing → Training → Deployment — full ML pipeline locally.
```

---

## Summary Checklist

| # | Mini-Project | Section | Time | Core Deps | Optional Deps |
|---|---|---|---|---|---|
| 1 | PCA from Scratch | 00-Mathematics | 30 min | numpy, matplotlib, sklearn | - |
| 2 | Gradient Descent Visualizer | 00-Mathematics | 30 min | numpy, matplotlib | - |
| 3 | Probability Simulator | 00-Mathematics | 20 min | numpy, matplotlib | - |
| 4 | EDA Report Generator | 01-Python-DS | 45 min | pandas, matplotlib, seaborn | - |
| 5 | Feature Engineering Pipeline | 01-Python-DS | 45 min | pandas, sklearn | - |
| 6 | Classifier Shootout | 02-ML (Supervised) | 30 min | sklearn, matplotlib | - |
| 7 | From-Scratch Logistic Regression | 02-ML (Supervised) | 45 min | numpy, sklearn | - |
| 8 | Hyperparameter Tuning Lab | 02-ML (Supervised) | 45 min | sklearn | optuna |
| 9 | Customer Segmentation | 02-ML (Unsupervised) | 45 min | numpy, sklearn, matplotlib | - |
| 10 | Anomaly Detector | 02-ML (Unsupervised) | 30 min | numpy, sklearn, matplotlib | - |
| 11 | Neural Network from Scratch | 03-Deep-Learning | 60 min | numpy, matplotlib | - |
| 12 | CNN on Fashion-MNIST | 03-Deep-Learning | 45 min | matplotlib | torch, torchvision |
| 13 | Attention Visualizer | 03-Deep-Learning | 30 min | numpy, matplotlib | transformers |
| 14 | RAG System from Scratch | 07-LLMs-GenAI | 45 min | sklearn | - |
| 15 | Prompt Engineering Lab | 07-LLMs-GenAI | 30 min | - | openai/ollama |
| 16 | Custom Dataset + DataLoader | 04-Frameworks | 30 min | pandas | torch |
| 17 | Training Loop Template | 04-Frameworks | 45 min | - | torch, tqdm |
| 18 | Model as API | 05-Production | 45 min | sklearn, joblib | fastapi, uvicorn |
| 19 | Model Monitoring Dashboard | 05-Production | 30 min | numpy, scipy | matplotlib |
| 20 | Word2Vec Explorer | 08-NLP | 30 min | numpy, sklearn | gensim |
| 21 | Text Classifier (TF-IDF) | 08-NLP | 20 min | sklearn | - |
| 22 | SQL Challenge Set | 11-Data-Eng | 60 min | sqlite3, pandas | - |
| 23 | Dockerize ML Model | 17-AWS-Deploy | 30 min | sklearn, joblib | docker, fastapi |
| 24 | SageMaker Local Mode | 17-AWS-Deploy | 30 min | sklearn, joblib | sagemaker, docker |

**Total time: ~15 hours across all 24 projects**

---

## Rules for Mini-Projects

```
1. TIMEBOXED: 30-60 minutes MAX. Set a timer. If time's up, stop and review what you have.

2. CORE DEPENDENCIES ONLY: numpy, pandas, sklearn, matplotlib, seaborn
   - These should ALWAYS be available
   - No pip install needed (assumed in any ML environment)

3. OPTIONAL DEPENDENCIES CLEARLY MARKED:
   - [torch] = PyTorch required
   - [transformers] = HuggingFace transformers
   - [gensim] = gensim for word vectors
   - [fastapi] = FastAPI for serving
   - [docker] = Docker for containerization
   - [optuna] = Optuna for hyperparameter tuning

4. EACH PROJECT HAS:
   - Clear goal (one sentence)
   - Starter hint (enough code to unblock you)
   - Expected output (so you know when you're done)
   - "You'll learn" (the key insight)
   - Stretch goal (only if base is complete)

5. SELF-CONTAINED:
   - No external API keys required (except optional LLM in #15)
   - No large downloads (use sklearn built-in datasets)
   - No cloud accounts needed
   - Everything runs on a laptop

6. PROGRESSIVE:
   - Each project builds on concepts from its section
   - Later projects assume skills from earlier ones
   - But each is independently completable

7. FAILURE IS FINE:
   - If your implementation is 80% working, that's SUCCESS
   - The goal is understanding, not perfection
   - Compare with reference solutions after attempting
```

---

## How to Use This Guide

```
WORKFLOW:
1. Finish reading a section (e.g., 02-Machine-Learning)
2. Open this file, find the corresponding mini-projects
3. Set a timer (30 or 45 or 60 minutes)
4. Build. If stuck > 15 min, read the STARTER HINT.
5. Compare your output with EXPECTED OUTPUT.
6. Read "YOU'LL LEARN" — does it match your experience?
7. If you have energy: do the STRETCH GOAL.
8. Move to next section. Repeat.

TRACKING:
[ ] Mini-Project 1:  PCA from Scratch
[ ] Mini-Project 2:  Gradient Descent Visualizer
[ ] Mini-Project 3:  Probability Simulator
[ ] Mini-Project 4:  EDA Report Generator
[ ] Mini-Project 5:  Feature Engineering Pipeline
[ ] Mini-Project 6:  Classifier Shootout
[ ] Mini-Project 7:  From-Scratch Logistic Regression
[ ] Mini-Project 8:  Hyperparameter Tuning Lab
[ ] Mini-Project 9:  Customer Segmentation
[ ] Mini-Project 10: Anomaly Detector
[ ] Mini-Project 11: Neural Network from Scratch
[ ] Mini-Project 12: CNN on Fashion-MNIST
[ ] Mini-Project 13: Attention Visualizer
[ ] Mini-Project 14: RAG System from Scratch
[ ] Mini-Project 15: Prompt Engineering Lab
[ ] Mini-Project 16: Custom Dataset + DataLoader
[ ] Mini-Project 17: Training Loop Template
[ ] Mini-Project 18: Model as API
[ ] Mini-Project 19: Model Monitoring Dashboard
[ ] Mini-Project 20: Word2Vec Explorer
[ ] Mini-Project 21: Text Classifier (TF-IDF)
[ ] Mini-Project 22: SQL Challenge Set
[ ] Mini-Project 23: Dockerize ML Model
[ ] Mini-Project 24: SageMaker Local Mode
```
