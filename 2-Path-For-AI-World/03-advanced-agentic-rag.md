# Advanced Track: Agentic RAG

**Learning level:** Advanced RAG architect  
**Outcome:** You can design systems that retrieve iteratively, verify evidence, compute confidence, abstain when needed, and escalate risky or uncertain cases.

---

## Phase 3: Advanced RAG and Agentic RAG

Agentic RAG allows the agent to plan retrieval, choose tools, retrieve iteratively, verify evidence, and decide whether to answer.

Agentic RAG flow:

```text
User asks complex question
  -> classify intent and risk
  -> decompose question
  -> choose retrieval tools
  -> retrieve from multiple sources
  -> rerank evidence
  -> check evidence sufficiency
  -> retrieve again if needed
  -> generate cited answer
  -> verify claims
  -> compute confidence
  -> answer, ask clarification, abstain, or escalate
```

Master:

- multi-hop retrieval
- query planning
- iterative retrieval
- tool-augmented retrieval
- source authority ranking
- evidence sufficiency scoring
- claim-level verification
- answer abstention
- human escalation
- memory-aware retrieval
- Graph RAG
- SQL + vector hybrid systems
- source freshness handling

Build:

- Agentic RAG assistant for policy Q&A
- iterative retrieval
- SQL tool
- API tool
- citation verifier
- confidence score
- abstention logic
- human escalation workflow

Milestone:

> Your system plans, retrieves, verifies, cites, and knows when not to answer.

---
