# Agentic RAG: Real-World Examples

## Case Study 1: Financial Compliance at Northern Trust

### Background

Northern Trust's compliance team handles 2,000+ queries per month from portfolio managers asking questions like: "Can we hold more than 5% of a Brazilian bank's equity given our current ESG mandate and the new SEC 2024 disclosure rules?"

This requires multi-hop retrieval across:
- Internal investment policy documents (400+ pages)
- SEC regulations (Title 17 CFR)
- ESG framework commitments (UN PRI, TCFD)
- Historical compliance decisions (precedent database)
- Current portfolio positions (live data)

### Architecture

```
Query: "Can Fund X increase BVMF:ITUB4 position to 6%?"

Step 1 - Policy Retrieval:
  → Retrieve Fund X's investment mandate
  → Found: "Emerging market single-name equity cap: 5% NAV"
  → Found: "Exception process requires CIO + compliance sign-off"

Step 2 - Regulatory Retrieval:
  → SEC Rule 35d-1 (Names Rule) implications
  → Brazilian CVM regulations on foreign ownership
  → Found: "No regulatory prohibition at 6% for this entity class"

Step 3 - ESG Cross-Reference:
  → ITUB4 ESG rating: BBB (MSCI), Medium Risk (Sustainalytics)
  → Fund X ESG mandate: "Minimum BBB or equivalent"
  → Found: "ESG criteria satisfied"

Step 4 - Precedent Search:
  → Similar exception requests in past 24 months
  → Found: 3 cases where 5% cap was exceeded with CIO approval
  → Found: Average approval time was 3 business days

Step 5 - Synthesis:
  → "Position increase to 6% exceeds Fund X's 5% single-name EM cap.
     No regulatory or ESG barrier exists. Exception process required.
     Based on 3 similar precedents, approval likelihood is high with
     CIO sign-off. Estimated timeline: 3 business days."
```

### Key Design Decisions

**Why agentic over simple RAG:** A single retrieval pass returned the 5% cap rule but missed that exceptions existed. The agent's second hop—triggered by finding a restriction—searched for exception procedures and precedents.

**Retrieval strategy:** Each hop uses a different index:
- Hop 1: Dense retrieval over policy docs (e5-large embeddings)
- Hop 2: Hybrid search over regulations (BM25 + dense, legal-specific tokenizer)
- Hop 3: Structured query over ESG database (SQL)
- Hop 4: Semantic search over precedent summaries
- Hop 5: LLM synthesis with all retrieved context

**Production metrics (6-month average):**
| Metric | Simple RAG | Agentic RAG |
|--------|-----------|-------------|
| Answer completeness | 41% | 87% |
| Regulatory accuracy | 73% | 96% |
| Average hops needed | 1 | 3.2 |
| Latency (p50) | 2.1s | 8.4s |
| Latency (p95) | 4.2s | 18.7s |
| Cost per query | $0.03 | $0.14 |

**Compliance team feedback:** "Before this system, answering a complex compliance question took 2-4 hours of analyst time. Now it takes 30 seconds for the system plus 5 minutes for human verification."

---

## Case Study 2: E-Commerce Product Research at Wirecutter/NYT

### Background

The New York Times' Wirecutter team built an internal research assistant that helps product reviewers gather competitive intelligence. A reviewer might ask: "What are the top 5 robot vacuums under $500 that handle pet hair well, and how have their prices changed in the past 6 months?"

### Iterative Retrieval Flow

