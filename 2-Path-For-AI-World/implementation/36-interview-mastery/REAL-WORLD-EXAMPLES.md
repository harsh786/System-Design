# Interview Mastery — Real-World Examples

## Complete AI System Design Interview Answers

---

## Question 1: "Design a RAG-based customer support system for an e-commerce company"

### 45-Minute Answer Structure

**Minutes 0-5: Requirements Clarification**
```
Questions to ask:
- Scale: How many queries/day? → "50K queries/day, 200 concurrent"
- Scope: Just product questions or orders, returns, policies too? → "All of the above"
- Languages: → "English + Spanish, 80/20 split"  
- Latency: → "P95 <4s for first token"
- Sources: Product catalog, FAQ, order history, policy docs, past ticket resolutions
- Success: How do we measure? → "Deflection rate, CSAT, escalation rate"
```

**Minutes 5-15: High-Level Architecture**

Draw this on the whiteboard:
```
User Query → API Gateway → Query Processing → Retrieval → Generation → Response
                                                    ↑
                              ┌──────────────────────┤
                              ↓                      ↓
                        Vector Store          Structured DB
                        (products, FAQ,       (orders, returns,
                         policies)             account info)
```

Key design decisions to articulate:
1. **Hybrid retrieval**: Semantic search for product/policy questions, structured lookup for order status
2. **Query classification first**: Route to different pipelines based on intent (order status = DB lookup, product question = RAG, complaint = agent escalation)
3. **Personalization**: Customer's order history as context for relevant answers

**Minutes 15-30: Component Deep-Dive**

```
Query Classifier (fast, cheap model like GPT-3.5):
├── Order/Account queries → Structured pipeline
│   └── SQL lookup → Template response → Personalize
├── Product questions → RAG pipeline
│   └── Embed → Retrieve (catalog + reviews) → Generate with citations
├── Policy questions → RAG pipeline (different index)
│   └── Embed → Retrieve (policy docs) → Generate with exact quotes
└── Complaints/Complex → Escalation
    └── Summarize context → Route to human agent with AI-prepared brief
```

Retrieval design:
- **Product index**: Embed product descriptions, specs, reviews. Metadata filter by category, price range, availability.
- **Policy index**: Chunk by policy section. Include effective dates in metadata.
- **Resolution index**: Past successful ticket resolutions as few-shot examples.

Generation design:
- System prompt enforces: cite sources, don't make promises, don't invent policies
- Include customer's order info when relevant (personalization)
- Confidence scoring: if retrieval scores are low, say "I'm not sure" and offer human agent

**Minutes 30-40: Evaluation, Monitoring, Edge Cases**

Metrics:
| Metric | Target | How Measured |
|--------|--------|--------------|
| Deflection rate | 65% | Tickets not escalated to human |
| CSAT for AI responses | 4.0/5 | Post-interaction survey |
| Groundedness | >92% | Weekly NLI audit on sample |
| Hallucinated policy | 0% | Automated policy claim checker |
| P95 latency | <4s | APM monitoring |

Edge cases:
- Customer asks about competitor products → Deflect gracefully
- Product recalled → Priority override with safety message
- Customer threatens legal action → Immediate escalation, don't engage
- Ambiguous query → Ask clarifying question (max 1 follow-up)

**Minutes 40-45: Scaling & Cost**

Cost model at 50K queries/day:
- Embedding queries: $50/day (ada-002)
- Classification (GPT-3.5): $30/day
- Generation (GPT-4o): $400/day (complex) + $100/day (GPT-3.5 for simple)
- Infrastructure: $200/day
- **Total: ~$780/day = $0.016/query**
- Compared to human agent: $8/ticket → Savings of $250K+/month at 65% deflection

**Scoring Rubric:**
| Dimension | Excellent (5) | Good (3) | Poor (1) |
|-----------|--------------|----------|----------|
| Requirements | Asked 5+ clarifying Qs, quantified targets | Asked a few Qs | Jumped to solution |
| Architecture | Clear separation of concerns, justified choices | Reasonable design | Monolithic/vague |
| Depth | Detailed retrieval + generation + eval | Covered basics | Surface-level only |
| Trade-offs | Articulated 3+ with reasoning | Mentioned some | No trade-offs |
| Production readiness | Monitoring, cost, failure modes | Some operational thinking | Just the happy path |

---

## Question 2: "How would you build an AI coding assistant like Cursor?"

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ IDE Extension (VS Code / Custom Editor)                          │
│ ┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐  │
│ │Tab Compl.│ │Inline Edit   │ │Chat Panel │ │Agent Mode    │  │
│ └────┬─────┘ └──────┬───────┘ └─────┬─────┘ └──────┬───────┘  │
└──────┼───────────────┼───────────────┼──────────────┼───────────┘
       │               │               │              │
       ▼               ▼               ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Context Engine (runs locally + server-side)                       │
