# Production RAG Challenges

## Overview

Building a RAG prototype takes a day. Building a production RAG system that's reliable, secure, and cost-effective takes months. This guide covers the hard problems that only surface at scale.

---

## Challenge 1: Stale Data and Freshness

**The problem**: Your vector store says the refund window is 14 days, but the policy was updated to 30 days yesterday.

### Freshness Strategies

| Strategy | Freshness | Cost | Complexity |
|----------|-----------|------|-----------|
| Full re-index (nightly) | 24h lag | High | Low |
| Incremental sync (hourly) | 1h lag | Medium | Medium |
| Event-driven (webhooks) | Minutes | Low | High |
| Real-time streaming | Seconds | Very high | Very high |

### Best Practice
- **Critical data** (pricing, policies): Event-driven, < 5 min lag
- **Reference data** (docs, guides): Hourly incremental sync
- **Archive data** (historical): Nightly batch

---

## Challenge 2: Permission-Aware Retrieval

**The problem**: User A asks "What's the salary band for L5 engineers?" They should only see this if they're in HR or management.

```mermaid
graph TD
    Q[Query + User Identity] --> AUTH[Check User Permissions]
    AUTH --> FILTER[Add permission filter<br>to vector search]
    FILTER --> SEARCH[Search ONLY<br>authorized documents]
    SEARCH --> LLM[Generate]
```

### Implementation Approaches

| Approach | How It Works | Tradeoff |
|----------|-------------|----------|
| **Pre-filter** | Filter by ACL before vector search | Fast but limits recall |
| **Post-filter** | Search all, filter results by permission | Wastes retrieval slots |
| **Separate indexes** | One index per permission group | Storage overhead |
| **Attribute-based** | Tag chunks with required permissions | Most flexible |

### Critical Rule
**Never rely on the LLM to enforce permissions.** The LLM will happily summarize confidential documents if they're in the context. Filtering must happen BEFORE the context reaches the LLM.

---

## Challenge 3: Multi-Tenant RAG

**The problem**: Company A and Company B both use your RAG platform. Company A must NEVER see Company B's data.

### Isolation Strategies

| Strategy | Isolation | Cost | Operations |
|----------|-----------|------|-----------|
| **Separate databases** | Complete | High | Complex |
| **Namespace/collection per tenant** | Strong | Medium | Medium |
| **Metadata filtering** | Logical | Low | Simple |

**Rule**: For regulated industries (healthcare, finance), use separate databases. For SaaS products, namespace isolation is usually sufficient.

---

## Challenge 4: Conflicting Information

**The problem**: Two documents say different things.
- Doc A (2023): "The maximum API rate limit is 100 req/s"
- Doc B (2024): "The maximum API rate limit is 500 req/s"

### Resolution Strategies

1. **Recency wins**: Always prefer the newer document (requires date metadata)
2. **Authority wins**: Official docs > blog posts > Slack messages
3. **Present both**: "According to [2024 doc], it's 500. Note: an older doc mentions 100."
4. **Human escalation**: Flag conflicting answers for review

---

## Challenge 5: Scale Challenges

### Millions of Documents

| Challenge | At 1K docs | At 1M docs | At 100M docs |
|-----------|-----------|-----------|-------------|
| Index time | Minutes | Hours | Days |
| Storage | MBs | GBs | TBs |
| Query latency | 5ms | 20ms | 100ms+ |
| Re-indexing | Easy | Expensive | Needs strategy |

### Scaling Strategies
- **Sharding**: Split index by domain/date/tenant
- **Hierarchical retrieval**: Coarse filter → fine search
- **Approximate nearest neighbor** (HNSW): Trade tiny accuracy for huge speed gains
- **Caching**: Frequent queries hit cache, not vector DB

---

## Challenge 6: Cost at Scale

### Cost Breakdown (100K queries/day)

| Component | Unit Cost | Daily Cost (100K queries) |
|-----------|-----------|--------------------------|
| Embedding (query) | $0.0001/query | $10 |
| Vector DB queries | $0.0001/query | $10 |
| Re-ranking | $0.001/query | $100 |
| LLM generation | $0.03/query | $3,000 |
| **Total** | | **~$3,120/day** |

