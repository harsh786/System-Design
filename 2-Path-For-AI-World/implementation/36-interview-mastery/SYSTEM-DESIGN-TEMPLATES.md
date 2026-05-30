# System Design Interview Templates for AI Architects

## General Template: "Design an X" Questions

Use this template for any system design question. Spend approximately the indicated time on each section in a 60-minute interview.

### Phase 1: Requirements & Scope (8-10 minutes)

```
1. CLARIFY THE USER
   - Who uses this system? (internal teams, end customers, developers)
   - What's their technical sophistication?
   - How many users? (10 users vs 10M users changes everything)

2. CLARIFY THE USE CASE
   - What's the primary job-to-be-done?
   - What does success look like for the user?
   - What are they doing today without this system?

3. DEFINE FUNCTIONAL REQUIREMENTS (pick 3-5 core)
   - What must the system do?
   - What are the inputs and expected outputs?
   - What's the interaction model? (real-time chat, batch, API)

4. DEFINE NON-FUNCTIONAL REQUIREMENTS
   - Latency: What response time is acceptable?
   - Throughput: How many requests/day?
   - Accuracy: What error rate is acceptable?
   - Availability: What's the uptime requirement?
   - Cost: What's the budget constraint?

5. DEFINE CONSTRAINTS
   - Existing systems to integrate with?
   - Data residency requirements?
   - Team size and skills?
   - Timeline?

6. STATE WHAT YOU'RE NOT BUILDING
   - Explicitly scope out to show you can prioritize
```

### Phase 2: High-Level Architecture (10-12 minutes)

```
1. IDENTIFY CORE COMPONENTS
   - Data ingestion pipeline
   - Storage layer (what type for what data)
   - Processing/inference layer
   - Serving layer
   - Evaluation/monitoring layer

2. DRAW THE DATA FLOW
   - User request → ... → Response
   - Background processing flows
   - Feedback loops

3. CHOOSE KEY TECHNOLOGIES (justify each)
   - Model selection (why this model for this task)
   - Storage choices (why this DB for this access pattern)
   - Infrastructure (cloud services, deployment model)

4. IDENTIFY THE HARD PROBLEMS
   - "The interesting challenges in this design are..."
   - This shows you know where complexity lives
```

### Phase 3: Deep Dive on 2-3 Components (20-25 minutes)

```
Pick components based on:
- What's unique/interesting about this problem
- What the interviewer seems interested in
- Where the hardest tradeoffs are

For each component:
1. Detailed design (data model, API, algorithms)
2. Tradeoffs considered and decision rationale
3. Failure modes and mitigations
4. Scale considerations
```

### Phase 4: Evaluation & Operations (8-10 minutes)

```
1. HOW DO WE KNOW IT'S WORKING?
   - Offline evaluation metrics
   - Online monitoring metrics
   - Business outcome metrics

2. HOW DO WE DEPLOY SAFELY?
   - Progressive rollout strategy
   - Rollback plan
   - Canary metrics

3. HOW DOES IT FAIL GRACEFULLY?
   - Circuit breakers
   - Fallback behaviors
   - Alerting thresholds

4. HOW DOES IT EVOLVE?
   - What changes as scale grows 10x?
   - How do we improve quality over time?
   - What's the v2 roadmap?
```

### Phase 5: Summary & Extensions (3-5 minutes)

```
1. Recap key decisions and tradeoffs
2. Acknowledge limitations of current design
3. Propose extensions if time allowed
```

---

## Requirements Gathering Framework

### The FORCE Framework

| Dimension | Questions to Ask | Why It Matters |
|-----------|-----------------|----------------|
| **F**unctionality | What must it do? What's out of scope? | Prevents over-engineering |
| **O**perational | Who operates it? What's the on-call model? | Drives simplicity vs flexibility tradeoff |
| **R**egulatory | What compliance? What data classification? | May eliminate certain architectures entirely |
| **C**ost | What's the budget? What's the cost per query target? | Constrains model and infrastructure choices |
| **E**volution | What changes in 6/12/24 months? | Drives extensibility decisions |

