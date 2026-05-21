# Enterprise Architecture and Operating Model

This track prepares you for architect interviews where the scope is larger than one system. It covers how architecture connects business capability, governance, platform strategy, vendor choices, risk, and multi-year technical direction.

## Architect-Level Outcome

You should be able to explain how an enterprise chooses, governs, evolves, and measures architecture across many teams and systems.

| Area | Architect-Level Outcome |
| --- | --- |
| Business capability modeling | Map technology investments to business capabilities and outcomes. |
| Operating model | Define how teams, platforms, governance, and ownership work together. |
| Architecture governance | Run lightweight reviews, standards, exceptions, and ADR processes. |
| Technology strategy | Build a technology radar and guide adoption, trial, hold, and retire decisions. |
| Build vs buy | Evaluate business fit, cost, integration, security, vendor risk, and exit strategy. |
| Portfolio modernization | Sequence migrations across systems without breaking delivery. |

## Enterprise Architecture Interview Formula

```text
Business outcome -> Capability map -> Current-state pain -> Target-state principles -> Options -> Operating model -> Governance -> Migration roadmap -> Metrics -> Risks
```

## Business Capability Modeling

Business capabilities describe what the business does, not how a system is implemented.

Examples:

- Customer onboarding.
- Identity and access.
- Billing and invoicing.
- Order management.
- Inventory management.
- Fraud detection.
- Reporting and analytics.
- Partner integration.

Why it matters:

- Capabilities are more stable than org charts and applications.
- They help identify duplicate systems.
- They connect architecture investments to business value.
- They support ownership and funding discussions.

## Capability Map Template

| Capability | Current Systems | Pain | Target State | Owner | Metrics |
| --- | --- | --- | --- | --- | --- |
| Billing | Legacy billing app, manual scripts | Slow changes, errors | Billing platform with APIs/events | Finance platform | invoice accuracy, time to launch plan |
| Identity | Multiple auth systems | inconsistent policy | centralized IAM and federation | security platform | login success, policy coverage |

## Architecture Principles

Good principles are decision filters, not slogans.

| Principle | Meaning | Example Decision |
| --- | --- | --- |
| API-first | Systems expose stable contracts. | No direct database access across domains. |
| Event-aware | Important business state changes emit events. | OrderCreated event after order source-of-truth commit. |
| Secure by default | Teams inherit guardrails. | Standard auth middleware and secret management. |
| Observable by default | New services emit logs, metrics, traces, and health. | Service template includes OpenTelemetry. |
| Data has owners | Every dataset has a steward and contract. | Product analytics table has owner, schema, freshness SLO. |
| Prefer paved roads | Teams can deviate with justification. | Approved service template unless exception is documented. |

## Governance Model

Architecture governance should reduce risk without becoming a blocking committee.

### Governance Artifacts

- Architecture principles.
- Standards and reference architectures.
- ADRs.
- Architecture review checklist.
- Exception register.
- Technology radar.
- System catalog.
- Dependency and risk register.
- Data ownership catalog.

### Review Triggers

Require review for:

- New service or data store.
- New external vendor.
- New sensitive data flow.
- New cross-region architecture.
- Major schema/API/event contract change.
- High-cost infrastructure commitment.
- Security boundary change.
- Migration of critical production workflow.

### Exception Register

| Exception | Reason | Risk | Expiry | Owner | Mitigation |
| --- | --- | --- | --- | --- | --- |
| Service uses non-standard DB | Required graph traversal | Operational skill gap | 2026-12-31 | Search team | runbook, backup drill, training |

## Technology Radar

Use four categories:

- Adopt: proven and recommended.
- Trial: promising with controlled use.
- Assess: watch and experiment.
- Hold: avoid for new work.

Evaluation criteria:

- Business fit.
- Operational maturity.
- Security posture.
- Team skill.
- Ecosystem support.
- Vendor lock-in.
- Cost model.
- Migration path.
- Failure modes.

## Build vs Buy vs Partner

| Dimension | Build | Buy | Partner |
| --- | --- | --- | --- |
| Differentiation | High | Low/medium | Medium |
| Time to market | Slower | Faster | Medium |
| Control | High | Lower | Medium |
| Operational burden | High | Lower | Shared |
| Customization | High | Limited | Negotiated |
| Vendor risk | Low | Medium/high | Medium/high |
| Exit complexity | Depends | Often high | Often high |

Interview answer rule:

```text
Build what differentiates the business. Buy commodity capability when integration, security, and exit risks are acceptable.
```

## Vendor Risk and Exit Strategy

Assess:

- Data export path.
- Contract terms and SLA.
- Security certifications.
- Audit rights.
- Regional/data residency support.
- Rate limits and quotas.
- Pricing growth at 10x usage.
- Integration complexity.
- Operational dependency.
- Replacement strategy.

Exit plan should include:

- Data portability.
- Abstraction boundary.
- Parallel run option.
- Contract termination timeline.
- Reconciliation process.

## Operating Model

### Team Ownership

Every service should have:

- Code owner.
- Runtime owner.
- Data owner.
- On-call owner.
- Product owner.
- SLO owner.
- Cost owner.

### Platform Team Role

Platform teams should provide:

- Golden paths.
- Service templates.
- CI/CD templates.
- Observability defaults.
- Security guardrails.
- Kubernetes/runtime platform.
- Secrets and policy tooling.
- Developer documentation.
- Support model and office hours.

### Architecture Decision Rights

| Decision | Owner |
| --- | --- |
| Business capability priority | Product/business leadership |
| Domain boundaries | Domain architects and engineering leads |
| Security baseline | Security architecture |
| Platform standards | Platform architecture |
| Service internals | Owning engineering team |
| Cross-domain contracts | Producing and consuming teams together |
| Exceptions | Architecture review group |

## Enterprise Roadmap Template

| Phase | Goal | Deliverables | Exit Criteria |
| --- | --- | --- | --- |
| 0 | Discover | capability map, system catalog, risk register | critical gaps known |
| 1 | Stabilize | observability, ownership, runbooks, backup drills | production risks reduced |
| 2 | Standardize | service templates, CI/CD, auth, logging, secrets | paved road available |
| 3 | Modernize | strangler migrations, APIs/events, data contracts | legacy coupling reduced |
| 4 | Optimize | cost, performance, reliability, developer productivity | measurable improvement |

## Interview Questions

1. How would you modernize a company with 200 services and no clear ownership?
2. How do you introduce architecture governance without slowing teams?
3. How do you decide whether to build or buy a billing system?
4. How do you create a technology radar?
5. How do you handle teams that want different databases for every service?
6. How do you map business capabilities to system boundaries?
7. How do you manage vendor lock-in?
8. How do you define platform standards across many teams?

