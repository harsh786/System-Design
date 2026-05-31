# Capstone Projects — Real-World Examples

## Project 1: Enterprise RAG System for a 10,000-Person Company

### Context & Requirements

**Company Profile:** Global financial services firm, 10,000 employees across 15 offices, 8 business units.

**Problem Statement:** Knowledge workers spend 2.3 hours/day searching for information across fragmented systems. Institutional knowledge is lost when employees leave. Support teams answer the same questions repeatedly.

**Quantified Requirements:**
| Metric | Target | Rationale |
|--------|--------|-----------|
| Document corpus | 2M documents | Current content across all sources |
| Daily active users | 500 | Phase 1 rollout to 3 business units |
| P95 latency | <3 seconds | User research showed >3s causes abandonment |
| Groundedness | >90% | Regulatory requirement for financial advice |
| Hallucination rate | <3% | Legal risk threshold |
| Uptime | 99.9% | Business-critical during market hours |
| Cost per query | <$0.05 | Budget constraint from CFO |

**Access Control Requirements:**
- Department-based: Legal docs only visible to Legal + C-suite
- Project-based: M&A documents restricted to deal teams
- Classification levels: Public, Internal, Confidential, Restricted
- Audit trail: Every document access logged for compliance

---

### Architecture Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                       │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │ Web App  │  │ Slack Bot    │  │ Teams Bot   │  │ API Consumers  │  │
│  └────┬─────┘  └──────┬───────┘  └──────┬──────┘  └───────┬────────┘  │
└───────┼────────────────┼─────────────────┼─────────────────┼────────────┘
        │                │                 │                 │
        ▼                ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (Kong)                                   │
│  Rate Limiting │ Auth (OAuth2 + SAML) │ Request Routing │ Audit Log     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      QUERY ORCHESTRATION LAYER                            │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │ Query Analyzer  │  │ Permission       │  │ Query Router          │  │
│  │ - Intent detect │  │ Resolver         │  │ - Simple → fast path  │  │
│  │ - Entity extract│  │ - User groups    │  │ - Complex → full RAG  │  │
│  │ - Reformulation │  │ - Doc ACLs       │  │ - Ambiguous → clarify │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────────┬───────────┘  │
└───────────┼─────────────────────┼────────────────────────┼──────────────┘
            │                     │                        │
            ▼                     ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      RETRIEVAL LAYER                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐   │
│  │ Semantic Search │  │ Keyword Search │  │ Hybrid Reranker         │   │
│  │ (Pinecone)     │  │ (Elasticsearch)│  │ (Cohere Rerank v3)      │   │
│  │ 2M vectors     │  │ Full-text index│  │ Cross-encoder scoring   │   │
│  └────────────────┘  └────────────────┘  └─────────────────────────┘   │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ Permission-Filtered Results (post-retrieval ACL enforcement)       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      GENERATION LAYER                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ Context Assembly │  │ LLM Generation   │  │ Post-Processing      │  │
│  │ - Chunk ordering │  │ - GPT-4o primary │  │ - Citation mapping   │  │
│  │ - Token budget   │  │ - Claude fallback│  │ - Groundedness check │  │
│  │ - Relevance gate │  │ - Temperature 0.1│  │ - PII redaction      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      INGESTION PIPELINE                                    │
│  ┌────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐    │
│  │Conflu- │ │SharePoint │ │Google    │ │ Slack  │ │    Jira      │    │
│  │ence    │ │           │ │Drive     │ │        │ │              │    │
│  └───┬────┘ └─────┬─────┘ └────┬─────┘ └───┬────┘ └──────┬───────┘    │
│      │             │            │           │             │             │
│      ▼             ▼            ▼           ▼             ▼             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Apache Airflow - Ingestion Orchestrator             │    │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌─────────────────┐ │    │
│  │  │ Extract  │→│ Transform│→│ Chunk      │→│ Embed + Index   │ │    │
│  │  │ (connec- │ │ (clean,  │ │ (semantic  │ │ (ada-002 +      │ │    │
│  │  │  tors)   │ │  parse)  │ │  chunking) │ │  metadata)      │ │    │
│  │  └──────────┘ └──────────┘ └────────────┘ └─────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Component Deep-Dive

#### 1. Ingestion Pipeline (Apache Airflow)

**Connector Architecture:**

