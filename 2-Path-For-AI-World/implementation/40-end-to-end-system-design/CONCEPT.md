# Module 40: End-to-End AI System Design Exercises

## Purpose

This module bridges ALL previous modules (1-39) into complete, interview-ready system design walkthroughs. Each design demonstrates how data pipelines, retrieval, agents, security, evaluation, deployment, and cost optimization converge in production systems.

---

## How to Use This Module

Each design follows the same structure:
1. **Requirements** — Functional + non-functional constraints
2. **Architecture** — ASCII diagram showing all components
3. **Component Deep-Dive** — How each piece works
4. **Data Flow** — Request lifecycle end-to-end
5. **Security Model** — Auth, guardrails, compliance
6. **Scaling Plan** — From MVP to enterprise scale
7. **Failure Modes** — What breaks and how to recover
8. **Cost Estimate** — Per-query and monthly breakdown
9. **Evaluation** — How you know it's working

---

# Design 1: Enterprise Knowledge Assistant (Glean/Guru-style)

## 1.1 Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Users | Enterprise employees | 100 → 100K users |
| Latency | Time to first token | < 2 seconds |
| Accuracy | Answer correctness | > 90% on golden set |
| Sources | Data integrations | Confluence, Slack, Drive, Jira, Email, Code |
| Security | Access control | Document-level ACL enforcement |
| Compliance | Data residency | Single-tenant, region-locked |
| Availability | Uptime SLA | 99.9% during business hours |
| Cost | Per-query budget | < $0.05 average |

## 1.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER LAYER                                     │
│  [Web App] [Slack Bot] [Browser Extension] [API]                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY                                       │
│  Auth │ Rate Limit │ Tenant Routing │ Request Logging                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ QUERY PLANNER│ │ RETRIEVAL    │ │ GENERATION           │
│              │ │              │ │                      │
│ Intent Class │ │ Hybrid Search│ │ Context Assembly     │
│ Query Rewrite│ │ Reranking    │ │ LLM Call (streaming) │
│ Tool Select  │ │ ACL Filter   │ │ Citation Extraction  │
│ Confidence   │ │ Freshness    │ │ Confidence Score     │
└──────────────┘ └──────────────┘ └──────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                           │
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ Vector DB   │  │ Full-Text   │  │ Graph DB    │  │ Cache Layer  │  │
│  │ (Pinecone)  │  │ (Elastic)   │  │ (Neo4j)     │  │ (Redis)      │  │
│  │             │  │             │  │             │  │              │  │
│  │ Embeddings  │  │ BM25 Index  │  │ Doc→Team    │  │ Query Cache  │  │
│  │ 768-dim     │  │ Per-source  │  │ User→Access │  │ Embedding $  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              INGESTION PIPELINE                                   │    │
│  │  Connectors → Extraction → Chunking → Embedding → Indexing      │    │
│  │  (20+ sources)  (Tika)    (semantic)  (batch GPU)  (upsert)     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY & EVAL                                    │
│  Traces (Langfuse) │ Metrics (Prometheus) │ Eval (Golden Set + Online)  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 1.3 Component Deep-Dive

### Ingestion Pipeline (Modules 3, 4, 5)

```
Source Connectors:
├── Confluence: REST API polling every 15min, webhook for real-time
├── Slack: Socket Mode for real-time, Conversations API for backfill
├── Google Drive: Push notifications + periodic full crawl
├── Jira: Webhooks + daily reconciliation
├── GitHub: Webhooks for PRs/Issues, clone for code
└── Email: Microsoft Graph API with delta sync

Chunking Strategy:
├── Documents: Semantic chunking (paragraph boundaries + topic shift)
├── Slack threads: Entire thread as one chunk (with metadata)
├── Code: Function-level + file-level summary chunks
├── Jira tickets: Title+Description as one chunk, comments separate
└── Target: 200-500 tokens per chunk, overlap 50 tokens

Embedding:
├── Model: text-embedding-3-small (cost) or text-embedding-3-large (quality)
├── Batch processing: GPU cluster, 10K chunks/minute
├── Incremental: New/modified docs only (content hash comparison)
└── Multi-vector: Title embedding + body embedding per chunk
```

### Retrieval Architecture (Modules 6, 7, 8)

```
Query Processing:
1. Intent classification → {factual, procedural, navigational, conversational}
2. Query expansion → Add synonyms, acronyms from company glossary
3. Hypothetical document embedding (HyDE) for ambiguous queries

Hybrid Search:
├── Vector search: Top-50 from Pinecone (cosine similarity)
├── Keyword search: Top-50 from Elasticsearch (BM25)
├── Fusion: Reciprocal Rank Fusion (RRF) → Top-30
└── Reranking: Cross-encoder (ms-marco-MiniLM) → Top-10

Access Control (CRITICAL):
├── Pre-filter: ACL tags in vector metadata → filter at search time
├── Post-filter: Verify user access against permission graph
├── Never cache across users (ACL-aware cache keys)
└── Audit log every document access
```

