# AI SRE (Site Reliability Engineering)

## Overview

AI SRE extends traditional Site Reliability Engineering principles to AI/ML systems, addressing unique challenges like non-deterministic behavior, model quality degradation, prompt sensitivity, and novel failure modes that don't exist in traditional software systems.

Traditional SRE focuses on availability, latency, and throughput. AI SRE adds dimensions of **quality** (groundedness, relevance, safety), **cost** (token economics), and **behavioral correctness** (agent loops, tool misuse, hallucination).

---

## 1. AI SLOs (Service Level Objectives)

### 1.1 Availability SLO (99.9%)

**Definition**: The AI system successfully processes requests without infrastructure-level failures.

- **SLI**: `successful_responses / total_requests` over a rolling 28-day window
- **Target**: 99.9% (allows ~43 minutes of downtime per month)
- **Exclusions**: Planned maintenance windows, client-side errors (4xx)
- **Measurement**: At the API gateway level, counting 5xx errors, timeouts, and circuit breaker activations

**What counts as "unavailable" for AI systems:**
- Model provider returning errors (OpenAI 500s, rate limits exhausted)
- Vector DB connection failures
- Embedding service timeouts
- Agent orchestrator crashes
- MCP server unreachable
- Token budget exhausted (system refuses all requests)

### 1.2 Latency SLO (p95 < target)

**Definition**: 95th percentile end-to-end response time stays below configured threshold.

- **SLI**: `p95(response_time)` measured at client-facing edge
- **Targets** (vary by endpoint type):
  - Simple RAG query: p95 < 3s
  - Multi-step agent task: p95 < 30s
  - Streaming first-token: p95 < 800ms
  - Tool execution: p95 < 5s per tool call
- **Measurement**: From request receipt to final response byte

**AI-specific latency concerns:**
- Token generation speed (tokens/second)
- Retrieval latency (vector search + reranking)
- Sequential tool calls compounding latency
- Model "thinking" time for reasoning models
- Retry overhead when primary model is slow

### 1.3 Cost SLO (below budget)

**Definition**: Per-request and aggregate costs stay within defined budgets.

- **SLI**: `actual_cost / budgeted_cost` ratio
- **Targets**:
  - Per-request median cost: < $0.05
  - Per-request p99 cost: < $2.00
  - Daily aggregate: < daily budget
  - Monthly aggregate: < monthly budget with linear burn
- **Measurement**: Token counts × model pricing, plus infrastructure costs

**Cost components tracked:**
- Input tokens (prompt + context)
- Output tokens (completion)
- Embedding generation
- Vector DB queries
- Tool API calls (external service costs)
- Compute for reranking/post-processing

### 1.4 Groundedness SLO (>= target)

**Definition**: AI responses are factually supported by provided context/sources.

- **SLI**: `grounded_responses / evaluated_responses` via automated judge
- **Target**: >= 85% of responses scored as grounded
- **Measurement**: LLM-as-judge evaluating if claims are supported by retrieved context
- **Sampling**: Evaluate 10% of production responses continuously

**Groundedness failures:**
- Hallucinated facts not in source documents
- Incorrect citations (citing wrong source)
- Over-extrapolation beyond what sources support
- Confabulated statistics or dates
- Mixing information across unrelated documents

### 1.5 Retrieval Recall SLO (>= target)

**Definition**: The retrieval system finds relevant documents for queries.

- **SLI**: `relevant_retrieved / total_relevant` on benchmark query set
- **Target**: >= 80% recall on golden test set
- **Measurement**: Weekly automated evaluation against curated query-document pairs
- **Supplementary SLI**: User feedback signals (thumbs up/down, reformulations)

### 1.6 Tool Success SLO (>= target)

**Definition**: When the AI decides to use a tool, the tool executes successfully.

- **SLI**: `successful_tool_calls / total_tool_calls`
- **Target**: >= 95% tool call success rate
- **Excludes**: Cases where AI correctly decides NOT to use a tool
- **Breakdown**: Per-tool success rates tracked individually

**Tool failure types:**
- Permission denied (auth expired)
- Invalid parameters (AI malformed the call)
- Timeout (external service slow)
- Rate limited (too many calls)
- Schema mismatch (tool API changed)

### 1.7 Safety SLO (zero critical)

**Definition**: No critical safety violations in production responses.

