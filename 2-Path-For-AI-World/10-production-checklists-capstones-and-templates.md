# Execution Assets: Production Checklists, Capstone Projects, and Architecture Templates

**Learning level:** Portfolio and delivery  
**Outcome:** You can prove capability through checklists, capstone systems, and reusable architecture artifacts.

---

# 6. Production Checklists

## Production Readiness Checklist

- [ ] use case defined
- [ ] non-goals defined
- [ ] risk tier assigned
- [ ] success metrics defined
- [ ] SLOs defined
- [ ] data sources approved
- [ ] access control implemented
- [ ] golden dataset created
- [ ] retrieval eval implemented
- [ ] RAG eval implemented
- [ ] trajectory eval implemented
- [ ] safety eval implemented
- [ ] guardrails implemented
- [ ] tool permissions scoped
- [ ] human approval defined
- [ ] observability implemented
- [ ] cost tracking implemented
- [ ] AI gateway in place
- [ ] fallback defined
- [ ] canary plan ready
- [ ] rollback plan ready
- [ ] incident runbooks ready

## RAG Checklist

- [ ] clean ingestion
- [ ] table-aware parsing
- [ ] OCR where needed
- [ ] RAG pattern selected and justified
- [ ] chunking benchmarked
- [ ] metadata schema defined
- [ ] ACL filters implemented
- [ ] embedding model benchmarked
- [ ] hybrid retrieval tested
- [ ] reranker tested
- [ ] retrieval failure modes documented
- [ ] citations verified
- [ ] stale docs removed
- [ ] deletion propagation works
- [ ] retrieval metrics monitored

## Agent Checklist

- [ ] clear goal
- [ ] clear boundaries
- [ ] minimal tool set
- [ ] strict schemas
- [ ] read/write tools separated
- [ ] max steps
- [ ] timeout
- [ ] token budget
- [ ] state persistence
- [ ] memory policy
- [ ] approval checkpoints
- [ ] training/improvement loop defined
- [ ] cost per successful task measured
- [ ] trajectory evals
- [ ] full traces

## Security Checklist

- [ ] prompt injection tests
- [ ] indirect injection tests
- [ ] RAG poisoning tests
- [ ] tool injection tests
- [ ] PII leakage tests
- [ ] tenant isolation tests
- [ ] secrets not in context
- [ ] logs redacted
- [ ] MCP servers approved
- [ ] A2A agents authenticated
- [ ] audit logs retained

---

# 7. Capstone Portfolio Projects

## Project 1: Enterprise RAG Platform

Include:

- document ingestion
- chunking experiments
- vector DB
- keyword search
- hybrid retrieval
- reranking
- metadata filters
- citations
- ACLs
- eval dashboard

## Project 2: Agentic RAG Assistant

Include:

- query decomposition
- iterative retrieval
- SQL tool
- API tool
- claim verification
- confidence score
- abstention
- human escalation

## Project 3: Evaluation Platform

Include:

- golden dataset manager
- retrieval metrics
- RAG metrics
- trajectory metrics
- LLM-as-judge
- human review queue
- CI gates
- dashboard

## Project 4: MCP Tool Ecosystem

Include:

- MCP knowledge-base server
- MCP SQL read-only server
- MCP ticket creation server
- scoped tool permissions
- audit logs
- approval workflow

## Project 5: A2A Multi-Agent System

Include:

- Agent Card
- discovery
- supervisor agent
- specialist agent
- task lifecycle
- authentication
- traceability

## Project 6: AI Gateway

Include:

- unified model API
- model routing
- fallback
- token tracking
- budgets
- semantic cache
- guardrails
- logs

## Project 7: Million-User Simulation

Include:

- load testing
- vector DB sharding
- queue-based tasks
- autoscaling plan
- cost model
- SLO dashboard
- runbooks

## Project 8: Agent Training and Optimization Lab

Include:

- production trace dataset
- failure clustering
- prompt/tool/graph variants
- retriever variants
- model routing experiment
- fine-tuning or distillation experiment
- golden eval comparison
- cost per successful task dashboard
- canary and rollback plan

## Project 9: World-Class AI Architecture Review Board

Include:

- AI use-case intake
- risk tiering
- architecture review checklist
- privacy and data governance review
- vendor/supply-chain risk review
- UX trust review
- production readiness gate
- ADR library

---

# 8. Architecture Templates

## Tool Contract Template

```yaml
tool_name: create_support_ticket
owner: customer_support_platform
risk_level: medium
side_effects: creates_ticket
requires_human_approval: false
allowed_roles:
  - support_agent
  - customer_success_manager
input_schema:
  type: object
  required:
    - customer_id
    - issue_type
    - description
validation:
  - user_must_have_customer_access
  - description_must_not_contain_secrets
audit:
  log_request: true
  log_response: true
  redact_fields:
    - description
```

## Agent Card Template

```yaml
agent_name: finance_analysis_agent
version: 1.0.0
owner: finance_ai_platform
capabilities:
  - analyze_invoices
  - summarize_financial_variance
  - answer_policy_questions
authentication:
  type: oauth2
permissions:
  read_tools:
    - invoice_search
    - policy_search
  write_tools:
    - draft_approval_request
human_approval_required_for:
  - payment_release
  - vendor_master_update
risk_level: high
observability:
  traces_required: true
  audit_log_required: true
```

## Model Risk Sheet Template

```yaml
model_name: example-model
provider: example-provider
use_case: customer_support_agent
risk_level: medium
data_sent:
  - user_query
  - retrieved_context
data_stored_by_provider: false
evaluation_score:
  groundedness: 0.95
  task_success: 0.88
known_limitations:
  - may fail on ambiguous refund policies
fallback: fallback-model
monitoring:
  - latency
  - cost
  - safety
  - groundedness
owner: ai_platform_team
approval_date: 2026-05-21
review_cycle: quarterly
```

---
