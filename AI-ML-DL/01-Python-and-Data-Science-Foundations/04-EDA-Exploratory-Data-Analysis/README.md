# Exploratory Data Analysis (EDA)

## 1. EDA Workflow and Methodology

```
┌──────────────────────────────────────────────────────────────┐
│                    EDA WORKFLOW                                │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. UNDERSTAND         2. CLEAN            3. EXPLORE         │
│  ┌──────────┐         ┌──────────┐        ┌──────────┐      │
│  │• Shape    │   →    │• Missing  │   →   │• Univar  │      │
│  │• Dtypes  │         │• Duplicates│       │• Bivar   │      │
│  │• Sample  │         │• Types    │        │• Multivar│      │
│  │• Target  │         │• Outliers │        │• Corr    │      │
│  └──────────┘         └──────────┘        └──────────┘      │
│                                                    │          │
│  6. DOCUMENT          5. HYPOTHESIZE    4. VISUALIZE         │
│  ┌──────────┐         ┌──────────┐        ┌──────────┐      │
│  │• Findings│   ←    │• Patterns │   ←   │• Distrib │      │
│  │• Actions │         │• Anomalies│        │• Trends  │      │
│  │• Next    │         │• Segments │        │• Groups  │      │
│  └──────────┘         └──────────┘        └──────────┘      │
└──────────────────────────────────────────────────────────────┘
```

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Step 0: Load and first look
df = pd.read_csv('dataset.csv')

def initial_look(df):
    """Quick overview of any dataset."""
    print(f"Shape: {df.shape}")
    print(f"\n--- Dtypes ---")
    print(df.dtypes.value_counts())
    print(f"\n--- Missing Values ---")
    missing = df.isna().sum()
    print(missing[missing > 0].sort_values(ascending=False))
    print(f"\n--- Duplicates: {df.duplicated().sum()} ---")
    print(f"\n--- Numeric Summary ---")
    print(df.describe().T)
    print(f"\n--- Categorical Summary ---")
    for col in df.select_dtypes(include='object').columns:
        print(f"{col}: {df[col].nunique()} unique, top={df[col].mode()[0]}")
    return df

initial_look(df)
```

## 2. Univariate Analysis

```python
def univariate_numeric(df, col):
    """Comprehensive univariate analysis for numeric column."""
    data = df[col].dropna()

    fig, axes = plt.subplots(1, 4, figsize=(20, 4))

    # Histogram + KDE
    axes[0].hist(data, bins=50, density=True, alpha=0.7, color='steelblue')
    data.plot.kde(ax=axes[0], color='red', linewidth=2)
    axes[0].set_title(f'{col} - Distribution')

    # Box plot
    axes[1].boxplot(data, vert=True)
    axes[1].set_title(f'{col} - Box Plot')

    # QQ plot (normality check)
    stats.probplot(data, plot=axes[2])
    axes[2].set_title(f'{col} - QQ Plot')

    # Violin plot
    axes[3].violinplot(data, showmeans=True, showmedians=True)
    axes[3].set_title(f'{col} - Violin')

    plt.tight_layout()
    plt.show()

    # Statistics
    print(f"--- {col} Statistics ---")
    print(f"  Mean: {data.mean():.4f}")
    print(f"  Median: {data.median():.4f}")
    print(f"  Std: {data.std():.4f}")
    print(f"  Skewness: {data.skew():.4f}")  # >1 or <-1 = highly skewed
    print(f"  Kurtosis: {data.kurtosis():.4f}")  # >3 = heavy tails
    print(f"  IQR: {data.quantile(0.75) - data.quantile(0.25):.4f}")

    # Normality test
    if len(data) < 5000:
        stat, p_value = stats.shapiro(data)
        print(f"  Shapiro-Wilk p-value: {p_value:.4f} ({'Normal' if p_value > 0.05 else 'Non-normal'})")


def univariate_categorical(df, col, top_n=15):
    """Univariate analysis for categorical column."""
    data = df[col].value_counts()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Bar plot (top N)
    data.head(top_n).plot.barh(ax=axes[0], color='steelblue')
    axes[0].set_title(f'{col} - Top {top_n} Categories')

    # Cumulative distribution
    cumsum = data.cumsum() / data.sum() * 100
    axes[1].plot(range(len(cumsum)), cumsum.values, marker='o', markersize=3)
    axes[1].axhline(80, color='red', linestyle='--', label='80%')
    axes[1].set_title(f'{col} - Cumulative %')
    axes[1].legend()

    plt.tight_layout()
    plt.show()

    print(f"  Unique values: {df[col].nunique()}")
    print(f"  Top value: {data.index[0]} ({data.iloc[0]} = {data.iloc[0]/len(df)*100:.1f}%)")
    print(f"  Categories for 80%: {(cumsum <= 80).sum()}")
