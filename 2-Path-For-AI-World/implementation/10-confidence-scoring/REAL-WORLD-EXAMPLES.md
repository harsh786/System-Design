# Confidence Scoring: Real-World Examples

## Case Study 1: Calibrated Confidence in Medical AI

### Context
A clinical decision support system (CDSS) assists radiologists in detecting pulmonary nodules on chest CT scans. Regulatory requirement: when the system says "85% confident," it must be correct 85% of the time (±3%).

### The Calibration Journey

**Phase 1: Raw Model Output (Uncalibrated)**

The base model (fine-tuned DenseNet-121) outputs logits that are systematically overconfident:

```python
# Calibration analysis of raw model outputs on 5,000 test CTs
raw_calibration = {
    "confidence_bucket": [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99],
    "actual_accuracy":   [0.52, 0.58, 0.63, 0.71, 0.78, 0.82, 0.88],
    # Gap:                -0.02  -0.02  -0.07  -0.09  -0.12  -0.13  -0.11
}
# Expected Calibration Error (ECE): 0.083
# Maximum Calibration Error (MCE): 0.13 (at 95% confidence bucket)
# The model is OVERCONFIDENT — says 90% but only right 78% of the time
```

**Phase 2: Platt Scaling Applied**

```python
from sklearn.linear_model import LogisticRegression
import numpy as np

class PlattScaling:
    """Temperature scaling variant for binary classification."""
    
    def __init__(self):
        self.calibrator = LogisticRegression()
    
    def fit(self, logits, true_labels, validation_set_size=1000):
        """Fit on held-out validation set (NEVER on test set)."""
        # logits shape: (n_samples,) — raw model output before sigmoid
        self.calibrator.fit(logits.reshape(-1, 1), true_labels)
        
    def calibrate(self, logit):
        """Transform raw logit into calibrated probability."""
        return self.calibrator.predict_proba(logit.reshape(-1, 1))[:, 1]

# For multi-class: Temperature Scaling
class TemperatureScaling:
    def __init__(self):
        self.temperature = 1.0  # Learned parameter
    
    def fit(self, logits, true_labels):
        """Optimize temperature on validation set using NLL loss."""
        from scipy.optimize import minimize_scalar
        
        def nll_loss(T):
            scaled = logits / T
            probs = softmax(scaled, axis=1)
            return -np.mean(np.log(probs[range(len(true_labels)), true_labels]))
        
        result = minimize_scalar(nll_loss, bounds=(0.1, 10.0), method='bounded')
        self.temperature = result.x  # Typical: T=1.5-2.5 for overconfident models
    
    def calibrate(self, logits):
        return softmax(logits / self.temperature, axis=1)
```

**Phase 3: Post-Calibration Results**

```python
# After Platt scaling on validation set of 1,000 CTs
calibrated_results = {
    "confidence_bucket": [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99],
    "actual_accuracy":   [0.49, 0.61, 0.69, 0.81, 0.88, 0.94, 0.97],
    # Gap:                +0.01  -0.01  +0.01  -0.01  +0.02  +0.01  +0.02
}
# ECE: 0.012 (down from 0.083 — 85% reduction)
# MCE: 0.02  (down from 0.13)
# Now within ±3% regulatory requirement at all confidence levels
```

**Phase 4: Continuous Monitoring**

```python
class CalibrationMonitor:
    """Run weekly on production predictions with confirmed outcomes."""
    
    def __init__(self, tolerance=0.03):
        self.tolerance = tolerance
    
    def weekly_check(self, predictions, outcomes):
        """Alert if calibration drifts beyond tolerance."""
        for bucket_start in np.arange(0.5, 1.0, 0.1):
            bucket_end = bucket_start + 0.1
            mask = (predictions >= bucket_start) & (predictions < bucket_end)
            
            if mask.sum() < 30:  # Need minimum samples
                continue
                
            expected = predictions[mask].mean()
            actual = outcomes[mask].mean()
            gap = abs(expected - actual)
            
            if gap > self.tolerance:
                alert(f"Calibration drift detected: bucket [{bucket_start:.1f}, {bucket_end:.1f}), "
                      f"expected={expected:.3f}, actual={actual:.3f}, gap={gap:.3f}")
                return "RECALIBRATE"
        
        return "OK"
```

---

## Case Study 2: Confidence-Driven Decision Making in Legal AI

### System Architecture

A legal research tool uses confidence to make three-way decisions:

