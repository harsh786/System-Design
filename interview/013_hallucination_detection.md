# Hallucination Detection & Mitigation - Staff Architect Interview

## Question 61: Hallucination Taxonomy and Detection
**Difficulty: Staff Level | Topic: LLM Reliability | Asked at: OpenAI, Anthropic, Google**

Classify the different types of hallucinations in LLM systems. Design a multi-layer detection system that identifies hallucinations in real-time with <100ms overhead.

### Expected Answer:

**Hallucination Taxonomy:**

1. **Types of Hallucinations:**
   | Type | Description | Example | Detection Difficulty |
   |------|-------------|---------|---------------------|
   | Intrinsic | Contradicts source material | "The paper says X" when paper says Y | Medium (NLI) |
   | Extrinsic | Not supported by any source | Fabricating citations/facts | Hard |
   | Factual | Incorrect real-world facts | "Paris is the capital of Germany" | Medium (KB lookup) |
   | Faithfulness | Doesn't match retrieved context | RAG returns A, LLM says B | Medium (NLI) |
   | Logical | Invalid reasoning/inference | "A implies B, B implies C, therefore A implies D" | Hard |
   | Temporal | Wrong time attribution | "GPT-4 was released in 2020" | Medium (date check) |
   | Entity | Wrong entity substitution | Confusing similar named entities | Medium (NER) |

2. **Multi-Layer Detection Architecture:**
   ```
   LLM Response
        │
        ▼
   ┌─────────────────────────────────────────────┐
   │ Layer 1: Statistical Detection (5ms)         │
   │ - Token probability analysis                  │
   │ - Entropy spikes in generation               │
   │ - Repetition/degeneration detection           │
   └─────────────────────┬───────────────────────┘
                         │
   ┌─────────────────────▼───────────────────────┐
   │ Layer 2: NLI-Based Faithfulness (30ms)       │
   │ - Check each claim against retrieved context  │
   │ - Entailment/Contradiction/Neutral scoring    │
   └─────────────────────┬───────────────────────┘
                         │
   ┌─────────────────────▼───────────────────────┐
   │ Layer 3: Claim Decomposition (50ms)          │
   │ - Break response into atomic claims           │
   │ - Verify each claim independently            │
   │ - Confidence scoring per claim               │
   └─────────────────────┬───────────────────────┘
                         │
   ┌─────────────────────▼───────────────────────┐
   │ Layer 4: Knowledge Base Verification (async)  │
   │ - Check against structured KB                 │
   │ - Entity validation                          │
   │ - Temporal fact checking                      │
   └─────────────────────────────────────────────┘
   ```

3. **Implementation:**
   ```python
   class HallucinationDetector:
       def __init__(self):
           self.nli_model = load_model('deberta-v3-large-mnli')  # Fast NLI
           self.claim_extractor = ClaimExtractor()
           self.kb_checker = KnowledgeBaseChecker()
       
       async def detect(self, response: str, context: List[str], 
                       latency_budget_ms: int = 100) -> HallucinationReport:
           
           # Layer 1: Fast statistical checks (always run)
           stats = self.statistical_check(response)
           if stats.is_degenerate:
               return HallucinationReport(hallucinated=True, type='degenerate')
           
           # Layer 2: NLI faithfulness (always run, <30ms)
           nli_scores = self.nli_check(response, context)
           
           # Layer 3: Claim verification (if budget allows)
           claims = []
           if latency_budget_ms > 50:
               claims = self.claim_extractor.extract(response)
               claim_scores = await self.verify_claims(claims, context)
           
           # Aggregate results
           return HallucinationReport(
               overall_faithfulness=nli_scores.mean(),
               hallucinated_claims=[c for c in claims if c.score < 0.5],
               confidence=self.aggregate_confidence(stats, nli_scores, claim_scores)
           )
       
       def nli_check(self, response: str, context: List[str]) -> np.ndarray:
           """Check if response is entailed by context."""
           combined_context = " ".join(context[:3])  # Top 3 for speed
           
           # Sentence-level NLI
           response_sentences = self.split_sentences(response)
           scores = []
           for sentence in response_sentences:
               result = self.nli_model.predict(
                   premise=combined_context,
                   hypothesis=sentence
               )
               # result: {entailment: 0.8, contradiction: 0.1, neutral: 0.1}
               scores.append(result['entailment'])
           
           return np.array(scores)
   ```

