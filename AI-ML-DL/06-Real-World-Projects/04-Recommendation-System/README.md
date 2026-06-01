# Project 4: Recommendation System

## What You'll Learn
- Collaborative filtering (user-based and item-based)
- Matrix factorization (SVD)
- Content-based filtering
- Hybrid approaches
- Evaluation metrics (RMSE, Precision@K, Recall@K)

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                   Recommendation Engine                       │
├─────────────────┬──────────────────┬────────────────────────┤
│  Collaborative  │  Content-Based   │   Hybrid (Weighted)    │
│  Filtering      │  Filtering       │                        │
│                 │                  │                        │
│ • User-User     │ • Item features  │ • Combine CF + CB      │
│ • Item-Item     │ • TF-IDF sim     │ • Weighted scores      │
│ • Matrix Factor │ • Cosine sim     │ • Re-rank              │
└─────────────────┴──────────────────┴────────────────────────┘
                            │
                    ┌───────▼───────┐
                    │  Top-K Recs   │
                    │  per User     │
                    └───────────────┘
```

## Prerequisites

```bash
pip install numpy pandas scikit-learn scipy
```

## How to Run

```bash
python recommendation_system.py
```

## Expected Output
- User-item matrix statistics
- RMSE for matrix factorization
- Sample recommendations for test users
- Precision@K and Recall@K metrics

## Extension Ideas
- Add implicit feedback (clicks, views)
- Neural collaborative filtering
- Real-time recommendation serving
- A/B testing framework
