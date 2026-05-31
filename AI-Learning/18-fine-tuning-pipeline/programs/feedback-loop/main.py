# Production Feedback Loop Simulator
# Demonstrates: feedback collection, example extraction, quality filtering, flywheel

import json
import random
import re
import os
from datetime import datetime, timedelta
from collections import Counter

random.seed(42)


# =============================================================================
# SIMULATED PRODUCTION TRAFFIC
# =============================================================================

QUERIES = [
    ("How do I export my data?", "technical", "easy"),
    ("The integration with Salesforce keeps failing", "technical", "hard"),
    ("Can I get a refund?", "billing", "medium"),
    ("Your product is slower than competitor X", "complaints", "hard"),
    ("What's the API rate limit?", "technical", "easy"),
    ("I need to add 50 users to my team", "billing", "medium"),
    ("Dashboard shows wrong metrics since yesterday", "technical", "hard"),
    ("Do you support HIPAA compliance?", "general", "medium"),
    ("How do I set up webhooks?", "technical", "medium"),
    ("Cancel my subscription immediately", "billing", "medium"),
    ("The mobile app crashes on Android 14", "technical", "hard"),
    ("Can I get a demo of enterprise features?", "general", "easy"),
    ("My API key was exposed, need to rotate", "technical", "hard"),
    ("Why was I charged after canceling?", "billing", "hard"),
    ("Feature request: dark mode", "feature_request", "easy"),
    ("Integration with Slack stopped working after update", "technical", "hard"),
    ("What's included in the Pro plan?", "general", "easy"),
    ("Need to transfer ownership to another user", "technical", "medium"),
    ("Your support response times are terrible", "complaints", "medium"),
    ("How do I set up SSO with Okta?", "technical", "hard"),
]

def generate_model_response(query, category, difficulty, model_version=1):
    """Simulate model generating a response (quality varies by version)."""
    
    # Model improves with version (flywheel effect)
    quality_base = 0.7 + (model_version - 1) * 0.05
    difficulty_penalty = {"easy": 0, "medium": 0.1, "hard": 0.2}
    
    quality = quality_base - difficulty_penalty[difficulty] + random.gauss(0, 0.1)
    quality = max(0.3, min(1.0, quality))
    
    # Simulate response
    good_responses = {
        "technical": f"I understand you're experiencing an issue. Let me help you troubleshoot this. First, please try clearing your cache and restarting the application. If that doesn't work, I'll escalate to our engineering team.",
        "billing": f"I'd be happy to help with your billing question. Let me look into your account and provide the relevant information.",
        "complaints": f"I sincerely apologize for the frustration. I understand this impacts your work, and I want to make it right. Here's what I can do for you.",
        "general": f"Great question! Here's the information you need about our product.",
        "feature_request": f"Thank you for the suggestion! I've logged this with our product team. We prioritize features based on user demand.",
    }
    
    poor_responses = {
        "technical": f"Have you tried turning it off and on again?",
        "billing": f"Please check our FAQ for billing information.",
        "complaints": f"I'm sorry you feel that way. Is there anything else I can help with?",
        "general": f"You can find that information on our website.",
        "feature_request": f"Thanks for the feedback.",
    }
    
    if quality > 0.7:
        response = good_responses[category]
    elif quality > 0.4:
        response = f"{good_responses[category][:50]}... Let me look into this further for you."
    else:
        response = poor_responses[category]
    
    return response, quality


