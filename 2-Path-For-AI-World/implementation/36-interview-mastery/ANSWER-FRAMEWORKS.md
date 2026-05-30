# Reusable Answer Frameworks for AI Architect Interviews

## Why Frameworks Matter

Frameworks give your answers structure, completeness, and consistency. When an interviewer asks an open-ended question, a framework ensures you don't miss critical dimensions while demonstrating systematic thinking. These seven frameworks cover the most common question patterns in senior AI architect interviews.

---

## Framework 1: Four Views Framework

**Use when**: Asked to evaluate an architecture, compare approaches, or critique a system design.

### The Four Views

| View | Key Questions | What Senior Architects Cover |
|------|--------------|------------------------------|
| **Data View** | What data flows where? What's the lineage? How is quality ensured? | Data pipelines, embedding strategies, chunk boundaries, metadata schemas, versioning of training/eval data |
| **Compute View** | What runs where? What are latency/throughput characteristics? | GPU vs CPU allocation, async vs sync paths, batch vs streaming, autoscaling triggers, cold start mitigation |
| **Control View** | Who decides what? What policies govern behavior? | Guardrails placement, circuit breakers, rate limits, approval workflows, human-in-the-loop triggers, A/B routing |
| **Trust View** | What can go wrong? How do we detect and recover? | Hallucination detection, PII leakage prevention, adversarial input handling, audit trails, compliance boundaries |

### How to Apply

**Step 1**: State the framework explicitly: "I evaluate architectures through four lenses: data, compute, control, and trust."

**Step 2**: Walk through each view systematically, spending more time on views most relevant to the question.

**Step 3**: Identify tensions between views: "The data view wants maximum context (long chunks), but the compute view needs low latency (short chunks). We resolve this with hierarchical retrieval—coarse chunks for recall, fine chunks for the final prompt."

### Example Application

**Question**: "How would you evaluate a RAG system that's underperforming?"

**Answer using framework**:
- **Data View**: Are embeddings stale? Is chunking losing context at boundaries? Is metadata enabling proper filtering? Check embedding drift metrics.
- **Compute View**: Is the retrieval latency budget consumed before generation starts? Are we hitting token limits and truncating context?
- **Control View**: Are relevance thresholds properly tuned? Is the reranker actually improving precision or just adding latency?
- **Trust View**: Is the system hallucinating because retrieved context is contradictory? Are users getting confident-sounding wrong answers?

---

## Framework 2: Evaluation First Framework

**Use when**: Asked to design, improve, or validate any AI system. Especially powerful for showing maturity—most candidates jump to solutions; you start with "how would we know if it's working?"

### The Framework

```
1. Define success metrics BEFORE architecture
2. Establish baseline measurements
3. Design evaluation pipeline (offline + online)
4. Build system with evaluation hooks
5. Deploy with measurement gates
6. Iterate based on evidence
```

### Three Evaluation Layers

| Layer | What It Measures | When It Runs | Examples |
|-------|-----------------|--------------|----------|
| **Offline** | Component quality in isolation | Before deployment | Retrieval recall@k, generation faithfulness, embedding quality |
| **Online** | System behavior in production | During serving | Latency p50/p95/p99, hallucination rate, user satisfaction signals |
| **Business** | Outcome achievement | Continuously | Ticket deflection rate, time-to-resolution, cost per interaction |

### Key Principles

1. **Eval before build**: "Before I design the retrieval pipeline, let me define what 'good retrieval' means for this use case—precision@5 > 0.8, with latency < 200ms."

2. **Offline predicts online**: "We validate that our offline eval correlates with online metrics. If offline faithfulness score doesn't predict user-reported accuracy, our eval is broken."

3. **Business closes the loop**: "Technical metrics matter only insofar as they drive business outcomes. We track the causal chain: better retrieval → better answers → fewer escalations → lower cost."

### Example Application

**Question**: "Design a Q&A system for internal documentation."

**Answer using framework**:
"Before architecture, let me define success:
- **Business metric**: 40% reduction in tickets to documentation team within 6 months
- **Online metrics**: Answer accuracy > 90% (human-judged sample), latency < 3s, user satisfaction > 4.2/5
- **Offline metrics**: Retrieval recall@10 > 0.85, faithfulness > 0.9, answer relevance > 0.8

