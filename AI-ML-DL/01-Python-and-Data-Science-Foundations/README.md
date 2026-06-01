# Python and Data Science Foundations

## Overview

This module covers the essential Python ecosystem for data science, machine learning, and deep learning. Mastering these foundations is critical before advancing to ML algorithms and neural networks.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA SCIENCE PYTHON STACK                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  NumPy   │  │  Pandas  │  │Matplotlib│  │   Scikit-    │   │
│  │          │  │          │  │ Seaborn  │  │   Learn      │   │
│  │ Arrays & │  │DataFrames│  │  Plotly  │  │              │   │
│  │ Linear   │  │  & Data  │  │          │  │  ML Models   │   │
│  │ Algebra  │  │ Wrangling│  │   Viz    │  │  & Metrics   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │              │              │               │            │
│       └──────────────┴──────────────┴───────────────┘            │
│                          │                                        │
│                    ┌─────┴─────┐                                  │
│                    │  Python   │                                  │
│                    │  3.10+    │                                  │
│                    └───────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

| # | Topic | Key Skills |
|---|-------|-----------|
| 01 | **NumPy** | ndarray, broadcasting, vectorization, linear algebra |
| 02 | **Pandas** | DataFrame ops, groupby, merge, time series |
| 03 | **Visualization** | Matplotlib, Seaborn, Plotly, chart selection |
| 04 | **EDA** | Statistical analysis, outlier detection, distributions |
| 05 | **Feature Engineering** | Encoding, scaling, feature selection, creation |

## Environment Setup

```bash
# Create virtual environment
python -m venv ds-env
source ds-env/bin/activate  # Linux/Mac
# ds-env\Scripts\activate   # Windows

# Install core packages
pip install numpy pandas matplotlib seaborn plotly scikit-learn
pip install jupyterlab ipython

# Optional but recommended
pip install pandas-profiling sweetviz featuretools
```

## Why These Foundations Matter

```
Raw Data → [NumPy/Pandas] → Clean Data → [EDA/Viz] → Insights → [Feature Eng] → ML-Ready Data
```

1. **NumPy** - The computational backbone. Every ML library (TensorFlow, PyTorch, scikit-learn) is built on NumPy arrays.
2. **Pandas** - Real-world data is messy. Pandas handles loading, cleaning, transforming tabular data.
3. **Visualization** - You cannot model what you don't understand. Viz reveals patterns, outliers, relationships.
4. **EDA** - Systematic exploration prevents garbage-in-garbage-out. Understand distributions, correlations, quality.
5. **Feature Engineering** - The single biggest lever for model performance. Domain knowledge encoded as features.

## Learning Path

```
Week 1: NumPy fundamentals + Pandas basics
Week 2: Pandas advanced + Visualization
Week 3: EDA methodology + practice on real datasets
Week 4: Feature Engineering + end-to-end mini-project
```

## Key Principles

- **Vectorize everything** - Avoid Python loops over arrays/DataFrames
- **Memory matters** - Choose appropriate dtypes, use chunking for large data
- **Reproducibility** - Set random seeds, document transformations
- **Validation** - Always check shapes, dtypes, null counts after operations
