# 16 - Architecture Decision Diagrams

## Why This Section Exists

> "A Staff Architect doesn't just know WHAT to use — they know WHY to use it,
> WHEN to use it, and what TRADEOFFS they're accepting."

The diagrams in this section are **decision workflows** — not just system illustrations.
Each diagram answers:
- **WHY** was this choice made?
- **WHAT TRADEOFFS** does it accept?
- **WHEN** would you choose differently?
- **WHAT BREAKS** if you choose wrong?

---

## The 6 Decision Domains

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAFF ARCHITECT DECISION SPACE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐    ┌──────────────────────────┐               │
│  │ 01. ALGORITHM        │    │ 02. TRAINING              │               │
│  │ SELECTION            │    │ INTERNALS                 │               │
│  │                      │    │                           │               │
│  │ Which algo? Why?     │    │ How training works.       │               │
│  │ Which loss? Why?     │    │ Why each step exists.     │               │
│  │ Which optimizer?     │    │ What breaks without it.   │               │
│  └──────────┬───────────┘    └─────────────┬────────────┘               │
│             │                               │                            │
│  ┌──────────▼───────────┐    ┌─────────────▼────────────┐              │
│  │ 03. SYSTEM            │    │ 04. DATA PIPELINE         │              │
│  │ ARCHITECTURE          │    │ DECISIONS                 │              │
│  │                       │    │                           │              │
│  │ Batch vs real-time?   │    │ ETL vs ELT? Streaming?   │              │
│  │ How to scale?         │    │ Feature engineering flow  │              │
│  │ When to cache?        │    │ Storage strategy          │              │
│  └──────────┬────────────┘    └─────────────┬────────────┘              │
│             │                                │                           │
│  ┌──────────▼───────────┐    ┌──────────────▼───────────┐              │
│  │ 05. MODEL LIFECYCLE   │    │ 06. LLM / GenAI           │              │
│  │ & MLOps               │    │ ARCHITECTURE              │              │
│  │                       │    │                           │              │
│  │ Dev → Prod pipeline   │    │ RAG vs fine-tune?         │              │
│  │ When to retrain?      │    │ Agent patterns            │              │
│  │ CI/CD for ML          │    │ Cost optimization         │              │
│  └───────────────────────┘    └───────────────────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Diagram Inventory (48 Mermaid diagrams)

| File | Diagrams | Key Decisions Covered |
|------|----------|----------------------|
| 01-Algorithm-Selection | 7 | Algo selection, DL arch, optimizer, loss, ensemble, regularization, attention |
| 02-Training-Pipeline | 8 | Forward/backward pass, training loop, gradient flow, data loading, distributed, mixed precision, batch norm, LR schedule |
| 03-System-Architecture | 8 | Batch vs RT, serving patterns, scaling, feature store, A/B testing, microservices, caching, fallbacks |
| 04-Data-Pipeline | 5 | ETL/ELT/streaming, feature engineering, data quality, batch vs stream features, storage |
| 05-Model-Lifecycle | 6 | Full lifecycle, MLOps maturity, monitoring/retraining, CI/CD for ML, skew prevention, retrain vs rebuild |
| 06-LLM-GenAI | 8 | RAG vs fine-tune, serving patterns, RAG deep dive, agent levels, cost optimization, guardrails, vector search, evaluation |

---

## How to Use These Diagrams

### For Learning
Read top-to-bottom. Each diagram builds on previous ones.

### For Architecture Reviews
Use as checklists: "Did we consider all these tradeoffs?"

### For Interviews
Staff/Principal interviews ask "why" — these diagrams ARE the answers.

### For Real Decisions
1. Find the relevant domain (algo? serving? data? LLM?)
2. Follow the decision tree
3. Note the WHY for your ADR (Architecture Decision Record)

---

## Quick Decision Lookup

| "I need to decide..." | Go to |
|----------------------|-------|
| Which ML algorithm to use | 01, Diagram 1 |
| CNN vs Transformer vs Gradient Boosting | 01, Diagram 2 |
| Which optimizer | 01, Diagram 3 |
| Which loss function | 01, Diagram 4 |
| How training actually works | 02, Diagrams 1-2 |
| Why ResNets work (gradient flow) | 02, Diagram 3 |
| How to speed up data loading | 02, Diagram 4 |
| Distributed training approach | 02, Diagram 5 |
| Batch vs real-time serving | 03, Diagram 1 |
| How to scale my model | 03, Diagram 3 |
| Whether to use feature store | 03, Diagram 4 |
| How to A/B test models | 03, Diagram 5 |
| ETL vs ELT vs streaming | 04, Diagram 1 |
| Feature engineering pipeline | 04, Diagram 2 |
| Data quality checks | 04, Diagram 3 |
| MLOps maturity level | 05, Diagram 2 |
| When to retrain model | 05, Diagram 3 |
| CI/CD for ML pipeline | 05, Diagram 4 |
| RAG vs fine-tuning | 06, Diagram 1 |
| LLM serving architecture | 06, Diagram 2 |
| Vector DB selection | 06, Diagram 7 |
| LLM cost optimization | 06, Diagram 5 |

---

## Rendering These Diagrams

Mermaid diagrams render in:
- **GitHub** (automatic in .md files)
- **VS Code** (with Mermaid extension)
- **Notion** (paste in code block, select Mermaid)
- **Mermaid Live Editor** (https://mermaid.live)
- **Obsidian** (native support)

For non-Mermaid environments, use:
```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Render to PNG
mmdc -i diagram.md -o diagram.png
```
