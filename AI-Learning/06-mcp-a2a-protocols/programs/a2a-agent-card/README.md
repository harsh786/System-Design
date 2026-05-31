# A2A Agent Card Server

A FastAPI server implementing the A2A (Agent-to-Agent) protocol with:
- Agent Card discovery at `/.well-known/agent.json`
- Task submission and lifecycle management
- Skill-based capabilities

## What This Demonstrates

- Hosting an Agent Card at the well-known URL
- Defining agent capabilities and skills
- Task submission endpoint
- Task lifecycle: submitted → working → completed
- Agent discovery pattern

## Prerequisites

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
# Server starts at http://localhost:8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/.well-known/agent.json` | Agent Card (discovery) |
| POST | `/tasks/send` | Submit a new task |
| GET | `/tasks/{task_id}` | Get task status |

## Testing

```bash
# Discover the agent
curl http://localhost:8000/.well-known/agent.json

# Submit a task
curl -X POST http://localhost:8000/tasks/send \
  -H "Content-Type: application/json" \
  -d '{"message": {"role": "user", "parts": [{"type": "text", "text": "Summarize AI trends"}]}}'

# Check task status
curl http://localhost:8000/tasks/{task_id}
```
