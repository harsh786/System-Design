# Feature Engineering

## 1. Numerical Feature Transformations

```python
import numpy as np
import pandas as pd
from sklearn.preprocessing import (
    StandardScaler, MinMaxScaler, RobustScaler,
    PowerTransformer, QuantileTransformer
)

# Sample data
df = pd.DataFrame({
    'income': [30000, 45000, 55000, 120000, 500000, 35000, 62000],
    'age': [22, 35, 42, 55, 38, 28, 50],
    'transactions': [5, 12, 8, 45, 100, 3, 20]
})

# === Standard Scaling (Z-score): mean=0, std=1 ===
# Use when: algorithm assumes normally distributed features (linear reg, SVM, kNN)
scaler = StandardScaler()
df['income_std'] = scaler.fit_transform(df[['income']])

# === Min-Max Scaling: [0, 1] ===
# Use when: need bounded values (neural networks, image data)
scaler = MinMaxScaler()
df['income_minmax'] = scaler.fit_transform(df[['income']])

# === Robust Scaling: uses median and IQR ===
# Use when: data has outliers (won't be affected by extreme values)
scaler = RobustScaler()
df['income_robust'] = scaler.fit_transform(df[['income']])

# === Log Transform: reduces right skewness ===
# Use when: feature is right-skewed (income, prices, counts)
df['income_log'] = np.log1p(df['income'])  # log1p handles zeros

# === Power Transform (Box-Cox / Yeo-Johnson) ===
# Box-Cox: only positive values; Yeo-Johnson: handles negatives
pt = PowerTransformer(method='yeo-johnson')
df['income_power'] = pt.fit_transform(df[['income']])

# === Quantile Transform: maps to uniform or normal distribution ===
# Use when: you want guaranteed normal distribution
qt = QuantileTransformer(output_distribution='normal', random_state=42)
df['income_quantile'] = qt.fit_transform(df[['income']])

# === Binning ===
df['age_bin'] = pd.cut(df['age'], bins=[0, 25, 35, 50, 100],
                       labels=['young', 'adult', 'middle', 'senior'])

# Quantile-based binning (equal frequency)
df['income_quantile_bin'] = pd.qcut(df['income'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
```

```
When to use which scaler:
┌────────────────────┬──────────────────────────────────────────┐
│ Scaler             │ Best for                                  │
├────────────────────┼──────────────────────────────────────────┤
│ StandardScaler     │ Normal-ish data, linear models, SVM      │
│ MinMaxScaler       │ Neural networks, bounded algorithms      │
│ RobustScaler       │ Data with outliers                        │
│ Log/Power transform│ Skewed distributions                      │
│ QuantileTransformer│ Force any distribution to normal/uniform │
└────────────────────┴──────────────────────────────────────────┘
```

## 2. Categorical Encoding

```python
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, OrdinalEncoder
import category_encoders as ce  # pip install category-encoders

df = pd.DataFrame({
    'color': ['red', 'blue', 'green', 'red', 'blue', 'green', 'red'],
    'size': ['S', 'M', 'L', 'XL', 'M', 'S', 'L'],
    'city': ['NYC', 'LA', 'NYC', 'Chicago', 'LA', 'NYC', 'Boston'],
    'target': [1, 0, 1, 1, 0, 1, 0]
})

# === One-Hot Encoding (nominal categories, low cardinality) ===
df_onehot = pd.get_dummies(df, columns=['color'], drop_first=True)  # drop_first avoids multicollinearity

# === Label Encoding (ordinal categories) ===
size_order = {'S': 0, 'M': 1, 'L': 2, 'XL': 3}
df['size_encoded'] = df['size'].map(size_order)

# === Frequency Encoding ===
# Use when: high cardinality, frequency matters
freq = df['city'].value_counts(normalize=True)
df['city_freq'] = df['city'].map(freq)

# === Target Encoding (mean encoding) ===
# Use when: high cardinality categorical with target relationship
# CRITICAL: Must use CV/smoothing to avoid leakage!
encoder = ce.TargetEncoder(cols=['city'], smoothing=1.0)
df['city_target'] = encoder.fit_transform(df['city'], df['target'])

# === Binary Encoding (high cardinality) ===
# Represents categories as binary digits - fewer columns than one-hot
encoder = ce.BinaryEncoder(cols=['city'])
df_binary = encoder.fit_transform(df)

# === Leave-One-Out Encoding (reduces leakage vs target encoding) ===
encoder = ce.LeaveOneOutEncoder(cols=['city'])
df['city_loo'] = encoder.fit_transform(df['city'], df['target'])

# PITFALL: Target encoding leakage
# ALWAYS use within cross-validation folds
# from sklearn.model_selection import KFold
# kf = KFold(n_splits=5)
# for train_idx, val_idx in kf.split(df):
#     encoder.fit(df.iloc[train_idx]['city'], df.iloc[train_idx]['target'])
#     df.iloc[val_idx, col_idx] = encoder.transform(df.iloc[val_idx]['city'])
```

