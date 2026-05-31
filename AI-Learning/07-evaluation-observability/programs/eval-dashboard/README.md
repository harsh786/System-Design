# Eval Dashboard

## What This Does

A FastAPI-based evaluation dashboard that stores, serves, and visualizes evaluation results over time. Detects quality regressions and provides an HTML dashboard with charts.

## Features

- **Submit eval results** — POST evaluation scores from your CI/CD pipeline
- **Get metrics over time** — Track quality trends
- **Regression detection** — Alerts when quality drops significantly
- **HTML dashboard** — Simple visual dashboard with embedded charts
- **Running averages** — Smoothed metrics for trend analysis

## Setup

```bash
cp .env.example .env
pip install -r requirements.txt
python main.py
```

Then open http://localhost:8000 for the dashboard.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | HTML dashboard |
| POST | `/api/eval` | Submit evaluation result |
| GET | `/api/metrics` | Get all metrics |
| GET | `/api/trends` | Get trend analysis |
| GET | `/api/regressions` | Get detected regressions |

## Example: Submit Eval Result

```bash
curl -X POST http://localhost:8000/api/eval \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "pr-123",
    "timestamp": "2024-01-15T10:30:00Z",
    "metrics": {
      "faithfulness": 0.94,
      "relevance": 0.91,
      "context_precision": 0.87,
      "hallucination_rate": 0.03
    }
  }'
```
