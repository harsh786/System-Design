"""
Confidence Scorer - Computes composite confidence for AI answers.

Combines multiple signals: retrieval score, source count, source agreement,
self-consistency, and citation coverage into a calibrated confidence score.
Demonstrates confidence-driven behavior (answer/caveat/abstain).
"""

import json
import os

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# --- Signal Weights ---
WEIGHTS = {
    "retrieval_score": 0.25,
    "source_count": 0.10,
    "source_agreement": 0.20,
    "self_consistency": 0.25,
    "citation_coverage": 0.20,
}

# --- Confidence Thresholds ---
THRESHOLDS = {
    "high": 0.85,       # Answer directly
    "medium": 0.65,     # Answer with caveats
    "low": 0.40,        # Ask for clarification
    # Below low = abstain
}


def compute_retrieval_score(contexts: list[dict]) -> float:
    """Compute average retrieval relevance score."""
    if not contexts:
        return 0.0
    scores = [ctx.get("relevance_score", 0.5) for ctx in contexts]
    return float(np.mean(scores))


def compute_source_count(contexts: list[dict], max_sources: int = 5) -> float:
    """Normalize source count: more sources = higher confidence."""
    relevant = [ctx for ctx in contexts if ctx.get("relevance_score", 0) > 0.7]
    return min(1.0, len(relevant) / max_sources)


def compute_source_agreement(contexts: list[dict]) -> float:
    """Check if sources agree with each other using LLM."""
    if len(contexts) < 2:
        return 0.5  # Can't assess agreement with one source

    texts = [ctx["text"] for ctx in contexts[:5]]
    prompt = f"""Do these text passages agree with each other or contradict each other?

Passages:
{chr(10).join(f'[{i+1}] {t}' for i, t in enumerate(texts))}

Output JSON: {{"agreement_score": <float 0-1 where 1=fully agree, 0=contradict>, "explanation": "..."}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("agreement_score", 0.5))
    except Exception:
        return 0.5


def compute_self_consistency(question: str, contexts: list[dict], n: int = 3) -> float:
    """Generate multiple answers and check agreement."""
    context_text = "\n".join(ctx["text"] for ctx in contexts)

    answers = []
    for _ in range(n):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"Answer based on this context:\n{context_text}"},
                    {"role": "user", "content": question},
                ],
                temperature=0.7,  # Higher temp for diversity
                max_tokens=200,
            )
            answers.append(response.choices[0].message.content)
        except Exception:
            pass

    if len(answers) < 2:
        return 0.5

    # Use LLM to judge agreement between answers
    prompt = f"""How consistent are these {len(answers)} answers to the same question?

Question: {question}

Answers:
{chr(10).join(f'[Answer {i+1}] {a}' for i, a in enumerate(answers))}

Output JSON: {{"consistency_score": <float 0-1 where 1=identical meaning, 0=completely different>, "explanation": "..."}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("consistency_score", 0.5))
    except Exception:
        return 0.5