- **SLI**: `critical_safety_violations` count (target: 0)
- **Target**: Zero critical violations; < 0.1% minor violations
- **Measurement**: Real-time safety classifier on all outputs + async human review sample
- **Critical violations**: PII exposure, harmful content generation, prompt injection success, unauthorized actions

**Safety categories:**
- **Critical (P0)**: Data leakage, unauthorized system access, harmful content to minors
- **High (P1)**: PII in responses, prompt injection partial success, policy violations
- **Medium (P2)**: Borderline content, overly confident wrong answers
- **Low (P3)**: Tone issues, minor policy stretches

### 1.8 Escalation Quality SLO

**Definition**: When the AI escalates to humans, the escalation is appropriate and well-formed.

- **SLI**: `appropriate_escalations / total_escalations` (judged by receiving team)
- **Target**: >= 90% of escalations rated as appropriate
- **Anti-target**: Under-escalation rate < 1% (missed escalations are worse than over-escalation)
- **Measurement**: Human review of escalation decisions + outcome tracking

---

## 2. AI Incident Types (11 Types)

### Type 1: Model Provider Outage

**Description**: The upstream LLM provider (OpenAI, Anthropic, Google) is unavailable or degraded.

**Symptoms:**
- 5xx errors from model API
- Elevated latency (>10x normal)
- Rate limit errors even at normal traffic
- Partial responses or truncated completions

**Blast radius**: All requests requiring that model; potentially entire system if no fallback.

**Detection**: Health check failures, error rate spike, latency spike on model calls.

**Typical duration**: 15 minutes to 4 hours.

### Type 2: Vector DB Outage

**Description**: The vector database (Pinecone, Weaviate, Qdrant, pgvector) is unavailable.

**Symptoms:**
- RAG queries return empty results
- Similarity search timeouts
- Connection pool exhaustion
- Inconsistent results (partial index availability)

**Blast radius**: All RAG-dependent queries; system may still answer from parametric knowledge.

**Detection**: Health checks, empty result rate spike, query latency spike.

### Type 3: Bad Prompt Deployment

**Description**: A prompt change was deployed that degrades quality, causes errors, or changes behavior unexpectedly.

**Symptoms:**
- Quality metrics drop (groundedness, relevance)
- Unexpected output format changes
- Increased hallucination rate
- User complaints spike
- Token usage anomaly (prompt too verbose or causes verbose outputs)

**Blast radius**: All requests using the affected prompt template.

**Detection**: Quality metric degradation, A/B test failure, user feedback spike.

**Subtlety**: May take hours to detect because individual responses "look reasonable" but aggregate quality drops.

### Type 4: Retrieval Index Corruption

**Description**: The vector index contains corrupted, duplicate, or incorrectly embedded documents.

**Symptoms:**
- Irrelevant retrieval results
- Duplicate chunks inflating context
- Retrieval recall drop on benchmark queries
- Specific topics always return wrong documents
- Embedding dimension mismatch errors

**Blast radius**: Queries related to corrupted portion of index.

**Detection**: Retrieval quality monitoring, embedding validation checks, user feedback patterns.

### Type 5: Embedding Version Mismatch

**Description**: Documents were indexed with embedding model v1 but queries use embedding model v2 (or vice versa).

**Symptoms:**
- Retrieval recall drops dramatically
- Cosine similarity scores uniformly low
- "No relevant results" for queries that should match
- Only recently indexed documents are retrievable

**Blast radius**: All retrieval queries against mismatched index partitions.

**Detection**: Average similarity score monitoring, retrieval recall benchmark, version metadata checks.

**Root cause**: Embedding model upgrade without full re-indexing, or partial re-index failure.

### Type 6: Tool API Permission Bug

**Description**: A tool's API credentials expired, permissions changed, or auth configuration is wrong.

**Symptoms:**
- Specific tool always fails with 401/403
- Agent retries tool calls repeatedly then gives up
- Degraded responses due to missing tool capabilities
- Cascading failures if tool provides critical data

**Blast radius**: All requests needing the affected tool.

**Detection**: Tool-specific error rate monitoring, permission check automation.

### Type 7: Cost Spike

**Description**: AI system costs increase dramatically beyond budget.

**Symptoms:**
- Daily spend exceeds 3x normal
- Per-request cost p99 explodes
- Token usage anomaly (very long prompts or completions)
- Specific users/tenants consuming disproportionate resources