```python
class LegalResearchConfidenceRouter:
    """
    Routes responses based on confidence level:
    - HIGH (>0.85): Direct answer with citations
    - MEDIUM (0.60-0.85): Answer with caveats and disclaimers
    - LOW (<0.60): Refuse to answer, suggest human attorney review
    """
    
    def __init__(self):
        self.thresholds = {
            "direct_answer": 0.85,
            "caveated_answer": 0.60,
            # Below 0.60 → refuse
        }
        # Different thresholds for different stakes
        self.domain_overrides = {
            "criminal_law": {"direct_answer": 0.92, "caveated_answer": 0.75},
            "contract_review": {"direct_answer": 0.80, "caveated_answer": 0.55},
            "general_info": {"direct_answer": 0.75, "caveated_answer": 0.50},
        }
    
    def route(self, query, response, confidence_score, domain):
        thresholds = self.domain_overrides.get(domain, self.thresholds)
        
        if confidence_score >= thresholds["direct_answer"]:
            return DirectAnswer(
                response=response,
                citations=self.extract_citations(response),
                confidence_display=f"High confidence ({confidence_score:.0%})"
            )
        elif confidence_score >= thresholds["caveated_answer"]:
            return CaveatedAnswer(
                response=response,
                caveat=self._generate_caveat(confidence_score, domain),
                citations=self.extract_citations(response),
                confidence_display=f"Moderate confidence ({confidence_score:.0%})",
                suggestion="Consider verifying with a licensed attorney for your specific situation."
            )
        else:
            return Refusal(
                message="I don't have sufficient confidence to provide legal guidance on this question.",
                reason=self._explain_low_confidence(query, confidence_score),
                suggestion="Please consult a licensed attorney specializing in this area.",
                confidence_display=f"Low confidence ({confidence_score:.0%})"
            )
    
    def _generate_caveat(self, confidence, domain):
        if confidence < 0.70:
            return ("This information is provided for general educational purposes only. "
                    "The legal landscape in this area is complex and jurisdiction-dependent. "
                    "Do not rely on this as legal advice.")
        else:
            return ("While this appears to be a straightforward legal question, "
                    "please verify the current applicability to your jurisdiction.")
```

### Production Distribution

```
Query volume: 50,000 queries/month
Routing breakdown:
  Direct answer (high confidence):     34% (17,000 queries)
  Caveated answer (medium confidence): 41% (20,500 queries)
  Refusal (low confidence):            25% (12,500 queries)

User satisfaction by route:
  Direct answers:   4.3/5 stars, 2% escalation to human
  Caveated answers: 3.8/5 stars, 12% escalation to human
  Refusals:         3.1/5 stars, 68% escalation to human (expected)

Correctness by route (verified by attorneys on 500 random samples):
  Direct answers:   96.2% fully correct, 3.1% minor issues, 0.7% wrong
  Caveated answers: 84.5% correct, 11.2% partially correct, 4.3% wrong
  Refusals:         N/A (correctly declined)

Key insight: The 0.7% error rate in "high confidence" answers is acceptable for 
the use case (educational, not advice). If this were for filing legal documents,
the direct_answer threshold would be raised to 0.95+.
```

---

## Case Study 3: Calibration in Practice — Reliability Diagrams

### Before/After Visualization (Textual Representation)

```
RELIABILITY DIAGRAM — BEFORE CALIBRATION (Temperature = 1.0)

Confidence →  0.5   0.6   0.7   0.8   0.9   1.0
              |     |     |     |     |     |
Accuracy:     ████████████████████
              0.50  0.55  0.60  0.67  0.74  0.82

Perfect calibration line: y = x (diagonal)
Model line: significantly below diagonal at high confidence
ECE = 0.091

Gap analysis:
  Confidence 0.5-0.6: actual accuracy 0.53 (gap: -0.02) ✓ OK
  Confidence 0.6-0.7: actual accuracy 0.59 (gap: -0.06) ⚠️ 
  Confidence 0.7-0.8: actual accuracy 0.67 (gap: -0.08) ⚠️
  Confidence 0.8-0.9: actual accuracy 0.74 (gap: -0.11) ❌
  Confidence 0.9-1.0: actual accuracy 0.82 (gap: -0.13) ❌

RELIABILITY DIAGRAM — AFTER TEMPERATURE SCALING (T = 1.85)

Confidence →  0.5   0.6   0.7   0.8   0.9   1.0
              |     |     |     |     |     |
Accuracy:     ████████████████████████████████
              0.50  0.59  0.71  0.79  0.91  0.97

Model line: closely tracks the diagonal
ECE = 0.014

Gap analysis:
  Confidence 0.5-0.6: actual accuracy 0.51 (gap: -0.01) ✓
  Confidence 0.6-0.7: actual accuracy 0.66 (gap: +0.01) ✓
  Confidence 0.7-0.8: actual accuracy 0.74 (gap: -0.01) ✓
  Confidence 0.8-0.9: actual accuracy 0.86 (gap: +0.01) ✓
  Confidence 0.9-1.0: actual accuracy 0.93 (gap: +0.02) ✓
```

**Implementation detail:** Temperature was found by grid search on 2,000 validation samples, optimizing negative log-likelihood. The optimal T=1.85 means the raw model was very overconfident — its logits needed to be "spread out" by nearly 2x.