```python
# Confluence Connector - Real Implementation Pattern
class ConfluenceConnector:
    def __init__(self, config: ConnectorConfig):
        self.client = AtlassianConfluence(
            url=config.base_url,
            username=config.username,
            password=config.api_token
        )
        self.rate_limiter = TokenBucketRateLimiter(
            tokens_per_second=5,  # Confluence API limit
            burst=10
        )
    
    async def crawl_space(self, space_key: str) -> AsyncIterator[RawDocument]:
        """Crawl all pages in a Confluence space with change detection."""
        last_sync = await self.state_store.get_last_sync(space_key)
        
        pages = self.client.get_all_pages_from_space(
            space_key,
            start=0,
            limit=100,
            expand="body.storage,version,ancestors,metadata.labels"
        )
        
        for page in pages:
            if page["version"]["when"] > last_sync:
                yield RawDocument(
                    source_id=f"confluence://{space_key}/{page['id']}",
                    content=page["body"]["storage"]["value"],
                    content_type="text/html",
                    metadata={
                        "title": page["title"],
                        "space": space_key,
                        "author": page["version"]["by"]["displayName"],
                        "last_modified": page["version"]["when"],
                        "labels": [l["name"] for l in page["metadata"]["labels"]["results"]],
                        "ancestors": [a["title"] for a in page["ancestors"]],
                        "url": f"{self.config.base_url}/wiki{page['_links']['webui']}"
                    },
                    permissions=await self._resolve_permissions(page)
                )
    
    async def _resolve_permissions(self, page: dict) -> DocumentPermissions:
        """Map Confluence restrictions to internal permission model."""
        restrictions = self.client.get_page_restrictions(page["id"])
        
        if not restrictions["read"]["restrictions"]["group"]["results"]:
            # No restrictions = space-level permissions apply
            space_perms = await self._get_space_permissions(page["space"]["key"])
            return DocumentPermissions(
                level="space_default",
                allowed_groups=space_perms.read_groups,
                allowed_users=space_perms.read_users
            )
        
        return DocumentPermissions(
            level="page_restricted",
            allowed_groups=[g["name"] for g in restrictions["read"]["restrictions"]["group"]["results"]],
            allowed_users=[u["username"] for u in restrictions["read"]["restrictions"]["user"]["results"]]
        )
```

**Chunking Strategy:**

```python
class SemanticChunker:
    """Production chunking strategy combining structural and semantic signals."""
    
    def __init__(self):
        self.sentence_splitter = spacy.load("en_core_web_sm")
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  # Fast local model for chunking
        self.target_chunk_size = 512  # tokens
        self.overlap = 64  # tokens
        self.similarity_threshold = 0.65
    
    def chunk_document(self, doc: ParsedDocument) -> List[Chunk]:
        chunks = []
        
        # Step 1: Split by structural boundaries (headers, sections)
        sections = self._split_by_structure(doc)
        
        # Step 2: For each section, apply semantic chunking
        for section in sections:
            sentences = list(self.sentence_splitter(section.text).sents)
            embeddings = self.embedding_model.encode([s.text for s in sentences])
            
            current_chunk_sentences = [sentences[0]]
            current_embedding = embeddings[0]
            
            for i in range(1, len(sentences)):
                similarity = cosine_similarity(
                    current_embedding.reshape(1, -1),
                    embeddings[i].reshape(1, -1)
                )[0][0]
                
                token_count = self._count_tokens(
                    " ".join(s.text for s in current_chunk_sentences + [sentences[i]])
                )
                
                if similarity >= self.similarity_threshold and token_count <= self.target_chunk_size:
                    current_chunk_sentences.append(sentences[i])
                    # Running average of embeddings
                    current_embedding = np.mean(embeddings[:i+1], axis=0)
                else:
                    # Emit chunk
                    chunks.append(self._create_chunk(
                        sentences=current_chunk_sentences,
                        section=section,
                        doc=doc
                    ))
                    current_chunk_sentences = [sentences[i]]
                    current_embedding = embeddings[i]
            
            # Don't forget the last chunk
            if current_chunk_sentences:
                chunks.append(self._create_chunk(current_chunk_sentences, section, doc))
        
        return chunks
```

#### 2. Access Control Implementation