**Blast radius**: Financial impact; may trigger rate limiting affecting all users.

**Root causes:**
- Runaway agent loops generating many tool calls
- Prompt injection causing maximum-length outputs
- Context window stuffing (retrieving too many documents)
- Model upgrade (GPT-4 instead of GPT-3.5 accidentally)
- Traffic spike from integration partner
- Retry storms from transient errors

### Type 8: Latency Spike

**Description**: Response times increase significantly beyond SLO targets.

**Symptoms:**
- p95 latency exceeds target by >2x
- User-visible slowness
- Timeouts increasing
- Queue depth growing

**Root causes:**
- Model provider degradation (not full outage)
- Vector DB under-provisioned for traffic
- Sequential tool calls with slow external APIs
- Context window size increase (more tokens = slower)
- Concurrent request saturation
- Network issues to cloud providers

### Type 9: Prompt Injection Incident

**Description**: An attacker successfully manipulates the AI through crafted inputs.

**Symptoms:**
- AI ignoring system instructions
- Unauthorized information disclosure
- AI performing unintended actions
- Output contains attacker's injected instructions
- Safety filters bypassed

**Blast radius**: Potentially critical—data leakage, unauthorized actions, reputation damage.

**Detection**: Output anomaly detection, safety classifier, behavioral drift monitoring, user report.

**Severity**: Always starts as P1/P0 until scope is determined.

### Type 10: Data Leakage

**Description**: AI system exposes sensitive data it shouldn't—PII, internal docs, other tenants' data.

**Symptoms:**
- PII detected in outputs (by classifier)
- User reports seeing other users' data
- Internal-only information in external-facing responses
- Training data memorization in outputs

**Blast radius**: Critical—regulatory, legal, trust implications.

**Detection**: PII classifier, data boundary monitoring, tenant isolation checks.

**Response**: Immediate containment, legal notification, audit of exposure scope.

### Type 11: Runaway Agent Loop

**Description**: An AI agent enters an infinite or near-infinite loop of tool calls without converging.

**Symptoms:**
- Single request consuming 50+ tool calls
- Cost per request orders of magnitude above normal
- Agent "thinking" for minutes without producing output
- Repeated identical tool calls
- Resource exhaustion from single request

**Blast radius**: Cost impact, resource starvation for other requests, potential external API abuse.

**Detection**: Step count monitoring, per-request cost tracking, tool call pattern analysis.

**Root cause**: Ambiguous instructions + tool that never returns satisfying result, circular dependencies, missing termination conditions.

---

## 3. Runbooks (11 Procedures)

### Runbook 1: Disable Tools

**When**: Tool is malfunctioning, compromised, or causing agent loops.

**Steps:**
1. Identify the problematic tool by name/ID
2. Verify tool is causing issues (check error logs, recent calls)
3. Update tool registry to mark tool as disabled
4. Verify AI system no longer attempts to call disabled tool
5. Monitor for degraded responses due to missing capability
6. Notify dependent teams
7. Document reason and expected re-enable timeline

**Verification**: Attempt a request that would normally use the tool; confirm graceful degradation.

### Runbook 2: Switch Model Provider

**When**: Primary model provider is down or severely degraded.

**Steps:**
1. Confirm primary provider outage (not just transient error)
2. Check fallback provider health and capacity
3. Update routing configuration to fallback provider
4. Verify prompt compatibility with fallback model
5. Monitor quality metrics (fallback may be lower quality)
6. Adjust rate limits for fallback (may have lower capacity)
7. Communicate to users if quality degradation expected
8. Set reminder to switch back when primary recovers

**Verification**: Send test queries through fallback; confirm responses are acceptable quality.

### Runbook 3: Rollback Prompt

**When**: New prompt deployment causes quality regression or errors.

**Steps:**
1. Identify the problematic prompt version
2. Verify previous version is available in version control
3. Deploy previous prompt version
4. Clear any prompt caches
5. Verify new requests use rolled-back prompt
6. Monitor quality metrics for recovery
7. Block the bad version from redeployment
8. Create ticket for prompt team to investigate

**Verification**: Run golden test set against rolled-back prompt; compare metrics to baseline.

### Runbook 4: Rollback Retriever

**When**: Retrieval quality has degraded due to index corruption, config change, or embedding mismatch.

