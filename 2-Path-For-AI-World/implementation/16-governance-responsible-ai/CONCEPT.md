# Governance and Responsible AI

## 1. NIST AI Risk Management Framework (AI RMF 1.0)

The NIST AI RMF provides a structured approach to managing AI risks throughout the AI lifecycle. It comprises four core functions:

### 1.1 GOVERN Function
The crosscutting function that establishes organizational context and enables the other functions:

- **Policies and Procedures**: Establish AI governance policies defining acceptable use, risk tolerance, roles/responsibilities
- **Accountability Structures**: Define who owns AI risk at each level (board, executive, operational)
- **Culture**: Foster risk-aware culture where teams proactively identify and report AI issues
- **Legal and Regulatory Compliance**: Map regulatory requirements to organizational controls
- **Stakeholder Engagement**: Identify and involve affected communities in governance decisions

Key activities:
- Define organizational risk tolerance for AI systems
- Establish AI ethics board or governance committee
- Create AI use case approval process
- Define escalation paths for AI-related decisions
- Maintain AI system inventory/registry

### 1.2 MAP Function
Contextualizes risks relative to the AI system:

- **System Context**: Document intended use, deployment context, affected stakeholders
- **Risk Identification**: Identify potential harms (to individuals, groups, organizations, ecosystems)
- **Interdependencies**: Map dependencies between AI components, data sources, downstream systems
- **Assumptions and Limitations**: Document what the system can/cannot do, known failure modes

Key activities:
- Create system impact assessments
- Document intended vs. out-of-scope uses
- Identify affected populations and differential impacts
- Map data lineage and provenance
- Document human-AI interaction patterns

### 1.3 MEASURE Function
Employs quantitative and qualitative methods to analyze risks:

- **Metrics and Benchmarks**: Define measurable indicators for trustworthiness characteristics
- **Testing and Evaluation**: Conduct regular assessments (accuracy, fairness, robustness, security)
- **Monitoring**: Continuously track system performance against established baselines
- **Feedback Integration**: Incorporate user feedback, incident reports, external research

Key metrics categories:
- Accuracy and reliability metrics
- Fairness metrics (demographic parity, equalized odds, predictive parity)
- Robustness metrics (adversarial testing, distribution shift detection)
- Privacy metrics (differential privacy guarantees, re-identification risk)
- Explainability metrics (feature attribution stability, explanation fidelity)

### 1.4 MANAGE Function
Allocates resources to mapped and measured risks:

- **Risk Prioritization**: Rank risks by severity, likelihood, and organizational risk tolerance
- **Risk Response**: Select response strategy (accept, mitigate, transfer, avoid)
- **Implementation**: Deploy controls and countermeasures
- **Monitoring Effectiveness**: Track whether mitigations achieve desired risk reduction
- **Continuous Improvement**: Update risk management based on new information

---

## 2. ISO/IEC 42001 - AI Management System (AIMS)

ISO/IEC 42001 provides a certifiable management system standard for organizations developing, providing, or using AI:

### 2.1 Structure (aligned with ISO management system standards)

| Clause | Topic | Key Requirements |
|--------|-------|-----------------|
| 4 | Context of the Organization | Understand internal/external issues affecting AI, interested parties, scope of AIMS |
| 5 | Leadership | Top management commitment, AI policy, organizational roles/responsibilities |
| 6 | Planning | Actions to address risks/opportunities, AI objectives, planning to achieve them |
| 7 | Support | Resources, competence, awareness, communication, documented information |
| 8 | Operation | Operational planning/control, AI risk assessment, AI risk treatment, AI impact assessment |
| 9 | Performance Evaluation | Monitoring, measurement, analysis, evaluation, internal audit, management review |
| 10 | Improvement | Nonconformity, corrective action, continual improvement |

### 2.2 Key Controls (Annex A)

- **A.2 Policies for AI**: Establish, communicate, and review AI-specific policies
- **A.3 Internal Organization**: Define roles (AI risk owner, data steward, model validator)
- **A.4 Resources for AI Systems**: Ensure adequate resources (compute, data, expertise)
- **A.5 Assessing Impacts of AI Systems**: Conduct impact assessments before deployment
- **A.6 AI System Lifecycle**: Manage through design, development, deployment, operation, retirement
- **A.7 Data for AI Systems**: Data quality, provenance, consent, retention
- **A.8 Information for Interested Parties**: Transparency about AI system capabilities/limitations
- **A.9 Use of AI Systems**: Monitor operational use, detect misuse
- **A.10 Third-party and Customer Relationships**: Vendor management, SLAs for AI services