### Agent Architecture (Modules 12, 13, 14)

```
Query Planning:
├── Simple factual → Single retrieval + generation
├── Multi-hop → Decompose into sub-queries, merge results
├── Aggregation → "How many tickets filed last week?" → SQL tool
├── Navigation → "Link to the onboarding doc" → Search + return link
└── Abstention → Low confidence or sensitive topic → "I don't know" + suggest human

Tool Selection:
├── search_documents(query, filters) → Vector/keyword search
├── search_people(name) → Org chart lookup
├── query_analytics(sql) → Read-only Jira/metrics queries
├── get_recent_slack(channel, days) → Slack search
└── escalate_to_human(reason) → Create support ticket

Confidence Scoring:
├── Retrieval confidence: Max similarity score of top results
├── Generation confidence: Token-level probability analysis
├── Calibration: If confidence < 0.6, add disclaimer
└── If confidence < 0.3, abstain entirely
```

### Security Architecture (Modules 20, 21, 22)

```
Authentication:
├── SSO via SAML/OIDC (Okta, Azure AD)
├── Service accounts for API access (JWT with short TTL)
└── Session management: 8-hour sliding window

Guardrails:
├── Input: PII detection, prompt injection detection, topic filter
├── Output: PII redaction, hallucination check (cite or abstain)
├── Content policy: No medical/legal advice, no HR decisions
└── Rate limiting: 100 queries/user/hour, 10K queries/org/day

Audit:
├── Every query logged with: user, intent, sources accessed, response
├── Every document access logged for compliance
├── 90-day retention, exportable for SOC2 audits
└── Anomaly detection: Unusual access patterns → alert security team
```

## 1.4 Data Flow (Single Query)

```
1. User asks: "What's our PTO policy for remote employees?"
2. API Gateway: Authenticate (JWT), extract tenant_id, rate check
3. Query Planner: Intent=factual, no decomposition needed
4. Query Rewrite: "PTO policy remote employees" + "paid time off work from home"
5. Hybrid Search:
   - Vector: embed query → search Pinecone (filter: tenant=acme, user_acl∋user_groups)
   - Keyword: BM25 search Elasticsearch (same filters)
   - Fuse: RRF top-30
6. Rerank: Cross-encoder scores top-30 → top-5
7. ACL Post-filter: Verify user can access each document (permission graph)
8. Context Assembly: Format top-5 chunks with source metadata
9. LLM Generation: GPT-4o-mini with system prompt + context + query
   - System: "Answer using only the provided context. Cite sources. Say I don't know if unsure."
10. Post-processing: Extract citations, check for PII, confidence score
11. Response: Stream answer with citations + confidence indicator
12. Logging: Trace to Langfuse, metrics to Prometheus
```

## 1.5 Scaling Plan

```
Phase 1 (100 users):
├── Single region, managed services (Pinecone Serverless, OpenAI API)
├── Monthly cost: ~$2K (embeddings $200, LLM $1K, infra $800)
└── Team: 2 engineers

Phase 2 (10K users):
├── Add caching layer (80% cache hit rate for common queries)
├── Move to dedicated vector DB instances
├── Add query routing: simple→GPT-4o-mini, complex→GPT-4o
├── Monthly cost: ~$15K
└── Team: 5 engineers

Phase 3 (100K users):
├── Multi-region deployment
├── Self-hosted embedding model (reduce API costs 90%)
├── Tiered storage: hot (recent) in vector DB, warm in S3+reindex on demand
├── Monthly cost: ~$80K
└── Team: 12 engineers (platform + product)
```

## 1.6 Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| LLM provider outage | No answers | Fallback to cached answers + "degraded mode" with search-only |
| Vector DB slow | High latency | Cache warm queries, circuit breaker at 5s, return keyword-only results |
| Stale index | Wrong answers | Freshness indicator in UI, force re-index button, staleness alerts |
| ACL sync lag | Data leak risk | Conservative: deny access if ACL status unknown, async reconciliation |
| Embedding drift | Quality degradation | Weekly eval on golden set, alert if accuracy drops >5% |
| Cost spike | Budget blown | Per-user rate limits, query complexity caps, kill switch for expensive models |

## 1.7 Cost Estimate (Per Query)

```
Average query cost breakdown:
├── Embedding (query):     $0.000013  (text-embedding-3-small)
├── Vector search:         $0.0001    (Pinecone serverless)
├── Reranking:            $0.001     (cross-encoder inference)
├── LLM generation:       $0.003     (GPT-4o-mini, ~1K input + 300 output tokens)
├── Infrastructure:       $0.001     (compute, networking, storage amortized)
└── Total:                ~$0.005/query (with 80% cache hit → $0.001 effective)

Monthly at 100K users (avg 20 queries/user/day):
├── 2M queries/day × 30 = 60M queries/month
├── Effective cost: 60M × $0.001 = $60K/month
├── + Fixed infra: $20K/month
└── Total: ~$80K/month
```

