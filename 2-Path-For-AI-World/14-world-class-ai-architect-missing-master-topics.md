# World-Class AI Architect Master Topics

**Learning level:** Principal / enterprise AI architect  
**Outcome:** You can lead AI architecture beyond models and agents: product strategy, privacy, supply chain, UX trust, operating model, architecture governance, and platform maturity.

---

# 1. AI Product and Business Architecture

A world-class AI architect does not start with a model. They start with the business workflow, risk, economics, users, and operating model.

## Master

- use-case discovery
- workflow mapping
- user journey mapping
- value-stream mapping
- task automation vs task augmentation
- ROI model
- cost-benefit model
- build vs buy
- pilot selection
- rollout strategy
- adoption and change management
- stakeholder mapping
- executive communication
- success metrics
- failure metrics
- human handoff model
- business continuity requirements

## Use-Case Intake Questions

| Question | Why It Matters |
|---|---|
| What decision or workflow changes if AI works? | prevents demo-driven architecture |
| What is the cost of a wrong answer or wrong action? | defines risk tier and controls |
| Who is accountable for the final decision? | defines human oversight |
| What data is needed and who owns it? | defines access and governance |
| What does success mean in business terms? | defines ROI and metrics |
| What must the AI never do? | defines non-goals and safety boundaries |

Senior phrase:

> I do not design an AI system until I understand the business workflow, risk tier, data ownership, human accountability, success metrics, and rollout path.

---

# 2. AI Privacy and Data Governance

Privacy is architecture, not paperwork. Retrieval, memory, logs, prompts, traces, eval datasets, and vendor calls can all leak data.

## Master

- data minimization
- purpose limitation
- consent
- retention policy
- right-to-delete workflows
- data residency
- data classification
- PII detection and redaction
- anonymization and pseudonymization
- differential privacy basics
- privacy impact assessments
- prompt/log redaction
- trace retention
- eval dataset privacy
- synthetic data privacy risk
- cross-tenant privacy boundaries
- memory deletion

## Privacy Architecture Pattern

```text
data source
  -> classification
  -> purpose and consent check
  -> minimization
  -> encryption
  -> permissioned retrieval
  -> redacted prompts/traces
  -> retention policy
  -> deletion workflow
  -> audit evidence
```

Architect rule:

> If data can enter prompts, memory, logs, traces, eval datasets, vector indexes, or vendor APIs, it needs a privacy policy and deletion story.

---

# 3. AI Supply Chain and Vendor Risk

Agentic AI systems depend on model providers, embedding providers, vector databases, MCP servers, open-source packages, SaaS tools, plugins, datasets, and cloud infrastructure.

## Master

- model provider risk
- embedding provider risk
- vector database vendor risk
- MCP server supply-chain risk
- open-source dependency risk
- model license risk
- dataset license risk
- SaaS API risk
- provider outage planning
- provider behavior drift
- vendor lock-in
- exit strategy
- fallback provider strategy
- AI bill of materials
- dependency scanning
- registry approval
- signed artifacts
- network egress controls

## AI Bill of Materials

Track:

- model provider and model version
- embedding model and dimension
- reranker model
- vector database/index version
- prompt versions
- tool schemas
- MCP servers
- A2A agents
- datasets used for eval or tuning
- fine-tuned model lineage
- third-party APIs
- deployment region
- owner and approver
- risk tier

Senior phrase:

> I treat AI dependencies as supply-chain dependencies. Every model, tool, MCP server, dataset, and vendor must have ownership, risk classification, approval, monitoring, and an exit plan.

---

# 4. AI UX and Human Factors

AI UX determines whether users trust the system correctly. Bad UX can make users over-trust weak answers or ignore useful ones.

## Master

- trust calibration
- uncertainty display
- citation UX
- confidence explanation
- human approval UX
- edit-before-action UX
- escalation UX
- refusal and abstention UX
- feedback collection
- error recovery
- audit trail visibility
- explainability for non-technical users
- avoiding automation bias
- avoiding false authority
- safe defaults

## UX Patterns

| Pattern | Use When |
|---|---|
| answer with citations | factual or policy answers |
| answer with confidence caveat | medium confidence result |
| ask clarification | underspecified query |
| abstain | evidence is missing or risk is high |
| propose action for approval | side-effecting action |
| show evidence bundle | reviewer needs source context |
| show change preview | agent edits code, document, ticket, or record |
| allow user correction | feedback improves eval data |

Senior phrase:

> The user interface must teach the user how much to trust the AI. Confidence, citations, evidence, editability, and escalation are part of the architecture.