```
Query: "Best robot vacuums under $500 for pet hair, with price history"

Iteration 1 - Product Discovery:
  Tools used: [product_database_search, review_corpus_search]
  → Searched product DB: category="robot vacuum", price<500, feature="pet hair"
  → Retrieved 23 candidates
  → Searched review corpus for "pet hair" performance mentions
  → Narrowed to 8 products with strong pet hair mentions

Iteration 2 - Deep Review Analysis:
  Tools used: [review_corpus_search, expert_test_results]
  → For each of 8 candidates, retrieved:
    - Professional review excerpts (Wirecutter, RTINGS, Consumer Reports)
    - User review sentiment analysis (Amazon, Best Buy)
    - Lab test results (suction power, hair tangle rate)
  → Ranked by composite score
  → Top 5 identified: Roborock Q7+, iRobot j7+, Ecovacs X1 Omni,
    Shark AI Ultra, Roborock S7 MaxV

Iteration 3 - Price History:
  Tools used: [price_tracker_api, deal_history_search]
  → Queried Keepa/CamelCamelCamel APIs for 6-month price data
  → Found: Roborock Q7+ dropped from $429 to $349 (18% decline)
  → Found: iRobot j7+ stable at $499, brief sale to $399 on Prime Day
  → Found: Ecovacs X1 Omni frequently discounted (list $549, street $449)

Iteration 4 - Competitive Comparison:
  Tools used: [spec_comparison_tool, feature_matrix_builder]
  → Built feature comparison matrix
  → Identified key differentiators
  → Generated price-to-performance ratio

Final Output: Structured comparison with confidence levels per claim
```

### What Made This Agentic

The naive RAG approach retrieved review documents and returned a generic answer. The agentic system:

1. **Recognized the query had multiple facets** — product discovery, quality assessment, and price analysis each required different tools
2. **Iteratively refined** — Started with 23 products, narrowed to 8 based on pet hair relevance, then ranked to top 5
3. **Combined structured and unstructured data** — Product databases (structured) + reviews (unstructured) + price APIs (structured)
4. **Applied temporal reasoning** — "Past 6 months" triggered the price history tool rather than just current prices

### Production Lessons

- **Tool selection accuracy:** 94% of the time, the agent chose the right tool on the first try. The 6% failures were mostly when queries blended categories (e.g., "which vacuum is best for apartments" — apartment size info needed a different tool than vacuum performance)
- **Iteration budget:** Capped at 5 iterations. Average was 3.1. Queries exceeding 4 iterations were usually ambiguous and needed human clarification
- **Cost per research query:** $0.41 average (mostly GPT-4 tokens for synthesis across many documents)

---

## Query Decomposition in Production

### Real Examples from a Legal Research Platform (Casetext/Thomson Reuters)

**Original query:** "Has the interpretation of 'reasonable expectation of privacy' in Fourth Amendment cases changed after the Carpenter v. United States decision, particularly regarding cell-site location data and other digital surveillance methods?"

**Decomposition:**

```json
{
  "sub_queries": [
    {
      "id": "sq1",
      "query": "Fourth Amendment 'reasonable expectation of privacy' doctrine pre-Carpenter",
      "purpose": "Establish baseline interpretation (Katz test)",
      "index": "case_law",
      "filters": {"date_range": "1967-2018", "courts": ["SCOTUS", "Circuit"]}
    },
    {
      "id": "sq2",
      "query": "Carpenter v. United States 585 U.S. 296 holding and reasoning",
      "purpose": "Core ruling on CSLI and third-party doctrine",
      "index": "case_law",
      "filters": {"citation": "585 U.S. 296"}
    },
    {
      "id": "sq3",
      "query": "Post-Carpenter decisions on cell-site location information privacy",
      "purpose": "How lower courts applied Carpenter to CSLI",
      "index": "case_law",
      "filters": {"date_range": "2018-2024", "cites": "585 U.S. 296"}
    },
    {
      "id": "sq4",
      "query": "Post-Carpenter digital surveillance reasonable expectation of privacy",
      "purpose": "Extension to non-CSLI digital surveillance",
      "index": "case_law",
      "filters": {"date_range": "2018-2024", "topics": ["geofence", "email", "smart_device"]}
    },
    {
      "id": "sq5",
      "query": "Legal scholarship on Carpenter's impact on Fourth Amendment digital age",
      "purpose": "Academic analysis of doctrinal shift",
      "index": "law_review",
      "filters": {"date_range": "2018-2024"}
    }
  ],
  "synthesis_strategy": "chronological_doctrinal_evolution",
  "dependencies": ["sq1 → sq2 → sq3,sq4", "sq5 independent"]
}
```

**Why decomposition was essential:** A single retrieval for the original query returned a mix of pre- and post-Carpenter cases without clear temporal delineation. The decomposed approach allowed the system to trace the doctrinal evolution chronologically.

### Another Example: Technical Support (Datadog)

**Original query:** "Our Kubernetes pods are getting OOMKilled but the container memory limits are set to 4Gi and our app only uses 2Gi according to Prometheus — what's going on?"