## 1.8 Evaluation Architecture (Modules 30, 31, 32)

```
Offline Evaluation:
├── Golden dataset: 500 curated Q&A pairs with ground-truth sources
├── Metrics: Answer correctness, citation accuracy, retrieval recall@10
├── Run weekly, block deployment if accuracy drops >3%
└── Slice by: query type, source type, department

Online Evaluation:
├── Thumbs up/down on every response (target: >80% positive)
├── Click-through on citations (measures source quality)
├── Reformulation rate (user rephrases = answer was bad)
├── Escalation rate (user clicked "ask a human")
└── Time-to-resolution comparison vs pre-AI baseline

Drift Detection:
├── Monitor embedding distribution shift (new vocabulary)
├── Monitor query pattern changes (new topics)
├── Alert if unanswered-query rate exceeds 15%
└── Quarterly: refresh golden set with new edge cases
```

---

# Design 2: AI-Powered Code Review System (CodeRabbit-style)

## 2.1 Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Integration | Git platforms | GitHub, GitLab, Bitbucket |
| Latency | Review posted | < 5 minutes after PR opened |
| Precision | False positive rate | < 10% (comments that are wrong/unhelpful) |
| Recall | Catch rate | > 60% of issues human reviewers find |
| Scale | PRs/day | 10K+ across all customers |
| Context | Understanding | Full repo context, not just diff |
| Safety | Never approve | System should suggest, never auto-merge |

## 2.2 Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                    GITHUB/GITLAB INTEGRATION                            │
│  Webhook Receiver │ App Installation │ Comment API │ Status Checks     │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ PR Opened/Updated Event
                               ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                                  │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │
│  │ PR Parser   │  │ Context     │  │ Review       │                   │
│  │             │  │ Assembler   │  │ Orchestrator │                   │
│  │ Diff extract│  │             │  │              │                   │
│  │ File tree   │  │ Repo index  │  │ Multi-pass   │                   │
│  │ Metadata    │  │ Related code│  │ Aggregation  │                   │
│  └─────────────┘  └─────────────┘  └─────────────┘                   │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ FAST CHECKS  │ │ DEEP ANALYSIS│ │ SUMMARY GEN      │
│ (GPT-4o-mini)│ │ (Claude/GPT4)│ │ (GPT-4o-mini)    │
│              │ │              │ │                  │
│ Style issues │ │ Logic bugs   │ │ PR summary       │
│ Naming       │ │ Race conds   │ │ Risk assessment  │
│ Simple bugs  │ │ Security     │ │ Review priority  │
│ Doc coverage │ │ Architecture │ │ Suggested tests  │
└──────────────┘ └──────────────┘ └──────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    QUALITY CONTROL                                      │
│  Confidence Filter │ Dedup │ Priority Sort │ Human Feedback Loop       │
└───────────────────────────────────────────────────────────────────────┘
```

## 2.3 Multi-Model Strategy

```
Tier 1 — Fast Model (GPT-4o-mini): Cost $0.001/PR-file
├── Linting-style checks (naming, formatting consistency)
├── Documentation coverage (missing docstrings)
├── Simple bug patterns (null checks, off-by-one)
├── Runs on EVERY file in the diff
└── Latency: <10s per file

Tier 2 — Frontier Model (Claude Sonnet/GPT-4o): Cost $0.05/PR-file
├── Complex logic analysis (race conditions, state management)
├── Security vulnerability detection
├── Architecture review (coupling, abstraction leaks)
├── Runs on files flagged as "complex" by Tier 1 or >100 lines changed
└── Latency: 30-60s per file

Tier 3 — Holistic Review (Claude Opus/GPT-4o): Cost $0.10/PR
├── Cross-file analysis (breaking changes, API contract violations)
├── Overall PR summary and risk assessment
├── Suggested tests based on change impact
├── Runs once per PR with full context
└── Latency: 60-120s per PR
```

## 2.4 Context Assembly

```
For each file in diff:
1. The diff itself (changed lines with surrounding context)
2. Full file content (pre and post change)
3. Related files: imports, callers, interfaces (from code graph)
4. Recent git history for the file (who changed what recently)
5. PR description and linked issues
6. Team's style guide / .editorconfig / linting rules
7. Previous review comments on this PR (avoid contradictions)

Context budget per model call:
├── Fast model: 8K tokens (diff + file + rules)
├── Deep model: 32K tokens (diff + file + related + history)
└── Holistic: 128K tokens (all files + PR desc + full context)
```

## 2.5 Quality Control Pipeline

```
Before posting a comment:
1. Confidence check: Model self-rates confidence [1-5]
   - Score < 3 → suppress comment
   - Score 3-4 → post as "suggestion" (softer language)
   - Score 5 → post as "issue" (stronger language)

2. Deduplication: Embedding similarity with existing comments
   - If >0.9 similarity with another comment → merge or drop