│ - File context (open files, recent edits)                        │
│ - Repository context (tree-sitter AST, symbol index)             │
│ - Codebase search (embeddings of all files)                      │
│ - Git context (recent diffs, blame)                              │
│ - Language server (types, definitions, references)               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Inference Router                                                  │
│ - Tab completion → Fast model (speculative decoding, <200ms)     │
│ - Inline edit → Medium model (GPT-4o-mini, <2s)                  │
│ - Chat → Full model (Claude Sonnet/GPT-4o, <5s)                  │
│ - Agent → Full model + tool use (multi-turn, minutes)            │
└─────────────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**

1. **Context window management**: Most critical problem. You have 128K tokens but codebases have millions of lines. Solution: intelligent context selection.
   - Current file (always included)
   - Cursor position ± 100 lines (high priority)
   - Open tabs (medium priority)
   - Semantically similar files via embeddings (retrieved on demand)
   - Type definitions for referenced symbols (via LSP)

2. **Latency tiers**: Tab completion MUST be <200ms or users disable it. Use smallest model with speculative decoding. Chat can be 3-5s. Agent can take minutes.

3. **Codebase indexing**: On repo open, index all files with tree-sitter for AST, compute embeddings for semantic search. Incremental updates on file save.

4. **Evaluation**:
   - Tab completion: acceptance rate, characters saved, edit distance from accepted to final
   - Chat: user satisfaction rating, follow-up questions needed
   - Agent: task completion rate, files correctly modified, tests still passing

5. **Scaling**: User sessions are stateful (workspace context). Route same user to same inference server (sticky sessions). Pre-warm models for active users.

---

## Question 3: "Design a multi-agent system for automated financial report analysis"

### Key Architecture Decisions

```
Input: Quarterly earnings PDF (10-K, 10-Q, earnings call transcript)
Output: Structured analysis with confidence scores, compliance flags, audit trail

Agent Pipeline:
┌──────────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐
│ Document │ → │ Extraction   │ → │ Analysis       │ → │ Report       │
│ Parser   │   │ Agents       │   │ Agents         │   │ Generator    │
└──────────┘   └──────────────┘   └────────────────┘   └──────────────┘
                     │                    │                      │
                     ▼                    ▼                      ▼
              ┌────────────┐     ┌──────────────┐      ┌──────────────┐
              │ Revenue    │     │ Trend Agent  │      │ Compliance   │
              │ Extractor  │     │ (YoY, QoQ)  │      │ Checker      │
              │ COGS Agent │     │ Risk Agent   │      │ (SEC rules)  │
              │ Guidance   │     │ Sentiment    │      │ Audit Logger │
              │ Agent      │     │ Agent        │      └──────────────┘
              └────────────┘     └──────────────┘
```

**Confidence & Compliance Requirements:**

```python
class FinancialClaimConfidence:
    """Every numerical claim must have a confidence score and source."""
    
    levels = {
        "high": {
            "threshold": 0.95,
            "criteria": "Directly extracted from table/statement, cross-verified",
            "action": "Include in report without caveat"
        },
        "medium": {
            "threshold": 0.80,
            "criteria": "Extracted from text, single source, no cross-verification",
            "action": "Include with 'based on reported figures' qualifier"
        },
        "low": {
            "threshold": 0.60,
            "criteria": "Inferred or calculated, assumptions required",
            "action": "Include with explicit assumptions stated"
        },
        "insufficient": {
            "threshold": 0.0,
            "criteria": "Cannot verify from source documents",
            "action": "Exclude from report, flag for human review"
        }
    }
```

**Audit Trail Implementation:**

```python
@dataclass
class AuditEntry:
    timestamp: datetime
    agent_id: str
    action: str  # "extracted", "calculated", "inferred", "cross_verified"
    input_source: str  # Page number, table ID, section reference
    output_claim: str
    confidence: float
    reasoning: str  # Chain-of-thought reasoning preserved
    verified_by: Optional[str]  # Another agent that cross-checked

# Every output links back to source with full provenance chain
class AnalysisOutput:
    claim: str  # "Revenue grew 12% YoY to $4.2B"
    confidence: float  # 0.97
    sources: List[str]  # ["10-Q p.3 table 1", "earnings call transcript p.12"]
    audit_trail: List[AuditEntry]  # Full chain of how this was derived
    compliance_flags: List[str]  # Any regulatory concerns
```

