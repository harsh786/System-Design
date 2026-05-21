# Production Quality Track: Evaluation, Confidence, Optimization, and Observability

**Learning level:** Advanced to production  
**Outcome:** You can ship AI changes through measurable quality gates, cost controls, confidence thresholds, tracing, and automated eval pipelines.

---

## Phase 8: Evaluation Mastery

Most AI systems fail because they are not evaluated correctly.

Evaluation layers:

| Layer | What to Evaluate |
|---|---|
| model eval | correctness, reasoning, formatting, refusal |
| prompt eval | instruction following, tone, schema adherence |
| retrieval eval | did we fetch the right docs? |
| RAG eval | groundedness, relevance, completeness |
| agent eval | tool choices, trajectory, task success |
| tool eval | arguments, side effects, API success |
| safety eval | jailbreak, PII leakage, unsafe action |
| business eval | ROI, task completion, CSAT |
| system eval | latency, uptime, throughput, cost |
| human eval | SME review, trust, escalation quality |

Golden dataset fields:

```json
{
  "id": "policy_qa_001",
  "query": "Can I claim hotel reimbursement for a delayed flight?",
  "expected_answer": "Yes, if conditions X and Y are met.",
  "acceptable_criteria": [
    "mentions delayed flight condition",
    "mentions reimbursement cap",
    "mentions receipt requirement"
  ],
  "required_sources": ["travel_policy_v4.pdf#section-7"],
  "forbidden_sources": ["travel_policy_v2.pdf"],
  "expected_tools": ["policy_search"],
  "risk_category": "finance_policy",
  "difficulty": "multi_hop",
  "tenant": "india",
  "language": "english",
  "must_refuse": false
}
```

RAG metrics:

- recall@k
- precision@k
- MRR
- nDCG
- context precision
- context recall
- faithfulness
- groundedness
- answer relevance
- answer correctness
- citation precision
- citation recall
- abstention accuracy

Agent metrics:

- task success rate
- tool selection accuracy
- tool argument accuracy
- trajectory correctness
- unnecessary tool-call rate
- loop rate
- recovery rate
- escalation precision
- side-effect safety
- cost per successful task
- latency per successful task

Milestone:

> You do not ship because the demo looks good. You ship because the system passes measurable quality, safety, latency, and cost gates.

---

## Phase 9: Confidence Scoring

Do not trust the model's self-reported confidence alone.

Create a composite confidence score:

```text
confidence =
  retrieval score
  + reranker score
  + source freshness
  + source authority
  + context coverage
  + groundedness score
  + citation support
  + answer consistency
  + tool success signal
  + risk classifier signal
  + historical performance for this intent
```

Use confidence for behavior:

| Confidence | Behavior |
|---|---|
| high | answer directly |
| medium | answer with caveat and citations |
| low | ask clarification |
| very low | abstain |
| high risk + not high confidence | human review |
| risky action | require approval |

Learn calibration:

- precision-recall curve
- ROC-AUC
- Brier score
- expected calibration error
- threshold tuning
- false positive / false negative tradeoffs

---

## Phase 10: Tuning and Optimization

Tune in the right order.

Do not fine-tune first.

Tuning layers:

| Layer | What to Tune |
|---|---|
| product | task definition, UX, risk boundaries |
| data | source quality, freshness, metadata |
| retrieval | chunking, embedding, top_k, reranker, hybrid weights |
| prompt | instructions, examples, schema, refusal behavior |
| agent | tools, max steps, graph transitions, memory, retries |
| model | model selection, fine-tuning, LoRA, SFT, DPO |
| platform | caching, routing, batching, latency, scale |

Use RAG when:

- knowledge changes often
- private data is needed
- citations are needed
- auditability is required

Use fine-tuning when:

- output style must be consistent
- extraction behavior must be stable
- smaller model must imitate larger model
- repeated task behavior matters

---

## Phase 11: Token Reduction and Cost Optimization

Token optimization improves cost and latency.

Techniques:

- compact prompts
- context budgeting
- retrieve fewer better chunks
- rerank many to few
- contextual compression
- summarize long history
- prompt caching
- semantic caching
- model routing
- output token limits
- batch embeddings
- reduce tool schema size
- use smaller models for simple tasks
- async long-running jobs

Track:

- cost per request
- cost per conversation
- cost per successful task
- cost per tenant
- token burn rate
- cache hit rate
- model cost
- retrieval cost
- eval cost
- human review cost

Architect principle:

> Optimize for cost per successful task, not only cost per request.

---

## Phase 12: Observability

A production agent without observability is a black box.

Trace:

- user input
- rewritten query
- retrieved chunks
- reranked chunks
- prompt/context sent to model
- model name/version
- token usage
- cost
- latency
- tool calls
- tool arguments
- tool outputs
- guardrail decisions
- final answer
- citations
- eval scores
- user feedback
- errors and retries

Dashboard metrics:

- p50/p95/p99 latency
- tokens per request
- cost per successful task
- retrieval recall estimate
- groundedness score
- tool error rate
- loop/timeout rate
- safety block rate
- escalation rate
- feedback score
- fallback rate
- cache hit rate
- per-tenant usage

Milestone:

> You can reconstruct why an agent produced a bad answer.

---


## Phase 18: Automated Evaluation Pipeline

```text
Developer changes prompt/tool/retriever/model
  -> unit tests
  -> golden dataset eval
  -> retrieval eval
  -> RAG eval
  -> agent trajectory eval
  -> safety eval
  -> cost/latency eval
  -> regression comparison
  -> fail build if score drops
  -> canary deploy
  -> monitor online metrics
  -> promote or rollback
```

Minimum gates:

| Gate | Example Target |
|---|---|
| retrieval recall@5 | >= 90% |
| groundedness | >= 95% for high-risk domains |
| citation correctness | >= 90% |
| tool argument accuracy | >= 95% |
| schema validity | >= 99% |
| unsafe action rate | zero critical failures |
| p95 latency | under SLO |
| cost per task | under budget |
| regression | no significant drop |

---