## 3. Text Features

```python
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

texts = [
    "machine learning is great for predictions",
    "deep learning uses neural networks",
    "natural language processing handles text",
    "machine learning and deep learning overlap"
]

# === TF-IDF ===
tfidf = TfidfVectorizer(max_features=100, ngram_range=(1, 2), stop_words='english')
tfidf_matrix = tfidf.fit_transform(texts)
print(f"Shape: {tfidf_matrix.shape}")  # (4, n_features)
print(f"Features: {tfidf.get_feature_names_out()[:10]}")

# === Basic text statistics (always useful) ===
df = pd.DataFrame({'text': texts})
df['word_count'] = df['text'].str.split().str.len()
df['char_count'] = df['text'].str.len()
df['avg_word_len'] = df['text'].apply(lambda x: np.mean([len(w) for w in x.split()]))
df['uppercase_count'] = df['text'].str.count(r'[A-Z]')
df['punctuation_count'] = df['text'].str.count(r'[^\w\s]')
df['unique_word_ratio'] = df['text'].apply(lambda x: len(set(x.split())) / len(x.split()))

# === Word Embeddings (pre-trained) ===
# Using sentence-transformers for modern embeddings
# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer('all-MiniLM-L6-v2')
# embeddings = model.encode(texts)  # shape: (4, 384)
```

## 4. Date/Time Features

```python
df = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=1000, freq='H')
})

# === Cyclical encoding (for periodic features) ===
# Why: hour 23 is close to hour 0, but numerically they're far apart
df['hour'] = df['timestamp'].dt.hour
df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)

df['day_of_week'] = df['timestamp'].dt.dayofweek
df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

df['month'] = df['timestamp'].dt.month
df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

# === Other useful time features ===
df['is_weekend'] = df['timestamp'].dt.dayofweek >= 5
df['is_month_start'] = df['timestamp'].dt.is_month_start
df['is_month_end'] = df['timestamp'].dt.is_month_end
df['quarter'] = df['timestamp'].dt.quarter
df['day_of_year'] = df['timestamp'].dt.dayofyear

# === Time since event ===
reference_date = pd.Timestamp('2024-01-01')
df['days_since_ref'] = (df['timestamp'] - reference_date).dt.days

# === Business-specific ===
df['is_business_hour'] = df['hour'].between(9, 17)
# holidays: use the `holidays` package
# import holidays
# us_holidays = holidays.US(years=2024)
# df['is_holiday'] = df['timestamp'].dt.date.isin(us_holidays)
```

## 5. Interaction Features

```python
df = pd.DataFrame({
    'height': [170, 165, 180, 175, 160],
    'weight': [70, 55, 85, 78, 50],
    'age': [30, 25, 40, 35, 22]
})

# === Arithmetic interactions ===
df['bmi'] = df['weight'] / (df['height']/100)**2        # domain knowledge
df['height_weight_ratio'] = df['height'] / df['weight']
df['age_bmi'] = df['age'] * df['bmi']                   # cross-feature

# === Ratios and differences ===
# Common in financial data
# df['debt_to_income'] = df['debt'] / df['income']
# df['savings_rate'] = df['savings'] / df['income']
# df['profit_margin'] = (df['revenue'] - df['cost']) / df['revenue']

# === Polynomial features ===
from sklearn.preprocessing import PolynomialFeatures

poly = PolynomialFeatures(degree=2, interaction_only=False, include_bias=False)
poly_features = poly.fit_transform(df[['height', 'weight']])
poly_names = poly.get_feature_names_out(['height', 'weight'])
print(poly_names)
# ['height', 'weight', 'height^2', 'height weight', 'weight^2']

# interaction_only=True: only cross-terms, no squared terms
poly_interact = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
interact_features = poly_interact.fit_transform(df[['height', 'weight', 'age']])
# ['height', 'weight', 'age', 'height*weight', 'height*age', 'weight*age']
```

