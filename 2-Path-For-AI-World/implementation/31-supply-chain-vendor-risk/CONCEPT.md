# Supply Chain and Vendor Risk in AI Systems

## Why This Matters

AI systems have an unprecedented dependency surface. Unlike traditional software where you control most of the logic, AI systems delegate critical reasoning to external providers. A single model provider change can silently alter every output your system produces. A vector database outage can render your RAG system useless. An MCP server compromise can inject malicious tool responses into your agent's decision loop.

**Senior Principle: "Treat AI dependencies as supply-chain dependencies."**

Every model, embedding, vector store, MCP server, dataset, and plugin is an attack surface, a reliability risk, and a compliance concern.

---

## The AI Dependency Surface

### What AI Systems Depend On

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR AI APPLICATION                          │
├─────────────────────────────────────────────────────────────────┤
│ Model Providers    │ OpenAI, Anthropic, Google, Cohere, local   │
│ Embedding Providers│ OpenAI, Cohere, Voyage, HuggingFace       │
│ Vector Databases   │ Pinecone, Weaviate, Qdrant, Milvus, pgvec │
│ MCP Servers        │ Tool providers, external capabilities      │
│ Open-Source Pkgs   │ LangChain, LlamaIndex, transformers       │
│ SaaS Tools         │ Guardrails APIs, moderation, classification│
│ Plugins/Extensions │ Custom tools, browser plugins, connectors  │
│ Datasets           │ Training data, eval sets, RAG corpora      │
│ Cloud Infra        │ GPU providers, serverless inference, CDNs  │
│ A2A Agents         │ Peer agents in multi-agent systems         │
└─────────────────────────────────────────────────────────────────┘
```

Each of these is:
- A potential point of failure
- A potential attack vector
- A potential compliance violation
- A potential cost escalation
- A potential behavior change without notice

---

## Risk Types

### 1. Model Provider Risk

**What can go wrong:**
- Provider deprecates a model version (OpenAI has done this repeatedly)
- Model behavior changes silently between versions
- Rate limits change, breaking your throughput assumptions
- Pricing changes make your cost model unsustainable
- Provider adds content restrictions that block legitimate use cases
- Provider suffers a data breach exposing your prompts
- Provider trains on your data without consent

**Mitigation:**
- Pin model versions explicitly (e.g., `gpt-4-0613` not `gpt-4`)
- Maintain evaluation suites that detect behavior drift
- Implement multi-provider fallback
- Monitor cost per request continuously
- Review ToS changes as security events
- Use data processing agreements (DPAs)

### 2. Embedding Provider Risk

**What can go wrong:**
- Embedding model deprecated → all your vectors become incompatible
- Dimension changes require complete re-indexing
- Semantic drift between model versions means retrieval quality degrades
- Provider outage means no new documents can be indexed

**Mitigation:**
- Track embedding model version alongside every vector
- Maintain re-indexing capability (can regenerate all embeddings)
- Store original text alongside vectors
- Test embedding quality with standardized benchmarks
- Plan for embedding migration (this is expensive and slow)

### 3. Vector DB Vendor Risk

**What can go wrong:**
- Vendor pricing changes (Pinecone has changed pricing models)
- Performance degradation as index grows
- Vendor outage loses your retrieval capability entirely
- Data residency issues with managed cloud instances
- Vendor sunset (startups can fail)

**Mitigation:**
- Abstract vector DB behind an interface
- Maintain export capability (can dump all vectors + metadata)
- Test with alternative vector stores periodically
- Monitor query latency and recall metrics
- Have a self-hosted fallback plan

### 4. MCP Server Supply-Chain Risk

**What can go wrong:**
- Malicious MCP server returns poisoned tool results
- MCP server compromise gives attacker influence over agent decisions
- MCP server goes offline, breaking agent capabilities
- MCP server changes response schema without notice
- Dependency confusion attacks on MCP server packages

**Mitigation:**
- Approve MCP servers through a review process
- Pin MCP server versions
- Validate MCP server responses against schemas
- Monitor MCP server behavior for anomalies
- Run MCP servers in sandboxed environments
- Maintain a registry of approved MCP servers

### 5. Open-Source Dependency Risk

**What can go wrong:**
- Malicious package update (supply-chain attack)
- License change (e.g., BSL transitions)
- Maintainer abandonment
- Breaking changes in minor versions
- Typosquatting attacks on AI package names

**Mitigation:**
- Lock dependency versions
- Use dependency scanning (Snyk, Dependabot, etc.)
- Maintain an approved package registry
- Monitor for license changes
- Audit transitive dependencies
- Sign and verify artifacts

### 6. Model License Risk

**What can go wrong:**
- Model license prohibits commercial use
- License requires attribution you're not providing
- License restricts certain use cases (medical, legal)
- Fine-tuned model inherits base model restrictions
- License changes retroactively

**Mitigation:**
- Track model licenses in your AI BOM
- Legal review before adopting any model
- Maintain license compatibility matrix
- Document fine-tuning lineage

### 7. Dataset License Risk

**What can go wrong:**
- Training data contains copyrighted material
- Dataset license prohibits derivative works
- PII in datasets creates GDPR/CCPA liability
- Dataset poisoning (malicious data injected)

**Mitigation:**
- Document dataset provenance
- Scan for PII before use
- Maintain data lineage records
- Use certified/audited datasets where possible

### 8. SaaS API Risk

**What can go wrong:**
- API deprecation with short notice
- Breaking API changes
- Rate limit reductions
- Data handling policy changes
- Vendor acquisition changes terms

**Mitigation:**
- Abstract APIs behind adapters
- Monitor API changelog feeds
- Maintain contract terms database
- Plan for API migration

### 9. Provider Outage Planning

Every external dependency will eventually go down. Plan for:
- Which components can operate in degraded mode?
- What's the blast radius of each provider outage?
- How long until cached results go stale?
- What's the user experience during outage?
- How do you detect outage vs. degradation?

### 10. Provider Behavior Drift

Models change behavior without version changes. This is insidious because:
- No explicit notification
- Gradual degradation is hard to detect
- Evaluation suites may not cover affected cases
- Users notice before monitoring does

**Detection:**
- Run evaluation suites on schedule (not just on deployment)
- Monitor output distribution statistics
- Track user satisfaction metrics per provider
- Compare outputs across time windows

### 11. Vendor Lock-In

Lock-in vectors in AI:
- Proprietary prompt formats
- Provider-specific function calling schemas
- Vector embeddings tied to specific models
- Fine-tuned models on proprietary platforms
- Proprietary evaluation frameworks
- Custom model distillation locked to provider

### 12. Exit Strategy

For every vendor, document:
- What data/artifacts you need to extract
- How long migration takes
- What capabilities you lose during transition
- What the cost of switching is
- Who the alternative providers are
- What format conversions are needed

### 13. Fallback Provider Strategy

Design your system so that:
- No single provider failure is catastrophic
- Degraded mode is well-defined and tested
- Failover is automatic for critical paths
- Fallback providers are pre-integrated and tested
- Recovery back to primary is also automatic

---

## AI Bill of Materials (AI-BOM)

### What to Track

Every AI system should maintain a complete inventory:

| Category | Track |
|----------|-------|
| Model Provider | Provider name, model ID, version, pin date |
| Embedding Model | Provider, model, dimensions, distance metric |
| Reranker | Provider, model, version |
| Vector DB | Provider, version, index config, region |
| Prompt Versions | Hash, version, author, change reason |
| Tool Schemas | Schema hash, version, capabilities |
| MCP Servers | Server ID, version, trust level, capabilities |
| A2A Agents | Agent ID, version, protocol version |
| Datasets | Source, version, license, hash, size |
| Fine-tuned Models | Base model, training data, hyperparams, date |
| Third-party APIs | Provider, version, endpoint, SLA |
| Deployment Region | Cloud, region, availability zone |
| Owner | Team, contact, escalation path |
| Risk Tier | Critical/High/Medium/Low |

### BOM Lifecycle

```
Register → Track → Monitor → Alert → Review → Update → Audit
```

Every component goes through this lifecycle. Changes trigger reviews. Audits happen on schedule.

---

## Dependency Scanning and Registry Approval

### Scanning Requirements

1. **Pre-adoption scan**: Before any new AI dependency enters the system
2. **Continuous scan**: Regular re-evaluation of existing dependencies
3. **Event-driven scan**: When vulnerability disclosures affect AI components

### Registry Approval Process

```
Developer requests new dependency
    → Security review (attack surface)
    → Legal review (license)
    → Architecture review (lock-in)
    → Performance review (SLA impact)
    → Cost review (budget impact)
    → Approval/Rejection with conditions
    → Registration in AI-BOM