---

## Case Study 4: Confidence-Driven Routing in Customer Support

### System: AI Customer Support with Human Escalation

```python
class CustomerSupportRouter:
    """
    Three-tier routing based on composite confidence:
    Tier 1: AI auto-responds (confidence >= 0.90)
    Tier 2: AI drafts, human reviews before sending (0.70-0.90)
    Tier 3: Route directly to human agent (confidence < 0.70)
    """
    
    def __init__(self):
        self.confidence_model = CompositeConfidenceScorer()
        self.thresholds = {"auto": 0.90, "review": 0.70}
    
    def process_ticket(self, ticket):
        # Generate AI response
        response = self.llm.generate(ticket.message, context=ticket.history)
        
        # Compute confidence
        confidence = self.confidence_model.score(
            query=ticket.message,
            response=response,
            context=ticket.history,
            customer_tier=ticket.customer.tier,  # Enterprise = stricter
        )
        
        # Apply customer tier multiplier
        if ticket.customer.tier == "enterprise":
            # Enterprise customers: raise thresholds by 5%
            effective_auto = self.thresholds["auto"] + 0.05
            effective_review = self.thresholds["review"] + 0.05
        else:
            effective_auto = self.thresholds["auto"]
            effective_review = self.thresholds["review"]
        
        # Route
        if confidence.overall >= effective_auto:
            return self.auto_respond(ticket, response, confidence)
        elif confidence.overall >= effective_review:
            return self.queue_for_review(ticket, response, confidence)
        else:
            return self.escalate_to_human(ticket, confidence)
    
    def auto_respond(self, ticket, response, confidence):
        """Send immediately, log for async QA sampling."""
        send_response(ticket, response)
        # 5% random sample goes to QA anyway
        if random.random() < 0.05:
            qa_queue.add(ticket, response, confidence, "auto_sampled")
        return {"action": "auto_responded", "confidence": confidence.overall}
```

### Production Metrics (6 months of data)

```
Monthly ticket volume: 85,000

Routing distribution:
  Tier 1 (auto-respond):     52% (44,200 tickets)
  Tier 2 (human review):     31% (26,350 tickets)
  Tier 3 (full escalation):  17% (14,450 tickets)

Quality metrics by tier:
  Tier 1 auto-responses:
    Customer satisfaction (CSAT): 4.1/5
    Resolution rate (no follow-up): 87%
    Error rate (wrong/harmful answer): 1.2%
    Average response time: 8 seconds
    
  Tier 2 human-reviewed:
    CSAT: 4.4/5
    Resolution rate: 91%
    Human edit rate: 34% (human modifies AI draft)
    Average response time: 12 minutes
    
  Tier 3 human-handled:
    CSAT: 4.2/5
    Resolution rate: 82% (often complex issues)
    Average response time: 2.4 hours

Cost comparison:
  Tier 1: $0.03/ticket (API costs only)
  Tier 2: $4.20/ticket (human time for review: ~3 min average)
  Tier 3: $18.50/ticket (full human handling: ~15 min average)
  
  Blended cost: $4.82/ticket
  Without AI (all human): $18.50/ticket
  Savings: 74% cost reduction
```

---

## Case Study 5: Composite Confidence Scoring — Signal Weights

### Production System: Enterprise RAG for Internal Knowledge Base