### 2.3 Implementation Approach

1. Gap analysis against current practices
2. Define scope and boundaries of AIMS
3. Establish AI policy and objectives
4. Implement required processes and controls
5. Train personnel
6. Monitor, audit, review
7. Certification audit (Stage 1 + Stage 2)

---

## 3. EU AI Act

### 3.1 Risk Categories

| Category | Examples | Requirements |
|----------|----------|-------------|
| **Unacceptable Risk (Banned)** | Social scoring by governments, real-time biometric identification in public spaces (with exceptions), manipulation exploiting vulnerabilities, emotion recognition in workplace/education | Prohibited - cannot be placed on market |
| **High Risk** | Critical infrastructure, education/employment decisions, law enforcement, migration/asylum, biometric identification, credit scoring | Full compliance regime (see below) |
| **Limited Risk** | Chatbots, deepfakes, emotion recognition (non-prohibited) | Transparency obligations |
| **Minimal Risk** | Spam filters, AI in video games, inventory management | No specific requirements (voluntary codes) |

### 3.2 High-Risk System Requirements

1. **Risk Management System** (Art. 9): Continuous iterative process throughout AI lifecycle
2. **Data Governance** (Art. 10): Training data quality, relevance, representativeness, bias examination
3. **Technical Documentation** (Art. 11): Detailed description enabling assessment of compliance
4. **Record-Keeping** (Art. 12): Automatic logging of events during operation
5. **Transparency** (Art. 13): Clear information to deployers about capabilities/limitations
6. **Human Oversight** (Art. 14): Measures enabling human oversight during use
7. **Accuracy, Robustness, Cybersecurity** (Art. 15): Appropriate levels throughout lifecycle
8. **Quality Management System** (Art. 17): Documented policies, procedures, instructions

### 3.3 General-Purpose AI (GPAI) Requirements

- **All GPAI providers**: Technical documentation, EU copyright law compliance, publish training content summary
- **GPAI with systemic risk** (>10^25 FLOPs threshold): Model evaluation, adversarial testing, incident reporting, cybersecurity measures, energy consumption reporting

### 3.4 Compliance Timeline

- February 2025: Prohibitions on unacceptable risk systems
- August 2025: GPAI rules and governance provisions
- August 2026: Most high-risk AI system requirements
- August 2027: High-risk systems in Annex I (regulated products)

---

## 4. OWASP Top 10 for LLM Applications (2025)

| # | Vulnerability | Description | Mitigation |
|---|--------------|-------------|-----------|
| LLM01 | **Prompt Injection** | Manipulating LLM via crafted inputs to override instructions | Input validation, privilege control, human approval for sensitive actions |
| LLM02 | **Sensitive Information Disclosure** | LLM reveals confidential data in responses | Output filtering, data sanitization in training, access controls |
| LLM03 | **Supply Chain Vulnerabilities** | Compromised training data, models, or plugins | Verify model provenance, scan dependencies, use trusted sources |
| LLM04 | **Data and Model Poisoning** | Corrupting training/fine-tuning data to alter behavior | Data validation, anomaly detection, provenance tracking |
| LLM05 | **Improper Output Handling** | Trusting LLM output without validation in downstream systems | Output validation, encoding, sandboxing, least privilege |
| LLM06 | **Excessive Agency** | LLM granted too many capabilities or autonomy | Minimize permissions, require human approval, rate limiting |
| LLM07 | **System Prompt Leakage** | Exposing system prompts revealing business logic or controls | Treat prompts as public, external guardrails, don't rely on prompt secrecy |
| LLM08 | **Vector and Embedding Weaknesses** | Manipulating RAG through poisoned embeddings/documents | Access controls on vector stores, input validation, relevance filtering |
| LLM09 | **Misinformation** | LLM generates false/misleading content (hallucination) | RAG with verified sources, output verification, confidence scoring |
| LLM10 | **Unbounded Consumption** | Resource exhaustion through excessive LLM queries | Rate limiting, token budgets, query complexity limits, monitoring |

---

## 5. Model Cards, System Cards, Data Cards

### 5.1 Model Cards (Mitchell et al., 2019)

Purpose: Standardized documentation for trained ML models.