```python
class PermissionResolver:
    """Resolves user permissions against document ACLs at query time."""
    
    def __init__(self, identity_provider: IdentityProvider, cache: Redis):
        self.idp = identity_provider
        self.cache = cache
        self.cache_ttl = 300  # 5 minutes - balance freshness vs performance
    
    async def get_user_access_filter(self, user_id: str) -> Dict:
        """Generate a Pinecone metadata filter for the user's permissions."""
        cache_key = f"access_filter:{user_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Resolve user's groups from identity provider (Azure AD / Okta)
        user_groups = await self.idp.get_user_groups(user_id)
        user_department = await self.idp.get_user_department(user_id)
        user_clearance = await self.idp.get_user_clearance_level(user_id)
        
        # Build filter that matches documents the user can see
        access_filter = {
            "$or": [
                {"access_level": "public"},
                {"allowed_groups": {"$in": user_groups}},
                {"allowed_users": {"$in": [user_id]}},
                {
                    "$and": [
                        {"access_level": "department"},
                        {"department": user_department}
                    ]
                }
            ]
        }
        
        # Clearance level gate
        clearance_hierarchy = ["public", "internal", "confidential", "restricted"]
        user_level_idx = clearance_hierarchy.index(user_clearance)
        access_filter["classification_level"] = {
            "$in": clearance_hierarchy[:user_level_idx + 1]
        }
        
        await self.cache.set(cache_key, json.dumps(access_filter), ex=self.cache_ttl)
        return access_filter
    
    async def post_retrieval_filter(
        self, chunks: List[RetrievedChunk], user_id: str
    ) -> List[RetrievedChunk]:
        """Defense-in-depth: Re-verify permissions after retrieval."""
        verified = []
        for chunk in chunks:
            has_access = await self._verify_source_access(
                user_id=user_id,
                source_id=chunk.metadata["source_id"],
                source_system=chunk.metadata["source_system"]
            )
            if has_access:
                verified.append(chunk)
            else:
                logger.warning(
                    "Post-retrieval ACL rejection",
                    user_id=user_id,
                    doc_id=chunk.metadata["source_id"],
                    reason="metadata_filter_bypass"
                )
        return verified
```

#### 3. Quality Assurance — Groundedness Scoring

```python
class GroundednessEvaluator:
    """Production groundedness scoring with fallback strategies."""
    
    async def evaluate_response(
        self, query: str, response: str, source_chunks: List[Chunk]
    ) -> GroundednessResult:
        """Score each claim in the response against source material."""
        
        # Step 1: Decompose response into atomic claims
        claims = await self._extract_claims(response)
        
        # Step 2: For each claim, find supporting evidence
        claim_scores = []
        for claim in claims:
            best_support = 0.0
            supporting_chunk = None
            
            for chunk in source_chunks:
                # NLI-based entailment scoring
                score = await self._compute_entailment(
                    premise=chunk.text,
                    hypothesis=claim.text
                )
                if score > best_support:
                    best_support = score
                    supporting_chunk = chunk
            
            claim_scores.append(ClaimScore(
                claim=claim,
                groundedness_score=best_support,
                supporting_chunk=supporting_chunk,
                is_grounded=best_support >= 0.7
            ))
        
        # Step 3: Aggregate
        grounded_claims = [c for c in claim_scores if c.is_grounded]
        overall_score = len(grounded_claims) / len(claim_scores) if claim_scores else 1.0
        
        return GroundednessResult(
            overall_score=overall_score,
            claim_scores=claim_scores,
            meets_threshold=overall_score >= 0.90,
            ungrounded_claims=[c for c in claim_scores if not c.is_grounded]
        )
```

---

### Deployment Architecture

**Infrastructure (AWS):**
- EKS cluster: 3 node groups (API, Workers, GPU inference)
- Pinecone: p2 pod, 2M vectors, 3 replicas
- Elasticsearch: 3-node cluster, 500GB SSD each
- Redis Cluster: 6 nodes for caching + session
- RDS PostgreSQL: Metadata, audit logs, user preferences
- S3: Raw document storage, processing artifacts

**Cost Model (Monthly):**
| Component | Cost | Notes |
|-----------|------|-------|
| LLM (GPT-4o) | $8,000 | ~160K queries/month, avg 2K tokens |
| Embeddings | $400 | Batch re-embedding monthly |
| Pinecone | $2,100 | p2 pod with replicas |
| EKS Compute | $3,500 | Mixed instance types |
| Elasticsearch | $1,800 | 3x r5.xlarge |
| Redis | $600 | Cache layer |
| Monitoring/Logging | $500 | Datadog |
| **Total** | **~$17,000** | **$0.034/query** |

---

### Monitoring & Observability

```yaml
# Key SLOs and alerting thresholds
slos:
  - name: query_latency_p95
    target: 3000ms
    window: 30d
    burn_rate_alert:
      fast: 14.4x over 1h  # Pages on-call
      slow: 6x over 6h     # Creates ticket

  - name: groundedness_score
    target: 0.90
    window: 7d
    alert_threshold: 0.85  # Early warning

  - name: availability
    target: 99.9%
    window: 30d
    error_budget: 43.2 minutes/month

dashboards:
  operational:
    - Query volume (real-time + trend)
    - Latency distribution (p50, p90, p95, p99)
    - Error rate by type (retrieval_empty, generation_timeout, permission_denied)
    - Cache hit rate
    - Token usage by model
    
  quality:
    - Groundedness score distribution (daily)
    - Hallucination detection rate
    - User satisfaction (thumbs up/down ratio)
    - Citation accuracy (weekly sample audit)
    - Empty retrieval rate by source
    
  business:
    - Cost per query trend
    - Time saved per user (estimated)
    - Adoption rate by department
    - Top queries without good answers (improvement backlog)
```