### Questions That Impress Interviewers

- "What's the cost of being wrong?" (shows risk thinking)
- "Is this replacing an existing process or net-new?" (shows migration thinking)
- "What data do we already have vs need to acquire?" (shows pragmatism)
- "Who is the most skeptical stakeholder and what would convince them?" (shows organizational awareness)
- "What's the minimum viable accuracy to be useful?" (shows product thinking)

---

## Worked Example 1: Customer Support AI Agent

### Requirements (summarized)

- **Users**: Customer support agents + end customers (self-service)
- **Scale**: 50K conversations/day, 500 support agents
- **Latency**: < 3 seconds for response suggestions, < 5 seconds for full answers
- **Accuracy**: Must not provide wrong information; "I don't know" preferred over wrong answer
- **Integration**: Existing ticketing system (Zendesk), knowledge base (Confluence), CRM (Salesforce)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                               │
│  [Chat Widget]  [Agent Desktop]  [API for Integrations]          │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
┌──────────────▼──────────────────────────▼───────────────────────┐
│                     Orchestration Layer                            │
│  [Intent Router] → [Conversation Manager] → [Response Builder]   │
│                         │                                         │
│              [Tool Selection & Execution]                         │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
┌──────────────▼────────┐  ┌─────────────▼────────────────────────┐
│    Retrieval Layer     │  │         Action Layer                  │
│ [Knowledge Base RAG]   │  │ [Ticket Creation]                    │
│ [Conversation History] │  │ [Order Lookup]                       │
│ [Product Catalog]      │  │ [Refund Processing]                  │
│ [Policy Documents]     │  │ [Escalation Routing]                 │
└────────────────────────┘  └──────────────────────────────────────┘
               │                          │
┌──────────────▼──────────────────────────▼───────────────────────┐
│                    Safety & Evaluation Layer                       │
│  [Input Validation] [Output Filtering] [Confidence Scoring]      │
│  [Conversation Logging] [Quality Monitoring] [A/B Testing]       │
└─────────────────────────────────────────────────────────────────┘
```

### Deep Dive: Intent Router & Escalation

The intent router classifies incoming messages into categories: informational (FAQ-like), transactional (needs action), complex (needs human), sensitive (complaint, legal threat).

**Design decisions**:
- Use a fine-tuned classifier (not LLM) for routing—faster (< 50ms), cheaper, more predictable
- Confidence threshold for automation: > 0.85 for full automation, 0.6-0.85 for agent-assisted, < 0.6 for human handoff
- Escalation triggers: sentiment drop, repeated questions, explicit request, safety keywords

**Tradeoffs**:
- Classifier vs LLM for routing: Classifier is 10x faster and cheaper, but requires labeled training data and can't handle novel intents. We add a fallback: if classifier confidence < 0.4, use LLM to classify (costs more but handles edge cases).

### Deep Dive: Knowledge Retrieval

**Chunking strategy**: Hierarchical—article-level summaries for initial matching, paragraph-level chunks for precise retrieval. This handles both "what's your return policy?" (needs the whole article) and "what's the return window for electronics?" (needs one paragraph).

**Freshness**: Knowledge base sync every 15 minutes. Embedding re-generation for changed documents triggered by webhook from Confluence. Stale content flagged with "last verified" date in citations.

**Multi-source fusion**: When query matches multiple sources (KB article + recent ticket resolution + product docs), we use a priority hierarchy: official policy > KB article > ticket resolution. Conflicts are surfaced to the agent rather than auto-resolved.

### Evaluation Strategy

| Metric | Target | Measurement |
|--------|--------|-------------|
| Self-service resolution rate | > 40% | Automated (no human touchpoint) |
| Agent productivity gain | > 25% | Conversations per agent per hour |
| Answer accuracy | > 95% | Weekly human review of 100 samples |
| Customer satisfaction | > 4.2/5 | Post-conversation survey |
| Escalation rate | < 15% | Automated tracking |
| Average handle time | -30% | Ticketing system metrics |

---

## Worked Example 2: Enterprise Document Q&A

### Requirements

- **Users**: 5000 employees across legal, HR, engineering, finance
- **Documents**: 500K documents (PDFs, Word, Confluence, Sharepoint), 2TB total
- **Access control**: Strict—users see only what they're authorized to see
- **Accuracy**: High—employees make decisions based on answers
- **Compliance**: SOC2, data residency (US only), audit trail required

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Ingestion Pipeline                        │
│ [Document Crawlers] → [Parser/Extractor] → [Chunker]      │
│          → [Embedder] → [Access Control Tagger]            │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Storage Layer                             │
│  [Vector Store (per-tenant partitioned)]                   │
│  [Document Store (original + parsed)]                      │
│  [Metadata Store (access, lineage, freshness)]             │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Query Pipeline                            │
│ [Auth Check] → [Query Understanding] → [Retrieval]         │
│     → [Access Filtering] → [Reranking] → [Generation]     │
│     → [Citation Attachment] → [Confidence Scoring]         │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│                    Governance Layer                          │
│  [Audit Log] [Usage Analytics] [Feedback Collection]       │
│  [Quality Monitoring] [Cost Tracking] [Admin Dashboard]    │
└────────────────────────────────────────────────────────────┘
```

