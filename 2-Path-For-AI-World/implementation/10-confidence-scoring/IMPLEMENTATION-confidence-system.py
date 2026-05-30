"""
Confidence Scoring System - Production Implementation

A composite confidence scoring system that aggregates multiple independent signals
to produce calibrated confidence scores for AI system outputs.
"""

import time
import math
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceAction(Enum):
    ANSWER = "answer"
    ANSWER_WITH_CAVEATS = "answer_with_caveats"
    CLARIFY = "clarify"
    ABSTAIN = "abstain"
    HUMAN_REVIEW = "human_review"


@dataclass
class SignalResult:
    """Result from a single confidence signal extractor."""
    name: str
    raw_score: float  # Original score from extractor
    normalized_score: float  # Normalized to [0, 1]
    weight: float  # Weight in composite score
    metadata: dict = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class ConfidenceResult:
    """Final confidence scoring result."""
    composite_score: float  # Raw composite [0, 1]
    calibrated_score: float  # After calibration [0, 1]
    action: ConfidenceAction
    signals: list  # List of SignalResult
    risk_level: RiskLevel
    explanation: str
    timestamp: float = field(default_factory=time.time)
    query_hash: str = ""
    latency_ms: float = 0.0


@dataclass
class RetrievalContext:
    """Context from the retrieval system."""
    query: str
    documents: list  # List of retrieved documents
    scores: list  # Retrieval similarity scores
    reranker_scores: list = field(default_factory=list)
    document_timestamps: list = field(default_factory=list)
    document_sources: list = field(default_factory=list)
    document_authority_scores: list = field(default_factory=list)


@dataclass
class GenerationContext:
    """Context from the generation step."""
    query: str
    answer: str
    retrieved_context: str
    citations: list = field(default_factory=list)
    token_logprobs: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    tool_results: list = field(default_factory=list)
    alternative_answers: list = field(default_factory=list)


@dataclass
class DomainConfig:
    """Domain-specific confidence configuration."""
    name: str
    high_threshold: float = 0.85
    medium_threshold: float = 0.60
    low_threshold: float = 0.35
    abstain_threshold: float = 0.20
    signal_weights: dict = field(default_factory=dict)
    freshness_decay_rate: float = 0.01  # per day
    risk_level: RiskLevel = RiskLevel.LOW


# =============================================================================
# Signal Extractors
# =============================================================================

