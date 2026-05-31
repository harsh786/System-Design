# Capstone Enterprise AI System

A complete, runnable mini-enterprise AI platform demonstrating all major components
working together: API Gateway, AI Router, RAG Pipeline, Agent System, Guardrails,
Observability, Cost Tracking, and more.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: configure API key
cp .env.example .env
# Edit .env with your OpenAI key (or leave blank for simulated mode)

# Run the server
python main.py

# In another terminal, run tests
python test_queries.py
```

## Architecture

```
User → API Gateway → Auth → AI Gateway → Router
                                            ├── Simple → Direct LLM
                                            ├── Medium → RAG Pipeline
                                            └── Complex → Agent Pipeline
```

## Files

| File | Purpose |
|------|---------|
| main.py | FastAPI app, entry point, routes |
| config.py | All configuration and settings |
| gateway.py | AI Gateway: routing, rate limiting, cost |
| router.py | Complexity classifier, pipeline dispatcher |
| rag_pipeline.py | RAG: embed → search → rerank → generate |
| agent_pipeline.py | Agent: plan → tools → evaluate → generate |
| guardrails.py | Input/output safety checks |
| memory.py | Session and user memory |
| observability.py | Tracing and metrics |
| evaluation.py | Confidence scoring, faithfulness |
| cost_tracker.py | Per-request and per-user cost tracking |
| auth.py | JWT authentication |
| knowledge_base.py | Sample documents + ChromaDB |
| tools.py | Agent tools (search, calculator, etc.) |
| test_queries.py | End-to-end test script |

## Modes

- **With OpenAI key**: Real LLM responses
- **Without key**: Simulated responses (same architecture, deterministic output)
