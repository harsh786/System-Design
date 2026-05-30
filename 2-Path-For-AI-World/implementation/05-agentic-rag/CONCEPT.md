# Agentic RAG: Deep Conceptual Guide

## 1. What Makes RAG "Agentic"?

Traditional RAG follows a fixed pipeline: embed query → retrieve top-K → generate answer. It is **reactive** and **single-shot**. Agentic RAG introduces autonomous decision-making into every stage:

| Capability | Traditional RAG | Agentic RAG |
|---|---|---|
| Query handling | Verbatim embedding | Planning, decomposition, reformulation |
| Retrieval | Single-shot top-K | Iterative, multi-source, tool-augmented |
| Evaluation | None | Sufficiency checking, re-retrieval |
| Generation | Single pass | Claim verification, grounding checks |
| Output | Always answers | Answer / Caveat / Clarify / Abstain / Escalate |
| Confidence | None | Multi-signal composite score |
| Memory | Stateless | Conversation-aware, preference-aware |

### The Five Pillars of Agentic RAG

**1. Planning** — The agent reasons about *how* to answer before retrieving. It classifies intent, assesses risk, decomposes complex queries, and selects appropriate tools.

**2. Iteration** — The agent retrieves, evaluates what it got, and decides whether to retrieve more, reformulate, or switch sources. It has a stopping criterion rather than a fixed number of retrievals.

**3. Verification** — Every claim in the generated answer is traced back to source evidence. Unsupported claims are removed or flagged.

**4. Confidence** — A composite score from multiple signals (retrieval quality, source authority, groundedness, consistency) drives behavior.

**5. Abstention** — The agent knows when it *doesn't know*. Rather than hallucinating, it abstains, asks for clarification, or escalates to a human.

---

## 2. Agentic RAG Complete Flow

```
User Query
    │
    ▼
┌─────────────────────┐
│ 1. CLASSIFY INTENT  │  → informational / transactional / navigational / ambiguous
│    & ASSESS RISK    │  → low / medium / high / critical
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 2. DECOMPOSE QUERY  │  → single query (pass-through) or sub-questions with dependency DAG
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────┐
│ 3. CHOOSE TOOLS/SOURCES │  → vector DB, SQL, knowledge graph, API, web search
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────────┐
│ 4. RETRIEVE (per sub-query) │  → parallel execution where possible
└─────────┬───────────────────┘
          │
          ▼
┌──────────────────────┐
│ 5. RERANK & FILTER   │  → cross-encoder reranking, authority weighting, freshness decay
└─────────┬────────────┘
          │
          ▼
┌──────────────────────────────┐
│ 6. CHECK EVIDENCE SUFFICIENCY│  → coverage score per sub-question
│    Sufficient? ──────────────┼──NO──→ Reformulate query → back to step 3/4
└─────────┬────────────────────┘         (max N iterations)
          │ YES
          ▼
┌─────────────────────┐
│ 7. GENERATE ANSWER  │  → with inline citation markers
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────┐
│ 8. VERIFY CLAIMS        │  → each sentence checked against retrieved evidence
│    All grounded? ───────┼──NO──→ Remove/flag ungrounded claims
└─────────┬───────────────┘
          │ YES
          ▼
┌──────────────────────────┐
│ 9. COMPUTE CONFIDENCE    │  → composite score from 8+ signals
└─────────┬────────────────┘
          │
          ▼
┌──────────────────────────────────────────────┐
│ 10. DECIDE OUTPUT ACTION                      │
│     confidence ≥ 0.85  → ANSWER              │
│     confidence 0.65-0.85 → ANSWER + CAVEAT   │
│     confidence 0.40-0.65 → ASK CLARIFICATION │
│     confidence < 0.40  → ABSTAIN             │
│     risk=critical & conf<0.90 → ESCALATE     │
└──────────────────────────────────────────────┘
```

---

## 3. Multi-Hop Retrieval Patterns

Multi-hop retrieval is needed when the answer requires connecting information across multiple documents or reasoning steps.

### Pattern 1: Sequential Chain
```
Q: "What is the revenue of the CEO's alma mater?"
  → Sub-Q1: "Who is the CEO?" → Answer: "John Smith"
  → Sub-Q2: "Where did John Smith go to school?" → Answer: "MIT"
  → Sub-Q3: "What is MIT's revenue?" → Answer: "$19.5B"
```
Each hop depends on the previous answer. Must execute sequentially.

### Pattern 2: Parallel Fan-Out
```
Q: "Compare AWS and Azure pricing for GPU instances"
  → Sub-Q1: "AWS GPU instance pricing" (independent)
  → Sub-Q2: "Azure GPU instance pricing" (independent)
  → Synthesis: Compare results
```
Sub-questions are independent. Execute in parallel for speed.

