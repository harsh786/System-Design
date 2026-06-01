# Data Visualization

## 1. Matplotlib Fundamentals

```
Matplotlib Object Hierarchy:
┌──────────────────────────────────────┐
│ Figure                                │
│  ┌────────────────┐ ┌──────────────┐ │
│  │ Axes (subplot) │ │ Axes         │ │
│  │  ┌──────────┐  │ │  ┌────────┐ │ │
│  │  │ Line2D   │  │ │  │ Bar    │ │ │
│  │  │ Text     │  │ │  │ Patch  │ │ │
│  │  │ Axis     │  │ │  │ Legend │ │ │
│  │  └──────────┘  │ │  └────────┘ │ │
│  └────────────────┘ └──────────────┘ │
└──────────────────────────────────────┘
```

```python
import matplotlib.pyplot as plt
import numpy as np

# === Object-oriented API (preferred) ===
fig, ax = plt.subplots(figsize=(10, 6))
x = np.linspace(0, 2*np.pi, 100)
ax.plot(x, np.sin(x), label='sin(x)', color='#2196F3', linewidth=2)
ax.plot(x, np.cos(x), label='cos(x)', color='#FF5722', linewidth=2, linestyle='--')
ax.set_xlabel('x', fontsize=12)
ax.set_ylabel('y', fontsize=12)
ax.set_title('Trigonometric Functions', fontsize=14, fontweight='bold')
ax.legend(loc='upper right', frameon=True)
ax.grid(True, alpha=0.3)
ax.set_xlim(0, 2*np.pi)
fig.tight_layout()
plt.savefig('trig.png', dpi=150, bbox_inches='tight')
plt.show()

# === Subplots ===
fig, axes = plt.subplots(2, 3, figsize=(15, 10))
for i, ax in enumerate(axes.flat):
    data = np.random.randn(100)
    ax.hist(data, bins=20, alpha=0.7, color=f'C{i}')
    ax.set_title(f'Distribution {i+1}')
fig.suptitle('Multiple Distributions', fontsize=16)
fig.tight_layout()

# Unequal subplot sizes with GridSpec
from matplotlib.gridspec import GridSpec
fig = plt.figure(figsize=(12, 8))
gs = GridSpec(2, 3, figure=fig)
ax_main = fig.add_subplot(gs[0, :2])    # spans 2 columns
ax_side = fig.add_subplot(gs[0, 2])      # single cell
ax_bottom = fig.add_subplot(gs[1, :])    # full bottom row
```

## 2. Common Plot Types

```python
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

np.random.seed(42)
n = 200

# === Line Plot ===
fig, ax = plt.subplots(figsize=(10, 5))
dates = pd.date_range('2024-01-01', periods=100)
values = np.cumsum(np.random.randn(100))
ax.plot(dates, values, color='steelblue')
ax.fill_between(dates, values - 1, values + 1, alpha=0.2)
ax.set_title('Time Series with Confidence Band')

# === Scatter Plot ===
fig, ax = plt.subplots(figsize=(8, 8))
x = np.random.randn(n)
y = 2*x + np.random.randn(n)*0.5
colors = np.random.randn(n)
sizes = np.abs(np.random.randn(n)) * 100
scatter = ax.scatter(x, y, c=colors, s=sizes, alpha=0.6, cmap='viridis')
fig.colorbar(scatter, label='Color Value')
ax.set_title('Scatter with Size and Color Encoding')

# === Bar Plot ===
fig, ax = plt.subplots(figsize=(10, 6))
categories = ['A', 'B', 'C', 'D', 'E']
values1 = [23, 45, 56, 78, 32]
values2 = [30, 40, 50, 60, 70]
x_pos = np.arange(len(categories))
width = 0.35
ax.bar(x_pos - width/2, values1, width, label='Group 1', color='#4CAF50')
ax.bar(x_pos + width/2, values2, width, label='Group 2', color='#2196F3')
ax.set_xticks(x_pos)
ax.set_xticklabels(categories)
ax.legend()

# === Histogram ===
fig, ax = plt.subplots(figsize=(10, 6))
data1 = np.random.normal(0, 1, 1000)
data2 = np.random.normal(2, 1.5, 1000)
ax.hist(data1, bins=40, alpha=0.5, label='N(0,1)', density=True)
ax.hist(data2, bins=40, alpha=0.5, label='N(2,1.5)', density=True)
ax.legend()
ax.set_title('Overlapping Histograms')

# === Box Plot ===
fig, ax = plt.subplots(figsize=(10, 6))
data = [np.random.normal(m, 1, 100) for m in range(5)]
bp = ax.boxplot(data, patch_artist=True, labels=[f'Group {i}' for i in range(5)])
for patch, color in zip(bp['boxes'], plt.cm.Set2(np.linspace(0, 1, 5))):
    patch.set_facecolor(color)

# === Violin Plot ===
fig, ax = plt.subplots(figsize=(10, 6))
parts = ax.violinplot(data, showmeans=True, showmedians=True)
```

## 3. Seaborn for Statistical Visualization