---

## Question 4: "How would you scale an AI system from 1K to 1M users?"

### Progressive Architecture Evolution

**Stage 1: 1K users — Monolith**
```
Single server: FastAPI + in-memory cache + single LLM provider
- Direct OpenAI API calls
- SQLite for user data
- No queue, synchronous processing
- Cost: ~$500/month
- Latency: variable (depends on OpenAI)
```

**Stage 2: 10K users — Basic Scaling**
```
Changes:
- Add Redis cache (semantic cache, 30% hit rate saves cost)
- Move to PostgreSQL
- Add async job queue (Celery) for non-real-time tasks
- Add basic rate limiting per user
- Multiple API server replicas behind load balancer
- Cost: ~$5,000/month
```

**Stage 3: 100K users — Serious Infrastructure**
```
Changes:
- AI Gateway layer (routing, failover, cost management)
- Multi-provider: GPT-4o primary, Claude fallback, local models for simple tasks
- Dedicated vector DB cluster (Pinecone/Qdrant)
- Streaming responses (TTFT optimization)
- CDN for static assets, edge caching for common queries
- Horizontal auto-scaling based on queue depth
- Observability stack (traces, metrics, logs)
- Cost: ~$80,000/month
```

**Stage 4: 1M users — Platform Scale**
```
Changes:
- Multi-region deployment (latency optimization)
- Tiered model routing (80% use cheap model, 15% medium, 5% expensive)
- Custom fine-tuned models for high-volume use cases
- Batch inference for async workloads
- Sharded vector stores by tenant/domain
- Rate limiting with token budgets per user tier
- Real-time model performance monitoring with auto-rollback
- A/B testing infrastructure for model/prompt changes
- Cost: ~$500,000/month (but $0.50/user/month at scale)
```

**Key Scaling Principles:**
1. Cache aggressively (semantic similarity cache is uniquely powerful for AI)
2. Route queries to cheapest model that can handle them
3. Make everything async that doesn't need to be real-time
4. Shard by tenant/use-case for isolation and performance
5. Monitor cost per query as a first-class metric

---

## Question 5: "Design the security architecture for an enterprise AI platform"

### Defense in Depth Architecture

```
Layer 1: NETWORK
├── WAF (prompt injection patterns in rules)
├── DDoS protection
├── mTLS between all services
└── Private endpoints for LLM providers (Azure Private Link)

Layer 2: IDENTITY & ACCESS
├── Zero-trust: verify every request, no implicit trust
├── OAuth2 + SAML for user authentication
├── Service mesh with service-to-service auth (SPIFFE/SPIRE)
├── RBAC: who can use which models, which data sources
└── API key rotation (automated, 90-day maximum)

Layer 3: DATA PROTECTION
├── Encryption at rest (AES-256) and in transit (TLS 1.3)
├── PII detection and redaction before LLM calls
├── Data classification tagging on all documents
├── DLP policies: classified data never sent to external LLMs
└── Customer data isolation (per-tenant encryption keys)

Layer 4: AI-SPECIFIC SECURITY
├── Prompt injection detection (input classifier)
├── Output filtering (PII, harmful content, data leakage)
├── Model access logging (who queried what, full audit)
├── Jailbreak detection with automatic blocking
├── Indirect prompt injection defense (content from RAG sources)
└── Rate limiting per user, per model, per token budget

Layer 5: OPERATIONAL SECURITY
├── Secrets management (Vault, never in code/config)
├── Immutable audit logs (tamper-proof, 7-year retention)
├── Automated vulnerability scanning of dependencies
├── Incident response playbook for AI-specific incidents
└── Regular red-team exercises (AI-focused pentesting)
```

**Zero Trust for AI — Specific Patterns:**

```python
class AIRequestValidator:
    """Validates every AI request against zero-trust policies."""
    
    async def validate(self, request: AIRequest) -> ValidationResult:
        checks = await asyncio.gather(
            self._verify_identity(request),      # Is this really who they say?
            self._check_authorization(request),   # Can they use this model/data?
            self._scan_for_injection(request),    # Is the input adversarial?
            self._check_data_classification(request),  # Can this data go to this model?
            self._check_rate_limits(request),     # Within budget?
            self._check_content_policy(request),  # Acceptable use?
        )
        
        if any(check.blocked for check in checks):
            blocked_reasons = [c.reason for c in checks if c.blocked]
            await self.audit_log.log_blocked_request(request, blocked_reasons)
            return ValidationResult(allowed=False, reasons=blocked_reasons)
        
        return ValidationResult(allowed=True)
```

---

## Question 6: "How would you implement AI governance for a Fortune 500?"

