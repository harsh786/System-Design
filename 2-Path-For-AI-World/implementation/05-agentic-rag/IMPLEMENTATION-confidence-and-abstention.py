"""
Confidence Scoring and Abstention System for Agentic RAG

Multi-signal confidence computation with threshold-based behavior decisions.
Handles: answer, caveat, clarify, abstain, and escalate actions.
"""

import asyncio
import json
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class OutputAction(Enum):
    ANSWER = "answer"
    ANSWER_WITH_CAVEAT = "answer_with_caveat"
    CLARIFY = "clarify"
    ABSTAIN = "abstain"
    ESCALATE = "escalate"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SignalScore:
    """Individual confidence signal with metadata."""
    name: str
    score: float  # 0.0 to 1.0
    weight: float
    reasoning: str = ""
    raw_values: list[float] = field(default_factory=list)


@dataclass
class ConfidenceResult:
    """Complete confidence assessment."""
    composite_score: float
    signals: list[SignalScore]
    action: OutputAction
    risk_level: RiskLevel
    reasoning: str = ""
    calibrated_score: Optional[float] = None  # After calibration


@dataclass
class RetrievedEvidence:
    """Simplified evidence representation for this module."""
    text: str
    similarity_score: float
    rerank_score: float = 0.0
    source_authority_tier: int = 2  # 1-4
    source_freshness_days: int = 30
    source_name: str = ""


@dataclass
class GeneratedAnswer:
    """The generated answer with metadata."""
    text: str
    claims: list[str] = field(default_factory=list)
    grounded_claims: list[str] = field(default_factory=list)
    ungrounded_claims: list[str] = field(default_factory=list)
    citations_count: int = 0
    total_sentences: int = 0


# ─────────────────────────────────────────────────────────────
# Individual Signal Computers
# ─────────────────────────────────────────────────────────────

class RetrievalQualitySignal:
    """
    Signal 1: How good were the retrieval scores?
    
    High scores indicate the vector DB found highly relevant content.
    Low scores suggest the query didn't match well against the corpus.
    """
    
    def compute(self, evidence: list[RetrievedEvidence]) -> SignalScore:
        if not evidence:
            return SignalScore(name="retrieval_quality", score=0.0, weight=0.15, reasoning="No evidence retrieved")
        
        # Use top-K similarity scores
        top_scores = [e.similarity_score for e in evidence[:5]]
        
        # Metrics:
        # 1. Mean of top scores
        mean_score = statistics.mean(top_scores)
        
        # 2. Score of the best match (ceiling)
        max_score = max(top_scores)
        
        # 3. Score drop-off (steep drop = only 1 good match)
        if len(top_scores) >= 2:
            dropoff = top_scores[0] - top_scores[-1]
            dropoff_penalty = min(dropoff * 0.5, 0.2)  # Penalize steep drop
        else:
            dropoff_penalty = 0.0
        
        # Composite: weighted combination
        score = 0.5 * mean_score + 0.3 * max_score - 0.2 * dropoff_penalty
        score = max(0.0, min(1.0, score))
        
        return SignalScore(
            name="retrieval_quality",
            score=score,
            weight=0.15,
            reasoning=f"Mean top-5 score: {mean_score:.3f}, max: {max_score:.3f}, dropoff penalty: {dropoff_penalty:.3f}",
            raw_values=top_scores,
        )


