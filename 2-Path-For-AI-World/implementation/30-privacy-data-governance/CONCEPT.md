# Privacy and Data Governance for AI Systems

## Core Philosophy: Privacy is Architecture, Not Paperwork

Privacy in AI systems cannot be bolted on after the fact. It must be woven into the architecture from day one. Every component that touches data—prompts, memory, logs, traces, eval datasets, vector indexes, vendor APIs—needs a privacy policy and a deletion story.

The fundamental challenge: AI systems are **data amplifiers**. A single piece of PII can propagate across dozens of subsystems within milliseconds:
- User sends a message containing their SSN
- It enters the prompt sent to an LLM vendor
- It appears in the response
- It's logged in observability traces
- It's stored in conversation memory
- It might be embedded in a vector index
- It could end up in an eval dataset
- It might be cached at multiple layers

**If you can't trace where data goes, you can't delete it. If you can't delete it, you can't comply with privacy law.**

---

## Data Minimization

### Principle
Only collect what you need. Every piece of data has a cost: storage, security, compliance, deletion complexity.

### In AI Context
- Don't store full prompts if summaries suffice
- Don't retain conversation history longer than needed
- Don't embed entire documents if key passages suffice
- Don't log full request/response bodies in production
- Don't send more context to vendors than the task requires

### Implementation Pattern
```
Before storing ANY data, answer:
1. What specific purpose does this serve?
2. What's the minimum data needed for that purpose?
3. How long do we need it?
4. Who needs access?
5. How will we delete it?
```

### Anti-Patterns
- Storing "everything in case we need it later"
- Logging full prompts "for debugging" without retention limits
- Keeping conversation history indefinitely "for personalization"
- Embedding all user documents without classification

---

## Purpose Limitation

### Principle
Data collected for one purpose cannot be used for another without explicit consent.

### AI-Specific Violations (Common)
- Using customer support conversations to train models
- Using user queries to build eval datasets
- Using conversation history for analytics without consent
- Sharing prompt data with vendors for their model improvement
- Using personal data in A/B testing of prompts

### Implementation
```python
class DataPurpose:
    CONVERSATION = "active_conversation"      # Real-time use
    PERSONALIZATION = "user_personalization"   # Memory/preferences
    ANALYTICS = "aggregate_analytics"         # De-identified only
    MODEL_TRAINING = "model_improvement"      # Requires explicit consent
    EVALUATION = "system_evaluation"          # Must be anonymized
    DEBUGGING = "incident_investigation"      # Time-limited access
```

Every data access must declare its purpose. The system validates that the declared purpose matches the consent given.

---

## Consent Management

### Consent Types in AI Systems
1. **Service consent** — Basic operation (required for service)
2. **Memory consent** — System remembers things about you
3. **Analytics consent** — Usage patterns analyzed
4. **Training consent** — Data used to improve models
5. **Third-party consent** — Data sent to vendor APIs
6. **Cross-context consent** — Data shared across conversations

### Consent Properties
- **Granular**: Per-purpose, per-data-type
- **Revocable**: Can be withdrawn at any time with effect
- **Informed**: User understands what they're consenting to
- **Explicit**: Not buried in terms of service
- **Auditable**: Complete record of consent history

### Consent Withdrawal = Deletion Trigger
When consent is withdrawn:
1. Stop using data for that purpose immediately
2. Queue deletion of data collected under that consent
3. Propagate deletion to all downstream systems
4. Verify deletion completion
5. Record withdrawal in audit trail

---

## Retention Policy Design

### Retention Categories for AI Systems

| Data Type | Typical Retention | Rationale |
|-----------|------------------|-----------|
| Active conversation | Session or 30 days | Immediate utility |
| Conversation memory | Until user deletes or 1 year | Personalization |
| Observability traces | 30-90 days | Debugging |
| Audit logs | 1-7 years | Compliance |
| Eval datasets | Until refreshed (anonymized) | Quality assurance |
| Vector embeddings | Tied to source document lifecycle | Search functionality |
| Model training data | Until model is retired | Model lineage |
| Cached responses | Hours to days | Performance |
| Error logs with PII | 7 days max, then redact | Incident response |