def simulate_user_feedback(query, response, quality):
    """Simulate user feedback based on response quality."""
    
    feedback = {
        "thumbs_up": False,
        "thumbs_down": False,
        "user_edit": None,
        "regenerated": False,
        "copied": False,
        "session_continued": False,
    }
    
    # Higher quality → more positive feedback
    if quality > 0.8:
        feedback["thumbs_up"] = random.random() < 0.6
        feedback["copied"] = random.random() < 0.4
        feedback["session_continued"] = random.random() < 0.7
    elif quality > 0.6:
        feedback["thumbs_up"] = random.random() < 0.3
        feedback["session_continued"] = random.random() < 0.5
        feedback["regenerated"] = random.random() < 0.2
    elif quality > 0.4:
        feedback["thumbs_down"] = random.random() < 0.3
        feedback["regenerated"] = random.random() < 0.4
        # Sometimes user provides a correction
        if random.random() < 0.2:
            feedback["user_edit"] = f"[CORRECTED] A better response would address the specific issue: {query}. The correct approach is to provide step-by-step troubleshooting tailored to their exact situation, including relevant links and escalation paths."
    else:
        feedback["thumbs_down"] = random.random() < 0.6
        feedback["regenerated"] = random.random() < 0.5
        if random.random() < 0.35:
            feedback["user_edit"] = f"[CORRECTED] The response should empathize with the user's situation regarding '{query}', provide concrete next steps, and offer to escalate if needed. Include specific timelines and follow-up commitments."
    
    return feedback


# =============================================================================
# PRODUCTION LOG SIMULATION
# =============================================================================

def generate_production_logs(n=100, model_version=1):
    """Generate N simulated production interactions."""
    logs = []
    base_time = datetime(2024, 6, 1, 9, 0, 0)
    
    for i in range(n):
        query, category, difficulty = random.choice(QUERIES)
        response, quality = generate_model_response(query, category, difficulty, model_version)
        feedback = simulate_user_feedback(query, response, quality)
        
        log = {
            "id": f"prod_{i:04d}",
            "timestamp": (base_time + timedelta(minutes=random.randint(0, 43200))).isoformat(),
            "query": query,
            "response": response,
            "category": category,
            "difficulty": difficulty,
            "model_confidence": quality + random.gauss(0, 0.05),
            "feedback": feedback,
            "model_version": model_version,
        }
        logs.append(log)
    
    return logs


# =============================================================================
# TRAINING EXAMPLE EXTRACTION
# =============================================================================

def extract_training_examples(logs):
    """Extract high-value training examples from production logs."""
    
    examples = []
    extraction_stats = Counter()
    
    for log in logs:
        feedback = log["feedback"]
        
        # Source 1: User corrections (HIGHEST VALUE)
        if feedback.get("user_edit"):
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful customer support agent. Be empathetic, specific, and action-oriented."},
                    {"role": "user", "content": log["query"]},
                    {"role": "assistant", "content": feedback["user_edit"]},
                ],
                "metadata": {
                    "source": "user_correction",
                    "value": "very_high",
                    "original_quality": log["model_confidence"],
                    "category": log["category"],
                },
            })
            extraction_stats["user_correction"] += 1
        
        # Source 2: High-confidence thumbs-up (verified good)
        elif feedback.get("thumbs_up") and log["model_confidence"] > 0.8:
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful customer support agent. Be empathetic, specific, and action-oriented."},
                    {"role": "user", "content": log["query"]},
                    {"role": "assistant", "content": log["response"]},
                ],
                "metadata": {
                    "source": "verified_positive",
                    "value": "high",
                    "original_quality": log["model_confidence"],
                    "category": log["category"],
                },
            })
            extraction_stats["verified_positive"] += 1
        
        # Source 3: Hard examples that succeeded (low confidence but thumbs-up)
        elif feedback.get("thumbs_up") and log["model_confidence"] < 0.6:
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful customer support agent. Be empathetic, specific, and action-oriented."},
                    {"role": "user", "content": log["query"]},
                    {"role": "assistant", "content": log["response"]},
                ],
                "metadata": {
                    "source": "hard_positive",
                    "value": "very_high",
                    "original_quality": log["model_confidence"],
                    "category": log["category"],
                },
            })
            extraction_stats["hard_positive"] += 1
        
        # Source 4: For DPO - thumbs down + later regeneration that was accepted
        elif feedback.get("thumbs_down") and feedback.get("regenerated"):
            # In a real system, you'd have the regenerated response too
            extraction_stats["dpo_candidate"] += 1
    
    return examples, extraction_stats