3. False positive filtering:
   - Known false positive patterns (from user feedback history)
   - Language-specific exceptions (e.g., Go error handling style)
   - Team preferences (loaded from config)

4. Priority sorting:
   - Security/correctness → post immediately
   - Style/improvement → batch and post as single review
   - Nitpicks → only if < 5 total comments (avoid noise)
```

## 2.6 Feedback Loop

```
User Actions:
├── 👍 on comment → Positive signal (store for fine-tuning)
├── 👎 on comment → False positive (add to suppression patterns)
├── "Resolve" without change → Likely false positive
├── Code changed matching suggestion → True positive
└── Configuration: "Don't flag X for this repo" → Update rules

Metrics:
├── Acceptance rate: % of comments that led to code changes (target >40%)
├── False positive rate: % of 👎 reactions (target <10%)
├── Coverage: % of human-found issues also caught by AI (target >60%)
├── Time saved: Avg hours between PR open and first human review (should decrease)
└── Developer satisfaction: Quarterly survey (target >4/5)
```

## 2.7 Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| LLM hallucination | Wrong suggestion | Confidence filter + never auto-apply |
| Context overflow | Miss cross-file bugs | Prioritize most relevant context, flag "limited context" |
| Noisy reviews | Developer fatigue | Strict confidence threshold, respect mute settings |
| Webhook failure | Missed PRs | Periodic polling as backup, dead letter queue |
| Rate limit (GitHub API) | Can't post comments | Queue + exponential backoff, batch comments |

## 2.8 Cost Model

```
Per-PR cost (average 8 files changed):
├── Fast checks (8 files × $0.001):    $0.008
├── Deep analysis (3 complex files × $0.05): $0.15
├── Holistic review (1 × $0.10):       $0.10
├── Embedding/indexing:                  $0.01
└── Total per PR:                        ~$0.27

At 10K PRs/day: $2,700/day → $81K/month
Revenue model: $20/developer/month → 4,000 developers to break even
```

---

# Design 3: Conversational AI for Banking (Erica-style)

## 3.1 Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Compliance | Regulatory | SOX, PCI-DSS, FFIEC, state banking laws |
| Actions | Read-only | Balance, transactions, statements |
| Actions | Write | Transfers (with 2FA), bill pay, card lock |
| Safety | What it CANNOT do | Investment advice, loan decisions, dispute resolution |
| Latency | Response time | < 3s for read, < 5s for write actions |
| Availability | Uptime | 99.99% (banking-grade) |
| Languages | Support | English + Spanish (US market) |
| Memory | Context | Full conversation history + last 90 days activity |

## 3.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                                      │
│  [Mobile App] [Web Banking] [SMS] [Voice (IVR)]                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ (TLS 1.3, Certificate Pinning)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SECURITY GATEWAY                                    │
│  mTLS │ OAuth2 │ Device Fingerprint │ Fraud Scoring │ WAF           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 CONVERSATION MANAGER                                   │
│                                                                         │
│  Session State │ Turn History │ Intent Router │ Escalation Engine     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │              COMPLIANCE LAYER (wraps every action)            │     │
│  │  ├── Input guard: Block prompt injection, social engineering │     │
│  │  ├── Output guard: No financial advice, no PII in logs      │     │
│  │  ├── Action guard: Transaction limits, velocity checks       │     │
│  │  └── Audit: Every interaction logged to immutable store      │     │
│  └─────────────────────────────────────────────────────────────┘     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ READ ACTIONS     │ │ WRITE ACTIONS    │ │ KNOWLEDGE QA     │
│                  │ │                  │ │                  │
│ Balance inquiry  │ │ Transfer funds   │ │ "What's APR?"    │
│ Transaction list │ │ Pay bills        │ │ "Branch hours?"  │
│ Statement DL     │ │ Lock/unlock card │ │ "How do I..."    │
│ Spending summary │ │ Update alerts    │ │                  │
│                  │ │                  │ │ RAG over bank    │
│ Auth: Session    │ │ Auth: Step-up    │ │ knowledge base   │
│ Latency: <1s    │ │ (2FA + confirm)  │ │                  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
              │                  │                  │
              ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CORE BANKING APIs                                   │
│  Account Service │ Payment Service │ Card Service │ Notification Svc │
└─────────────────────────────────────────────────────────────────────┘
```

## 3.3 Compliance-First Design

```
CANNOT DO (hard blocks, no exceptions):
├── Provide investment advice ("You should buy/sell...")
├── Make loan/credit decisions
├── Resolve disputes (must escalate)
├── Share other customers' information
├── Discuss internal bank policies/procedures in detail
├── Process transactions above $10K without human approval
└── Continue conversation if fraud signals detected

MUST DO (regulatory requirements):
├── Identify as AI in every conversation start
├── Offer human escalation at any point
├── Provide Reg E disclosures for error claims
├── Log all interactions for 7-year retention
├── Support accessibility (screen reader compatible)
└── Provide Spanish option when requested

GUARDRAIL IMPLEMENTATION:
├── Pre-prompt: Constitutional AI instructions baked into system prompt
├── Input classifier: Fine-tuned model detects social engineering attempts
├── Output validator: Regex + LLM-judge checks every response before sending
├── Action validator: All write actions go through dual-approval system
└── Kill switch: Compliance team can disable any capability instantly
```