Sections:
- **Model Details**: Developer, version, type, architecture, training date, license
- **Intended Use**: Primary use cases, out-of-scope uses, users
- **Factors**: Relevant demographic/phenotypic groups, instrumentation, environment
- **Metrics**: Performance measures chosen, why, thresholds
- **Evaluation Data**: Datasets used, motivation, preprocessing
- **Training Data**: Summary (may be proprietary), size, composition
- **Quantitative Analyses**: Disaggregated results across factors
- **Ethical Considerations**: Known risks, harms, limitations
- **Caveats and Recommendations**: Additional guidance for use

### 5.2 System Cards

Purpose: Document entire AI systems (not just individual models).

Additional sections beyond model cards:
- **System Architecture**: Components, data flows, integration points
- **Human-in-the-Loop**: Where and how humans interact with the system
- **Feedback Mechanisms**: How user/stakeholder feedback is collected and acted upon
- **Deployment Context**: Infrastructure, scaling, geographic availability
- **Monitoring and Alerting**: What is monitored, alert thresholds, response procedures
- **Incident History**: Past incidents, resolutions, lessons learned
- **Downstream Dependencies**: Systems that consume this system's outputs

### 5.3 Data Cards (Pushkarna et al., 2022)

Purpose: Document datasets used in AI systems.

Sections:
- **Dataset Overview**: Name, version, purpose, creator, license
- **Composition**: What data is included, instances, features, labels
- **Collection Process**: How data was collected, who collected it, time period
- **Preprocessing**: Cleaning, transformations, filtering applied
- **Distribution**: How dataset is distributed, access controls
- **Maintenance**: Who maintains it, update frequency, retention
- **Legal and Ethical**: Consent, privacy review, known biases
- **Intended Use**: Tasks, domains, populations appropriate for

---

## 6. AI Risk Register

### 6.1 Risk Identification

Sources of AI risk:
- **Model risks**: Accuracy degradation, bias amplification, adversarial vulnerability, hallucination
- **Data risks**: Data poisoning, privacy violations, consent issues, quality degradation, representativeness
- **Operational risks**: System outages, scaling failures, dependency failures, misuse
- **Security risks**: Prompt injection, model theft, data exfiltration, adversarial attacks
- **Ethical risks**: Discrimination, lack of transparency, autonomy violation, environmental impact
- **Legal/Compliance risks**: Regulatory violations, intellectual property, liability
- **Reputational risks**: Public trust erosion, media attention, stakeholder concerns

### 6.2 Risk Assessment

**Likelihood scoring** (1-5):
1. Rare (< 5% probability in next 12 months)
2. Unlikely (5-20%)
3. Possible (20-50%)
4. Likely (50-80%)
5. Almost Certain (> 80%)

**Impact scoring** (1-5):
1. Negligible (minor inconvenience, easily corrected)
2. Minor (limited harm to small group, short duration)
3. Moderate (significant harm to individuals or moderate business impact)
4. Major (serious harm to many, significant legal/financial consequences)
5. Critical (catastrophic harm, existential business threat, irreversible damage)

**Risk Rating** = Likelihood × Impact
- 1-4: Low (accept/monitor)
- 5-9: Medium (mitigate within quarter)
- 10-15: High (mitigate immediately)
- 16-25: Critical (stop/escalate to board)

### 6.3 Risk Mitigation Strategies

- **Avoid**: Don't deploy the system / remove feature
- **Mitigate**: Implement controls to reduce likelihood or impact
- **Transfer**: Insurance, contractual allocation, third-party services
- **Accept**: Document acceptance rationale with appropriate authority sign-off

---

## 7. Human Oversight Process

### 7.1 Levels of Human Oversight

| Level | Description | When to Use |
|-------|-------------|-------------|
| **Human-in-the-loop** | Human approves every decision | High-risk, low-volume decisions (loan denials, medical diagnoses) |
| **Human-on-the-loop** | Human monitors and can intervene | Medium-risk, high-volume (content moderation, fraud detection) |
| **Human-over-the-loop** | Human sets parameters, reviews periodically | Low-risk, very high-volume (recommendations, spam filtering) |

### 7.2 Intervention Triggers

- Confidence score below threshold
- Anomaly detected in input or output
- Sensitive category affected (protected characteristics)
- High-stakes decision (financial threshold, safety-critical)
- Adversarial pattern detected
- User requests human review
- Regulatory requirement mandates human decision

### 7.3 Oversight Design Principles