**Steps:**
1. Identify retrieval degradation scope (all queries or subset)
2. Check for recent index changes or embedding model updates
3. Switch to previous known-good index snapshot
4. If snapshot unavailable, switch to degraded mode (no RAG, or reduced context)
5. Verify retrieval recall recovers on benchmark queries
6. Plan full re-index if corruption is confirmed
7. Investigate root cause (bad ingest, embedding change, etc.)

**Verification**: Run retrieval benchmark suite; confirm recall >= target.

### Runbook 5: Disable MCP Server

**When**: An MCP (Model Context Protocol) server is compromised, malfunctioning, or causing issues.

**Steps:**
1. Identify problematic MCP server
2. Disconnect MCP server from agent orchestrator
3. Update tool availability (tools provided by that MCP server become unavailable)
4. Verify agent handles missing tools gracefully
5. Monitor for user-visible impact
6. Investigate MCP server issue
7. Plan remediation and re-enable criteria

### Runbook 6: Block Tenant/User

**When**: A specific tenant or user is abusing the system, triggering safety violations, or causing resource issues.

**Steps:**
1. Identify the tenant/user ID
2. Verify abuse (not false positive from detection system)
3. Apply block at API gateway level
4. Return appropriate error message (429 or 403)
5. Preserve evidence (request logs, response logs)
6. Notify account management / trust & safety team
7. Document block reason and review timeline
8. Set calendar reminder for review

### Runbook 7: Lower Max Steps

**When**: Agent loops are occurring, cost is spiking, or you need to reduce blast radius.

**Steps:**
1. Determine current max steps configuration
2. Reduce max steps (e.g., from 20 to 5)
3. Deploy configuration change
4. Monitor for requests hitting the new lower limit
5. Assess user impact (are legitimate complex tasks being truncated?)
6. Communicate to users about temporary reduced capability
7. Plan restoration after root cause addressed

### Runbook 8: Force Human Approval

**When**: AI is taking actions with unexpected consequences, during incident investigation, or after safety incident.