class RerankerAgreementSignal:
    """
    Signal 2: Do the reranker scores agree with initial retrieval?
    
    High agreement = retrieval was accurate.
    Low agreement = initial retrieval may have missed relevant docs.
    """
    
    def compute(self, evidence: list[RetrievedEvidence]) -> SignalScore:
        if not evidence or not any(e.rerank_score > 0 for e in evidence):
            return SignalScore(name="reranker_agreement", score=0.5, weight=0.10, reasoning="No reranker scores available")
        
        # Compute rank correlation between initial and reranked order
        initial_order = list(range(len(evidence[:5])))
        rerank_scores = [e.rerank_score for e in evidence[:5]]
        reranked_order = sorted(range(len(rerank_scores)), key=lambda i: rerank_scores[i], reverse=True)
        
        # Kendall's tau approximation (simplified)
        concordant = 0
        discordant = 0
        n = len(initial_order)
        for i in range(n):
            for j in range(i + 1, n):
                if (initial_order[i] - initial_order[j]) * (reranked_order[i] - reranked_order[j]) > 0:
                    concordant += 1
                else:
                    discordant += 1
        
        pairs = n * (n - 1) / 2
        tau = (concordant - discordant) / pairs if pairs > 0 else 0
        
        # Normalize tau from [-1, 1] to [0, 1]
        score = (tau + 1) / 2
        
        # Also factor in absolute rerank scores
        mean_rerank = statistics.mean(rerank_scores) if rerank_scores else 0.5
        
        final_score = 0.5 * score + 0.5 * mean_rerank
        
        return SignalScore(
            name="reranker_agreement",
            score=final_score,
            weight=0.10,
            reasoning=f"Rank correlation (tau): {tau:.3f}, mean rerank score: {mean_rerank:.3f}",
            raw_values=rerank_scores,
        )


class SourceFreshnessSignal:
    """
    Signal 3: How recent is the evidence?
    
    Important for time-sensitive queries. Less important for stable knowledge.
    """
    
    def __init__(self, query_is_time_sensitive: bool = False):
        self.time_sensitive = query_is_time_sensitive
    
    def compute(self, evidence: list[RetrievedEvidence]) -> SignalScore:
        if not evidence:
            return SignalScore(name="source_freshness", score=0.0, weight=0.10, reasoning="No evidence")
        
        # Compute freshness per source (exponential decay)
        freshness_scores = []
        for e in evidence[:5]:
            days = e.source_freshness_days
            if self.time_sensitive:
                # Aggressive decay for time-sensitive queries
                freshness = math.exp(-days / 30)  # Half-life ~21 days
            else:
                # Gentle decay for stable knowledge
                freshness = math.exp(-days / 365)  # Half-life ~253 days
            freshness_scores.append(freshness)
        
        score = statistics.mean(freshness_scores)
        
        # Adjust weight based on time sensitivity
        weight = 0.15 if self.time_sensitive else 0.05
        
        return SignalScore(
            name="source_freshness",
            score=score,
            weight=weight,
            reasoning=f"Time-sensitive={self.time_sensitive}, mean freshness={score:.3f}, source ages={[e.source_freshness_days for e in evidence[:5]]}",
            raw_values=freshness_scores,
        )


class SourceAuthoritySignal:
    """
    Signal 4: How authoritative are the sources?
    
    Tier 1 (official docs) > Tier 2 (wiki) > Tier 3 (slack) > Tier 4 (external)
    """
    
    TIER_SCORES = {1: 1.0, 2: 0.8, 3: 0.55, 4: 0.3}
    
    def compute(self, evidence: list[RetrievedEvidence]) -> SignalScore:
        if not evidence:
            return SignalScore(name="source_authority", score=0.0, weight=0.15, reasoning="No evidence")
        
        authority_scores = [self.TIER_SCORES.get(e.source_authority_tier, 0.5) for e in evidence[:5]]
        
        # Weighted: top result matters more
        weights = [0.35, 0.25, 0.20, 0.12, 0.08][:len(authority_scores)]
        weighted_score = sum(s * w for s, w in zip(authority_scores, weights))
        
        # Bonus if multiple high-authority sources agree
        tier1_count = sum(1 for e in evidence[:5] if e.source_authority_tier == 1)
        consensus_bonus = min(tier1_count * 0.05, 0.1)
        
        score = min(1.0, weighted_score + consensus_bonus)
        
        return SignalScore(
            name="source_authority",
            score=score,
            weight=0.15,
            reasoning=f"Source tiers: {[e.source_authority_tier for e in evidence[:5]]}, consensus bonus: {consensus_bonus:.2f}",
            raw_values=authority_scores,
        )