### Organizational Model

```
┌─────────────────────────────────────────────────────────────┐
│                    BOARD / C-SUITE                            │
│     AI Ethics Committee (quarterly review)                   │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              CENTRAL AI GOVERNANCE OFFICE                     │
│  - Chief AI Officer (or VP-level)                           │
│  - Policy team (2-3 people)                                 │
│  - Risk assessment team (2-3 people)                        │
│  - Audit/compliance team (2-3 people)                       │
└──────┬──────────────────────────────────────────┬───────────┘
       │                                          │
       ▼                                          ▼
┌──────────────────┐                    ┌─────────────────────┐
│ AI REVIEW BOARD  │                    │ PLATFORM TEAM       │
│ (cross-functional│                    │ (implements tooling) │
│  approval body)  │                    │                     │
│ - Legal          │                    │ - Model registry    │
│ - Privacy        │                    │ - Eval platform     │
│ - Security       │                    │ - Monitoring        │
│ - Business       │                    │ - Guardrails        │
│ - Ethics         │                    │ - Audit logs        │
└──────────────────┘                    └─────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│              PRODUCT TEAMS (20+ teams)                        │
│  Each team has:                                              │
│  - Designated "AI Champion" (governance liaison)             │
│  - Mandatory use-case registration                           │
│  - Risk tier classification for each AI feature              │
└──────────────────────────────────────────────────────────────┘
```

**Risk Tier Classification:**

| Tier | Description | Example | Review Required |
|------|-------------|---------|-----------------|
| 1 - Low | Internal tooling, no customer impact | Code suggestion for devs | Self-service, auto-approved |
| 2 - Medium | Customer-facing, non-critical | Product recommendations | Team lead + AI Champion |
| 3 - High | Financial/legal/health decisions | Credit scoring, medical triage | Full AI Review Board |
| 4 - Critical | Safety-critical, regulated | Autonomous actions affecting lives | Board + External audit |

**Process Flow for New AI Use Case:**

```
1. Team registers use case in AI Registry (mandatory)
2. Auto-classification assigns risk tier
3. Based on tier:
   - Tier 1: Auto-approved, proceed with standard guardrails
   - Tier 2: AI Champion reviews, 48-hour approval
   - Tier 3: AI Review Board, 2-week review cycle
   - Tier 4: External assessment + board approval, 4-8 weeks
4. Approved use cases get:
   - Mandatory eval suite configured
   - Monitoring dashboard provisioned
   - Incident response plan documented
5. Ongoing: Quarterly re-review of all Tier 3-4 use cases
```

---

## Question 7: "Design an AI gateway that handles 10K requests/second across 4 providers"

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI GATEWAY CLUSTER                             │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ INGRESS (HAProxy / Envoy)                                 │   │
│  │ - TLS termination                                         │   │
│  │ - Rate limiting (token bucket per API key)                │   │
│  │ - Request validation                                      │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                               │                                   │
│  ┌────────────────────────────▼─────────────────────────────┐   │
│  │ ROUTING ENGINE                                            │   │
│  │                                                           │   │
│  │ Decision factors (in priority order):                     │   │
│  │ 1. Policy constraints (data residency, model allow-list) │   │
│  │ 2. Provider health (circuit breaker state)                │   │
│  │ 3. Latency optimization (P95 by provider last 5 min)     │   │
│  │ 4. Cost optimization (cheapest available for capability)  │   │
│  │ 5. Load balancing (distribute across providers/keys)      │   │
│  └───┬──────────┬──────────┬──────────┬────────────────────┘   │
│      │          │          │          │                          │
│      ▼          ▼          ▼          ▼                          │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────────┐                   │
│  │OpenAI │ │Anthro-│ │Google │ │Azure      │                   │
│  │       │ │pic    │ │Gemini │ │OpenAI     │                   │
│  └───────┘ └───────┘ └───────┘ └───────────┘                   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ SEMANTIC CACHE (Redis + vector similarity)                │   │
│  │ - Exact match cache: hash of (model + prompt + params)    │   │
│  │ - Semantic cache: if query embedding >0.98 similarity     │   │
│  │ - Cache hit rate target: 25-40%                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ CIRCUIT BREAKER (per provider)                            │   │
│  │ - Closed: normal operation                                │   │
│  │ - Open: >5% error rate in 30s window → stop sending       │   │
│  │ - Half-open: after 60s, send 10% traffic to test          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Failover Logic:**