### Deep Dive: Access Control in RAG

This is the hardest problem in enterprise document Q&A. Three approaches:

1. **Pre-filtering** (index per group): Create separate vector indices per access group. User query hits only their authorized index.
   - Pro: Guaranteed isolation, fast queries
   - Con: Storage explosion (N copies), slow updates, group membership changes are expensive

2. **Post-filtering** (metadata filter at query time): Single index, each chunk tagged with access groups. Filter results after retrieval.
   - Pro: Single index, simple updates
   - Con: Recall degradation (retrieve 100, filter to 10—might miss relevant authorized docs), metadata leakage risk

3. **Hybrid** (recommended): Partition by classification level (public, internal, confidential, restricted). Within each partition, use metadata filtering for fine-grained access. Most queries hit public + internal (90% of content), so recall is preserved.

**Implementation**: 
- Sync access control from Active Directory/Okta every 5 minutes
- Document classification at ingestion time (automated + human review for sensitive)
- Query-time: resolve user → groups → classification levels → query appropriate partitions
- Audit: log every document chunk served to every user (compliance requirement)

### Deep Dive: Document Freshness & Versioning

- Documents change. The system must handle: new versions, deleted documents, renamed documents
- **Approach**: Content-hash based deduplication. On each crawl, hash content. If hash differs, re-embed and store new version. Old version marked as superseded but retained for audit.
- **Staleness indicator**: Each answer includes "Based on documents last updated [date]." If source document > 90 days old, add warning.
- **Conflict resolution**: When two documents contradict (old policy vs new policy), prefer: (1) more recent, (2) higher authority source, (3) flag for human review if unclear.

---

## Worked Example 3: AI Code Review System

### Requirements

- **Users**: 200 developers across 5 teams
- **Integration**: GitHub PRs, CI/CD pipeline
- **Scope**: Security vulnerabilities, performance issues, style consistency, architecture patterns
- **Constraint**: Must not slow down PR merge velocity
- **Privacy**: Code must not leave the corporate network

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   GitHub Integration Layer                    │
│  [Webhook Listener] → [PR Analyzer] → [Comment Poster]     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Analysis Pipeline                           │
│  [Diff Extractor] → [Context Builder] → [Multi-Pass Review] │
│                                                              │
│  Pass 1: Security (dedicated model, high priority)          │
│  Pass 2: Performance (pattern matching + LLM)               │
│  Pass 3: Style/Architecture (LLM with team config)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Context Layer                               │
│  [Codebase Embeddings] [Team Style Guides] [Past Reviews]   │
│  [Architecture Decision Records] [Known Issues DB]          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Learning & Feedback                         │
│  [Developer Feedback (👍/👎)] → [False Positive Tracker]    │
│  → [Model Improvement Pipeline] → [Precision Monitoring]    │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Self-hosted model**: Since code can't leave the network, deploy a self-hosted model (CodeLlama 34B or similar). Trade off: lower capability than GPT-4 but satisfies privacy constraint. Mitigate with better context (RAG over codebase patterns) and multi-pass analysis.