class ContextCoverageSignal:
    """
    Signal 5: Does the evidence cover all aspects of the question?
    
    Uses the sufficiency score from the evidence sufficiency checker.
    """
    
    def compute(self, sufficiency_score: float, covered_facets: int = 0, total_facets: int = 1) -> SignalScore:
        # Primary: use sufficiency score directly
        score = sufficiency_score
        
        # Secondary: facet coverage ratio
        if total_facets > 0:
            facet_ratio = covered_facets / total_facets
            score = 0.7 * sufficiency_score + 0.3 * facet_ratio
        
        return SignalScore(
            name="context_coverage",
            score=score,
            weight=0.15,
            reasoning=f"Sufficiency={sufficiency_score:.3f}, facets covered={covered_facets}/{total_facets}",
        )


class GroundednessSignal:
    """
    Signal 6: What fraction of claims are grounded in evidence?
    
    This is THE most important signal for preventing hallucination.
    """
    
    def compute(self, answer: GeneratedAnswer) -> SignalScore:
        if not answer.claims:
            return SignalScore(name="groundedness", score=0.5, weight=0.20, reasoning="No claims extracted")
        
        total = len(answer.claims)
        grounded = len(answer.grounded_claims)
        ungrounded = len(answer.ungrounded_claims)
        
        # Base score: fraction grounded
        base_score = grounded / total
        
        # Severe penalty for any ungrounded claims
        if ungrounded > 0:
            penalty = 0.1 * ungrounded  # Each ungrounded claim costs 0.1
            base_score = max(0.0, base_score - penalty)
        
        return SignalScore(
            name="groundedness",
            score=base_score,
            weight=0.20,
            reasoning=f"Claims: {total}, grounded: {grounded}, ungrounded: {ungrounded}",
            raw_values=[grounded / total if total > 0 else 0],
        )


class CitationSupportSignal:
    """
    Signal 7: What fraction of the answer has citation support?
    """
    
    def compute(self, answer: GeneratedAnswer) -> SignalScore:
        if answer.total_sentences == 0:
            return SignalScore(name="citation_support", score=0.0, weight=0.05, reasoning="Empty answer")
        
        citation_ratio = answer.citations_count / answer.total_sentences
        score = min(1.0, citation_ratio)  # Cap at 1.0
        
        return SignalScore(
            name="citation_support",
            score=score,
            weight=0.05,
            reasoning=f"Sentences with citations: {answer.citations_count}/{answer.total_sentences}",
        )


class AnswerConsistencySignal:
    """
    Signal 8: Do multiple generations of the answer agree?
    
    If the model gives different answers each time, confidence should be low.
    This requires generating the answer multiple times (N=3 typically).
    """
    
    def __init__(self, llm=None):
        self.llm = llm
    
    async def compute(self, question: str, evidence_text: str, num_samples: int = 3) -> SignalScore:
        """Generate N answers and measure agreement."""
        if not self.llm or num_samples <= 1:
            return SignalScore(name="answer_consistency", score=0.8, weight=0.10, reasoning="Single generation (assumed consistent)")
        
        # Generate multiple answers with temperature > 0
        answers = []
        for _ in range(num_samples):
            ans = await self.llm.generate(
                f"Question: {question}\nEvidence: {evidence_text}\nAnswer concisely:",
                temperature=0.7,
            )
            answers.append(ans)
        
        # Measure agreement using LLM-as-judge
        if len(answers) >= 2:
            agreement_score = await self._measure_agreement(answers)
        else:
            agreement_score = 1.0
        
        return SignalScore(
            name="answer_consistency",
            score=agreement_score,
            weight=0.10,
            reasoning=f"Generated {num_samples} samples, agreement={agreement_score:.3f}",
            raw_values=[agreement_score],
        )
    
    async def _measure_agreement(self, answers: list[str]) -> float:
        """Measure semantic agreement between multiple generated answers."""
        # In production: use embedding similarity or LLM judge
        # Simplified: check key fact overlap via token intersection
        token_sets = [set(a.lower().split()) for a in answers]
        
        if len(token_sets) < 2:
            return 1.0
        
        # Pairwise Jaccard similarity
        similarities = []
        for i in range(len(token_sets)):
            for j in range(i + 1, len(token_sets)):
                intersection = token_sets[i] & token_sets[j]
                union = token_sets[i] | token_sets[j]
                if union:
                    similarities.append(len(intersection) / len(union))
        
        return statistics.mean(similarities) if similarities else 0.0