```python
import seaborn as sns
import pandas as pd

# Load sample dataset
tips = sns.load_dataset('tips')

# === Relational plots ===
sns.relplot(data=tips, x='total_bill', y='tip', hue='smoker',
            style='time', size='size', col='day', col_wrap=2,
            kind='scatter', alpha=0.7, height=4)

# === Distribution plots ===
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
sns.histplot(tips['total_bill'], kde=True, ax=axes[0])
sns.kdeplot(data=tips, x='total_bill', hue='time', ax=axes[1])
sns.ecdfplot(data=tips, x='total_bill', hue='day', ax=axes[2])

# === Categorical plots ===
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
sns.boxplot(data=tips, x='day', y='total_bill', hue='smoker', ax=axes[0,0])
sns.violinplot(data=tips, x='day', y='total_bill', split=True, hue='sex', ax=axes[0,1])
sns.swarmplot(data=tips, x='day', y='total_bill', hue='sex', ax=axes[1,0], size=3)
sns.barplot(data=tips, x='day', y='total_bill', hue='sex', ci=95, ax=axes[1,1])

# === Heatmap (correlation matrix) ===
fig, ax = plt.subplots(figsize=(8, 6))
corr = tips.select_dtypes(include='number').corr()
sns.heatmap(corr, annot=True, cmap='coolwarm', center=0, vmin=-1, vmax=1,
            square=True, fmt='.2f', ax=ax)

# === Pairplot (quick EDA) ===
sns.pairplot(tips, hue='smoker', diag_kind='kde', corner=True)

# === Joint plot ===
sns.jointplot(data=tips, x='total_bill', y='tip', kind='hex', marginal_kws={'bins': 30})

# === Regression plot ===
sns.lmplot(data=tips, x='total_bill', y='tip', hue='smoker',
           col='time', robust=True, height=5)
```

## 4. Plotly for Interactive Plots

```python
import plotly.express as px
import plotly.graph_objects as go

# === Quick interactive plots with plotly.express ===
df = px.data.gapminder()

# Animated scatter
fig = px.scatter(
    df, x='gdpPercap', y='lifeExp',
    size='pop', color='continent',
    hover_name='country', log_x=True,
    animation_frame='year', animation_group='country',
    size_max=60, range_y=[25, 90],
    title='Gapminder: Life Expectancy vs GDP'
)
fig.show()

# Sunburst chart
fig = px.sunburst(df[df['year']==2007], path=['continent', 'country'],
                  values='pop', color='lifeExp', color_continuous_scale='RdYlGn')
fig.show()

# === Graph Objects for full control ===
fig = go.Figure()
fig.add_trace(go.Scatter(x=x, y=np.sin(x), mode='lines', name='sin'))
fig.add_trace(go.Scatter(x=x, y=np.cos(x), mode='lines', name='cos'))
fig.update_layout(
    title='Interactive Trig Functions',
    xaxis_title='x', yaxis_title='y',
    template='plotly_white',
    hovermode='x unified'
)

# === Subplots in Plotly ===
from plotly.subplots import make_subplots
fig = make_subplots(rows=2, cols=2, subplot_titles=['A', 'B', 'C', 'D'])
fig.add_trace(go.Histogram(x=np.random.randn(500)), row=1, col=1)
fig.add_trace(go.Box(y=np.random.randn(500)), row=1, col=2)
fig.update_layout(height=600, showlegend=False)
fig.show()
```

## 5. Choosing the Right Chart Type

```
┌─────────────────────────────────────────────────────────────┐
│              CHART SELECTION FLOWCHART                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  What do you want to show?                                   │
│  │                                                           │
│  ├─ COMPARISON ─────── Few items? ── Bar chart               │
│  │                     Many items? ── Dot plot / Lollipop    │
│  │                     Over time? ─── Line chart             │
│  │                                                           │
│  ├─ DISTRIBUTION ───── One variable? ── Histogram / KDE     │
│  │                     Compare groups? ─ Box / Violin        │
│  │                     Two variables? ── 2D Histogram / Hex  │
│  │                                                           │
│  ├─ RELATIONSHIP ───── Two numeric? ──── Scatter             │
│  │                     + categorical? ── Scatter + hue       │
│  │                     Many variables? ── Pairplot / Heatmap │
│  │                                                           │
│  ├─ COMPOSITION ────── At a point? ──── Pie / Stacked bar   │
│  │                     Over time? ────── Stacked area        │
│  │                     Hierarchical? ─── Treemap / Sunburst  │
│  │                                                           │
│  └─ TREND/CHANGE ───── Time series? ─── Line + confidence   │
│                        Before/after? ── Slope chart          │
│                        Geospatial? ──── Choropleth map       │
└─────────────────────────────────────────────────────────────┘
```

## 6. Color Theory for Data Viz