1. Meaningful oversight (not rubber-stamping)
2. Adequate time and information for decision
3. Authority to override AI recommendations
4. No automation bias pressure
5. Clear accountability for oversight decisions
6. Regular calibration and training for overseers

---

## 8. Incident Reporting and Response

### 8.1 Incident Classification

**Severity levels**:
- **SEV1 (Critical)**: Active harm to individuals, regulatory breach, system weaponized
- **SEV2 (High)**: Significant bias discovered affecting decisions, data breach involving AI data
- **SEV3 (Medium)**: Performance degradation affecting users, minor fairness issues
- **SEV4 (Low)**: Near-miss events, minor anomalies, documentation gaps

**Incident types**:
- Safety incident (harm to individuals)
- Fairness/bias incident
- Privacy/security incident
- Reliability/availability incident
- Misuse/abuse incident
- Compliance incident

### 8.2 Response Process

1. **Detection**: Automated monitoring, user reports, external reports
2. **Triage**: Classify severity, assign responder, establish communication channel
3. **Containment**: Reduce harm (disable system, activate fallback, restrict access)
4. **Investigation**: Root cause analysis, impact assessment, evidence preservation
5. **Remediation**: Fix underlying issue, validate fix, restore service
6. **Communication**: Notify affected parties, regulators (if required), stakeholders
7. **Post-Incident Review**: Blameless retrospective, lessons learned, action items
8. **Prevention**: Systemic improvements to prevent recurrence

---

## 9. Auditability Requirements

### 9.1 What Must Be Auditable

- **Decision logs**: Every consequential AI decision with inputs, outputs, confidence, reasoning
- **Model lineage**: Training data, hyperparameters, training process, evaluation results
- **Change history**: All changes to models, data, configuration with who/when/why
- **Access logs**: Who accessed what data/models/systems and when
- **Override logs**: Human overrides of AI decisions with rationale
- **Incident logs**: All incidents, responses, resolutions
- **Compliance evidence**: Proof of compliance activities (testing, reviews, approvals)

### 9.2 Retention Requirements

- Decision logs: Minimum duration matching the decision's reversibility period
- Model artifacts: Full lifecycle plus statutory retention period
- Training data provenance: Lifecycle of all models trained on it
- Audit trails: Regulatory minimum (often 5-7 years)

---

## 10. Data Retention and Right to Deletion

### 10.1 Challenges in AI Context

- **Model memorization**: Models may memorize training data, making deletion incomplete
- **Embedding persistence**: Vector databases may retain semantic information about deleted data
- **Derived insights**: Features/patterns derived from deleted data persist in model weights
- **Backup and versioning**: Deleted data may exist in model checkpoints, training snapshots

### 10.2 Approaches

- **Machine unlearning**: Techniques to remove influence of specific data from trained models
- **Retraining**: Full retraining excluding deleted data (gold standard but expensive)
- **Approximate unlearning**: SISA training, influence functions, gradient-based methods
- **Architecture design**: Design systems where deletion is practical (modular, retrieval-based)
- **Data minimization**: Collect and retain only what's necessary
- **Anonymization**: Transform data so individuals cannot be identified

---

## 11. Vendor Risk Management

### 11.1 AI Vendor Assessment Areas

- **Model provenance**: Where did training data come from? What's the model architecture?
- **Security posture**: Data handling, encryption, access controls, certifications (SOC2, ISO 27001)
- **Compliance**: GDPR compliance, AI Act readiness, sector-specific requirements
- **Transparency**: Can you audit the model? Access evaluations? Understand limitations?
- **Business continuity**: What happens if vendor is acquired/shutdown? Model portability?
- **Data handling**: Where is data processed? Data residency? Sub-processors?
- **Performance guarantees**: SLAs for accuracy, latency, availability
- **Incident response**: Vendor's process for AI incidents affecting your data/users

### 11.2 Contract Considerations

- Right to audit
- Data processing agreements
- Liability for AI-caused harm
- IP ownership of fine-tuned models
- Exit strategy and data portability
- Notification requirements for model changes
- Compliance with your AI governance policies

---

## 12. Responsible AI Principles

### 12.1 Fairness
- No unfair discrimination against individuals or groups
- Equitable outcomes across demographic groups
- Awareness of historical biases in data
- Regular fairness audits with appropriate metrics

### 12.2 Transparency
- Clear disclosure when AI is being used
- Explainable decisions (appropriate to audience)
- Open about limitations and failure modes
- Accessible documentation

