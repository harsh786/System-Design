# Real-World AI/ML/DL Projects

A collection of production-quality, runnable machine learning projects progressing from classical ML to deep learning to full production pipelines.

## Projects Overview

| # | Project | Difficulty | Key Skills |
|---|---------|-----------|------------|
| 1 | House Price Prediction | Beginner | Regression, Feature Engineering, Model Comparison |
| 2 | Image Classification | Intermediate | CNNs, PyTorch, Data Augmentation |
| 3 | NLP Sentiment Analysis | Intermediate | TF-IDF, LSTM, Text Processing |
| 4 | Recommendation System | Intermediate | Collaborative Filtering, Matrix Factorization |
| 5 | Time Series Forecasting | Advanced | ARIMA, LSTM, Sequential Models |
| 6 | End-to-End ML Pipeline | Advanced | MLOps, FastAPI, Docker, Monitoring |

## Learning Path

```
Beginner                 Intermediate                    Advanced
─────────────────────────────────────────────────────────────────
[1. House Prices] ──► [2. Image Classification] ──► [5. Time Series]
                      [3. Sentiment Analysis]        [6. E2E Pipeline]
                      [4. Recommendations]
```

## Prerequisites

```bash
pip install numpy pandas scikit-learn matplotlib seaborn
pip install torch torchvision  # For deep learning projects
pip install fastapi uvicorn    # For serving project
pip install statsmodels        # For time series
```

## How to Run Any Project

```bash
cd <project-directory>
python <main_script>.py
```

All projects use built-in datasets (sklearn, torchvision) or generate synthetic data — no external downloads needed.