```

## 3. Bivariate Analysis

```python
def bivariate_numeric(df, col1, col2, target=None):
    """Analyze relationship between two numeric variables."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Scatter plot
    if target:
        scatter = axes[0].scatter(df[col1], df[col2], c=df[target],
                                   alpha=0.5, cmap='viridis', s=20)
        plt.colorbar(scatter, ax=axes[0], label=target)
    else:
        axes[0].scatter(df[col1], df[col2], alpha=0.3, s=20)
    axes[0].set_xlabel(col1)
    axes[0].set_ylabel(col2)
    axes[0].set_title(f'{col1} vs {col2}')

    # Hexbin for dense data
    axes[1].hexbin(df[col1], df[col2], gridsize=30, cmap='YlOrRd')
    axes[1].set_title('Hexbin Density')

    # Regression
    sns.regplot(x=col1, y=col2, data=df, ax=axes[2], scatter_kws={'alpha': 0.3, 's': 20})
    axes[2].set_title('With Regression Line')

    plt.tight_layout()
    plt.show()

    # Correlation
    pearson_r, pearson_p = stats.pearsonr(df[col1].dropna(), df[col2].dropna())
    spearman_r, spearman_p = stats.spearmanr(df[col1].dropna(), df[col2].dropna())
    print(f"  Pearson r={pearson_r:.4f} (p={pearson_p:.4e})")
    print(f"  Spearman ρ={spearman_r:.4f} (p={spearman_p:.4e})")


def bivariate_cat_num(df, cat_col, num_col):
    """Analyze numeric variable across categories."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Box plot
    df.boxplot(column=num_col, by=cat_col, ax=axes[0])
    axes[0].set_title(f'{num_col} by {cat_col}')

    # Violin plot
    categories = df[cat_col].value_counts().index[:10]
    subset = df[df[cat_col].isin(categories)]
    sns.violinplot(data=subset, x=cat_col, y=num_col, ax=axes[1])
    axes[1].tick_params(axis='x', rotation=45)

    # Mean + CI
    sns.barplot(data=subset, x=cat_col, y=num_col, ci=95, ax=axes[2])
    axes[2].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.show()

    # ANOVA test
    groups = [group[num_col].dropna().values for name, group in df.groupby(cat_col)]
    if len(groups) >= 2:
        f_stat, p_value = stats.f_oneway(*groups)
        print(f"  ANOVA F={f_stat:.4f}, p={p_value:.4e}")
        print(f"  {'Significant' if p_value < 0.05 else 'Not significant'} difference between groups")
```

## 4. Multivariate Analysis

```python
def multivariate_analysis(df, numeric_cols, target=None):
    """Multivariate exploration."""

    # Correlation heatmap
    fig, ax = plt.subplots(figsize=(10, 8))
    corr = df[numeric_cols].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, annot=True, cmap='coolwarm', center=0,
                fmt='.2f', square=True, ax=ax)
    ax.set_title('Correlation Matrix')
    plt.tight_layout()
    plt.show()

    # Pairplot
    if len(numeric_cols) <= 6:
        g = sns.pairplot(df[numeric_cols + ([target] if target else [])],
                         hue=target, diag_kind='kde', corner=True,
                         plot_kws={'alpha': 0.5, 's': 20})
        plt.show()

    # Top correlations
    corr_pairs = corr.unstack()
    corr_pairs = corr_pairs[corr_pairs < 1.0].abs().sort_values(ascending=False)
    corr_pairs = corr_pairs.drop_duplicates()
    print("Top 10 correlations:")
    print(corr_pairs.head(10))
```

## 5. Correlation Analysis

```python
def comprehensive_correlation(df, numeric_cols):
    """Compare Pearson, Spearman, and Kendall correlations."""

    pearson = df[numeric_cols].corr(method='pearson')    # linear relationships
    spearman = df[numeric_cols].corr(method='spearman')  # monotonic relationships
    kendall = df[numeric_cols].corr(method='kendall')    # ordinal associations

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for ax, corr_mat, title in zip(axes,
                                     [pearson, spearman, kendall],
                                     ['Pearson (linear)', 'Spearman (monotonic)', 'Kendall (ordinal)']):
        sns.heatmap(corr_mat, annot=True, cmap='coolwarm', center=0,
                    vmin=-1, vmax=1, fmt='.2f', ax=ax)
        ax.set_title(title)
    plt.tight_layout()
    plt.show()

    # When to use which:
    # Pearson:  both variables ~normal, linear relationship
    # Spearman: non-normal data, monotonic relationships, ordinal data
    # Kendall:  small samples, many tied values, more robust

    # Point-biserial correlation (binary vs continuous)
    # from scipy.stats import pointbiserialr
    # r, p = pointbiserialr(df['binary_col'], df['numeric_col'])

    # Cramér's V for categorical vs categorical
    def cramers_v(x, y):
        confusion_matrix = pd.crosstab(x, y)
        chi2 = stats.chi2_contingency(confusion_matrix)[0]
        n = confusion_matrix.sum().sum()
        phi2 = chi2 / n
        r, k = confusion_matrix.shape
        return np.sqrt(phi2 / min(k-1, r-1))