def compute_citation_coverage(answer: str, contexts: list[dict]) -> float:
    """Check what fraction of claims in the answer are supported by sources."""
    context_text = "\n".join(ctx["text"] for ctx in contexts)

    prompt = f"""Identify factual claims in this answer and check if each is supported by the context.

Answer: {answer}
Context: {context_text}

Output JSON: {{
  "total_claims": <int>,
  "supported_claims": <int>,
  "coverage_score": <float 0-1 = supported/total>
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("coverage_score", 0.5))
    except Exception:
        return 0.5


def compute_composite_confidence(signals: dict) -> float:
    """Weighted combination of all signals."""
    score = sum(WEIGHTS[key] * signals[key] for key in WEIGHTS)
    return round(score, 3)


def determine_behavior(confidence: float) -> tuple[str, str]:
    """Determine how the system should behave based on confidence."""
    if confidence >= THRESHOLDS["high"]:
        return "HIGH", "Answer directly — no qualifiers needed"
    elif confidence >= THRESHOLDS["medium"]:
        return "MEDIUM", "Answer with caveats — 'Based on available information...'"
    elif confidence >= THRESHOLDS["low"]:
        return "LOW", "Ask for clarification — 'Could you provide more context?'"
    else:
        return "VERY LOW", "Abstain — 'I cannot confidently answer. Escalating to human.'"


def score_confidence(question: str, contexts: list[dict], answer: str) -> dict:
    """Full confidence scoring pipeline."""
    print(f"  Computing signals...")

    signals = {
        "retrieval_score": compute_retrieval_score(contexts),
        "source_count": compute_source_count(contexts),
        "source_agreement": compute_source_agreement(contexts),
        "self_consistency": compute_self_consistency(question, contexts),
        "citation_coverage": compute_citation_coverage(answer, contexts),
    }

    composite = compute_composite_confidence(signals)
    level, behavior = determine_behavior(composite)

    return {
        "signals": signals,
        "composite_confidence": composite,
        "confidence_level": level,
        "recommended_behavior": behavior,
    }


# --- Demo Examples ---

DEMO_EXAMPLES = [
    {
        "question": "What is the refund policy for annual subscriptions?",
        "contexts": [
            {"text": "Annual subscriptions can be refunded within 30 days of purchase.", "relevance_score": 0.95},
            {"text": "After 30 days, refunds are prorated based on remaining months.", "relevance_score": 0.92},
            {"text": "No refunds after 6 months from purchase date.", "relevance_score": 0.88},
            {"text": "Refund requests are processed within 5-7 business days.", "relevance_score": 0.85},
        ],
        "answer": "Annual subscriptions can be fully refunded within 30 days. After that, refunds are prorated. No refunds after 6 months.",
    },
    {
        "question": "What is the company's stance on quantum computing?",
        "contexts": [
            {"text": "Our roadmap includes cloud services and AI features.", "relevance_score": 0.35},
            {"text": "We partner with various technology providers.", "relevance_score": 0.28},
        ],
        "answer": "The company is investing heavily in quantum computing research and plans to release quantum services by 2025.",
    },
    {
        "question": "How do I configure SSO with Okta?",
        "contexts": [
            {"text": "SSO configuration: Go to Settings > Security > SSO. Select your provider.", "relevance_score": 0.78},
            {"text": "We support SAML-based SSO with Okta, Azure AD, and OneLogin.", "relevance_score": 0.82},
            {"text": "For Okta: use our Entity ID from the SSO settings page and configure the ACS URL.", "relevance_score": 0.90},
        ],
        "answer": "To configure SSO with Okta: 1) Go to Settings > Security > SSO, 2) Select Okta as provider, 3) Copy the Entity ID and ACS URL into Okta's SAML app config.",
    },
]


def run_demo():
    """Run confidence scoring on demo examples."""
    print("=" * 55)
    print("        CONFIDENCE SCORER DEMO")
    print("=" * 55)

    for i, example in enumerate(DEMO_EXAMPLES):
        print(f"\n--- Example {i+1} ---")
        print(f"Question: {example['question']}")

        result = score_confidence(
            example["question"],
            example["contexts"],
            example["answer"],
        )

        print(f"\n  Composite Confidence: {result['composite_confidence']:.3f} ({result['confidence_level']})")
        print(f"\n  Signals:")
        for signal, value in result["signals"].items():
            bar = "\u2588" * int(value * 20) + "\u2591" * (20 - int(value * 20))
            print(f"    {signal:<20} {bar} {value:.2f}")
        print(f"\n  Behavior: {result['recommended_behavior']}")

    # Calibration analysis
    print("\n" + "=" * 55)
    print("  CALIBRATION ANALYSIS (simulated)")
    print("=" * 55)
    print("\n  Confidence Bucket | Predicted | Actual Accuracy | Calibrated?")
    print("  " + "-" * 60)
    calibration_data = [
        ("0.90 - 1.00", "95%", "92%", "Yes (within 5%)"),
        ("0.80 - 0.90", "85%", "81%", "Yes (within 5%)"),
        ("0.70 - 0.80", "75%", "70%", "Yes (within 5%)"),
        ("0.60 - 0.70", "65%", "58%", "Slightly overconfident"),
        ("0.40 - 0.60", "50%", "41%", "Overconfident - needs calibration"),
    ]
    for bucket, predicted, actual, status in calibration_data:
        print(f"  {bucket:<19} {predicted:<11} {actual:<17} {status}")


if __name__ == "__main__":
    run_demo()