Now I'll design evaluation infrastructure first—a golden test set of 200 question-answer pairs from the documentation team, automated scoring pipeline, and weekly human evaluation of 50 random production queries. With this in place, every architectural decision becomes testable."

---

## Framework 3: Security Layers Framework

**Use when**: Asked about security, safety, compliance, or risk management in AI systems.

### The Five Layers

```
Layer 1: Input Validation    → Block malicious inputs before they reach the model
Layer 2: Context Isolation   → Prevent data leakage between tenants/contexts
Layer 3: Model Guardrails    → Constrain model behavior at inference time
Layer 4: Output Filtering    → Catch harmful/leaked content before user sees it
Layer 5: Audit & Detection   → Log everything, detect anomalies, enable forensics
```

### Layer Details

**Layer 1 - Input Validation**
- Prompt injection detection (classifier-based + rule-based)
- Input length and format validation
- Rate limiting per user/tenant
- PII detection and masking in inputs
- Known attack pattern matching

**Layer 2 - Context Isolation**
- Tenant-scoped vector stores (not just metadata filtering)
- Session isolation (no cross-session context leakage)
- Document-level access control enforced at retrieval time
- Separate embedding spaces for different classification levels

**Layer 3 - Model Guardrails**
- System prompt hardening (instruction hierarchy)
- Tool use restrictions (allowlist, not blocklist)
- Response format constraints
- Topic boundaries and refusal patterns
- Constitutional AI principles for alignment

**Layer 4 - Output Filtering**
- PII/credential detection in outputs
- Toxicity and harm classification
- Citation verification (does the output match sources?)
- Confidence calibration (flag low-confidence responses)
- Regex patterns for known sensitive formats (SSN, credit cards)

**Layer 5 - Audit & Detection**
- Complete conversation logging (encrypted, access-controlled)
- Anomaly detection on usage patterns
- Red team testing (automated + manual)
- Incident response playbooks
- Compliance reporting dashboards

### How to Apply

"I think about AI security in five layers, defense-in-depth style. No single layer is sufficient—we need all five because each catches different threat vectors. Let me walk through how each applies to this system..."

---

## Framework 4: Tuning Order Framework

**Use when**: Asked how to improve AI system quality, or how to approach optimization.

### The Order (Cheapest/Fastest First)

```
1. Prompt Engineering     → Hours to implement, zero training cost
2. Retrieval Optimization → Days to implement, infrastructure cost only
3. Fine-tuning           → Weeks to implement, moderate compute cost
4. Custom Training       → Months to implement, significant cost
5. Architecture Change   → Quarters to implement, high org cost
```

### Decision Matrix

| Level | When to Use | Expected Improvement | Risk |
|-------|------------|---------------------|------|
| **Prompt Engineering** | First attempt, quick experiments | 10-30% quality improvement | Low—easily reversible |
| **Retrieval Optimization** | Prompt is good but context is wrong | 20-50% for retrieval-dependent tasks | Low—infrastructure only |
| **Fine-tuning** | Need domain adaptation, style control | 10-40% on domain tasks | Medium—need eval pipeline |
| **Custom Training** | Unique task, no existing model fits | Variable, potentially transformative | High—data, compute, expertise |
| **Architecture Change** | Fundamental limitations hit | Removes ceiling, doesn't guarantee improvement | Very high—organizational disruption |

### Key Principles

1. **Exhaust cheaper options first**: "Before fine-tuning, have we tried few-shot examples? Chain-of-thought? Better retrieval? Often 80% of the gain comes from the cheapest interventions."

2. **Measure at each step**: "We don't move to the next level without evidence that the current level is insufficient. If prompt engineering gets us to 85% accuracy and the target is 90%, fine-tuning might close that gap—but we need the eval pipeline to prove it."

3. **Compound improvements**: "These aren't exclusive. The best systems combine optimized prompts + excellent retrieval + targeted fine-tuning. But we implement and validate sequentially."

### Example Application

**Question**: "Our AI customer support bot gives generic answers. How do you improve it?"