### Pattern 3: Bridge Entity
```
Q: "Did the author of 'Attention Is All You Need' work at the company that acquired DeepMind?"
  → Sub-Q1: "Who authored Attention Is All You Need?" → "Vaswani et al. at Google"
  → Sub-Q2: "Who acquired DeepMind?" → "Google"
  → Bridge: Same entity (Google) → Answer: "Yes"
```

### Pattern 4: Temporal Chain
```
Q: "What happened to the stock price after the CEO was replaced?"
  → Sub-Q1: "When was the CEO replaced?" → "March 2024"
  → Sub-Q2: "Stock price movement after March 2024" → retrieve time-series data
```

### When to Use Multi-Hop

Indicators that multi-hop is needed:
- Comparative questions ("compare X and Y")
- Questions with relative references ("the company that...")
- Questions requiring inference across facts
- Questions spanning time periods
- Questions with implicit entities

---

## 4. Query Planning and Decomposition

### Decision: To Decompose or Not?

```
Simple (no decomposition):
  - "What is the return policy?"
  - "How do I reset my password?"
  - Single entity, single fact, direct lookup

Complex (decompose):
  - "How does our Q3 revenue compare to competitors in the same region?"
  - "What are the security implications of migrating from Kafka to Pulsar?"
  - Multiple entities, multiple facts, reasoning required
```

### Decomposition Strategy

1. **Identify entities and relations** in the query
2. **Determine information needs** — what facts are required?
3. **Build dependency DAG** — which facts depend on others?
4. **Assign execution order** — topological sort of the DAG
5. **Identify parallelizable groups** — independent sub-questions in same tier

### Example Decomposition

Query: "What security certifications does our payment processor have, and are they sufficient for our expansion into the EU?"

```
Sub-Q1: "Who is our payment processor?" [lookup, tier 0]
Sub-Q2: "What security certifications does [Sub-Q1.answer] have?" [depends on Q1, tier 1]
Sub-Q3: "What security certifications are required for payment processing in the EU?" [independent, tier 0]
Sub-Q4: "Does [Sub-Q2.answer] satisfy [Sub-Q3.answer]?" [depends on Q2, Q3, tier 2]
```

Execution plan:
- Tier 0 (parallel): Sub-Q1, Sub-Q3
- Tier 1 (after Q1): Sub-Q2
- Tier 2 (after Q2, Q3): Sub-Q4 (synthesis, may not need retrieval)

---

## 5. Iterative Retrieval: When to Stop

The agent must decide after each retrieval whether it has enough evidence. This is the **sufficiency loop**:

```
while iterations < MAX_ITERATIONS:
    evidence = retrieve(current_query, current_source)
    sufficiency = evaluate_sufficiency(evidence, original_question)
    
    if sufficiency.score >= THRESHOLD:
        break
    
    if sufficiency.diagnosis == "wrong_source":
        switch source
    elif sufficiency.diagnosis == "too_broad":
        narrow query with filters
    elif sufficiency.diagnosis == "too_narrow":
        broaden query, remove constraints
    elif sufficiency.diagnosis == "missing_entity":
        add entity-specific query
    elif sufficiency.diagnosis == "partial":
        formulate follow-up for missing aspects
    
    iterations += 1
```

### Stopping Criteria

1. **Sufficiency threshold met** — evidence covers all aspects of the question
2. **Max iterations reached** — hard cap (typically 3-5) to prevent infinite loops
3. **Diminishing returns** — new retrieval adds <5% new information
4. **Source exhaustion** — all available sources have been queried
5. **Contradiction detected** — conflicting evidence requires human judgment

---

## 6. Tool-Augmented Retrieval

Agentic RAG selects the right tool for each sub-question:

| Tool | Best For | Example |
|---|---|---|
| Vector Search | Semantic similarity, concepts, fuzzy matching | "How does our caching strategy work?" |
| SQL/Structured | Exact facts, aggregations, filters | "Total revenue in Q3 2024" |
| Knowledge Graph | Entity relationships, multi-hop paths | "Who reports to the VP of Engineering?" |
| API Call | Real-time data, external services | "Current stock price of AAPL" |
| Web Search | Recent events, public knowledge | "Latest CVE for Log4j" |
| Document Store | Specific document lookup by ID/title | "Section 4.2 of the SLA" |

### Tool Selection Logic

```python
def select_tool(sub_question, available_tools):
    """
    Signals for tool selection:
    1. Presence of aggregation keywords (sum, count, average) → SQL
    2. Entity-relationship patterns (who manages, reports to) → Graph
    3. Exact ID/title reference → Document Store
    4. Real-time/current/latest → API or Web Search
    5. Conceptual/how/why → Vector Search
    6. Comparison across structured fields → SQL
    """
```