### Retention Enforcement
- Automated cleanup jobs (not manual processes)
- Retention clock starts at collection, not "when we get around to it"
- Cascading deletion when source data expires
- Verification that deletion actually happened
- Exception process for legal holds

---

## Right-to-Delete Workflows

### The Challenge in AI Systems
Deletion in traditional systems: delete rows from a database.
Deletion in AI systems: delete data from potentially dozens of interconnected systems, some of which don't support point deletion (embeddings, model weights).

### Components That May Hold User Data
1. **Databases** — User profiles, preferences, history
2. **Conversation stores** — Chat history, messages
3. **Memory systems** — Agent memories about the user
4. **Vector indexes** — Embeddings of user documents/messages
5. **Caches** — Redis, CDN, application caches
6. **Logs** — Application logs, access logs, error logs
7. **Traces** — Observability traces with request data
8. **Eval datasets** — If user data was used for evaluation
9. **Model weights** — If user data was used in fine-tuning (hardest)
10. **Vendor systems** — Data sent to third-party APIs
11. **Backups** — All of the above, but in backup storage
12. **Analytics** — Aggregated metrics (may need re-aggregation)

### Deletion Workflow
```
1. Receive deletion request
2. Authenticate the requester
3. Discover all data locations (data inventory)
4. Create deletion plan with dependencies
5. Execute deletion in dependency order
6. Handle undeletable data (model weights → document + flag)
7. Verify deletion across all systems
8. Generate deletion certificate
9. Record audit trail (what was deleted, not the data itself)
10. Notify requester of completion
```

### Hard Problems
- **Vector embeddings**: Must re-index without the deleted documents
- **Fine-tuned models**: Cannot "unlearn" — must retrain or document
- **Distributed caches**: Must invalidate across all nodes
- **Vendor data**: Must request deletion from vendors (and verify)
- **Backups**: Must track what needs deletion when backups rotate

---

## Data Residency Requirements

### Common Requirements
- EU data stays in EU (GDPR)
- Healthcare data in specific jurisdictions (HIPAA)
- Financial data residency (various)
- Government data sovereignty

### AI-Specific Residency Challenges
- LLM vendor APIs may process data in any region
- Vector databases may replicate globally
- CDN caches may store data in edge locations worldwide
- Model training may aggregate data across regions

### Architecture Pattern
```
User Request → Region Detection → Regional Router
                                       ↓
                         ┌─────────────────────────────┐
                         │  Region-specific processing  │
                         │  - Regional LLM endpoint     │
                         │  - Regional vector DB        │
                         │  - Regional memory store     │
                         │  - Regional logging          │
                         └─────────────────────────────┘
```

---

## Data Classification

### Sensitivity Levels

| Level | Label | Examples | Controls |
|-------|-------|----------|----------|
| 0 | Public | Marketing content, public docs | None special |
| 1 | Internal | Internal docs, non-sensitive business data | Access control |
| 2 | Confidential | Customer data, PII, business secrets | Encryption + access control + audit |
| 3 | Restricted | SSN, health records, payment cards, secrets | All above + DLP + special handling |

### Classification in AI Pipelines
Every piece of data entering an AI system must be classified:
- **At ingestion**: Classify documents before embedding
- **At prompt construction**: Classify context being assembled
- **At output**: Classify generated responses
- **At logging**: Classify what's being logged
- **At storage**: Classify what's being persisted

---

## PII Detection and Redaction

### PII Categories
- **Direct identifiers**: Name, email, phone, SSN, passport
- **Quasi-identifiers**: Age, zip code, job title (can re-identify in combination)
- **Sensitive attributes**: Health conditions, political views, sexual orientation
- **Behavioral data**: Browsing history, purchase patterns, location history

