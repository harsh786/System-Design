# Planner-Executor Agent

Demonstrates the plan-then-execute pattern with re-planning on failure.

## What This Demonstrates

- Separation of planning and execution into distinct LLM calls
- Structured plan generation (JSON steps with dependencies)
- Step-by-step execution with result tracking
- Re-planning when a step fails
- A complex task: "Research, compare, and recommend a tech stack"

## Architecture

```
User Task → [Planner Agent] → Plan (steps) → [Executor Agent] → Results
                  ↑                                    │
                  └──── Re-plan on failure ────────────┘
```

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```