### 12.3 Accountability
- Clear ownership for AI system outcomes
- Defined escalation and remediation paths
- Mechanisms for affected parties to seek recourse
- Regular governance reviews

### 12.4 Safety
- Robust testing before deployment
- Continuous monitoring for harmful outputs
- Fail-safe mechanisms and graceful degradation
- Red-teaming and adversarial testing

### 12.5 Privacy
- Data minimization
- Purpose limitation
- Informed consent
- Technical privacy protections (differential privacy, federated learning)

### 12.6 Inclusiveness
- Diverse perspectives in design and development
- Accessibility across abilities, languages, cultures
- Consideration of marginalized communities
- Participatory design approaches

---

## 13. Bias Detection and Mitigation

### 13.1 Types of Bias

- **Historical bias**: Reflects past societal inequities in training data
- **Representation bias**: Under/over-representation of groups in data
- **Measurement bias**: Features/labels measured differently across groups
- **Aggregation bias**: Single model for diverse populations with different relationships
- **Evaluation bias**: Benchmark datasets not representative of real-world use
- **Deployment bias**: System used in contexts different from design intent
- **Automation bias**: Users over-rely on AI outputs

### 13.2 Detection Methods

- Disaggregated evaluation across protected attributes
- Statistical parity testing
- Counterfactual fairness analysis
- Intersectional analysis (combinations of attributes)
- Adversarial debiasing probes
- Community feedback and participatory audits

### 13.3 Mitigation Approaches

**Pre-processing** (data-level):
- Resampling / reweighting
- Data augmentation for underrepresented groups
- Removing correlations with protected attributes

**In-processing** (model-level):
- Fairness constraints during training
- Adversarial debiasing
- Multi-objective optimization (accuracy + fairness)

**Post-processing** (output-level):
- Threshold adjustment per group
- Calibration across groups
- Reject option classification

---

## 14. Explainability and Interpretability

### 14.1 Levels of Explanation

| Audience | Need | Approach |
|----------|------|----------|
| End user | Why this decision? | Natural language, counterfactual ("if X were different...") |
| Domain expert | Is the reasoning sound? | Feature importance, decision rules, similar cases |
| Regulator | Is it compliant? | Full audit trail, statistical analysis, documentation |
| Developer | What's going wrong? | Attention visualization, gradient analysis, probing |

### 14.2 Techniques

- **SHAP** (SHapley Additive exPlanations): Game-theoretic feature attribution
- **LIME** (Local Interpretable Model-agnostic Explanations): Local surrogate models
- **Attention visualization**: For transformer models, visualize attention patterns
- **Counterfactual explanations**: Minimal changes to input that change output
- **Concept-based explanations**: Map to human-understandable concepts (TCAV)
- **Chain-of-thought**: For LLMs, generate reasoning steps (note: may not reflect actual computation)

---

## 15. Governance Operating Model

### 15.1 Three Lines Model for AI

| Line | Role | Responsibilities |
|------|------|-----------------|
| **First Line** | AI development teams | Build responsibly, self-assess, implement controls, document |
| **Second Line** | AI governance/risk function | Set standards, review, challenge, provide tools and frameworks |
| **Third Line** | Internal audit | Independent assurance, verify effectiveness of governance |

### 15.2 Key Roles

- **Chief AI Officer (CAIO)**: Strategic AI direction, governance accountability
- **AI Ethics Board**: Review high-risk use cases, set ethical guidelines
- **AI Risk Manager**: Maintain risk register, coordinate assessments
- **Model Validator**: Independent model evaluation and challenge
- **Data Steward**: Data quality, lineage, compliance
- **AI Auditor**: Periodic independent review of AI systems and governance

### 15.3 Governance Cadence

- **Weekly**: Model monitoring review, incident triage
- **Monthly**: Risk register update, metrics dashboard review
- **Quarterly**: AI ethics board meeting, governance policy review
- **Annually**: Full AI system inventory audit, governance maturity assessment, training refresh
- **Event-driven**: New deployment review, incident response, regulatory change assessment

### 15.4 Maturity Levels

1. **Initial**: Ad-hoc, individual responsibility, reactive
2. **Developing**: Basic policies exist, some documentation, awareness growing
3. **Defined**: Formal governance structure, standardized processes, regular reviews
4. **Managed**: Metrics-driven, continuous monitoring, proactive risk management
5. **Optimizing**: Continuous improvement, industry leadership, embedded culture
