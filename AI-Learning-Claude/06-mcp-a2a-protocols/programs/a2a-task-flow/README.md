# A2A Task Flow - Multi-Agent Communication

Demonstrates the full A2A task lifecycle between two agents:
- **Coordinator Agent** (port 8001): Receives user requests, delegates to specialist
- **Specialist Agent** (port 8002): Performs the actual work

## What This Demonstrates

- Agent-to-agent task delegation
- Task lifecycle: submitted → working → completed
- Agent discovery via Agent Cards
- Status polling between agents
- Error handling and timeouts
- Running multiple agents simultaneously

## Prerequisites

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

This starts BOTH agents on ports 8001 and 8002.

## Testing the Flow

```bash
# 1. Check both agent cards
curl http://localhost:8001/.well-known/agent.json
curl http://localhost:8002/.well-known/agent.json

# 2. Send a task to the coordinator
curl -X POST http://localhost:8001/tasks/send \
  -H "Content-Type: application/json" \
  -d '{"message": {"role": "user", "parts": [{"type": "text", "text": "Analyze the pros and cons of microservices"}]}}'

# 3. Poll for results (use the task_id from step 2)
curl http://localhost:8001/tasks/{task_id}
```

## Architecture

```
User → Coordinator (8001) → Specialist (8002)
                          ← polls for result ←
     ← returns final result
```