```python
class ProviderRouter:
    async def route(self, request: LLMRequest) -> LLMResponse:
        # Get ranked providers for this request's capability needs
        candidates = self.rank_providers(request)
        
        for provider in candidates:
            if self.circuit_breaker[provider].is_open:
                continue
            
            try:
                response = await asyncio.wait_for(
                    self.providers[provider].call(request),
                    timeout=request.timeout or 30.0
                )
                self.circuit_breaker[provider].record_success()
                return response
                
            except (TimeoutError, ProviderOverloadError) as e:
                self.circuit_breaker[provider].record_failure()
                self.metrics.increment("provider_failover", 
                    tags={"from": provider, "reason": type(e).__name__})
                continue  # Try next provider
        
        # All providers failed
        raise AllProvidersUnavailableError(
            tried=candidates,
            circuit_states={p: self.circuit_breaker[p].state for p in candidates}
        )
```

---

## Question 8: "How would you evaluate and improve an AI system that's producing wrong answers?"

### Systematic Debugging Framework

```
Step 1: CHARACTERIZE the failures
├── Collect 100+ bad responses (user reports, automated detection)
├── Categorize failure types:
│   ├── Hallucination (made up facts)
│   ├── Wrong retrieval (right answer exists, not found)
│   ├── Outdated info (correct at time of indexing, now stale)
│   ├── Misunderstanding query (interpreted differently)
│   ├── Context overflow (relevant info pushed out by irrelevant)
│   └── Instruction following (ignored constraints in prompt)
└── Quantify: What % is each category? Focus on biggest bucket.

Step 2: ISOLATE the component
├── Is it a retrieval problem? → Check retrieval quality in isolation
│   └── For failed queries: do relevant chunks exist in the index?
│       ├── No → Ingestion problem (chunking, missing sources)
│       └── Yes → Retrieval ranking problem (embedding model, reranker)
├── Is it a generation problem? → Give perfect context, still fails?
│   ├── Yes → Prompt engineering, model choice, or inherent limitation
│   └── No → Confirmed retrieval issue
└── Is it a data freshness problem? → When was source last indexed?

Step 3: IMPLEMENT targeted fixes
├── Retrieval failures:
│   ├── Add query expansion (reformulate + multi-query)
│   ├── Improve chunking strategy for failed document types
│   ├── Add hybrid search (semantic + keyword) if not already
│   └── Fine-tune embedding model on domain data
├── Generation failures:
│   ├── Add few-shot examples of correct behavior
│   ├── Strengthen system prompt constraints
│   ├── Add post-generation validation (groundedness check)
│   └── Reduce temperature, add structured output
└── Data failures:
    ├── Increase sync frequency for volatile sources
    ├── Add freshness metadata and prefer recent documents
    └── Detect and flag stale content

Step 4: VALIDATE with eval suite
├── Run full eval suite (not just the failures you found)
├── Check for regressions (fixing one category shouldn't break others)
├── A/B test in production with small traffic slice
└── Monitor for 1-2 weeks before full rollout
```

---

## Question 9: "Design a multi-tenant AI platform for a SaaS company"

### Isolation Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ TENANT ISOLATION LEVELS                                        │
│                                                                │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Level 1: LOGICAL ISOLATION (most tenants)                 │ │
│ │ - Shared infrastructure, tenant ID on every request       │ │
│ │ - Separate vector namespaces per tenant                   │ │
│ │ - Row-level security in PostgreSQL                        │ │
│ │ - Shared LLM deployments with tenant-tagged requests      │ │
│ │ - Cost allocated by token counting per tenant             │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Level 2: DEDICATED RESOURCES (enterprise tenants)         │ │
│ │ - Dedicated vector DB namespace with reserved capacity    │ │
│ │ - Dedicated inference endpoints (Azure OpenAI deployment) │ │
│ │ - Separate encryption keys (BYOK)                         │ │
│ │ - Data residency guarantees (region-specific)             │ │
│ │ - Custom model fine-tuning                                │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Level 3: FULLY ISOLATED (regulated industries)            │ │
│ │ - Dedicated Kubernetes namespace or cluster               │ │
│ │ - Own VPC / network isolation                             │ │
│ │ - Private LLM deployment (on-prem or dedicated cloud)     │ │
│ │ - Customer-managed encryption keys                        │ │
│ │ - Independent audit logging                               │ │
│ └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

**Cost Allocation:**