```python
class CompositeConfidenceScorer:
    """
    Combines multiple signals into a single calibrated confidence score.
    Weights learned from 10,000 labeled examples using logistic regression.
    """
    
    def __init__(self):
        # Weights learned from production data (logistic regression on labeled outcomes)
        self.signal_weights = {
            "retrieval_relevance": 0.30,    # How relevant are retrieved docs?
            "groundedness": 0.25,           # Is answer supported by retrieved text?
            "source_authority": 0.20,       # Are sources authoritative/official?
            "freshness": 0.15,              # How recent is the source data?
            "internal_consistency": 0.10,   # Does the answer contradict itself?
        }
        self.calibrator = TemperatureScaling()  # Post-hoc calibration
    
    def score(self, query, response, retrieved_docs):
        signals = {}
        
        # Signal 1: Retrieval relevance (cross-encoder reranker score)
        signals["retrieval_relevance"] = self._retrieval_relevance(query, retrieved_docs)
        
        # Signal 2: Groundedness (NLI-based — does response follow from context?)
        signals["groundedness"] = self._groundedness(response, retrieved_docs)
        
        # Signal 3: Source authority (metadata-based)
        signals["source_authority"] = self._source_authority(retrieved_docs)
        
        # Signal 4: Freshness (time decay)
        signals["freshness"] = self._freshness(retrieved_docs)
        
        # Signal 5: Internal consistency (self-check)
        signals["internal_consistency"] = self._consistency(query, response)
        
        # Weighted combination
        raw_score = sum(
            self.signal_weights[k] * signals[k] for k in self.signal_weights
        )
        
        # Calibrate to true probability
        calibrated = self.calibrator.calibrate(raw_score)
        
        return ConfidenceResult(
            overall=calibrated,
            signals=signals,
            explanation=self._explain(signals)
        )
    
    def _retrieval_relevance(self, query, docs):
        """Cross-encoder score averaged over top-k docs."""
        scores = [self.reranker.score(query, doc.text) for doc in docs[:5]]
        # Weighted: top doc matters most
        weights = [0.35, 0.25, 0.20, 0.12, 0.08]
        return sum(s * w for s, w in zip(sorted(scores, reverse=True), weights))
    
    def _groundedness(self, response, docs):
        """NLI model: what fraction of response claims are entailed by docs?"""
        claims = self.claim_extractor.extract(response)
        if not claims:
            return 0.5  # No verifiable claims
        
        entailed = 0
        for claim in claims:
            context = " ".join(doc.text for doc in docs)
            nli_result = self.nli_model.predict(premise=context, hypothesis=claim)
            if nli_result == "entailment":
                entailed += 1
            elif nli_result == "contradiction":
                entailed -= 0.5  # Penalize contradictions heavily
        
        return max(0, entailed / len(claims))
    
    def _source_authority(self, docs):
        """Score based on document metadata."""
        authority_scores = {
            "official_documentation": 1.0,
            "internal_wiki_verified": 0.9,
            "internal_wiki_unverified": 0.7,
            "slack_conversation": 0.4,
            "external_blog": 0.3,
        }
        scores = [authority_scores.get(doc.source_type, 0.5) for doc in docs]
        return np.mean(scores) if scores else 0.3
    
    def _freshness(self, docs):
        """Time-based decay — different rates for different content types."""
        now = datetime.utcnow()
        freshness_scores = []
        for doc in docs:
            age_days = (now - doc.last_updated).days
            # Decay rate depends on content type
            if doc.content_type == "policy":
                half_life = 180  # Policies change every ~6 months
            elif doc.content_type == "technical_spec":
                half_life = 365  # Specs change yearly
            elif doc.content_type == "meeting_notes":
                half_life = 30   # Meeting context decays fast
            else:
                half_life = 90
            
            freshness = 0.5 ** (age_days / half_life)
            freshness_scores.append(freshness)
        
        return np.mean(freshness_scores) if freshness_scores else 0.3
    
    def _consistency(self, query, response):
        """Generate answer twice with temperature, check agreement."""
        response_2 = self.llm.generate(query, temperature=0.7)
        # Semantic similarity between two generations
        similarity = self.embedder.cosine_similarity(response, response_2)
        return similarity  # High similarity = consistent = confident
```

### Weight Discovery Process

```
How weights were determined:

1. Collected 10,000 (query, response, human_judgment) triples
   - human_judgment: "correct", "partially_correct", "incorrect"
   
2. Computed all 5 signals for each example

3. Fit logistic regression: P(correct) = sigmoid(w1*s1 + w2*s2 + ... + w5*s5)

4. Resulting coefficients (normalized to sum to 1):
   retrieval_relevance:   0.30 (most predictive single signal)
   groundedness:          0.25 (second most important)
   source_authority:      0.20 (surprisingly important for enterprise)
   freshness:             0.15 (important for fast-changing domains)
   internal_consistency:  0.10 (useful but noisy signal)

5. Validation: calibrated composite achieves ECE = 0.021 on held-out test set
```

---

## Case Study 6: Threshold Tuning Workshop

### Step-by-Step Process

A team needs to set the confidence threshold for auto-approving AI-generated insurance claim summaries.

**Step 1: Define the Business Constraint**
```
Requirement from compliance: 
  - False positive rate (bad summary auto-approved) must be < 2%
  - Want to maximize auto-approval rate (reduce human workload)
  
This is a precision-recall tradeoff:
  - Higher threshold → fewer auto-approvals, lower error rate
  - Lower threshold → more auto-approvals, higher error rate
```

**Step 2: Generate Precision-Recall Curve**

