# Stage 2: Core Machine Learning

> Duration: 3-4 months | Output: Kaggle competition medal + deployed prediction service

---

## The Mindset Shift

Stage 1 was about "can I build the pieces?" Stage 2 is about "can I solve problems
that matter?" This is where you stop being a student and start being a practitioner.

The skill here is NOT memorizing 50 algorithms. It's knowing:
- Which algorithm to reach for given the problem shape
- How to engineer features that make simple models powerful
- When a model is "good enough" vs when you're overfitting to noise
- How to validate results so you're not lying to yourself

---

## The Real-World ML Workflow

Most ML courses teach: data → model → accuracy number. That's maybe 20% of the job.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    THE ACTUAL ML WORKFLOW                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   1. PROBLEM           2. DATA              3. FEATURES                    │
│   FRAMING              WRANGLING            ENGINEERING                    │
│                                                                            │
│   "What are we         "The data is a       "The model is only            │
│   actually trying      mess. Always."       as good as what                │
│   to predict?"                              you feed it."                  │
│                                                                            │
│   ┌──────────┐        ┌──────────┐         ┌──────────┐                  │
│   │ Business │───────▶│ Collect  │────────▶│ Create   │                  │
│   │ Question │        │ Clean    │         │ Select   │                  │
│   │ → ML     │        │ Validate │         │ Transform│                  │
│   │ Question │        │ Version  │         │ Validate │                  │
│   └──────────┘        └──────────┘         └──────────┘                  │
│        │                    │                    │                         │
│        ▼                    ▼                    ▼                         │
│   4. MODELING          5. EVALUATION        6. DEPLOYMENT                 │
│                                                                            │
│   "Simple baseline     "If you can't        "A model in a                │
│   FIRST. Always."      explain why it's     notebook is                   │
│                        better, it isn't."    worthless."                   │
│                                                                            │
│   ┌──────────┐        ┌──────────┐         ┌──────────┐                  │
│   │ Baseline │───────▶│ Metrics  │────────▶│ API      │                  │
│   │ Iterate  │        │ Validate │         │ Monitor  │                  │
│   │ Ensemble │        │ Compare  │         │ Retrain  │                  │
│   └──────────┘        └──────────┘         └──────────┘                  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

   Time distribution in real ML projects:
   
   Problem Framing    ████░░░░░░░░░░░░░░░░  10%
   Data Work          ████████████░░░░░░░░  50%  ← This is where you live
   Feature Eng.       ████████░░░░░░░░░░░░  20%
   Modeling           ███░░░░░░░░░░░░░░░░░  10%
   Evaluation         ██░░░░░░░░░░░░░░░░░░   5%
   Deployment         ██░░░░░░░░░░░░░░░░░░   5%
```

---

## Month 1: The Algorithm Toolkit

### What to Actually Master (Not Just "Know About")

**Tier 1 - Use these daily (master completely):**
- Logistic Regression (it's a neural net with 0 hidden layers)
- Random Forest (your go-to baseline for everything)
- XGBoost / LightGBM (this wins most tabular competitions)
- Linear Regression + regularization (Ridge/Lasso/ElasticNet)

**Tier 2 - Understand well, use when appropriate:**
- SVM (the kernel trick is beautiful; practical use declining)
- KNN (good baseline, terrible at scale)
- Naive Bayes (surprisingly good for text)
- K-Means, DBSCAN (clustering)
- PCA, UMAP (dimensionality reduction, visualization)

**Tier 3 - Know conceptually, use libraries:**
- Gaussian Processes (uncertainty estimation)
- Hidden Markov Models (sequences)
- Isolation Forest (anomaly detection)

### The Right Way to Learn Each Algorithm

For EACH Tier 1 algorithm, do this (in order):
1. **Implement from scratch** using only NumPy (no sklearn)
2. **Test against sklearn** -- your results must match
3. **Understand the hyperparameters** -- what does each one do? what happens at extremes?
4. **Apply to 3 different datasets** -- watch it succeed and fail
5. **Learn when NOT to use it** -- this is the real knowledge

### Resources

| Resource | What It's For | Link |
|----------|--------------|------|
| ISLR (free book) | Best introduction to statistical learning. Read chapters 2-9. | https://www.statlearning.com/ |
| Stanford CS229 lectures | Andrew Ng's derivations. Math behind every algorithm. | https://youtube.com/playlist?list=PLoROMvodv4rMiGQp3WXShtMGgzqpfVfbU |
| Scikit-learn User Guide | Not just API docs -- the "User Guide" explains the theory | https://scikit-learn.org/stable/user_guide.html |
| "Hands-On ML" - Geron (Part 1) | Most practical ML book. Code for everything. | Book (3rd ed, 2022) |
| fast.ai "Practical ML for Coders" | Jeremy Howard's practical approach | https://course.fast.ai/ |

### Week 1-2 Exercise: Implement from Scratch

Build these using ONLY NumPy:
```python
from_scratch/
├── linear_regression.py      # Normal equation + GD, L1/L2 regularization
├── logistic_regression.py    # Binary + multiclass (softmax)
├── decision_tree.py          # CART with Gini impurity, pruning
├── random_forest.py          # Bagging + feature randomness
├── knn.py                    # Brute force + KD-tree
├── kmeans.py                 # K-means++ initialization
├── pca.py                    # Via eigendecomposition and SVD
├── naive_bayes.py            # Gaussian + Multinomial
└── tests/                    # Compare all against sklearn
```

### Week 3-4: Gradient Boosting Deep Dive

XGBoost/LightGBM are the most important tools for tabular data. Period.

**Learn:**
- How boosting works (sequential weak learners)
- Difference between AdaBoost, Gradient Boosting, XGBoost, LightGBM, CatBoost
- Key hyperparameters: learning_rate, n_estimators, max_depth, subsample, colsample
- How to tune them (don't just random search; understand what each does)
- Feature importance: gain vs split vs SHAP
- When tree methods beat neural nets (spoiler: most tabular data)

| Resource | Link |
|----------|------|
| XGBoost paper | https://arxiv.org/abs/1603.02754 |
| LightGBM paper | https://papers.nips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html |
| CatBoost paper | https://arxiv.org/abs/1706.09516 |
| "How to win Kaggle" (slides) | Search "Kazanova winning data science competitions" |

---

## Month 2: Feature Engineering (The Real Skill)

### Why This Matters More Than Algorithms

A mediocre model with great features beats a great model with raw features. Every time.

Feature engineering is where domain knowledge meets creativity meets statistics. It's
the most underrated skill in ML because it can't be easily automated (yet).

### Feature Engineering by Data Type

```
NUMERICAL FEATURES:
├── Transformations: log, sqrt, Box-Cox (fix skewness)
├── Binning: turn continuous into categorical (age groups)
├── Interactions: feature_A * feature_B, ratios, differences
├── Aggregations: rolling mean, cumsum, group statistics
├── Polynomial: x^2, x^3, cross-terms
└── Domain: velocity = distance/time, BMI = weight/height^2

