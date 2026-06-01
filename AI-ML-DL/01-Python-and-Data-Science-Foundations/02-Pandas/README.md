# Pandas Mastery

## 1. Series and DataFrame

```python
import pandas as pd
import numpy as np

# === Series: 1D labeled array ===
s = pd.Series([10, 20, 30], index=['a', 'b', 'c'], name='values')
print(s['b'])        # 20
print(s.values)      # numpy array
print(s.index)       # Index(['a', 'b', 'c'])

# === DataFrame: 2D labeled table ===
df = pd.DataFrame({
    'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'age': [25, 30, 35, 28],
    'salary': [50000, 70000, 80000, 60000],
    'department': ['Engineering', 'Marketing', 'Engineering', 'Marketing']
})

# Key attributes
print(df.shape)      # (4, 4)
print(df.dtypes)     # column types
print(df.columns)    # column names
print(df.info())     # memory usage, dtypes, non-null counts
print(df.describe()) # statistical summary
```

## 2. Reading/Writing Data

```python
# === CSV ===
df = pd.read_csv('data.csv',
    parse_dates=['date_col'],
    dtype={'id': str, 'amount': float},
    usecols=['id', 'amount', 'date_col'],  # only load needed columns
    nrows=1000,                             # sample first
    na_values=['NA', 'missing', ''],
    low_memory=False
)
df.to_csv('output.csv', index=False)

# === JSON ===
df = pd.read_json('data.json', orient='records')
df.to_json('output.json', orient='records', lines=True)  # JSON Lines format

# === Parquet (preferred for large datasets) ===
df = pd.read_parquet('data.parquet', columns=['col1', 'col2'])
df.to_parquet('output.parquet', engine='pyarrow', compression='snappy')

# === SQL ===
from sqlalchemy import create_engine
engine = create_engine('sqlite:///database.db')
df = pd.read_sql('SELECT * FROM users WHERE age > 25', engine)
df.to_sql('users_processed', engine, if_exists='replace', index=False)

# === Excel ===
df = pd.read_excel('data.xlsx', sheet_name='Sheet1')

# Performance comparison for 1M rows:
# CSV read:     ~2-5 seconds
# Parquet read: ~0.2-0.5 seconds
# Parquet is 5-10x smaller on disk too
```

## 3. Indexing: loc, iloc, boolean

```python
df = pd.DataFrame({
    'A': range(10),
    'B': range(10, 20),
    'C': list('abcdefghij')
}, index=pd.date_range('2024-01-01', periods=10))

# loc: Label-based (inclusive on both ends)
df.loc['2024-01-01':'2024-01-03']          # rows by label
df.loc['2024-01-01', 'A']                  # single value
df.loc[:, ['A', 'B']]                      # all rows, specific cols

# iloc: Integer position-based (exclusive on end)
df.iloc[0:3]                                # first 3 rows
df.iloc[0, 0]                              # first element
df.iloc[:, [0, 1]]                         # all rows, first 2 cols

# Boolean indexing
mask = df['A'] > 5
df[mask]                                    # rows where A > 5
df.loc[mask, 'B']                          # column B where A > 5

# Combined conditions
df[(df['A'] > 3) & (df['B'] < 18)]        # AND
df[(df['A'] > 7) | (df['B'] < 12)]        # OR
df[df['C'].isin(['a', 'b', 'c'])]         # IN

# query() for readable filtering
df.query('A > 3 and B < 18')
threshold = 5
df.query('A > @threshold')                  # use variables with @

# PITFALL: SettingWithCopyWarning
# BAD:  df[df['A'] > 5]['B'] = 0          # might not work
# GOOD: df.loc[df['A'] > 5, 'B'] = 0     # always works
```

## 4. GroupBy Operations

```python
# Sample data
sales = pd.DataFrame({
    'store': ['A', 'A', 'B', 'B', 'A', 'B'] * 100,
    'product': ['X', 'Y', 'X', 'Y', 'X', 'Y'] * 100,
    'revenue': np.random.uniform(100, 1000, 600),
    'quantity': np.random.randint(1, 50, 600)
})

# Basic groupby
grouped = sales.groupby('store')['revenue']
print(grouped.mean())
print(grouped.agg(['mean', 'sum', 'count', 'std']))

# Multiple columns groupby
sales.groupby(['store', 'product']).agg(
    total_revenue=('revenue', 'sum'),
    avg_quantity=('quantity', 'mean'),
    num_transactions=('revenue', 'count')
).reset_index()

# Custom aggregation functions
def revenue_range(x):
    return x.max() - x.min()

sales.groupby('store')['revenue'].agg(revenue_range)

# Transform: returns same-shaped output (useful for normalization)
sales['revenue_zscore'] = sales.groupby('store')['revenue'].transform(
    lambda x: (x - x.mean()) / x.std()
)

# Filter: keep groups meeting a condition
large_stores = sales.groupby('store').filter(
    lambda x: x['revenue'].sum() > 50000
)

# Apply: flexible group operations
def top_3_by_revenue(group):
    return group.nlargest(3, 'revenue')

sales.groupby('store').apply(top_3_by_revenue).reset_index(drop=True)
```