## 3.4 Multi-Turn Memory Architecture

```
Session Memory (Redis):
├── Current conversation turns (last 20 messages)
├── Active intent and slot-filling state
├── Pending confirmations (e.g., "Transfer $500 to Mom?")
└── TTL: 30 minutes of inactivity

User Memory (PostgreSQL):
├── Conversation summaries (last 10 conversations)
├── Preferences (preferred name, notification settings)
├── Frequent actions (payees, typical transfer amounts)
├── Last 90 days transaction summary (precomputed)
└── Stored encrypted at rest, access-logged

Context Assembly per Turn:
1. System prompt (compliance rules, persona, capabilities)
2. User profile summary (from User Memory)
3. Current session history (from Session Memory)
4. Retrieved context (if knowledge QA)
5. Available actions (based on auth level and account type)
```

## 3.5 Escalation to Human

```
Escalation Triggers:
├── User explicitly requests human agent
├── Sentiment analysis detects frustration (3+ negative turns)
├── Compliance topic detected (dispute, complaint, legal)
├── System confidence < 0.4 for 2+ consecutive turns
├── Transaction requires manual approval
└── Fraud signals detected

Context Transfer Package:
├── Full conversation transcript
├── Detected intent and entities
├── Actions already taken / attempted
├── Customer profile summary
├── Recommended resolution (for human agent)
├── Priority level (1-5 based on customer tier + issue severity)
└── Format: Structured JSON → rendered in agent desktop

SLA After Escalation:
├── Priority 1 (fraud): Immediate connection (<30s)
├── Priority 2 (complaint): <2 minutes
├── Priority 3 (complex query): <5 minutes
├── Priority 4 (preference): <10 minutes (or callback)
└── Always offer: "Would you like a callback instead of waiting?"
```

## 3.6 Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| LLM returns financial advice | Regulatory violation | Output classifier blocks + incident report |
| Core banking API timeout | Can't show balance | Cached last-known balance + "as of X" disclaimer |
| Session state lost | User repeats themselves | Persist to Redis cluster with replication |
| Fraud detection false positive | Legitimate user blocked | Quick escalation path, SMS verification bypass |
| Model hallucination about account | Trust damage | Never fabricate; only display verified API data |
| Complete AI system failure | No self-service | Graceful fallback to IVR menu + human queue |

## 3.7 Cost Model

```
Per-conversation cost (avg 6 turns):
├── LLM (GPT-4o-mini, 6 turns × 2K tokens): $0.006
├── Guardrail checks (input+output × 6):     $0.003
├── API calls to core banking:                $0.001
├── Infrastructure (per-conversation share):  $0.002
└── Total: ~$0.012/conversation

Comparison: Human agent call costs $7-12
AI handles 80% of queries → Deflection saves: $5.60-$9.60 per deflected call
At 1M conversations/month: $12K AI cost vs $7M human cost (for those queries)
```

---

# Design 4: AI Content Moderation at Scale (YouTube/TikTok-style)

## 4.1 Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Volume | Items/day | 5M+ uploads (text, image, video, audio) |
| Latency | Real-time path | < 500ms for upload-blocking decisions |
| Latency | Batch path | < 4 hours for backlog scanning |
| Accuracy | Precision (CSAM) | > 99.9% (near-zero false negatives) |
| Accuracy | Precision (hate speech) | > 85% (balance free speech) |
| Scale | Concurrent processing | 50K items/minute peak |
| Appeals | Resolution time | < 24 hours with human review |
| Coverage | Modalities | Text, image, video, audio, live stream |

## 4.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     UPLOAD PIPELINE                                    │
│  CDN Ingest │ Format Validation │ Dedup (perceptual hash) │ Queue   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ REAL-TIME PATH   │ │ ASYNC PATH       │ │ PERIODIC RESCAN  │
│ (< 500ms)        │ │ (< 4 hours)      │ │ (policy updates) │
│                  │ │                  │ │                  │
│ ML classifiers   │ │ LLM deep review  │ │ Re-evaluate old  │
│ Hash matching    │ │ Context analysis │ │ content against  │
│ Rule engine      │ │ Multi-modal      │ │ new policies     │
│                  │ │ Cross-reference  │ │                  │
│ Decision:        │ │ Decision:        │ │ Decision:        │
│ ALLOW/BLOCK/HOLD │ │ ALLOW/REMOVE/ESC │ │ REMOVE/FLAG      │
└──────────────────┘ └──────────────────┘ └──────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HUMAN REVIEW QUEUE                                  │
│                                                                         │
│  Priority Queue │ Specialist Routing │ Consensus (2-of-3) │ QA       │
│                                                                         │
│  CSAM → Dedicated team (mandatory report to NCMEC)                    │
│  Terrorism → Specialist reviewers + law enforcement API               │
│  Hate speech → Cultural context reviewers (region-specific)           │
│  Appeals → Different reviewer than original decision                  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FEEDBACK & RETRAINING                               │
│  Human labels → Active learning → Model retraining (weekly)          │
│  Appeal outcomes → Policy refinement → Rule engine updates           │
│  False positive analysis → Threshold tuning per category             │
└─────────────────────────────────────────────────────────────────────┘
```

## 4.3 Multi-Modal Processing

```
TEXT MODERATION:
├── Fast path: Keyword blocklist + regex patterns (< 10ms)
├── ML classifier: Fine-tuned BERT for toxicity (< 50ms)
├── LLM analysis: Context-aware for sarcasm, coded language (async, < 5s)
└── Language support: 50+ languages, auto-detect

