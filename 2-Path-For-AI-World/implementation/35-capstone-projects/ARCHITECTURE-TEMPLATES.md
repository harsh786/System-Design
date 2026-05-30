# Architecture Templates for AI Systems

Reusable templates for documenting, evaluating, and operating AI systems at staff architect level.

---

## 1. Tool Contract Template (YAML)

```yaml
# Tool Contract: Defines the interface, behavior, and guarantees of an AI tool
tool:
  name: "knowledge_base_search"
  version: "1.2.0"
  owner: "platform-team"
  description: |
    Search the enterprise knowledge base using hybrid retrieval.
    Returns ranked document chunks with relevance scores.

interface:
  input:
    type: object
    required: [query]
    properties:
      query:
        type: string
        description: "Natural language search query"
        max_length: 2000
      top_k:
        type: integer
        default: 5
        min: 1
        max: 50
      filters:
        type: object
        properties:
          source:
            type: string
            enum: [wiki, confluence, slack, docs]
          date_range:
            type: object
            properties:
              start: { type: string, format: date }
              end: { type: string, format: date }
          tags:
            type: array
            items: { type: string }

  output:
    type: object
    properties:
      results:
        type: array
        items:
          type: object
          properties:
            chunk_id: { type: string }
            content: { type: string }
            score: { type: number, min: 0, max: 1 }
            source: { type: string }
            metadata: { type: object }
      total_found: { type: integer }
      latency_ms: { type: number }

behavior:
  idempotent: true
  cacheable: true
  cache_ttl_seconds: 300
  max_retries: 3
  timeout_ms: 5000
  rate_limit:
    requests_per_minute: 100
    tokens_per_minute: 50000

  error_handling:
    - code: INVALID_QUERY
      description: "Query is empty or exceeds max length"
      action: "Return 400 with validation details"
    - code: TIMEOUT
      description: "Search exceeded timeout"
      action: "Return partial results with warning"
    - code: SERVICE_UNAVAILABLE
      description: "Vector store is unavailable"
      action: "Return 503, circuit breaker triggers after 5 failures"

security:
  authentication: "Bearer token (service-to-service)"
  authorization: "Tool-level permission + document ACLs"
  pii_handling: "Never log query content; mask PII in results"
  audit_logging: true

observability:
  metrics:
    - name: tool_latency_ms
      type: histogram
      labels: [tool_name, status]
    - name: tool_requests_total
      type: counter
      labels: [tool_name, status, source]
    - name: tool_result_count
      type: histogram
      labels: [tool_name]
  logging:
    level: INFO
    fields: [request_id, tenant_id, latency_ms, result_count]
  tracing:
    span_name: "tool.knowledge_base_search"
    attributes: [query_length, top_k, filter_count]

sla:
  availability: 99.9%
  p50_latency_ms: 100
  p95_latency_ms: 500
  p99_latency_ms: 2000
  max_result_staleness: 60s

testing:
  unit_tests: "tests/tools/test_knowledge_base_search.py"
  integration_tests: "tests/integration/test_kb_tool_e2e.py"
  load_test_profile: "100 RPS sustained, 500 RPS burst"
  golden_queries: "eval/golden/kb_search_queries.json"
```

---

## 2. Agent Card Template (YAML)