```

## 6. Outlier Detection Methods

```python
def detect_outliers(df, col):
    """Multiple outlier detection methods."""
    data = df[col].dropna()
    results = {}

    # Method 1: IQR (Tukey's method)
    Q1, Q3 = data.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    lower, upper = Q1 - 1.5*IQR, Q3 + 1.5*IQR
    iqr_outliers = (data < lower) | (data > upper)
    results['IQR'] = iqr_outliers.sum()

    # Method 2: Z-score
    z_scores = np.abs(stats.zscore(data))
    z_outliers = z_scores > 3
    results['Z-score (>3)'] = z_outliers.sum()

    # Method 3: Modified Z-score (robust, uses median)
    median = data.median()
    mad = np.median(np.abs(data - median))
    modified_z = 0.6745 * (data - median) / mad
    mod_z_outliers = np.abs(modified_z) > 3.5
    results['Modified Z'] = mod_z_outliers.sum()

    # Method 4: Percentile-based
    p_lower, p_upper = data.quantile([0.01, 0.99])
    pct_outliers = (data < p_lower) | (data > p_upper)
    results['Percentile (1-99)'] = pct_outliers.sum()

    print(f"--- Outlier Detection for '{col}' (n={len(data)}) ---")
    for method, count in results.items():
        print(f"  {method}: {count} outliers ({count/len(data)*100:.1f}%)")

    # Visualization
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].boxplot(data)
    axes[0].set_title('Box Plot')

    axes[1].hist(data, bins=50, alpha=0.7)
    axes[1].axvline(lower, color='r', linestyle='--', label='IQR bounds')
    axes[1].axvline(upper, color='r', linestyle='--')
    axes[1].legend()
    axes[1].set_title('Distribution with IQR Bounds')

    # Sorted values plot
    sorted_data = np.sort(data)
    axes[2].plot(sorted_data)
    axes[2].axhline(upper, color='r', linestyle='--')
    axes[2].axhline(lower, color='r', linestyle='--')
    axes[2].set_title('Sorted Values')
    plt.tight_layout()
    plt.show()

    return iqr_outliers
```

## 7. Data Quality Assessment

```python
def data_quality_report(df):
    """Comprehensive data quality assessment."""
    report = pd.DataFrame({
        'dtype': df.dtypes,
        'non_null': df.count(),
        'null_count': df.isna().sum(),
        'null_pct': (df.isna().sum() / len(df) * 100).round(2),
        'unique': df.nunique(),
        'unique_pct': (df.nunique() / len(df) * 100).round(2),
    })

    # Add numeric-specific stats
    for col in df.select_dtypes(include='number').columns:
        report.loc[col, 'zeros'] = (df[col] == 0).sum()
        report.loc[col, 'negatives'] = (df[col] < 0).sum()
        report.loc[col, 'mean'] = df[col].mean()
        report.loc[col, 'std'] = df[col].std()

    print("=== DATA QUALITY REPORT ===")
    print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
    print(f"Memory: {df.memory_usage(deep=True).sum() / 1e6:.2f} MB")
    print(f"Duplicated rows: {df.duplicated().sum()} ({df.duplicated().sum()/len(df)*100:.2f}%)")
    print(f"\nColumns with >50% missing: {(report['null_pct'] > 50).sum()}")
    print(f"Constant columns: {(report['unique'] == 1).sum()}")
    print(f"High cardinality (>95% unique): {(report['unique_pct'] > 95).sum()}")

    # Visualize missing data pattern
    fig, ax = plt.subplots(figsize=(12, 6))
    missing_cols = df.columns[df.isna().any()].tolist()
    if missing_cols:
        sns.heatmap(df[missing_cols].isna().T, cbar=False, cmap='YlOrRd', ax=ax)
        ax.set_title('Missing Data Pattern (yellow = missing)')
        plt.tight_layout()
        plt.show()

    return report