class BaseSignalExtractor:
    """Base class for confidence signal extractors."""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    def extract(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> SignalResult:
        start = time.time()
        raw_score = self._compute(retrieval_ctx, generation_ctx)
        normalized = self._normalize(raw_score)
        latency = (time.time() - start) * 1000
        return SignalResult(
            name=self.name,
            raw_score=raw_score,
            normalized_score=max(0.0, min(1.0, normalized)),
            weight=self.weight,
            latency_ms=latency,
        )

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        raise NotImplementedError

    def _normalize(self, raw_score: float) -> float:
        """Default normalization: clamp to [0, 1]."""
        return max(0.0, min(1.0, raw_score))


class RetrievalScoreExtractor(BaseSignalExtractor):
    """Extracts confidence from retrieval similarity scores."""

    def __init__(self, weight: float = 1.0, top_k: int = 5, min_score_threshold: float = 0.3):
        super().__init__("retrieval_score", weight)
        self.top_k = top_k
        self.min_score_threshold = min_score_threshold

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        if not retrieval_ctx.scores:
            return 0.0

        scores = sorted(retrieval_ctx.scores, reverse=True)[:self.top_k]
        top_score = scores[0]
        avg_score = sum(scores) / len(scores)

        # Penalize if no document meets minimum threshold
        above_threshold = [s for s in scores if s >= self.min_score_threshold]
        coverage_factor = len(above_threshold) / self.top_k

        # Combine: top score matters most, but average and coverage help
        combined = 0.5 * top_score + 0.3 * avg_score + 0.2 * coverage_factor
        return combined

    def _normalize(self, raw_score: float) -> float:
        # Cosine similarity is already [0, 1] in most cases
        return max(0.0, min(1.0, raw_score))


class RerankerScoreExtractor(BaseSignalExtractor):
    """Extracts confidence from cross-encoder reranker scores."""

    def __init__(self, weight: float = 1.2):
        super().__init__("reranker_score", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        if not retrieval_ctx.reranker_scores:
            return 0.5  # Neutral if no reranker available

        scores = sorted(retrieval_ctx.reranker_scores, reverse=True)
        top_score = scores[0]

        # Gap between top-1 and top-2 indicates clarity of best match
        gap = scores[0] - scores[1] if len(scores) > 1 else 0.0
        gap_bonus = min(0.1, gap * 0.5)  # Small bonus for clear winner

        return top_score + gap_bonus


class FreshnessExtractor(BaseSignalExtractor):
    """Extracts confidence based on source document freshness."""

    def __init__(self, weight: float = 0.8, decay_rate: float = 0.01):
        super().__init__("source_freshness", weight)
        self.decay_rate = decay_rate  # per day

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        if not retrieval_ctx.document_timestamps:
            return 0.5  # Unknown freshness

        now = time.time()
        freshness_scores = []
        for ts in retrieval_ctx.document_timestamps:
            days_old = (now - ts) / 86400
            freshness = math.exp(-self.decay_rate * days_old)
            freshness_scores.append(freshness)

        # Weight by retrieval score if available
        if retrieval_ctx.scores and len(retrieval_ctx.scores) == len(freshness_scores):
            total_weight = sum(retrieval_ctx.scores)
            if total_weight > 0:
                weighted = sum(f * s for f, s in zip(freshness_scores, retrieval_ctx.scores))
                return weighted / total_weight

        return sum(freshness_scores) / len(freshness_scores)


class AuthorityExtractor(BaseSignalExtractor):
    """Extracts confidence from source authority/credibility."""

    # Pre-defined authority tiers
    AUTHORITY_TIERS = {
        "official_docs": 1.0,
        "peer_reviewed": 0.95,
        "government": 0.90,
        "enterprise": 0.85,
        "established_media": 0.75,
        "blog_known_expert": 0.70,
        "community_wiki": 0.60,
        "blog_unknown": 0.40,
        "forum": 0.35,
        "social_media": 0.25,
        "unknown": 0.30,
    }

    def __init__(self, weight: float = 0.7):
        super().__init__("source_authority", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        if not retrieval_ctx.document_authority_scores:
            if retrieval_ctx.document_sources:
                # Attempt to classify sources
                scores = [self._classify_source(s) for s in retrieval_ctx.document_sources]
                return max(scores) if scores else 0.5
            return 0.5

        # Use pre-computed authority scores, weighted by retrieval relevance
        auth_scores = retrieval_ctx.document_authority_scores
        if retrieval_ctx.scores and len(retrieval_ctx.scores) == len(auth_scores):
            total_weight = sum(retrieval_ctx.scores)
            if total_weight > 0:
                return sum(a * s for a, s in zip(auth_scores, retrieval_ctx.scores)) / total_weight
        return max(auth_scores)

    def _classify_source(self, source: str) -> float:
        """Simple heuristic source classification."""
        source_lower = source.lower()
        if any(d in source_lower for d in [".gov", ".edu"]):
            return 0.90
        if any(d in source_lower for d in ["docs.", "documentation", "developer."]):
            return 0.95
        if "wikipedia" in source_lower:
            return 0.60
        if any(d in source_lower for d in ["stackoverflow", "github.com"]):
            return 0.65
        return 0.40


class ContextCoverageExtractor(BaseSignalExtractor):
    """Estimates what fraction of the query's information needs are covered by context."""

    def __init__(self, weight: float = 1.0):
        super().__init__("context_coverage", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        query = retrieval_ctx.query
        context = generation_ctx.retrieved_context

        if not context:
            return 0.0

        # Heuristic: keyword overlap between query and context
        query_tokens = set(query.lower().split())
        # Remove stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why",
                      "when", "where", "who", "which", "do", "does", "did", "can", "could",
                      "would", "should", "in", "on", "at", "to", "for", "of", "with", "and", "or"}
        query_keywords = query_tokens - stop_words

        if not query_keywords:
            return 0.5

        context_lower = context.lower()
        covered = sum(1 for kw in query_keywords if kw in context_lower)
        coverage = covered / len(query_keywords)

        # Also check: is context substantial enough?
        context_length_factor = min(1.0, len(context) / 500)  # At least 500 chars expected

        return 0.7 * coverage + 0.3 * context_length_factor


class GroundednessExtractor(BaseSignalExtractor):
    """
    Measures whether the answer is grounded in the provided context.
    In production, use an NLI model (e.g., MiniCheck, AlignScore).
    This implementation uses a heuristic approximation.
    """

    def __init__(self, weight: float = 1.5, nli_model=None):
        super().__init__("groundedness", weight)
        self.nli_model = nli_model  # Optional NLI model for production use

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        if self.nli_model:
            return self._nli_groundedness(generation_ctx)
        return self._heuristic_groundedness(generation_ctx)

    def _nli_groundedness(self, generation_ctx: GenerationContext) -> float:
        """Use NLI model to check entailment. Replace with actual model call."""
        # Decompose answer into sentences/claims
        claims = self._extract_claims(generation_ctx.answer)
        if not claims:
            return 0.5

        scores = []
        for claim in claims:
            # In production: score = nli_model.predict(premise=context, hypothesis=claim)
            score = self.nli_model.predict(
                premise=generation_ctx.retrieved_context,
                hypothesis=claim
            )
            scores.append(score)

        # Use minimum as conservative estimate (weakest link)
        return 0.4 * min(scores) + 0.6 * (sum(scores) / len(scores))

    def _heuristic_groundedness(self, generation_ctx: GenerationContext) -> float:
        """Heuristic groundedness check based on n-gram overlap."""
        answer = generation_ctx.answer.lower()
        context = generation_ctx.retrieved_context.lower()

        if not context or not answer:
            return 0.0

        # Check sentence-level overlap
        answer_sentences = [s.strip() for s in answer.split('.') if len(s.strip()) > 10]
        if not answer_sentences:
            return 0.5

        grounded_count = 0
        for sentence in answer_sentences:
            # Check if key phrases from sentence appear in context
            words = sentence.split()
            # Check 3-grams
            trigrams = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]
            if trigrams:
                overlap = sum(1 for tg in trigrams if tg in context) / len(trigrams)
                if overlap > 0.3:
                    grounded_count += 1

        return grounded_count / len(answer_sentences)

    def _extract_claims(self, answer: str) -> list:
        """Split answer into atomic claims."""
        sentences = [s.strip() for s in answer.split('.') if len(s.strip()) > 10]
        return sentences


class CitationSupportExtractor(BaseSignalExtractor):
    """Measures citation precision and recall."""

    def __init__(self, weight: float = 0.9):
        super().__init__("citation_support", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        citations = generation_ctx.citations
        if not citations:
            # No citations provided — can't verify, neutral-low signal
            return 0.4

        # Check citation validity
        valid_citations = 0
        for citation in citations:
            if self._verify_citation(citation, generation_ctx.retrieved_context):
                valid_citations += 1

        precision = valid_citations / len(citations) if citations else 0

        # Estimate recall: how many answer sentences have citations?
        answer_sentences = [s.strip() for s in generation_ctx.answer.split('.') if len(s.strip()) > 10]
        cited_sentences = len(citations)  # Simplified: assume 1 citation per sentence
        recall = min(1.0, cited_sentences / max(1, len(answer_sentences)))

        # F1 of citation precision and recall
        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        return f1

    def _verify_citation(self, citation: dict, context: str) -> bool:
        """Verify a citation references actual content in the context."""
        cited_text = citation.get("text", "")
        if not cited_text:
            return False
        # Check if cited text appears in context (simplified)
        return cited_text.lower()[:50] in context.lower()


class ConsistencyExtractor(BaseSignalExtractor):
    """
    Measures answer consistency across multiple generations.
    Requires pre-computed alternative answers.
    """

    def __init__(self, weight: float = 1.0):
        super().__init__("answer_consistency", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        alternatives = generation_ctx.alternative_answers
        if not alternatives:
            return 0.5  # Can't measure consistency without alternatives

        main_answer = generation_ctx.answer.lower()
        similarities = []

        for alt in alternatives:
            sim = self._compute_similarity(main_answer, alt.lower())
            similarities.append(sim)

        # Average pairwise similarity
        avg_sim = sum(similarities) / len(similarities)

        # Also check: are alternatives consistent with each other?
        if len(alternatives) >= 2:
            pairwise = []
            for i in range(len(alternatives)):
                for j in range(i + 1, len(alternatives)):
                    pairwise.append(self._compute_similarity(
                        alternatives[i].lower(), alternatives[j].lower()
                    ))
            mutual_consistency = sum(pairwise) / len(pairwise) if pairwise else 0.5
            return 0.6 * avg_sim + 0.4 * mutual_consistency

        return avg_sim

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity on word sets (simplified; use embeddings in production)."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)


class ToolSuccessExtractor(BaseSignalExtractor):
    """Measures success rate of tool/API calls."""

    def __init__(self, weight: float = 1.1):
        super().__init__("tool_success", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        tool_calls = generation_ctx.tool_calls
        tool_results = generation_ctx.tool_results

        if not tool_calls:
            return 0.7  # No tools needed — slightly positive signal

        if not tool_results:
            return 0.0  # Tools called but no results — failure

        success_count = 0
        for result in tool_results:
            if isinstance(result, dict):
                if result.get("success", False):
                    success_count += 1
                elif result.get("status_code", 500) < 400:
                    success_count += 1
            elif result is not None:
                success_count += 1

        success_rate = success_count / len(tool_calls)

        # Penalize partial failures more heavily
        if success_rate < 1.0 and success_rate > 0.0:
            return success_rate * 0.8  # Discount partial success

        return success_rate


class RiskClassifierExtractor(BaseSignalExtractor):
    """
    Classifies query risk level. Does NOT contribute to confidence score directly;
    instead, it modifies the threshold for action decisions.
    """

    RISK_KEYWORDS = {
        RiskLevel.CRITICAL: ["suicide", "emergency", "overdose", "kill", "die"],
        RiskLevel.HIGH: ["dosage", "medication", "invest", "legal advice", "diagnosis",
                         "treatment", "symptom", "side effect", "contraindication"],
        RiskLevel.MEDIUM: ["tax", "insurance", "contract", "regulation", "compliance",
                           "health", "medical", "financial"],
    }

    def __init__(self, weight: float = 0.0):  # Weight 0 — doesn't contribute to score
        super().__init__("risk_classifier", weight)

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        """Returns risk level as float (higher = riskier)."""
        query_lower = retrieval_ctx.query.lower()

        for level in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM]:
            if any(kw in query_lower for kw in self.RISK_KEYWORDS[level]):
                return {"critical": 1.0, "high": 0.8, "medium": 0.5}[level.value]

        return 0.1  # Low risk

    def classify_risk(self, query: str) -> RiskLevel:
        """Get the discrete risk level."""
        query_lower = query.lower()
        for level in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM]:
            if any(kw in query_lower for kw in self.RISK_KEYWORDS[level]):
                return level
        return RiskLevel.LOW


class HistoricalPerformanceExtractor(BaseSignalExtractor):
    """Uses historical accuracy for similar queries as a prior."""

    def __init__(self, weight: float = 0.6, performance_store: dict = None):
        super().__init__("historical_performance", weight)
        # In production: backed by a database keyed on query cluster
        self.performance_store = performance_store or {}

    def _compute(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> float:
        query = retrieval_ctx.query
        cluster = self._get_query_cluster(query)

        if cluster in self.performance_store:
            historical = self.performance_store[cluster]
            accuracy = historical.get("accuracy", 0.5)
            sample_size = historical.get("n", 0)
            # Shrink toward prior with small samples (Bayesian smoothing)
            prior = 0.5
            smoothed = (accuracy * sample_size + prior * 10) / (sample_size + 10)
            return smoothed

        return 0.5  # No history — neutral

    def _get_query_cluster(self, query: str) -> str:
        """Simple hash-based clustering (replace with embedding clustering in production)."""
        # Simplified: cluster by first significant word
        words = [w for w in query.lower().split()
                 if w not in {"what", "how", "why", "is", "the", "a", "an"}]
        if words:
            return words[0]
        return "unknown"

    def update(self, query: str, was_correct: bool):
        """Update historical performance with new feedback."""
        cluster = self._get_query_cluster(query)
        if cluster not in self.performance_store:
            self.performance_store[cluster] = {"accuracy": 0.5, "n": 0, "correct": 0}

        entry = self.performance_store[cluster]
        entry["n"] += 1
        if was_correct:
            entry["correct"] += 1
        entry["accuracy"] = entry["correct"] / entry["n"]


# =============================================================================
# Composite Confidence Scorer
# =============================================================================

class CompositeConfidenceScorer:
    """
    Aggregates multiple confidence signals into a single composite score.
    Supports weighted combination, calibration, and action mapping.
    """

    def __init__(self, domain_config: DomainConfig = None):
        self.domain_config = domain_config or DomainConfig(name="general")
        self.extractors: list[BaseSignalExtractor] = []
        self.risk_classifier = RiskClassifierExtractor()
        self.calibrator: Optional[Callable] = None  # Calibration function
        self.history: list = []  # For analytics

    def add_extractor(self, extractor: BaseSignalExtractor):
        """Add a signal extractor to the pipeline."""
        # Apply domain-specific weight override if configured
        if extractor.name in self.domain_config.signal_weights:
            extractor.weight = self.domain_config.signal_weights[extractor.name]
        self.extractors.append(extractor)

    def set_calibrator(self, calibrator: Callable):
        """Set a calibration function (raw_score -> calibrated_score)."""
        self.calibrator = calibrator

    def score(self, retrieval_ctx: RetrievalContext, generation_ctx: GenerationContext) -> ConfidenceResult:
        """Compute the full confidence score."""
        start = time.time()

        # Extract all signals
        signals = []
        for extractor in self.extractors:
            try:
                signal = extractor.extract(retrieval_ctx, generation_ctx)
                signals.append(signal)
            except Exception as e:
                logger.warning(f"Signal extractor {extractor.name} failed: {e}")
                # Use neutral score on failure
                signals.append(SignalResult(
                    name=extractor.name, raw_score=0.5,
                    normalized_score=0.5, weight=extractor.weight,
                    metadata={"error": str(e)}
                ))

        # Compute weighted composite
        composite = self._aggregate(signals)

        # Apply calibration
        calibrated = self.calibrator(composite) if self.calibrator else composite

        # Determine risk level
        risk_level = self.risk_classifier.classify_risk(retrieval_ctx.query)

        # Map to action
        action = self._map_to_action(calibrated, risk_level)

        # Generate explanation
        explanation = self._explain(signals, composite, calibrated, action, risk_level)

        # Build result
        result = ConfidenceResult(
            composite_score=composite,
            calibrated_score=calibrated,
            action=action,
            signals=signals,
            risk_level=risk_level,
            explanation=explanation,
            query_hash=hashlib.md5(retrieval_ctx.query.encode()).hexdigest()[:8],
            latency_ms=(time.time() - start) * 1000,
        )

        # Log for analytics
        self._log(result)

        return result

    def _aggregate(self, signals: list[SignalResult]) -> float:
        """Weighted average aggregation with normalization."""
        # Filter out zero-weight signals (like risk classifier)
        scoring_signals = [s for s in signals if s.weight > 0]
        if not scoring_signals:
            return 0.5

        total_weight = sum(s.weight for s in scoring_signals)
        weighted_sum = sum(s.normalized_score * s.weight for s in scoring_signals)

        return weighted_sum / total_weight

    def _map_to_action(self, calibrated_score: float, risk_level: RiskLevel) -> ConfidenceAction:
        """Map confidence score + risk to an action."""
        cfg = self.domain_config

        # High-risk override: require higher confidence
        if risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            if calibrated_score < cfg.high_threshold:
                return ConfidenceAction.HUMAN_REVIEW

        if calibrated_score >= cfg.high_threshold:
            return ConfidenceAction.ANSWER
        elif calibrated_score >= cfg.medium_threshold:
            return ConfidenceAction.ANSWER_WITH_CAVEATS
        elif calibrated_score >= cfg.low_threshold:
            return ConfidenceAction.CLARIFY
        else:
            return ConfidenceAction.ABSTAIN

    def _explain(self, signals, composite, calibrated, action, risk_level) -> str:
        """Generate human-readable explanation of confidence decision."""
        parts = [f"Composite={composite:.3f}, Calibrated={calibrated:.3f}, Action={action.value}"]
        parts.append(f"Risk={risk_level.value}")

        # Identify weakest signals
        scoring_signals = sorted(
            [s for s in signals if s.weight > 0],
            key=lambda s: s.normalized_score
        )
        if scoring_signals:
            weakest = scoring_signals[0]
            strongest = scoring_signals[-1]
            parts.append(f"Weakest: {weakest.name}={weakest.normalized_score:.2f}")
            parts.append(f"Strongest: {strongest.name}={strongest.normalized_score:.2f}")

        return " | ".join(parts)

    def _log(self, result: ConfidenceResult):
        """Log result for analytics and calibration data collection."""
        self.history.append({
            "timestamp": result.timestamp,
            "query_hash": result.query_hash,
            "composite": result.composite_score,
            "calibrated": result.calibrated_score,
            "action": result.action.value,
            "risk": result.risk_level.value,
            "signals": {s.name: s.normalized_score for s in result.signals},
            "latency_ms": result.latency_ms,
        })

        # Keep bounded history
        if len(self.history) > 10000:
            self.history = self.history[-5000:]


# =============================================================================
# Confidence Analytics
# =============================================================================

class ConfidenceAnalytics:
    """Analytics and monitoring for confidence scoring system."""

    def __init__(self, scorer: CompositeConfidenceScorer):
        self.scorer = scorer
        self.feedback: list = []  # (query_hash, was_correct) pairs

    def record_feedback(self, query_hash: str, was_correct: bool):
        """Record ground truth feedback for calibration."""
        self.feedback.append({
            "query_hash": query_hash,
            "was_correct": was_correct,
            "timestamp": time.time(),
        })

    def compute_accuracy_by_confidence_bin(self, n_bins: int = 10) -> dict:
        """Compute accuracy within confidence bins for calibration analysis."""
        # Match feedback to history by query_hash
        feedback_map = {f["query_hash"]: f["was_correct"] for f in self.feedback}
        matched = [(h["calibrated"], feedback_map[h["query_hash"]])
                   for h in self.scorer.history if h["query_hash"] in feedback_map]

        if not matched:
            return {}

        bins = defaultdict(list)
        for score, correct in matched:
            bin_idx = min(int(score * n_bins), n_bins - 1)
            bins[bin_idx].append(correct)

        result = {}
        for bin_idx, outcomes in bins.items():
            bin_center = (bin_idx + 0.5) / n_bins
            accuracy = sum(outcomes) / len(outcomes)
            result[bin_center] = {
                "accuracy": accuracy,
                "count": len(outcomes),
                "avg_confidence": bin_center,
                "calibration_error": abs(accuracy - bin_center),
            }

        return result

    def compute_ece(self, n_bins: int = 10) -> float:
        """Expected Calibration Error."""
        bins = self.compute_accuracy_by_confidence_bin(n_bins)
        if not bins:
            return -1.0

        total_samples = sum(b["count"] for b in bins.values())
        ece = sum(b["count"] / total_samples * b["calibration_error"] for b in bins.values())
        return ece

    def get_signal_importance(self) -> dict:
        """Analyze which signals are most predictive of correct answers."""
        feedback_map = {f["query_hash"]: f["was_correct"] for f in self.feedback}

        signal_scores_correct = defaultdict(list)
        signal_scores_incorrect = defaultdict(list)

        for h in self.scorer.history:
            if h["query_hash"] in feedback_map:
                target = signal_scores_correct if feedback_map[h["query_hash"]] else signal_scores_incorrect
                for signal_name, score in h["signals"].items():
                    target[signal_name].append(score)

        importance = {}
        all_signals = set(list(signal_scores_correct.keys()) + list(signal_scores_incorrect.keys()))
        for signal in all_signals:
            correct_mean = (sum(signal_scores_correct[signal]) / len(signal_scores_correct[signal])
                           if signal_scores_correct[signal] else 0.5)
            incorrect_mean = (sum(signal_scores_incorrect[signal]) / len(signal_scores_incorrect[signal])
                             if signal_scores_incorrect[signal] else 0.5)
            importance[signal] = correct_mean - incorrect_mean  # Separation

        return dict(sorted(importance.items(), key=lambda x: -x[1]))

    def get_confidence_distribution(self) -> dict:
        """Get distribution statistics of confidence scores."""
        if not self.scorer.history:
            return {}

        scores = [h["calibrated"] for h in self.scorer.history]
        scores.sort()
        n = len(scores)

        return {
            "count": n,
            "mean": sum(scores) / n,
            "median": scores[n // 2],
            "p10": scores[int(n * 0.1)],
            "p25": scores[int(n * 0.25)],
            "p75": scores[int(n * 0.75)],
            "p90": scores[int(n * 0.9)],
            "std": (sum((s - sum(scores)/n)**2 for s in scores) / n) ** 0.5,
            "abstain_rate": sum(1 for h in self.scorer.history if h["action"] == "abstain") / n,
        }


# =============================================================================
# A/B Testing for Scoring Weights
# =============================================================================

class ConfidenceABTest:
    """A/B test different weight configurations."""

    def __init__(self):
        self.variants: dict[str, dict] = {}  # variant_name -> weights
        self.results: dict[str, list] = defaultdict(list)  # variant -> outcomes

    def add_variant(self, name: str, weights: dict):
        """Add a weight configuration variant."""
        self.variants[name] = weights

    def assign_variant(self, query_hash: str) -> str:
        """Deterministically assign a query to a variant."""
        variant_names = sorted(self.variants.keys())
        idx = int(hashlib.md5(query_hash.encode()).hexdigest(), 16) % len(variant_names)
        return variant_names[idx]

    def record_outcome(self, variant: str, was_correct: bool, confidence: float):
        """Record outcome for a variant."""
        self.results[variant].append({
            "correct": was_correct,
            "confidence": confidence,
        })

    def get_results(self) -> dict:
        """Get comparative results across variants."""
        summary = {}
        for variant, outcomes in self.results.items():
            if not outcomes:
                continue
            n = len(outcomes)
            accuracy = sum(o["correct"] for o in outcomes) / n
            avg_confidence = sum(o["confidence"] for o in outcomes) / n
            # Brier score
            brier = sum((o["confidence"] - (1 if o["correct"] else 0))**2 for o in outcomes) / n
            summary[variant] = {
                "n": n,
                "accuracy": accuracy,
                "avg_confidence": avg_confidence,
                "brier_score": brier,
            }
        return summary


# =============================================================================
# Factory: Build Default Scorer
# =============================================================================

def build_default_scorer(domain: str = "general") -> CompositeConfidenceScorer:
    """Build a scorer with all default extractors for a given domain."""
    configs = {
        "general": DomainConfig(
            name="general", high_threshold=0.85, medium_threshold=0.60,
            low_threshold=0.35, abstain_threshold=0.20
        ),
        "medical": DomainConfig(
            name="medical", high_threshold=0.95, medium_threshold=0.80,
            low_threshold=0.60, abstain_threshold=0.40,
            signal_weights={"groundedness": 2.0, "source_authority": 1.5, "source_freshness": 1.2}
        ),
        "financial": DomainConfig(
            name="financial", high_threshold=0.90, medium_threshold=0.75,
            low_threshold=0.50, abstain_threshold=0.30,
            signal_weights={"source_freshness": 2.0, "tool_success": 1.5}
        ),
        "legal": DomainConfig(
            name="legal", high_threshold=0.92, medium_threshold=0.78,
            low_threshold=0.55, abstain_threshold=0.35,
            signal_weights={"source_authority": 2.0, "citation_support": 1.5}
        ),
    }

    config = configs.get(domain, configs["general"])
    scorer = CompositeConfidenceScorer(domain_config=config)

    # Add all extractors
    scorer.add_extractor(RetrievalScoreExtractor())
    scorer.add_extractor(RerankerScoreExtractor())
    scorer.add_extractor(FreshnessExtractor(decay_rate=config.freshness_decay_rate))
    scorer.add_extractor(AuthorityExtractor())
    scorer.add_extractor(ContextCoverageExtractor())
    scorer.add_extractor(GroundednessExtractor())
    scorer.add_extractor(CitationSupportExtractor())
    scorer.add_extractor(ConsistencyExtractor())
    scorer.add_extractor(ToolSuccessExtractor())
    scorer.add_extractor(HistoricalPerformanceExtractor())

    return scorer


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Build scorer for general domain
    scorer = build_default_scorer("medical")

    # Simulate a query
    retrieval_ctx = RetrievalContext(
        query="What is the recommended dosage of metformin for type 2 diabetes?",
        documents=["doc1", "doc2", "doc3"],
        scores=[0.92, 0.85, 0.71],
        reranker_scores=[0.95, 0.78, 0.62],
        document_timestamps=[time.time() - 86400 * 30, time.time() - 86400 * 90, time.time() - 86400 * 365],
        document_sources=["docs.medical-reference.org", "pubmed.ncbi.nlm.nih.gov", "healthblog.com"],
        document_authority_scores=[0.95, 0.95, 0.40],
    )

    generation_ctx = GenerationContext(
        query="What is the recommended dosage of metformin for type 2 diabetes?",
        answer="The recommended starting dosage of metformin for type 2 diabetes is 500mg twice daily or 850mg once daily, with gradual titration. Maximum dose is typically 2550mg/day divided into doses.",
        retrieved_context="Metformin hydrochloride tablets: Initial dose 500mg twice daily or 850mg once daily. Increase in increments of 500mg weekly or 850mg every 2 weeks. Maximum recommended dose 2550mg daily.",
        citations=[{"text": "Metformin hydrochloride tablets: Initial dose 500mg twice daily"}],
        alternative_answers=[
            "Metformin starting dose is 500mg BID or 850mg daily, titrated up to max 2550mg/day.",
            "For type 2 diabetes, metformin is started at 500-850mg daily and can be increased to 2550mg maximum.",
        ],
    )

    result = scorer.score(retrieval_ctx, generation_ctx)

    print(f"Composite Score: {result.composite_score:.3f}")
    print(f"Calibrated Score: {result.calibrated_score:.3f}")
    print(f"Action: {result.action.value}")
    print(f"Risk Level: {result.risk_level.value}")
    print(f"Explanation: {result.explanation}")
    print(f"Latency: {result.latency_ms:.1f}ms")
    print("\nSignal Breakdown:")
    for signal in sorted(result.signals, key=lambda s: -s.normalized_score):
        print(f"  {signal.name:25s} = {signal.normalized_score:.3f} (weight={signal.weight:.1f})")
