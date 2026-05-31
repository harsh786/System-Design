# Cost Tracker - AI Spend Management

Tracks every AI API call, aggregates costs, enforces budgets, and provides
spending reports.

## What This Demonstrates

- **Per-request cost recording** (model, tokens, cost, user, timestamp)
- **Aggregation** by user, model, day, and endpoint
- **Budget enforcement** with alerts at 80% and blocking at 100%
- **Reporting** - daily costs, top spenders, trends
- **Simple HTML dashboard** for visualization

## Running

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

## API Endpoints

```bash
# Record a usage event
POST /usage

# Get cost summary
GET /summary

# Get costs by user
GET /costs/by-user

# Get costs by model
GET /costs/by-model

# Get daily costs
GET /costs/daily

# Check budget status
GET /budget/{user_id}

# Set budget for a user
PUT /budget/{user_id}

# Dashboard (HTML)
GET /dashboard
```

## Example

```bash
# Record usage
curl -X POST http://localhost:8002/usage -H "Content-Type: application/json" -d '{
  "user_id": "user-123",
  "model": "gpt-4o",
  "input_tokens": 500,
  "output_tokens": 200,
  "endpoint": "/chat"
}'

# Check budget
curl http://localhost:8002/budget/user-123

# View dashboard
open http://localhost:8002/dashboard
```