4. **Confidence Calibration:**
   - Train threshold on labeled dataset (1000+ examples)
   - Different thresholds for different use cases:
     - Medical: Conservative (flag if confidence < 0.9)
     - Casual chat: Lenient (flag if confidence < 0.5)
   - Bayesian calibration: Convert raw scores to calibrated probabilities

5. **Handling Detected Hallucinations:**
   | Severity | Action | User Experience |
   |----------|--------|-----------------|
   | Low (single uncertain claim) | Add qualifier | "Based on available information..." |
   | Medium (unsupported but plausible) | Add disclaimer | "Note: I couldn't verify..." |
   | High (contradicts sources) | Remove claim | Regenerate without hallucinated part |
   | Critical (dangerous misinformation) | Block response | "I cannot provide a reliable answer" |

---

## Question 62: Grounded Generation Architecture
**Difficulty: Staff Level | Topic: Faithfulness | Asked at: Google, Microsoft, Anthropic**

Design a generation system that guarantees factual grounding - every claim in the output must be traceable to a source document. How do you architect "attribution-by-design" rather than post-hoc fact-checking?

### Expected Answer:

**Attribution-by-Design Architecture:**

1. **Core Principle:** Never generate ungrounded text. Every sentence must cite a source.

2. **Constrained Generation Pipeline:**
   ```python
   class GroundedGenerator:
       def generate(self, query: str, sources: List[Document]) -> AttributedResponse:
           # Step 1: Extract citable facts from sources
           fact_database = self.extract_facts(sources)
           # [{fact: "Revenue grew 15%", source: doc_3, para: 2}, ...]
           
           # Step 2: Plan response structure
           outline = self.plan_response(query, fact_database)
           # [{point: "Revenue growth", supporting_facts: [fact_1, fact_3]}, ...]
           
           # Step 3: Generate with inline citations
           response = self.generate_with_citations(outline, fact_database)
           
           # Step 4: Verify all citations are valid
           verified = self.verify_citations(response, sources)
           
           return verified
       
       def generate_with_citations(self, outline, facts):
           """
           Prompt engineering for grounded generation:
           
           Instructions: Generate a response using ONLY the provided facts.
           Every sentence must end with a citation [Source X].
           If you cannot answer from the provided facts, say "Not found in sources."
           
           Available Facts:
           [1] Revenue grew 15% YoY (Source: Q3 Report, p.4)
           [2] Customer count reached 10M (Source: Press Release, Jan 2024)
           ...
           
           DO NOT state anything not directly supported by the facts above.
           """
           prompt = self.build_grounded_prompt(outline, facts)
           return self.llm.generate(prompt)
   ```

3. **Fact Extraction & Indexing:**
   ```python
   class FactExtractor:
       def extract_facts(self, documents: List[Document]) -> FactDatabase:
           facts = []
           for doc in documents:
               for paragraph in doc.paragraphs:
                   # Extract atomic claims
                   claims = self.decompose_to_claims(paragraph)
                   for claim in claims:
                       facts.append(Fact(
                           text=claim.text,
                           source_doc=doc.id,
                           source_paragraph=paragraph.id,
                           source_page=paragraph.page,
                           entities=claim.entities,
                           confidence=claim.confidence,
                           temporal_scope=claim.time_reference
                       ))
           
           return FactDatabase(facts)
   ```

4. **Citation Verification:**
   ```python
   class CitationVerifier:
       def verify(self, response: AttributedResponse, sources: List[Document]):
           for sentence in response.sentences:
               if not sentence.has_citation:
                   # Ungrounded sentence! 
                   if self.is_transitional(sentence):
                       pass  # "In summary..." doesn't need citation
                   else:
                       sentence.mark_ungrounded()
               else:
                   # Verify citation accuracy
                   cited_source = sources[sentence.citation_id]
                   entailment = self.nli_check(
                       premise=cited_source.text,
                       hypothesis=sentence.text
                   )
                   if entailment < 0.7:
                       sentence.mark_misattributed()
           
           return response
   ```

