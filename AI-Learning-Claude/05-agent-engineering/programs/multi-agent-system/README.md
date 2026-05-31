# Multi-Agent System

A supervisor agent that delegates work to three specialist agents.

## What This Demonstrates

- Supervisor pattern: one agent orchestrates specialists
- Three specialists: Researcher, Analyzer, Writer
- Inter-agent communication via shared state
- Supervisor decision-making (which agent to call next)
- End-to-end task: "Create a market analysis report"

## Architecture

```
            ┌─────────────┐
            │  Supervisor  │
            └──────┬──────┘
         ┌─────────┼─────────┐
         ▼         ▼         ▼
   ┌──────────┐ ┌────────┐ ┌────────┐
   │Researcher│ │Analyzer│ │ Writer │
   └──────────┘ └────────┘ └────────┘
```

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```