```yaml
# Agent Card: Capability descriptor for agent discovery (A2A protocol)
agent:
  id: "urn:company:agents:research-assistant-v2"
  name: "Research Assistant"
  version: "2.1.0"
  description: |
    Answers complex research questions by decomposing queries,
    searching multiple knowledge bases, and synthesizing findings
    with citations.

  owner:
    team: "ai-platform"
    contact: "ai-platform@company.com"
    oncall: "https://pagerduty.com/services/ai-platform"

capabilities:
  - id: "research_query"
    description: "Answer research questions with cited sources"
    input_schema:
      type: object
      required: [question]
      properties:
        question: { type: string, max_length: 5000 }
        depth: { type: string, enum: [quick, standard, deep] }
        sources: { type: array, items: { type: string } }
    output_schema:
      type: object
      properties:
        answer: { type: string }
        citations: { type: array }
        confidence: { type: number }
        follow_up_questions: { type: array }

  - id: "summarize_document"
    description: "Summarize a document at specified detail level"
    input_schema:
      type: object
      required: [document_id]
      properties:
        document_id: { type: string }
        detail_level: { type: string, enum: [brief, standard, detailed] }

  - id: "compare_topics"
    description: "Compare and contrast multiple topics"
    input_schema:
      type: object
      required: [topics]
      properties:
        topics: { type: array, min_items: 2, max_items: 5 }
        dimensions: { type: array, items: { type: string } }

communication:
  protocol: "A2A/1.0"
  transport: "HTTPS"
  endpoint: "https://agents.company.com/research-assistant/v2"
  authentication:
    type: "mTLS"
    issuer: "https://ca.company.com"
  message_format: "application/json"
  streaming: true
  max_message_size_bytes: 1048576  # 1MB

lifecycle:
  states: [submitted, working, review, complete, failed, cancelled]
  timeout_seconds: 300
  heartbeat_interval_seconds: 30
  max_retries: 2

constraints:
  max_concurrent_tasks: 10
  max_tokens_per_task: 50000
  max_cost_per_task_usd: 0.50
  supported_languages: [en, es, fr, de, ja]
  data_residency: [us-east-1, eu-west-1]

dependencies:
  tools:
    - knowledge_base_search
    - sql_query
    - web_search
  agents:
    - "urn:company:agents:citation-verifier-v1"
  models:
    primary: "claude-sonnet-4-20250514"
    fallback: "gpt-4o"

evaluation:
  metrics_endpoint: "https://agents.company.com/research-assistant/v2/metrics"
  golden_dataset: "eval/research_assistant_golden_v2.json"
  minimum_scores:
    task_completion: 0.92
    faithfulness: 0.88
    citation_accuracy: 0.85
  last_eval_date: "2025-01-15"
  last_eval_score: 0.91

discovery:
  tags: [research, qa, knowledge, citations]
  domain: "enterprise_knowledge"
  maturity: "production"  # experimental, beta, production, deprecated
  registration_url: "https://registry.company.com/agents/research-assistant-v2"
```

---

## 3. Model Risk Sheet Template (YAML)

```yaml
# Model Risk Sheet: Risk assessment for AI model deployment
model_risk_assessment:
  model_id: "rag-system-v2.1"
  assessment_date: "2025-01-20"
  assessor: "AI Architecture Review Board"
  review_status: "approved_with_conditions"
  next_review_date: "2025-04-20"

model_overview:
  name: "Enterprise RAG System v2.1"
  type: "Retrieval-Augmented Generation"
  purpose: "Answer employee questions using internal documentation"
  users: "All employees via Slack bot and web UI"
  decisions_supported: "Information lookup, not decision-making"
  autonomy_level: "advisory"  # advisory, semi-autonomous, autonomous

risk_classification:
  tier: 2  # 1=low, 2=medium, 3=high, 4=critical
  justification: |
    Medium risk: provides information to employees but does not make
    autonomous decisions. Incorrect answers could waste time but
    unlikely to cause direct harm.

  risk_factors:
    pii_exposure:
      score: 3  # 1-5
      mitigation: "ACL-based retrieval filtering, PII detection guardrail"
    decision_autonomy:
      score: 1
      mitigation: "Advisory only, always shows sources"
    blast_radius:
      score: 3
      mitigation: "Rate limiting, circuit breaker, rollback capability"
    reversibility:
      score: 5
      mitigation: "Fully reversible - can disable at any time"
    bias_potential:
      score: 2
      mitigation: "Grounded in documents, limited generation freedom"
    data_sensitivity:
      score: 3
      mitigation: "Internal docs only, no customer data in retrieval"

  overall_risk_score: 2.8  # Weighted average

performance_metrics:
  current:
    faithfulness: 0.89
    answer_relevance: 0.85
    retrieval_mrr: 0.78
    p95_latency_ms: 1200
    error_rate: 0.02
    cost_per_query: 0.018
  thresholds:
    faithfulness_min: 0.85
    answer_relevance_min: 0.80
    error_rate_max: 0.05
    latency_p95_max_ms: 3000
  monitoring:
    dashboard: "https://grafana.company.com/d/rag-system"
    alerting: "PagerDuty: ai-platform-oncall"
    eval_frequency: "weekly"

data_governance:
  training_data: "N/A (uses pre-trained models)"
  retrieval_corpus:
    sources: [confluence, sharepoint, internal_wiki, slack_public]
    update_frequency: "hourly incremental, daily full"
    retention_policy: "Matches source document retention"
    data_classification: "Internal + Confidential (ACL-gated)"
  logging:
    what_is_logged: "Query, response, sources, latency, user_id"
    what_is_not_logged: "Full document content, user session history"
    retention: "90 days"
    access: "AI team + security team"

failure_modes:
  - mode: "Hallucination"
    likelihood: "medium"
    impact: "low-medium"
    detection: "Faithfulness metric < 0.85 triggers alert"
    mitigation: "Citations shown, confidence score displayed"
  - mode: "ACL bypass"
    likelihood: "very low"
    impact: "high"
    detection: "ACL audit log anomaly detection"
    mitigation: "Pre-filter enforcement, quarterly audit"
  - mode: "Prompt injection"
    likelihood: "low"
    impact: "medium"
    detection: "Guardrail pattern matching"
    mitigation: "Input sanitization, output validation"
  - mode: "Provider outage"
    likelihood: "low"
    impact: "medium"
    detection: "Circuit breaker, health checks"
    mitigation: "Multi-provider fallback"

compliance:
  gdpr_compliant: true
  data_residency: "EU (eu-west-1)"
  right_to_erasure: "Document deletion propagates to vector store within 24h"
  dpia_completed: true
  dpia_reference: "DPIA-2025-042"

approval_conditions:
  - "Weekly eval runs must maintain faithfulness > 0.85"
  - "ACL audit must pass quarterly review"
  - "Incident response runbook must be maintained"
  - "User feedback mechanism must remain active"
```