# ─────────────────────────────────────────────────────────────
# Composite Confidence Scorer
# ─────────────────────────────────────────────────────────────

class CompositeConfidenceScorer:
    """
    Aggregates all signal scores into a single composite confidence score.
    Supports dynamic weight adjustment and calibration.
    """
    
    DEFAULT_WEIGHTS = {
        "retrieval_quality": 0.15,
        "reranker_agreement": 0.10,
        "source_freshness": 0.10,
        "source_authority": 0.15,
        "context_coverage": 0.15,
        "groundedness": 0.20,
        "citation_support": 0.05,
        "answer_consistency": 0.10,
    }
    
    def __init__(self, llm=None, calibration_params: Optional[dict] = None):
        self.llm = llm
        self.calibration_params = calibration_params  # For Platt scaling / isotonic regression
        
        # Initialize signal computers
        self.retrieval_signal = RetrievalQualitySignal()
        self.reranker_signal = RerankerAgreementSignal()
        self.freshness_signal = SourceFreshnessSignal()
        self.authority_signal = SourceAuthoritySignal()
        self.coverage_signal = ContextCoverageSignal()
        self.groundedness_signal = GroundednessSignal()
        self.citation_signal = CitationSupportSignal()
        self.consistency_signal = AnswerConsistencySignal(llm)
    
    async def compute(
        self,
        evidence: list[RetrievedEvidence],
        answer: GeneratedAnswer,
        sufficiency_score: float,
        question: str = "",
        time_sensitive: bool = False,
        covered_facets: int = 0,
        total_facets: int = 1,
        compute_consistency: bool = False,
    ) -> tuple[float, list[SignalScore]]:
        """
        Compute composite confidence score.
        
        Returns: (composite_score, individual_signals)
        """
        # Update freshness signal time sensitivity
        self.freshness_signal.time_sensitive = time_sensitive
        
        # Compute all signals
        signals = [
            self.retrieval_signal.compute(evidence),
            self.reranker_signal.compute(evidence),
            self.freshness_signal.compute(evidence),
            self.authority_signal.compute(evidence),
            self.coverage_signal.compute(sufficiency_score, covered_facets, total_facets),
            self.groundedness_signal.compute(answer),
            self.citation_signal.compute(answer),
        ]
        
        # Consistency signal (async, optional due to cost)
        if compute_consistency and self.llm:
            evidence_text = "\n".join(e.text[:200] for e in evidence[:5])
            consistency = await self.consistency_signal.compute(question, evidence_text)
            signals.append(consistency)
        else:
            signals.append(SignalScore(name="answer_consistency", score=0.8, weight=0.10, reasoning="Skipped"))
        
        # Normalize weights to sum to 1.0
        total_weight = sum(s.weight for s in signals)
        if total_weight > 0:
            for s in signals:
                s.weight = s.weight / total_weight
        
        # Weighted sum
        composite = sum(s.score * s.weight for s in signals)
        
        # Apply calibration if available
        if self.calibration_params:
            composite = self._calibrate(composite)
        
        return composite, signals
    
    def _calibrate(self, raw_score: float) -> float:
        """
        Apply calibration to raw confidence score.
        
        Uses Platt scaling: calibrated = sigmoid(a * raw + b)
        where a, b are learned from evaluation data.
        """
        a = self.calibration_params.get("a", 1.0)
        b = self.calibration_params.get("b", 0.0)
        
        logit = a * raw_score + b
        calibrated = 1 / (1 + math.exp(-logit))
        
        return calibrated


# ─────────────────────────────────────────────────────────────
# Threshold-Based Action Decider
# ─────────────────────────────────────────────────────────────

