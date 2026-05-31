# Real-World Examples: Architecture Governance for AI Systems

## Case Study 1: Google/DeepMind AI Architecture Review Board

### Background

Google's AI architecture review process (reconstructed from public talks, papers, and job postings) represents one of the most mature governance structures for AI systems in production.

### Board Structure

```yaml
ai_architecture_review_board:
  name: "AI Production Readiness Review Board"
  
  membership:
    permanent_members:
      - role: "Chair"
        profile: "Distinguished Engineer, 15+ years ML infrastructure"
        veto_power: true
      - role: "ML Platform Lead"
        profile: "Owns Vertex AI / internal ML serving infra"
        veto_power: true
      - role: "Security & Privacy Lead"
        profile: "AI security specialist, adversarial ML background"
        veto_power: true
      - role: "Responsible AI Lead"
        profile: "ML fairness, model cards, ethical review"
        veto_power: true
      - role: "SRE/Reliability Lead"
        profile: "Owns SLOs for ML serving systems"
        veto_power: false
        
    rotating_members:  # 6-month rotation
      - role: "Product Area Representative"
        profile: "Senior engineer from the team being reviewed"
      - role: "Customer/User Advocate"
        profile: "UX researcher or PM focused on user impact"
    
    invited_experts:  # Per-review basis
      - "Domain experts relevant to the specific system"
      - "Legal/compliance when regulations apply"
      
  cadence:
    regular_reviews: "Weekly, Tuesdays 2-4 PM"
    emergency_reviews: "Within 24 hours for critical incidents"
    capacity: "3-4 reviews per session"
    
  decision_criteria:
    must_pass_all:
      - "Model serving meets latency SLO (P99 < threshold)"
      - "Monitoring covers all critical failure modes"
      - "Rollback can complete within 5 minutes"
      - "Bias/fairness evaluation completed with acceptable scores"
      - "Data pipeline has lineage tracking"
      - "No training data compliance issues"
    
    veto_triggers:
      - "Unmitigated bias in protected categories"
      - "No fallback for model failure"
      - "PII in training data without consent framework"
      - "Missing adversarial robustness testing"
      
  decision_outcomes:
    - "APPROVED: Ship to production"
    - "APPROVED_WITH_CONDITIONS: Ship after addressing specific items (< 1 week)"
    - "REVISE_AND_RESUBMIT: Significant changes needed (re-review in 2-4 weeks)"
    - "REJECTED: Fundamental design issues, needs rearchitecture"
```

### Review Process Flow

```
Week -2: Team submits review packet
Week -1: Board members async-review materials, leave questions
Week 0:  Live review (1 hour)
         ├── 15 min: Team presents architecture
         ├── 30 min: Board asks challenge questions
         ├── 10 min: Board deliberates (team steps out)
         └── 5 min:  Decision communicated
Week +1: Team addresses conditions (if any)
```

---

## Case Study 2: Fortune 100 AI Center of Excellence

### Background

A Fortune 100 financial services company (2023-2024) created an AI CoE after three incidents: a customer-facing chatbot hallucinated policy terms, an internal summarization tool leaked PII across departments, and an ML model showed demographic bias in loan recommendations.

### Organization Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Center of Excellence                    │
│                    (Reports to CTO + Chief Risk Officer)      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐  │
│  │ Architecture    │  │ Standards &     │  │ Enablement │  │
│  │ Review Team     │  │ Patterns Team   │  │ Team       │  │
│  │                 │  │                 │  │            │  │
│  │ - Reviews all   │  │ - Publishes     │  │ - Training │  │
│  │   AI projects   │  │   approved      │  │ - Templates│  │
│  │   before prod   │  │   patterns      │  │ - Tooling  │  │
│  │ - 4 architects  │  │ - Maintains     │  │ - Support  │  │
│  │ - Gate control  │  │   model catalog │  │ - 6 people │  │
│  │                 │  │ - 3 engineers   │  │            │  │
│  └─────────────────┘  └─────────────────┘  └────────────┘  │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ Risk & Ethics   │  │ Platform Ops    │                   │
│  │ Team            │  │ Team            │                   │
│  │                 │  │                 │                   │
│  │ - Bias testing  │  │ - Shared infra  │                   │
│  │ - Privacy       │  │ - Model serving │                   │
│  │ - Regulatory    │  │ - Monitoring    │                   │
│  │ - 3 specialists │  │ - 5 engineers   │                   │
│  └─────────────────┘  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Gate Process

Every AI project must pass through gates before production:

```
Gate 0: Intake (Day 1)
  └── AI CoE scores proposal → Go/No-Go/Needs More Info

Gate 1: Design Review (Week 2-3)
  └── Architecture review with patterns team → Approved design

Gate 2: Security & Privacy Review (Week 4-5)  
  └── Threat model, data classification, PII handling → Cleared

Gate 3: Bias & Ethics Review (Week 5-6)
  └── Fairness evaluation, model card, impact assessment → Passed

Gate 4: Production Readiness (Week 6-8)
  └── Load test, monitoring, rollback, runbook → Cleared for launch

Gate 5: Post-Launch Review (Week 12)
  └── Actual metrics vs. predicted, incident review → Continue/Modify/Retire
```