```

## 8. Distribution Analysis

```python
def distribution_analysis(df, col):
    """Fit and compare distributions."""
    data = df[col].dropna()

    # Common distributions to test
    distributions = ['norm', 'lognorm', 'expon', 'gamma', 'beta', 'weibull_min']

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(data, bins=50, density=True, alpha=0.5, label='Data')

    results = []
    x = np.linspace(data.min(), data.max(), 200)

    for dist_name in distributions:
        try:
            dist = getattr(stats, dist_name)
            params = dist.fit(data)
            pdf = dist.pdf(x, *params)
            ax.plot(x, pdf, linewidth=2, label=f'{dist_name}')

            # Kolmogorov-Smirnov test
            ks_stat, ks_p = stats.kstest(data, dist_name, args=params)
            results.append({'dist': dist_name, 'ks_stat': ks_stat, 'p_value': ks_p})
        except Exception:
            pass

    ax.legend()
    ax.set_title(f'Distribution Fitting: {col}')
    plt.show()

    results_df = pd.DataFrame(results).sort_values('ks_stat')
    print("Best fitting distributions (lower KS stat = better):")
    print(results_df.to_string(index=False))
```

## 9. Complete EDA Walkthrough

```python
"""
Complete EDA on the Titanic dataset (or any classification dataset).
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Load data
df = sns.load_dataset('titanic')

# === STEP 1: Initial Overview ===
print(f"Shape: {df.shape}")
print(f"\nColumn types:\n{df.dtypes}")
print(f"\nMissing values:\n{df.isna().sum()[df.isna().sum() > 0]}")
print(f"\nTarget distribution:\n{df['survived'].value_counts(normalize=True)}")

# === STEP 2: Univariate Analysis ===
# Numeric columns
for col in ['age', 'fare', 'sibsp', 'parch']:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    df[col].hist(bins=30, ax=axes[0])
    axes[0].set_title(f'{col} distribution')
    df.boxplot(column=col, by='survived', ax=axes[1])
    plt.tight_layout()
    plt.show()

# === STEP 3: Bivariate Analysis (features vs target) ===
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
sns.barplot(data=df, x='pclass', y='survived', ax=axes[0,0])
sns.barplot(data=df, x='sex', y='survived', ax=axes[0,1])
sns.barplot(data=df, x='embarked', y='survived', ax=axes[1,0])
sns.kdeplot(data=df, x='age', hue='survived', ax=axes[1,1], fill=True)
plt.tight_layout()
plt.show()

# === STEP 4: Feature interactions ===
# Survival by class AND sex
survival_rates = df.pivot_table(values='survived', index='pclass', columns='sex', aggfunc='mean')
print("Survival rates by class and sex:")
print(survival_rates)

# === STEP 5: Correlations ===
numeric_cols = df.select_dtypes(include='number').columns
corr = df[numeric_cols].corr()
fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(corr, annot=True, cmap='coolwarm', center=0, ax=ax)
plt.tight_layout()
plt.show()

# === STEP 6: Key Findings ===
print("""
EDA Findings:
1. Survival rate: 38.4% (imbalanced but not extreme)
2. Strong predictors: sex (female 74% vs male 19%), pclass, fare
3. Age: younger passengers slightly more likely to survive
4. Missing: age (19.9%), deck (77.2%), embarked (0.2%)
5. Fare is right-skewed (log transform recommended)
6. Family size (sibsp + parch) shows non-linear relationship with survival
""")
```

## 10. Automated EDA Tools

```python
# === pandas-profiling (now ydata-profiling) ===
# pip install ydata-profiling
from ydata_profiling import ProfileReport
profile = ProfileReport(df, title="Dataset EDA Report",
                        explorative=True, minimal=False)
profile.to_file("eda_report.html")

# === Sweetviz ===
# pip install sweetviz
import sweetviz as sv
report = sv.analyze(df, target_feat='survived')
report.show_html('sweetviz_report.html')

# Compare train vs test
# report = sv.compare([train, "Train"], [test, "Test"], target_feat='survived')

# === D-Tale (interactive) ===
# pip install dtale
# import dtale
# d = dtale.show(df)
# d.open_browser()

# When to use automated tools:
# - Quick first pass on new data
# - Generating reports for stakeholders
# - Catching issues you might miss manually
# BUT: Never replace manual EDA entirely - automated tools miss context
```

## Common Pitfalls

| Pitfall | Impact | Fix |
|---------|--------|-----|
| Looking at correlations without scatter plots | Miss non-linear relationships | Always visualize |
| Ignoring data leakage in EDA | Overly optimistic features | Time-aware analysis |
| Not checking class imbalance | Misleading accuracy | Check target distribution first |
| Treating all missing as random | Biased analysis | Check missingness patterns (MCAR/MAR/MNAR) |
| Computing mean on skewed data | Misleading summary | Use median + IQR |
| Too many hypothesis tests | False discoveries | Bonferroni correction |