class ThresholdActionDecider:
    """
    Maps (confidence, risk) pairs to output actions using a configurable threshold matrix.
    """
    
    # Default thresholds: {risk_level: [(min_conf, action), ...]} — ordered high to low
    DEFAULT_THRESHOLDS = {
        RiskLevel.LOW: [
            (0.80, OutputAction.ANSWER),
            (0.60, OutputAction.ANSWER_WITH_CAVEAT),
            (0.40, OutputAction.CLARIFY),
            (0.00, OutputAction.ABSTAIN),
        ],
        RiskLevel.MEDIUM: [
            (0.85, OutputAction.ANSWER),
            (0.70, OutputAction.ANSWER_WITH_CAVEAT),
            (0.50, OutputAction.CLARIFY),
            (0.30, OutputAction.ABSTAIN),
            (0.00, OutputAction.ESCALATE),
        ],
        RiskLevel.HIGH: [
            (0.90, OutputAction.ANSWER),
            (0.80, OutputAction.ANSWER_WITH_CAVEAT),
            (0.60, OutputAction.ESCALATE),
            (0.00, OutputAction.ESCALATE),
        ],
        RiskLevel.CRITICAL: [
            (0.95, OutputAction.ANSWER_WITH_CAVEAT),
            (0.00, OutputAction.ESCALATE),
        ],
    }
    
    # Keywords that force escalation regardless of confidence
    FORCE_ESCALATE_KEYWORDS = [
        "legal action", "lawsuit", "termination", "compliance violation",
        "data breach", "security incident", "regulatory", "audit finding",
    ]
    
    def __init__(self, thresholds: Optional[dict] = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
    
    def decide(
        self,
        confidence: float,
        risk: RiskLevel,
        query: str = "",
        signals: Optional[list[SignalScore]] = None,
    ) -> tuple[OutputAction, str]:
        """
        Decide output action based on confidence and risk.
        
        Returns: (action, reasoning)
        """
        # Check force-escalation keywords
        query_lower = query.lower()
        for keyword in self.FORCE_ESCALATE_KEYWORDS:
            if keyword in query_lower:
                return OutputAction.ESCALATE, f"Force-escalate: topic contains '{keyword}'"
        
        # Check for specific signal red flags
        if signals:
            groundedness = next((s for s in signals if s.name == "groundedness"), None)
            if groundedness and groundedness.score < 0.3:
                return OutputAction.ABSTAIN, f"Groundedness critically low ({groundedness.score:.2f})"
        
        # Look up in threshold matrix
        risk_thresholds = self.thresholds.get(risk, self.thresholds[RiskLevel.MEDIUM])
        
        for min_conf, action in risk_thresholds:
            if confidence >= min_conf:
                reasoning = f"Confidence {confidence:.2f} >= {min_conf} threshold for risk={risk.value} → {action.value}"
                return action, reasoning
        
        # Fallback
        return OutputAction.ABSTAIN, "No threshold matched"
    
    def explain_decision(
        self,
        confidence: float,
        risk: RiskLevel,
        action: OutputAction,
        signals: list[SignalScore],
    ) -> str:
        """Generate human-readable explanation of the decision."""
        explanation = [
            f"Decision: {action.value}",
            f"Composite confidence: {confidence:.2f}",
            f"Risk level: {risk.value}",
            "",
            "Signal breakdown:",
        ]
        
        for signal in sorted(signals, key=lambda s: s.weight, reverse=True):
            bar = "█" * int(signal.score * 20) + "░" * (20 - int(signal.score * 20))
            explanation.append(f"  {signal.name:<22} {bar} {signal.score:.2f} (w={signal.weight:.2f})")
            if signal.reasoning:
                explanation.append(f"    └─ {signal.reasoning}")
        
        return "\n".join(explanation)


# ─────────────────────────────────────────────────────────────
# Calibration System
# ─────────────────────────────────────────────────────────────

class ConfidenceCalibrator:
    """
    Calibrates confidence scores using evaluation data.
    
    A well-calibrated system means: when it says "80% confident",
    it should be correct ~80% of the time.
    """
    
    def __init__(self):
        self.evaluation_data: list[tuple[float, bool]] = []  # (predicted_conf, was_correct)
    
    def add_evaluation_point(self, predicted_confidence: float, was_correct: bool):
        """Add a single evaluation data point."""
        self.evaluation_data.append((predicted_confidence, was_correct))
    
    def compute_calibration_error(self, n_bins: int = 10) -> dict:
        """
        Compute Expected Calibration Error (ECE) and per-bin statistics.
        """
        if not self.evaluation_data:
            return {"ece": 0.0, "bins": []}
        
        # Bin predictions
        bins = [[] for _ in range(n_bins)]
        for conf, correct in self.evaluation_data:
            bin_idx = min(int(conf * n_bins), n_bins - 1)
            bins[bin_idx].append((conf, correct))
        
        # Compute per-bin accuracy and confidence
        bin_stats = []
        ece = 0.0
        total = len(self.evaluation_data)
        
        for i, bin_data in enumerate(bins):
            if not bin_data:
                bin_stats.append({"bin": i, "count": 0, "avg_conf": 0, "accuracy": 0, "gap": 0})
                continue
            
            avg_conf = statistics.mean(conf for conf, _ in bin_data)
            accuracy = sum(1 for _, correct in bin_data if correct) / len(bin_data)
            gap = abs(avg_conf - accuracy)
            
            bin_stats.append({
                "bin": i,
                "range": f"{i/n_bins:.1f}-{(i+1)/n_bins:.1f}",
                "count": len(bin_data),
                "avg_confidence": avg_conf,
                "accuracy": accuracy,
                "gap": gap,
            })
            
            ece += (len(bin_data) / total) * gap
        
        return {"ece": ece, "bins": bin_stats}
    
    def fit_platt_scaling(self) -> dict:
        """
        Fit Platt scaling parameters (logistic calibration).
        
        Returns: {"a": float, "b": float} for sigmoid(a * score + b)
        """
        if len(self.evaluation_data) < 10:
            return {"a": 1.0, "b": 0.0}
        
        # Simple gradient descent for Platt scaling
        # In production: use sklearn.calibration.CalibratedClassifierCV
        a, b = 1.0, 0.0
        lr = 0.01
        
        for _ in range(1000):
            grad_a, grad_b = 0.0, 0.0
            for conf, correct in self.evaluation_data:
                logit = a * conf + b
                pred = 1 / (1 + math.exp(-logit))
                error = pred - (1.0 if correct else 0.0)
                grad_a += error * conf
                grad_b += error
            
            grad_a /= len(self.evaluation_data)
            grad_b /= len(self.evaluation_data)
            
            a -= lr * grad_a
            b -= lr * grad_b
        
        return {"a": a, "b": b}
    
    def fit_isotonic_regression(self) -> list[tuple[float, float]]:
        """
        Fit isotonic regression for calibration.
        Returns mapping points: [(raw_score, calibrated_score), ...]
        """
        if len(self.evaluation_data) < 5:
            return [(0.0, 0.0), (1.0, 1.0)]
        
        # Sort by predicted confidence
        sorted_data = sorted(self.evaluation_data, key=lambda x: x[0])
        
        # Pool Adjacent Violators Algorithm (PAVA)
        n = len(sorted_data)
        block_values = [1.0 if correct else 0.0 for _, correct in sorted_data]
        block_weights = [1] * n
        
        # Forward pass: merge violating pairs
        i = 0
        while i < len(block_values) - 1:
            if block_values[i] > block_values[i + 1]:
                # Merge blocks
                total_weight = block_weights[i] + block_weights[i + 1]
                merged_value = (block_values[i] * block_weights[i] + block_values[i + 1] * block_weights[i + 1]) / total_weight
                block_values[i] = merged_value
                block_weights[i] = total_weight
                block_values.pop(i + 1)
                block_weights.pop(i + 1)
                # Check backward
                if i > 0:
                    i -= 1
            else:
                i += 1
        
        # Create mapping points
        mapping = []
        idx = 0
        for value, weight in zip(block_values, block_weights):
            mid_idx = idx + weight // 2
            if mid_idx < n:
                raw_score = sorted_data[mid_idx][0]
                mapping.append((raw_score, value))
            idx += weight
        
        return mapping


# ─────────────────────────────────────────────────────────────
# Threshold Tuner
# ─────────────────────────────────────────────────────────────

class ThresholdTuner:
    """
    Tunes action thresholds based on evaluation data and business constraints.
    
    Balances:
    - Coverage: Answer as many questions as possible
    - Accuracy: Don't answer incorrectly
    - Safety: Escalate when uncertain on high-risk topics
    """
    
    def __init__(self, evaluation_data: list[dict] = None):
        """
        evaluation_data: list of {
            "confidence": float,
            "risk": str,
            "action_taken": str,
            "was_correct": bool,
            "user_satisfied": bool,
        }
        """
        self.data = evaluation_data or []
    
    def find_optimal_thresholds(
        self,
        target_accuracy: float = 0.90,
        min_coverage: float = 0.60,
    ) -> dict[RiskLevel, list[tuple[float, OutputAction]]]:
        """
        Find thresholds that achieve target accuracy while maximizing coverage.
        """
        optimal = {}
        
        for risk in RiskLevel:
            risk_data = [d for d in self.data if d["risk"] == risk.value]
            if not risk_data:
                optimal[risk] = ThresholdActionDecider.DEFAULT_THRESHOLDS[risk]
                continue
            
            # Binary search for the confidence threshold where accuracy >= target
            answer_threshold = self._find_threshold(risk_data, target_accuracy)
            
            # Set thresholds based on found optimal point
            optimal[risk] = [
                (answer_threshold, OutputAction.ANSWER),
                (answer_threshold - 0.15, OutputAction.ANSWER_WITH_CAVEAT),
                (answer_threshold - 0.30, OutputAction.CLARIFY),
                (max(0.0, answer_threshold - 0.50), OutputAction.ABSTAIN if risk in (RiskLevel.LOW, RiskLevel.MEDIUM) else OutputAction.ESCALATE),
                (0.0, OutputAction.ESCALATE if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) else OutputAction.ABSTAIN),
            ]
        
        return optimal
    
    def _find_threshold(self, data: list[dict], target_accuracy: float) -> float:
        """Binary search for optimal confidence threshold."""
        lo, hi = 0.0, 1.0
        
        for _ in range(20):  # 20 iterations of binary search
            mid = (lo + hi) / 2
            
            # Filter to samples above threshold
            above = [d for d in data if d["confidence"] >= mid]
            if not above:
                hi = mid
                continue
            
            accuracy = sum(1 for d in above if d["was_correct"]) / len(above)
            
            if accuracy >= target_accuracy:
                hi = mid  # Can lower threshold
            else:
                lo = mid  # Need higher threshold
        
        return (lo + hi) / 2
    
    def generate_report(self) -> str:
        """Generate a threshold tuning report."""
        if not self.data:
            return "No evaluation data available for tuning."
        
        lines = ["Threshold Tuning Report", "=" * 50, ""]
        
        for risk in RiskLevel:
            risk_data = [d for d in self.data if d["risk"] == risk.value]
            if not risk_data:
                continue
            
            total = len(risk_data)
            correct = sum(1 for d in risk_data if d["was_correct"])
            answered = sum(1 for d in risk_data if d["action_taken"] in ("answer", "answer_with_caveat"))
            
            lines.append(f"Risk: {risk.value}")
            lines.append(f"  Samples: {total}")
            lines.append(f"  Overall accuracy: {correct/total:.1%}")
            lines.append(f"  Coverage (answered): {answered/total:.1%}")
            
            # Accuracy at different thresholds
            for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
                above = [d for d in risk_data if d["confidence"] >= threshold]
                if above:
                    acc = sum(1 for d in above if d["was_correct"]) / len(above)
                    cov = len(above) / total
                    lines.append(f"  @{threshold:.1f}: accuracy={acc:.1%}, coverage={cov:.1%}")
            
            lines.append("")
        
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Complete Confidence & Abstention Pipeline
# ─────────────────────────────────────────────────────────────