```python
class TenantCostTracker:
    """Track and allocate AI costs per tenant with precision."""
    
    async def record_usage(self, tenant_id: str, request: LLMRequest, response: LLMResponse):
        usage = UsageRecord(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            model=request.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            embedding_tokens=getattr(response.usage, 'embedding_tokens', 0),
            vector_queries=request.metadata.get('vector_queries', 0),
            compute_seconds=response.latency_seconds,
            
            # Cost calculation
            input_cost=response.usage.prompt_tokens * MODEL_PRICING[request.model]['input'],
            output_cost=response.usage.completion_tokens * MODEL_PRICING[request.model]['output'],
            infra_cost=self._compute_infra_allocation(tenant_id),
        )
        
        await self.usage_store.insert(usage)
        
        # Check against tenant's budget
        monthly_spend = await self.get_monthly_spend(tenant_id)
        tenant_config = await self.get_tenant_config(tenant_id)
        
        if monthly_spend >= tenant_config.hard_limit:
            await self.enforce_hard_limit(tenant_id)  # Block requests
        elif monthly_spend >= tenant_config.soft_limit:
            await self.notify_tenant(tenant_id, "approaching_limit")
```

**Noisy Neighbor Prevention:**

```python
class TenantRateLimiter:
    """Prevent any single tenant from degrading service for others."""
    
    limits = {
        "free": {"rpm": 60, "tpm": 40_000, "concurrent": 5},
        "pro": {"rpm": 300, "tpm": 200_000, "concurrent": 20},
        "enterprise": {"rpm": 1000, "tpm": 1_000_000, "concurrent": 50},
        "dedicated": {"rpm": None, "tpm": None, "concurrent": None},  # No shared limits
    }
    
    async def check_and_consume(self, tenant_id: str, request: LLMRequest) -> bool:
        tier = await self.get_tenant_tier(tenant_id)
        limits = self.limits[tier]
        
        if limits["rpm"] is None:
            return True  # Dedicated tier has no shared limits
        
        # Sliding window rate limit
        current_rpm = await self.redis.get_window_count(
            f"rpm:{tenant_id}", window_seconds=60
        )
        if current_rpm >= limits["rpm"]:
            raise RateLimitExceededError(
                tenant_id=tenant_id,
                limit_type="rpm",
                current=current_rpm,
                limit=limits["rpm"],
                retry_after=self._compute_retry_after(tenant_id)
            )
        
        # Token budget (estimated before call, reconciled after)
        estimated_tokens = self._estimate_tokens(request)
        current_tpm = await self.redis.get_window_count(
            f"tpm:{tenant_id}", window_seconds=60
        )
        if current_tpm + estimated_tokens > limits["tpm"]:
            raise RateLimitExceededError(limit_type="tpm")
        
        return True
```

---

## Question 10: "How would you handle an AI incident where the system gave harmful medical advice?"

### Incident Response Playbook

```
SEVERITY: P1 - CRITICAL
TRIGGER: AI system provided medical advice that could cause physical harm

IMMEDIATE ACTIONS (First 15 minutes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. CONTAIN
   □ Disable the AI feature immediately (feature flag → OFF)
   □ Replace with static message: "This service is temporarily unavailable. 
     For medical questions, please consult a healthcare professional."
   □ Identify all users who received similar responses (last 24-72 hours)
   □ Page: Engineering Lead, Legal, Head of Product, CISO

2. ASSESS SCOPE
   □ How many users received potentially harmful advice?
   □ What was the specific harmful content?
   □ Was this a single failure or systematic?
   □ Query the audit logs: same prompt pattern → how many matches?

3. NOTIFY AFFECTED USERS (within 1 hour)
   □ Direct notification to affected users (email + in-app)
   □ Message: "We identified an error in a response you received on [date]. 
     The information about [topic] was incorrect. Please disregard that advice
     and consult a healthcare professional for medical questions."
   □ Legal reviews notification before sending

SHORT-TERM (24-48 hours):
━━━━━━━━━━━━━━━━━━━━━━━━
4. ROOT CAUSE ANALYSIS
   □ Why did the guardrails fail to catch this?
   □ Was there a prompt injection? Data poisoning? Model hallucination?
   □ Review the full request/response chain with context
   □ Identify all defense layers that should have caught this

5. IMMEDIATE FIXES (before re-enabling)
   □ Add explicit medical advice detection to output filter
   □ Add hard-coded refusal for medical/health/safety topics
   □ Strengthen system prompt: "NEVER provide medical advice..."
   □ Add human-in-the-loop for any health-related responses
   □ Run full eval suite with medical safety test cases

6. EXTERNAL COMMUNICATION
   □ Prepare public statement if users are affected at scale
   □ Notify regulators if required (depends on jurisdiction)
   □ Document for compliance record

LONG-TERM (1-4 weeks):
━━━━━━━━━━━━━━━━━━━━━━
7. SYSTEMATIC PREVENTION
   □ Build comprehensive medical/safety eval dataset (500+ test cases)
   □ Implement topic classification BEFORE generation
   □ Add mandatory disclaimer injection for any health-adjacent response
   □ Create "forbidden topics" registry with zero-tolerance enforcement
   □ Red-team exercise: adversarial testing of safety guardrails
   □ External safety audit of the system

8. PROCESS IMPROVEMENTS
   □ Update incident response playbook with learnings
   □ Add this failure mode to regression test suite
   □ Review all other high-risk topic categories
   □ Implement canary deployment for prompt/guardrail changes
```