---

## Project 2: Agentic AI Customer Support Platform

### Context & Requirements

**Company Profile:** B2B SaaS company, 5,000 customers, 50K support tickets/month across billing, technical, and account management.

**Current State:** 45 human agents, average resolution time 4.2 hours, CSAT 3.8/5, cost per ticket $12.

**Target State:**
| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Auto-resolution rate | 0% | 70% | New capability |
| Avg resolution time | 4.2 hours | 15 min (auto) / 2 hours (human) | 60-94% faster |
| CSAT | 3.8/5 | 4.3/5 | +13% |
| Cost per ticket | $12 | $3.50 (blended) | -71% |
| Agent capacity | 45 agents | 20 agents + AI | -55% headcount |

---

### Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    INCOMING TICKETS                               │
│  Zendesk │ Email │ Chat │ In-App │ Phone (transcribed)          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TRIAGE AGENT                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Classify: billing | technical | account | feedback     │  │
│  │ 2. Priority: P1 (outage) | P2 (broken) | P3 (question)   │  │
│  │ 3. Sentiment: angry | frustrated | neutral | happy        │  │
│  │ 4. Complexity: simple | moderate | complex | escalate     │  │
│  │ 5. Route decision: auto-resolve | specialist | human      │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Confidence threshold: >0.85 for auto-routing                    │
│  Fallback: Human triage queue if confidence <0.85                │
└──────────┬──────────────────┬────────────────────┬──────────────┘
           │                  │                    │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌────────▼────────┐
    │  BILLING    │   │ TECHNICAL   │   │  ESCALATION     │
    │  AGENT      │   │ AGENT       │   │  AGENT          │
    └─────────────┘   └─────────────┘   └─────────────────┘
```

**Agent Definitions:**

```python
class TriageAgent:
    """First-touch agent that classifies and routes every ticket."""
    
    SYSTEM_PROMPT = """You are the first-line triage agent for Acme SaaS support.
    
    Your job:
    1. Read the customer's message carefully
    2. Classify the issue category
    3. Assess priority based on business impact
    4. Determine if this can be auto-resolved or needs specialist/human
    
    Rules:
    - NEVER attempt resolution yourself, only classify and route
    - If the customer mentions legal action, data breach, or executive escalation → always route to human
    - If sentiment is "angry" AND priority is P1 → route to human with priority flag
    - If you're <85% confident in classification → route to human triage
    """
    
    TOOLS = [
        CustomerLookupTool(),      # Get customer tier, history, plan
        TicketHistoryTool(),       # Recent tickets from same customer
        OutageStatusTool(),        # Check if known outage matches issue
    ]
    
    async def process(self, ticket: Ticket) -> TriageDecision:
        customer = await self.tools.customer_lookup(ticket.customer_id)
        recent_tickets = await self.tools.ticket_history(ticket.customer_id, limit=5)
        active_outages = await self.tools.outage_status()
        
        # Check if this matches a known outage
        if self._matches_outage(ticket, active_outages):
            return TriageDecision(
                category="technical",
                priority="P1",
                route="auto_resolve",
                resolution_template="known_outage",
                confidence=0.95
            )
        
        # LLM classification with structured output
        classification = await self.llm.classify(
            ticket=ticket,
            customer_context=customer,
            recent_history=recent_tickets
        )
        
        # Apply business rules on top of LLM classification
        decision = self._apply_business_rules(classification, customer)
        
        return decision


class BillingAgent:
    """Handles billing inquiries with access to Stripe and internal billing system."""
    
    SYSTEM_PROMPT = """You are a billing specialist agent for Acme SaaS.
    
    You can:
    - Explain charges and invoices
    - Apply credits up to $500 without approval
    - Process refunds up to $200 without approval
    - Upgrade/downgrade plans
    - Fix billing errors
    
    You cannot:
    - Issue refunds >$200 (escalate to billing manager)
    - Modify enterprise contracts (escalate to account manager)
    - Override fraud holds (escalate to security)
    
    Always:
    - Confirm the action before executing
    - Provide a clear summary of what was done
    - Include relevant invoice/credit numbers in response
    """
    
    TOOLS = [
        StripeCustomerTool(),      # Read customer billing info
        StripeCreditTool(),        # Issue credits (max $500)
        StripeRefundTool(),        # Process refunds (max $200)
        PlanChangeTool(),          # Upgrade/downgrade subscriptions
        InvoiceExplainTool(),      # Break down invoice line items
        InternalCRMNoteTool(),     # Log actions taken
    ]
    
    GUARDRAILS = [
        MaxCreditGuardrail(limit=500),
        MaxRefundGuardrail(limit=200),
        CustomerTierGuardrail(),   # Enterprise customers → always escalate
        FraudCheckGuardrail(),     # Check for refund abuse patterns
    ]