## 6. Feature Selection Methods

```python
from sklearn.feature_selection import (
    SelectKBest, f_classif, mutual_info_classif,
    RFE, SelectFromModel
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LassoCV

# Sample data
from sklearn.datasets import make_classification
X, y = make_classification(n_samples=1000, n_features=20,
                           n_informative=10, n_redundant=5, random_state=42)
feature_names = [f'feature_{i}' for i in range(20)]

# === FILTER Methods (fast, model-agnostic) ===

# ANOVA F-test (for classification)
selector = SelectKBest(f_classif, k=10)
X_selected = selector.fit_transform(X, y)
scores = pd.Series(selector.scores_, index=feature_names).sort_values(ascending=False)
print("Top features (F-test):", scores.head(10).index.tolist())

# Mutual Information (captures non-linear relationships)
mi_scores = mutual_info_classif(X, y, random_state=42)
mi_series = pd.Series(mi_scores, index=feature_names).sort_values(ascending=False)

# Correlation filter (remove highly correlated features)
def remove_correlated(df, threshold=0.95):
    corr_matrix = df.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [col for col in upper.columns if any(upper[col] > threshold)]
    return df.drop(columns=to_drop), to_drop

# === WRAPPER Methods (slower, model-specific) ===

# Recursive Feature Elimination
model = RandomForestClassifier(n_estimators=100, random_state=42)
rfe = RFE(model, n_features_to_select=10, step=1)
rfe.fit(X, y)
selected = [f for f, s in zip(feature_names, rfe.support_) if s]
print("RFE selected:", selected)

# === EMBEDDED Methods (during model training) ===

# L1 regularization (Lasso) - drives coefficients to zero
lasso = LassoCV(cv=5, random_state=42)
lasso.fit(X, y)
importance = pd.Series(np.abs(lasso.coef_), index=feature_names).sort_values(ascending=False)
selected = importance[importance > 0].index.tolist()

# Tree-based feature importance
rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X, y)
importances = pd.Series(rf.feature_importances_, index=feature_names).sort_values(ascending=False)

# SelectFromModel (auto threshold)
selector = SelectFromModel(rf, threshold='median')
X_important = selector.fit_transform(X, y)
```

```
Feature Selection Decision Guide:
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  Many features (>100)?                                       │
│  ├─ YES → Start with Filter (variance, correlation)         │
│  │         Then Embedded (Lasso, tree importance)            │
│  └─ NO  → Go directly to Wrapper (RFE) or Embedded         │
│                                                              │
│  Need interpretability?                                      │
│  ├─ YES → Lasso coefficients, tree importance               │
│  └─ NO  → Any method, focus on validation performance       │
│                                                              │
│  Non-linear relationships?                                   │
│  ├─ YES → Mutual Information, tree-based methods            │
│  └─ NO  → F-test, Pearson correlation, Lasso                │
└─────────────────────────────────────────────────────────────┘
```

## 7. Feature Importance Analysis

```python
import shap
from sklearn.inspection import permutation_importance

# === Permutation Importance (model-agnostic, reliable) ===
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)

perm_importance = permutation_importance(rf, X_test, y_test, n_repeats=10, random_state=42)
perm_df = pd.DataFrame({
    'feature': feature_names,
    'importance_mean': perm_importance.importances_mean,
    'importance_std': perm_importance.importances_std
}).sort_values('importance_mean', ascending=False)

# === SHAP Values (gold standard for interpretation) ===
explainer = shap.TreeExplainer(rf)
shap_values = explainer.shap_values(X_test)

# Summary plot
shap.summary_plot(shap_values[1], X_test, feature_names=feature_names)

# Force plot for single prediction
shap.force_plot(explainer.expected_value[1], shap_values[1][0], X_test[0],
                feature_names=feature_names)

# SHAP importance (mean absolute SHAP values)
shap_importance = np.abs(shap_values[1]).mean(axis=0)
shap_df = pd.Series(shap_importance, index=feature_names).sort_values(ascending=False)
```

## 8. Automated Feature Engineering