### Multi-Tool Fusion

For complex questions, multiple tools may be needed:
```
Q: "How does our error rate compare to the SLA threshold?"
  → SQL: query metrics table for current error rate
  → Vector/Doc: retrieve SLA document for threshold definition
  → Synthesis: compare the two values
```

---

## 7. Source Authority Ranking

Not all sources are equal. The agent maintains a source authority model:

### Authority Factors

| Factor | Description | Weight |
|---|---|---|
| Recency | When was the source last updated? | 0.20 |
| Provenance | Official docs > blog posts > forums | 0.25 |
| Author expertise | Domain expert vs. general contributor | 0.15 |
| Verification status | Reviewed/approved vs. draft | 0.20 |
| Citation count | How often is this source referenced? | 0.10 |
| Consistency | Does it agree with other authoritative sources? | 0.10 |

### Authority Hierarchy (Example: Enterprise Knowledge Base)

```
Tier 1 (Authoritative):
  - Official product documentation
  - Approved policies and SOPs
  - Legal/compliance documents
  - Signed contracts and SLAs

Tier 2 (Reliable):
  - Engineering design documents
  - Meeting notes from decision meetings
  - Internal wiki (reviewed sections)

Tier 3 (Informational):
  - Slack threads
  - Internal blog posts
  - Draft documents
  - Personal notes

Tier 4 (External):
  - Third-party documentation
  - Stack Overflow answers
  - Blog posts
```

### Conflict Resolution

When sources conflict:
1. Higher authority source wins
2. More recent source wins (if same authority)
3. If truly ambiguous → present both perspectives with sources
4. If high-risk → escalate to human

---

## 8. Evidence Sufficiency Scoring

After retrieval, the agent evaluates whether it has enough evidence to answer:

### Sufficiency Dimensions

1. **Coverage** — Does the evidence address all aspects of the question?
   - Extract required information facets from the question
   - Check which facets are covered by retrieved evidence
   - Score = covered_facets / total_facets

2. **Relevance** — Is the evidence actually about the question topic?
   - Semantic similarity between question and evidence
   - Entity overlap between question and evidence

3. **Specificity** — Is the evidence specific enough (not too general)?
   - Evidence mentions specific entities from the question
   - Evidence provides concrete facts, not vague statements

4. **Recency** — Is the evidence fresh enough for this question?
   - Time-sensitive questions need recent evidence
   - Stable facts (physics, math) don't need recency

5. **Consensus** — Do multiple sources agree?
   - Multiple sources confirming same fact = higher sufficiency
   - Single source for critical claim = lower sufficiency

### Scoring Formula

```
sufficiency = (
    0.35 * coverage +
    0.25 * relevance +
    0.20 * specificity +
    0.10 * recency +
    0.10 * consensus
)

if sufficiency >= 0.75: SUFFICIENT
elif sufficiency >= 0.50: PARTIAL (may proceed with caveats)
else: INSUFFICIENT (re-retrieve or abstain)
```

---

## 9. Claim-Level Verification

After generating an answer, every claim is individually verified:

### Process

1. **Decompose answer into claims** — Split the generated answer into atomic factual statements
2. **For each claim, find supporting evidence** — Match claim to retrieved chunks
3. **Score support level**:
   - SUPPORTED: Evidence directly states or strongly implies the claim
   - PARTIALLY_SUPPORTED: Evidence is related but doesn't fully confirm
   - NOT_SUPPORTED: No evidence found for this claim
   - CONTRADICTED: Evidence contradicts the claim

### Actions Based on Verification

| Verification Result | Action |
|---|---|
| All claims SUPPORTED | Proceed with high confidence |
| Some PARTIALLY_SUPPORTED | Add caveats to those claims |
| Any NOT_SUPPORTED | Remove claim or mark as "unverified" |
| Any CONTRADICTED | Remove claim, flag for review |

### Example

```
Generated answer: "Our SLA guarantees 99.99% uptime with a 15-minute response time for P1 incidents."

Claim 1: "SLA guarantees 99.99% uptime"
  → Evidence: SLA doc states "99.9% availability" → CONTRADICTED
  → Action: Correct to 99.9%

Claim 2: "15-minute response time for P1 incidents"
  → Evidence: SLA doc states "P1: 15 min response, 1 hour resolution" → SUPPORTED
  → Action: Keep as-is
```

---

## 10. Answer Abstention: When and How

### When to Abstain

1. **Insufficient evidence** — Retrieved documents don't contain the answer
2. **Contradictory evidence** — Sources disagree and we can't resolve
3. **Out of scope** — Question is outside the knowledge domain
4. **Stale information** — Only old evidence available for time-sensitive question
5. **High risk + low confidence** — Stakes are too high for uncertain answers
6. **Ambiguous question** — Multiple valid interpretations, can't determine which