### Outcomes (first year)

| Metric | Result |
|--------|--------|
| Projects reviewed | 47 |
| Approved first pass | 19 (40%) |
| Approved with conditions | 21 (45%) |
| Sent back for redesign | 5 (11%) |
| Rejected entirely | 2 (4%) |
| Production incidents (AI) | 1 (vs. 3 in prior year) |
| Average time through gates | 6.2 weeks |
| Developer satisfaction | 3.8/5 ("rigorous but fair") |

---

## Case Study 3: Architecture Decision Records (ADRs) for AI Systems

### ADR-001: Choosing RAG over Fine-Tuning

```markdown
# ADR-001: Use RAG Pattern for Knowledge-Grounded Responses

**Status:** Accepted  
**Date:** 2024-02-15  
**Deciders:** AI Architecture Team, Product, Legal  

## Context
Our customer support agent needs access to 50,000 product documents that update weekly.
We need to decide between fine-tuning and RAG for knowledge grounding.

## Decision
We will use Retrieval-Augmented Generation (RAG) with a vector database.

## Rationale

| Criterion | Fine-Tuning | RAG | Winner |
|-----------|-------------|-----|--------|
| Knowledge freshness | Days (retrain) | Minutes (re-index) | RAG |
| Hallucination control | Low (no citations) | High (source attribution) | RAG |
| Cost at scale | $$$$ (per retrain) | $$ (inference + retrieval) | RAG |
| Auditability | Cannot trace to source | Can cite exact document | RAG |
| Regulatory (explainability) | Fails | Passes | RAG |

## Consequences
- Need to invest in chunking strategy and embedding pipeline
- Need vector database (additional infrastructure)
- Retrieval quality becomes critical path — must measure recall@10
- Latency increases by ~200ms (acceptable for our use case)

## Alternatives Considered
1. Fine-tuning: Rejected — cannot explain sources, expensive retraining
2. Long-context stuffing: Rejected — 50K docs exceed context window, cost prohibitive
3. Hybrid (RAG + light fine-tune for tone): Deferred to v2
```

### ADR-002: Vector Database Selection

```markdown
# ADR-002: Select Pinecone as Vector Database

**Status:** Accepted  
**Date:** 2024-02-20  
**Deciders:** AI Platform Team, Infrastructure, Finance  

## Context
We need a vector database for our RAG system. Requirements:
- 10M+ vectors (1536 dimensions, OpenAI embeddings)
- P99 query latency < 50ms
- Metadata filtering (by product, region, date)
- SOC 2 Type II compliance (we're in financial services)
- Managed service preferred (team of 3, no capacity for self-hosting)

## Decision
Pinecone Serverless (AWS us-east-1)

## Evaluation Matrix

| Criterion (weight) | Pinecone | Weaviate Cloud | Qdrant Cloud | pgvector |
|-------------------|----------|----------------|--------------|----------|
| Latency P99 (25%) | 35ms ✓ | 42ms ✓ | 38ms ✓ | 120ms ✗ |
| Scale to 10M (20%) | Yes | Yes | Yes | Degraded |
| Metadata filter (15%) | Excellent | Good | Good | SQL ✓ |
| SOC 2 (20%) | Yes | Yes | No | Via RDS ✓ |
| Managed ops (10%) | Serverless | Managed | Managed | Self-manage |
| Cost @ 10M vectors (10%) | $70/mo | $95/mo | $80/mo | $200/mo |
| **Total Score** | **92** | **84** | **75** | **61** |

## Consequences
- Vendor lock-in on Pinecone's API (mitigated: abstraction layer)
- Need to implement embedding pipeline that writes to Pinecone
- Monitoring: Pinecone dashboard + custom latency alerting

## Risks
- Pinecone outage = RAG system degraded (mitigation: fallback to cached top results)
- Cost could grow with scale (mitigation: serverless pricing, archive old vectors)
```

### ADR-003: Model Provider Strategy

```markdown
# ADR-003: Multi-Provider Model Strategy with OpenAI Primary

**Status:** Accepted  
**Date:** 2024-03-01  
**Deciders:** AI CoE, Security, Finance, Legal  

## Context
We need to select LLM provider(s) for production. Single-provider risk is unacceptable
for Tier 1 customer-facing systems.

## Decision
- Primary: Azure OpenAI (GPT-4 Turbo) — all customer-facing workloads
- Secondary: Anthropic Claude 3 (via AWS Bedrock) — failover + specific use cases
- Internal: Self-hosted Llama 3 70B — sensitive data that cannot leave our VPC

## Rationale
- Azure OpenAI: Enterprise agreements, data residency, our existing Azure investment
- Anthropic via Bedrock: Different failure domain, strong at analysis tasks
- Self-hosted: Regulatory requirement for certain PII-heavy workloads

## Architecture
```
                    ┌──────────────────┐
                    │  Model Router    │
                    │  (our service)   │
                    └───────┬──────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │Azure AOAI│  │ Bedrock  │  │ Self-host│
      │ GPT-4T   │  │ Claude 3 │  │ Llama 3  │
      │ Primary  │  │ Failover │  │ PII-safe │
      └──────────┘  └──────────┘  └──────────┘