```

**Technical Agent — Tool Use Pattern:**

```python
class TechnicalAgent:
    """Handles technical issues with access to logs, configs, and runbooks."""
    
    TOOLS = [
        LogSearchTool(),           # Search customer's application logs
        ConfigInspectTool(),       # Read customer's configuration
        RunbookSearchTool(),       # Search internal runbooks for solutions
        APIHealthCheckTool(),      # Check status of customer's API endpoints
        FeatureFlagTool(),         # Check/toggle feature flags
        SandboxTestTool(),         # Run tests in customer's sandbox
    ]
    
    async def resolve(self, ticket: Ticket, triage: TriageDecision) -> Resolution:
        """Multi-step reasoning to diagnose and resolve technical issues."""
        
        # Step 1: Gather context
        logs = await self.tools.log_search(
            customer_id=ticket.customer_id,
            timerange="last_24h",
            query=self._extract_error_keywords(ticket)
        )
        
        config = await self.tools.config_inspect(ticket.customer_id)
        
        # Step 2: Search runbooks for matching patterns
        runbook_matches = await self.tools.runbook_search(
            symptoms=self._summarize_symptoms(ticket, logs)
        )
        
        # Step 3: LLM reasoning with chain-of-thought
        diagnosis = await self.llm.diagnose(
            ticket=ticket,
            logs=logs,
            config=config,
            runbook_matches=runbook_matches
        )
        
        # Step 4: If confidence high enough, attempt resolution
        if diagnosis.confidence >= 0.85 and diagnosis.action_type in self.SAFE_ACTIONS:
            result = await self._execute_resolution(diagnosis)
            
            # Step 5: Verify fix
            verification = await self._verify_resolution(ticket, diagnosis, result)
            
            if verification.success:
                return Resolution(
                    status="auto_resolved",
                    summary=diagnosis.customer_explanation,
                    actions_taken=result.actions,
                    verification=verification
                )
        
        # Couldn't auto-resolve — prepare handoff
        return Resolution(
            status="escalate_to_human",
            summary=diagnosis.customer_explanation,
            internal_notes=diagnosis.detailed_analysis,
            suggested_actions=diagnosis.recommended_actions
        )
```

---

### Evaluation & Monitoring

```python
# Real metrics tracked in production
class SupportAgentMetrics:
    """Metrics collected for every ticket processed by AI agents."""
    
    # Resolution metrics
    auto_resolution_rate: float          # Target: 70%
    correct_resolution_rate: float       # Target: 95% (verified by QA sampling)
    false_resolution_rate: float         # Target: <2% (customer reopens within 24h)
    
    # Routing metrics  
    triage_accuracy: float               # Target: 92% (compared to human triage)
    escalation_appropriateness: float    # Target: 90% (were escalations necessary?)
    missed_escalation_rate: float        # Target: <1% (should have escalated but didn't)
    
    # Customer experience
    csat_auto_resolved: float            # Target: 4.0/5
    csat_human_resolved: float           # Target: 4.5/5
    response_time_auto: timedelta        # Target: <2 minutes
    response_time_human: timedelta       # Target: <1 hour
    
    # Safety metrics
    harmful_action_rate: float           # Target: 0% (wrong refund, wrong config change)
    pii_leak_rate: float                 # Target: 0%
    unauthorized_action_rate: float      # Target: 0%

# Weekly quality review process
class WeeklyQualityReview:
    def run(self):
        # Sample 100 auto-resolved tickets
        sample = self.sample_resolved_tickets(n=100)
        
        # Human reviewers grade each one
        for ticket in sample:
            review = HumanReview(
                was_correct=True/False,
                was_complete=True/False,
                tone_appropriate=True/False,
                would_customer_be_satisfied=1-5,
                notes="..."
            )
        
        # Compute weekly quality score
        # If score drops below threshold → reduce auto-resolution confidence threshold
        # effectively sending more tickets to humans until quality recovers
