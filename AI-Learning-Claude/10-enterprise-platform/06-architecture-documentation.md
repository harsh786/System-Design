# Architecture Documentation for AI Systems

## Why Document AI Architecture?

The **"bus factor" problem**: If the person who designed your AI system gets hit by a bus (or, more realistically, leaves for a competitor), can the team continue operating and evolving the system?

AI systems are particularly dangerous to leave undocumented because:
- Prompt engineering decisions look arbitrary without context ("why is this word here?")
- Model choices have non-obvious tradeoffs
- Data pipeline decisions cascade through the entire system
- Guardrails exist for reasons that aren't obvious until they're removed

**Without documentation:**
```
New engineer: "Why do we use GPT-4 here instead of GPT-3.5?"
Team: "...Bob set that up. Bob left 6 months ago."
New engineer: *changes to GPT-3.5*
Result: Quality drops 40%, nobody knows why for 2 weeks
```

## 14 Must-Have Architecture Documents

### 1. Architecture Decision Records (ADRs)

Record **why** decisions were made, not just what was decided. The "why" is what gets lost.

```markdown
# ADR-007: Use GPT-4o for Legal Document Analysis

## Status: Accepted

## Context
We need to analyze legal contracts for risk clauses. Accuracy is critical 
because errors have financial and legal consequences.

## Decision
Use GPT-4o (not GPT-3.5 or GPT-4o-mini) for legal analysis despite 10x cost.

## Consequences
- Higher per-request cost ($0.03 vs $0.003)
- Higher accuracy (92% vs 71% on our legal eval set)
- Acceptable because volume is low (< 100 docs/day)
- Budget impact: ~$90/day

## Alternatives Considered
- GPT-3.5: Too low accuracy for legal domain (71%)
- Claude 3.5: Good accuracy (89%) but no Azure deployment (data residency)
- Fine-tuned model: Not enough training data yet (< 500 examples)
```

### 2. System Context Diagram
Shows how your AI system fits in the broader organization. What systems does it interact with? Who are the users?

### 3. Component Diagram
Internal components and their responsibilities. The gateway, registries, vector stores, etc.

### 4. Data Flow Diagram
How data moves from sources through pipelines to vectors to answers. Critical for debugging and compliance.

### 5. Deployment Diagram
Where things run: which cloud, which region, which Kubernetes cluster, how many replicas.

### 6. API Specifications
OpenAPI specs for every API surface. Include AI-specific details like token limits, streaming behavior, and rate limits.

### 7. Tool Contracts
For every tool an agent can call: schema, permissions, rate limits, side effects, error handling.

### 8. Agent Specifications
Per agent: purpose, tools, models, guardrails, escalation paths, expected behavior.

### 9. Evaluation Strategy
What metrics, how they're measured, thresholds for deployment, evaluation datasets.

### 10. Security Architecture
Auth flows, PII handling, data classification, encryption, access control, threat model.

### 11. Disaster Recovery Plan
What happens when OpenAI goes down? When the vector DB corrupts? RTO and RPO for each component.

### 12. Capacity Plan
Current usage, growth projections, scaling triggers, cost projections.

### 13. Cost Model
Cost per request, per user, per feature. Budget allocation and alerts.

### 14. Runbook Library
Step-by-step procedures for common operational tasks: "How to rollback a prompt," "How to reindex a data source," "How to investigate quality drops."

## ADR Template

```markdown
# ADR-{NUMBER}: {TITLE}

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
What is the issue that we're seeing that motivates this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult because of this change?

## Alternatives Considered
What other options were evaluated and why were they rejected?

## References
Links to relevant docs, benchmarks, discussions.
```

## Architecture Review Checklist

Before deploying any AI system, verify:

**Functional:**
- [ ] Does the system meet quality requirements? (eval scores above threshold)
- [ ] Are all data sources connected and fresh?
- [ ] Are guardrails tested against adversarial inputs?
- [ ] Is the system accessible to all intended users?

**Operational:**
- [ ] Is observability in place? (traces, metrics, logs)
- [ ] Are alerts configured for quality/cost/latency?
- [ ] Is there a rollback procedure documented and tested?
- [ ] Is the on-call rotation defined?

**Security:**
- [ ] Is PII handled correctly?
- [ ] Are API keys rotated and stored securely?
- [ ] Is access control enforced at retrieval time?
- [ ] Has a security review been completed?

**Cost:**
- [ ] Is the cost model documented?
- [ ] Are budgets set and alerts configured?
- [ ] Is there a path to cost optimization?