```

## Consequences
- Need model router service (added complexity)
- Need prompt compatibility layer (different APIs)
- Eval suite must run against all providers
- Cost tracking per provider
```

### ADR-004: Authentication for AI Agents

```markdown
# ADR-004: OAuth 2.0 On-Behalf-Of Flow for User-Facing Agents

**Status:** Accepted  
**Date:** 2024-03-10  

## Context
Our AI agents act on behalf of users (send emails, access files). We need to decide
how agents authenticate to downstream services.

## Options Considered
1. **Shared service account** — Agent uses one credential for all users
2. **User token passthrough** — Agent uses user's original token directly  
3. **On-Behalf-Of (OBO) flow** — Agent exchanges user token for scoped agent token
4. **Agent-specific identity + user context** — Agent has own identity, carries user claim

## Decision
Option 3: OAuth 2.0 On-Behalf-Of flow (RFC 7523)

## Rationale
- Option 1 rejected: No per-user audit trail, excessive privilege
- Option 2 rejected: Token scope too broad, cannot limit agent's access
- Option 3 selected: Per-user identity, scoped permissions, standard protocol
- Option 4 considered: More complex, similar security properties, less tooling support

## Consequences
- Each agent needs app registration with OBO configured
- Token caching strategy needed (per-user token storage)
- Consent experience must be designed (what does user see?)
- Token lifetime management: refresh tokens stored securely
```

### ADR-005: Caching Strategy for LLM Responses

```markdown
# ADR-005: Semantic Cache with 15-Minute TTL for FAQ-Type Queries

**Status:** Accepted  
**Date:** 2024-03-15  

## Context
40% of our support agent queries are near-duplicates ("how do I reset my password?").
LLM calls cost $0.03 each. At 100K queries/day, 40K are cacheable = $1,200/day savings.

## Decision
Implement semantic similarity cache:
- Cache key: embedding of user query
- Cache hit: cosine similarity > 0.95 with cached query
- TTL: 15 minutes (balances freshness vs. cost)
- Cache store: Redis with vector search (RediSearch)

## Consequences
- 40% cost reduction on LLM spend
- Latency for cache hits: 50ms vs. 2000ms (40x improvement)
- Risk: Stale answers if knowledge base updates (mitigated: 15min TTL + cache invalidation on doc update)
- Risk: Semantically similar but contextually different queries return wrong answer
  (mitigated: 0.95 threshold is very strict, + include user metadata in cache key)

## Metrics to Track
- Cache hit rate (target: 35-45%)
- False positive rate (wrong cached answer served) — target: < 0.1%
- Cost savings vs. baseline
```

---

## Case Study 4: Production Readiness Review Checklist

### The Actual Checklist (used by a Series D AI startup)

```yaml
production_readiness_review:
  metadata:
    system_name: ""
    team: ""
    review_date: ""
    reviewer: ""
    target_launch: ""
    risk_tier: ""  # 1-4

  section_1_model_quality:
    - check: "Evaluation suite exists and passes thresholds"
      criteria: "Accuracy/F1/BLEU above team-defined threshold"
      evidence_required: "Eval report with scores + thresholds"
      pass_fail: ""
      
    - check: "Evaluation covers edge cases and failure modes"
      criteria: "Min 50 adversarial test cases, all handled gracefully"
      evidence_required: "Adversarial eval results"
      pass_fail: ""
      
    - check: "Model behavior is consistent across demographic groups"
      criteria: "Performance delta < 5% across protected categories"
      evidence_required: "Disaggregated eval metrics"
      pass_fail: ""
      
    - check: "Hallucination rate measured and acceptable"
      criteria: "Hallucination rate < 2% on held-out test set"
      evidence_required: "Hallucination eval with human review sample"
      pass_fail: ""
      
    - check: "Model card completed"
      criteria: "All sections filled, limitations documented"
      evidence_required: "Link to model card document"
      pass_fail: ""

  section_2_reliability:
    - check: "Load testing completed at 2x expected peak"
      criteria: "System handles 2x peak without degradation"
      evidence_required: "Load test report with P50/P95/P99 latencies"
      pass_fail: ""
      
    - check: "Graceful degradation when model is unavailable"
      criteria: "Fallback behavior defined and tested"
      evidence_required: "Chaos test results (kill model, verify fallback)"
      pass_fail: ""
      
    - check: "Rollback procedure documented and tested"
      criteria: "Can rollback to previous version within 5 minutes"
      evidence_required: "Rollback test recording with timestamps"
      pass_fail: ""
      
    - check: "SLO defined and monitoring in place"
      criteria: "Availability, latency, error rate SLOs defined with alerts"
      evidence_required: "Dashboard screenshot + alert configuration"
      pass_fail: ""
      
    - check: "Rate limiting and backpressure implemented"
      criteria: "System rejects gracefully when overloaded"
      evidence_required: "Rate limit test results"
      pass_fail: ""

  section_3_security:
    - check: "Input validation and injection protection"
      criteria: "Prompt injection test suite passes (min 100 attacks blocked)"
      evidence_required: "Red team report or automated injection test results"
      pass_fail: ""
      
    - check: "Output filtering for sensitive data"
      criteria: "PII/secrets never appear in responses (DLP scan)"
      evidence_required: "DLP test results on 1000+ sample outputs"
      pass_fail: ""
      
    - check: "Authentication and authorization"
      criteria: "All endpoints authenticated, RBAC enforced"
      evidence_required: "Security review sign-off"
      pass_fail: ""
      
    - check: "Data encryption at rest and in transit"
      criteria: "TLS 1.3, AES-256 at rest, no plaintext secrets"
      evidence_required: "Infrastructure security scan"
      pass_fail: ""

  section_4_observability:
    - check: "Structured logging for all LLM interactions"
      criteria: "Every prompt/response logged with correlation IDs"
      evidence_required: "Log query showing full request lifecycle"
      pass_fail: ""
      
    - check: "Cost tracking per request/user/feature"
      criteria: "Token usage tracked, cost dashboard available"
      evidence_required: "Cost dashboard screenshot"
      pass_fail: ""
      
    - check: "Drift detection for model quality"
      criteria: "Automated eval runs daily, alerts on degradation > 5%"
      evidence_required: "Drift detection pipeline + alert config"
      pass_fail: ""
      
    - check: "User feedback collection mechanism"
      criteria: "Thumbs up/down + optional text on every response"
      evidence_required: "Feedback UI screenshot + storage"
      pass_fail: ""

  section_5_operational:
    - check: "Runbook exists for common failure scenarios"
      criteria: "Min 5 runbook entries covering top failure modes"
      evidence_required: "Link to runbook"
      pass_fail: ""
      
    - check: "On-call rotation defined"
      criteria: "Team has on-call schedule covering this system"
      evidence_required: "PagerDuty/OpsGenie configuration"
      pass_fail: ""
      
    - check: "Cost guardrails in place"
      criteria: "Hard spending cap, alerts at 50%, 75%, 90%"
      evidence_required: "Budget alert configuration"
      pass_fail: ""

  decision:
    result: ""  # PASS / CONDITIONAL_PASS / FAIL
    conditions: []
    blocking_issues: []
    next_review_date: ""
```

