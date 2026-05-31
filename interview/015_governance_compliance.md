# AI Governance & Compliance - Staff Architect Interview

## Question 71: AI Governance Framework Design
**Difficulty: Staff Level | Topic: Governance | Asked at: Microsoft, Google, Large Enterprises**

Design an enterprise AI governance framework that covers model lifecycle management, ethical review, risk assessment, and regulatory compliance. How do you balance innovation speed with governance rigor?

### Expected Answer:

**Enterprise AI Governance Architecture:**

1. **Governance Layers:**
   ```
   ┌─────────────────────────────────────────┐
   │ Layer 1: Strategic Governance            │
   │ - AI Ethics Board (quarterly review)     │
   │ - Risk appetite definition               │
   │ - Policy setting                         │
   ├─────────────────────────────────────────┤
   │ Layer 2: Operational Governance          │
   │ - Model risk assessment (per deployment) │
   │ - Automated policy enforcement           │
   │ - Continuous monitoring                  │
   ├─────────────────────────────────────────┤
   │ Layer 3: Technical Controls             │
   │ - Guardrails, content filters            │
   │ - Access controls, audit logging         │
   │ - Model cards, documentation             │
   └─────────────────────────────────────────┘
   ```

2. **Model Risk Tiering:**
   | Tier | Risk Level | Examples | Governance Required |
   |------|-----------|----------|-------------------|
   | 1 | Low | Internal search, summarization | Self-assessment + auto-approval |
   | 2 | Medium | Customer-facing chatbot | Team review + testing |
   | 3 | High | Financial decisions, hiring assist | Ethics board + external audit |
   | 4 | Critical | Healthcare, autonomous systems | Regulatory approval + ongoing monitoring |

3. **Automated Governance Pipeline:**
   ```python
   class GovernancePipeline:
       async def evaluate_deployment(self, model_deployment: ModelDeployment):
           report = GovernanceReport()
           
           # Step 1: Risk classification
           risk_tier = self.classify_risk(model_deployment)
           report.risk_tier = risk_tier
           
           # Step 2: Automated checks (all tiers)
           report.bias_assessment = await self.run_bias_tests(model_deployment)
           report.safety_assessment = await self.run_safety_tests(model_deployment)
           report.performance_assessment = await self.run_performance_tests(model_deployment)
           report.privacy_assessment = await self.run_privacy_tests(model_deployment)
           
           # Step 3: Documentation completeness
           report.documentation = self.check_documentation(model_deployment)
           # Model card, data card, intended use, limitations, risks
           
           # Step 4: Approval routing
           if risk_tier <= 1 and report.all_checks_pass():
               report.decision = 'AUTO_APPROVED'
           elif risk_tier == 2:
               report.decision = 'PENDING_TEAM_REVIEW'
               await self.notify_reviewers(model_deployment.team)
           else:
               report.decision = 'PENDING_ETHICS_BOARD'
               await self.notify_ethics_board(model_deployment)
           
           return report
   ```