**Compliance:**
- [ ] Data residency requirements met?
- [ ] Retention policies configured?
- [ ] Audit trail in place?
- [ ] Regulatory requirements addressed?

## Keeping Documentation Alive

Documentation rots fast. Combat this with automation:

### 1. Documentation as Code
Store docs in the same repo as code. Review docs in the same PR.

### 2. CI Checks
```yaml
# .github/workflows/docs-check.yml
- name: Check ADR exists for new models
  run: |
    if git diff --name-only | grep -q "model_config"; then
      echo "Model config changed - verify ADR exists"
    fi

- name: Validate API specs match implementation
  run: openapi-diff expected.yaml actual.yaml

- name: Check runbooks are up to date
  run: ./scripts/validate-runbooks.sh
```

### 3. Auto-Generated Docs
- API docs from OpenAPI specs (auto-generated)
- Deployment diagrams from Terraform/Kubernetes configs
- Cost reports from usage data
- Component diagrams from code dependencies

### 4. Documentation Reviews
- Monthly "doc review" calendar event
- Assign document owners (like code owners)
- Track freshness: "Last reviewed: 2024-03-01"

## The "Living Documentation" Principle

```mermaid
flowchart LR
    A[Code Change] --> B[PR Review]
    B --> C{Does this need<br/>doc update?}
    C -->|Yes| D[Update docs in same PR]
    C -->|No| E[Merge]
    D --> E
    
    F[Monthly Review] --> G[Check all docs<br/>for staleness]
    G --> H[Update or archive<br/>stale docs]
```

**Rules for living documentation:**
1. **Docs live with code** — same repo, same PR
2. **No orphan docs** — every doc has an owner
3. **Stale = deleted** — outdated docs are worse than no docs
4. **Automate what you can** — generate from code wherever possible
5. **Review regularly** — monthly freshness check

## Documentation Anti-Patterns

| Anti-Pattern | Problem | Solution |
|-------------|---------|----------|
| Wiki graveyard | Nobody reads or updates | Docs in repo, CI checks |
| Novel-length docs | Nobody reads past page 1 | Keep concise, link for depth |
| Missing "why" | Future team repeats mistakes | ADRs capture reasoning |
| Screenshots of architecture | Can't update, go stale | Mermaid/PlantUML in markdown |
| Tribal knowledge | Bus factor = 1 | Write it down, review in PR |

## Key Takeaways

1. **ADRs are the highest-value document** — capture the "why" before it's forgotten
2. **14 documents sounds like a lot** — start with ADRs + system context + runbooks
3. **Documentation is a team practice** — enforce through PR reviews and CI
4. **Auto-generate what you can** — reduce manual maintenance burden
5. **Stale docs are worse than no docs** — actively maintain or delete
6. **Diagrams as code** (Mermaid) stay current because they're easy to update

---

## Staff+ Deep Dive: Anti-Patterns, Trade-offs, and What to Document

### Anti-Patterns to Avoid

**1. Documentation as Afterthought**
"We'll document it after we ship." You won't. The context, reasoning, and alternatives considered evaporate from memory within weeks. The only documentation that gets written is documentation written at decision time.

Fix: Make ADR creation part of the design review process. No design approval without a written record of the decision and its rationale.

**2. Docs That Are Immediately Stale**
A 50-page architecture document created once and never updated. Within 3 months it actively misleads new team members. Stale documentation is worse than no documentation — at least with no docs, people ask questions instead of trusting lies.

Fix: Either commit to maintaining it (with ownership and review cadence) or don't write it. Prefer small, scoped documents that are cheap to update over comprehensive documents that are expensive to maintain.

**3. No Architecture Decision Records**
Teams make dozens of significant decisions (which vector DB, what chunking strategy, sync vs async, which provider) but record none of them. Six months later, someone asks "why did we choose Pinecone over Weaviate?" and nobody remembers the evaluation criteria.

Fix: Lightweight ADR template — context, decision, consequences, status. Takes 15 minutes to write. Saves hours of re-evaluation.

**4. Documenting "What" Without "Why"**
"We use Kafka for event streaming" — great, but WHY? What alternatives were considered? What constraints drove this choice? Without "why," future engineers can't evaluate whether the decision still holds when constraints change.

### Critical Trade-offs

**Living Docs (Wiki) vs. Formal Docs (Versioned)**