---

## Case Study 5: Standards Library — Published AI Architecture Standards

### How a Platform Team Publishes Standards

```yaml
# ai-standards-catalog.yaml
# Published at: https://standards.internal.company.com/ai/

standards:
  - id: "AI-STD-001"
    title: "Approved LLM Models for Production"
    version: "3.1"
    last_updated: "2024-03-01"
    owner: "AI Platform Team"
    enforcement: "automated"  # Blocked in CI/CD if violated
    
    content:
      approved_models:
        tier_1_customer_facing:
          - "azure-openai/gpt-4-turbo-2024-04-09"
          - "azure-openai/gpt-4o-2024-05-13"
          - "anthropic/claude-3.5-sonnet (via Bedrock)"
        tier_2_internal_tools:
          - "All tier 1 models"
          - "azure-openai/gpt-3.5-turbo-0125"
          - "self-hosted/llama-3-70b-instruct"
        tier_3_experimentation:
          - "Any model (non-production only)"
          
      prohibited:
        - "Any model from providers without SOC 2 / BAA"
        - "Any model < 6 months old without eval completion"
        - "Open-source models without license review"
        
      exception_process: "Submit AI-EXC form, requires VP + Security approval"

  - id: "AI-STD-002"
    title: "Required Guardrails for AI Systems"
    version: "2.0"
    enforcement: "automated"
    
    content:
      all_systems_must_have:
        - "Input length limit (max 10,000 tokens)"
        - "Output length limit (max 4,000 tokens)"
        - "Rate limiting per user (max 100 req/min)"
        - "Cost cap per request ($0.50 max)"
        - "Timeout (30 seconds max for synchronous)"
        - "Content filtering on output (PII, toxicity)"
        
      customer_facing_additionally:
        - "Prompt injection detection layer"
        - "Hallucination detection (grounding check)"
        - "Source attribution for factual claims"
        - "Disclaimer when confidence is low"
        - "Human escalation path available"
        
      systems_handling_pii:
        - "Data minimization in prompts"
        - "No PII in logs (tokenize before logging)"
        - "Consent verification before processing"
        - "Right-to-deletion support"

  - id: "AI-STD-003"
    title: "AI System Monitoring Requirements"
    version: "1.5"
    enforcement: "review_gate"
    
    content:
      required_metrics:
        - metric: "request_latency_p99"
          alert_threshold: "SLO + 20%"
        - metric: "error_rate"
          alert_threshold: "> 1% over 5 minutes"
        - metric: "token_cost_per_request"
          alert_threshold: "> 2x 7-day average"
        - metric: "hallucination_rate"
          alert_threshold: "> 5% (measured by grounding check)"
        - metric: "user_satisfaction_score"
          alert_threshold: "< 3.5/5 rolling 24h average"
      
      required_dashboards:
        - "Request volume and latency"
        - "Error rate by type"
        - "Cost (daily, weekly, monthly)"
        - "Quality metrics (eval scores over time)"
        - "User feedback distribution"
```

