# Hallucination Prevention Pipeline

## What This Demonstrates

A complete anti-hallucination pipeline showing how production RAG systems prevent LLMs from making things up. Each defense layer is demonstrated independently so you can see what it catches.

### The 6-Layer Defense Pipeline

1. **Retrieval with Relevance Scoring** - Reject chunks below a relevance threshold. If nothing relevant is found, don't even try to answer.

2. **Context Sufficiency Check** - Even with relevant chunks, ask: "Do these chunks actually contain enough information to answer this specific question?"

3. **Grounded Generation** - Force the model to cite sources. Every claim must reference a specific chunk. No chunk = no claim.

4. **Output Verification** - Decompose the generated answer into individual claims. Verify each claim against the retrieved context. Flag unsupported claims.

5. **Confidence Scoring** - Composite score from: retrieval relevance, context coverage, citation density, claim verification rate.

6. **Decision Logic** - Based on confidence:
   - HIGH (>0.8): Answer confidently
   - MEDIUM (0.5-0.8): Answer with caveats
   - LOW (0.3-0.5): Abstain ("I don't have enough information")
   - VERY LOW (<0.3): Escalate to human

### Test Scenarios

The program runs 5 test questions showing different behaviors:
- Fully answerable questions → confident answers
- Partially answerable → caveated answers
- Unanswerable → graceful abstention
- Hallucination traps → caught and prevented
- Conflicting information → flagged

## Running

```bash
pip install -r requirements.txt
python main.py
```

Note: This uses simulated LLM responses to demonstrate the pipeline mechanics without requiring an API key. Set `USE_REAL_LLM=true` in `.env` and provide an API key to use real OpenAI calls.

## Learning Outcomes

- Understand why RAG systems hallucinate and how to prevent it
- Learn the multi-layer defense approach used in production
- See confidence scoring drive user-facing behavior
- Understand the tradeoff between helpfulness and accuracy