```python
def compute_precision_recall_at_thresholds(predictions, labels):
    """
    predictions: confidence scores (0-1) for 2,000 labeled examples
    labels: 1 = correct summary, 0 = incorrect summary
    """
    thresholds = np.arange(0.50, 0.99, 0.01)
    results = []
    
    for t in thresholds:
        approved = predictions >= t
        
        if approved.sum() == 0:
            continue
        
        precision = labels[approved].mean()       # Of approved, how many correct?
        recall = approved.sum() / len(labels)     # What % gets auto-approved?
        
        results.append({
            "threshold": t,
            "precision": precision,
            "recall": recall,  # = auto-approval rate
            "n_approved": approved.sum(),
            "error_rate": 1 - precision,
        })
    
    return pd.DataFrame(results)

# Real results from 2,000 labeled examples:
"""
Threshold | Precision | Auto-Approval Rate | Error Rate
   0.60   |   0.91    |       78%          |   9.0%   ← too many errors
   0.70   |   0.94    |       68%          |   6.0%
   0.75   |   0.96    |       61%          |   4.0%
   0.80   |   0.975   |       53%          |   2.5%
   0.82   |   0.981   |       49%          |   1.9%   ← MEETS REQUIREMENT
   0.85   |   0.988   |       44%          |   1.2%
   0.90   |   0.994   |       35%          |   0.6%
   0.95   |   0.998   |       22%          |   0.2%   ← too conservative
"""
```

**Step 3: Select Operating Point**

```
Decision: Threshold = 0.82

Rationale:
  - Error rate 1.9% < 2% requirement ✓
  - Auto-approval rate 49% (saves ~half of human review workload)
  - Next step down (0.80) has 2.5% error rate — violates constraint
  
Business impact:
  - 10,000 claims/month × 49% auto-approved = 4,900 fewer human reviews
  - Human review cost: $8/claim × 4,900 = $39,200/month saved
  - Remaining errors: 4,900 × 1.9% = 93 bad summaries/month
  - Cost of catching bad summaries downstream: ~$50 each = $4,650/month
  - Net monthly savings: $34,550
```

**Step 4: Deploy with Safety Margins**

```python
# Production deployment with monitoring
PRODUCTION_THRESHOLD = 0.82
SHADOW_THRESHOLD = 0.78  # Track what we WOULD approve at lower threshold

def process_claim(claim):
    summary = generate_summary(claim)
    confidence = confidence_scorer.score(claim, summary)
    
    if confidence >= PRODUCTION_THRESHOLD:
        auto_approve(summary)
        log_decision("auto_approved", confidence)
    elif confidence >= SHADOW_THRESHOLD:
        # Don't auto-approve but log as "shadow approved" for analysis
        queue_for_human_review(summary)
        log_decision("shadow_approved", confidence)
    else:
        queue_for_human_review(summary)
        log_decision("human_required", confidence)
```

---

## Case Study 7: Confidence Decay in Financial Systems

### System: AI-Powered Market Analysis

Financial data has explicit temporal sensitivity. A market analysis system implements confidence decay:

```python
class FinancialConfidenceDecay:
    """
    Confidence decays as underlying data ages.
    Different data types decay at different rates.
    """
    
    DECAY_RATES = {
        # Half-life in hours — confidence drops to 50% after this period
        "real_time_price": 0.5,        # 30 minutes — prices move fast
        "daily_market_data": 24,       # 1 day
        "quarterly_earnings": 2160,    # 90 days (until next earnings)
        "annual_report": 8760,         # 365 days
        "macroeconomic_indicator": 720, # 30 days (monthly releases)
        "regulatory_filing": 4380,     # 6 months
        "analyst_consensus": 168,      # 7 days (consensus shifts weekly)
    }
    
    # Volatility multiplier — during high-vol periods, decay faster
    VOLATILITY_MULTIPLIER = {
        "low": 1.0,      # VIX < 15
        "normal": 1.5,   # VIX 15-25
        "high": 3.0,     # VIX 25-35
        "extreme": 6.0,  # VIX > 35
    }
    
    def compute_temporal_confidence(self, data_sources, current_time):
        """
        Returns confidence adjusted for data freshness.
        """
        source_confidences = []
        
        for source in data_sources:
            age_hours = (current_time - source.timestamp).total_seconds() / 3600
            half_life = self.DECAY_RATES[source.data_type]
            
            # Adjust for current market volatility
            vol_regime = self._get_volatility_regime()
            effective_half_life = half_life / self.VOLATILITY_MULTIPLIER[vol_regime]
            
            # Exponential decay
            temporal_confidence = 0.5 ** (age_hours / effective_half_life)
            
            # Floor: even very old data has some residual value
            temporal_confidence = max(temporal_confidence, source.residual_floor)
            
            source_confidences.append({
                "source": source.name,
                "base_confidence": source.relevance_score,
                "temporal_factor": temporal_confidence,
                "effective_confidence": source.relevance_score * temporal_confidence,
                "age_hours": age_hours,
                "data_type": source.data_type,
            })
        
        # Overall confidence: weighted by source importance
        overall = np.average(
            [s["effective_confidence"] for s in source_confidences],
            weights=[s["base_confidence"] for s in source_confidences]
        )
        
        return TemporalConfidenceResult(
            overall=overall,
            sources=source_confidences,
            vol_regime=vol_regime,
            decay_warning=overall < 0.5  # Flag when confidence is low
        )

# Example scenario:
"""
Query: "What is the fair value of AAPL stock?"
Time: Monday 2:00 PM ET

Data sources:
  1. Real-time price (2 min old):     base=0.95, temporal=0.91, effective=0.86
  2. Analyst consensus (3 days old):  base=0.80, temporal=0.74, effective=0.59
  3. Quarterly earnings (45 days old): base=0.85, temporal=0.71, effective=0.60
  4. Annual report (200 days old):    base=0.70, temporal=0.63, effective=0.44

Overall confidence: 0.64
System response: "Here's my analysis [with caveat about moderate confidence]"

Same query on Friday evening (markets closed, data 5 hours stale):
  1. Last price (5 hours old):        base=0.95, temporal=0.001, effective=0.001
  System: "Market is closed. Last available data is from 4:00 PM..."
  Overall confidence drops to 0.41 → triggers caveat mode
"""
```

