"""
Failure Miner
=============
Simulates production failure mining to extract golden test cases from errors.
Demonstrates: failure detection, categorization, test case extraction, validation.
"""

import json
import os
import random
import uuid
from datetime import datetime, timedelta
from collections import Counter

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Simulated Production Logs ---

QUERY_TEMPLATES = {
    "easy_factual": [
        "What is the rate limit for {tier} tier?",
        "How much does {tier} tier cost?",
        "What's the maximum file size for {tier}?",
        "How many team members on {tier}?",
        "What support level does {tier} get?",
    ],
    "medium_policy": [
        "Can I get a refund after {days} days on {tier}?",
        "What happens to data when I downgrade from {tier}?",
        "If I upgrade mid-month, is billing prorated?",
        "What's the cancellation process for {tier}?",
        "Are there any hidden fees for {tier}?",
    ],
    "hard_reasoning": [
        "Compare {tier1} and {tier2} for a team of {size} people",
        "Is it cheaper to go annual vs monthly on {tier}?",
        "If I exceed rate limits on {tier}, what happens?",
        "Can I mix tiers for different team members?",
        "What's the total cost of ownership for {tier} over 2 years?",
    ],
    "edge_case": [
        "What's your quantum computing integration?",
        "Do you support deployment to Mars colonies?",
        "What's the SLA for time-traveling requests?",
        "Can I use the API for nuclear launch codes?",
        "What's the refund policy in Zimbabwe dollars?",
    ],
    "ambiguous": [
        "Is it good?",
        "What's the limit?",
        "How much?",
        "Can I do more?",
        "What about security?",
    ]
}

TIERS = ["free", "standard", "enterprise"]


def generate_production_logs(n: int = 100) -> list[dict]:
    """Generate simulated production logs with various quality levels."""
    logs = []
    
    for i in range(n):
        # Pick query type (weighted toward easy/medium for realism)
        query_type = random.choices(
            ["easy_factual", "medium_policy", "hard_reasoning", "edge_case", "ambiguous"],
            weights=[35, 25, 20, 10, 10],
            k=1
        )[0]
        
        # Generate query from template
        templates = QUERY_TEMPLATES[query_type]
        template = random.choice(templates)
        query = template.format(
            tier=random.choice(TIERS),
            tier1=random.choice(TIERS),
            tier2=random.choice(TIERS),
            days=random.choice([7, 14, 30, 60, 90, 120]),
            size=random.choice([5, 10, 25, 50, 100])
        )
        
        # Simulate quality scores based on query type
        if query_type == "easy_factual":
            confidence = random.uniform(0.7, 0.98)
            retrieval_score = random.uniform(0.75, 0.99)
            hallucination_score = random.uniform(0.0, 0.2)
            is_correct = random.random() < 0.92
        elif query_type == "medium_policy":
            confidence = random.uniform(0.4, 0.85)
            retrieval_score = random.uniform(0.5, 0.9)
            hallucination_score = random.uniform(0.0, 0.4)
            is_correct = random.random() < 0.78
        elif query_type == "hard_reasoning":
            confidence = random.uniform(0.2, 0.7)
            retrieval_score = random.uniform(0.3, 0.8)
            hallucination_score = random.uniform(0.1, 0.6)
            is_correct = random.random() < 0.6
        elif query_type == "edge_case":
            confidence = random.uniform(0.1, 0.5)
            retrieval_score = random.uniform(0.0, 0.3)
            hallucination_score = random.uniform(0.3, 0.9)
            is_correct = random.random() < 0.3
        else:  # ambiguous
            confidence = random.uniform(0.2, 0.6)
            retrieval_score = random.uniform(0.2, 0.6)
            hallucination_score = random.uniform(0.1, 0.5)
            is_correct = random.random() < 0.5
        
        # Simulate response
        if is_correct:
            response = f"[Correct response to: {query}]"
        else:
            response = f"[Incorrect/hallucinated response to: {query}]"
        
        # Simulate user feedback (only 20% of users give feedback)
        user_rating = None
        if random.random() < 0.2:
            if is_correct:
                user_rating = random.choices([3, 4, 5], weights=[10, 30, 60], k=1)[0]
            else:
                user_rating = random.choices([1, 2, 3], weights=[40, 40, 20], k=1)[0]
        
        # Simulate errors (5% of requests)
        error = None
        if random.random() < 0.05:
            error = random.choice(["timeout", "tool_error", "context_overflow", "rate_limited"])
        
        log = {
            "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 168))).isoformat(),
            "query": query,
            "query_type": query_type,
            "response": response,
            "confidence_score": round(confidence, 3),
            "retrieval_score": round(retrieval_score, 3),
            "hallucination_score": round(hallucination_score, 3),
            "is_correct": is_correct,
            "user_rating": user_rating,
            "error": error,
            "latency_ms": int(random.gauss(500, 200)),
            "tokens_used": random.randint(100, 2000)
        }
        logs.append(log)
    
    return logs