### Cost Optimization
1. **Cache frequent queries** — 20% of queries are repeats
2. **Use smaller models** for simple queries (routing)
3. **Reduce context size** — fewer chunks = fewer tokens = lower cost
4. **Batch embeddings** during ingestion
5. **Use local models** for embedding and reranking

---

## Challenge 7: Monitoring RAG Quality

### What to Monitor

```mermaid
graph TD
    subgraph "Health Metrics"
        H1[Retrieval latency P50/P95]
        H2[Empty result rate]
        H3[Error rate]
    end
    
    subgraph "Quality Metrics"
        Q1[Faithfulness score<br>sampled]
        Q2[User satisfaction<br>thumbs up/down]
        Q3[Retrieval relevance<br>LLM-judged]
    end
    
    subgraph "Business Metrics"
        B1[Queries per day]
        B2[Cost per query]
        B3[Escalation rate]
    end
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Empty retrieval rate | > 5% | > 15% |
| Avg faithfulness | < 0.8 | < 0.6 |
| P95 latency | > 3s | > 5s |
| User thumbs-down rate | > 10% | > 25% |

---

## Challenge 8: Common Failure Modes

### The Retrieval Failure Taxonomy

| Failure Mode | Symptom | Root Cause | Fix |
|-------------|---------|-----------|-----|
| **No results** | "I don't have that info" | Query doesn't match any chunks | Multi-query, HyDE |
| **Wrong results** | Confident wrong answer | Retrieved irrelevant chunks | Better chunking, reranking |
| **Partial results** | Incomplete answer | Answer spans multiple chunks | Overlap, parent-child |
| **Stale results** | Outdated answer | Index not refreshed | Freshness pipeline |
| **Hallucinated answer** | Plausible but unsupported | LLM ignoring context | Stronger prompting, faithfulness check |
| **Permission leak** | Unauthorized info exposed | Missing ACL filter | Pre-retrieval filtering |

### Debugging Workflow

```mermaid
graph TD
    BAD[Bad Answer] --> CHECK1{Retrieved chunks<br>relevant?}
    CHECK1 -->|No| RETRIEVAL[Fix retrieval<br>chunking/embedding/query]
    CHECK1 -->|Yes| CHECK2{Answer matches<br>chunks?}
    CHECK2 -->|No| GENERATION[Fix generation<br>prompting/model]
    CHECK2 -->|Yes| CHECK3{Chunks accurate/<br>current?}
    CHECK3 -->|No| INGESTION[Fix ingestion<br>freshness/cleaning]
    CHECK3 -->|Yes| GOOD[System working<br>correctly]
```

---

## Challenge 9: Latency Budget

Users expect < 3 seconds for a response. Here's how to hit that:

| Component | Target | Optimization |
|-----------|--------|-------------|
| Query processing | < 50ms | Cache embeddings |
| Vector search | < 50ms | ANN indexes, limit scope |
| Re-ranking | < 150ms | Limit to top 20 candidates |
| LLM generation | < 2000ms | Streaming, smaller context |
| **Total** | **< 2.5s** | |

**Key insight**: Stream the LLM response. Users perceive streaming as faster even if total time is the same.

---

## Production Checklist

Before launching RAG to production:

- [ ] Permission filtering verified (red team tested)
- [ ] Freshness pipeline running and monitored
- [ ] Evaluation pipeline with golden dataset
- [ ] Cost projections at expected scale
- [ ] Latency within SLA under load
- [ ] Graceful degradation when components fail
- [ ] Logging for debugging (query, retrieved chunks, answer)
- [ ] User feedback mechanism (thumbs up/down)
- [ ] Alerting on quality drops
- [ ] Data deletion/GDPR compliance

---

## Key Takeaways

1. **Security first**: Permission filtering is non-negotiable
2. **Freshness is a spectrum**: Match freshness guarantees to data criticality
3. **Monitor quality continuously**: Silent degradation is the norm
4. **Cost grows with scale**: Plan optimization early
5. **Debug systematically**: Isolate retrieval vs generation failures
6. **Production RAG is an ongoing operation**, not a one-time build
