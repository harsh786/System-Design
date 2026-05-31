# Agentic RAG Implementation

The most advanced RAG pattern: an **agent** that decides what to retrieve, evaluates results, refines queries, and knows when to abstain.

## What Makes This "Agentic"

Unlike static RAG pipelines, the agent:
1. **Decides IF** retrieval is needed
2. **Chooses WHAT** to search for (may differ from user's exact words)
3. **Evaluates** retrieved results for relevance
4. **Iterates**: refines the query and searches again if needed
5. **Abstains**: says "I don't know" when evidence is insufficient

## Agent Decision Flow

```
User Query
    → Agent thinks: "Do I need to search?"
    → If yes: "What exactly should I search for?"
    → Search → Evaluate results
    → "Are these sufficient? Or do I need a different angle?"
    → If insufficient: refine query → search again
    → If sufficient: generate answer with confidence score
    → If still insufficient after retries: abstain
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Watch the Agent Think

The output shows the agent's reasoning at every step — you'll see it
decide, search, evaluate, and iterate (or abstain).
