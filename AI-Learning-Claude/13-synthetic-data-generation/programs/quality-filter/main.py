"""
Quality Filter
==============
Multi-stage filtering pipeline for synthetic data:
Rule-based → LLM Judge → Deduplication → Diversity Check
"""

import json
import os
import re
import time
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
JUDGE_MODEL = os.getenv("MODEL_JUDGE", "gpt-4")
QUALITY_THRESHOLD = int(os.getenv("QUALITY_THRESHOLD", "4"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))

# ─── Sample Input Data (simulating raw synthetic output) ───────────────────────

def generate_sample_input(n=100):
    """Generate sample synthetic data with intentional quality variance."""
    
    # Mix of good and bad examples to demonstrate filtering
    examples = [
        # Good examples
        {"id": i, "instruction": f"Customer asks about feature #{i} and how to configure it",
         "response": f"I'd be happy to help you configure feature #{i}. Here's what you need to do: First, navigate to Settings > Features. Then enable the feature toggle. Finally, configure the parameters according to your needs. Let me know if you have questions about any specific step!"}
        for i in range(1, 71)
    ] + [
        # Too short (should be filtered)
        {"id": i, "instruction": "Help me", "response": "OK."}
        for i in range(71, 81)
    ] + [
        # Refusal patterns (should be filtered)
        {"id": i, "instruction": f"Question about topic {i}",
         "response": "I'm sorry, but as an AI language model, I cannot provide specific advice on this matter."}
        for i in range(81, 88)
    ] + [
        # Near-duplicates (should be deduplicated)
        {"id": 88, "instruction": "How do I reset my password?",
         "response": "To reset your password, go to Settings > Security > Change Password. Enter your current password, then your new password twice. Click Save."},
        {"id": 89, "instruction": "How can I change my password?",
         "response": "To change your password, navigate to Settings > Security > Change Password. Type your current password, then enter your new password twice. Click Save."},
        {"id": 90, "instruction": "I need to update my password",
         "response": "To update your password, go to Settings > Security > Change Password. Input your current password, then your new password twice. Click Save."},
    ] + [
        # Contains PII patterns (should be filtered)
        {"id": i, "instruction": f"Customer with SSN 123-45-{i:04d} needs help",
         "response": f"I can see your account. Let me help you with that issue."}
        for i in range(91, 96)
    ] + [
        # Good but varied
        {"id": 96, "instruction": "I'm furious! Your app crashed and I lost 2 hours of work!",
         "response": "I completely understand your frustration — losing work is incredibly disruptive. I'm sorry this happened. Let me help: 1) Check if autosave captured your work (Settings > Recovery), 2) I'll escalate this crash to our engineering team with your session ID, 3) I can extend your trial by a week for the inconvenience. Which would you like to start with?"},
        {"id": 97, "instruction": "Can I integrate with Salesforce?",
         "response": "Great question! We don't have a native Salesforce integration yet, but there are two options: 1) Use our Zapier connector to sync data between ProjectFlow and Salesforce, 2) Use our REST API to build a custom integration. Many Enterprise customers use option 2 for real-time sync. Would you like documentation for either approach?"},
        {"id": 98, "instruction": "What happens to my data if I cancel?",
         "response": "If you cancel your subscription: Your data remains accessible in read-only mode for 30 days. During that time, you can export everything (Projects > Export All). After 30 days, data is permanently deleted from our servers. Backups are purged after 90 days per our retention policy. I'd recommend exporting before canceling. Want me to walk you through the export process?"},
        {"id": 99, "instruction": "Is there a way to set up recurring tasks?",
         "response": "Yes! Recurring tasks are available on Pro and Enterprise plans. To set one up: Open any task > Click the repeat icon (↻) > Choose frequency (daily, weekly, monthly, custom). You can set an end date or let it repeat indefinitely. The new instance is created when the previous one is marked complete. Need help with a specific recurrence pattern?"},
        {"id": 100, "instruction": "My team member can't see the project I shared with them",
         "response": "Let's troubleshoot this access issue. A few things to check: 1) Is the team member on the correct workspace? (They may have multiple accounts), 2) What role did you assign? Viewers can't see draft projects, 3) Did they accept the workspace invitation email? You can verify their status in Settings > Team. If they show as 'pending', resend the invite. Would you like me to check anything specific?"},
    ]
    
    return examples


# ─── Filter Stages ─────────────────────────────────────────────────────────────

def rule_based_filter(example: dict) -> tuple[bool, list[str]]:
    """Stage 1: Fast rule-based checks."""
    reasons = []
    
    instruction = example.get("instruction", "")
    response = example.get("response", "")
    
    # Length checks
    if len(response.split()) < 10:
        reasons.append("too_short")
    if len(response.split()) > 800:
        reasons.append("too_long")
    if len(instruction.split()) < 3:
        reasons.append("instruction_too_short")
    
    # Refusal patterns
    refusal_patterns = [
        r"as an AI language model",
        r"I cannot provide",
        r"I'm not able to help with that",
    ]
    for pattern in refusal_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            reasons.append("refusal_pattern")
            break
    
    # PII patterns
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', instruction + response):
        reasons.append("contains_pii_ssn")
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response):
        reasons.append("contains_email_in_response")
    
    # Empty or whitespace
    if not response.strip():
        reasons.append("empty_response")
    
    return len(reasons) == 0, reasons