**Answer**: "I'd work through the tuning order:
1. **Prompt engineering**: Add company voice guidelines, few-shot examples of ideal responses, structured output format. Measure improvement.
2. **Retrieval optimization**: Are we pulling the right knowledge articles? Improve chunking, add metadata filtering by product/issue type, implement reranking. Measure again.
3. **Fine-tuning**: If still generic, fine-tune on 1000+ examples of excellent agent responses. This teaches tone and domain-specific reasoning patterns.
4. I'd expect steps 1-2 to solve 80% of the problem. Step 3 for the remaining 20%."

---

## Framework 5: Cost Optimization Framework

**Use when**: Asked about reducing costs, justifying spend, or designing for efficiency.

### The Three Levers

```
1. Reduce Calls    → Do we need to call the model at all?
2. Reduce Tokens   → Can we achieve the same result with less input/output?
3. Reduce Model    → Can a cheaper model handle this case?
```

### Detailed Strategies

**Lever 1: Reduce Calls**
- Semantic caching (cache responses for similar queries)
- Deterministic routing (rule-based handling for simple cases)
- Batch processing (combine multiple requests)
- Pre-computation (generate common answers offline)
- User-side filtering (prevent obviously bad queries)

**Lever 2: Reduce Tokens**
- Prompt compression (remove redundancy, use abbreviations in system prompts)
- Smart context selection (only retrieve what's needed)
- Output length control (constrain response format)
- Conversation summarization (compress history)
- Efficient few-shot (minimal examples that maximize signal)

**Lever 3: Reduce Model**
- Cascade architecture (small model first, escalate to large)
- Task-specific routing (use GPT-4 for reasoning, GPT-3.5 for formatting)
- Distillation (train smaller model on larger model's outputs)
- Fine-tuned small models (domain-specific small > general large)
- Edge inference for simple classification

### Cost Formula

```
Total Cost = Σ (calls_per_tier × tokens_per_call × cost_per_token)

Optimization target: Minimize total cost while maintaining quality above threshold
```

### Example Application

**Question**: "Our AI system costs $50K/month. Reduce it to $20K without quality loss."

**Answer**: "I'd analyze the cost breakdown across the three levers:
1. **Reduce calls**: Implement semantic cache—typically 30-40% of queries are near-duplicates. Add deterministic routing for FAQ-like queries (another 10-15%).
2. **Reduce tokens**: Audit prompts for bloat. Often system prompts accumulate instructions over time. Compress context window—are we stuffing 10 documents when 3 would suffice?
3. **Reduce model**: Implement a cascade—route 60% of simple queries to GPT-3.5-turbo (10x cheaper), escalate complex ones to GPT-4. Fine-tune a small model for the most common query types.

Expected savings: Cache (35%) + routing (15%) + cascade (30%) = ~60% reduction, hitting the $20K target."

---

## Framework 6: Risk Tier Framework

**Use when**: Asked about governance, deployment strategy, or how to handle different types of AI applications.

### The Three Tiers

| Tier | Risk Level | Examples | Governance Required |
|------|-----------|----------|-------------------|
| **Tier 1** | Low | Internal summarization, code suggestions with human review, content tagging | Team-level review, standard monitoring |
| **Tier 2** | Medium | Customer-facing chat, automated document generation, recommendation systems | Architecture review board, A/B testing required, rollback plan |
| **Tier 3** | High | Medical/legal advice, financial decisions, autonomous actions with real-world impact | Ethics review, legal sign-off, human-in-the-loop mandatory, external audit |

### Governance Requirements by Tier

**Tier 1 - Standard**
- Code review of prompts/pipelines
- Basic monitoring (latency, errors)
- Weekly quality spot-checks
- Team-owned eval suite

**Tier 2 - Enhanced**
- All of Tier 1, plus:
- Architecture review before launch
- Automated evaluation pipeline with quality gates
- A/B testing with statistical significance
- Incident response plan
- Monthly bias/fairness audit
- User feedback loop with action triggers

**Tier 3 - Critical**
- All of Tier 2, plus:
- Ethics committee review
- Legal/compliance sign-off
- External audit (annual minimum)
- Human-in-the-loop for edge cases
- Explainability requirements (why did the system decide this?)
- Regulatory compliance documentation
- Insurance/liability assessment
- Kill switch with <5 minute activation

### How to Apply

"I classify AI applications into three risk tiers. The tier determines governance overhead—we don't want to slow down low-risk experiments with heavy process, but we can't deploy high-risk systems without proper safeguards. Let me classify this system and describe the appropriate governance..."

---

## Framework 7: Progressive Deployment Framework

**Use when**: Asked about rollout strategy, migration, or how to safely introduce AI into production.

### The Five Stages

```
Stage 1: Shadow Mode      → AI runs but outputs aren't shown to users
Stage 2: Internal Only    → Available to internal users/testers
Stage 3: Controlled GA    → Small percentage of external users, with fallback
Stage 4: Broad GA         → Majority of users, monitoring-heavy
Stage 5: Full Production  → Standard operation with ongoing optimization
```

### Stage Details

**Stage 1 - Shadow Mode (1-2 weeks)**
- AI processes real traffic but responses are logged, not served
- Compare AI responses against existing system/human responses
- Measure quality metrics without user impact
- Identify failure modes and edge cases
- **Gate to Stage 2**: Offline eval meets quality thresholds

**Stage 2 - Internal Only (1-2 weeks)**
- Deploy to internal users (employees, beta testers)
- Gather qualitative feedback on response quality
- Stress test with adversarial inputs
- Validate monitoring and alerting
- **Gate to Stage 3**: Internal satisfaction > 4/5, no critical issues

**Stage 3 - Controlled GA (2-4 weeks)**
- 5-10% of external traffic routed to AI
- Side-by-side comparison with existing system
- Statistical significance testing on key metrics
- Automatic rollback triggers defined
- **Gate to Stage 4**: No degradation in key metrics, positive signals

**Stage 4 - Broad GA (2-4 weeks)**
- 50-90% of traffic
- Focus on long-tail issues and scale behavior
- Cost monitoring at scale
- Performance optimization
- **Gate to Stage 5**: Stable metrics for 2+ weeks, cost within budget

**Stage 5 - Full Production (Ongoing)**
- 100% traffic
- Continuous monitoring and improvement
- Regular eval refresh (prevent drift)
- Periodic red team exercises
- Feature iteration based on production learnings

### Rollback Criteria

| Signal | Action |
|--------|--------|
| Error rate > 2x baseline | Automatic rollback |
| Latency p99 > SLA | Alert + manual review |
| User satisfaction drop > 10% | Pause rollout, investigate |
| Any PII leakage | Immediate shutdown |
| Hallucination rate > threshold | Reduce traffic percentage |

### Example Application

**Question**: "How would you roll out an AI-powered search to replace existing keyword search?"

**Answer**: "I'd use progressive deployment across five stages:
1. **Shadow**: Run AI search in parallel for 2 weeks. Log results alongside keyword results. Measure NDCG@10 comparison.
2. **Internal**: Give employees the AI search option. Gather feedback, fix obvious issues.
3. **Controlled GA**: 5% of users get AI search with a 'try classic search' fallback button. Track click-through rate, time-to-find, and support tickets.
4. **Broad GA**: Scale to 50%, then 80%. Monitor for long-tail queries that work in keyword but fail in AI.
5. **Full Production**: Deprecate keyword search (but keep the index warm for 90 days as emergency fallback).

Key: At every stage, we have defined rollback criteria and the technical ability to revert in under 5 minutes."

---

## Combining Frameworks

The real power is combining frameworks in a single answer:

**Example**: "Design a safe, cost-effective AI system for medical question answering."

1. **Risk Tier** → This is Tier 3 (medical advice). Governance requirements are high.
2. **Security Layers** → All five layers needed, with emphasis on output filtering (medical accuracy).
3. **Evaluation First** → Define clinical accuracy metrics before architecture.
4. **Cost Optimization** → Cascade architecture (simple questions → small model, complex → large model + retrieval).
5. **Progressive Deployment** → Extended shadow mode with clinician review.
6. **Tuning Order** → Start with retrieval from medical knowledge bases + careful prompting. Fine-tuning only after thorough evaluation.
7. **Four Views** → Data (medical knowledge freshness), Compute (latency for urgent queries), Control (when to refuse/escalate), Trust (liability, audit trail).

This combination demonstrates the senior architect's ability to hold multiple concerns simultaneously and produce coherent, defensible architecture decisions.