---

## 4. Architecture Decision Record (ADR) Template

```markdown
# ADR-{NUMBER}: {TITLE}

## Status
{Proposed | Accepted | Deprecated | Superseded by ADR-XXX}

## Date
YYYY-MM-DD

## Context
What is the issue that we're seeing that is motivating this decision or change?
Include relevant technical context, constraints, and business requirements.

## Decision Drivers
- {driver 1, e.g., performance requirement}
- {driver 2, e.g., cost constraint}
- {driver 3, e.g., team capability}
- {driver 4, e.g., operational complexity}

## Considered Options
1. **{Option A}** - Brief description
2. **{Option B}** - Brief description
3. **{Option C}** - Brief description

## Decision
We will use **{chosen option}** because {justification}.

## Comparison Matrix

| Criteria (weight)     | Option A | Option B | Option C |
|-----------------------|----------|----------|----------|
| Performance (30%)     | ⭐⭐⭐   | ⭐⭐     | ⭐⭐⭐⭐  |
| Cost (25%)            | ⭐⭐⭐⭐  | ⭐⭐⭐   | ⭐⭐     |
| Complexity (20%)      | ⭐⭐⭐   | ⭐⭐⭐⭐  | ⭐⭐     |
| Team familiarity (15%)| ⭐⭐⭐⭐  | ⭐⭐     | ⭐⭐⭐   |
| Migration path (10%)  | ⭐⭐⭐   | ⭐⭐⭐   | ⭐⭐⭐⭐  |
| **Weighted Score**    | **3.25** | **2.95** | **3.00** |

## Consequences

### Positive
- {consequence 1}
- {consequence 2}

### Negative
- {consequence 1}
- {consequence 2}

### Risks
- {risk 1} — Mitigation: {how we address it}
- {risk 2} — Mitigation: {how we address it}

## Validation
How will we know this decision was correct?
- Metric 1: {target}
- Metric 2: {target}
- Review date: {when we'll reassess}

## References
- {link to relevant doc}
- {link to prototype/POC}
- {link to benchmark results}
```

---

## 5. System Design Document Template