---

## Case Study 8: War Story — Miscalibrated Confidence in Production

### The Incident

**System:** A customer-facing AI chatbot for a SaaS platform (project management tool)
**Date:** March 2024
**Impact:** 3,200 users received confidently-stated wrong answers over 48 hours

### What Happened

```
Timeline:
  
  Day 0: Team deploys new embedding model (text-embedding-3-large → voyage-2)
         for the RAG system. Eval suite passes. Confidence scoring NOT re-calibrated.
  
  Day 1, 2:00 AM: First user reports: "The bot told me with high confidence 
         that I could bulk-delete tasks via API, but that endpoint doesn't exist."
  
  Day 1, 10:00 AM: Support team notices pattern — 15 similar reports.
         Bot is confidently recommending API endpoints from an OLD version
         of the documentation that was still in the vector store.
  
  Day 1, 3:00 PM: Engineering investigates. Root cause identified.
  
  Day 2, 9:00 AM: Fix deployed. Incident post-mortem scheduled.
```

### Root Cause Analysis

```python
# The problem: Confidence was computed using cosine similarity from retrieval
# The NEW embedding model (voyage-2) has different similarity distributions
# than the old model (text-embedding-3-large)

# Old model similarity distribution:
#   Relevant docs: mean=0.82, std=0.06
#   Irrelevant docs: mean=0.45, std=0.12
#   → Threshold of 0.70 correctly separated them

# New model similarity distribution:
#   Relevant docs: mean=0.91, std=0.03  ← MUCH HIGHER baseline
#   Irrelevant docs: mean=0.72, std=0.08 ← ALSO HIGHER
#   → Old threshold of 0.70 now lets irrelevant docs through as "confident"

# What this meant in practice:
# The system retrieved OUTDATED docs (similarity=0.75 with new model)
# Old threshold said "0.75 > 0.70, this is relevant, confidence=HIGH"
# But these were docs about deprecated API endpoints

# The confidence scorer used raw similarity as a signal:
def old_confidence(retrieval_score):
    # Calibrated for old model's distribution
    if retrieval_score > 0.80:
        return 0.95  # High confidence
    elif retrieval_score > 0.70:
        return 0.80  # Medium-high confidence  ← PROBLEM ZONE
    elif retrieval_score > 0.55:
        return 0.60
    else:
        return 0.30
```

### The Fix

```python
class RobustConfidenceScorer:
    """Fix: Confidence must be re-calibrated whenever retrieval model changes."""
    
    def __init__(self, embedding_model_id):
        # Each model has its own calibration parameters
        self.calibration = load_calibration(embedding_model_id)
        # If no calibration exists for this model, BLOCK deployment
        if not self.calibration:
            raise DeploymentBlockError(
                f"No calibration found for model {embedding_model_id}. "
                "Run calibration pipeline before deploying."
            )
    
    def score(self, retrieval_scores):
        # Normalize to model-specific distribution
        normalized = (retrieval_scores - self.calibration.mean) / self.calibration.std
        # Apply calibrated mapping
        return self.calibration.transform(normalized)

# New deployment checklist (added post-incident):
deployment_checks = [
    "✓ Eval suite passes",
    "✓ Confidence calibration run on new model",     # NEW
    "✓ Calibration ECE < 0.03",                      # NEW
    "✓ Similarity distribution check (shift < 0.1)", # NEW
    "✓ 100 random production queries spot-checked",  # NEW
    "✓ Gradual rollout (5% → 25% → 100%)",          # NEW
]
```

### Impact and Lessons

```
Impact:
  - 3,200 users received wrong answers with "high confidence" label
  - 847 support tickets filed
  - ~$125,000 in engineering + support costs
  - Trust damage (measured by 8% drop in chatbot usage over next 2 weeks)

Lessons:
  1. Confidence calibration is model-specific — ALWAYS recalibrate on model change
  2. Raw similarity scores are NOT confidence scores
  3. Deploy with canary/gradual rollout — would have caught this at 5%
  4. Monitor confidence distribution shifts, not just accuracy
  5. Add "confidence distribution anomaly detection" to alerts
```