### Enforcement via CI/CD

```yaml
# .github/workflows/ai-standards-check.yml
name: AI Standards Compliance Check

on: [pull_request]

jobs:
  check-model-compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Scan for model references
        run: |
          # Check all config files for model IDs
          python scripts/check_approved_models.py \
            --config-dir ./config \
            --standards-url https://standards.internal/ai/AI-STD-001.yaml
            
      - name: Check guardrail presence
        run: |
          # Verify required guardrails are configured
          python scripts/check_guardrails.py \
            --service-config ./service.yaml \
            --tier $(cat ./RISK_TIER)
            
      - name: Check monitoring configuration
        run: |
          # Verify all required metrics and alerts exist
          python scripts/check_monitoring.py \
            --dashboards-dir ./monitoring/ \
            --alerts-dir ./alerts/
```

---

## Case Study 6: Risk Tiering — 4 Levels of Governance

### Tier Classification Framework

```
┌────────────────────────────────────────────────────────────────────┐
│                    AI Risk Tier Classification                       │
├──────────┬─────────────┬────────────────┬──────────────────────────┤
│  Tier    │ Risk Level  │ Example        │ Governance Required       │
├──────────┼─────────────┼────────────────┼──────────────────────────┤
│ Tier 1   │ Low         │ Internal code  │ Self-service,            │
│          │             │ completion,    │ automated checks only    │
│          │             │ doc summary    │                          │
├──────────┼─────────────┼────────────────┼──────────────────────────┤
│ Tier 2   │ Medium      │ Internal       │ Peer review +            │
│          │             │ chatbot,       │ automated checks         │
│          │             │ data analysis  │                          │
├──────────┼─────────────┼────────────────┼──────────────────────────┤
│ Tier 3   │ High        │ Customer-      │ Architecture review +    │
│          │             │ facing agent,  │ security review +        │
│          │             │ content gen    │ bias evaluation          │
├──────────┼─────────────┼────────────────┼──────────────────────────┤
│ Tier 4   │ Critical    │ Financial      │ Full board review +      │
│          │             │ decisions,     │ legal + external audit   │
│          │             │ medical, legal │ + ongoing monitoring     │
└──────────┴─────────────┴────────────────┴──────────────────────────┘
```

### Scoring Rubric for Tier Assignment

```yaml
risk_scoring:
  dimensions:
    autonomy_level:
      1: "Suggestions only (human always decides)"
      2: "Executes with confirmation"
      3: "Executes autonomously, human can override"
      4: "Executes autonomously, difficult to reverse"
      
    data_sensitivity:
      1: "Public data only"
      2: "Internal/confidential data"
      3: "PII or financial data"
      4: "Regulated data (HIPAA, PCI, classified)"
      
    blast_radius:
      1: "Affects single user"
      2: "Affects team/department"
      3: "Affects all customers"
      4: "Affects company reputation / regulatory standing"
      
    reversibility:
      1: "Fully reversible (undo button)"
      2: "Reversible with effort (restore from backup)"
      3: "Partially reversible (some data loss possible)"
      4: "Irreversible (sent communication, financial transfer)"

  tier_assignment:
    tier_1: "Max score across all dimensions = 1"
    tier_2: "Max score across all dimensions = 2"
    tier_3: "Max score across all dimensions = 3"
    tier_4: "Any dimension scores 4"
```

### Governance Requirements Per Tier

```yaml
tier_1_low:
  pre_launch:
    - "Automated standards check (CI/CD) passes"
    - "Basic eval suite exists and passes"
  ongoing:
    - "Standard monitoring dashboards"
    - "Quarterly self-assessment"
  review_time: "0 days (self-service)"
  
tier_2_medium:
  pre_launch:
    - "Everything in Tier 1"
    - "Peer architecture review (async, 1 reviewer)"
    - "Security questionnaire completed"
    - "Cost projection documented"
  ongoing:
    - "Monthly quality metrics review"
    - "Incident postmortem within 48 hours"
  review_time: "3-5 days"
  
tier_3_high:
  pre_launch:
    - "Everything in Tier 2"
    - "Full architecture review (live, with AI CoE)"
    - "Security penetration testing"
    - "Bias/fairness evaluation with report"
    - "Load testing at 2x peak"
    - "Rollback procedure tested"
    - "Legal/compliance sign-off"
  ongoing:
    - "Weekly quality metrics review"
    - "Monthly bias re-evaluation"
    - "Quarterly full security assessment"
    - "Continuous drift monitoring with auto-alerts"
  review_time: "2-4 weeks"
  
tier_4_critical:
  pre_launch:
    - "Everything in Tier 3"
    - "Board-level review with VP/C-suite sponsor"
    - "External third-party audit"
    - "Regulatory compliance documentation"
    - "Insurance/liability review"
    - "Human-in-the-loop design validated"
    - "Adversarial red team exercise"
    - "Full disaster recovery test"
  ongoing:
    - "Daily quality monitoring with human review"
    - "Monthly external audit"
    - "Quarterly regulatory compliance check"
    - "Annual full system re-certification"
  review_time: "4-8 weeks"
```