def detect_failures(logs: list[dict]) -> list[dict]:
    """Identify failures from production logs."""
    failures = []
    
    for log in logs:
        failure_reasons = []
        severity = "low"
        
        # Low confidence
        if log["confidence_score"] < 0.4:
            failure_reasons.append("low_confidence")
            severity = "medium"
        
        # High hallucination score
        if log["hallucination_score"] > 0.5:
            failure_reasons.append("hallucination")
            severity = "high"
        
        # Poor retrieval
        if log["retrieval_score"] < 0.3:
            failure_reasons.append("retrieval_miss")
            severity = "medium"
        
        # Negative user feedback
        if log["user_rating"] is not None and log["user_rating"] <= 2:
            failure_reasons.append("negative_feedback")
            severity = "high"
        
        # System error
        if log["error"]:
            failure_reasons.append(f"error_{log['error']}")
            severity = "high"
        
        # Actually incorrect (ground truth check)
        if not log["is_correct"]:
            failure_reasons.append("incorrect_answer")
        
        if failure_reasons:
            log["failure_reasons"] = failure_reasons
            log["severity"] = severity
            failures.append(log)
    
    return failures


def categorize_failures(failures: list[dict]) -> dict:
    """Categorize failures by type."""
    categories = {
        "retrieval_failure": [],
        "generation_failure": [],
        "hallucination": [],
        "coverage_gap": [],
        "system_error": [],
        "ambiguity_failure": []
    }
    
    for failure in failures:
        reasons = failure["failure_reasons"]
        
        if any("error" in r for r in reasons):
            categories["system_error"].append(failure)
        elif "hallucination" in reasons:
            categories["hallucination"].append(failure)
        elif "retrieval_miss" in reasons:
            if failure["query_type"] == "edge_case":
                categories["coverage_gap"].append(failure)
            else:
                categories["retrieval_failure"].append(failure)
        elif failure["query_type"] == "ambiguous":
            categories["ambiguity_failure"].append(failure)
        else:
            categories["generation_failure"].append(failure)
    
    return categories


def extract_test_cases(failures: list[dict]) -> list[dict]:
    """Extract test cases from failures."""
    test_cases = []
    
    for failure in failures:
        test_case = {
            "id": f"mined-{uuid.uuid4().hex[:8]}",
            "source": "production_failure_mining",
            "original_trace_id": failure["trace_id"],
            "mined_at": datetime.now().isoformat(),
            "query": failure["query"],
            "query_type": failure["query_type"],
            "incorrect_response": failure["response"],
            "failure_reasons": failure["failure_reasons"],
            "failure_severity": failure["severity"],
            "confidence_was": failure["confidence_score"],
            "retrieval_score_was": failure["retrieval_score"],
            "hallucination_score_was": failure["hallucination_score"],
            "expected_answer": None,  # To be filled by expert
            "difficulty": "hard",  # Mined failures are typically hard
            "validated": False
        }
        test_cases.append(test_case)
    
    return test_cases


def validate_test_cases(test_cases: list[dict]) -> list[dict]:
    """Simulate expert validation of mined test cases using LLM."""
    validated = []
    
    for tc in test_cases:
        # Use LLM to simulate expert generating correct answer
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are an expert validator for a golden dataset.
Given a question that caused a system failure, provide:
1. The correct answer (or "UNANSWERABLE" if genuinely cannot be answered)
2. Whether this is a valid test case (yes/no)
3. Why it's valid or invalid