```python
# === Featuretools (Deep Feature Synthesis) ===
# pip install featuretools
import featuretools as ft

# Define entity set
es = ft.EntitySet(id='customers')

# Add entities (tables)
es = es.add_dataframe(
    dataframe_name='customers',
    dataframe=customers_df,
    index='customer_id'
)
es = es.add_dataframe(
    dataframe_name='transactions',
    dataframe=transactions_df,
    index='transaction_id',
    time_index='timestamp'
)

# Define relationships
es = es.add_relationship('customers', 'customer_id', 'transactions', 'customer_id')

# Generate features automatically
feature_matrix, feature_defs = ft.dfs(
    entityset=es,
    target_dataframe_name='customers',
    agg_primitives=['mean', 'sum', 'count', 'std', 'max', 'min', 'trend'],
    trans_primitives=['year', 'month', 'weekday'],
    max_depth=2
)
print(f"Generated {len(feature_defs)} features automatically")
```

## 9. Domain-Specific Feature Engineering

```python
# === E-commerce ===
def ecommerce_features(df):
    df['avg_order_value'] = df['total_spent'] / df['num_orders']
    df['days_since_last_order'] = (pd.Timestamp.now() - df['last_order_date']).dt.days
    df['order_frequency'] = df['num_orders'] / df['account_age_days']
    df['is_returning'] = (df['num_orders'] > 1).astype(int)
    # RFM features
    df['recency_score'] = pd.qcut(df['days_since_last_order'], 5, labels=[5,4,3,2,1])
    df['frequency_score'] = pd.qcut(df['num_orders'], 5, labels=[1,2,3,4,5])
    df['monetary_score'] = pd.qcut(df['total_spent'], 5, labels=[1,2,3,4,5])
    return df

# === Time Series / Forecasting ===
def time_series_features(df, target_col, lags=[1,7,14,30]):
    for lag in lags:
        df[f'lag_{lag}'] = df[target_col].shift(lag)
    # Rolling statistics
    for window in [7, 14, 30]:
        df[f'rolling_mean_{window}'] = df[target_col].rolling(window).mean()
        df[f'rolling_std_{window}'] = df[target_col].rolling(window).std()
    # Expanding features
    df['expanding_mean'] = df[target_col].expanding().mean()
    # Diff features
    df['diff_1'] = df[target_col].diff(1)
    df['diff_7'] = df[target_col].diff(7)
    return df

# === NLP / Text Classification ===
def text_features(df, text_col):
    df['n_words'] = df[text_col].str.split().str.len()
    df['n_chars'] = df[text_col].str.len()
    df['n_sentences'] = df[text_col].str.count(r'[.!?]+')
    df['avg_word_length'] = df[text_col].apply(lambda x: np.mean([len(w) for w in x.split()]))
    df['n_uppercase'] = df[text_col].str.count(r'[A-Z]')
    df['n_exclamation'] = df[text_col].str.count('!')
    df['sentiment_length_ratio'] = df['n_exclamation'] / df['n_words']
    return df
```

## 10. Production Considerations

```python
# === Feature Engineering Pipeline (sklearn) ===
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

numeric_features = ['age', 'income', 'transactions']
categorical_features = ['city', 'gender']

numeric_transformer = Pipeline(steps=[
    ('scaler', RobustScaler()),
    ('power', PowerTransformer(method='yeo-johnson'))
])

categorical_transformer = Pipeline(steps=[
    ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

preprocessor = ColumnTransformer(transformers=[
    ('num', numeric_transformer, numeric_features),
    ('cat', categorical_transformer, categorical_features)
])

# Full pipeline with model
from sklearn.ensemble import GradientBoostingClassifier
full_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', GradientBoostingClassifier())
])

# Fit and predict (no data leakage!)
full_pipeline.fit(X_train, y_train)
predictions = full_pipeline.predict(X_test)

# Save pipeline
import joblib
joblib.dump(full_pipeline, 'model_pipeline.pkl')
loaded_pipeline = joblib.load('model_pipeline.pkl')
```

## Common Pitfalls

| Pitfall | Impact | Fix |
|---------|--------|-----|
| Fitting scaler on full data before split | Data leakage, optimistic results | Fit ONLY on training data |
| Target encoding without CV | Overfitting on train | Use KFold target encoding |
| Creating features from future data | Leakage in time series | Respect temporal order |
| Too many features from one-hot encoding | Curse of dimensionality | Use frequency/target encoding for high cardinality |
| Not handling unseen categories at inference | Crashes in production | Use `handle_unknown='ignore'` |
| Log transform on zeros/negatives | NaN/errors | Use `np.log1p()` or Yeo-Johnson |
| Not saving the fitted transformer | Can't reproduce at inference | Use sklearn Pipeline + joblib |