```markdown
# System Design: {System Name}

## 1. Overview
### 1.1 Problem Statement
{What problem does this system solve? For whom?}

### 1.2 Goals & Non-Goals
**Goals:**
- {goal 1}
- {goal 2}

**Non-Goals:**
- {explicitly out of scope}

### 1.3 Success Metrics
| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| {metric} | {baseline} | {target} | {how measured} |

## 2. Requirements
### 2.1 Functional Requirements
- FR1: {requirement}
- FR2: {requirement}

### 2.2 Non-Functional Requirements
- **Latency:** P95 < {X}ms
- **Throughput:** {X} requests/second
- **Availability:** {X}% uptime
- **Data retention:** {X} days
- **Cost:** < ${X}/month at expected scale

### 2.3 Constraints
- Must integrate with {existing system}
- Must comply with {regulation}
- Team size: {N} engineers
- Timeline: {X} weeks

## 3. Architecture

### 3.1 High-Level Architecture (C4 Level 1)
{System context diagram description}

### 3.2 Container Diagram (C4 Level 2)
{Major components and their interactions}

### 3.3 Component Deep Dives (C4 Level 3)
#### Component A: {Name}
- Responsibility: {what it does}
- Technology: {stack}
- Scaling: {horizontal/vertical}
- Data store: {what and where}

### 3.4 Data Flow
{Describe the flow of data through the system for key scenarios}

## 4. Key Design Decisions
- ADR-001: {decision}
- ADR-002: {decision}

## 5. API Design
### 5.1 External API
{Key endpoints, request/response schemas}

### 5.2 Internal Interfaces
{Service-to-service contracts}

## 6. Data Model
{Key entities, relationships, storage strategy}

## 7. Failure Modes & Resilience
| Failure Mode | Impact | Detection | Mitigation |
|--------------|--------|-----------|------------|
| {failure} | {impact} | {how detected} | {how handled} |

## 8. Security
- Authentication: {mechanism}
- Authorization: {model}
- Data encryption: {at rest, in transit}
- Secrets management: {approach}

## 9. Observability
- Logging: {strategy}
- Metrics: {key metrics, dashboards}
- Tracing: {distributed tracing approach}
- Alerting: {critical alerts, runbooks}

## 10. Cost Model
| Component | Monthly Cost | Scaling Factor |
|-----------|-------------|----------------|
| {component} | ${cost} | {per-user, per-query, etc.} |

## 11. Rollout Plan
- Phase 1: {scope, timeline}
- Phase 2: {scope, timeline}
- Rollback plan: {how to revert}

## 12. Future Considerations
- {known limitation and future solution}
- {scalability path}
```

---

## 6. Evaluation Report Template

```markdown
# Evaluation Report: {System Name} v{Version}

## Summary
| Metric | Score | Threshold | Status |
|--------|-------|-----------|--------|
| Faithfulness | 0.89 | ≥ 0.85 | ✅ PASS |
| Answer Relevance | 0.82 | ≥ 0.80 | ✅ PASS |
| Retrieval MRR@10 | 0.71 | ≥ 0.70 | ✅ PASS |
| P95 Latency | 1.8s | ≤ 2.0s | ✅ PASS |
| Error Rate | 3.2% | ≤ 5% | ✅ PASS |

**Overall: PASS** (all thresholds met)

## Dataset
- **Name:** {dataset name}
- **Version:** {version}
- **Size:** {N} examples
- **Difficulty distribution:** Easy: {n}%, Medium: {n}%, Hard: {n}%
- **Last updated:** {date}

## Methodology
- Evaluation framework: {tool/framework used}
- LLM Judge model: {model, calibration date}
- Human agreement (Cohen's κ): {score}
- Statistical significance: Bootstrap CI at 95%
- Compared against baseline: {version}

## Detailed Results

### Retrieval Metrics
| Metric | Easy | Medium | Hard | Overall |
|--------|------|--------|------|---------|
| Precision@5 | | | | |
| Recall@10 | | | | |
| MRR | | | | |
| NDCG@10 | | | | |

### RAG Quality Metrics
| Metric | Easy | Medium | Hard | Overall |
|--------|------|--------|------|---------|
| Faithfulness | | | | |
| Groundedness | | | | |
| Answer Relevance | | | | |
| Citation Precision | | | | |

### Regression Analysis
- Compared to: {baseline version}
- Regressions: {list or "none detected"}
- Improvements: {list}
- Statistical test: {method, p-values}

## Failure Analysis
### Top Failure Categories
1. {category}: {count} examples — Root cause: {explanation}
2. {category}: {count} examples — Root cause: {explanation}

### Example Failures
| Query | Expected | Got | Failure Mode |
|-------|----------|-----|--------------|
| {query} | {expected} | {actual} | {mode} |

## Recommendations
1. {recommendation with expected impact}
2. {recommendation with expected impact}

## Appendix
- Full results: {link}
- Dataset: {link}
- Traces: {link}
- Dashboard: {link}
```