```

---

### Integration Architecture with Zendesk

```python
# Zendesk webhook handler - real production pattern
@app.post("/webhooks/zendesk/ticket-created")
async def handle_new_ticket(payload: ZendeskWebhook):
    """Process new ticket from Zendesk via webhook."""
    
    ticket = Ticket(
        external_id=payload.ticket.id,
        customer_id=payload.ticket.requester_id,
        subject=payload.ticket.subject,
        body=payload.ticket.description,
        channel=payload.ticket.via.channel,
        priority=payload.ticket.priority,
        tags=payload.ticket.tags
    )
    
    # Check if AI handling is enabled for this customer/tier
    if not await feature_flags.is_enabled("ai_support", ticket.customer_id):
        return {"action": "skip", "reason": "feature_disabled"}
    
    # Process through agent pipeline
    result = await agent_pipeline.process(ticket)
    
    if result.status == "auto_resolved":
        # Post AI response as internal note first (for audit)
        await zendesk.add_internal_note(
            ticket_id=ticket.external_id,
            body=f"[AI Auto-Resolution]\n{result.internal_notes}"
        )
        # Post customer-facing response
        await zendesk.add_public_reply(
            ticket_id=ticket.external_id,
            body=result.customer_response
        )
        # Set ticket to "solved" (not "closed" — customer can reopen)
        await zendesk.update_ticket(
            ticket_id=ticket.external_id,
            status="solved",
            tags=["ai_resolved", f"agent_{result.agent_type}"]
        )
    
    elif result.status == "escalate_to_human":
        # Add AI analysis as internal note for human agent
        await zendesk.add_internal_note(
            ticket_id=ticket.external_id,
            body=f"[AI Triage Analysis]\n{result.internal_notes}\n\nSuggested actions:\n{result.suggested_actions}"
        )
        # Assign to appropriate group
        await zendesk.update_ticket(
            ticket_id=ticket.external_id,
            group_id=AGENT_GROUP_MAP[result.escalation_target],
            tags=["ai_triaged", "needs_human"]
        )
```

---

## Project 3: AI Evaluation Platform as Internal Product

### Context & Requirements

**Company Profile:** Large tech company with 20 AI product teams building various LLM-powered features (search, coding assistant, content generation, customer support, etc.).

**Problem Statement:** Each team builds their own evaluation infrastructure, leading to:
- Inconsistent quality standards across products
- No shared benchmarks or baselines
- Duplicated effort (each team spending 2-3 engineers on eval tooling)
- No way to compare models/approaches across teams
- Evaluation results not integrated into CI/CD

**Platform Requirements:**
| Capability | Description |
|-----------|-------------|
| Eval types | RAG eval, agent eval, safety eval, general LLM eval |
| Golden datasets | Managed annotation workflow, versioning, sampling |
| CI/CD integration | Eval gates in GitHub Actions, blocking deploys on regression |
| Dashboard | Team-level metrics, cross-team comparisons, trends |
| Scale | 500K eval runs/month across 20 teams |
| Self-serve | Teams can define custom metrics and datasets |

---

### Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EVALUATION PLATFORM                               │
│                                                                       │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │   Web UI    │  │   CLI Tool      │  │   CI/CD Plugin          │ │
│  │  (React)    │  │  (eval-cli)     │  │  (GitHub Action)        │ │
│  └──────┬──────┘  └────────┬────────┘  └────────────┬────────────┘ │
│         │                  │                        │               │
│         ▼                  ▼                        ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    EVAL API (FastAPI)                         │   │
│  │  POST /eval/run          - Trigger evaluation run            │   │
│  │  GET  /eval/results/{id} - Get results                       │   │
│  │  POST /datasets          - Create/update golden dataset      │   │
│  │  POST /metrics/custom    - Register custom metric            │   │
│  │  GET  /dashboard/team    - Team metrics                      │   │
│  └──────────────────────────────┬──────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼──────────────────────────────┐   │
│  │                    EVAL ORCHESTRATOR                          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │   │
│  │  │ Job Queue  │  │ Executor   │  │ Result Aggregator    │  │   │
│  │  │ (Celery)   │  │ (K8s Jobs) │  │ (scoring + storage)  │  │   │
│  │  └────────────┘  └────────────┘  └──────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    METRIC REGISTRY                            │   │
│  │  Built-in:                    Custom (per-team):             │   │
│  │  - Groundedness (NLI)         - Domain-specific accuracy    │   │
│  │  - Faithfulness               - Business metric correlation │   │
│  │  - Answer relevance           - User preference alignment   │   │
│  │  - Context precision/recall   - Latency budgets             │   │
│  │  - Toxicity                   - Cost constraints            │   │
│  │  - PII detection                                            │   │
│  │  - Agent task completion                                    │   │
│  │  - Tool use accuracy                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    DATASET MANAGEMENT                         │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐  │   │
│  │  │ Annotation   │  │ Versioning    │  │ Sampling        │  │   │
│  │  │ Workflow     │  │ (Git-like)    │  │ Strategy        │  │   │
│  │  │ - Label UI   │  │ - Branches    │  │ - Stratified    │  │   │
│  │  │ - IAA score  │  │ - Diffs       │  │ - Difficulty    │  │   │
│  │  │ - Consensus  │  │ - Rollback    │  │ - Edge cases    │  │   │
│  │  └──────────────┘  └───────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

### CI/CD Integration — Eval Gates

```yaml
# .github/workflows/ai-eval-gate.yml
name: AI Evaluation Gate

