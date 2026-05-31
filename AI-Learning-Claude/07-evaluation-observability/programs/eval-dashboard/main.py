"""
Eval Dashboard - FastAPI server for storing and visualizing evaluation results.

Features:
- Submit evaluation results via API
- Track metrics over time
- Detect quality regressions
- Serve an HTML dashboard with charts
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="AI Eval Dashboard", version="1.0.0")

# --- In-memory storage (use a real DB in production) ---
eval_results: list[dict] = []

# Seed with sample data for demo
SAMPLE_DATA = [
    {"run_id": f"run-{i}", "timestamp": (datetime.now() - timedelta(days=14-i)).isoformat(),
     "metrics": {
         "faithfulness": 0.90 + (i % 5) * 0.02 - (0.05 if i == 10 else 0),
         "relevance": 0.87 + (i % 4) * 0.02,
         "context_precision": 0.84 + (i % 3) * 0.02,
         "hallucination_rate": 0.05 - (i % 4) * 0.005 + (0.04 if i == 10 else 0),
     }}
    for i in range(14)
]
eval_results.extend(SAMPLE_DATA)


# --- Models ---


class EvalSubmission(BaseModel):
    run_id: str
    timestamp: Optional[str] = None
    metrics: dict[str, float]


class TrendResponse(BaseModel):
    metric: str
    current: float
    previous: float
    change: float
    trend: str  # "improving", "stable", "degrading"


# --- API Endpoints ---


@app.post("/api/eval")
async def submit_eval(submission: EvalSubmission):
    """Submit a new evaluation result."""
    entry = {
        "run_id": submission.run_id,
        "timestamp": submission.timestamp or datetime.now().isoformat(),
        "metrics": submission.metrics,
    }
    eval_results.append(entry)

    # Check for regressions
    regressions = detect_regressions(entry)
    return {
        "status": "accepted",
        "run_id": submission.run_id,
        "regressions": regressions,
    }


@app.get("/api/metrics")
async def get_metrics(limit: int = 50):
    """Get recent evaluation metrics."""
    recent = eval_results[-limit:]
    return {"count": len(recent), "results": recent}


@app.get("/api/trends")
async def get_trends():
    """Compute trend analysis for each metric."""
    if len(eval_results) < 4:
        return {"message": "Not enough data for trends"}

    recent = eval_results[-7:]
    older = eval_results[-14:-7] if len(eval_results) >= 14 else eval_results[:7]

    trends = []
    metric_names = recent[0]["metrics"].keys()

    for metric in metric_names:
        recent_avg = sum(r["metrics"].get(metric, 0) for r in recent) / len(recent)
        older_avg = sum(r["metrics"].get(metric, 0) for r in older) / len(older)
        change = recent_avg - older_avg

        # For hallucination_rate, negative change is good
        if "rate" in metric:
            trend = "improving" if change < -0.01 else ("degrading" if change > 0.01 else "stable")
        else:
            trend = "improving" if change > 0.01 else ("degrading" if change < -0.01 else "stable")

        trends.append({
            "metric": metric,
            "current": round(recent_avg, 4),
            "previous": round(older_avg, 4),
            "change": round(change, 4),
            "trend": trend,
        })

    return {"trends": trends}


@app.get("/api/regressions")
async def get_regressions():
    """Get all detected regressions."""
    thresholds = {
        "faithfulness": {"min": 0.90, "direction": "higher_is_better"},
        "relevance": {"min": 0.85, "direction": "higher_is_better"},
        "context_precision": {"min": 0.80, "direction": "higher_is_better"},
        "hallucination_rate": {"max": 0.05, "direction": "lower_is_better"},
    }

    regressions = []
    for entry in eval_results[-10:]:
        for metric, config in thresholds.items():
            value = entry["metrics"].get(metric)
            if value is None:
                continue
            if config["direction"] == "higher_is_better" and value < config.get("min", 0):
                regressions.append({
                    "run_id": entry["run_id"],
                    "timestamp": entry["timestamp"],
                    "metric": metric,
                    "value": value,
                    "threshold": config["min"],
                    "severity": "critical" if value < config["min"] - 0.05 else "warning",
                })
            elif config["direction"] == "lower_is_better" and value > config.get("max", 1):
                regressions.append({
                    "run_id": entry["run_id"],
                    "timestamp": entry["timestamp"],
                    "metric": metric,
                    "value": value,
                    "threshold": config["max"],
                    "severity": "critical" if value > config["max"] + 0.03 else "warning",
                })

    return {"regressions": regressions}


def detect_regressions(entry: dict) -> list[dict]:
    """Check if a new entry has any regressions vs recent average."""
    if len(eval_results) < 5:
        return []

    recent = eval_results[-5:]
    regressions = []

    for metric, value in entry["metrics"].items():
        avg = sum(r["metrics"].get(metric, value) for r in recent) / len(recent)
        if "rate" in metric:
            if value > avg * 1.5:  # 50% increase in bad metric
                regressions.append({"metric": metric, "value": value, "avg": round(avg, 4)})
        else:
            if value < avg * 0.9:  # 10% drop in good metric
                regressions.append({"metric": metric, "value": value, "avg": round(avg, 4)})

    return regressions


# --- HTML Dashboard ---


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the HTML dashboard."""
    # Prepare data for charts
    timestamps = [r["timestamp"][:10] for r in eval_results[-14:]]
    faithfulness = [r["metrics"].get("faithfulness", 0) for r in eval_results[-14:]]
    relevance = [r["metrics"].get("relevance", 0) for r in eval_results[-14:]]
    hallucination = [r["metrics"].get("hallucination_rate", 0) for r in eval_results[-14:]]

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>AI Eval Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card .value {{ font-size: 2em; font-weight: bold; }}
        .card .label {{ color: #666; font-size: 0.9em; }}
        .good {{ color: #2e7d32; }}
        .bad {{ color: #c62828; }}
        .chart-container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Evaluation Dashboard</h1>

        <div class="cards">
            <div class="card">
                <div class="value {'good' if faithfulness[-1] >= 0.9 else 'bad'}">{faithfulness[-1]:.3f}</div>
                <div class="label">Faithfulness (latest)</div>
            </div>
            <div class="card">
                <div class="value {'good' if relevance[-1] >= 0.85 else 'bad'}">{relevance[-1]:.3f}</div>
                <div class="label">Relevance (latest)</div>
            </div>
            <div class="card">
                <div class="value {'good' if hallucination[-1] <= 0.05 else 'bad'}">{hallucination[-1]:.3f}</div>
                <div class="label">Hallucination Rate (latest)</div>
            </div>
            <div class="card">
                <div class="value">{len(eval_results)}</div>
                <div class="label">Total Eval Runs</div>
            </div>
        </div>

        <div class="chart-container">
            <canvas id="qualityChart"></canvas>
        </div>

        <div class="chart-container">
            <canvas id="hallucinationChart"></canvas>
        </div>
    </div>

    <script>
        new Chart(document.getElementById('qualityChart'), {{
            type: 'line',
            data: {{
                labels: {timestamps},
                datasets: [
                    {{ label: 'Faithfulness', data: {faithfulness}, borderColor: '#2e7d32', fill: false }},
                    {{ label: 'Relevance', data: {relevance}, borderColor: '#1565c0', fill: false }},
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ title: {{ display: true, text: 'Quality Metrics Over Time' }} }},
                scales: {{ y: {{ min: 0.7, max: 1.0 }} }}
            }}
        }});

        new Chart(document.getElementById('hallucinationChart'), {{
            type: 'line',
            data: {{
                labels: {timestamps},
                datasets: [
                    {{ label: 'Hallucination Rate', data: {hallucination}, borderColor: '#c62828', fill: false }},
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ title: {{ display: true, text: 'Hallucination Rate Over Time (lower is better)' }} }},
                scales: {{ y: {{ min: 0, max: 0.15 }} }}
            }}
        }});
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    print(f"Starting Eval Dashboard on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