---

## Case Study 7: Use-Case Intake Process

### Intake Form

```yaml
# AI Project Intake Form — submit at ai-intake.internal.company.com

section_1_basics:
  project_name: ""
  team: ""
  sponsor: ""  # VP or above
  target_launch_date: ""
  brief_description: ""  # 2-3 sentences

section_2_business_value:
  problem_statement: ""
  who_benefits: ""  # Users, customers, internal
  success_metrics:
    - metric: ""
      current_baseline: ""
      target: ""
  estimated_annual_value: ""  # $ or time saved
  alternatives_considered: ""  # Why AI vs. traditional?

section_3_technical:
  ai_pattern: ""  # RAG, agent, classification, generation, summarization
  model_requirements: ""  # What capabilities needed
  data_sources: []
  expected_request_volume: ""  # per day
  latency_requirement: ""  # P99
  integration_points: []  # What systems does it connect to?

section_4_risk:
  data_classification: ""  # Public, Internal, Confidential, Restricted
  contains_pii: true/false
  customer_facing: true/false
  makes_decisions_autonomously: true/false
  financial_impact_possible: true/false
  regulated_domain: true/false  # Healthcare, finance, legal
  
section_5_readiness:
  team_ml_experience: ""  # None, Basic, Experienced, Expert
  existing_infrastructure: ""  # What you already have
  estimated_effort: ""  # Person-months
  dependencies: []  # Other teams/systems needed
```

### Scoring Rubric (used by AI CoE to prioritize)

```yaml
scoring_rubric:
  business_value:  # 0-30 points
    annual_value_over_1m: 30
    annual_value_500k_1m: 25
    annual_value_100k_500k: 20
    annual_value_under_100k: 10
    
  feasibility:  # 0-25 points
    proven_pattern_team_experienced: 25
    proven_pattern_team_learning: 20
    novel_pattern_team_experienced: 15
    novel_pattern_team_learning: 5
    
  risk_inverse:  # 0-25 points (lower risk = more points)
    tier_1: 25
    tier_2: 20
    tier_3: 10
    tier_4: 5
    
  strategic_alignment:  # 0-20 points
    top_3_company_priority: 20
    departmental_priority: 15
    team_initiative: 10
    exploration: 5

  # Total: /100
  # Score >= 70: Fast-track
  # Score 50-69: Standard queue  
  # Score 30-49: Needs stronger justification
  # Score < 30: Likely redirect to non-AI solution
```

---

## Case Study 8: Architecture Review Meeting — 1 Hour

### Agenda

```
AI Architecture Review — 60 Minutes
System: "CustomerInsight Agent" (Tier 3)
Team: Customer Analytics
Date: 2024-03-19, 2:00 PM

─────────────────────────────────────────────────────────────
0:00 - 0:05   Setup & Context (Chair)
               - Introduce system, risk tier, reviewers
               - State decision needed today
               
0:05 - 0:20   Architecture Presentation (Team)
               - Problem & approach (3 min)
               - Architecture diagram walkthrough (5 min)
               - Data flow & security model (4 min)
               - Eval results & quality metrics (3 min)
               
0:20 - 0:50   Challenge Questions (Board)
               - Round 1: Reliability & Scale
               - Round 2: Security & Privacy  
               - Round 3: Quality & Safety
               - Round 4: Operational Readiness
               
0:50 - 0:55   Deliberation (Board only, team steps out)

0:55 - 1:00   Decision & Next Steps
─────────────────────────────────────────────────────────────
```

### Standard Challenge Questions

```yaml
reliability_questions:
  - "What happens when the LLM provider has an outage?"
  - "Show me your load test results at 2x peak."
  - "How long does rollback take? Have you tested it?"
  - "What's your error budget and how do you track it?"

security_questions:
  - "Walk me through a prompt injection attempt against your system."
  - "What PII flows through the LLM? How is it protected?"
  - "How do you prevent the model from revealing system prompts?"
  - "What's the authentication model for agent-to-service calls?"

quality_questions:
  - "What's your hallucination rate and how do you measure it?"
  - "Show me 5 failure cases from your eval suite."
  - "How do you detect quality degradation in production?"
  - "What's your plan when the model version is deprecated?"

operational_questions:
  - "Who is on call for this system? Show me the PagerDuty config."
  - "What does your runbook say to do when quality drops below SLO?"
  - "What's your monthly cost and what's the cap?"
  - "How do you handle a sudden 10x traffic spike?"
```

### Decision Record Template

```markdown
## Review Decision: CustomerInsight Agent

**Date:** 2024-03-19  
**Decision:** APPROVED WITH CONDITIONS  

**Conditions (must complete before launch):**
1. Add circuit breaker for LLM provider (currently no fallback) — Due: March 26
2. Implement PII stripping before prompt construction — Due: March 26
3. Add cost alerting at 75% and 90% of monthly cap — Due: March 22

**Observations (non-blocking, address within 30 days):**
- Consider adding semantic caching for repeated queries
- Eval suite should include more multilingual test cases
- Runbook entry for "model quality degradation" is thin — expand it

**What went well:**
- Thorough eval methodology with human review sample
- Clean separation of concerns in architecture
- Team clearly understands failure modes

**Next review:** Post-launch check-in at Week 4 (April 16)
```

