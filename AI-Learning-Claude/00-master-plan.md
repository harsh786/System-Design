# World-Class AI Architect: Complete Learning Path

## Who This Is For

You are a software engineer who wants to become a **Senior/Principal AI Architect** -- someone who designs, builds, and governs enterprise AI systems at scale. This path takes you from zero to architect-level mastery.

## What Makes This Different

- Every concept is explained like a teacher explaining to a student
- Every concept has a runnable program you can execute
- Diagrams and flows for visual understanding
- Real-world examples, not toy examples
- Split into small, digestible files
- Progressive: each category builds on the previous one

---

## Learning Categories

| # | Category | What You Will Learn | Time |
|---|----------|-------------------|------|
| 01 | **Foundations** | Python for AI, APIs, LLM fundamentals, tokens, context windows | 3-4 weeks |
| 02 | **Prompt Engineering** | Chain-of-thought, few-shot, structured output, context engineering | 2-3 weeks |
| 03 | **RAG Architecture** | All 20 RAG patterns, chunking, retrieval, ingestion pipelines | 4-5 weeks |
| 04 | **Vector Databases & Embeddings** | Vector search, HNSW, IVF, embedding models, multi-tenant design | 3-4 weeks |
| 05 | **Agent Engineering** | ReAct, tool-calling, planning, multi-agent systems, memory | 4-5 weeks |
| 06 | **MCP & A2A Protocols** | Model Context Protocol, Agent-to-Agent, interoperability | 2-3 weeks |
| 07 | **Evaluation & Observability** | RAG evals, agent evals, confidence scoring, dashboards | 3-4 weeks |
| 08 | **Security & Governance** | Guardrails, prompt injection defense, auth, compliance | 3-4 weeks |
| 09 | **Production & Scaling** | Deployment, caching, load balancing, billion-request design | 3-4 weeks |
| 10 | **Enterprise Platform** | AI gateway, model routing, registries, LLMOps, AgentOps | 3-4 weeks |
| 11 | **Advanced Topics** | Streaming AI, knowledge graphs, edge AI, multi-cloud, MLOps | 3-4 weeks |
| 12 | **Interview Prep** | 100+ questions, case studies, system design walkthroughs | 2-3 weeks |

**Total estimated time: 9-12 months** (studying 1-2 hours/day)

---

## How to Use This Path

### Learning Order
```
01-foundations ──> 02-prompt-engineering ──> 03-rag-architecture
                                                    │
                                                    ▼
04-vector-databases ──> 05-agent-engineering ──> 06-mcp-a2a-protocols
                                                    │
                                                    ▼
07-evaluation ──> 08-security ──> 09-production-scaling
                                        │
                                        ▼
                  10-enterprise-platform ──> 11-advanced-topics
                                                    │
                                                    ▼
                                            12-interview-prep
```

### For Each Concept
1. **Read the explanation** -- understand the "why" before the "how"
2. **Study the diagram** -- visualize the architecture
3. **Run the program** -- hands-on practice cements understanding
4. **Modify the program** -- experiment to deepen learning
5. **Connect it** -- understand how it fits into the bigger picture

### Running Programs
Each program subfolder has:
- `README.md` -- what the program does and how to run it
- `requirements.txt` -- Python dependencies
- `main.py` (or similar) -- the runnable code
- `.env.example` -- environment variables needed

```bash
cd programs/<program-name>
pip install -r requirements.txt
cp .env.example .env  # fill in your API keys
python main.py
```

---

## Prerequisites

- Python 3.10+ installed
- Basic understanding of REST APIs
- A code editor (VS Code recommended)
- OpenAI API key (or equivalent for other providers)
- Docker installed (for later sections)
- Willingness to learn and experiment

---

## Mastery Gates

Before moving to the next category, you should be able to:

| Gate | You Must Be Able To |
|------|-------------------|
| After 01 | Call any LLM API, understand tokens/costs, build a streaming API |
| After 02 | Write production-quality prompts, use chain-of-thought, parse structured output |
| After 03 | Design a complete RAG pipeline, choose the right RAG pattern for a use case |
| After 04 | Select a vector DB, design an embedding strategy, explain HNSW vs IVF |
| After 05 | Build a tool-calling agent, design multi-agent workflows, implement memory |
| After 06 | Build an MCP server, create an A2A agent card, explain the protocols |
| After 07 | Design an eval pipeline, calculate confidence scores, build dashboards |
| After 08 | Defend against prompt injection, implement guardrails, design auth flows |
| After 09 | Deploy to production, design caching, handle billion-request scale |
| After 10 | Design an enterprise AI platform with all registries and governance |
| After 11 | Handle streaming, knowledge graphs, edge AI, multi-cloud architecture |
| After 12 | Pass any AI architect interview at FAANG-level companies |

---

## The Architect's Mindset

> "Do not build an LLM app. Build an evaluated, observable, secure, governed AI system."

An AI Architect is NOT just someone who can call GPT-4. An AI Architect:

1. **Thinks in systems** -- not features
2. **Designs for failure** -- not just the happy path
3. **Measures everything** -- if you can't measure it, you can't improve it
4. **Governs by default** -- security, privacy, compliance are not afterthoughts
5. **Optimizes for cost** -- every token has a price
6. **Plans for scale** -- what works for 100 users must work for 1 million
7. **Communicates with business** -- translates tech to business value

---

## File Naming Convention

Each category folder contains:
```
NN-category/
├── 01-concept-name.md          # Explanation file
├── 02-concept-name.md          # Next concept
├── ...
├── diagrams/                   # Architecture diagrams (Mermaid)
└── programs/                   # Runnable code
    └── program-name/
        ├── README.md
        ├── requirements.txt
        ├── main.py
        └── .env.example
```

Let's begin.