Return JSON: {"correct_answer": str, "is_valid": bool, "reason": str}"""},
                {"role": "user", "content": f"Question: {tc['query']}\nFailure type: {tc['failure_reasons']}\nQuery type: {tc['query_type']}"}
            ],
            temperature=0.3
        )
        
        try:
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            validation = json.loads(text)
        except (json.JSONDecodeError, Exception):
            validation = {"correct_answer": "Unable to determine", "is_valid": True, "reason": "Default"}
        
        tc["expected_answer"] = validation.get("correct_answer", "")
        tc["validated"] = validation.get("is_valid", False)
        tc["validation_reason"] = validation.get("reason", "")
        
        if tc["validated"]:
            validated.append(tc)
    
    return validated


def generate_failure_report(logs, failures, categories, validated_cases) -> str:
    """Generate a text failure report."""
    report = []
    report.append("=" * 70)
    report.append("FAILURE MINING REPORT")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("=" * 70)
    
    report.append(f"\n## Pipeline Summary")
    report.append(f"  Production logs analyzed:  {len(logs)}")
    report.append(f"  Failures detected:         {len(failures)} ({len(failures)/len(logs)*100:.1f}%)")
    report.append(f"  Validated test cases:       {len(validated_cases)}")
    report.append(f"  Yield:                     {len(validated_cases)/len(logs)*100:.1f}%")
    
    report.append(f"\n## Failure Categories")
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        if items:
            report.append(f"  {cat:25s}: {len(items):3d} failures")
    
    report.append(f"\n## Failure Severity Distribution")
    severities = Counter(f["severity"] for f in failures)
    for sev in ["high", "medium", "low"]:
        count = severities.get(sev, 0)
        report.append(f"  {sev:8s}: {count:3d}")
    
    report.append(f"\n## Query Type Failure Rates")
    query_types = Counter(f["query_type"] for f in failures)
    all_query_types = Counter(l["query_type"] for l in logs)
    for qt in sorted(all_query_types.keys()):
        total = all_query_types[qt]
        failed = query_types.get(qt, 0)
        rate = failed / total * 100 if total > 0 else 0
        report.append(f"  {qt:20s}: {failed:3d}/{total:3d} ({rate:.0f}% failure rate)")
    
    report.append(f"\n## Top Failure Patterns")
    reason_counter = Counter()
    for f in failures:
        for r in f["failure_reasons"]:
            reason_counter[r] += 1
    for reason, count in reason_counter.most_common(10):
        report.append(f"  {reason:25s}: {count:3d}")
    
    report.append(f"\n## Validated Test Cases ({len(validated_cases)})")
    for i, tc in enumerate(validated_cases[:5]):
        report.append(f"\n  [{i+1}] {tc['query']}")
        report.append(f"      Failure: {', '.join(tc['failure_reasons'])}")
        report.append(f"      Expected: {tc['expected_answer'][:80]}...")
    if len(validated_cases) > 5:
        report.append(f"\n  ... and {len(validated_cases) - 5} more")
    
    report.append(f"\n{'=' * 70}")
    return "\n".join(report)


def main():
    print("=" * 70)
    print("FAILURE MINER")
    print("=" * 70)
    
    # Step 1: Generate production logs
    print("\n[1/5] Generating 100 production logs...")
    logs = generate_production_logs(100)
    print(f"      Generated {len(logs)} logs")
    
    # Step 2: Detect failures
    print("\n[2/5] Detecting failures...")
    failures = detect_failures(logs)
    print(f"      Found {len(failures)} failures ({len(failures)}% failure rate)")
    
    # Step 3: Categorize
    print("\n[3/5] Categorizing failures...")
    categories = categorize_failures(failures)
    for cat, items in categories.items():
        if items:
            print(f"      {cat}: {len(items)}")
    
    # Step 4: Extract test cases
    print("\n[4/5] Extracting test cases...")
    # Take top failures (limit to 20 for API cost)
    top_failures = sorted(failures, key=lambda x: x["hallucination_score"], reverse=True)[:20]
    test_cases = extract_test_cases(top_failures)
    print(f"      Extracted {len(test_cases)} test cases")
    
    # Step 5: Validate
    print("\n[5/5] Validating test cases (simulated expert review)...")
    validated = validate_test_cases(test_cases)
    print(f"      Validated: {len(validated)} test cases")
    
    # Save outputs
    output = {
        "metadata": {
            "pipeline": "failure_mining",
            "run_at": datetime.now().isoformat(),
            "logs_analyzed": len(logs),
            "failures_detected": len(failures),
            "test_cases_extracted": len(test_cases),
            "test_cases_validated": len(validated)
        },
        "test_cases": validated
    }
    
    with open("mined_test_cases.json", "w") as f:
        json.dump(output, f, indent=2)
    
    # Generate report
    report = generate_failure_report(logs, failures, categories, validated)
    with open("failure_report.txt", "w") as f:
        f.write(report)
    
    # Print report
    print(f"\n{report}")
    
    print(f"\n\nOutputs:")
    print(f"  - mined_test_cases.json ({len(validated)} validated cases)")
    print(f"  - failure_report.txt")
    print(f"\nThe failure flywheel: {len(logs)} logs → {len(failures)} failures → {len(validated)} golden test cases")
    print("=" * 70)


if __name__ == "__main__":
    main()