```python
# Sequential: for ordered data (low → high)
# 'viridis', 'plasma', 'inferno', 'magma', 'cividis'
# These are perceptually uniform and colorblind-safe

# Diverging: for data with meaningful center (e.g., correlation)
# 'coolwarm', 'RdBu', 'BrBG', 'PiYG'

# Categorical: for distinct groups
# 'Set2', 'tab10', 'Dark2'

# RULES:
# 1. Never use rainbow/jet (not perceptually uniform)
# 2. Use sequential for continuous data
# 3. Use diverging when there's a meaningful midpoint
# 4. Max 7-8 colors for categorical (human limit)
# 5. Test with colorblind simulator (e.g., coblis.myndex.com)

# Custom color palette
custom_palette = ['#264653', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51']
sns.set_palette(custom_palette)
```

## 7. Publication-Quality Figures

```python
# Style setup for papers/presentations
plt.rcParams.update({
    'font.size': 12,
    'font.family': 'serif',
    'axes.labelsize': 14,
    'axes.titlesize': 16,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 11,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Or use a built-in style
plt.style.use('seaborn-v0_8-whitegrid')

# Example publication figure
fig, ax = plt.subplots(figsize=(7, 5))
x = np.linspace(0, 10, 100)
for i, (alpha, label) in enumerate([(0.1, 'α=0.1'), (0.5, 'α=0.5'), (1.0, 'α=1.0')]):
    y = np.exp(-alpha * x)
    ax.plot(x, y, label=label, linewidth=2)

ax.set_xlabel('Time (s)')
ax.set_ylabel('Amplitude')
ax.set_title('Exponential Decay')
ax.legend(frameon=False)
ax.set_ylim(0, 1.05)
fig.savefig('publication_figure.pdf')  # Vector format for papers
fig.savefig('publication_figure.png', dpi=300)  # Raster for web
```

## 8. Dashboard Creation

```python
# Multi-panel dashboard with matplotlib
fig = plt.figure(figsize=(16, 10))
gs = GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.3)

# KPI cards (top row)
for i, (metric, value) in enumerate([('Revenue', '$1.2M'), ('Users', '45.2K'), ('Growth', '+12%')]):
    ax = fig.add_subplot(gs[0, i])
    ax.text(0.5, 0.6, value, fontsize=28, fontweight='bold', ha='center', va='center')
    ax.text(0.5, 0.2, metric, fontsize=14, ha='center', va='center', color='gray')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

# Time series (middle, spanning 2 cols)
ax_ts = fig.add_subplot(gs[1, :2])
dates = pd.date_range('2024-01-01', periods=90)
ax_ts.plot(dates, np.cumsum(np.random.randn(90)) + 50)
ax_ts.set_title('Daily Revenue Trend')

# Pie chart
ax_pie = fig.add_subplot(gs[1, 2])
ax_pie.pie([35, 25, 20, 20], labels=['Product A', 'B', 'C', 'D'], autopct='%1.0f%%')

# Bar chart (bottom)
ax_bar = fig.add_subplot(gs[2, :])
categories = [f'Region {i}' for i in range(8)]
ax_bar.barh(categories, np.random.uniform(50, 200, 8), color='steelblue')
ax_bar.set_title('Revenue by Region')

plt.savefig('dashboard.png', dpi=150, facecolor='white')
```

## 9. Visualization Best Practices

| Principle | Do | Don't |
|-----------|-----|-------|
| Data-ink ratio | Remove chartjunk, minimize non-data ink | 3D effects, heavy gridlines |
| Clarity | Label axes, include units | Rely on legend for everything |
| Honesty | Start y-axis at 0 for bars | Truncate axes to exaggerate |
| Accessibility | Colorblind-safe palettes | Red-green only encoding |
| Context | Add annotations for key events | Let viewer guess significance |

```python
# Good annotation example
fig, ax = plt.subplots(figsize=(12, 6))
dates = pd.date_range('2024-01-01', periods=365)
stock = 100 + np.cumsum(np.random.randn(365) * 2)
ax.plot(dates, stock, color='steelblue', linewidth=1.5)

# Annotate important events
ax.annotate('Product Launch', xy=(dates[60], stock[60]),
            xytext=(dates[80], stock[60] + 15),
            arrowprops=dict(arrowstyle='->', color='red'),
            fontsize=11, color='red')
ax.axvline(dates[60], color='red', linestyle='--', alpha=0.5)
ax.set_title('Stock Price with Key Events')
```

## 10. Performance Tips

```python
# For large datasets (>100K points):
# 1. Use rasterized=True for scatter plots
ax.scatter(x, y, rasterized=True)  # vector axes, raster points

# 2. Datashader for millions of points
# import datashader as ds
# canvas = ds.Canvas(plot_width=800, plot_height=600)
# agg = canvas.points(df, 'x', 'y')

# 3. Downsample before plotting
from scipy.signal import decimate
downsampled = decimate(signal, q=10)  # reduce by factor of 10

# 4. Use Agg backend for non-interactive (faster rendering)
import matplotlib
matplotlib.use('Agg')  # before importing pyplot

# 5. Batch save with minimal overhead
fig, ax = plt.subplots()
for i in range(100):
    ax.clear()
    ax.plot(data[i])
    fig.savefig(f'frame_{i:03d}.png')
plt.close(fig)  # free memory
```