```

Only dependencies in the approved registry may be used in production.

---

## Signed Artifacts

For AI components, signing means:
- **Models**: Hash of model weights, signed by provider
- **Prompts**: Version-controlled with commit signatures
- **Datasets**: Content hash with provenance attestation
- **MCP Servers**: Package signatures, SBOM attestation
- **Configurations**: Signed deployment manifests

Verify signatures at:
- Build time
- Deployment time
- Runtime (for dynamically loaded components)

---

## Network Egress Controls

AI systems make many outbound calls. Control them:
- Whitelist allowed API endpoints per service
- Monitor for unexpected outbound connections
- Block direct internet access from inference services
- Route all provider calls through a gateway
- Log all egress with request/response metadata
- Alert on new egress destinations

---

## Key Principles Summary

1. **Every AI dependency is a supply-chain dependency** — treat it with the same rigor
2. **Pin everything** — models, embeddings, packages, MCP servers
3. **Monitor for drift** — behavior changes without version changes
4. **Plan for exit** — every vendor relationship should have an exit plan
5. **Test fallbacks** — untested fallbacks don't work when needed
6. **Maintain your AI-BOM** — you can't secure what you can't see
7. **Approve before adopt** — no unapproved components in production
8. **Sign and verify** — trust but verify at every layer
9. **Assume breach** — what happens when a provider is compromised?
10. **Cost is a risk** — unexpected cost spikes are operational incidents