| Dimension | Living Docs (Wiki/Notion) | Formal Docs (Git-versioned) |
|-----------|---------------------------|----------------------------|
| Currency | Always up-to-date (ideally) | Point-in-time snapshots |
| Review process | None or informal | PR review, approval |
| Discoverability | Search, linking | File structure, README |
| Accountability | "Anyone can edit" = nobody owns | Clear ownership via CODEOWNERS |
| Best for | Runbooks, how-tos, onboarding | ADRs, contracts, SLAs |

Most effective approach: ADRs and architecture contracts in git (immutable history matters), operational docs in wiki (easy to update when procedures change).

**Lightweight ADRs vs. Heavy Design Docs**
- Lightweight ADR (1-2 pages): title, context, decision, consequences. Written in 15-30 minutes. Low friction = high adoption.
- Heavy design doc (5-20 pages): problem statement, requirements, alternatives analysis, detailed design, rollout plan. Written in days. Thorough but high friction.
- When to use which: ADR for most decisions. Full design doc only for decisions with >$100K cost impact, cross-team dependencies, or irreversible infrastructure choices.

### What to Document: Decisions, Not Just Diagrams

**The Documentation Priority Stack** (in order of value per minute spent):

1. **Architecture Decision Records** — Why did we choose X over Y? Highest ROI documentation.
2. **System context diagram** — What talks to what? One diagram, kept current.
3. **Runbooks** — How to operate, debug, recover. Written during incidents, refined after.
4. **Data flow diagrams** — Where does data go? Critical for compliance and debugging.
5. **Component diagrams** — Internal structure. Useful but changes frequently.
6. **Detailed design docs** — Full specifications. Only for the most complex systems.

**AI-Specific Documentation Needs**:
- Model card per deployed model (capabilities, limitations, eval results, bias analysis)
- Prompt registry (all production prompts with version history and performance data)
- Data lineage documentation (where does training/retrieval data come from?)
- Eval suite documentation (what are we measuring, what are the thresholds?)
- Incident playbooks specific to AI failures (hallucination spikes, quality degradation, cost runaway)

**The "Decision Journal" Practice**: Senior engineers maintain a running decision journal — not just big architectural decisions, but the smaller ones too. "We chose to chunk at 512 tokens because..." This builds institutional knowledge that survives team changes.

---

## Documentation Templates List

| Template | Purpose | Update Frequency | Owner |
|---|---|---|---|
| **Architecture Decision Record (ADR)** | Capture context, decision, consequences for significant choices | At decision time (immutable once written) | Tech Lead |
| **Model Card** | Document model capabilities, limitations, eval results, bias analysis | Per model version | ML Engineer |
| **System Context Diagram** | Show system boundaries, external dependencies, data flows | Quarterly or on significant change | Platform Architect |
| **Runbook / Playbook** | Step-by-step operational procedures for incidents and maintenance | After each incident (update) | On-call Engineer |
| **API Contract** | OpenAPI/protobuf spec for all service interfaces | Per release | Service Owner |
| **Data Flow Diagram** | Map data from ingestion through processing to storage/serving | Per feature launch | Data Engineer |
| **Eval Suite Spec** | Document what's measured, thresholds, failure actions | Per eval change | ML Engineer |
| **Cost Model** | Document expected cost per request/user/feature with scaling projections | Monthly review | Platform Lead |

---

## Documentation Review Cadence

| Review Type | Frequency | Participants | Output |
|---|---|---|---|
| ADR backlog check | Biweekly | Tech leads | New ADRs drafted for undocumented decisions |
| Architecture diagram refresh | Quarterly | Platform team + product leads | Updated diagrams, deprecated components marked |
| Runbook drill | Monthly | On-call rotation | Runbook gaps identified and fixed |
| Model card audit | Per model deployment | ML eng + ethics review | Updated cards, stale cards archived |
| Full documentation health check | Semi-annually | Architecture team | Documentation debt backlog prioritized |

---

## Documentation Tooling Comparison

| Tool | Strengths | Weaknesses | Best For |
|---|---|---|---|
| **Markdown in repo (docs/)** | Version-controlled, lives with code, PR reviews | Poor discoverability, no rich rendering | ADRs, technical specs |
| **Confluence/Notion** | Searchable, rich media, collaboration | Drifts from code, no version control | Runbooks, onboarding, broad audience |
| **Backstage (Spotify)** | Service catalog + docs, TechDocs plugin | Setup overhead, maintenance cost | Large orgs with many services |
| **Structurizr** | Architecture-as-code (C4 model), versioned diagrams | Learning curve, narrow focus | Architecture diagrams specifically |
| **Swimm** | Auto-validates docs against code changes | Newer tool, smaller ecosystem | Keeping docs in sync with code |