## 5. Merge, Join, Concat

```
┌─────────────────────────────────────────────────────┐
│ Merge Types:                                         │
│                                                      │
│ INNER JOIN       LEFT JOIN        OUTER JOIN         │
│  A ∩ B           A (+ matching B)  A ∪ B            │
│   ┌──┐            ┌────┐           ┌────────┐      │
│   │AB│            │A│AB│           │A│AB│B  │      │
│   └──┘            └────┘           └────────┘      │
└─────────────────────────────────────────────────────┘
```

```python
# DataFrames
customers = pd.DataFrame({
    'customer_id': [1, 2, 3, 4],
    'name': ['Alice', 'Bob', 'Charlie', 'Diana']
})
orders = pd.DataFrame({
    'order_id': [101, 102, 103, 104],
    'customer_id': [1, 2, 2, 5],
    'amount': [250, 150, 300, 100]
})

# Merge (SQL-style joins)
inner = pd.merge(customers, orders, on='customer_id', how='inner')  # only matches
left = pd.merge(customers, orders, on='customer_id', how='left')    # keep all customers
outer = pd.merge(customers, orders, on='customer_id', how='outer')  # keep everything

# Different column names
pd.merge(df1, df2, left_on='id', right_on='customer_id')

# Multiple keys
pd.merge(df1, df2, on=['year', 'quarter'])

# Validate merge (catch data issues!)
pd.merge(customers, orders, on='customer_id', validate='one_to_many')

# Concat: stack DataFrames
combined = pd.concat([df1, df2, df3], axis=0, ignore_index=True)  # vertically
wide = pd.concat([df1, df2], axis=1)                               # horizontally

# PITFALL: Always check merge results
print(f"Left: {len(customers)}, Right: {len(orders)}, Merged: {len(inner)}")
# If merged > max(left, right), you likely have duplicate keys → many-to-many
```

## 6. Pivot Tables and Cross-tabulations

```python
# Sample sales data
data = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=365),
    'region': np.random.choice(['North', 'South', 'East', 'West'], 365),
    'product': np.random.choice(['A', 'B', 'C'], 365),
    'sales': np.random.uniform(100, 1000, 365),
    'units': np.random.randint(1, 100, 365)
})

# Pivot table
pivot = data.pivot_table(
    values='sales',
    index='region',
    columns='product',
    aggfunc='mean',
    margins=True  # adds row/col totals
)

# Multiple aggregations
pivot_multi = data.pivot_table(
    values=['sales', 'units'],
    index='region',
    columns='product',
    aggfunc={'sales': 'sum', 'units': 'mean'}
)

# Cross-tabulation (frequency tables)
ct = pd.crosstab(data['region'], data['product'], margins=True)
ct_norm = pd.crosstab(data['region'], data['product'], normalize='index')  # row percentages

# Melt (unpivot) - wide to long
wide_df = pivot.reset_index()
long_df = pd.melt(wide_df, id_vars=['region'], var_name='product', value_name='avg_sales')
```

## 7. Time Series Functionality

```python
# Date range creation
dates = pd.date_range('2024-01-01', periods=365, freq='D')
business_days = pd.bdate_range('2024-01-01', '2024-12-31')

# Time series DataFrame
ts = pd.DataFrame({
    'date': dates,
    'value': np.cumsum(np.random.randn(365)) + 100
}).set_index('date')

# Resampling (downsampling: higher freq → lower freq)
monthly = ts.resample('M').agg({'value': ['mean', 'std', 'last']})
weekly = ts.resample('W').mean()

# Upsampling with fill
hourly = ts.resample('H').ffill()   # forward fill
hourly = ts.resample('H').interpolate(method='linear')

# Rolling windows
ts['rolling_7d'] = ts['value'].rolling(window=7).mean()
ts['rolling_30d'] = ts['value'].rolling(window=30).mean()
ts['ewm'] = ts['value'].ewm(span=7).mean()  # exponential weighted

# Shifting (lag/lead features for ML)
ts['lag_1'] = ts['value'].shift(1)     # previous day
ts['lag_7'] = ts['value'].shift(7)     # previous week
ts['pct_change'] = ts['value'].pct_change()  # daily return

# Date components
ts['dayofweek'] = ts.index.dayofweek
ts['month'] = ts.index.month
ts['quarter'] = ts.index.quarter
ts['is_weekend'] = ts.index.dayofweek >= 5

# Between dates
mask = (ts.index >= '2024-06-01') & (ts.index <= '2024-08-31')
summer = ts[mask]
```

## 8. Missing Data Handling