### Detection Approaches
1. **Regex patterns**: Fast, high precision for structured PII (SSN, email, phone)
2. **NER models**: Better for names, addresses, organizations
3. **Context-aware detection**: Understanding that "my number is 555-1234" is PII
4. **Custom patterns**: Organization-specific identifiers (employee IDs, account numbers)

### Redaction Strategies
- **Full redaction**: Replace with `[REDACTED]`
- **Type-preserving**: Replace with `[EMAIL]`, `[PHONE]`, `[NAME]`
- **Format-preserving**: Replace with same-format fake data
- **Partial redaction**: Show last 4 digits of SSN: `***-**-1234`
- **Tokenization**: Replace with reversible token (for authorized de-identification)

---

## Anonymization and Pseudonymization

### Anonymization (Irreversible)
- Remove all identifiers
- Generalize quasi-identifiers (age → age range, zip → region)
- Add noise to numerical values
- Suppress rare combinations (k-anonymity)
- Result: Cannot re-identify individuals

### Pseudonymization (Reversible with Key)
- Replace identifiers with consistent tokens
- Maintain referential integrity (same person = same token)
- Key stored separately with strict access control
- Useful when you need to re-identify for legitimate purposes

### When to Use Which
- **Anonymization**: Eval datasets, analytics, public reporting
- **Pseudonymization**: Cross-system linking, debugging, research

---

## Differential Privacy Basics

### Concept
Add calibrated noise to query results so that no individual's data significantly affects the output. Mathematical guarantee: an adversary cannot determine whether any individual's data was included.

### In AI Context
- Add noise to aggregated analytics (user behavior patterns)
- Use differentially private training (DP-SGD) for fine-tuning
- Apply to eval metrics to prevent memorization detection
- Protect against membership inference attacks

### Key Parameters
- **Epsilon (ε)**: Privacy budget. Lower = more private, less accurate
- **Delta (δ)**: Probability of privacy failure. Should be very small
- **Sensitivity**: How much one individual can affect the result

### Practical Guidance
- ε < 1: Strong privacy (significant noise)
- ε = 1-10: Moderate privacy (common in practice)
- ε > 10: Weak privacy (may not provide meaningful protection)

---

## Privacy Impact Assessments (PIA)

### When to Conduct
- New AI feature that processes personal data
- New vendor integration
- New data collection
- Change in data processing purpose
- New cross-system data flow

### Assessment Framework
1. **Data inventory**: What personal data is involved?
2. **Purpose**: Why is processing necessary?
3. **Proportionality**: Is the data collection proportionate to the purpose?
4. **Data flows**: Where does data go? (Including vendors)
5. **Risks**: What could go wrong? (Breach, misuse, bias)
6. **Mitigations**: How are risks addressed?
7. **Residual risk**: What risk remains after mitigations?
8. **Decision**: Proceed, modify, or reject?

---

## Prompt/Log Redaction

### The Problem
Prompts and logs are the most common source of PII leakage in AI systems. Developers enable verbose logging for debugging and forget that prompts contain user data.

### Redaction Points
1. **Before sending to LLM**: Redact unnecessary PII from context
2. **Before logging**: Redact PII from logged prompts/responses
3. **Before tracing**: Redact PII from observability traces
4. **Before analytics**: Redact PII from usage metrics

### Implementation Pattern
```
User Input → PII Detection → Redacted Input → LLM
                                    ↓
                            Redacted Logs/Traces
```

Never log raw prompts in production. Always pass through redaction pipeline.

---

## Trace Retention and Privacy

### Challenge
Observability traces are essential for debugging but contain sensitive data:
- Full request/response payloads
- User identifiers
- Context assembled from user data
- Model outputs that may echo PII

### Strategy
- **Hot tier** (0-7 days): Full traces, restricted access, auto-redaction of known PII
- **Warm tier** (7-30 days): Redacted traces, operational access
- **Cold tier** (30-90 days): Metadata only (latency, tokens, errors), no content
- **Archive** (90+ days): Aggregated metrics only

---

## Eval Dataset Privacy Concerns