**Comment quality over quantity**: The biggest risk is noisy reviews that developers ignore. Design principle: fewer, higher-confidence comments. Only post comments with confidence > 0.8. Group related issues into single comments. Maximum 5 comments per PR (prioritized by severity).

**Feedback loop**: Every comment has 👍/👎. Track precision per category per team. If a category's precision drops below 70%, disable it and retrain. This ensures the system maintains developer trust over time.

**Context building**: Don't just analyze the diff. Pull: (1) full file context, (2) related files changed in the same PR, (3) team's style guide, (4) past review comments on similar patterns, (5) architecture decision records. This transforms superficial "linting" into meaningful architectural review.

---

## Worked Example 4: Multi-Tenant AI Platform

### Requirements

- **Users**: 50+ enterprise customers, each with their own data and models
- **Scale**: 10M total queries/day across all tenants
- **Isolation**: Strict data isolation, performance isolation, configuration isolation
- **Customization**: Each tenant can customize: model, prompts, guardrails, tools, knowledge base
- **SLA**: 99.9% availability, < 2s p95 latency

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                                │
│  [Authentication] [Rate Limiting] [Tenant Routing] [Metering]   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Tenant Configuration Layer                     │
│  [Config Store (per-tenant)] [Feature Flags] [Model Registry]   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Orchestration Layer (shared)                   │
│  [Pipeline Executor] → Reads tenant config → Assembles pipeline │
│                                                                  │
│  Shared compute pool with tenant-aware scheduling               │
└────────┬─────────────────────┬──────────────────────┬───────────┘
         │                     │                      │
┌────────▼────────┐ ┌─────────▼─────────┐ ┌─────────▼──────────┐
│  Retrieval Pool  │ │  Inference Pool    │ │  Tool Execution    │
│ (tenant-scoped   │ │ (shared GPU pool   │ │  (sandboxed per    │
│  vector stores)  │ │  with priority     │ │   tenant)          │
│                  │ │  queuing)          │ │                    │
└──────────────────┘ └────────────────────┘ └────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Observability Layer                            │
│  [Per-tenant metrics] [Usage metering] [Quality monitoring]     │
│  [Cost attribution] [SLA tracking] [Alerting]                   │
└─────────────────────────────────────────────────────────────────┘
```

### Deep Dive: Tenant Isolation

**Data isolation**: Each tenant gets a dedicated namespace in the vector store. Not just metadata filtering—physically separate collections. This prevents any possibility of cross-tenant data leakage, even in case of bugs.

**Performance isolation**: Shared compute pool but with per-tenant quotas and priority queuing. No single tenant can starve others. Implementation: token bucket rate limiting + fair-share scheduling. Burst capacity available if pool has headroom.

**Configuration isolation**: Each tenant's pipeline is assembled from shared components but with tenant-specific configuration. Think of it like a template engine: the orchestration logic is shared, but prompts, models, guardrails, and tools are tenant-specific.

**Noisy neighbor prevention**: 
- Per-tenant request queues with max depth
- Circuit breaker per tenant (if one tenant's backend is failing, don't let retries consume shared resources)
- Dedicated capacity option for premium tier (guaranteed GPU allocation)

### Deep Dive: Cost Attribution & Metering

Every API call is metered across dimensions:
- Input tokens, output tokens (model-specific pricing)
- Retrieval queries (vector DB usage)
- Tool executions (external API calls)
- Storage (vector store + document store)

This enables: per-tenant cost tracking, usage-based billing, margin analysis, and capacity planning.

---

## Worked Example 5: AI-Powered Search

### Requirements

- **Users**: E-commerce platform, 5M monthly active users
- **Queries**: 20M searches/day
- **Content**: 2M products with descriptions, reviews, images
- **Latency**: < 200ms p95 (users abandon after 300ms)
- **Revenue**: Search directly drives purchasing; 1% improvement in search relevance = $2M/year

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Query Understanding                          │
│  [Spell Correct] → [Intent Classify] → [Query Expand/Rewrite]  │
│                          (< 30ms total)                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      Retrieval (Parallel)                         │
│  [Lexical/BM25 (30ms)] ║ [Dense Vector (50ms)] ║ [Filters]     │
│                          │                                       │
│              [Fusion & Deduplication (10ms)]                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      Ranking Pipeline                             │
│  [L1: Lightweight ranker (all candidates, < 20ms)]              │
│  [L2: Cross-encoder reranker (top 50, < 50ms)]                  │
│  [L3: Business rules (boost, bury, pin)]                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      Serving Layer                                │
│  [Result Assembly] [Personalization] [A/B Testing] [Cache]      │
└─────────────────────────────────────────────────────────────────┘
```