IMAGE MODERATION:
├── Perceptual hash: Match against known-bad database (PhotoDNA) (< 20ms)
├── NSFW classifier: CNN-based, multi-label (nudity, violence, gore) (< 100ms)
├── OCR + text moderation: Extract text from images (< 200ms)
├── Object detection: Weapons, drugs, symbols (< 150ms)
└── Deepfake detection: Face manipulation score (async)

VIDEO MODERATION:
├── Keyframe extraction: 1 frame/second for short, 1/10s for long (< 1s)
├── Apply image pipeline to keyframes (parallelized)
├── Audio extraction → speech-to-text → text moderation
├── Scene classification: Violence timeline, NSFW segments
└── Full video analysis: Only for flagged content (expensive)

AUDIO MODERATION:
├── Speech-to-text (Whisper) → text moderation pipeline
├── Audio classifier: Gunshots, screaming, hate speech tone
├── Music identification: Copyright + explicit content flags
└── Voice cloning detection: Speaker verification models
```

## 4.4 Decision Framework

```
Category-specific thresholds:

CSAM / Child Safety:
├── Threshold: 0.001 (block at smallest suspicion)
├── False negatives: UNACCEPTABLE (mandatory reporting)
├── False positives: Acceptable (human review clears quickly)
└── Action: Immediate block + report to NCMEC + account suspension

Terrorism / Extremism:
├── Threshold: 0.3 (aggressive blocking)
├── Appeal path: Yes, with human review
└── Action: Remove + flag account + report to authorities if credible threat

Hate Speech:
├── Threshold: 0.7 (balance with free expression)
├── Context matters: News reporting vs. promoting hatred
├── Region-specific: Different standards per jurisdiction
└── Action: Remove or reduce distribution + warning to creator

Spam / Scam:
├── Threshold: 0.8 (high precision to avoid false blocks on legitimate content)
├── Action: Shadow-ban (reduce reach) rather than hard block
└── Appeal: Automated re-review after 24h