---

## 7. SLO Document Template

```yaml
# Service Level Objectives: {Service Name}

service:
  name: "Enterprise RAG API"
  owner: "ai-platform-team"
  tier: 2  # 1=critical, 2=important, 3=best-effort
  dependencies: [vector_db, llm_provider, auth_service]

slos:
  - name: "Availability"
    description: "Percentage of successful (non-5xx) responses"
    sli:
      metric: "sum(rate(http_requests_total{status!~'5..'}[5m])) / sum(rate(http_requests_total[5m]))"
      good_event: "HTTP response with status < 500"
      valid_event: "Any HTTP request"
    objective: 99.9%
    window: "30 days rolling"
    error_budget: "43.2 minutes/month"
    alerting:
      - burn_rate: 14.4  # 1 hour to exhaust budget
        severity: critical
        notification: pagerduty
      - burn_rate: 6.0   # 2.4 hours to exhaust budget
        severity: warning
        notification: slack

  - name: "Latency (P95)"
    description: "95th percentile response time"
    sli:
      metric: "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))"
      good_event: "Response delivered within 2000ms"
      valid_event: "Any non-cached request"
    objective: 95%  # 95% of requests under 2s
    window: "7 days rolling"
    error_budget: "5% of requests can exceed 2s"
    alerting:
      - threshold: 3000ms
        severity: warning
      - threshold: 5000ms
        severity: critical

  - name: "Quality (Faithfulness)"
    description: "Percentage of responses that are faithful to sources"
    sli:
      metric: "Weekly eval run faithfulness score"
      good_event: "Faithfulness score >= 0.85"
      valid_event: "Any evaluated response"
    objective: 85%
    window: "7 days"
    measurement: "Weekly automated eval on golden dataset"
    alerting:
      - threshold: 0.80
        severity: critical
        notification: pagerduty
      - threshold: 0.85
        severity: warning
        notification: slack

  - name: "Cost Efficiency"
    description: "Average cost per query stays within budget"
    sli:
      metric: "sum(token_cost_usd) / count(queries)"
    objective: "< $0.03 per query average"
    window: "24 hours rolling"
    alerting:
      - threshold: 0.05
        severity: warning

error_budget_policy:
  when_budget_exhausted:
    - "Freeze non-critical deployments"
    - "Redirect engineering effort to reliability"
    - "Conduct incident review"
  when_budget_healthy:
    - "Normal feature development pace"
    - "Experimentation allowed"
  escalation:
    - level: 1
      trigger: "50% budget consumed in first week"
      action: "Team standup to discuss"
    - level: 2
      trigger: "Budget exhausted"
      action: "Director review, deployment freeze"

dashboards:
  primary: "https://grafana.company.com/d/rag-slo"
  error_budget: "https://grafana.company.com/d/rag-error-budget"
  detailed: "https://grafana.company.com/d/rag-detailed"

review_cadence: "Monthly SLO review meeting"
last_reviewed: "2025-01-15"
next_review: "2025-02-15"
```

---

## 8. Runbook Template

```markdown
# Runbook: {Alert/Scenario Name}

## Metadata
- **Service:** {service name}
- **Alert:** {alert name from monitoring}
- **Severity:** {P1/P2/P3/P4}
- **Owner:** {oncall team}
- **Last updated:** {date}
- **Last used:** {date}

## Overview
{Brief description of what this alert means and why it matters}

## Impact
- **Users affected:** {who and how}
- **Business impact:** {revenue, productivity, compliance}
- **SLO impact:** {which SLO is burning, budget remaining}

## Detection
- **Alert source:** {Prometheus/Grafana/PagerDuty rule}
- **Alert condition:** {exact condition}
- **Dashboard:** {link to relevant dashboard}
- **Key metrics to check:**
  - {metric 1}: {where to find it}
  - {metric 2}: {where to find it}

## Diagnosis Steps

### Step 1: Assess Scope
```bash
# Check error rate
curl -s https://monitoring.company.com/api/v1/query \
  --data-urlencode "query=rate(http_errors_total[5m])"