# =============================================================================
# QUALITY FILTERING
# =============================================================================

def filter_examples(examples):
    """Apply quality filters to extracted examples."""
    filtered = []
    filter_stats = Counter()
    
    for ex in examples:
        assistant_msg = ex["messages"][-1]["content"]
        
        # Filter: too short
        if len(assistant_msg) < 30:
            filter_stats["too_short"] += 1
            continue
        
        # Filter: contains PII patterns
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', assistant_msg):
            filter_stats["contains_pii"] += 1
            continue
        
        # Filter: low diversity (near-duplicate of existing)
        # Simplified: check if query is already in filtered set
        existing_queries = [f["messages"][1]["content"] for f in filtered]
        if ex["messages"][1]["content"] in existing_queries:
            filter_stats["duplicate"] += 1
            continue
        
        # Filter: suspiciously generic
        generic_phrases = ["I'm sorry you feel that way", "Please check our FAQ"]
        if any(phrase in assistant_msg for phrase in generic_phrases):
            filter_stats["too_generic"] += 1
            continue
        
        filtered.append(ex)
        filter_stats["passed"] += 1
    
    return filtered, filter_stats


# =============================================================================
# FLYWHEEL DEMONSTRATION
# =============================================================================

def demonstrate_flywheel():
    """Show how the flywheel effect improves over multiple cycles."""
    print(f"\n{'='*60}")
    print("  FLYWHEEL EFFECT: Multiple Improvement Cycles")
    print(f"{'='*60}")
    
    print(f"\n  Simulating 5 cycles of continuous improvement...\n")
    print(f"  {'Cycle':<8} {'Model':<12} {'Avg Quality':>12} {'Feedback+':>10} {'Feedback-':>10} {'New Examples':>13}")
    print(f"  {'─'*68}")
    
    cumulative_examples = 0
    for cycle in range(1, 6):
        logs = generate_production_logs(n=100, model_version=cycle)
        
        # Calculate metrics
        avg_quality = sum(log["model_confidence"] for log in logs) / len(logs)
        thumbs_up = sum(1 for log in logs if log["feedback"]["thumbs_up"])
        thumbs_down = sum(1 for log in logs if log["feedback"]["thumbs_down"])
        
        examples, _ = extract_training_examples(logs)
        filtered, _ = filter_examples(examples)
        cumulative_examples += len(filtered)
        
        quality_bar = "█" * int(avg_quality * 20)
        print(f"  {cycle:<8} v{cycle:<11} {avg_quality:>10.3f}   {thumbs_up:>8}   {thumbs_down:>8}   {len(filtered):>11}")
    
    print(f"\n  Total new training examples across 5 cycles: {cumulative_examples}")
    print(f"  Each cycle: better model → more positive feedback → higher quality examples")
    print(f"  This is the flywheel: improvement compounds over time.")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  PRODUCTION FEEDBACK LOOP SIMULATOR")
    print("=" * 60)
    
    # Generate production logs
    print(f"\n{'='*60}")
    print("  STEP 1: Simulating Production Traffic")
    print(f"{'='*60}")
    
    logs = generate_production_logs(n=100, model_version=1)
    print(f"  Generated {len(logs)} production interactions")
    
    # Feedback summary
    thumbs_up = sum(1 for log in logs if log["feedback"]["thumbs_up"])
    thumbs_down = sum(1 for log in logs if log["feedback"]["thumbs_down"])
    edits = sum(1 for log in logs if log["feedback"]["user_edit"])
    regenerated = sum(1 for log in logs if log["feedback"]["regenerated"])
    no_feedback = sum(1 for log in logs if not any([
        log["feedback"]["thumbs_up"], log["feedback"]["thumbs_down"],
        log["feedback"]["user_edit"], log["feedback"]["regenerated"]
    ]))
    
    print(f"\n  Feedback Distribution:")
    print(f"    👍 Thumbs up:    {thumbs_up:>3} ({thumbs_up}%)")
    print(f"    👎 Thumbs down:  {thumbs_down:>3} ({thumbs_down}%)")
    print(f"    ✏️  User edits:   {edits:>3} ({edits}%)")
    print(f"    🔄 Regenerated:  {regenerated:>3} ({regenerated}%)")
    print(f"    —  No feedback:  {no_feedback:>3} ({no_feedback}%)")
    
    # Extract training examples
    print(f"\n{'='*60}")
    print("  STEP 2: Extracting Training Examples")
    print(f"{'='*60}")
    
    examples, extraction_stats = extract_training_examples(logs)
    print(f"\n  Extraction Results:")
    for source, count in extraction_stats.most_common():
        value_label = {"user_correction": "VERY HIGH", "hard_positive": "VERY HIGH", 
                      "verified_positive": "HIGH", "dpo_candidate": "HIGH (for DPO)"}
        print(f"    {source:20s}: {count:>3} examples  (value: {value_label.get(source, 'medium')})")
    print(f"    {'─'*50}")
    print(f"    {'TOTAL extracted':20s}: {len(examples):>3} examples")
    
    # Filter
    print(f"\n{'='*60}")
    print("  STEP 3: Quality Filtering")
    print(f"{'='*60}")
    
    filtered, filter_stats = filter_examples(examples)
    print(f"\n  Filter Results:")
    for reason, count in filter_stats.most_common():
        status = "✓" if reason == "passed" else "✗"
        print(f"    {status} {reason:15s}: {count:>3}")
    print(f"\n  Final training examples: {len(filtered)}/{len(examples)} passed filters")
    
    # Show sample examples
    print(f"\n{'='*60}")
    print("  STEP 4: Sample Extracted Examples")
    print(f"{'='*60}")
    
    for i, ex in enumerate(filtered[:5]):
        meta = ex["metadata"]
        print(f"\n  Example {i+1} (source: {meta['source']}, value: {meta['value']}):")
        print(f"    Category: {meta['category']}")
        print(f"    User: {ex['messages'][1]['content'][:70]}...")
        print(f"    Assistant: {ex['messages'][2]['content'][:70]}...")
    
    # Save output
    print(f"\n{'='*60}")
    print("  STEP 5: Saving New Training Examples")
    print(f"{'='*60}")
    
    output_file = "new_training_examples.jsonl"
    with open(output_file, "w") as f:
        for ex in filtered:
            # Remove metadata for training file
            training_ex = {"messages": ex["messages"]}
            f.write(json.dumps(training_ex) + "\n")
    
    print(f"\n  Saved {len(filtered)} examples to {output_file}")
    print(f"  These should be reviewed by a domain expert before adding to training set.")
    
    # Value breakdown
    value_counts = Counter(ex["metadata"]["value"] for ex in filtered)
    print(f"\n  Value distribution of extracted examples:")
    for value, count in value_counts.most_common():
        bar = "█" * count
        print(f"    {value:12s}: {count:>3} {bar}")
    
    # Flywheel demonstration
    demonstrate_flywheel()
    
    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY & NEXT STEPS")
    print(f"{'='*60}")
    print(f"""
  From 100 production interactions:
    - Extracted {len(examples)} candidate training examples
    - After filtering: {len(filtered)} high-quality examples
    - Value: {value_counts.get('very_high', 0)} very high + {value_counts.get('high', 0)} high

  Recommended actions:
    1. Human review the {len(filtered)} examples (especially user corrections)
    2. Add approved examples to training dataset
    3. If dataset grew by >20%, trigger re-fine-tuning
    4. Evaluate new model vs current on held-out test set
    5. Deploy if better, continue collecting feedback

  At 100 interactions/day → ~{len(filtered)//2} usable examples/day → {len(filtered)//2 * 30} examples/month
  After 3 months: enough for a strong fine-tuning dataset!
""")


if __name__ == "__main__":
    main()