class ConfidenceAbstentionPipeline:
    """
    End-to-end pipeline: compute signals → aggregate → decide action.
    """
    
    def __init__(self, llm=None, calibration_params: Optional[dict] = None, custom_thresholds: Optional[dict] = None):
        self.scorer = CompositeConfidenceScorer(llm, calibration_params)
        self.decider = ThresholdActionDecider(custom_thresholds)
    
    async def evaluate(
        self,
        evidence: list[RetrievedEvidence],
        answer: GeneratedAnswer,
        question: str,
        risk: RiskLevel,
        sufficiency_score: float,
        time_sensitive: bool = False,
        covered_facets: int = 0,
        total_facets: int = 1,
    ) -> ConfidenceResult:
        """
        Run the full confidence evaluation pipeline.
        """
        # Compute composite confidence
        composite, signals = await self.scorer.compute(
            evidence=evidence,
            answer=answer,
            sufficiency_score=sufficiency_score,
            question=question,
            time_sensitive=time_sensitive,
            covered_facets=covered_facets,
            total_facets=total_facets,
        )
        
        # Decide action
        action, reasoning = self.decider.decide(composite, risk, question, signals)
        
        return ConfidenceResult(
            composite_score=composite,
            signals=signals,
            action=action,
            risk_level=risk,
            reasoning=reasoning,
        )