### How to Abstain (Gracefully)

Bad abstention: "I don't know."

Good abstention:
```
"I don't have sufficient information to answer this question accurately.

What I found:
- [Partial relevant information if any]

What's missing:
- [Specific information gap]

Suggestions:
- [Who/where to ask instead]
- [How to reformulate for better results]
"
```

### Abstention vs. Clarification vs. Escalation

```
if question_is_ambiguous:
    → ASK CLARIFICATION (we might be able to answer with more info)
elif evidence_insufficient AND risk_is_low:
    → ABSTAIN (gracefully decline)
elif evidence_insufficient AND risk_is_high:
    → ESCALATE TO HUMAN (too risky to guess)
elif evidence_contradictory:
    → PRESENT BOTH SIDES + ESCALATE
```

---

## 11. Human Escalation Triggers

### Automatic Escalation Conditions

| Trigger | Condition | Rationale |
|---|---|---|
| Risk threshold | risk=critical AND confidence<0.90 | Can't afford to be wrong |
| Legal/compliance | Topic involves legal, regulatory, HR | Requires human judgment |
| Financial impact | Answer could affect >$X decisions | Need human sign-off |
| Contradiction | Authoritative sources contradict each other | Need human to resolve |
| Policy gap | No policy exists for this scenario | Need human to decide |
| Repeated failure | 3+ retrieval iterations, still insufficient | Sources may not contain answer |
| User frustration | User rephrases same question 3+ times | System isn't helping |

### Escalation Payload

When escalating, provide the human with:
1. Original question
2. What was attempted (queries, sources)
3. What was found (partial evidence)
4. Why escalation was triggered
5. Suggested next steps
6. Priority/urgency assessment

---

## 12. Memory-Aware Retrieval

The agent uses conversation history and user context to improve retrieval:

### Short-Term Memory (Conversation)
- Resolve coreferences: "What about their pricing?" → "What about [Company X mentioned 2 turns ago]'s pricing?"
- Maintain context: Follow-up questions inherit context from previous answers
- Track what's already been retrieved (don't re-fetch same docs)

### Long-Term Memory (User Profile)
- User's role/department → affects which sources are relevant
- Previous questions → anticipate follow-ups
- Preferred detail level → adjust answer depth
- Access permissions → filter sources by authorization

### Memory-Enhanced Query Reformulation

```
Original query: "How much did it grow?"
Conversation context: Previous Q was about Q3 revenue

Reformulated: "How much did Q3 revenue grow compared to Q2?"
Additional context: User is in Finance → include financial metrics sources
```

---

## 13. Confidence-Driven Behavior Matrix

The confidence score maps to specific behaviors:

| Confidence | Risk: Low | Risk: Medium | Risk: High | Risk: Critical |
|---|---|---|---|---|
| ≥ 0.90 | Answer | Answer | Answer | Answer + caveat |
| 0.80-0.90 | Answer | Answer + caveat | Answer + caveat | Escalate |
| 0.65-0.80 | Answer + caveat | Clarify | Escalate | Escalate |
| 0.50-0.65 | Clarify | Clarify | Escalate | Escalate |
| 0.35-0.50 | Abstain | Escalate | Escalate | Escalate |
| < 0.35 | Abstain | Abstain | Escalate | Escalate |

### Confidence Signals (Summary)

1. **Retrieval quality** — Top-K similarity scores
2. **Reranker agreement** — Cross-encoder confirms relevance
3. **Source authority** — How trustworthy are the sources?
4. **Freshness** — How recent is the evidence?
5. **Coverage** — Does evidence cover all question facets?
6. **Groundedness** — Is every generated claim backed by evidence?
7. **Consistency** — Do multiple generations agree?
8. **Citation density** — What fraction of the answer has citations?

### Calibration

Confidence scores must be **calibrated**: when the system says 80% confidence, it should be correct ~80% of the time. Calibration requires:
- Evaluation dataset with ground truth
- Plotting predicted confidence vs. actual accuracy
- Applying temperature scaling or isotonic regression to calibrate
- Regular recalibration as the system evolves

---

## Summary: Why Agentic RAG Matters

Traditional RAG fails silently — it retrieves irrelevant content and hallucinates an answer with no indication of uncertainty. Agentic RAG makes the system **trustworthy** by:

1. Planning before acting (right tool, right source)
2. Iterating until evidence is sufficient (not just top-K and hope)
3. Verifying every claim (no ungrounded statements)
4. Knowing its limits (abstaining when uncertain)
5. Escalating appropriately (humans in the loop for high stakes)

This transforms RAG from a "fancy search + generation" trick into a **reliable knowledge system** suitable for production enterprise use.
