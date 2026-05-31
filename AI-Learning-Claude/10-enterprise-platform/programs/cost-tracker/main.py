"""
Cost Tracker - AI Spend Management Service

Records every AI API call, aggregates costs, enforces budgets, and provides reports.
"""

from collections import defaultdict
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Cost Tracker", description="AI spend management and budget enforcement")

# --- Configuration ---

MODEL_PRICING = {
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}

DEFAULT_DAILY_BUDGET = 10.00  # dollars per user per day

# --- Models ---


class UsageEvent(BaseModel):
    user_id: str
    model: str
    input_tokens: int
    output_tokens: int = 0
    endpoint: str = "/chat"
    metadata: dict = {}


class BudgetConfig(BaseModel):
    daily_limit: float
    alert_threshold: float = 0.8  # Alert at 80%


# --- Storage ---

usage_records: list[dict] = []
budgets: dict[str, BudgetConfig] = {}


# --- Helpers ---


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0.005, "output": 0.015})
    return (input_tokens / 1000) * pricing["input"] + \
           (output_tokens / 1000) * pricing["output"]


def get_user_daily_spend(user_id: str, day: Optional[date] = None) -> float:
    target_day = day or date.today()
    return sum(
        r["cost"] for r in usage_records
        if r["user_id"] == user_id and r["date"] == target_day.isoformat()
    )


# --- Seed Data ---


def seed_data():
    """Add sample usage data for demonstration."""
    today = date.today().isoformat()
    sample_events = [
        {"user_id": "alice", "model": "gpt-4o", "input_tokens": 1500, "output_tokens": 800, "endpoint": "/chat", "cost": 0.0195, "date": today, "timestamp": datetime.utcnow().isoformat()},
        {"user_id": "alice", "model": "gpt-4o-mini", "input_tokens": 500, "output_tokens": 300, "endpoint": "/chat", "cost": 0.000255, "date": today, "timestamp": datetime.utcnow().isoformat()},
        {"user_id": "bob", "model": "gpt-4o", "input_tokens": 3000, "output_tokens": 1500, "endpoint": "/analysis", "cost": 0.0375, "date": today, "timestamp": datetime.utcnow().isoformat()},
        {"user_id": "bob", "model": "text-embedding-3-small", "input_tokens": 10000, "output_tokens": 0, "endpoint": "/embed", "cost": 0.0002, "date": today, "timestamp": datetime.utcnow().isoformat()},
        {"user_id": "carol", "model": "gpt-3.5-turbo", "input_tokens": 200, "output_tokens": 100, "endpoint": "/chat", "cost": 0.00025, "date": today, "timestamp": datetime.utcnow().isoformat()},
    ]
    usage_records.extend(sample_events)
    budgets["alice"] = BudgetConfig(daily_limit=5.00)
    budgets["bob"] = BudgetConfig(daily_limit=10.00)


seed_data()


# --- API Endpoints ---


@app.post("/usage", status_code=201)
async def record_usage(event: UsageEvent):
    """Record an AI API usage event."""
    cost = calculate_cost(event.model, event.input_tokens, event.output_tokens)
    today = date.today().isoformat()

    # Check budget before recording
    user_budget = budgets.get(event.user_id)
    if user_budget:
        current_spend = get_user_daily_spend(event.user_id)
        if current_spend + cost > user_budget.daily_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Budget exceeded",
                    "daily_limit": user_budget.daily_limit,
                    "current_spend": round(current_spend, 6),
                    "requested_cost": round(cost, 6),
                }
            )

    record = {
        "user_id": event.user_id,
        "model": event.model,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "endpoint": event.endpoint,
        "cost": cost,
        "date": today,
        "timestamp": datetime.utcnow().isoformat(),
    }
    usage_records.append(record)

    # Check alert threshold
    alert = None
    if user_budget:
        new_spend = get_user_daily_spend(event.user_id)
        if new_spend > user_budget.daily_limit * user_budget.alert_threshold:
            alert = f"WARNING: User '{event.user_id}' at {new_spend/user_budget.daily_limit*100:.0f}% of daily budget"

    return {"cost": round(cost, 6), "total_tokens": event.input_tokens + event.output_tokens, "alert": alert}


@app.get("/summary")
async def get_summary():
    """Get overall cost summary."""
    total_cost = sum(r["cost"] for r in usage_records)
    total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in usage_records)
    return {
        "total_cost": round(total_cost, 6),
        "total_requests": len(usage_records),
        "total_tokens": total_tokens,
        "unique_users": len(set(r["user_id"] for r in usage_records)),
        "models_used": list(set(r["model"] for r in usage_records)),
    }


