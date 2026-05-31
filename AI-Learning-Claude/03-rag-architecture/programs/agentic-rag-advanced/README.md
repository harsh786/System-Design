# Agentic RAG Advanced Demo

## What This Is

A **comprehensive Agentic RAG** demonstration showing how an AI agent reasons through complex queries using multiple tools, self-correction, and confidence-based decision making.

## Capabilities Demonstrated

| Capability | Description |
|---|---|
| **Query Decomposition** | Breaking complex queries into sub-queries with tool assignments |
| **Multi-Tool Routing** | Selecting vector search, SQL, graph lookup, or calculator per sub-query |
| **Multi-Hop Retrieval** | Chaining results across multiple retrieval steps |
| **CRAG Self-Correction** | Detecting low-relevance results and reformulating queries |
| **Confidence Scoring** | Composite scoring based on relevance, source count, claim support |
| **Abstention** | Refusing to answer when evidence is insufficient |

## How to Run

```bash
pip install -r requirements.txt
python main.py
```

No API key required — the program uses simulated LLM responses when `OPENAI_API_KEY` is not set.
To use real OpenAI calls, copy `.env.example` to `.env` and add your key.

## What You'll See

The agent thinking through 6 complex queries step-by-step:
- Simple lookup (single tool, high confidence)
- Multi-hop reasoning (chained retrievals)
- Computation (SQL + calculator)
- Multi-tool comparison (graph + SQL + vector)
- Abstention (insufficient evidence detection)
- CRAG self-correction (low relevance → reformulate → caveat)

Each query shows the full pipeline: classify → decompose → plan → execute → evaluate → generate → verify → score → decide.