---

# 5. Agent Identity and Runtime Permissioning

Enterprise agents need identities, scoped permissions, and auditable action ownership.

## Master

- agent identity
- user identity propagation
- service identity
- on-behalf-of flow
- delegated authorization
- short-lived tool tokens
- scoped credentials
- per-tool permission checks
- per-action approval
- just-in-time privilege
- secret isolation
- audit action as user plus agent
- tenant and resource boundaries
- remote agent trust

## Correct Action Pattern

```text
user authenticates
  -> agent receives user and tenant context
  -> policy engine checks allowed tools
  -> tool receives scoped short-lived token
  -> risky action requires approval
  -> action is executed with audit trail
  -> result is logged with redaction
```

Wrong pattern:

```text
agent uses one permanent admin token for every user and tool
```

Senior phrase:

> The agent should never be a hidden super-admin. It should act with scoped, auditable, least-privilege authority tied to the user, tenant, tool, and action.

---

# 6. Architecture Review and Governance Operating Model

Large organizations need repeatable architecture governance so teams do not rebuild unsafe AI patterns in every product.

## Master

- AI architecture review board
- use-case intake
- risk tiering
- model approval
- prompt approval
- tool approval
- MCP server approval
- A2A agent approval
- data-source approval
- eval gate approval
- privacy review
- security review
- production readiness review
- incident review
- ADR process
- platform standards

## Review Gates

| Gate | Required Evidence |
|---|---|
| use-case approval | business goal, risk tier, owner, non-goals |
| data approval | source owner, classification, retention, access model |
| architecture approval | diagrams, sequence flows, threat model, ADRs |
| eval approval | golden set, safety set, metrics, regression thresholds |
| security approval | auth, tool permissions, prompt-injection tests, audit logs |
| privacy approval | minimization, retention, deletion, redaction |
| production approval | SLOs, monitoring, runbooks, rollback, cost budget |

Architect rule:

> A platform team should make the secure path the easy path: approved models, registries, eval harnesses, gateway controls, templates, and review gates.

---

# 7. AI Platform Maturity Model

Use this model to assess teams and plan upgrades.

| Level | Description | Typical Gaps |
|---|---|---|
| L0 ad hoc AI | prompts and demos | no evals, no security, no ownership |
| L1 app-specific AI | one product has RAG or tools | duplicated patterns, weak governance |
| L2 reusable platform basics | gateway, prompt registry, traces, basic evals | limited policy automation |
| L3 governed enterprise platform | model/tool/agent registries, eval gates, risk tiers | scaling and operating model maturity |
| L4 optimized AI operating system | automated evals, routing, budgets, incident loops, reusable agents | advanced autonomy governance |
| L5 adaptive enterprise intelligence | controlled continuous improvement across workflows | requires strict oversight and auditability |

Target state:

> Most enterprises should aim for L3 first: governed platform controls, reusable components, measurable quality, security, and operational discipline.

---

# 8. Build vs Buy Decision Framework

| Build | Buy |
|---|---|
| unique workflow or differentiating capability | commodity capability |
| strict data/control requirement | vendor meets data and risk requirements |
| deep integration with internal systems | standard SaaS integration is enough |
| need custom eval/guardrail behavior | vendor provides sufficient controls |
| long-term scale justifies platform investment | speed matters more than customization |

Decision factors:

- strategic differentiation
- data sensitivity
- compliance
- integration depth
- operational skill
- lock-in risk
- time to value
- total cost of ownership
- fallback and exit options

Senior phrase:

> I build platform primitives that create durable advantage and buy commodity capabilities when vendor risk, cost, and control are acceptable.

---

# 9. Missing Interview Questions To Practice

Use these after finishing the top 100.

1. How would you create an AI architecture review board for a large enterprise?
2. How do you decide whether to build or buy an AI agent platform?
3. How do you design right-to-delete for vector indexes, prompts, memory, traces, and eval data?
4. How do you prevent users from over-trusting AI answers?
5. How do you audit an AI action taken through a tool on behalf of a user?
6. What belongs in an AI bill of materials?
7. How do you migrate from ad hoc AI apps to a governed AI platform?
8. How do you design a vendor exit strategy for model providers?
9. How do you evaluate UX trust and human review quality?
10. What is your target AI platform maturity model for the first year?

---

# Final Architect Statement

> A world-class AI architect designs the system around business value, governed data, measurable quality, safe autonomy, runtime identity, human trust, supply-chain control, cost discipline, and operational resilience. Models are only one component of the architecture.