5. **Production Trade-offs:**
   - Grounded generation is more conservative (may miss useful inferences)
   - Latency: +100-200ms for fact extraction and verification
   - Quality: Higher precision, lower recall (won't state useful obvious facts without source)
   - User experience: Citations add visual noise but build trust
   - Hybrid: Allow parametric knowledge for "common knowledge" with lower citation requirements

---

## Question 63: Hallucination in Multi-Step Reasoning
**Difficulty: Staff Level | Topic: Chain-of-Thought Reliability | Asked at: Google DeepMind, OpenAI**

LLMs hallucinate more in multi-step reasoning chains. Design a system that detects and prevents hallucination at each reasoning step, ensuring the final answer is reliable even for complex 5+ step reasoning tasks.

### Expected Answer:

**Verified Chain-of-Thought Architecture:**

1. **Problem Statement:**
   - Each reasoning step has P(correct) ≈ 0.9
   - For 5 steps: P(all correct) = 0.9^5 = 0.59 (41% error rate!)
   - Need: Verify each step independently

2. **Step-Level Verification:**
   ```python
   class VerifiedReasoningChain:
       def reason(self, query: str, context: str) -> VerifiedAnswer:
           steps = []
           current_context = context
           
           for i in range(self.max_steps):
               # Generate next reasoning step
               step = self.generate_step(query, current_context, steps)
               
               if step.is_conclusion:
                   break
               
               # Verify this step
               verification = self.verify_step(step, current_context, steps)
               
               if verification.valid:
                   steps.append(step)
                   current_context += f"\nVerified: {step.text}"
               else:
                   # Step is invalid - try alternative reasoning
                   alternative = self.generate_alternative_step(
                       query, current_context, steps, 
                       invalid_step=step,
                       reason=verification.failure_reason
                   )
                   if self.verify_step(alternative, current_context, steps).valid:
                       steps.append(alternative)
                   else:
                       # Cannot find valid next step
                       return VerifiedAnswer(
                           answer=None,
                           confidence=0.0,
                           failure_point=i,
                           reason="Could not verify reasoning step"
                       )
           
           return VerifiedAnswer(
               answer=steps[-1].conclusion,
               confidence=self.chain_confidence(steps),
               reasoning_chain=steps
           )
   ```

3. **Step Verification Methods:**
   ```python
   class StepVerifier:
       def verify_step(self, step, context, previous_steps):
           checks = []
           
           # Check 1: Logical consistency with previous steps
           checks.append(self.logical_consistency(step, previous_steps))
           
           # Check 2: Factual grounding in context
           checks.append(self.factual_grounding(step, context))
           
           # Check 3: Mathematical/logical validity
           if step.has_calculation:
               checks.append(self.verify_calculation(step))
           
           # Check 4: Self-consistency (generate same step 3 times)
           alternatives = [self.generate_step_fresh() for _ in range(3)]
           consistency = self.measure_agreement(step, alternatives)
           checks.append(consistency > 0.7)
           
           return VerificationResult(
               valid=all(checks),
               confidence=min(c.score for c in checks),
               failure_reason=next((c.reason for c in checks if not c.passed), None)
           )
   ```

4. **Beam Search over Reasoning Paths:**
   ```
   Query: "What's the ROI of implementing RAG vs fine-tuning?"
   
   Path A (beam 1):              Path B (beam 2):
   Step 1: Calculate RAG cost    Step 1: Define ROI metrics
   Step 2: Calculate FT cost     Step 2: Calculate RAG cost
   Step 3: Compare quality       Step 3: Calculate FT cost  
   Step 4: Calculate ROI         Step 4: Compare quality + cost
   ✓ Verified                    ✓ Verified
   
   → Select highest-confidence path
   ```

5. **Production Implementation:**
   - Use smaller/cheaper model for verification (GPT-3.5 verifies GPT-4 steps)
   - Parallel verification: While generating step N+1, verify step N
   - Cache verified reasoning patterns (common reasoning chains)
   - Latency: 2-3x single generation (acceptable for complex queries)
   - Fallback: If no path verifies, return "Unable to determine" with partial analysis

---

## Question 64: Reducing Hallucination Through Retrieval Optimization
**Difficulty: Staff Level | Topic: RAG Quality | Asked at: Anthropic, Cohere, Microsoft**

Studies show that irrelevant retrieved context INCREASES hallucination rates. Design a retrieval quality optimization system that minimizes hallucination by ensuring only high-quality, relevant context reaches the LLM.

### Expected Answer:

**Retrieval Quality Optimization for Hallucination Reduction:**

1. **The Counter-Intuitive Problem:**
   - More context ≠ less hallucination
   - Irrelevant context confuses the LLM → MORE hallucination
   - Contradictory context → LLM makes up a "middle ground" (hallucination)
   - Partial information → LLM fills gaps with fabrication

2. **Quality-First Retrieval Pipeline:**
   ```python
   class QualityOptimizedRetriever:
       def retrieve(self, query: str) -> List[Document]:
           # Step 1: Over-retrieve
           candidates = self.vector_search(query, top_k=50)
           
           # Step 2: Relevance filtering (strict threshold)
           relevant = [doc for doc in candidates 
                      if doc.similarity_score > self.relevance_threshold]
           # threshold = 0.75 (learned from hallucination correlation data)
           
           # Step 3: Contradiction detection
           non_contradictory = self.remove_contradictions(relevant)
           
           # Step 4: Completeness assessment
           if self.information_sufficient(query, non_contradictory):
               return non_contradictory[:5]
           else:
               # Better to return nothing than partial info
               return self.annotated_return(
                   non_contradictory, 
                   gaps=self.identify_gaps(query, non_contradictory)
               )
       
       def remove_contradictions(self, documents):
           """Remove documents that contradict the majority."""
           claims_per_doc = [self.extract_claims(doc) for doc in documents]
           
           for i, doc_claims in enumerate(claims_per_doc):
               for claim in doc_claims:
                   contradictions = sum(
                       1 for j, other_claims in enumerate(claims_per_doc)
                       if i != j and self.contradicts(claim, other_claims)
                   )
                   if contradictions > len(documents) * 0.3:
                       documents[i].flag_contradictory(claim)
           
           return [doc for doc in documents if not doc.has_contradictions]
   ```

3. **Context Quality Scoring:**
   | Quality Signal | Weight | Measurement |
   |---------------|--------|-------------|
   | Relevance to query | 0.30 | Cross-encoder score |
   | Information density | 0.20 | Unique facts per token |
   | Source authority | 0.15 | Document trust score |
   | Freshness | 0.15 | Document age penalty |
   | Completeness | 0.10 | Covers all query aspects |
   | Consistency | 0.10 | No contradictions with other docs |

4. **Hallucination-Aware Prompt Design:**
   ```python
   ANTI_HALLUCINATION_PROMPT = """
   Answer the question using ONLY the provided context.
   
   Rules:
   1. If the context doesn't contain the answer, say "The provided documents don't contain this information."
   2. If the context partially answers the question, answer only what's supported and explicitly state what's missing.
   3. Never extrapolate beyond what's explicitly stated.
   4. If documents contradict each other, present both views with sources.
   5. Prefix uncertain statements with "Based on limited information..."
   
   Context quality note: {context_quality_assessment}
   - Coverage: {coverage_percentage}% of query aspects covered
   - Gaps: {identified_gaps}
   
   Context:
   {filtered_context}
   
   Question: {query}
   """
   ```

5. **Feedback Loop for Threshold Optimization:**
   - Log (query, context, response, hallucination_detected) tuples
   - Correlate relevance thresholds with hallucination rates
   - Automatically adjust thresholds to minimize hallucination while maintaining answer rate
   - Target: <2% hallucination rate with >85% answer rate

---

## Question 65: Hallucination Benchmarking and Red-Teaming
**Difficulty: Staff Level | Topic: Evaluation | Asked at: Anthropic, OpenAI, Google DeepMind**

Design a comprehensive hallucination benchmarking framework and red-teaming strategy for a production RAG system serving healthcare information. Include synthetic adversarial test generation.

### Expected Answer:

**Healthcare RAG Hallucination Benchmarking:**

1. **Benchmark Categories:**
   | Category | Description | Example | Risk Level |
   |----------|-------------|---------|------------|
   | Drug interactions | Incorrect drug combo safety | "X and Y are safe together" (they're not) | Critical |
   | Dosage hallucination | Wrong dosage information | "Take 500mg" (correct is 50mg) | Critical |
   | Symptom attribution | Wrong disease for symptoms | "Chest pain = anxiety" (could be cardiac) | High |
   | Outdated guidelines | Citing superseded protocols | Using 2015 guidelines when 2023 exist | Medium |
   | Entity confusion | Mixing up similar drugs | Confusing Metformin with Methotrexate | Critical |
   | Statistical fabrication | Inventing study results | "Studies show 95% efficacy" (no such study) | High |

2. **Adversarial Test Generation:**
   ```python
   class HealthcareRedTeamGenerator:
       def generate_adversarial_tests(self) -> List[TestCase]:
           tests = []
           
           # Type 1: Confusion pairs (similar names, different drugs)
           confusion_pairs = [
               ("metformin", "methotrexate"),
               ("hydroxyzine", "hydroxychloroquine"),
               ("prednisone", "prednisolone")
           ]
           for drug_a, drug_b in confusion_pairs:
               tests.append(TestCase(
                   query=f"What are the side effects of {drug_a}?",
                   expected_answer_about=drug_a,
                   hallucination_if_mentions=drug_b,
                   category='entity_confusion'
               ))
           
           # Type 2: Boundary conditions (max doses, contraindications)
           for drug in self.drug_database:
               tests.append(TestCase(
                   query=f"What is the maximum daily dose of {drug.name}?",
                   ground_truth=drug.max_dose,
                   tolerance=0,  # Must be exact
                   category='dosage'
               ))
           
           # Type 3: Temporal traps (outdated info)
           for guideline in self.guidelines_with_updates:
               tests.append(TestCase(
                   query=f"What is the current recommendation for {guideline.topic}?",
                   current_answer=guideline.current_version,
                   outdated_answer=guideline.previous_version,
                   hallucination_if_matches='outdated',
                   category='temporal'
               ))
           
           # Type 4: Non-existent entities (should refuse)
           tests.append(TestCase(
               query="What are the indications for Fakemedicil 500mg?",
               expected="refuse_or_state_unknown",
               hallucination_if="provides_any_medical_info",
               category='fabrication'
           ))
           
           return tests
   ```

3. **Automated Red-Team Pipeline:**
   ```
   Monthly Red-Team Cycle:
   1. Generate 500 adversarial queries (LLM-generated + template-based)
   2. Run against production system (shadow mode)
   3. Automated grading (NLI + rule-based + expert review)
   4. Report: Hallucination rate by category
   5. Root cause analysis for new failure modes
   6. Update guardrails and retrieval thresholds
   7. Regression test: Verify previous failures are fixed
   ```

4. **Scoring Framework:**
   ```python
   class HallucinationScorer:
       def score_response(self, response, test_case):
           score = {
               'factual_accuracy': self.check_facts(response, test_case.ground_truth),
               'citation_accuracy': self.verify_citations(response),
               'refusal_appropriateness': self.check_refusal(response, test_case),
               'entity_correctness': self.verify_entities(response, test_case),
               'temporal_accuracy': self.check_dates(response, test_case),
               'severity': self.assess_harm_potential(response, test_case)
           }
           
           # Healthcare-specific: any critical hallucination = immediate fail
           if score['severity'] == 'critical' and score['factual_accuracy'] < 1.0:
               score['overall'] = 0.0  # Zero tolerance for critical errors
           
           return score
   ```

5. **Continuous Monitoring in Production:**
   - Real-time hallucination detection on 100% of medical responses
   - Weekly human expert audit of 100 random responses
   - Monthly adversarial red-team exercises
   - Immediate alert on critical category hallucinations
   - Quarterly benchmark refresh (new drugs, updated guidelines)
   - Incident response: Any confirmed critical hallucination → system pause + investigation
