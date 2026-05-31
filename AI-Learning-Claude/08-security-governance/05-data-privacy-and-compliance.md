# Data Privacy and Compliance for AI Systems

## Privacy Challenges Specific to AI

AI systems are privacy nightmares because they **consume, process, and generate** personal data at every stage. Unlike a traditional database where PII sits in defined columns, AI systems scatter personal data across prompts, embeddings, model weights, logs, and outputs in ways that are hard to track and harder to delete.

The analogy: Traditional systems are like a filing cabinet — you know exactly where the sensitive folder is. AI systems are like a person who read the sensitive folder — the information is now distributed throughout their memory in unpredictable ways.

---

## Where PII Hides in AI Systems

### PII in Prompts

Users accidentally (or intentionally) include personal data:
```
"My SSN is 123-45-6789, can you help me fill out this tax form?"
"Here's my colleague's email: john.smith@company.com, please draft a message"
```

**Risk:** This PII goes to the model provider, gets logged, may be used for training.

### PII in Training Data

Models memorize training data, especially repeated or distinctive text:
```
# A model trained on emails might complete:
"Dear Mr. Johnson, your account number 4532-XXXX-XXXX-7891..."
```

**Risk:** Model regurgitates PII from training data to other users.

### PII in RAG Data

Your vector database contains documents with personal information:
```
Employee handbook → names, titles
Customer records → addresses, purchase history
Support tickets → detailed personal issues
```

**Risk:** Retrieved context exposes PII from others to the current user.

### PII in Logs and Traces

Observability captures everything:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "prompt": "My credit card 4532-1234-5678-9012 was charged incorrectly",
  "response": "I see the charge on card ending 9012...",
  "tokens_used": 450
}
```

**Risk:** Log aggregation systems become PII goldmines for attackers.

---

## Data Flow with Privacy Controls

```mermaid
graph LR
    subgraph "Input Stage"
        USER[User Input] --> PII_SCAN[PII Scanner]
        PII_SCAN -->|PII Found| REDACT[Redact/Mask]
        PII_SCAN -->|Clean| PASS[Pass Through]
        REDACT --> CLEAN_INPUT[Cleaned Input]
        PASS --> CLEAN_INPUT
    end

    subgraph "Processing Stage"
        CLEAN_INPUT --> RAG[RAG Retrieval]
        RAG --> PERM_FILTER[Permission Filter]
        PERM_FILTER --> PII_FILTER[PII Filter on Context]
        PII_FILTER --> LLM[LLM]
    end

    subgraph "Output Stage"
        LLM --> OUT_SCAN[Output PII Scan]
        OUT_SCAN -->|PII Detected| OUT_REDACT[Redact Output]
        OUT_SCAN -->|Clean| DELIVER[Deliver Response]
        OUT_REDACT --> DELIVER
    end

    subgraph "Logging Stage"
        CLEAN_INPUT -.-> LOG_REDACT[Redacted Logging]
        LLM -.-> LOG_REDACT
        DELIVER -.-> LOG_REDACT
        LOG_REDACT --> SECURE_LOG[(Encrypted Log Store)]
    end

    style PII_SCAN fill:#ff9999
    style OUT_SCAN fill:#ff9999
    style LOG_REDACT fill:#ffdd57
    style SECURE_LOG fill:#a8e6cf
```

---

## Data Minimization for AI

**Principle:** Only send the minimum data necessary to the LLM.

```python
# BAD: Send entire customer record to LLM
prompt = f"Help this customer: {customer.to_json()}"
# Sends: name, SSN, DOB, address, payment methods, full history...

# GOOD: Send only what's needed for this specific task
relevant_data = {
    "first_name": customer.first_name,
    "issue_category": ticket.category,
    "product": ticket.product_name,
}
prompt = f"Help resolve this {relevant_data['issue_category']} issue about {relevant_data['product']} for {relevant_data['first_name']}"
```

---

## GDPR Compliance for AI

### Right to Erasure (Article 17)

**The hard question:** Can you delete someone's data from embeddings?

- **Vector databases:** You can delete specific document embeddings ✓
- **Fine-tuned models:** You cannot easily remove individual data points ✗
- **Foundation models:** Impossible to remove from base model weights ✗

**Practical approach:**
1. Don't fine-tune on personal data
2. Keep personal data in retrievable/deletable stores (RAG, not weights)
3. Maintain deletion audit trails
4. Re-embed documents after removing PII

### Purpose Limitation (Article 5)

Data collected for customer support cannot be used to train a marketing model without consent.

```python
class DataUsagePolicy:
    def check_purpose(self, data_source, intended_use):
        allowed_purposes = self.get_consent_purposes(data_source)
        if intended_use not in allowed_purposes:
            raise PurposeLimitationViolation(
                f"Data from {data_source} not consented for {intended_use}"
            )
```

### Automated Decision-Making (Article 22)

If your AI makes decisions that significantly affect people (loan approvals, hiring), users have the right to:
- Know a decision was automated
- Get a human review
- Receive an explanation of the logic

---

## HIPAA for Healthcare AI

Protected Health Information (PHI) in AI systems requires:

| Requirement | AI Implementation |
|------------|------------------|
| Minimum necessary | Only include relevant medical data in prompts |
| Access controls | Permission-aware RAG for patient records |
| Audit trails | Log all access to PHI through AI |
| BAA with vendors | Business Associate Agreement with model providers |
| De-identification | Strip 18 HIPAA identifiers before processing |
| Encryption | Encrypt PHI in transit to/from model APIs |

**Critical:** Most cloud LLM providers are NOT HIPAA-compliant by default. You need specific enterprise agreements (Azure OpenAI with BAA, AWS Bedrock with BAA).

---

## SOC2 for AI SaaS

If you're building AI products, SOC2 auditors will ask:

1. **How do you protect customer data sent to AI models?** → Encryption, DLP, data minimization
2. **Where does the data go geographically?** → Data residency controls
3. **Is customer data used for training?** → Opt-out mechanisms, contractual guarantees
4. **How do you handle data breaches involving AI?** → Incident response plan
5. **What's your data retention policy?** → Auto-deletion of prompts/logs after N days

---

## Data Residency Requirements

**The problem:** You send a prompt to OpenAI's API — where does that data physically go?

```
User in EU → Your EU server → OpenAI API (US?) → Response
                                    ↑
                     Potential GDPR violation!
```

**Solutions:**
- Use regional API endpoints (Azure OpenAI in EU regions)
- Self-host models for sensitive workloads
- Contractual data processing agreements
- Encrypt data client-side before sending

---

## The Data Flow Audit

For compliance, you must be able to answer: "Where does personal data go in our AI system?"

**Audit checklist:**
1. What PII enters the system? (Input classification)
2. Where is it sent? (Model provider, vector DB, cache, logs)
3. How long is it retained? (TTLs on all stores)
4. Who can access it? (Access controls at every layer)
5. Can it be deleted on request? (Erasure capability)
6. Is it encrypted at rest and in transit? (Encryption audit)
7. Does it cross borders? (Data residency map)
8. Is it used for purposes beyond original consent? (Purpose tracking)

Document this as a **Data Protection Impact Assessment (DPIA)** — required under GDPR for high-risk processing like AI.

---

## Key Takeaways

1. **PII is everywhere in AI systems** — prompts, embeddings, logs, outputs. Scan all layers.
2. **Data minimization is your best defense** — don't send data you don't need.
3. **Logging vs privacy is a real tension** — redact PII from logs, or use privacy-preserving logging.
4. **Deletion from AI is hard** — keep PII in deletable stores, not model weights.
5. **Regional deployment matters** — know where your data physically travels.