# Check which endpoints are affected
kubectl logs -l app=rag-api --since=5m | grep ERROR | sort | uniq -c | sort -rn | head
```

### Step 2: Identify Root Cause
Common causes (check in order):
1. **LLM Provider outage** — Check {provider status page}
2. **Vector DB overload** — Check {metric: vector_db_latency_p99}
3. **Memory pressure** — Check {metric: container_memory_usage}
4. **Deployment regression** — Check {last deploy time vs alert start}
5. **Traffic spike** — Check {metric: requests_per_second}

### Step 3: Check Dependencies
```bash
# Provider health
curl -s https://status.openai.com/api/v2/status.json | jq .status

# Vector DB health
kubectl exec -it pgvector-0 -- pg_isready

# Cache health
redis-cli -h cache.internal ping
```

## Mitigation Steps

### If: LLM Provider Down
1. Verify circuit breaker has triggered: `curl gateway/health | jq .providers`
2. Confirm fallback provider is handling traffic
3. If no fallback: enable degraded mode (return cached responses only)
```bash
kubectl set env deployment/rag-api DEGRADED_MODE=true
```

### If: Vector DB Overload
1. Check connection pool: `kubectl exec pgvector-0 -- psql -c "SELECT count(*) FROM pg_stat_activity"`
2. If pool exhausted: restart connection pooler
```bash
kubectl rollout restart deployment/pgbouncer
```
3. If query timeout: check for long-running queries and kill them
4. Scale read replicas if sustained load

### If: Deployment Regression
1. Check recent deploys: `kubectl rollout history deployment/rag-api`
2. Rollback immediately:
```bash
kubectl rollout undo deployment/rag-api
```
3. Verify metrics recover within 5 minutes
4. Page the deployer to investigate

### If: Traffic Spike
1. Check if legitimate: correlate with business events
2. If DDoS/abuse: enable rate limiting
```bash
kubectl set env deployment/rag-api RATE_LIMIT_RPM=50
```
3. Scale horizontally:
```bash
kubectl scale deployment/rag-api --replicas=10
```

## Escalation
- **If not resolved in 15 min:** Page {senior oncall}
- **If P1 for 30+ min:** Notify {engineering director}
- **If data loss suspected:** Notify {security team}

## Recovery Verification
After mitigation:
1. [ ] Error rate below threshold for 10 minutes
2. [ ] P95 latency returned to normal
3. [ ] No errors in application logs
4. [ ] SLO error budget burn rate normalized
5. [ ] Synthetic monitors passing

## Post-Incident
- [ ] Create incident ticket
- [ ] Schedule post-mortem (within 48h for P1/P2)
- [ ] Update this runbook if steps were missing/wrong
- [ ] Create action items for prevention

## Historical Incidents
| Date | Duration | Root Cause | Action Items |
|------|----------|------------|--------------|
| {date} | {duration} | {cause} | {link to action items} |
```

---

## Usage Guide

These templates should be:
1. **Customized** per project — remove sections that don't apply, add project-specific ones
2. **Living documents** — updated as the system evolves, not write-once artifacts
3. **Reviewed regularly** — ADRs at design reviews, SLOs monthly, runbooks after incidents
4. **Machine-readable where possible** — YAML templates can be validated by CI
5. **Linked together** — ADRs reference design docs, design docs reference SLOs, runbooks reference dashboards

### Template Selection Guide
| Situation | Template |
|-----------|----------|
| Adding a new tool to agent | Tool Contract |
| Deploying a new agent | Agent Card |
| Using a new AI model | Model Risk Sheet |
| Making a technical choice | ADR |
| Designing a new system | System Design Doc |
| Validating AI quality | Evaluation Report |
| Defining reliability targets | SLO Document |
| Preparing for incidents | Runbook |