---

## Case Study 9: Governance Automation in CI/CD

### Pipeline Architecture

```yaml
# Automated governance checks run on every PR to AI services

governance_pipeline:
  stage_1_static_analysis:
    - name: "model-allowlist-check"
      what: "Scans config for model IDs, verifies against approved list"
      blocks_merge: true
      
    - name: "guardrail-presence-check"  
      what: "Verifies required guardrails are configured per risk tier"
      blocks_merge: true
      
    - name: "secret-scan"
      what: "Ensures no API keys, tokens in code"
      blocks_merge: true

  stage_2_eval_validation:
    - name: "eval-suite-exists"
      what: "Verifies eval directory has test cases"
      blocks_merge: true
      
    - name: "eval-threshold-check"
      what: "Runs eval suite, verifies scores meet thresholds"
      blocks_merge: true
      min_test_cases: 50
      
    - name: "eval-regression-check"
      what: "Compares eval scores to main branch, flags regressions > 2%"
      blocks_merge: true

  stage_3_security:
    - name: "prompt-injection-test"
      what: "Runs standard injection attack suite"
      blocks_merge: true
      min_attacks_blocked: "95%"
      
    - name: "output-pii-scan"
      what: "Generates 100 sample outputs, scans for PII leakage"
      blocks_merge: true
      max_pii_leakage: "0%"

  stage_4_cost_governance:
    - name: "cost-estimation"
      what: "Estimates monthly cost based on expected traffic"
      blocks_merge: false  # Warning only
      warning_threshold: "$5000/month"
      
    - name: "token-budget-check"
      what: "Verifies max_tokens is set and reasonable"
      blocks_merge: true
```

### Example: Automated Model Allowlist Check

```python
# scripts/check_approved_models.py
import yaml
import sys
from pathlib import Path

STANDARDS_URL = "https://standards.internal/ai/AI-STD-001.yaml"

def check_models(config_dir: str):
    """Scan all config files for model references and validate against allowlist."""
    
    standards = fetch_standards(STANDARDS_URL)
    risk_tier = int(Path("RISK_TIER").read_text().strip())
    
    approved = set()
    if risk_tier <= 2:
        approved = set(standards["approved_models"]["tier_2_internal_tools"])
    else:
        approved = set(standards["approved_models"]["tier_1_customer_facing"])
    
    violations = []
    
    for config_file in Path(config_dir).rglob("*.yaml"):
        config = yaml.safe_load(config_file.read_text())
        models_found = extract_model_references(config)
        
        for model in models_found:
            if model not in approved:
                violations.append({
                    "file": str(config_file),
                    "model": model,
                    "approved_list": list(approved)
                })
    
    if violations:
        print("❌ MODEL COMPLIANCE VIOLATIONS:")
        for v in violations:
            print(f"  File: {v['file']}")
            print(f"  Model: {v['model']} (NOT APPROVED for Tier {risk_tier})")
            print(f"  Approved models: {v['approved_list']}")
            print()
        sys.exit(1)
    
    print(f"✓ All models approved for Tier {risk_tier}")
    sys.exit(0)
```

---

## Case Study 10: Exception Process

### Exception Request Form

```yaml
# AI Standards Exception Request

request_metadata:
  requestor: "Jane Smith, Staff Engineer"
  team: "Search Relevance"
  date: "2024-03-20"
  standard_id: "AI-STD-001"  # Which standard needs exception
  specific_requirement: "Must use approved model for Tier 3"

exception_details:
  what_you_want_to_do: |
    Use Mistral Large (via Azure AI) for our search re-ranking system.
    This model is not currently on the Tier 3 approved list.
    
  why_standard_cannot_be_met: |
    Our benchmarks show Mistral Large outperforms GPT-4 Turbo by 12% on our 
    specific re-ranking task while costing 60% less. The performance difference
    is significant for user experience (search relevance directly impacts revenue).
    
  risk_mitigation: |
    - Mistral Large is hosted on Azure AI (same compliance as Azure OpenAI)
    - We have run full eval suite: passes all thresholds
    - We have run bias evaluation: no demographic disparities
    - We will maintain GPT-4 Turbo as hot fallback
    - We commit to migrating if Mistral Large shows quality issues
    
  duration_requested: "6 months (until September 2024 re-evaluation)"
  
  rollback_plan: |
    Configuration flag to switch to GPT-4 Turbo in < 5 minutes.
    No code changes required for rollback.

approval_chain:
  - approver: "AI CoE Architecture Lead"
    status: "pending"
    
  - approver: "Security Lead (for new provider assessment)"
    status: "pending"
    
  - approver: "VP Engineering (sponsor)"
    status: "pending"
```

### Exception Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Submitted│───>│ Under    │───>│ Approved │───>│ Active   │
│          │    │ Review   │    │          │    │          │
└──────────┘    └────┬─────┘    └──────────┘    └────┬─────┘
                     │                                │
                     ▼                                ▼
                ┌──────────┐                    ┌──────────┐
                │ Denied   │                    │ Expired  │
                │(with     │                    │(must     │
                │ guidance)│                    │ renew or │
                └──────────┘                    │ comply)  │
                                                └──────────┘