```python
df = pd.DataFrame({
    'A': [1, 2, np.nan, 4, 5],
    'B': [np.nan, 2, 3, np.nan, 5],
    'C': ['x', None, 'z', 'w', None]
})

# Detection
df.isna().sum()                    # count NaN per column
df.isna().mean()                   # fraction missing per column
df.isna().sum().sum()              # total missing values

# Dropping
df.dropna()                         # drop rows with ANY NaN
df.dropna(thresh=2)                # keep rows with at least 2 non-NaN
df.dropna(subset=['A', 'B'])       # only consider specific columns

# Filling
df['A'].fillna(df['A'].median())   # fill with median
df['C'].fillna('unknown')          # fill categorical
df.fillna(method='ffill')          # forward fill (time series)
df.fillna(method='bfill')          # backward fill

# Interpolation
df['A'].interpolate(method='linear')
df['A'].interpolate(method='spline', order=2)

# Strategy by column type
def handle_missing(df):
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64']:
            df[col].fillna(df[col].median(), inplace=True)
        else:
            df[col].fillna(df[col].mode()[0], inplace=True)
    return df

# PITFALL: inplace=True returns None
# BAD: df = df.fillna(0, inplace=True)   # df is now None!
# GOOD: df.fillna(0, inplace=True)       # or df = df.fillna(0)
```

## 9. Method Chaining

```python
# Clean, readable data pipelines using method chaining
result = (
    pd.read_csv('sales.csv')
    .rename(columns=str.lower)
    .rename(columns=lambda x: x.replace(' ', '_'))
    .assign(
        date=lambda df: pd.to_datetime(df['date']),
        revenue=lambda df: df['quantity'] * df['price'],
        month=lambda df: df['date'].dt.month
    )
    .query('revenue > 0')
    .dropna(subset=['customer_id'])
    .groupby(['month', 'category'], as_index=False)
    .agg(
        total_revenue=('revenue', 'sum'),
        num_orders=('order_id', 'nunique'),
        avg_order_value=('revenue', 'mean')
    )
    .sort_values('total_revenue', ascending=False)
    .reset_index(drop=True)
)

# pipe() for custom functions in the chain
def remove_outliers(df, column, n_std=3):
    mean = df[column].mean()
    std = df[column].std()
    return df[(df[column] - mean).abs() <= n_std * std]

result = (
    df
    .pipe(remove_outliers, 'revenue', n_std=3)
    .pipe(lambda d: d[d['quantity'] > 0])
)
```

## 10. Performance Optimization

```python
# === Dtype optimization ===
def optimize_dtypes(df):
    """Reduce memory usage by downcasting types."""
    for col in df.select_dtypes(include=['int']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    for col in df.select_dtypes(include=['float']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    for col in df.select_dtypes(include=['object']).columns:
        if df[col].nunique() / len(df) < 0.5:  # < 50% unique
            df[col] = df[col].astype('category')
    return df

# Memory reduction: often 50-80%!
print(f"Before: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")
df = optimize_dtypes(df)
print(f"After: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

# === Vectorization > apply > iterrows ===
# BEST: vectorized
df['bmi'] = df['weight'] / (df['height'] / 100) ** 2

# OK: apply (still slow but sometimes necessary)
df['category'] = df['score'].apply(lambda x: 'high' if x > 80 else 'low')

# BETTER than apply for conditions: np.select
conditions = [df['score'] > 80, df['score'] > 50, df['score'] > 0]
choices = ['high', 'medium', 'low']
df['category'] = np.select(conditions, choices, default='none')

# NEVER: iterrows (100-1000x slower)
# for idx, row in df.iterrows():  # AVOID THIS

# === Large Dataset Handling ===
# Chunked reading
chunks = pd.read_csv('huge_file.csv', chunksize=100_000)
results = []
for chunk in chunks:
    processed = chunk.groupby('category')['value'].sum()
    results.append(processed)
final = pd.concat(results).groupby(level=0).sum()

# Parquet with column selection (only reads needed columns from disk)
df = pd.read_parquet('data.parquet', columns=['col1', 'col2'])

# For truly large data: consider polars, dask, or vaex
# import polars as pl
# df = pl.read_parquet('data.parquet')  # often 5-10x faster than pandas
```

## Common Pitfalls Summary

| Pitfall | Fix |
|---------|-----|
| Chained indexing (`df[cond]['col'] = val`) | Use `df.loc[cond, 'col'] = val` |
| `inplace=True` returns None | Don't assign: `df.fillna(0, inplace=True)` |
| Merge creates duplicates unexpectedly | Use `validate='one_to_many'` |
| String operations on object columns are slow | Convert to `category` dtype |
| `df.append()` in a loop | Collect list, then `pd.concat()` once |
| Not specifying dtypes on read | Use `dtype=` parameter |
| Timezone-naive datetime comparisons | Always `tz_localize` or `tz_convert` |