Misinformation:
├── Threshold: N/A (don't block, add context)
├── Action: Add information label + reduce algorithmic amplification
└── Fact-check partnership for trending claims
```

## 4.5 Scaling Architecture

```
Processing Pipeline (Kafka-based):
├── Upload events → Kafka topic (partitioned by content_type)
├── Real-time consumers: 500 pods, auto-scale on lag
├── Async consumers: 200 pods, scale on queue depth
├── GPU pool: 100 A100s for image/video inference (spot instances for batch)
└── Peak handling: 50K items/minute (burst to 100K with auto-scale)

Storage:
├── Content store: S3 with lifecycle policies (move to Glacier after 90 days)
├── Decision store: DynamoDB (content_id → decision + metadata)
├── Hash database: 500M+ hashes, Redis cluster for fast lookup
├── Model registry: MLflow with A/B testing support
└── Audit log: Immutable append-only store (legal hold capable)

Cost at Scale (5M items/day):
├── GPU inference: $50K/month (spot pricing)
├── LLM calls (async deep review, 10% of items): $30K/month
├── Human review (5% escalation, $0.10/review): $75K/month
├── Storage + compute: $40K/month
└── Total: ~$195K/month for 5M items/day → $0.0013/item
```

## 4.6 Appeal Process

```
User submits appeal:
1. Auto-review: Re-run moderation with lower thresholds + more context
   - If clearly wrong → auto-reinstate (saves human review cost)
   - If borderline → route to human
2. Human review: Different reviewer than original (avoid confirmation bias)
   - Provide: Original content, decision reason, policy reference, user history
   - Reviewer decides: Uphold / Overturn / Escalate to senior
3. Senior review: For edge cases, policy team weighs in
4. Outcome: Notify user with specific policy explanation
5. Feedback loop: Appeal outcomes retrain models (active learning)

SLA: 90% of appeals resolved within 24 hours
Target overturn rate: 10-15% (too low = model too aggressive, too high = model broken)
```

---

# Design 5: Internal AI Platform (Platform-as-a-Product)

## 5.1 Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Users | Product teams | 20 teams, 200+ developers |
| Models | Supported | OpenAI, Anthropic, Google, self-hosted OSS |
| Governance | Controls | Prompt review, cost caps, PII guardrails |
| Self-service | Onboarding | New team productive in < 1 day |
| Cost | Visibility | Per-team, per-feature cost attribution |
| SLA | Platform uptime | 99.9% for proxy, 99.5% for tooling |
| Scale | Requests | 10M LLM calls/month across all teams |

## 5.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PRODUCT TEAMS                                       │
│  Team A: Search │ Team B: Support │ Team C: Content │ ... Team N     │
│                                                                         │
│  Each team uses: SDK │ Playground │ Dashboard │ CI/CD Hooks           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ (Platform SDK / API)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AI GATEWAY (Core Platform)                          │
│                                                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │
│  │ Auth &  │ │ Rate    │ │ Cost    │ │ Guard-  │ │ Routing │      │
│  │ Tenant  │ │ Limiting│ │ Control │ │ rails   │ │ Engine  │      │
│  │ ID      │ │         │ │         │ │         │ │         │      │
│  │ API keys│ │ Per-team│ │ Budget  │ │ PII     │ │ Model   │      │
│  │ Scoping │ │ Per-user│ │ alerts  │ │ Toxicity│ │ Select  │      │
│  │         │ │ Per-min │ │ Kill sw │ │ Injection│ │ Fallback│      │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │                    OBSERVABILITY                              │     │
│  │  Request logs │ Traces │ Metrics │ Cost attribution │ Alerts │     │
│  └─────────────────────────────────────────────────────────────┘     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ MODEL PROVIDERS  │ │ SELF-HOSTED      │ │ PLATFORM SERVICES│
│                  │ │                  │ │                  │
│ OpenAI API      │ │ vLLM cluster     │ │ Prompt Registry  │
│ Anthropic API   │ │ (Llama, Mistral) │ │ Tool Registry    │
│ Google AI       │ │                  │ │ Eval Framework   │
│ Azure OpenAI    │ │ GPU: 8×A100     │ │ Vector DB (shared│
│                  │ │ Auto-scale      │ │ RAG infra)       │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

## 5.3 Registry System

```
MODEL REGISTRY:
├── Catalog: All available models with capabilities, pricing, latency stats
├── Versioning: Model versions pinned per team (opt-in to upgrades)
├── Deprecation: 30-day notice before model retirement
├── Benchmarks: Internal eval scores updated weekly
└── Access control: Some models restricted (e.g., GPT-4o only for approved use cases)

PROMPT REGISTRY:
├── Version control: Git-backed, PR review for production prompts
├── Templates: Parameterized prompts with variable injection
├── A/B testing: Deploy multiple prompt versions, measure performance
├── Sharing: Teams can publish prompts for org-wide reuse
├── Compliance review: Auto-flag prompts that bypass guardrails
└── Rollback: Instant revert to previous prompt version

TOOL REGISTRY:
├── Catalog: All available tools/functions with schemas
├── Shared tools: Company-wide (e.g., search_docs, get_user_info)
├── Team tools: Team-specific integrations
├── Approval flow: New tools require security review before production
├── Usage metrics: Which tools are called how often by which teams
└── Deprecation: Usage alerts before removing tools
```

## 5.4 Cost Management

```
ALLOCATION MODEL:
├── Per-request tagging: team_id, feature_id, environment, model, tokens
├── Real-time dashboard: Current spend vs budget (per team)
├── Alerts: 50%, 75%, 90%, 100% of monthly budget
├── Hard cap: Requests rejected above budget (configurable per team)
└── Chargeback: Monthly cost report to team's cost center

OPTIMIZATION STRATEGIES (platform provides):
├── Caching: Semantic cache (same question → same answer, save $$$)
│   └── Cache hit rate across platform: ~30% (saves $50K/month)
├── Model routing: Auto-select cheapest model that meets quality threshold
│   └── "Use GPT-4o-mini unless quality score drops below X"
├── Prompt optimization: Auto-compress prompts (remove redundancy)
├── Batch API: Queue non-urgent requests for 50% discount
└── Self-hosted fallback: Route overflow to vLLM (fixed cost vs per-token)

MONTHLY COST BREAKDOWN (example):
├── OpenAI API: $120K (GPT-4o: $80K, GPT-4o-mini: $30K, embeddings: $10K)
├── Anthropic API: $40K (Claude for long-context use cases)
├── Self-hosted GPU: $25K (8×A100 on-demand)
├── Platform infra: $15K (gateway, observability, registries)
├── Total: $200K/month for 10M requests
├── Effective cost: $0.02/request average
└── Without platform optimizations: would be $300K (33% savings)
```

## 5.5 Governance Model

```
TEAM ONBOARDING:
1. Request access → Auto-provisioned: API key, sandbox, $500 budget
2. Complete security training (30-min module on AI safety)
3. Submit use case description for classification:
   - Tier 1 (low risk): Internal tools, summarization → auto-approved
   - Tier 2 (medium risk): Customer-facing, content gen → 1 reviewer
   - Tier 3 (high risk): Financial, medical, legal → full review board
4. Choose models, configure guardrails, deploy to staging
5. Production deployment requires: eval results + guardrail config + incident runbook

GUARDRAIL TIERS:
├── Platform-wide (mandatory, cannot disable):
│   ├── PII detection and masking in logs
│   ├── Prompt injection detection
│   ├── Request/response size limits
│   └── Cost caps
├── Team-configurable:
│   ├── Content policy strictness (1-5)
│   ├── Custom blocklists/allowlists
│   ├── Output format validation
│   └── Confidence thresholds
└── Feature-specific:
    ├── Per-endpoint rate limits
    ├── Model restrictions
    └── Custom validators
```

## 5.6 Platform SLOs vs Product SLOs

```
PLATFORM SLOs (what AI platform team guarantees):
├── Availability: 99.9% (gateway accepts requests)
├── Latency overhead: < 50ms added by gateway (p99)
├── Cost accuracy: Billing within 5% of actual
├── Guardrail latency: < 100ms per check
└── Incident response: Page within 5min, update within 30min

PRODUCT SLOs (what product teams own):
├── End-to-end latency (includes model inference time)
├── Answer quality (measured by team's eval framework)
├── Error rate (retries, timeouts, model errors)
└── User satisfaction (team measures independently)

BOUNDARY: Platform guarantees the pipe works. Product teams own the quality of what flows through it.

SHARED RESPONSIBILITY:
├── Platform provides: Monitoring dashboards, alerting templates, eval framework
├── Product teams provide: Golden datasets, quality thresholds, incident runbooks
└── Joint: Capacity planning (teams forecast, platform provisions)
```

## 5.7 Failure Modes

| Failure | Impact | Platform Response |
|---------|--------|-------------------|
| OpenAI outage | All dependent teams blocked | Auto-failover to Azure OpenAI or Anthropic |
| Cost spike (runaway loop) | Budget blown in minutes | Circuit breaker: kill after 10x normal rate |
| PII leak in logs | Compliance violation | Auto-redaction + incident, rotate API keys |
| Model quality regression | All teams affected | Pin model versions, alert on eval score drop |
| Platform gateway down | All AI features down | Multi-AZ deployment, fallback to direct API (bypass) |
| New model release breaks prompts | Silent quality degradation | Version pinning, require explicit opt-in to new models |

---

## Cross-Design Patterns

These patterns appear across ALL five designs:

### Pattern 1: Layered Quality Control
```
Every system has multiple quality gates:
Input → Validate → Process → Validate → Output → Monitor → Feedback
```

### Pattern 2: Graceful Degradation
```
Full service → Reduced quality → Cached results → Static fallback → Error page
Never let users see a blank screen or unhandled error.
```

### Pattern 3: Cost-Aware Routing
```
Simple requests → Cheap model (80% of traffic)
Complex requests → Expensive model (20% of traffic)
Result: 60% cost reduction vs using expensive model for everything
```

### Pattern 4: Human-in-the-Loop Escape Hatch
```
Every AI system needs a path to a human:
- Explicit: User requests human
- Implicit: System detects low confidence
- Mandatory: High-stakes decisions always require human approval
```

### Pattern 5: Evaluation as Infrastructure
```
Not an afterthought. Built into the system from day 1:
- Offline evals gate deployments
- Online evals detect drift
- User feedback closes the loop
- Golden datasets grow continuously
```

---

## Module Cross-Reference

| Component | Relevant Modules |
|-----------|-----------------|
| Data ingestion & chunking | 3, 4, 5 |
| Embedding & vector search | 6, 7, 8 |
| Hybrid retrieval & reranking | 9, 10 |
| Agent architecture | 12, 13, 14, 15 |
| Tool use & function calling | 16, 17 |
| Memory & context management | 18, 19 |
| Security & guardrails | 20, 21, 22 |
| Deployment & scaling | 23, 24, 25 |
| Observability & monitoring | 26, 27 |
| Evaluation & testing | 30, 31, 32 |
| Cost optimization | 33, 34 |
| Multi-model routing | 35 |
| Interview preparation | 36, 37 |
| Production hardening | 38, 39 |

---

## Summary

These five designs represent the most common AI system design interview questions. Each exercises different muscles:

1. **Knowledge Assistant** → RAG mastery, access control, scaling
2. **Code Review** → Multi-model strategy, quality control, developer UX
3. **Banking AI** → Compliance-first design, action safety, escalation
4. **Content Moderation** → Scale, multi-modal, precision/recall tradeoffs
5. **AI Platform** → Platform thinking, governance, cost management

Master all five and you can handle any AI system design interview.