---

## Case Study 9: Multi-Agent Confidence Aggregation

### Architecture: 4-Agent Research Pipeline

```python
class MultiAgentConfidencePipeline:
    """
    Pipeline: Query → Planner → Researcher → Synthesizer → Reviewer
    Each agent has its own confidence. How do you aggregate?
    """
    
    def __init__(self):
        self.agents = {
            "planner": PlannerAgent(),       # Decomposes query into sub-questions
            "researcher": ResearcherAgent(), # Retrieves and processes information
            "synthesizer": SynthesizerAgent(), # Combines findings into answer
            "reviewer": ReviewerAgent(),     # Checks quality and accuracy
        }
    
    def run_pipeline(self, query):
        # Stage 1: Planning
        plan = self.agents["planner"].plan(query)
        plan_confidence = plan.confidence  # How well-defined is the task?
        
        # Stage 2: Research (may run multiple sub-queries)
        research_results = []
        for sub_query in plan.sub_queries:
            result = self.agents["researcher"].research(sub_query)
            research_results.append(result)
        research_confidence = self._aggregate_research_confidence(research_results)
        
        # Stage 3: Synthesis
        synthesis = self.agents["synthesizer"].synthesize(research_results)
        synthesis_confidence = synthesis.confidence
        
        # Stage 4: Review
        review = self.agents["reviewer"].review(query, synthesis)
        review_confidence = review.confidence
        
        # Aggregate confidence across pipeline
        pipeline_confidence = self._aggregate_pipeline_confidence(
            plan_confidence=plan_confidence,
            research_confidence=research_confidence,
            synthesis_confidence=synthesis_confidence,
            review_confidence=review_confidence,
        )
        
        return PipelineResult(
            answer=synthesis.answer,
            confidence=pipeline_confidence,
            stage_confidences={
                "planning": plan_confidence,
                "research": research_confidence,
                "synthesis": synthesis_confidence,
                "review": review_confidence,
            }
        )
    
    def _aggregate_pipeline_confidence(self, **stage_confidences):
        """
        Key insight: Pipeline confidence is bounded by the WEAKEST link.
        But it's not simply min() — it's more nuanced.
        
        Options considered:
        1. Product (independent assumption): Π(ci) — too pessimistic
        2. Minimum: min(ci) — ignores relative importance
        3. Weighted harmonic mean — balances pessimism with importance
        4. Learned aggregation — best but requires training data
        
        We use option 3 with bottleneck detection.
        """
        weights = {
            "plan_confidence": 0.15,      # Planning errors cascade
            "research_confidence": 0.35,  # Garbage in, garbage out
            "synthesis_confidence": 0.30, # Core reasoning step
            "review_confidence": 0.20,    # Final quality gate
        }
        
        # Weighted harmonic mean (penalizes low values more than arithmetic mean)
        weighted_sum = sum(
            weights[k] / max(v, 0.01)  # Avoid division by zero
            for k, v in stage_confidences.items()
        )
        harmonic = sum(weights.values()) / weighted_sum
        
        # Bottleneck penalty: if any stage < 0.5, apply additional penalty
        min_confidence = min(stage_confidences.values())
        if min_confidence < 0.5:
            bottleneck_penalty = 0.3 * (0.5 - min_confidence)
            harmonic -= bottleneck_penalty
        
        return max(0.0, min(1.0, harmonic))
```

### Real Pipeline Confidence Examples

```
Example 1: Clear factual query
  Query: "What is our company's parental leave policy?"
  Stage confidences: plan=0.95, research=0.92, synthesis=0.90, review=0.93
  Aggregated confidence: 0.91
  → Auto-answer

Example 2: Ambiguous query requiring judgment
  Query: "Should we switch to the new pricing model?"
  Stage confidences: plan=0.72, research=0.68, synthesis=0.61, review=0.55
  Aggregated confidence: 0.58 (+ bottleneck penalty from review=0.55)
  → Escalate with explanation of uncertainty

Example 3: Research failure propagation
  Query: "What did the CEO say about Q4 targets in last week's all-hands?"
  Stage confidences: plan=0.90, research=0.35, synthesis=0.42, review=0.38
  Aggregated confidence: 0.32 (research failure cascades)
  → Refuse: "I couldn't find reliable information about this topic"

Key insight: Research confidence < 0.5 almost always means the pipeline 
should refuse. No amount of good synthesis can fix bad retrieval.
```

---

## Case Study 10: Business Impact — ROI of Confidence Scoring

### Before/After Confidence Implementation

**Company:** B2B SaaS with AI-powered document analysis (contracts)
**Scale:** 50,000 documents/month analyzed