on:
  pull_request:
    paths:
      - 'src/ai/**'
      - 'prompts/**'
      - 'config/models/**'

jobs:
  eval-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run AI Evaluation Suite
        uses: internal/ai-eval-action@v2
        with:
          eval-config: .ai-eval.yml
          dataset: golden-v3.2
          metrics: |
            groundedness >= 0.90
            faithfulness >= 0.88
            answer_relevance >= 0.85
            toxicity <= 0.01
            latency_p95 <= 3000
            cost_per_query <= 0.06
          
          # Compare against main branch baseline
          baseline-branch: main
          regression-threshold: 0.03  # Block if any metric drops >3%
          
          # Sampling for speed (full eval runs nightly)
          sample-size: 200
          confidence-level: 0.95
      
      - name: Post Results to PR
        if: always()
        uses: internal/ai-eval-comment@v1
        with:
          results-path: eval-results.json
          show-regressions: true
          show-improvements: true
```

**Eval Configuration File:**

```yaml
# .ai-eval.yml - Per-team evaluation configuration
version: "2.0"
team: search-ai
product: enterprise-search

datasets:
  - name: golden-v3.2
    source: eval-platform://datasets/search-ai/golden
    version: "3.2"
    size: 500
    
  - name: edge-cases
    source: eval-platform://datasets/search-ai/edge-cases
    version: "1.4"
    size: 100

evaluators:
  rag:
    metrics:
      - groundedness:
          model: gpt-4o  # Judge model
          threshold: 0.90
      - context_precision:
          k: 10
          threshold: 0.75
      - context_recall:
          threshold: 0.80
      - answer_relevance:
          threshold: 0.85
          
  safety:
    metrics:
      - toxicity:
          model: perspective-api
          threshold: 0.01
      - pii_detection:
          scanner: presidio
          threshold: 0.0  # Zero tolerance
      - bias:
          categories: [gender, race, age]
          threshold: 0.02

  performance:
    metrics:
      - latency_p50:
          threshold: 1500
      - latency_p95:
          threshold: 3000
      - cost_per_query:
          threshold: 0.06

gates:
  pr_merge:
    required_metrics: [groundedness, toxicity, pii_detection]
    regression_tolerance: 0.03
    
  staging_deploy:
    required_metrics: all
    regression_tolerance: 0.02
    min_sample_size: 500
    
  production_deploy:
    required_metrics: all
    regression_tolerance: 0.01
    min_sample_size: 1000
    requires_approval: true
    approvers: [ai-quality-team]
```

---

### Golden Dataset Management

```python
class GoldenDatasetManager:
    """Manages versioned golden datasets with annotation workflow."""
    
    async def create_annotation_task(
        self, dataset_id: str, sample_config: SampleConfig
    ) -> AnnotationTask:
        """Create a new annotation task for dataset expansion."""
        
        # Sample from production traffic
        candidates = await self.sample_production_queries(
            product=sample_config.product,
            timerange=sample_config.timerange,
            strategy=sample_config.strategy,  # stratified, difficulty-based, etc.
            n=sample_config.target_size
        )
        
        # De-duplicate against existing dataset
        new_candidates = await self.deduplicate(candidates, dataset_id)
        
        # Create annotation task with multiple annotators
        task = AnnotationTask(
            dataset_id=dataset_id,
            candidates=new_candidates,
            annotators_per_item=3,  # Triple annotation for quality
            annotation_schema=self._get_schema(dataset_id),
            consensus_strategy="majority_vote",
            min_inter_annotator_agreement=0.75  # Cohen's kappa
        )
        
        return await self.task_store.create(task)
    
    async def finalize_annotations(self, task_id: str) -> DatasetVersion:
        """Finalize annotations and create new dataset version."""
        task = await self.task_store.get(task_id)
        
        # Compute inter-annotator agreement
        iaa = self._compute_iaa(task.annotations)
        if iaa.cohens_kappa < 0.75:
            raise QualityError(
                f"IAA too low: {iaa.cohens_kappa:.2f}. "
                f"Disagreement items need adjudication."
            )
        
        # Resolve consensus
        consensus_items = []
        for item in task.candidates:
            annotations = task.annotations[item.id]
            consensus = self._resolve_consensus(annotations)
            if consensus.confidence >= 0.8:
                consensus_items.append(GoldenItem(
                    query=item.query,
                    expected_answer=consensus.answer,
                    expected_sources=consensus.sources,
                    difficulty=consensus.difficulty,
                    category=consensus.category,
                    annotator_agreement=consensus.agreement_score
                ))
        
        # Create new version (git-like)
        new_version = await self.versioning.create_version(
            dataset_id=task.dataset_id,
            parent_version=await self.versioning.get_latest(task.dataset_id),
            added_items=consensus_items,
            changelog=f"Added {len(consensus_items)} items from annotation task {task_id}"
        )
        
        return new_version