Rules:
- All exceptions have sunset dates (max 6 months)
- 30 days before expiry: automated reminder to renew or comply
- Expired exceptions: system automatically blocks in next CI run
- No exception can be "permanent" — forces periodic re-evaluation
```

---

## Case Study 11: Governance Metrics Dashboard

### Measuring if Governance is Working

```yaml
governance_effectiveness_metrics:
  
  speed_metrics:
    - name: "Time to First Review"
      definition: "Days from intake submission to first architecture review"
      target: "< 10 business days"
      current: "7.2 days"
      trend: "improving"
      
    - name: "Time to Production"
      definition: "Days from intake to production deployment"
      target: "Tier 1: < 5 days, Tier 2: < 15, Tier 3: < 30, Tier 4: < 60"
      current: "Tier 1: 2d, Tier 2: 11d, Tier 3: 24d, Tier 4: 52d"
      trend: "stable"
      
    - name: "Review Cycle Time"
      definition: "Days from submission to decision (excluding team work time)"
      target: "< 5 business days"
      current: "3.8 days"
      trend: "improving"

  quality_metrics:
    - name: "First-Pass Approval Rate"
      definition: "% of reviews approved without conditions on first attempt"
      target: "40-60% (too high = rubber stamp, too low = unclear standards)"
      current: "43%"
      trend: "healthy"
      
    - name: "Post-Launch Incident Rate"
      definition: "AI-related incidents per system per quarter"
      target: "< 0.5 incidents/system/quarter"
      current: "0.3"
      trend: "improving"
      
    - name: "Governance Escape Rate"
      definition: "AI systems found in production that bypassed governance"
      target: "0"
      current: "2 (both addressed within 1 week of discovery)"
      trend: "watch"

  satisfaction_metrics:
    - name: "Developer Satisfaction with Governance"
      definition: "Quarterly survey, 1-5 scale"
      target: "> 3.5/5"
      current: "3.8/5"
      trend: "stable"
      survey_feedback:
        positive: "Clear standards, helpful review feedback, reasonable timelines"
        negative: "Too many forms, some reviews feel checkbox-y"
      
    - name: "Standards Clarity Score"
      definition: "% of developers who report standards are 'clear' or 'very clear'"
      target: "> 80%"
      current: "76%"
      action: "Rewriting AI-STD-002 with more examples"

  compliance_metrics:
    - name: "CI/CD Governance Check Pass Rate"
      definition: "% of PRs that pass all automated governance checks on first push"
      target: "> 85% (shows developers internalized standards)"
      current: "82%"
      trend: "improving"
      
    - name: "Exception Rate"  
      definition: "% of projects requiring standards exceptions"
      target: "< 15% (too high = standards wrong, too low = too easy)"
      current: "11%"
      trend: "healthy"
      
    - name: "Exception Expiry Compliance"
      definition: "% of expired exceptions that were renewed OR brought into compliance"
      target: "100%"
      current: "94% (1 exception required forced remediation)"
      trend: "watch"
```

### Monthly Governance Report (executive summary format)

```markdown
## AI Governance Monthly Report — March 2024

### Key Numbers
| Metric | This Month | Last Month | Trend |
|--------|-----------|------------|-------|
| New AI projects submitted | 8 | 6 | ↑ |
| Reviews completed | 7 | 5 | ↑ |
| Approved (first pass) | 3 | 2 | → |
| Approved with conditions | 3 | 2 | → |
| Sent back for redesign | 1 | 1 | → |
| AI production incidents | 0 | 1 | ↓ ✓ |
| Avg review cycle time | 3.8d | 4.1d | ↓ ✓ |
| Developer satisfaction | 3.8/5 | 3.7/5 | ↑ |

### Highlights
- Zero production incidents (first clean month in 6 months)
- Automated model allowlist check caught 3 violations before merge
- New "RAG Reference Architecture" template reduced review time by 40% for RAG projects

### Concerns
- 2 shadow AI systems discovered (teams using OpenAI API directly without governance)
  - Action: Blocked at network level, teams onboarded to proper process
- Exception for Mistral Large approaching expiry — team must decide by April 15

### Next Month Focus
- Publish "Agent Architecture" reference template
- Reduce Tier 3 review time from 24d to 20d
- Address developer feedback on form complexity
```

---

## Summary: Governance That Enables Rather Than Blocks

The most effective AI governance programs share these traits:

| Principle | Implementation |
|-----------|---------------|
| Speed proportional to risk | Tier 1 = self-service; Tier 4 = full board |
| Automation over process | CI/CD checks catch 80% of issues before review |
| Clear standards | Published, versioned, with examples |
| Feedback loops | Measure satisfaction, adjust based on data |
| Exceptions are normal | Codified process, not bureaucratic punishment |
| Review adds value | Teams leave with better architectures, not just approval |
| Sunset everything | Standards, exceptions, approvals all have expiry dates |