### Deep Dive: Hybrid Retrieval

Why both lexical and semantic search?
- **Lexical (BM25)**: Excellent for exact matches, product names, SKUs, specific terms. Zero latency for indexed terms. Handles "iPhone 15 Pro Max 256GB" perfectly.
- **Semantic (Dense Vector)**: Handles conceptual queries ("comfortable shoes for standing all day"), misspellings, synonyms. Misses exact terms sometimes.
- **Fusion**: Reciprocal Rank Fusion (RRF) to combine. Weight tuned per query type—product name queries weight lexical higher, descriptive queries weight semantic higher.

**Latency budget allocation** (200ms total):
- Query understanding: 30ms
- Retrieval (parallel): 50ms
- Ranking L1: 20ms
- Ranking L2: 50ms
- Business rules + assembly: 20ms
- Network/overhead: 30ms

### Deep Dive: Real-Time Personalization

Challenge: personalize results without adding latency.

**Approach**: Pre-compute user embedding from purchase history + browse history. Update every 6 hours (not real-time—too expensive). At query time, add user embedding as a lightweight re-ranking signal (multiply relevance score by cosine similarity to user embedding). Adds < 5ms.

**Cold start**: New users get popularity-based ranking until we have 5+ interactions. After that, collaborative filtering embedding kicks in.

### AI-Enhanced Features

- **Natural language search**: "Show me red dresses under $100 for a summer wedding" → parsed into: category=dresses, color=red, price<100, occasion=wedding, season=summer
- **Review summarization**: Pre-computed summaries of product reviews, updated nightly. Shown in search results for quick evaluation.
- **Visual search**: User uploads image → CLIP embedding → find similar products. Separate retrieval path, merged at the fusion layer.

---

## Interview Execution Tips

1. **Drive the conversation**: Don't wait for the interviewer to ask "what about X?" Proactively cover: requirements, architecture, deep dives, evaluation, operations.

2. **State tradeoffs explicitly**: "I'm choosing X over Y because [reason]. The cost of this decision is [downside], which I'm comfortable with because [mitigation]."

3. **Use concrete numbers**: "At 50K queries/day, that's ~0.5 QPS average, maybe 5 QPS peak. A single instance handles this easily, so I won't over-engineer for scale yet—but I'll design the data model to be shardable."

4. **Acknowledge what you're not covering**: "I'm skipping the deployment pipeline details to focus on the retrieval architecture, which I think is the harder problem here. Happy to go into deployment if you'd like."

5. **Show operational maturity**: Always mention: how you monitor it, how you deploy it safely, how it fails gracefully, and how you improve it over time.
