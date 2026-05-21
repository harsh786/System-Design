# Enterprise Safety Track: Security, Governance, Auth, and Gateways

**Learning level:** Production to enterprise  
**Outcome:** You can secure Agentic AI systems across identity, retrieval, tools, MCP servers, A2A agents, guardrails, auditability, governance, and gateway policy enforcement.

---

## Phase 13: Guardrails, Safety, and Security

Threats:

- direct prompt injection
- indirect prompt injection
- tool injection
- RAG poisoning
- data exfiltration
- over-permissioned tools
- system prompt leakage
- vector DB poisoning
- unauthorized retrieval
- SSRF/tool abuse
- PII leakage
- jailbreaks
- excessive agency
- MCP supply-chain risk
- A2A remote-agent risk

Guardrail layers:

| Layer | Guardrail |
|---|---|
| input | moderation, jailbreak detection, intent classification |
| retrieval | ACL filters, source trust, injection scanning |
| prompt | context separation, source labeling, instruction hierarchy |
| tool | schema validation, allowlists, least privilege |
| action | human approval for risky operations |
| output | PII redaction, groundedness, policy checks |
| runtime | rate limits, anomaly detection, audit logs |
| platform | AI gateway, secrets isolation, egress controls |
| governance | red-team evals, compliance review, incident response |

Security principle:

> Treat user input, retrieved documents, tool outputs, MCP servers, and remote agents as untrusted unless explicitly verified.

---

## Phase 14: Authentication and Authorization

Authentication:

- OAuth2
- OIDC
- SSO
- JWT
- mTLS
- API keys
- service accounts
- short-lived tokens
- token exchange
- on-behalf-of flow

Authorization:

- RBAC
- ABAC
- ReBAC
- row-level security
- document-level permissions
- tenant isolation
- scoped tool permissions
- policy engines
- approval workflows

Correct pattern:

```text
User logs in
  -> identity and scopes propagated
  -> retriever filters documents by permissions
  -> tools execute with least privilege
  -> actions audited as user + agent
```

Wrong pattern:

```text
Agent uses one super-admin credential for all retrieval and actions.
```

---

## Phase 15: AI Gateway and API Gateway

AI gateway responsibilities:

- model routing
- provider abstraction
- fallback
- retry
- rate limit
- token budget
- cost tracking
- key management
- prompt cache
- semantic cache
- logging
- guardrail hooks
- tenant usage tracking
- policy enforcement

Architecture:

```text
Client apps
  -> API Gateway
  -> Auth + tenant policy
  -> AI Gateway
  -> prompt/security filters
  -> model router
  -> provider A / provider B / self-hosted model
  -> response guardrails
  -> logs/traces/eval sampling
```

---


## 4.2 Governance and Responsible AI

Master:

- NIST AI RMF
- ISO/IEC 42001
- EU AI Act awareness
- OWASP Top 10 for LLM Applications
- model cards
- system cards
- data cards
- AI risk register
- human oversight process
- incident reporting
- auditability
- data retention
- right to deletion
- vendor risk management

Questions you must answer:

- How do you classify AI risk?
- What human oversight is needed?
- What logs are retained?
- How do you audit a wrong answer?
- How do you prove the system was tested?
- What if the model provider changes behavior?
- How do you handle data residency?
- How do you handle right-to-delete requests?

---

## 4.3 AI Security and Red Teaming Depth

Go beyond basic guardrails.

Master:

- prompt injection
- indirect prompt injection
- tool injection
- RAG poisoning
- MCP server risk
- A2A agent trust
- data exfiltration
- over-permissioned tools
- secrets leakage
- cross-tenant leakage
- jailbreak resilience
- supply-chain risk

Security architecture:

```text
Input security
  -> prompt-injection classifier
  -> context isolation
  -> permission-filtered retrieval
  -> tool allowlist
  -> runtime policy engine
  -> human approval for high-risk actions
  -> output validation
  -> audit log
```

Interview answer:

> I secure AI agents at multiple layers: identity, retrieval permissions, tool permissions, prompt-injection defense, sandboxing, action approval, output filtering, audit logging, and continuous red-team evaluation.

---

## 4.4 Protocol Security: MCP and A2A

MCP architect topics:

- host/client/server model
- tools/resources/prompts
- server trust levels
- auth and authorization
- user-scoped access
- registry approval
- tool risk tiers
- audit logging
- sandboxing
- supply-chain validation

A2A architect topics:

- Agent Cards
- agent identity
- task lifecycle
- task delegation
- authentication
- authorization
- capability discovery
- traceability
- cross-framework interoperability

Interview answer:

> I do not trust tools or agents by default. I require identity, scoped permissions, registry approval, runtime policy checks, audit logs, sandboxing, rate limits, and human approval for risky side effects.

---