```

---

### Dashboard Design

**Team-Level View:**
- Current quality scores (all metrics, trend arrows)
- Eval run history (pass/fail timeline)
- Regression alerts (which PR caused which drop)
- Dataset coverage analysis (which categories are under-represented)
- Cost tracking (eval compute cost per team)

**System-Level View (Platform Team):**
- Cross-team quality comparison (anonymized leaderboard)
- Platform health (eval job queue depth, p95 execution time)
- Model performance comparison (GPT-4o vs Claude vs Gemini across all teams)
- Monthly quality trends across the org
- Eval infrastructure cost allocation

---

## Portfolio Presentation Tips

### How to Present These Projects in an AI Architect Interview

**1. Start with the Problem, Not the Solution**
```
Bad:  "I built a RAG system using Pinecone, GPT-4, and LangChain."
Good: "Knowledge workers were spending 2.3 hours/day searching for info across 
       5 systems. I designed a unified retrieval system that reduced this to 
       20 minutes while maintaining regulatory compliance."
```

**2. Show Trade-off Reasoning**
```
"We chose post-retrieval ACL filtering over pre-filtered indices because:
 - Pre-filtered would require N indices per permission group (explosion at scale)
 - Post-retrieval adds ~200ms but handles dynamic group membership
 - Defense-in-depth: metadata filter + post-retrieval verification"
```

**3. Include Failure Modes and Mitigations**
```
"The biggest failure mode was permission leakage. A user could potentially see 
document snippets they shouldn't access if the metadata sync was stale. 
We mitigated this with:
 - Real-time permission webhook from identity provider
 - 5-minute cache TTL (not permanent)
 - Post-retrieval re-verification against source system
 - Weekly audit comparing retrieved docs against actual permissions"
```

**4. Quantify Everything**
- Cost per query, cost savings, latency breakdown
- Before/after metrics
- Scale numbers (documents, users, queries/day)

**5. Show Monitoring Maturity**
- What SLOs did you set and why?
- How do you detect quality degradation before users notice?
- What's your incident response for AI failures?

---

## Common Architecture Mistakes in Capstone Projects

### Mistake 1: No Access Control Design
**Problem:** Building RAG without thinking about who can see what.
**Fix:** Design permission model FIRST. It affects chunking, indexing, retrieval, and caching.

### Mistake 2: Over-Engineering Agent Autonomy
**Problem:** Letting agents take irreversible actions without guardrails.
**Fix:** Start with read-only tools. Add write tools with explicit confirmation steps and undo capability. Set dollar/impact limits.

### Mistake 3: No Evaluation Strategy
**Problem:** "We'll add eval later." You won't know if your system works.
**Fix:** Define golden dataset and key metrics before writing application code. Run evals in CI.

### Mistake 4: Ignoring Cost at Design Time
**Problem:** Architecture that costs $50/query in production.
**Fix:** Model token usage and API costs during design. Use tiered approaches (cheap model for simple queries, expensive for complex).

### Mistake 5: Monolithic Agent Design
**Problem:** One giant prompt/agent trying to do everything.
**Fix:** Decompose into specialized agents with clear responsibilities. Easier to evaluate, debug, and improve independently.

### Mistake 6: No Graceful Degradation
**Problem:** System fails completely when LLM provider has an outage.
**Fix:** Design fallback paths: cached responses, simpler models, rule-based defaults, "I don't know" responses.

### Mistake 7: Treating All Documents Equally
**Problem:** Same chunking strategy for code, legal docs, and Slack messages.
**Fix:** Source-specific processing pipelines. Code needs AST-aware chunking. Legal needs section-aware splitting. Slack needs thread aggregation.

### Mistake 8: No Human-in-the-Loop Escape Hatch
**Problem:** Users stuck when AI can't help them.
**Fix:** Every AI interaction must have a clear path to human assistance. Track when users hit this path — it's your improvement signal.