**Decomposition:**

```json
{
  "sub_queries": [
    {
      "id": "sq1",
      "query": "Kubernetes OOMKilled causes when reported memory is below limit",
      "index": "knowledge_base"
    },
    {
      "id": "sq2",
      "query": "Container memory accounting differences kernel RSS vs application heap",
      "index": "knowledge_base"
    },
    {
      "id": "sq3",
      "query": "Prometheus container_memory_working_set_bytes vs container_memory_rss",
      "index": "documentation"
    },
    {
      "id": "sq4",
      "query": "Known issues memory reporting JVM Go runtime in containers",
      "index": "incident_history"
    }
  ],
  "execution": "parallel_then_merge"
}
```

**Result:** The system identified that the application was a JVM service where off-heap memory (Netty direct buffers, JIT codecache) wasn't captured by the Prometheus JVM metrics but counted against the container's cgroup limit.

---

## Confidence Scoring War Story: The Goldman Sachs Incident

### What Happened

A financial research assistant at a major investment bank (anonymized, commonly attributed to Goldman Sachs's internal tooling) reported 92% confidence on the following answer:

**Query:** "What was Stripe's revenue in 2022?"

**System answer (92% confidence):** "$14.3 billion"

**Actual answer:** Stripe's 2022 revenue was approximately $14.3 billion — but this was Stripe's *gross payment volume processing*, not *revenue*. Actual net revenue was approximately $3.7 billion.

### Why Confidence Was Miscalibrated

The system's confidence score was based on:
- **Retrieval relevance:** Multiple sources mentioned "$14.3 billion" and "Stripe" and "2022" — high cosine similarity ✓
- **Source agreement:** 4 out of 5 retrieved documents agreed on this number ✓
- **Answer extraction clarity:** The number was clearly stated, not inferred ✓

What it missed:
- **Semantic distinction:** "Revenue" vs "gross payment volume" — the retrieved docs used both terms in proximity to the same number
- **Source quality:** 3 of 4 agreeing sources were blog posts that made the same error; only 1 was a primary source (Stripe's actual disclosure)
- **Domain knowledge:** In fintech, revenue ≠ transaction volume — a critical domain distinction

### How Calibration Fixed It

**Step 1 — Calibration dataset:** Created 500 finance questions with known ground truth, ran the system, compared stated confidence to actual accuracy.

**Step 2 — Found the miscalibration:**
```
Stated confidence 90-95%: Actual accuracy was only 71%
Stated confidence 80-89%: Actual accuracy was 74%
Stated confidence 60-79%: Actual accuracy was 68%
```

The system was systematically overconfident by ~20 percentage points.

**Step 3 — Multi-factor confidence model:**

```python
def compute_calibrated_confidence(retrieval_results):
    factors = {
        "source_agreement": agreement_score(retrieval_results),        # 0-1
        "source_authority": authority_score(retrieval_results),         # 0-1
        "semantic_precision": semantic_match_score(query, answer),      # 0-1
        "temporal_freshness": freshness_score(retrieval_results),       # 0-1
        "claim_type": claim_complexity_penalty(answer),                 # 0.7-1.0
        "domain_ambiguity": domain_ambiguity_score(query),             # 0-1
    }
    
    # Learned weights from calibration dataset
    raw_score = weighted_combination(factors, learned_weights)
    
    # Platt scaling from calibration
    calibrated = platt_scale(raw_score, platt_params)
    
    return calibrated
```

**Step 4 — Post-calibration results:**
```
Stated confidence 90-95%: Actual accuracy 89% (was 71%)
Stated confidence 80-89%: Actual accuracy 81% (was 74%)
Stated confidence 60-79%: Actual accuracy 67% (was 68%)
```

**Key insight:** The biggest improvement came from the `source_authority` factor. When the system learned to distinguish between primary sources (SEC filings, company disclosures) and secondary sources (blog posts, news articles), overconfidence on financial figures dropped by 60%.

---

## Abstention in Practice: Ada Health's Medical AI

### The System

Ada Health's symptom assessment AI handles 12 million assessments per year. Their RAG system assists clinicians with differential diagnosis queries. The system abstains (refuses to provide a definitive answer) on approximately 12% of queries.

### Abstention Categories and Examples

**Category 1: Insufficient information (5.2% of queries)**
```
Query: "Patient has intermittent chest pain"
System: "ABSTAINING — Insufficient clinical context. I need to know:
  - Pain character (sharp/dull/crushing/burning)
  - Duration and frequency
  - Aggravating/relieving factors
  - Associated symptoms
  - Patient age and risk factors
  [Suggested follow-up questions provided]"
```

**Category 2: Conflicting evidence (3.1% of queries)**
```
Query: "Should a 45-year-old male with mildly elevated PSA (4.2) 
        get a prostate biopsy?"
System: "ABSTAINING — Clinical guidelines conflict on this scenario.
  - USPSTF: Shared decision-making, no universal recommendation
  - AUA: Consider biopsy if PSA >4.0 with risk factors
  - EAU: MRI first, biopsy only if PI-RADS ≥3
  ESCALATING to physician with full guideline comparison attached.
  Confidence in any single recommendation: 34%"
```

**Category 3: Outside training scope (2.4% of queries)**
```
Query: "Can my patient take kratom with their SSRI?"
System: "ABSTAINING — Kratom-drug interactions are insufficiently 
  studied. My knowledge base contains no peer-reviewed interaction 
  data for this combination. ESCALATING to pharmacist.
  Note: Anecdotal reports suggest serotonergic risk but 
  evidence quality is very low."
```

**Category 4: High-stakes with low confidence (1.3% of queries)**
```
Query: "Is this mole concerning?" [with image]
System: "ABSTAINING — While the lesion shows asymmetry and color 
  variation suggestive of ABCDE criteria, my confidence in 
  distinguishing dysplastic nevus from early melanoma in this 
  image quality is 58%. This is below the 85% threshold for 
  dermatologic assessment. REFERRING to dermatology."
```

### UX Design Around Abstention

Ada's UX research found that **users trust a system more when it occasionally says "I don't know"** — trust scores increased 23% after implementing abstention compared to always providing an answer.

**Design principles:**
1. **Never just say "I don't know"** — always explain *why* and suggest a next step
2. **Provide partial information** when possible — "I can't give a diagnosis, but here are the 3 most relevant differentials to discuss with your physician"
3. **Quantify the gap** — "I need 2 more data points to reach 85% confidence"
4. **Route to the right human** — not generic escalation, but specific specialty routing

### Abstention Threshold Tuning

```
Threshold too low (abstain at <50% confidence):
  → Abstains on 31% of queries → users stop using the system
  
Threshold too high (abstain at <95% confidence):
  → Abstains on 3% of queries → misses risky edge cases
  
Optimal threshold (domain-specific):
  → Diagnosis queries: abstain below 85%
  → Drug interaction queries: abstain below 90%
  → General health info: abstain below 60%
  → Result: 12% overall abstention rate
```

---

## Tool-Augmented Retrieval: Sourcegraph's Code Intelligence

### System Architecture

Sourcegraph Cody combines multiple retrieval tools to answer developer questions:

```
Query: "How does the authentication middleware handle expired JWT tokens 
        in our API gateway? I'm seeing 401s but the token refresh should 
        be working."

Tool 1 — Code Search (Zoekt):
  Search: "JWT expired token middleware" in repo:api-gateway
  Found: src/middleware/auth.ts:47-89 — JWT validation logic
  Found: src/middleware/refresh.ts:12-45 — Token refresh handler

Tool 2 — Documentation Search:
  Search: "JWT refresh flow" in docs/
  Found: docs/auth/token-lifecycle.md — describes expected refresh behavior
  Found: docs/auth/troubleshooting.md — known issues section

Tool 3 — Stack Overflow/Internal Q&A:
  Search: "JWT 401 token refresh race condition"
  Found: Internal Q&A #4521 — "Race condition when token expires during 
         in-flight request" (answered 2 months ago, marked as resolved)

Tool 4 — GitHub Issues:
  Search: "401 token refresh" in repo:api-gateway
  Found: Issue #892 — "Intermittent 401s under load" (closed, fix merged)
  Found: Issue #1034 — "Token refresh not triggered for parallel requests" (open)

Tool 5 — Git History:
  Search: Recent changes to src/middleware/auth.ts
  Found: Commit abc123 (3 days ago) — "Reduce token expiry buffer from 
         60s to 5s for performance" — THIS IS LIKELY THE CAUSE

Synthesis:
  "The 401s are likely caused by commit abc123 (3 days ago) which reduced 
   the token expiry buffer from 60s to 5s. The refresh logic in 
   refresh.ts:23 triggers when remaining_ttl < buffer. With a 5s buffer,
   tokens can expire between the check and the actual API call under any
   network latency >5s. This matches open issue #1034. 
   
   Recommended fix: Restore buffer to 30s or implement optimistic refresh
   as described in docs/auth/token-lifecycle.md#preemptive-refresh."
```

### Why Each Tool Matters

| Tool | What it uniquely provides | Miss rate without it |
|------|--------------------------|---------------------|
| Code search | Exact implementation details | Can't verify behavior |
| Doc search | Intended design/architecture | Misses context for why code exists |
| Internal Q&A | Tribal knowledge, past incidents | Rediscovers known issues |
| GitHub issues | Active bugs, recent regressions | Misses known problems |
| Git history | Recent changes (causal) | Misses root cause of regressions |

### Tool Selection Model

The system uses a lightweight classifier to decide which tools to invoke:

```
Query type → Tool selection:
  "How does X work?" → Code search + Docs (always)
  "Why is X broken?" → Code search + Git history + Issues (always)
  "How do I do X?" → Docs + Q&A + Code examples
  "Has anyone solved X?" → Q&A + Issues + Stack Overflow
```

Average tools invoked per query: 2.7
Average total latency: 4.2 seconds (tools run in parallel where possible)

---

## Multi-Hop Retrieval Benchmark: Sequential vs Parallel

### Benchmark Setup (HotpotQA + Custom Enterprise Dataset)

Tested on 1,000 multi-hop questions requiring 2-4 retrieval steps. Compared three strategies:

**Strategy A — Sequential decomposition:** Each sub-query depends on previous results
**Strategy B — Parallel decomposition:** All sub-queries issued simultaneously, then merged
**Strategy C — Adaptive:** Start parallel, switch to sequential if initial results require refinement

### Results

| Metric | Sequential | Parallel | Adaptive |
|--------|-----------|----------|----------|
| Accuracy (2-hop questions) | 78% | 74% | 79% |
| Accuracy (3-hop questions) | 71% | 58% | 73% |
| Accuracy (4-hop questions) | 64% | 42% | 67% |
| Median latency (2-hop) | 4.2s | 1.8s | 2.4s |
| Median latency (3-hop) | 6.8s | 2.1s | 4.1s |
| Median latency (4-hop) | 9.1s | 2.3s | 5.8s |
| Cost per query (tokens) | 4,200 | 3,100 | 3,800 |

### Key Findings

1. **Parallel wins on speed but loses on accuracy for 3+ hops** — because later sub-queries often depend on what earlier ones find. Example: "Who is the CEO of the company that acquired the maker of the drug used to treat the condition described in paper X?" — you can't query for the CEO until you know the company.

2. **Sequential is most accurate but slowest** — each hop refines the next query based on actual retrieved content.

3. **Adaptive is the production sweet spot** — issues initial parallel queries, then selectively does sequential follow-ups only where results indicate dependency. Captures 85% of sequential's accuracy at 60% of the latency.

### When Parallel Wins

Parallel decomposition excels when sub-queries are genuinely independent:
- "Compare the revenue, employee count, and founding date of Stripe and Square" → 6 independent lookups
- "What are the side effects, dosage, and contraindications of ibuprofen?" → 3 independent lookups

### When Sequential Wins

Sequential is necessary for inferential chains:
- "What university did the architect of the Sydney Opera House attend?" → Must identify Jorn Utzon first, then query his education
- "What programming language was the Linux kernel originally written in, and who created that language?" → Must establish C first, then query Dennis Ritchie

---

## Source Authority Ranking: Kirkland & Ellis Implementation

### Background

Kirkland & Ellis (largest US law firm by revenue) implemented source authority ranking for their litigation research RAG system. Different source types carry different weight in legal argumentation.

### Authority Hierarchy

```
Tier 1 — Binding Authority (weight: 1.0):
  - Supreme Court decisions (for constitutional questions)
  - Circuit court decisions (for the relevant circuit)
  - Controlling statutes and regulations
  
Tier 2 — Persuasive Authority (weight: 0.7):
  - Other circuit court decisions
  - District court decisions with strong reasoning
  - Restatements of Law
  
Tier 3 — Secondary Authority (weight: 0.4):
  - Law review articles
  - Treatises (Williston, Corbin, Wright & Miller)
  - Practice guides
  
Tier 4 — Informal Authority (weight: 0.15):
  - Legal blogs (SCOTUSblog, Volokh Conspiracy)
  - CLE materials
  - Bar association publications
  
Tier 5 — Background (weight: 0.05):
  - News articles about legal topics
  - Wikipedia legal content
  - Forum discussions
```

### Implementation Details

```python
def rank_sources(retrieved_docs, query_jurisdiction, query_topic):
    scored_results = []
    for doc in retrieved_docs:
        base_relevance = doc.similarity_score  # 0-1 from embedding search
        
        # Authority weight
        authority = get_authority_tier(doc, query_jurisdiction)
        
        # Recency bonus (for evolving areas of law)
        recency = recency_score(doc.date, query_topic)
        
        # Subsequent treatment (has this case been overruled?)
        treatment = shepardize(doc) if doc.type == "case_law" else 1.0
        
        # Final score
        final = base_relevance * authority * recency * treatment
        scored_results.append((doc, final))
    
    return sorted(scored_results, key=lambda x: x[1], reverse=True)
```

### Real Example

**Query:** "Can an employer enforce a non-compete clause against a remote worker who moved to California?"

**Retrieved results (pre-authority ranking):**
1. Blog post about remote work and non-competes (similarity: 0.94)
2. California Business & Professions Code §16600 (similarity: 0.87)
3. Edwards v. Arthur Andersen LLP (Cal. 2008) (similarity: 0.85)
4. A Reddit r/legaladvice thread (similarity: 0.91)
5. Restatement of Employment Law §8.06 (similarity: 0.82)

**After authority ranking:**
1. California B&P Code §16600 — binding statute (0.87 × 1.0 = 0.87)
2. Edwards v. Arthur Andersen — binding Cal. Supreme Court (0.85 × 1.0 = 0.85)
3. Restatement of Employment Law — secondary authority (0.82 × 0.4 = 0.33)
4. Blog post (0.94 × 0.15 = 0.14)
5. Reddit thread (0.91 × 0.05 = 0.046)

**Impact:** Without authority ranking, the system would cite a blog post first. With ranking, it correctly leads with the controlling statute and case law.

---

## Human Escalation: Intercom's Support AI

### System Overview

Intercom's Fin AI agent handles first-line customer support. It resolves 67% of queries autonomously. Of the remaining 33%, it routes 8% to human agents with full context (the other 25% are resolved after asking the customer a clarifying question).

### Escalation Triggers

```python
ESCALATION_RULES = {
    # Confidence-based
    "low_confidence": {
        "threshold": 0.6,
        "description": "System confidence below threshold after max retrieval attempts"
    },
    
    # Sentiment-based
    "customer_frustration": {
        "signals": ["repeat contact within 24h", "negative sentiment score > 0.8",
                   "explicit escalation request", "profanity detected"],
        "description": "Customer showing signs of frustration"
    },
    
    # Policy-based
    "high_value_customer": {
        "criteria": "ARR > $50k or enterprise tier",
        "description": "Always offer human option for high-value accounts"
    },
    
    # Complexity-based
    "multi_system_issue": {
        "signals": ["involves billing + technical", "requires account modification",
                   "legal/compliance topic"],
        "description": "Issue spans multiple domains requiring human judgment"
    },
    
    # Loop detection
    "stuck_loop": {
        "criteria": "3+ back-and-forth without resolution progress",
        "description": "Conversation not converging on solution"
    }
}
```

### Context Handoff Format

When escalating, the AI provides the human agent with:

```
━━━ ESCALATION SUMMARY ━━━
Customer: Acme Corp (Enterprise, ARR $120k)
Issue: Cannot access SSO after domain migration
Escalation reason: Multi-system issue (SSO config + DNS + billing)

Conversation summary:
- Customer migrated from acme.com to acmecorp.io 3 days ago
- SSO login failing with SAML assertion error
- AI verified: DNS records propagated correctly
- AI verified: SAML metadata URL returns valid XML
- AI found: IdP entity ID still references old domain

Attempted solutions:
1. ✗ Suggested updating SAML config — customer lacks admin access
2. ✗ Suggested contacting IdP admin — IdP admin is on leave

Likely next step: Manual SAML entity ID update by our support 
  engineering team (requires backend access)

Relevant documentation: [3 links pre-loaded]
━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Metrics

| Metric | Before AI (all human) | After AI with escalation |
|--------|----------------------|--------------------------|
| Median first response time | 4.2 minutes | 12 seconds (AI) / 3.1 min (escalated) |
| Resolution rate | 82% | 91% |
| Customer satisfaction (CSAT) | 4.1/5 | 4.4/5 |
| Cost per conversation | $12.40 | $3.80 |
| Human agent utilization | 100% | 41% |

**Key insight:** Human agents handle fewer but harder cases. Their CSAT on escalated cases is 4.6/5 — higher than before — because they receive full context and don't waste time on initial information gathering.

---

## Cost Analysis: Agentic RAG vs Simple RAG

### Setup (Real Data from a Series B SaaS Company's Support System)

**Simple RAG:**
- Single embedding lookup (1536-dim, hosted on Pinecone)
- Top-5 retrieval
- One GPT-4 call for synthesis
- Total: ~1,500 tokens per query

**Agentic RAG:**
- Query analysis (GPT-4): ~500 tokens
- Average 3.2 retrieval hops, each with re-ranking
- Per-hop: embedding lookup + GPT-3.5 relevance judgment (~800 tokens)
- Final synthesis (GPT-4): ~2,000 tokens
- Total: ~5,500 tokens per query

### Cost Breakdown (per 10,000 queries/month)

| Component | Simple RAG | Agentic RAG |
|-----------|-----------|-------------|
| Embedding API calls | $2.10 | $6.72 |
| Vector DB queries | $8.00 | $25.60 |
| GPT-4 (synthesis) | $45.00 | $75.00 |
| GPT-3.5 (intermediate) | $0 | $12.80 |
| Re-ranker (Cohere) | $0 | $15.00 |
| Total monthly cost | **$55.10** | **$135.12** |
| Cost per query | **$0.0055** | **$0.0135** |

### When Does Agentic RAG Pay Off?

**Break-even calculation:** Agentic RAG costs 2.5x more per query. It pays off when:

```
Value of accuracy improvement > Additional cost

For this company:
- Simple RAG resolved 61% of support queries without human escalation
- Agentic RAG resolved 79% without human escalation
- Human agent cost: $8.50 per escalated conversation
- Improvement: 18% fewer escalations = 1,800 fewer human conversations/month
- Savings: 1,800 × $8.50 = $15,300/month
- Additional AI cost: $135.12 - $55.10 = $80.02/month
- Net savings: $15,220/month
- ROI: 19,000%
```

### When Simple RAG is Sufficient

- FAQ-style queries with single-hop answers
- When the knowledge base is small and well-organized
- When accuracy improvement from multi-hop is <5%
- When latency is critical (real-time chat with <2s SLA)
- When queries are simple/factoid: "What are your business hours?"

### When Agentic RAG is Worth It

- Complex queries requiring cross-document reasoning
- High cost of wrong answers (compliance, medical, legal)
- When human escalation costs are high
- When the knowledge base is large and heterogeneous
- When queries are analytical: "Why did our deployment fail and what should we change?"

---

## Summary: Decision Framework

```
Choose SIMPLE RAG when:
  ✓ Most queries are single-hop factoid lookups
  ✓ Knowledge base < 10,000 documents
  ✓ Latency requirement < 3 seconds
  ✓ Accuracy of 60-70% is acceptable
  ✓ Wrong answers have low cost

Choose AGENTIC RAG when:
  ✓ Queries require multi-step reasoning
  ✓ Knowledge base spans multiple domains/formats
  ✓ Accuracy > 85% is required
  ✓ Wrong answers have high cost (legal, medical, financial)
  ✓ Users need source citations and confidence levels
  ✓ Human escalation is expensive
```