**Steps:**
1. Enable human-in-the-loop for all write actions
2. Configure approval queue with on-call team
3. Set SLA for approval response time
4. Monitor queue depth (ensure approvals aren't bottlenecked)
5. Track rejection rate (high rejection = AI is still misbehaving)
6. Plan criteria for returning to autonomous operation

### Runbook 9: Pause Write Actions

**When**: AI is performing unintended writes, data corruption suspected, or during security incident.

**Steps:**
1. Identify write action categories to pause (all, or specific tools)
2. Update action policy to read-only mode
3. Return informative message to users ("write actions temporarily unavailable")
4. Verify no write actions are getting through
5. Audit recent write actions for damage assessment
6. Plan remediation for any incorrect writes
7. Define criteria for re-enabling writes

### Runbook 10: Purge Poisoned Documents

**When**: Malicious or incorrect documents were ingested into the knowledge base.

**Steps:**
1. Identify poisoned documents (by source, timestamp, content pattern)
2. Remove documents from vector index
3. Remove documents from document store
4. Clear any caches that may serve stale results
5. Verify removal (search for known poisoned content, confirm zero results)
6. Assess if any users received responses based on poisoned documents
7. If yes, notify affected users
8. Investigate ingestion pipeline for how bad docs entered
9. Add validation rules to prevent recurrence

### Runbook 11: Re-index Knowledge Base

**When**: Index corruption, embedding model upgrade, or after purging documents.

**Steps:**
1. Verify source documents are intact and clean
2. Choose re-indexing strategy (full rebuild vs. incremental)
3. If full rebuild: create new index alongside old
4. Run embedding pipeline on all documents
5. Validate new index with retrieval benchmark
6. If benchmark passes: switch traffic to new index
7. If benchmark fails: investigate, keep old index active
8. Decommission old index after validation period
9. Update metadata (embedding model version, index timestamp)

---

## 4. Error Budgets for AI Systems

### Traditional Error Budget Concept

Error budget = 1 - SLO target. For 99.9% availability, error budget is 0.1% (43.2 minutes/month).

### AI-Specific Error Budget Dimensions

**Multi-dimensional error budgets:** AI systems have error budgets across multiple SLOs simultaneously:

| SLO | Target | Monthly Budget |
|-----|--------|----------------|
| Availability | 99.9% | 43.2 min downtime |
| Latency (p95) | < 3s | 0.1% of requests can exceed |
| Groundedness | >= 85% | 15% of responses can be ungrounded |
| Safety | 0 critical | 0 critical violations |
| Cost | < budget | 10% overage buffer |

### Error Budget Policies

**When budget is healthy (>50% remaining):**
- Normal deployment velocity
- Experimentation allowed
- Chaos engineering runs permitted
- New prompt versions can be deployed

**When budget is concerning (20-50% remaining):**
- Slow down deployments
- Extra review for changes
- Increase monitoring sensitivity
- No chaos experiments

**When budget is critical (<20% remaining):**
- Freeze non-critical deployments
- Focus entirely on reliability
- Incident review for every SLO breach
- Consider rollbacks of recent changes

**When budget is exhausted (0%):**
- All feature work stops
- Only reliability improvements deployed
- Mandatory postmortem for budget exhaustion
- Executive visibility

### AI-Specific Budget Considerations

1. **Quality budgets are harder to measure** — groundedness requires evaluation which has latency
2. **Safety has zero budget** — any critical safety violation is immediately an incident
3. **Cost budgets interact with availability** — cutting costs may reduce availability (cheaper model = more errors)
4. **Seasonal patterns** — some AI workloads have periodic quality fluctuations

---

## 5. On-Call for AI Systems

### What's Different from Traditional SRE On-Call

| Aspect | Traditional SRE | AI SRE |
|--------|----------------|--------|
| Alert clarity | "Server X is down" | "Groundedness dropped 5% in last hour" |
| Debugging | Deterministic—same input, same bug | Non-deterministic—same input, different output |
| Rollback | Deploy previous binary | Which component? Prompt? Model? Index? Config? |
| Vendor dependency | Your infra, your control | Model provider outage = nothing you can do |
| Failure detection | Immediate (health checks) | Gradual (quality degrades over hours) |
| Blast radius assessment | Clear (which servers affected) | Unclear (which queries affected?) |
| Root cause | Stack trace, logs, metrics | "The model started hallucinating more" |

### On-Call Responsibilities

1. **Monitor SLO dashboards** — all 8 SLO dimensions
2. **Triage alerts** — distinguish model issues from infra issues
3. **Execute runbooks** — follow documented procedures
4. **Escalate appropriately** — know when to wake up ML engineers vs. infra vs. security
5. **Communicate** — status page updates, stakeholder notifications
6. **Preserve evidence** — save problematic requests/responses for analysis

### On-Call Toolkit

- Access to all runbooks with one-click execution
- Model provider status pages (bookmarked)
- Query replay capability (re-run problematic queries)
- Feature flags for quick toggling
- Direct escalation contacts for each failure domain

### On-Call Rotation Design

- **Primary**: Handles all alerts, executes runbooks
- **Secondary**: Backup for complex incidents, ML expertise
- **Escalation**: ML engineers for model quality issues, Security for safety incidents

---

## 6. Postmortem Process for AI Incidents

### AI Postmortem Template

```
# Incident Postmortem: [Title]

## Summary
- Duration: X hours Y minutes
- Impact: Z users affected, N requests degraded
- Severity: P0/P1/P2/P3
- SLOs breached: [list]
- Error budget consumed: X%

## Timeline
- HH:MM - First signal (what metric moved)
- HH:MM - Alert fired
- HH:MM - On-call acknowledged
- HH:MM - Root cause identified
- HH:MM - Mitigation applied
- HH:MM - Full recovery confirmed

## Root Cause
[Detailed technical explanation]

## AI-Specific Analysis
- Was this a model behavior change?
- Was this a data/retrieval issue?
- Was this a prompt/configuration issue?
- Could this have been caught by evaluation?
- Did non-determinism make this harder to detect?

## What Went Well
- [bullet points]

## What Went Wrong
- [bullet points]

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
| ... | ... | ... | ... |

## Lessons Learned
- [Specific to AI systems]
```

### AI-Specific Postmortem Questions

1. **Could automated evaluation have caught this earlier?**
2. **Was the failure mode in our chaos engineering scenarios?**
3. **Did we have appropriate fallback behavior?**
4. **Was the model provider's status page accurate?**
5. **Did our quality monitoring have sufficient coverage?**
6. **Was the prompt change process sufficient?**
7. **Do we need new SLOs based on this incident?**

---

## 7. Chaos Engineering for AI Systems

### Why Chaos Engineering for AI

AI systems have unique failure modes that are hard to predict:
- What happens when the model returns garbage?
- What happens when retrieval returns irrelevant results?
- What happens when a tool is slow but not down?
- What happens when embeddings are slightly wrong?

### Chaos Experiment Categories

**Infrastructure chaos:**
- Kill model provider connection
- Add latency to vector DB
- Corrupt network between services
- Exhaust token rate limits

**Data chaos:**
- Inject irrelevant documents into index
- Return empty retrieval results
- Serve stale embeddings
- Corrupt metadata

**Model behavior chaos:**
- Inject high-latency responses
- Return malformed JSON from model
- Simulate model returning refusals
- Add random truncation to responses

**Load chaos:**
- Spike traffic 10x
- Send adversarial queries
- Flood with expensive requests
- Simulate retry storms

### Safety Controls

- **Kill switch**: Immediately stop any chaos experiment
- **Blast radius limits**: Never affect more than X% of traffic
- **Duration limits**: Auto-stop after configured time
- **Environment gates**: Never run in production without approval
- **Monitoring integration**: Auto-stop if SLOs breach during experiment

---

## 8. Capacity Planning and Autoscaling

### AI-Specific Capacity Dimensions

1. **Token throughput**: Tokens/second the system can process
2. **Concurrent requests**: Max parallel model calls
3. **Vector DB QPS**: Queries per second for retrieval
4. **Embedding throughput**: Documents/second for indexing
5. **Context window utilization**: How much of model context is used (affects cost and latency)
6. **Rate limits**: Provider-imposed limits on API calls

### Autoscaling Strategies

**Horizontal scaling:**
- More retrieval replicas for read-heavy workloads
- More embedding workers for indexing spikes
- More orchestrator instances for concurrent requests

**Vertical scaling:**
- Larger context windows (upgrade model tier)
- Higher-memory vector DB instances
- Faster compute for reranking

**Model-level scaling:**
- Route simple queries to smaller/cheaper models
- Use larger models only when needed (quality routing)
- Batch similar requests for efficiency
- Pre-compute common queries

### Capacity Planning Signals

- Token usage growth rate
- Query volume trends
- Knowledge base growth rate
- New tool/capability additions (each adds load)
- Seasonal patterns (end of quarter, holidays)

---

## 9. Cost SRE (Managing AI Costs as Reliability)

### Philosophy

In AI systems, **cost is a reliability dimension**. Uncontrolled costs lead to:
- Budget exhaustion → system shutdown → availability impact
- Cost-cutting → quality degradation → user experience impact
- Surprise bills → organizational trust erosion → reduced investment

### Cost Monitoring

**Real-time cost tracking:**
- Per-request cost (tokens × price)
- Per-tenant cost allocation
- Per-feature cost attribution
- Cost anomaly detection

**Cost SLIs:**
- Median cost per request
- p95 cost per request
- Daily total spend
- Cost per successful outcome (not just per request)

### Cost Optimization Levers

1. **Prompt optimization**: Shorter prompts = fewer input tokens
2. **Context pruning**: Retrieve fewer, more relevant documents
3. **Model routing**: Use cheaper models for simple queries
4. **Caching**: Cache common queries/embeddings
5. **Batching**: Combine multiple operations
6. **Output length limits**: Cap maximum response tokens
7. **Early termination**: Stop agent when answer is sufficient

### Cost Incident Response

When cost spikes are detected:
1. Identify source (which tenant, feature, or query pattern)
2. Apply per-request cost caps
3. Enable aggressive caching
4. Route to cheaper models
5. Rate limit expensive operations
6. Investigate root cause (runaway loops, prompt injection, traffic spike)

---

## Summary

AI SRE is fundamentally about applying disciplined reliability engineering to systems that are:
- **Non-deterministic** (same input, different output)
- **Multi-vendor dependent** (model providers, embedding services, tool APIs)
- **Quality-sensitive** (not just up/down, but "good enough")
- **Expensive** (every request has meaningful cost)
- **Safety-critical** (bad outputs can cause real harm)

The key insight: **Traditional SRE asks "is it working?" AI SRE asks "is it working well enough, safely enough, cheaply enough?"**