---

## Behavioral Interview Examples (STAR Format)

### Example 1: "Tell me about a time you made a difficult technical decision under uncertainty"

**Situation:** Building a RAG system for a healthcare company. Had to choose between using GPT-4 (better quality but data leaves the network) vs. an on-premise open-source model (worse quality but full data control).

**Task:** Make the architecture decision with incomplete information. We didn't know the exact quality gap, and the compliance team hadn't finalized their data handling policy.

**Action:** I ran a 2-week evaluation comparing both approaches on 200 sample queries. GPT-4 scored 0.92 groundedness vs. Llama-2-70B at 0.78. Presented the data to stakeholders with three options: (1) GPT-4 with Azure Private Link and BAA, (2) on-prem Llama with quality trade-off, (3) hybrid where non-PHI queries go to GPT-4 and PHI queries use on-prem. Built a cost model for each.

**Result:** Team chose option 3 (hybrid). It took 3 extra weeks to implement the query classifier, but we achieved 0.89 groundedness overall while maintaining full HIPAA compliance. The evaluation data I collected became the basis for our ongoing quality monitoring.

### Example 2: "Describe a time you had to push back on a stakeholder's request"

**Situation:** VP of Product wanted to launch an AI feature that auto-approved customer refunds up to $1,000 based on sentiment analysis of their complaint. "If they're angry enough, just refund them."

**Task:** I was responsible for the AI system's reliability and safety. I believed this approach was vulnerable to gaming and could cost millions.

**Action:** I didn't just say "no." I built a proof-of-concept showing how easy it was to game the system (wrote 10 prompts that would fool the sentiment classifier). Presented data: at 50K monthly tickets, even 5% gaming rate = $600K/year in fraudulent refunds. Proposed alternative: AI suggests refund to human agent with one-click approval, plus fraud detection layer for patterns.

**Result:** VP agreed to the human-in-the-loop approach. We launched 3 weeks later. Auto-suggestion with human approval achieved 94% approval rate (so barely any friction) while catching 12 fraud attempts in the first month.

### Example 3: "Tell me about a production failure you were responsible for"

**Situation:** Deployed a prompt change to our customer support AI that removed a guardrail against making promises about delivery dates. Didn't realize the guardrail was there because it was buried in a 2,000-token system prompt.

**Task:** Customers received incorrect delivery promises for 4 hours before we caught it. ~200 customers affected.

**Action:** Immediately reverted the change. Sent correction emails to all affected customers. Then built three preventive measures: (1) eval gate in CI that tests all critical behaviors before prompt changes deploy, (2) prompt change review checklist with "what guardrails might this affect?", (3) real-time monitoring of response patterns that alerts on distribution shift (delivery date mentions spiked 400% which should have triggered an alert).

**Result:** Never had a similar incident. The eval gate has since caught 6 regressions before they reached production. I presented this as a case study internally, and 3 other teams adopted the same eval gate pattern.

### Example 4: "How do you handle disagreements with your team?"

**Situation:** Senior engineer on my team insisted we needed to fine-tune a model for our use case. I believed prompt engineering with RAG was sufficient and fine-tuning would add 2 months and $50K in compute costs.

**Task:** Make the right technical decision without damaging the working relationship.

**Action:** Proposed a structured experiment: 1 week each. He'd build a fine-tuning proof-of-concept, I'd optimize the RAG + prompt approach. We defined the eval metrics upfront: groundedness, latency, and cost per query. We agreed that whoever's approach scored better on the eval suite would win, regardless of personal preference.

**Result:** My RAG approach scored 0.91 groundedness at $0.03/query. His fine-tuned model scored 0.89 at $0.08/query (inference on A100s). He acknowledged the data and we went with RAG. But — his fine-tuning work wasn't wasted. We used it 6 months later when we needed a fast, cheap model for a high-volume classification task where RAG was overkill.

### Example 5: "Describe a project where you had to learn something completely new"

**Situation:** Company decided to build a multi-agent system. I had deep RAG experience but zero experience with agent frameworks, tool use, or multi-agent orchestration.

**Task:** Design and ship the agent architecture within 8 weeks.