```
BEFORE CONFIDENCE SCORING (all outputs sent to human review):

  Documents processed by AI:          50,000/month
  Human review rate:                   100% (ALL documents)
  Human reviewers needed:              25 FTEs
  Average review time:                 8 minutes/document
  Monthly human review cost:           25 × $6,500 = $162,500
  AI infrastructure cost:              $15,000/month
  Total monthly cost:                  $177,500
  
  Quality: 98.5% accuracy (humans catch AI errors)
  Throughput: 2,000 docs/reviewer/month

AFTER CONFIDENCE SCORING (tiered review):

  Tier 1 (confidence > 0.92): Auto-approve
    Volume: 28,000 documents (56%)
    Error rate: 1.1% (within acceptable threshold of 2%)
    Human cost: $0
    
  Tier 2 (confidence 0.75-0.92): Spot-check (30% sampling)
    Volume: 14,000 documents (28%)
    Sampled for review: 4,200 documents
    Human cost: 4,200 × 8 min × ($6,500/160 hrs) = ~$14,000
    
  Tier 3 (confidence < 0.75): Full human review
    Volume: 8,000 documents (16%)
    Human cost: 8,000 × 8 min × ($6,500/160 hrs) = ~$27,000
    
  Total human review cost:             $41,000/month
  AI infrastructure cost:              $18,000/month (confidence adds ~$3K)
  Total monthly cost:                  $59,000/month
  
  Quality: 97.8% accuracy (slight decrease — acceptable)
  Human reviewers needed:              10 FTEs (from 25)

═══════════════════════════════════════════════════
MONTHLY SAVINGS:        $118,500 (67% reduction)
ANNUAL SAVINGS:         $1,422,000
IMPLEMENTATION COST:    $180,000 (3 engineers × 2 months + calibration dataset)
PAYBACK PERIOD:         6.7 weeks
ROI (first year):       690%
```

### Detailed Implementation Cost Breakdown

```
Confidence scoring implementation:

Engineering (3 senior engineers × 2 months):        $130,000
  - Confidence model design and training:           40%
  - Calibration dataset creation (5K labeled docs): 25%
  - Integration with existing pipeline:             20%
  - Monitoring and alerting:                        15%

Calibration dataset:                                 $35,000
  - 5,000 documents with ground truth labels
  - 3 annotators per document at key decision boundaries
  - Domain expert adjudication for disagreements

Infrastructure (one-time):                           $15,000
  - NLI model hosting for groundedness signal
  - Additional compute for confidence computation
  - Monitoring dashboards

═══════════════════════════════════════════════════
Total implementation:                               $180,000
```

### Ongoing Monitoring Costs

```
Monthly operational costs for confidence scoring:

Compute (confidence inference on 50K docs):          $3,000
Calibration monitoring (weekly checks):              $500
Monthly recalibration runs:                          $200
Quarterly human audit (200 docs deep-review):        $2,000
Engineering maintenance (0.1 FTE):                   $2,000
─────────────────────────────────────────────────────────
Monthly operational overhead:                        $7,700

NET monthly savings after overhead: $118,500 - $7,700 = $110,800
```

---

## Key Takeaways for AI Architects

1. **Calibration is non-negotiable for high-stakes systems.** Raw model probabilities are almost never calibrated. Always apply post-hoc calibration (temperature scaling or Platt scaling) and verify with reliability diagrams.

2. **Confidence enables tiered service delivery.** The biggest ROI comes from routing: auto-approve high-confidence, human-review low-confidence. This typically saves 60-75% of human review costs.

3. **Confidence is model-specific.** Changing any component (embedding model, LLM, retrieval method) invalidates your confidence calibration. Build recalibration into your deployment pipeline.

4. **Composite scores outperform single signals.** Combine 4-6 orthogonal signals (retrieval quality, groundedness, source authority, freshness, consistency) with learned weights for robust confidence.

5. **Time decays confidence.** Especially in financial, legal, and medical domains. Implement explicit temporal decay with domain-appropriate half-lives.

6. **Pipeline confidence follows the weakest link.** In multi-agent systems, a single low-confidence stage should prevent high-confidence final output. Use harmonic mean with bottleneck penalties.

7. **Threshold selection is a business decision, not a technical one.** Use precision-recall curves and involve stakeholders in choosing the operating point that balances automation rate against acceptable error rate.

8. **Monitor calibration drift continuously.** Confidence scoring is not "set and forget." Weekly calibration checks with alerts for drift > 3% are essential.

9. **The cost of miscalibrated confidence exceeds the cost of no confidence.** A system that says "I don't know" is safer than one that says "I'm 95% sure" when it shouldn't be. Err on the side of under-confidence until calibration is proven.

10. **ROI is massive but requires upfront investment.** Typical payback is 2-3 months. Budget $150-250K for initial implementation at scale, expect $1M+ annual savings.