4. **Continuous Compliance Monitoring:**
   - Real-time bias monitoring (demographic parity, equalized odds)
   - Output toxicity scanning (every response in production)
   - Drift detection (model performance degradation over time)
   - Usage auditing (who's using the model, for what purpose)
   - Incident tracking (hallucinations, harmful outputs, user complaints)
   - Regulatory change monitoring (new AI regulations → impact assessment)

5. **Balancing Speed vs Governance:**
   - Pre-approved patterns: Common use cases with pre-approved configurations
   - Sandbox environments: Experiment freely, governance only at promotion
   - Progressive deployment: Start restricted, earn broader access with track record
   - Automated checks: 80% of governance is automated (minutes, not weeks)
   - Exception process: Fast-track with CTO/ethics board sponsor

---

## Question 72: Responsible AI and Bias Detection
**Difficulty: Staff Level | Topic: Fairness | Asked at: Google, Microsoft, Meta**

Design a bias detection and mitigation system for an AI-powered hiring assistant that uses RAG over resumes and job descriptions. How do you ensure fairness across protected categories while maintaining utility?

### Expected Answer:

**Bias Detection & Mitigation for Hiring AI:**

1. **Bias Sources in Hiring RAG:**
   | Source | Example | Mitigation |
   |--------|---------|------------|
   | Training data | Historical hiring favored certain demographics | De-bias training data |
   | Embedding bias | "Engineer" closer to male names in embedding space | Embedding de-biasing |
   | Retrieval bias | Certain resume formats/schools ranked higher | Blind retrieval features |
   | Generation bias | LLM reflects societal stereotypes | Output auditing + guardrails |
   | Feedback loop | Biased outcomes → biased future training | Regular bias audits |

2. **Bias Detection Pipeline:**
   ```python
   class BiasDetector:
       PROTECTED_CATEGORIES = ['gender', 'race', 'age', 'disability', 'nationality']
       
       def audit_system(self, test_dataset: List[Resume]) -> BiasReport:
           results = {}
           
           for category in self.PROTECTED_CATEGORIES:
               # Create matched pairs (identical qualifications, different demographics)
               pairs = self.create_matched_pairs(test_dataset, category)
               
               # Run both through system
               scores_group_a = [self.score_resume(p.resume_a) for p in pairs]
               scores_group_b = [self.score_resume(p.resume_b) for p in pairs]
               
               # Statistical tests
               results[category] = {
                   'mean_difference': np.mean(scores_group_a) - np.mean(scores_group_b),
                   'statistical_significance': self.t_test(scores_group_a, scores_group_b),
                   'demographic_parity': self.demographic_parity(scores_group_a, scores_group_b),
                   'equal_opportunity': self.equal_opportunity(scores_group_a, scores_group_b),
                   'disparate_impact': min(
                       np.mean(scores_group_a) / np.mean(scores_group_b),
                       np.mean(scores_group_b) / np.mean(scores_group_a)
                   )  # Should be > 0.8 (4/5 rule)
               }
           
           return BiasReport(results=results)
   ```

3. **Mitigation Strategies:**
   ```python
   class BiasMitigator:
       # Pre-processing: Remove protected info from retrieval
       def anonymize_resume(self, resume):
           """Remove all demographic signals before RAG processing."""
           anonymized = resume.copy()
           anonymized.remove_names()        # Names correlate with gender/race
           anonymized.remove_photos()       # Visual demographic signals
           anonymized.remove_dates()        # Age inference from graduation year
           anonymized.standardize_format()  # Remove school prestige signals
           anonymized.remove_addresses()    # Socioeconomic inference
           return anonymized
       
       # In-processing: Embedding de-biasing
       def debias_embedding(self, embedding, bias_direction):
           """Remove bias direction from embedding space."""
           # Compute projection onto bias direction
           projection = np.dot(embedding, bias_direction) * bias_direction
           # Remove projection
           debiased = embedding - projection
           return debiased / np.linalg.norm(debiased)
       
       # Post-processing: Outcome calibration
       def calibrate_scores(self, scores, demographics):
           """Ensure equal selection rates across groups."""
           for group in demographics.unique_groups():
               group_scores = scores[demographics == group]
               # Normalize within group to ensure equal distribution
               scores[demographics == group] = self.percentile_normalize(group_scores)
           return scores
   ```

4. **Continuous Fairness Monitoring:**
   ```
   Production Pipeline:
   Resumes → [Anonymization] → [RAG Scoring] → [Bias Check] → Output
                                                      │
                                              If bias detected:
                                              - Flag for human review
                                              - Log incident
                                              - Adjust calibration
   
   Weekly Audit:
   - Run matched-pair tests (500 synthetic pairs per category)
   - Compare against fairness thresholds
   - Generate compliance report
   - Alert if any metric violates 4/5 rule
   ```

5. **Regulatory Compliance:**
   - EEOC compliance (US): Document adverse impact analysis
   - EU AI Act: High-risk system, requires conformity assessment
   - NYC Local Law 144: Annual bias audit by independent auditor
   - Document all decisions + provide explanations
   - Right to human review for any AI-influenced hiring decision

---

## Question 73: Audit Logging and Explainability
**Difficulty: Staff Level | Topic: Transparency | Asked at: Financial Services, Healthcare**

Design an audit logging and explainability system for a RAG-powered financial advisory tool. Regulators require full traceability of every recommendation. How do you provide explanations for AI decisions at scale?

### Expected Answer:

**Financial AI Audit & Explainability Architecture:**

1. **Complete Decision Trace:**
   ```python
   class AuditableRAGPipeline:
       async def process(self, query, user) -> AuditedResponse:
           trace = AuditTrace(trace_id=uuid4())
           
           # Log everything at each step
           trace.log_input(query=query, user=user, timestamp=now())
           
           # Retrieval with explanation
           retrieved_docs = await self.retrieve(query)
           trace.log_retrieval(
               query_embedding=query_embedding.tolist(),
               documents_retrieved=[{
                   'doc_id': d.id,
                   'similarity_score': d.score,
                   'source': d.source,
                   'retrieved_text': d.text[:500]
               } for d in retrieved_docs],
               retrieval_method='hybrid_rrf',
               filters_applied=self.get_active_filters(user)
           )
           
           # Generation with explanation
           response = await self.generate(query, retrieved_docs)
           trace.log_generation(
               model_id=self.model.id,
               model_version=self.model.version,
               prompt_template_id=self.prompt.id,
               full_prompt=self.last_prompt,  # Complete prompt sent to LLM
               raw_response=response.raw,
               processed_response=response.processed,
               token_usage={'input': response.input_tokens, 'output': response.output_tokens},
               temperature=self.config.temperature
           )
           
           # Post-processing explanation
           trace.log_postprocessing(
               guardrails_applied=self.guardrails.last_results,
               citations_added=response.citations,
               disclaimers_added=response.disclaimers
           )
           
           # Store complete trace
           await self.audit_store.save(trace)
           
           return AuditedResponse(
               response=response,
               trace_id=trace.trace_id,
               explanation=self.generate_explanation(trace)
           )
   ```

2. **Explanation Generation:**
   ```python
   class ExplanationEngine:
       def generate_explanation(self, trace: AuditTrace) -> Explanation:
           return Explanation(
               # Why this answer?
               reasoning=f"This recommendation is based on {len(trace.docs)} "
                        f"documents from {trace.sources}",
               
               # What sources?
               sources=[{
                   'document': doc.title,
                   'relevance': doc.score,
                   'key_quote': doc.highlight
               } for doc in trace.top_docs],
               
               # What was considered?
               factors_considered=self.extract_factors(trace),
               
               # What was NOT considered?
               limitations=[
                   "Based on data available as of " + trace.data_freshness,
                   "Does not account for personal risk tolerance",
                   "Past performance not indicative of future results"
               ],
               
               # Confidence level
               confidence=trace.confidence_score,
               confidence_explanation=self.explain_confidence(trace)
           )
   ```

3. **Immutable Audit Storage:**
   | Requirement | Implementation |
   |-------------|---------------|
   | Tamper-proof | Append-only log with cryptographic chaining |
   | Searchable | Indexed by user, timestamp, trace_id, decision type |
   | Retainable | 7-year retention (financial regulation requirement) |
   | Exportable | Structured format for regulatory submission |
   | Scalable | Time-series DB + object storage for large traces |

4. **Regulatory Report Generation:**
   ```python
   class RegulatoryReporter:
       def generate_report(self, period: DateRange) -> ComplianceReport:
           return ComplianceReport(
               period=period,
               total_decisions=self.count_decisions(period),
               decision_breakdown=self.breakdown_by_type(period),
               model_versions_used=self.get_model_versions(period),
               bias_metrics=self.compute_fairness_metrics(period),
               error_rate=self.compute_error_rate(period),
               escalation_rate=self.compute_escalation_rate(period),
               sample_traces=self.random_sample(period, n=100),
               anomalies_detected=self.get_anomalies(period),
               human_override_rate=self.compute_override_rate(period)
           )
   ```

5. **Real-Time Explainability at Scale:**
   - Pre-compute explanation templates (don't use LLM for explanations)
   - Cache common explanations (similar queries → similar explanations)
   - Tiered detail: Summary for user, full trace for compliance team
   - Async trace storage (don't add latency to user response)
   - Sampling for expensive analysis (full analysis on 10%, summary on 100%)

---

## Question 74: Content Safety and Guardrails
**Difficulty: Staff Level | Topic: Safety Systems | Asked at: OpenAI, Anthropic, Google**

Design a comprehensive content safety system (guardrails) for a consumer-facing AI assistant. Cover input filtering, output filtering, topic restrictions, and graceful refusals. How do you minimize false positives while catching all harmful content?

### Expected Answer:

**Multi-Layer Content Safety Architecture:**

1. **Safety Pipeline:**
   ```
   User Input
       │
       ▼
   ┌──────────────────┐
   │ Input Classifier  │ → Block/Allow/Flag
   │ (2ms, rule-based) │
   └────────┬─────────┘
            │ (if allowed)
            ▼
   ┌──────────────────┐
   │ Semantic Safety   │ → Block/Allow/Warn
   │ (15ms, ML model)  │
   └────────┬─────────┘
            │ (if allowed)
            ▼
   ┌──────────────────┐
   │ LLM Generation    │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ Output Safety     │ → Block/Modify/Pass
   │ (20ms, ML model)  │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ PII Redaction     │ → Redact/Pass
   │ (5ms, NER)        │
   └────────┬─────────┘
            │
            ▼
   Response to User
   ```

2. **Input Safety Classifier:**
   ```python
   class InputSafetyClassifier:
       CATEGORIES = [
           'harassment', 'hate_speech', 'self_harm', 'sexual_content',
           'violence', 'illegal_activity', 'pii_sharing', 'prompt_injection'
       ]
       
       def classify(self, text: str) -> SafetyDecision:
           # Layer 1: Fast regex/keyword (blocks obvious violations)
           keyword_result = self.keyword_filter(text)
           if keyword_result.blocked:
               return SafetyDecision(action='block', reason=keyword_result.category)
           
           # Layer 2: ML classifier (catches nuanced violations)
           ml_scores = self.safety_model.predict(text)
           # Returns: {category: probability} for each category
           
           max_category = max(ml_scores, key=ml_scores.get)
           max_score = ml_scores[max_category]
           
           if max_score > 0.95:
               return SafetyDecision(action='block', reason=max_category, confidence=max_score)
           elif max_score > 0.7:
               return SafetyDecision(action='flag', reason=max_category, confidence=max_score)
           
           return SafetyDecision(action='allow')
   ```

3. **Topic Restriction Engine:**
   ```python
   class TopicRestrictionEngine:
       """Configurable per-deployment topic boundaries."""
       
       def __init__(self, config):
           self.allowed_topics = config.allowed_topics
           self.blocked_topics = config.blocked_topics
           self.gray_areas = config.gray_area_handling
       
       def check_topic(self, query: str, response: str) -> TopicDecision:
           detected_topics = self.topic_classifier.classify(query + response)
           
           for topic in detected_topics:
               if topic in self.blocked_topics:
                   return TopicDecision(
                       allowed=False,
                       refusal_message=self.get_refusal(topic),
                       redirect=self.get_redirect(topic)
                   )
           
           return TopicDecision(allowed=True)
       
       def get_refusal(self, topic):
           """Graceful, helpful refusal messages."""
           refusals = {
               'medical_advice': "I can't provide medical advice. Please consult a healthcare professional.",
               'legal_advice': "For legal matters, please consult a qualified attorney.",
               'financial_advice': "I'm not qualified to give financial advice. Consider consulting a financial advisor.",
           }
           return refusals.get(topic, "I'm not able to help with this topic.")
   ```

4. **Minimizing False Positives:**
   | Strategy | Impact on FP | Impact on FN | Trade-off |
   |----------|-------------|-------------|-----------|
   | Higher threshold (0.95) | Fewer FP | More FN (misses) | Riskier |
   | Context-aware classification | Fewer FP | Same FN | More compute |
   | Multi-model ensemble | Fewer FP | Fewer FN | Higher latency |
   | User history consideration | Fewer FP | Same FN | Privacy concern |
   | Human review for gray area | Zero FP (for reviewed) | Higher latency | Expensive |
   
   Best approach: **Cascade with escalation**
   - High confidence violations → auto-block
   - Medium confidence → softer intervention (warning, topic redirect)
   - Low confidence → allow with monitoring

5. **Metrics & Continuous Improvement:**
   - False positive rate: <1% (measure via user feedback + human review)
   - False negative rate: <0.1% for critical categories (red-team testing)
   - Latency overhead: <50ms total for all safety checks
   - User satisfaction: Track completion rates before/after safety interventions
   - Weekly review: Sample flagged content, retrain classifiers monthly

---

## Question 75: Secrets Management and Key Rotation for AI Services
**Difficulty: Staff Level | Topic: Security Operations | Asked at: Cloud Providers, Enterprise**

Design a secrets management system for an AI platform that manages API keys for multiple LLM providers, vector DB credentials, embedding service tokens, and customer encryption keys. Handle rotation, access control, and breach response.

### Expected Answer:

**AI Platform Secrets Management:**

1. **Secrets Taxonomy:**
   | Secret Type | Rotation Frequency | Impact if Leaked |
   |------------|-------------------|-----------------|
   | LLM API keys (OpenAI, etc.) | 30 days | Cost exposure, data access |
   | Vector DB credentials | 90 days | Data breach |
   | Customer encryption keys | Annual | Total data compromise |
   | Service-to-service tokens | 24 hours | Lateral movement |
   | TLS certificates | 90 days | MITM attacks |
   | Database passwords | 30 days | Data breach |

2. **Architecture:**
   ```
   ┌─────────────────────────────────────────┐
   │  Secrets Manager (HashiCorp Vault/AWS SM) │
   ├─────────────────────────────────────────┤
   │  Dynamic Secrets Engine                   │
   │  - Just-in-time credential generation     │
   │  - Auto-rotation with zero downtime       │
   │  - Lease-based access (auto-expire)       │
   ├─────────────────────────────────────────┤
   │  Access Control                           │
   │  - Policy-based (role → secrets mapping)  │
   │  - Audit logging (who accessed what)      │
   │  - Break-glass procedures                 │
   └─────────────────────────────────────────┘
   ```

3. **Zero-Downtime Rotation:**
   ```python
   class SecretRotator:
       async def rotate_llm_api_key(self, provider: str):
           """Rotate API key without service interruption."""
           
           # Step 1: Generate new key
           new_key = await self.provider_api.create_key(provider)
           
           # Step 2: Store new key (both old and new are valid)
           await self.vault.store(
               path=f"ai/{provider}/api_key",
               value=new_key,
               metadata={'version': 'new', 'created': now()}
           )
           
           # Step 3: Gradually shift traffic to new key
           await self.feature_flag.set(f"{provider}_new_key_percentage", 10)
           await asyncio.sleep(300)  # 5 min validation
           
           # Step 4: Verify new key works
           if await self.health_check(provider, new_key):
               await self.feature_flag.set(f"{provider}_new_key_percentage", 100)
           else:
               await self.rollback(provider)
               return RotationResult(success=False)
           
           # Step 5: Revoke old key (after grace period)
           await asyncio.sleep(3600)  # 1 hour grace
           await self.provider_api.revoke_key(provider, old_key)
           
           return RotationResult(success=True)
   ```

4. **Breach Response Automation:**
   ```python
   class BreachResponder:
       async def handle_key_compromise(self, compromised_key: str):
           """Automated response to key compromise detection."""
           
           # Step 1: Immediate revocation (within seconds)
           await self.revoke_key(compromised_key)
           
           # Step 2: Emergency rotation of all related secrets
           related = await self.find_related_secrets(compromised_key)
           await asyncio.gather(*[
               self.emergency_rotate(secret) for secret in related
           ])
           
           # Step 3: Assess blast radius
           blast_radius = await self.assess_impact(
               key=compromised_key,
               access_logs=self.get_access_logs(compromised_key, hours=72)
           )
           
           # Step 4: Notify stakeholders
           await self.notify(
               security_team=True,
               affected_customers=blast_radius.affected_customers,
               executives=blast_radius.severity == 'critical'
           )
           
           # Step 5: Forensics
           await self.start_forensics_investigation(compromised_key)
   ```

5. **Best Practices:**
   - Never store secrets in code, config files, or environment variables directly
   - Use short-lived dynamic credentials (Vault dynamic secrets)
   - Implement secret scanning in CI/CD (prevent accidental commits)
   - Encrypt secrets at rest with HSM-backed keys
   - Separate secret access by environment (dev secrets ≠ prod secrets)
   - Implement secret access anomaly detection (unusual access patterns → alert)
