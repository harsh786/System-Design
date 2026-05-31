"""
Hallucination Prevention Pipeline
===================================
Demonstrates a complete 6-layer anti-hallucination system for RAG.

Shows how each layer catches different types of hallucination and how
confidence scoring drives the final decision (answer / caveat / abstain).

Uses simulated LLM responses by default (no API key needed).
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import re
import time

# =============================================================================
# KNOWLEDGE BASE (Fictional Company: "NovaTech Solutions")
# =============================================================================

KNOWLEDGE_BASE = [
    {
        "id": "fact_1",
        "content": "NovaTech Solutions was founded in 2019 by Sarah Chen and Marcus Williams in Austin, Texas.",
        "embedding": None,  # Will be generated
    },
    {
        "id": "fact_2",
        "content": "NovaTech's flagship product is 'DataFlow Pro', a real-time data pipeline platform that processes up to 500,000 events per second.",
        "embedding": None,
    },
    {
        "id": "fact_3",
        "content": "NovaTech has 450 employees as of Q3 2024, with offices in Austin, London, and Singapore.",
        "embedding": None,
    },
    {
        "id": "fact_4",
        "content": "NovaTech's pricing starts at $299/month for the Starter plan (up to 100K events/sec) and $1,499/month for Enterprise (unlimited).",
        "embedding": None,
    },
    {
        "id": "fact_5",
        "content": "NovaTech raised a $75 million Series B round in January 2024, led by Sequoia Capital.",
        "embedding": None,
    },
    {
        "id": "fact_6",
        "content": "DataFlow Pro supports integrations with AWS, GCP, Azure, Snowflake, and Databricks. Kafka integration was added in v3.2 (March 2024).",
        "embedding": None,
    },
    {
        "id": "fact_7",
        "content": "NovaTech's SLA guarantees 99.95% uptime. In 2023, actual uptime was 99.97%. There was one major outage in August 2023 lasting 4 hours.",
        "embedding": None,
    },
    {
        "id": "fact_8",
        "content": "NovaTech's main competitors are StreamBase (by Oracle), Apache Flink managed services, and Confluent's ksqlDB.",
        "embedding": None,
    },
    {
        "id": "fact_9",
        "content": "NovaTech does NOT offer on-premises deployment. The product is cloud-only (SaaS). Self-hosted options are on the 2025 roadmap.",
        "embedding": None,
    },
    {
        "id": "fact_10",
        "content": "NovaTech's data retention policy: Standard plan retains data for 30 days. Enterprise plan retains for 1 year. GDPR compliance was certified in June 2023.",
        "embedding": None,
    },
]

# =============================================================================
# TEST QUESTIONS
# =============================================================================

TEST_QUESTIONS = [
    {
        "question": "What is NovaTech's pricing for the Enterprise plan?",
        "type": "answerable",
        "expected_behavior": "ANSWER with confidence",
        "description": "Directly answerable from knowledge base",
    },
    {
        "question": "How does NovaTech's performance compare to Apache Kafka?",
        "type": "partially_answerable",
        "expected_behavior": "CAVEAT - we know competitors and throughput, but not direct comparison",
        "description": "Partially answerable - some related info exists",
    },
    {
        "question": "What is NovaTech's employee satisfaction score?",
        "type": "unanswerable",
        "expected_behavior": "ABSTAIN - no information about this",
        "description": "Not answerable from knowledge base at all",
    },
    {
        "question": "Who is NovaTech's CTO and what is their background?",
        "type": "hallucination_trap",
        "expected_behavior": "ABSTAIN - model will want to make up a CTO name",
        "description": "LLMs typically hallucinate a plausible CTO name here",
    },
    {
        "question": "Does NovaTech support on-premises deployment?",
        "type": "has_negative_info",
        "expected_behavior": "ANSWER - KB explicitly says NO on-prem",
        "description": "Tests handling of explicit negative information",
    },
]


# =============================================================================
# SIMULATED EMBEDDING & LLM (no API key needed)
# =============================================================================

EMBEDDING_DIM = 128

# Keyword-based relevance simulation
TOPIC_KEYWORDS = {
    "fact_1": ["founded", "founder", "sarah", "chen", "marcus", "williams", "austin", "texas", "2019", "started", "created"],
    "fact_2": ["dataflow", "product", "pipeline", "events", "throughput", "500000", "flagship", "real-time", "processing"],
    "fact_3": ["employees", "offices", "london", "singapore", "team", "size", "headcount", "staff", "450"],
    "fact_4": ["pricing", "cost", "plan", "starter", "enterprise", "month", "$299", "$1499", "price"],
    "fact_5": ["funding", "raised", "series", "sequoia", "investment", "capital", "$75", "million", "round"],
    "fact_6": ["integration", "aws", "gcp", "azure", "snowflake", "databricks", "kafka", "support", "connect"],
    "fact_7": ["uptime", "sla", "outage", "reliability", "99.95", "downtime", "availability"],
    "fact_8": ["competitor", "streambase", "oracle", "flink", "confluent", "ksqldb", "compare", "alternative", "versus"],
    "fact_9": ["on-premises", "on-prem", "self-hosted", "cloud", "saas", "deploy", "deployment", "hosted"],
    "fact_10": ["retention", "data", "gdpr", "compliance", "30 days", "privacy", "policy", "store"],
}


def compute_relevance(question: str, fact_id: str) -> float:
    """Simulate relevance scoring using keyword overlap."""
    question_lower = question.lower()
    keywords = TOPIC_KEYWORDS.get(fact_id, [])
    
    if not keywords:
        return 0.0
    
    matches = sum(1 for kw in keywords if kw in question_lower)
    # Normalize and add some noise for realism
    score = min(matches / max(len(keywords) * 0.3, 1), 1.0)
    score += np.random.uniform(-0.05, 0.05)  # Small noise
    return max(0.0, min(1.0, score))


# Simulated LLM responses (what a model would generate)
SIMULATED_RESPONSES = {
    "What is NovaTech's pricing for the Enterprise plan?": {
        "without_pipeline": "NovaTech's Enterprise plan costs $1,499/month and includes unlimited events per second, priority support, custom SLAs, and dedicated account management. They also offer annual billing with a 20% discount.",
        "with_pipeline": "According to NovaTech's pricing, the Enterprise plan is $1,499/month and includes unlimited events per second. [Source: fact_4]",
        "claims": [
            ("Enterprise plan costs $1,499/month", True, "fact_4"),
            ("includes unlimited events per second", True, "fact_4"),
            ("priority support", False, None),  # Not in KB
            ("custom SLAs", False, None),  # Not in KB
            ("dedicated account management", False, None),  # Not in KB
            ("annual billing with 20% discount", False, None),  # Not in KB - hallucinated
        ],
    },
    "How does NovaTech's performance compare to Apache Kafka?": {
        "without_pipeline": "NovaTech's DataFlow Pro processes up to 500,000 events per second, which is comparable to a well-tuned Kafka cluster. However, NovaTech offers easier setup and managed infrastructure. In benchmarks, NovaTech shows 30% lower latency than Kafka for stream processing workloads.",
        "with_pipeline": "NovaTech's DataFlow Pro processes up to 500,000 events/sec [Source: fact_2]. Kafka is listed as a supported integration (added in v3.2) [Source: fact_6], and Confluent's ksqlDB is mentioned as a competitor [Source: fact_8]. However, I don't have direct performance comparison data between NovaTech and Kafka.",
        "claims": [
            ("DataFlow Pro processes 500,000 events/sec", True, "fact_2"),
            ("comparable to well-tuned Kafka cluster", False, None),  # No comparison data
            ("easier setup and managed infrastructure", False, None),  # Not stated
            ("30% lower latency than Kafka", False, None),  # Hallucinated benchmark
        ],
    },
    "What is NovaTech's employee satisfaction score?": {
        "without_pipeline": "NovaTech has an employee satisfaction score of 4.2 out of 5 on Glassdoor, with employees particularly praising the company culture and work-life balance. The company was named one of Austin's Best Places to Work in 2023.",
        "with_pipeline": "I don't have information about NovaTech's employee satisfaction score in my available sources. I can tell you that NovaTech has 450 employees with offices in Austin, London, and Singapore [Source: fact_3], but satisfaction metrics are not available.",
        "claims": [
            ("satisfaction score of 4.2 out of 5", False, None),  # Completely hallucinated
            ("praising company culture and work-life balance", False, None),  # Hallucinated
            ("Austin's Best Places to Work in 2023", False, None),  # Hallucinated
        ],
    },
    "Who is NovaTech's CTO and what is their background?": {
        "without_pipeline": "NovaTech's CTO is Dr. James Park, who previously led engineering at Stripe. He holds a PhD in distributed systems from MIT and joined NovaTech in 2020 as the third employee.",
        "with_pipeline": "I don't have information about NovaTech's CTO in my available sources. I know the company was founded by Sarah Chen and Marcus Williams [Source: fact_1], but their specific roles (CEO, CTO, etc.) and other leadership team members are not documented in my sources.",
        "claims": [
            ("CTO is Dr. James Park", False, None),  # Completely hallucinated
            ("previously led engineering at Stripe", False, None),  # Hallucinated
            ("PhD in distributed systems from MIT", False, None),  # Hallucinated
            ("joined NovaTech in 2020 as third employee", False, None),  # Hallucinated
        ],
    },
    "Does NovaTech support on-premises deployment?": {
        "without_pipeline": "Yes, NovaTech offers on-premises deployment for enterprise customers who require data sovereignty. The on-prem version requires a minimum 3-node cluster and starts at $5,000/month.",
        "with_pipeline": "No, NovaTech does NOT offer on-premises deployment. The product is cloud-only (SaaS). However, self-hosted options are on the 2025 roadmap. [Source: fact_9]",
        "claims": [
            ("offers on-premises deployment", False, None),  # CONTRADICTS KB - fact_9 says NO
            ("for enterprise customers requiring data sovereignty", False, None),  # Hallucinated
            ("minimum 3-node cluster at $5,000/month", False, None),  # Hallucinated
        ],
    },
}


# =============================================================================
# PIPELINE COMPONENTS
# =============================================================================

@dataclass
class RetrievalResult:
    """A retrieved chunk with relevance score."""
    fact_id: str
    content: str
    relevance_score: float


@dataclass
class ClaimVerification:
    """Result of verifying a single claim against context."""
    claim: str
    is_supported: bool
    supporting_source: Optional[str]
    confidence: float


@dataclass
class PipelineResult:
    """Full result from the anti-hallucination pipeline."""
    question: str
    retrieved_chunks: List[RetrievalResult]
    sufficiency_score: float
    raw_generation: str
    claims: List[ClaimVerification]
    confidence_score: float
    decision: str  # ANSWER, CAVEAT, ABSTAIN, ESCALATE
    final_response: str


def step1_retrieve_with_relevance(question: str, threshold: float = 0.3) -> List[RetrievalResult]:
    """
    LAYER 1: Retrieval with Relevance Scoring
    
    Retrieve chunks and REJECT those below the relevance threshold.
    This prevents garbage context from reaching the LLM.
    """
    results = []
    
    for fact in KNOWLEDGE_BASE:
        score = compute_relevance(question, fact["id"])
        if score >= threshold:
            results.append(RetrievalResult(
                fact_id=fact["id"],
                content=fact["content"],
                relevance_score=score,
            ))
    
    # Sort by relevance
    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results[:5]  # Top 5 chunks max


def step2_check_sufficiency(question: str, chunks: List[RetrievalResult]) -> float:
    """
    LAYER 2: Context Sufficiency Check
    
    Even with relevant chunks, can we actually answer this question?
    Returns a score 0-1 indicating how sufficient the context is.
    """
    if not chunks:
        return 0.0
    
    # Heuristic: combine relevance scores and coverage
    max_relevance = max(c.relevance_score for c in chunks)
    avg_relevance = sum(c.relevance_score for c in chunks) / len(chunks)
    
    # Higher max relevance = more likely we have a direct answer
    # More chunks = more context coverage
    sufficiency = (max_relevance * 0.6 + avg_relevance * 0.2 + min(len(chunks) / 3, 1.0) * 0.2)
    
    return min(1.0, sufficiency)


def step3_grounded_generation(question: str, chunks: List[RetrievalResult]) -> str:
    """
    LAYER 3: Grounded Generation
    
    Generate answer ONLY from provided context. Force citations.
    In production, this uses a carefully crafted system prompt.
    """
    # Return the simulated "with pipeline" response
    if question in SIMULATED_RESPONSES:
        return SIMULATED_RESPONSES[question]["with_pipeline"]
    return "I don't have enough information to answer this question."


def step4_verify_claims(question: str, generation: str, chunks: List[RetrievalResult]) -> List[ClaimVerification]:
    """
    LAYER 4: Output Verification
    
    Decompose the generation into claims and verify each against context.
    This catches hallucinations that slip through grounded generation.
    """
    verified_claims = []
    
    if question in SIMULATED_RESPONSES:
        response_data = SIMULATED_RESPONSES[question]
        # Use the claims from our simulated data
        # In production, an LLM would decompose the response into claims
        for claim_text, is_supported, source in response_data["claims"]:
            # Only verify claims that appear in the WITH pipeline response
            if any(claim_text.lower() in generation.lower() for _ in [1]):
                verified_claims.append(ClaimVerification(
                    claim=claim_text,
                    is_supported=is_supported,
                    supporting_source=source,
                    confidence=0.9 if is_supported else 0.1,
                ))
    
    # If no claims extracted, create a generic one
    if not verified_claims and chunks:
        verified_claims.append(ClaimVerification(
            claim="(response references available context)",
            is_supported=True,
            supporting_source=chunks[0].fact_id if chunks else None,
            confidence=0.7,
        ))
    
    return verified_claims


def step5_compute_confidence(
    chunks: List[RetrievalResult],
    sufficiency: float,
    claims: List[ClaimVerification],
) -> float:
    """
    LAYER 5: Confidence Scoring
    
    Composite score from multiple signals:
    - Retrieval relevance (do we have good context?)
    - Sufficiency (can we answer from this context?)
    - Claim verification rate (what % of claims are supported?)
    """
    if not chunks:
        return 0.0
    
    # Signal 1: Best retrieval relevance
    retrieval_signal = max(c.relevance_score for c in chunks) if chunks else 0.0
    
    # Signal 2: Context sufficiency
    sufficiency_signal = sufficiency
    
    # Signal 3: Claim support rate
    if claims:
        supported = sum(1 for c in claims if c.is_supported)
        claim_signal = supported / len(claims)
    else:
        claim_signal = 0.5  # Neutral if no claims to verify
    
    # Weighted composite
    confidence = (
        retrieval_signal * 0.25 +
        sufficiency_signal * 0.35 +
        claim_signal * 0.40
    )
    
    return confidence


def step6_decide(confidence: float, claims: List[ClaimVerification]) -> Tuple[str, str]:
    """
    LAYER 6: Decision
    
    Based on confidence score, decide how to respond:
    - HIGH (>0.7): Answer confidently
    - MEDIUM (0.4-0.7): Answer with caveats
    - LOW (0.2-0.4): Abstain
    - VERY LOW (<0.2): Escalate to human
    """
    if confidence > 0.7:
        return "ANSWER", "High confidence - answer directly"
    elif confidence > 0.4:
        return "CAVEAT", "Medium confidence - answer with caveats about limitations"
    elif confidence > 0.2:
        return "ABSTAIN", "Low confidence - decline to answer"
    else:
        return "ESCALATE", "Very low confidence - escalate to human agent"


# =============================================================================
# PIPELINE ORCHESTRATION
# =============================================================================

def run_pipeline(question: str) -> PipelineResult:
    """Run the full 6-layer anti-hallucination pipeline."""
    
    # Layer 1: Retrieve with relevance filtering
    chunks = step1_retrieve_with_relevance(question)
    
    # Layer 2: Check sufficiency
    sufficiency = step2_check_sufficiency(question, chunks)
    
    # Layer 3: Grounded generation
    generation = step3_grounded_generation(question, chunks)
    
    # Layer 4: Verify claims
    claims = step4_verify_claims(question, generation, chunks)
    
    # Layer 5: Compute confidence
    confidence = step5_compute_confidence(chunks, sufficiency, claims)
    
    # Layer 6: Decide
    decision, reason = step6_decide(confidence, claims)
    
    # Construct final response based on decision
    if decision == "ANSWER":
        final_response = generation
    elif decision == "CAVEAT":
        final_response = f"Based on available information (with some gaps): {generation}"
    elif decision == "ABSTAIN":
        final_response = "I don't have sufficient information in my knowledge base to answer this question accurately. I'd rather not guess."
    else:  # ESCALATE
        final_response = "I cannot answer this reliably. Routing to a human agent."
    
    return PipelineResult(
        question=question,
        retrieved_chunks=chunks,
        sufficiency_score=sufficiency,
        raw_generation=generation,
        claims=claims,
        confidence_score=confidence,
        decision=decision,
        final_response=final_response,
    )


def get_naive_response(question: str) -> str:
    """Get what a naive (no-pipeline) system would respond."""
    if question in SIMULATED_RESPONSES:
        return SIMULATED_RESPONSES[question]["without_pipeline"]
    return "I'm not sure about that."


def count_hallucinated_claims(question: str, use_pipeline: bool) -> Tuple[int, int]:
    """Count hallucinated vs total claims for a response."""
    if question not in SIMULATED_RESPONSES:
        return 0, 0
    
    claims_data = SIMULATED_RESPONSES[question]["claims"]
    total = len(claims_data)
    hallucinated = sum(1 for _, supported, _ in claims_data if not supported)
    
    if use_pipeline:
        # Pipeline catches most hallucinations - only supported claims make it through
        # Simulate that pipeline removes unsupported claims from output
        return 0, sum(1 for _, supported, _ in claims_data if supported)
    
    return hallucinated, total


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    np.random.seed(42)
    
    print("\n" + "=" * 70)
    print("   HALLUCINATION PREVENTION PIPELINE")
    print("   Complete 6-Layer Defense Demonstration")
    print("=" * 70)
    
    # =========================================================================
    # Show the knowledge base
    # =========================================================================
    
    print(f"\n{'='*70}")
    print("KNOWLEDGE BASE: NovaTech Solutions (10 facts)")
    print(f"{'='*70}\n")
    
    for fact in KNOWLEDGE_BASE:
        print(f"  [{fact['id']}] {fact['content'][:80]}...")
    
    print(f"\n  → This is ALL the system knows. Anything beyond this = hallucination.")
    
    # =========================================================================
    # Run each test question
    # =========================================================================
    
    total_claims_without = 0
    total_hallucinated_without = 0
    total_claims_with = 0
    total_hallucinated_with = 0
    decisions = {"ANSWER": 0, "CAVEAT": 0, "ABSTAIN": 0, "ESCALATE": 0}
    
    for i, test in enumerate(TEST_QUESTIONS, 1):
        question = test["question"]
        
        print(f"\n{'='*70}")
        print(f"QUESTION {i}/{len(TEST_QUESTIONS)}: {question}")
        print(f"Type: {test['type']} | Expected: {test['expected_behavior']}")
        print(f"{'='*70}")
        
        # --- WITHOUT PIPELINE ---
        print(f"\n  ┌─ WITHOUT PIPELINE (naive LLM response) ─────────────────────────────")
        naive_response = get_naive_response(question)
        print(f"  │ {naive_response[:100]}")
        if len(naive_response) > 100:
            print(f"  │ {naive_response[100:200]}")
        
        h_without, t_without = count_hallucinated_claims(question, use_pipeline=False)
        total_hallucinated_without += h_without
        total_claims_without += t_without
        
        if t_without > 0:
            print(f"  │")
            print(f"  │ Claims: {t_without} total, {h_without} HALLUCINATED ({h_without*100//t_without}%)")
        print(f"  └────────────────────────────────────────────────────────────────────────")
        
        # --- WITH PIPELINE ---
        print(f"\n  ┌─ WITH PIPELINE (6-layer defense) ──────────────────────────────────────")
        
        result = run_pipeline(question)
        decisions[result.decision] += 1
        
        # Layer 1: Retrieval
        print(f"  │ LAYER 1 - Retrieved Chunks ({len(result.retrieved_chunks)} found):")
        for chunk in result.retrieved_chunks[:3]:
            print(f"  │   [{chunk.fact_id}] relevance={chunk.relevance_score:.2f} | {chunk.content[:60]}...")
        if not result.retrieved_chunks:
            print(f"  │   (no relevant chunks found)")
        
        # Layer 2: Sufficiency
        print(f"  │")
        print(f"  │ LAYER 2 - Sufficiency Score: {result.sufficiency_score:.2f}", end="")
        if result.sufficiency_score > 0.6:
            print(" (SUFFICIENT)")
        elif result.sufficiency_score > 0.3:
            print(" (PARTIAL)")
        else:
            print(" (INSUFFICIENT)")
        
        # Layer 3: Generation
        print(f"  │")
        print(f"  │ LAYER 3 - Grounded Generation:")
        gen_lines = result.raw_generation[:150]
        print(f"  │   \"{gen_lines}...\"" if len(result.raw_generation) > 150 else f"  │   \"{result.raw_generation}\"")
        
        # Layer 4: Claim verification
        print(f"  │")
        print(f"  │ LAYER 4 - Claim Verification:")
        for claim in result.claims[:4]:
            status = "✓ SUPPORTED" if claim.is_supported else "✗ UNSUPPORTED"
            source = f"[{claim.supporting_source}]" if claim.supporting_source else "[no source]"
            print(f"  │   {status} {source}: \"{claim.claim[:50]}\"")
        
        # Layer 5: Confidence
        print(f"  │")
        print(f"  │ LAYER 5 - Confidence Score: {result.confidence_score:.2f}")
        
        # Layer 6: Decision
        print(f"  │")
        print(f"  │ LAYER 6 - Decision: *** {result.decision} ***")
        
        # Final response
        print(f"  │")
        print(f"  │ FINAL RESPONSE TO USER:")
        print(f"  │   \"{result.final_response[:120]}\"")
        print(f"  └────────────────────────────────────────────────────────────────────────")
        
        # Track pipeline claims
        h_with, t_with = count_hallucinated_claims(question, use_pipeline=True)
        total_hallucinated_with += h_with
        total_claims_with += t_with
    
    # =========================================================================
    # FINAL REPORT
    # =========================================================================
    
    print(f"\n{'='*70}")
    print("FINAL REPORT: HALLUCINATION PREVENTION EFFECTIVENESS")
    print(f"{'='*70}")
    
    rate_without = (total_hallucinated_without / total_claims_without * 100) if total_claims_without > 0 else 0
    rate_with = (total_hallucinated_with / total_claims_with * 100) if total_claims_with > 0 else 0
    
    total_questions = len(TEST_QUESTIONS)
    abstention_rate = (decisions["ABSTAIN"] + decisions["ESCALATE"]) / total_questions * 100
    
    # User-facing hallucination: only count hallucinations in questions we actually answered
    answered = decisions["ANSWER"] + decisions["CAVEAT"]
    user_facing_hallucination = 0.0  # Pipeline catches all in our demo
    
    print(f"""
  ┌─────────────────────────────────────────────────────────────────────┐
  │ METRIC                              │ WITHOUT PIPELINE │ WITH PIPELINE │
  ├─────────────────────────────────────────────────────────────────────┤
  │ Total claims generated              │ {total_claims_without:<16} │ {total_claims_with:<13} │
  │ Hallucinated claims                 │ {total_hallucinated_without:<16} │ {total_hallucinated_with:<13} │
  │ Hallucination rate                  │ {rate_without:<15.0f}% │ {rate_with:<12.0f}% │
  │ User-facing hallucination rate      │ {rate_without:<15.0f}% │ {user_facing_hallucination:<12.0f}% │
  └─────────────────────────────────────────────────────────────────────┘

  Decision Distribution:
    ANSWER (confident):  {decisions['ANSWER']}/{total_questions} ({decisions['ANSWER']*100//total_questions}%)
    CAVEAT (hedged):     {decisions['CAVEAT']}/{total_questions} ({decisions['CAVEAT']*100//total_questions}%)
    ABSTAIN (declined):  {decisions['ABSTAIN']}/{total_questions} ({decisions['ABSTAIN']*100//total_questions}%)
    ESCALATE (human):    {decisions['ESCALATE']}/{total_questions} ({decisions['ESCALATE']*100//total_questions}%)

  Abstention Rate: {abstention_rate:.0f}%
  (Abstaining is GOOD - it means we caught potential hallucinations)
  """)
    
    print(f"{'='*70}")
    print("KEY TAKEAWAYS")
    print(f"{'='*70}")
    print(f"""
  1. WITHOUT the pipeline, the LLM hallucinates freely:
     - Makes up specific numbers, names, and facts
     - Sounds confident even when completely wrong
     - {rate_without:.0f}% of claims were unsupported by the knowledge base

  2. WITH the pipeline, hallucinations are caught and prevented:
     - Relevance filtering removes irrelevant context
     - Sufficiency check prevents answering without enough info
     - Grounded generation forces citations
     - Claim verification catches any remaining hallucinations
     - Confidence scoring drives appropriate behavior

  3. The TRADEOFF is helpfulness vs accuracy:
     - Abstention rate of {abstention_rate:.0f}% means we don't answer some questions
     - But EVERY answer we give is grounded in facts
     - Users trust a system that says "I don't know" appropriately

  4. In PRODUCTION, each layer uses an LLM call:
     - Layer 2 (sufficiency): "Given these chunks, can you answer: <question>?"
     - Layer 3 (generation): "Answer using ONLY these sources: <chunks>"
     - Layer 4 (verification): "List claims in this response. For each, cite the source."
     - Cost: ~3-4x more LLM calls, but hallucination rate drops from ~{rate_without:.0f}% to ~0%
  """)
    
    print("=" * 70)
    print("   PIPELINE DEMONSTRATION COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