# ─────────────────────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────────────────────

async def example():
    """Demonstrate the confidence and abstention system."""
    
    # Simulated evidence
    evidence = [
        RetrievedEvidence(text="Our SLA guarantees 99.9% uptime...", similarity_score=0.92, rerank_score=0.88, source_authority_tier=1, source_freshness_days=15),
        RetrievedEvidence(text="Response time targets: P1=15min...", similarity_score=0.87, rerank_score=0.85, source_authority_tier=1, source_freshness_days=15),
        RetrievedEvidence(text="Q3 revenue was $12.5M...", similarity_score=0.75, rerank_score=0.70, source_authority_tier=2, source_freshness_days=45),
        RetrievedEvidence(text="Customer satisfaction at 87%...", similarity_score=0.65, rerank_score=0.60, source_authority_tier=3, source_freshness_days=60),
    ]
    
    # Simulated answer
    answer = GeneratedAnswer(
        text="Our SLA guarantees 99.9% uptime with a 15-minute P1 response time. Q3 revenue was $12.5M.",
        claims=["SLA guarantees 99.9% uptime", "15-minute P1 response time", "Q3 revenue was $12.5M"],
        grounded_claims=["SLA guarantees 99.9% uptime", "15-minute P1 response time", "Q3 revenue was $12.5M"],
        ungrounded_claims=[],
        citations_count=3,
        total_sentences=3,
    )
    
    # Run pipeline
    pipeline = ConfidenceAbstentionPipeline()
    
    result = await pipeline.evaluate(
        evidence=evidence,
        answer=answer,
        question="What does our SLA guarantee and what was Q3 revenue?",
        risk=RiskLevel.MEDIUM,
        sufficiency_score=0.85,
        covered_facets=2,
        total_facets=2,
    )
    
    # Print results
    print(f"Composite confidence: {result.composite_score:.3f}")
    print(f"Action: {result.action.value}")
    print(f"Risk: {result.risk_level.value}")
    print(f"Reasoning: {result.reasoning}")
    print()
    
    # Print signal breakdown
    explanation = pipeline.decider.explain_decision(
        result.composite_score, result.risk_level, result.action, result.signals
    )
    print(explanation)
    
    # Demonstrate calibration
    print("\n\n--- Calibration Demo ---")
    calibrator = ConfidenceCalibrator()
    
    # Simulate evaluation data
    import random
    random.seed(42)
    for _ in range(100):
        conf = random.random()
        # Simulate: higher confidence → more likely correct (but imperfect)
        correct = random.random() < (conf * 0.8 + 0.1)
        calibrator.add_evaluation_point(conf, correct)
    
    cal_error = calibrator.compute_calibration_error()
    print(f"Expected Calibration Error: {cal_error['ece']:.4f}")
    
    platt_params = calibrator.fit_platt_scaling()
    print(f"Platt scaling params: a={platt_params['a']:.3f}, b={platt_params['b']:.3f}")


if __name__ == "__main__":
    asyncio.run(example())
