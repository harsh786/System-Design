"""
Evaluation module.
Confidence scoring, faithfulness checking, quality metrics.
"""

from config import EVALUATION


class EvaluationResult:
    def __init__(self, confidence: float, faithful: bool, should_abstain: bool,
                 signals: dict = None):
        self.confidence = confidence
        self.faithful = faithful
        self.should_abstain = should_abstain
        self.signals = signals or {}

    def __repr__(self):
        status = "ABSTAIN" if self.should_abstain else "PASS"
        return f"EvalResult({status}, confidence={self.confidence:.2f}, faithful={self.faithful})"


def evaluate_response(
    query: str,
    response: str,
    context: str = "",
    retrieval_scores: list[float] = None,
) -> EvaluationResult:
    """
    Evaluate quality of a response using multiple signals.
    Returns confidence score and abstention decision.
    """
    print("[EVAL] Evaluating response quality...")
    signals = {}

    # Signal 1: Retrieval quality (if RAG was used)
    retrieval_confidence = 1.0
    if retrieval_scores:
        avg_score = sum(retrieval_scores) / len(retrieval_scores)
        retrieval_confidence = min(avg_score, 1.0)
        signals["retrieval_quality"] = retrieval_confidence

    # Signal 2: Response completeness
    # Heuristic: very short responses for complex queries = low confidence
    completeness = min(len(response) / 50, 1.0)  # At least 50 chars expected
    signals["completeness"] = completeness

    # Signal 3: Faithfulness (is response supported by context?)
    faithfulness = 1.0
    if context:
        faithfulness = check_faithfulness(response, context)
        signals["faithfulness"] = faithfulness

    # Signal 4: Hedging language detection
    hedge_words = ["might", "possibly", "unclear", "not sure", "uncertain", "maybe"]
    hedge_count = sum(1 for w in hedge_words if w in response.lower())
    hedge_penalty = min(hedge_count * 0.1, 0.3)
    signals["hedge_penalty"] = hedge_penalty

    # Signal 5: Abstention language detection
    abstention_phrases = [
        "i don't have", "i cannot find", "no information",
        "not in the context", "unable to determine"
    ]
    has_abstention = any(p in response.lower() for p in abstention_phrases)
    if has_abstention:
        signals["self_abstention"] = True

    # Combine signals
    confidence = (
        retrieval_confidence * 0.35 +
        completeness * 0.20 +
        faithfulness * 0.30 +
        (1.0 - hedge_penalty) * 0.15
    )

    # Override: if model itself says it can't answer, respect that
    if has_abstention:
        confidence = min(confidence, 0.3)

    should_abstain = confidence < EVALUATION["confidence_threshold"]
    faithful = faithfulness >= EVALUATION["faithfulness_threshold"]

    result = EvaluationResult(
        confidence=round(confidence, 3),
        faithful=faithful,
        should_abstain=should_abstain,
        signals=signals,
    )

    level = "LOW" if confidence < 0.4 else "MEDIUM" if confidence < 0.7 else "HIGH"
    print(f"[EVAL] Confidence: {confidence:.3f} ({level})")
    if should_abstain:
        print("[EVAL] Decision: ABSTAIN (below threshold)")

    return result


def check_faithfulness(response: str, context: str) -> float:
    """
    Check if response is faithful to context.
    Simple heuristic: what fraction of response sentences have keywords in context?
    """
    import re
    sentences = re.split(r'[.!?]+', response)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return 1.0

    supported = 0
    context_lower = context.lower()

    for sentence in sentences:
        # Check if key words from sentence appear in context
        words = set(sentence.lower().split())
        # Remove common words
        stop_words = {"the", "a", "an", "is", "was", "are", "were", "in", "on", "at",
                      "to", "for", "of", "and", "or", "but", "not", "with", "this", "that"}
        key_words = words - stop_words
        if not key_words:
            supported += 1
            continue

        matches = sum(1 for w in key_words if w in context_lower)
        if matches / len(key_words) > 0.3:
            supported += 1

    faithfulness = supported / len(sentences)
    return round(faithfulness, 3)