**Action:** Week 1-2: Read every paper and production writeup I could find (AutoGen, CrewAI, LangGraph docs, Anthropic's agent patterns). Week 3: Built 3 small prototypes comparing frameworks. Week 4: Made architecture decision (LangGraph for controllability over AutoGen's autonomous approach). Week 5-8: Built the production system with the team, doing daily knowledge-sharing sessions where I taught what I'd learned.

**Result:** Shipped on time. The agent system handled 70% of tickets autonomously. Key learning: I documented my entire learning journey as an internal "Agent Architecture Decisions" doc that became required reading for new AI engineers joining the team.

---

## Whiteboard Presentation Tips

### How to Draw Architecture Diagrams Under Time Pressure

**1. Start with the user flow (left to right or top to bottom)**
```
Don't start with infrastructure. Start with:
User → [what happens] → [what happens] → Response
Then fill in the components that make each step work.
```

**2. Use consistent notation**
```
┌─────────┐  Rectangles = services/components
│ Service │
└─────────┘

(  Database )  Cylinders = data stores

[  Queue  ]    Brackets = async/queues

─────────→     Solid arrow = synchronous
- - - - -→    Dashed arrow = asynchronous
```

**3. Label every arrow with what flows through it**
```
Bad:  Service A ──→ Service B
Good: Service A ──query + user_context──→ Service B
```

**4. Show the data path, not just the control path**
```
Interviewers want to know: where does data live? How does it flow?
Always show: input → processing → storage → retrieval → output
```

**5. Time management**
- Minutes 0-3: Requirements on one side of whiteboard
- Minutes 3-8: High-level diagram (5-7 boxes, main flows)
- Minutes 8-25: Deep-dive on 2-3 critical components
- Minutes 25-35: Scaling, failure modes, monitoring
- Minutes 35-45: Discussion with interviewer

---

## Common Interviewer Follow-up Questions

### After any AI system design:

1. **"What happens when the LLM provider goes down?"**
   → Failover strategy, graceful degradation, cached responses, queue for retry

2. **"How do you know the system is working correctly in production?"**
   → Metrics (latency, groundedness, user satisfaction), alerting thresholds, weekly quality audits

3. **"What if a user tries to jailbreak the system?"**
   → Input classifier, output filter, rate limiting, monitoring for anomalous patterns

4. **"How would you reduce costs by 50%?"**
   → Caching, smaller models for simple queries, batch processing, reduce context window, fine-tuning

5. **"What's your testing strategy?"**
   → Unit tests for components, eval suite for quality, integration tests for flows, load tests for scale, red-team for safety

6. **"How do you handle model updates?"**
   → Canary deployment, A/B testing, eval comparison against current model, rollback plan

7. **"What would you build first?"**
   → MVP scoping: simplest valuable slice, usually one use case with one data source, then expand

8. **"What are the biggest risks?"**
   → Enumerate: quality degradation, security breach, cost explosion, vendor lock-in, compliance violation. For each: likelihood, impact, mitigation.

---

## Red Flags Interviewers Look For

### Automatic Disqualifiers:

1. **No requirements gathering** — Jumping straight to "I'd use LangChain and Pinecone" without understanding the problem.

2. **Name-dropping without understanding** — "I'd use a transformer architecture with attention mechanisms" without explaining WHY or what trade-offs exist.

3. **No failure mode thinking** — Only describing the happy path. Real architects think about what breaks.

4. **Hand-waving on evaluation** — "We'd test it" without explaining how, what metrics, what thresholds.

5. **Ignoring cost** — Designing a system that costs $100/query without acknowledging it or proposing optimizations.

6. **Over-engineering** — Using 15 services for a problem that needs 3. Complexity is a cost, not a feature.

7. **No security consideration** — Especially for enterprise contexts. PII, prompt injection, and access control should be mentioned unprompted.

8. **Inability to go deep** — Broad architecture is necessary but insufficient. When asked "how does the retrieval work exactly?", you need specific answers about embedding models, chunk sizes, reranking strategies.

9. **Rigid thinking** — Refusing to adapt when the interviewer changes requirements. "But I already designed it this way" is a red flag. Good architects pivot.

10. **No trade-off articulation** — Every decision has trade-offs. If you can't articulate what you're giving up with each choice, you haven't thought deeply enough.

### Green Flags That Impress:

- Quantifying everything (latency targets, cost per query, error budgets)
- Mentioning monitoring and observability unprompted
- Discussing how you'd evaluate the system before building it
- Acknowledging what you don't know and how you'd find out
- Referencing real-world systems and their public architecture writeups
- Progressive disclosure: high-level first, then depth on request
- Connecting technical decisions to business outcomes