CATEGORICAL FEATURES:
├── One-hot: sparse binary (low cardinality only)
├── Target encoding: mean of target per category (+smoothing!)
├── Frequency encoding: count/proportion of each value
├── Binary encoding: integer → binary digits
├── Embedding: learn dense representation (for high cardinality)
└── Combinations: category_A + "_" + category_B (interaction)

TEMPORAL FEATURES:
├── Components: year, month, day, hour, minute, weekday, is_weekend
├── Cyclical: sin(2*pi*hour/24), cos(2*pi*month/12)
├── Relative: days_since_last_event, days_until_next_event
├── Lags: value_yesterday, value_last_week
├── Windows: rolling_mean_7d, rolling_std_30d, ewma
└── Calendar: is_holiday, is_quarter_end, business_day_number

TEXT FEATURES:
├── Statistics: length, word_count, avg_word_length, punctuation_count
├── TF-IDF: sparse term-frequency features
├── Sentiment: polarity scores
├── NER: presence of person/org/location names
├── Regex: email_present, phone_present, url_count
└── Embeddings: sentence-transformers (move to Stage 4)

MISSING DATA:
├── Indicator: is_missing flag (missingness is often informative!)
├── Imputation: median (numeric), mode (categorical)
├── Model-based: KNN imputer, iterative imputer
└── Domain: sometimes missing = 0, or missing = "not applicable"
```

### The Feature Engineering Workflow

```
1. Start with raw data
2. Generate MANY candidate features (50-200 for a typical problem)
3. Check for leakage (features that "know" the target)
4. Assess importance (mutual information, correlation, tree importance)
5. Remove redundant features (highly correlated pairs)
6. Validate: does adding this feature improve CV score?
7. Iterate. The best feature is the one you haven't thought of yet.
```

### Resources for Feature Engineering

| Resource | Link |
|----------|------|
| Feature Engineering for ML (O'Reilly) | Book by Alice Zheng |
| Kaggle: Feature Engineering course | https://www.kaggle.com/learn/feature-engineering |
| Feature Engineering & Selection (Kuhn/Johnson) | http://www.feat.engineering/ (free online) |
| Winning solutions on Kaggle | Study top 3 solutions of past competitions |

---

## Month 3: Validation, Selection, and Shipping

### Proper Validation (Most People Get This Wrong)

```
COMMON MISTAKES:
├── Using accuracy on imbalanced data (99% accuracy by predicting majority class!)
├── Fitting scaler/encoder on entire dataset, then splitting (LEAKAGE)
├── Using random split on time-series data (LEAKAGE from future)
├── Using random split when rows are grouped (LEAKAGE from same group)
├── Tuning hyperparameters on test set (you're just overfitting to test)
└── Reporting best single run instead of average across folds

HOW TO DO IT RIGHT:
├── Use stratified k-fold for classification (preserve class ratios)
├── Use group k-fold when data has natural groups (patients, users, stores)
├── Use time-series split when data is temporal
├── Use nested CV: outer for evaluation, inner for hyperparameter tuning
├── Report mean +/- std across folds, not just the best fold
└── ALWAYS compare against a dumb baseline (majority class, mean prediction)
```

### Model Selection Decision Tree

```
                        What's your data?
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          Tabular         Images/Text       Sequential
              │               │               │
              ▼               ▼               ▼
         < 1000 rows?     Deep Learning    Time series
              │             (Stage 3-4)     forecasting
         ┌────┴────┐                            │
         ▼         ▼                            ▼
        Yes        No                      Prophet / 
         │         │                       ARIMA /
         ▼         ▼                       LSTM
   Simple model  Gradient Boosting
   (LogReg,RF)   (XGBoost/LGBM)
         │              │
         ▼              ▼
   Ensemble if    Tune extensively,
   needed         then ensemble top-3
```

### Metrics That Actually Matter

| Problem Type | Metric | When to Use |
|-------------|--------|-------------|
| Binary Classification | AUC-ROC | When you care about ranking |
| Binary Classification | F1 / PR-AUC | When classes are imbalanced |
| Binary Classification | Log Loss | When you need calibrated probabilities |
| Multi-class | Macro F1 | When all classes matter equally |
| Regression | RMSE | When large errors are very bad |
| Regression | MAE | When you want robustness to outliers |
| Regression | MAPE | When relative error matters |
| Ranking | NDCG@K | Search/recommendation |
| Business | Revenue, conversion, retention | Always translate to business impact |

---

## Month 3-4: Real Projects + Kaggle

### Project 1: Kaggle Competition (Tabular)

**Do these in order:**

1. **Titanic** (Getting Started) -- just to learn the platform. Spend max 1 day.
2. **House Prices** (Getting Started) -- practice feature engineering. 2-3 days.
3. **Pick an ACTIVE competition** with tabular data. Spend 2-3 weeks. Target: top 20%.

**What to do in each competition:**
- Day 1: EDA notebook. Understand the data deeply before modeling.
- Day 2-3: Build strongest baseline possible (XGBoost, no tricks)
- Day 4-7: Feature engineering. Generate 50+ features, select best 20-30.
- Day 8-10: Try multiple algorithms, tune top 3
- Day 11-14: Ensemble, stack, submit and iterate

### Project 2: End-to-End Deployed ML Service

**This is the project that separates you from tutorial-followers.**

```
PROJECT: Prediction Service (choose one domain)
─────────────────────────────────────────────────

Option A: Real Estate Price Predictor
Option B: Customer Churn Predictor  
Option C: Credit Risk Scorer

Requirements:
├── Data pipeline that handles new data (not just a static dataset)
├── Feature store (precomputed features, versioned)
├── Model training pipeline (reproducible, logged)
├── Model registry (track experiments, promote best model)
├── REST API (FastAPI) for predictions
├── Input validation (Pydantic schemas)
├── Monitoring dashboard (prediction distribution, latency)
├── Batch + real-time inference paths
├── A/B testing framework (serve 2 models, compare)
├── Automated retraining trigger (on data drift)
├── Docker containerized, docker-compose for local dev
└── README with architecture diagram

Tech stack:
├── Training: scikit-learn/XGBoost + Optuna for tuning
├── Tracking: MLflow or Weights & Biases
├── Serving: FastAPI + uvicorn
├── Monitoring: Prometheus + Grafana (or Evidently AI)
├── Data validation: Great Expectations or Pandera
├── Orchestration: Prefect or simple cron for now
└── CI/CD: GitHub Actions

Architecture:
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Data Source  │────▶│  Feature Eng │────▶│  Training   │
│ (CSV/SQL/API)│     │  Pipeline    │     │  Pipeline   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                  │
                                                  ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Monitoring │◀────│  Prediction  │◀────│   Model     │
│  Dashboard  │     │  API         │     │   Registry  │
└─────────────┘     └──────────────┘     └─────────────┘
```

---

## Interpretability (Learn This Now, Not Later)

**SHAP is non-negotiable.** Every model you build from this point on must have
SHAP explanations. Here's why: if you can't explain why a model makes a prediction,
you can't debug it, you can't convince stakeholders, and in some industries you're
breaking the law.

```python
import shap

# For tree models (fast):
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Key plots to always generate:
shap.summary_plot(shap_values, X_test)          # Global importance
shap.dependence_plot("feature_name", shap_values, X_test)  # Feature effect
shap.force_plot(explainer.expected_value, shap_values[0])   # Single prediction
shap.waterfall_plot(shap_values[0])             # Detailed breakdown
```

---

## Stage 2 Completion Criteria

- [ ] Implemented 8+ algorithms from scratch, tested against sklearn
- [ ] Competed in at least 2 Kaggle competitions (one top-20% finish minimum)
- [ ] Built a deployed ML service with API, monitoring, and retraining
- [ ] Can do feature engineering for any data type without looking at tutorials
- [ ] Can set up proper cross-validation and explain why random splits can lie
- [ ] Can explain the bias-variance tradeoff and identify it in learning curves
- [ ] Can use SHAP to explain any model's predictions
- [ ] Can articulate when to use logistic regression vs random forest vs XGBoost
- [ ] GitHub has the deployed service + competition notebooks