def llm_judge_score(example: dict) -> dict:
    """Stage 2: LLM quality scoring."""
    
    prompt = f"""Rate this customer support training example (1-5):

Instruction: {example['instruction']}
Response: {example['response']}

Criteria:
- Correctness: Is the response appropriate?
- Helpfulness: Does it solve the problem?
- Tone: Professional and empathetic?
- Completeness: Addresses the full query?

Return JSON: {{"overall": N, "reasoning": "brief"}}
1=terrible, 2=poor, 3=acceptable, 4=good, 5=excellent"""

    try:
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"overall": 3, "reasoning": "scoring_error"}


def deduplicate_examples(examples: list) -> tuple[list, list]:
    """Stage 3: Embedding-based deduplication."""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        texts = [e["instruction"] + " " + e["response"] for e in examples]
        embeddings = model.encode(texts)
        
        keep_indices = [0]
        removed = []
        
        for i in range(1, len(examples)):
            is_dup = False
            for j in keep_indices:
                sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                if sim > SIMILARITY_THRESHOLD:
                    is_dup = True
                    removed.append({"id": examples[i]["id"], "duplicate_of": examples[j]["id"], "similarity": float(sim)})
                    break
            if not is_dup:
                keep_indices.append(i)
        
        return [examples[i] for i in keep_indices], removed
    except ImportError:
        print("  (sentence-transformers not installed, skipping dedup)")
        return examples, []


def diversity_check(examples: list) -> dict:
    """Stage 4: Check topic diversity."""
    # Simple heuristic: check instruction uniqueness
    instructions = [e["instruction"].lower() for e in examples]
    unique_starts = len(set(i[:30] for i in instructions))
    diversity_score = unique_starts / len(examples) if examples else 0
    
    return {
        "diversity_score": diversity_score,
        "unique_starts": unique_starts,
        "total": len(examples),
        "assessment": "good" if diversity_score > 0.8 else "needs_improvement"
    }


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  QUALITY FILTER PIPELINE")
    print("=" * 60)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Load input
    examples = generate_sample_input(100)
    print(f"\n  Input: {len(examples)} examples")
    
    all_rejections = []
    
    # Stage 1: Rule-based filtering
    print(f"\n[Stage 1] Rule-based filtering...")
    passed_rules = []
    for ex in examples:
        passed, reasons = rule_based_filter(ex)
        if passed:
            passed_rules.append(ex)
        else:
            all_rejections.append({"id": ex["id"], "stage": "rule_based", "reasons": reasons})
    print(f"  {len(examples)} → {len(passed_rules)} (rejected {len(examples) - len(passed_rules)})")
    
    # Stage 2: LLM Quality Scoring
    print(f"\n[Stage 2] LLM quality scoring...")
    passed_quality = []
    for i, ex in enumerate(passed_rules):
        score = llm_judge_score(ex)
        ex["quality_score"] = score.get("overall", 3)
        if ex["quality_score"] >= QUALITY_THRESHOLD:
            passed_quality.append(ex)
        else:
            all_rejections.append({"id": ex["id"], "stage": "llm_judge", "score": ex["quality_score"], "reasoning": score.get("reasoning", "")})
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(passed_rules)}")
        time.sleep(0.3)
    print(f"  {len(passed_rules)} → {len(passed_quality)} (rejected {len(passed_rules) - len(passed_quality)})")
    
    # Stage 3: Deduplication
    print(f"\n[Stage 3] Deduplication...")
    passed_dedup, dup_removed = deduplicate_examples(passed_quality)
    for dup in dup_removed:
        all_rejections.append({"id": dup["id"], "stage": "deduplication", "duplicate_of": dup["duplicate_of"], "similarity": dup["similarity"]})
    print(f"  {len(passed_quality)} → {len(passed_dedup)} (removed {len(dup_removed)} duplicates)")
    
    # Stage 4: Diversity check
    print(f"\n[Stage 4] Diversity analysis...")
    diversity = diversity_check(passed_dedup)
    print(f"  Diversity score: {diversity['diversity_score']:.2f} ({diversity['assessment']})")
    
    # Generate report
    rejection_reasons = Counter([r["stage"] for r in all_rejections])
    
    report = {
        "input_count": len(examples),
        "output_count": len(passed_dedup),
        "acceptance_rate": len(passed_dedup) / len(examples),
        "rejection_by_stage": dict(rejection_reasons),
        "diversity": diversity,
        "quality_distribution": {
            "5_stars": sum(1 for e in passed_dedup if e.get("quality_score") == 5),
            "4_stars": sum(1 for e in passed_dedup if e.get("quality_score") == 4),
        },
        "avg_quality": np.mean([e.get("quality_score", 0) for e in passed_dedup]) if passed_dedup else 0,
    }
    
    # Save outputs
    with open(output_dir / "filtered_data.json", "w") as f:
        json.dump(passed_dedup, f, indent=2)
    
    with open(output_dir / "rejected_data.json", "w") as f:
        json.dump(all_rejections, f, indent=2)
    
    with open(output_dir / "filter_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  FILTERING REPORT")
    print(f"{'=' * 60}")
    print(f"  Input:            {report['input_count']} examples")
    print(f"  Output:           {report['output_count']} examples")
    print(f"  Acceptance rate:  {report['acceptance_rate']:.0%}")
    print(f"  Rejected by stage:")
    for stage, count in rejection_reasons.items():
        print(f"    - {stage}: {count}")
    print(f"  Avg quality:      {report['avg_quality']:.1f}/5")
    print(f"  Diversity:        {diversity['diversity_score']:.2f}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