### Risks
- Eval datasets often derived from real user interactions
- May contain PII even after "anonymization"
- Shared broadly within organization for testing
- May be committed to version control
- Could be sent to vendor systems for evaluation

### Mitigations
- Use synthetic data for evaluation where possible
- Apply rigorous anonymization to real data
- Maintain access controls on eval datasets
- Never commit eval data to source control
- Track provenance: which real data contributed to which eval
- Honor deletion requests: re-derive eval data if source is deleted

---

## Synthetic Data Privacy Risk

### The False Safety of Synthetic Data
Synthetic data generated from real data can still leak privacy:
- Models memorize training data
- Synthetic data may reproduce rare individuals verbatim
- Statistical properties of synthetic data can enable re-identification
- Prompt-based synthesis may echo training data PII

### Mitigations
- Validate synthetic data doesn't reproduce real records
- Apply differential privacy to synthetic data generation
- Monitor for memorization (membership inference tests)
- Maintain clear separation between synthetic and real data

---

## Cross-Tenant Privacy Boundaries

### Multi-Tenant AI Systems
- Each tenant's data must be completely isolated
- Prompts from one tenant must never appear in another's context
- Vector indexes must be tenant-scoped
- Memory systems must enforce tenant boundaries
- Model fine-tuning must not cross tenant boundaries
- Caches must be tenant-aware

### Failure Modes
- Shared vector index returns another tenant's documents
- Shared cache returns another tenant's responses
- Shared memory contains cross-tenant information
- Shared eval dataset contains multiple tenants' data
- Shared model fine-tuned on multiple tenants' data

---

## Memory Deletion (Critical for Agents)

### The Agent Memory Problem
AI agents that maintain memory about users create deep privacy challenges:
- Memories may reference multiple users
- Memories may be derived (inferred, not directly stated)
- Memories influence future behavior
- Memories may be summarized (original data lost but influence remains)

### Deletion Requirements
- Delete all memories directly about the user
- Delete all memories derived from user's data
- Delete memories that reference the user in other users' contexts
- Invalidate any decisions/preferences learned from the user
- Verify that agent behavior no longer reflects deleted memories

### Implementation
```
1. Index all memories by contributing users
2. On deletion request, find all memories linked to user
3. For shared memories (multiple users), redact user's contribution
4. For single-user memories, delete entirely
5. Rebuild any summary/derived memories without user's data
6. Verify agent doesn't exhibit user-specific behavior post-deletion
```

---

## The Architect's Rule

> **"If data can enter prompts, memory, logs, traces, eval datasets, vector indexes, or vendor APIs, it needs a privacy policy and deletion story."**

For every new feature, ask:
1. What data enters this system?
2. Where can it flow from here?
3. Who can access it?
4. How long is it kept?
5. How do we delete it?
6. Can we prove it's deleted?
7. What happens when a user revokes consent?

If you can't answer all seven questions, the feature isn't ready for production.

---

## Regulatory Landscape (Key Requirements)

| Regulation | Key AI Privacy Requirements |
|-----------|---------------------------|
| GDPR | Right to deletion, purpose limitation, data minimization, consent, DPIAs |
| CCPA/CPRA | Right to delete, right to know, opt-out of "sale" (includes AI training) |
| HIPAA | PHI protection, minimum necessary, BAAs with vendors |
| SOC 2 | Data handling controls, access management, monitoring |
| EU AI Act | Transparency, data governance for training data, bias monitoring |
| PIPEDA | Consent, purpose limitation, accuracy, retention limits |

---

## Summary: Privacy Architecture Principles

1. **Minimize** — Collect least data needed
2. **Classify** — Know what sensitivity level every piece of data has
3. **Track** — Know where every piece of data flows
4. **Protect** — Encrypt, redact, access-control appropriately
5. **Limit** — Enforce purpose limitation and retention
6. **Delete** — Have a working deletion story for every data store
7. **Verify** — Prove that privacy controls actually work
8. **Audit** — Maintain complete records of data handling decisions
9. **Test** — Regularly test for privacy violations
10. **Evolve** — Update as systems and regulations change