@app.get("/costs/by-user")
async def costs_by_user():
    """Aggregate costs by user."""
    user_costs = defaultdict(lambda: {"cost": 0.0, "requests": 0, "tokens": 0})
    for r in usage_records:
        user_costs[r["user_id"]]["cost"] += r["cost"]
        user_costs[r["user_id"]]["requests"] += 1
        user_costs[r["user_id"]]["tokens"] += r["input_tokens"] + r["output_tokens"]

    return {
        "by_user": [
            {"user_id": uid, "cost": round(d["cost"], 6), "requests": d["requests"], "tokens": d["tokens"]}
            for uid, d in sorted(user_costs.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]
    }


@app.get("/costs/by-model")
async def costs_by_model():
    """Aggregate costs by model."""
    model_costs = defaultdict(lambda: {"cost": 0.0, "requests": 0, "tokens": 0})
    for r in usage_records:
        model_costs[r["model"]]["cost"] += r["cost"]
        model_costs[r["model"]]["requests"] += 1
        model_costs[r["model"]]["tokens"] += r["input_tokens"] + r["output_tokens"]

    return {
        "by_model": [
            {"model": m, "cost": round(d["cost"], 6), "requests": d["requests"], "tokens": d["tokens"]}
            for m, d in sorted(model_costs.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]
    }


@app.get("/costs/daily")
async def costs_daily():
    """Aggregate costs by day."""
    daily_costs = defaultdict(lambda: {"cost": 0.0, "requests": 0})
    for r in usage_records:
        daily_costs[r["date"]]["cost"] += r["cost"]
        daily_costs[r["date"]]["requests"] += 1

    return {
        "daily": [
            {"date": d, "cost": round(v["cost"], 6), "requests": v["requests"]}
            for d, v in sorted(daily_costs.items())
        ]
    }


@app.get("/budget/{user_id}")
async def get_budget(user_id: str):
    """Check budget status for a user."""
    budget = budgets.get(user_id, BudgetConfig(daily_limit=DEFAULT_DAILY_BUDGET))
    current_spend = get_user_daily_spend(user_id)
    pct_used = (current_spend / budget.daily_limit * 100) if budget.daily_limit > 0 else 0

    return {
        "user_id": user_id,
        "daily_limit": budget.daily_limit,
        "current_spend": round(current_spend, 6),
        "remaining": round(budget.daily_limit - current_spend, 6),
        "percent_used": round(pct_used, 1),
        "status": "blocked" if pct_used >= 100 else "warning" if pct_used >= 80 else "ok",
    }


@app.put("/budget/{user_id}")
async def set_budget(user_id: str, config: BudgetConfig):
    """Set or update budget for a user."""
    budgets[user_id] = config
    return {"message": f"Budget updated for '{user_id}'", "config": config.model_dump()}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard showing costs."""
    total_cost = sum(r["cost"] for r in usage_records)
    total_requests = len(usage_records)

    # By user
    user_costs = defaultdict(float)
    for r in usage_records:
        user_costs[r["user_id"]] += r["cost"]

    # By model
    model_costs = defaultdict(float)
    for r in usage_records:
        model_costs[r["model"]] += r["cost"]

    user_rows = "".join(
        f"<tr><td>{u}</td><td>${c:.4f}</td></tr>"
        for u, c in sorted(user_costs.items(), key=lambda x: x[1], reverse=True)
    )
    model_rows = "".join(
        f"<tr><td>{m}</td><td>${c:.4f}</td></tr>"
        for m, c in sorted(model_costs.items(), key=lambda x: x[1], reverse=True)
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Cost Dashboard</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; }}
            h1 {{ color: #333; }}
            .metric {{ display: inline-block; background: #f5f5f5; padding: 20px; margin: 10px; border-radius: 8px; min-width: 150px; text-align: center; }}
            .metric .value {{ font-size: 2em; font-weight: bold; color: #2196F3; }}
            .metric .label {{ color: #666; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f5f5f5; }}
        </style>
    </head>
    <body>
        <h1>AI Cost Dashboard</h1>
        <div>
            <div class="metric">
                <div class="value">${total_cost:.4f}</div>
                <div class="label">Total Spend</div>
            </div>
            <div class="metric">
                <div class="value">{total_requests}</div>
                <div class="label">Total Requests</div>
            </div>
            <div class="metric">
                <div class="value">{len(user_costs)}</div>
                <div class="label">Active Users</div>
            </div>
        </div>
        <h2>Cost by User</h2>
        <table><tr><th>User</th><th>Cost</th></tr>{user_rows}</table>
        <h2>Cost by Model</h2>
        <table><tr><th>Model</th><th>Cost</th></tr>{model_rows}</table>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
