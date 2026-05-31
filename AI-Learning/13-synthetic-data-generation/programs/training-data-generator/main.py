"""
Training Data Generator
=======================
Generates instruction-response pairs for fine-tuning from seed examples.
Demonstrates: seed-based generation, persona diversity, LLM judging, deduplication.
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("MODEL_GENERATE", "gpt-4")
JUDGE_MODEL = os.getenv("MODEL_JUDGE", "gpt-4")

# ─── Configuration ─────────────────────────────────────────────────────────────

DOMAIN_DESCRIPTION = """
Customer support agent for a SaaS project management tool.
Handles: billing, technical issues, feature questions, account management.
Tone: Professional, empathetic, action-oriented.
"""

SEED_EXAMPLES = [
    {
        "instruction": "Customer says they were charged twice for their monthly subscription",
        "response": "I'm sorry about the duplicate charge — that's definitely not right. I can see the double billing on your account. I've initiated a refund for the extra charge, which should appear in 3-5 business days. I've also flagged your account to prevent this from recurring. Is there anything else I can help with?"
    },
    {
        "instruction": "Customer can't figure out how to invite team members to their workspace",
        "response": "Happy to help you add team members! Here's how: Go to Settings → Team → Invite Members. Enter their email addresses (you can add multiple at once), select their role (Admin, Editor, or Viewer), and click Send Invites. They'll get an email with a link to join. Note: your current plan allows up to 10 members. Would you like me to walk you through the roles?"
    },
    {
        "instruction": "Customer is angry that a feature they relied on was removed in the latest update",
        "response": "I completely understand your frustration — having a workflow disrupted is really inconvenient. The feature was consolidated into our new Automation Hub, which actually offers more flexibility. Let me show you how to recreate your workflow there: [steps]. If the new approach doesn't work for your use case, I can escalate this to our product team with your specific scenario. Would either of those help?"
    }
]

SYSTEM_PROMPT = "You are a helpful customer support agent for ProjectFlow, a SaaS project management tool."

N_TO_GENERATE = 50

# ─── Personas for Diversity ────────────────────────────────────────────────────

PERSONAS = [
    "a frustrated enterprise admin who expects immediate resolution",
    "a confused new user who just signed up today",
    "a technical power user who provides error codes and logs",
    "a non-native English speaker with grammatically imperfect messages",
    "a polite but impatient manager on a deadline",
]

# ─── Generation ────────────────────────────────────────────────────────────────

def generate_instructions(seeds: list, n: int) -> list[str]:
    """Generate diverse instructions inspired by seeds."""
    
    seed_text = "\n".join([f"- {s['instruction']}" for s in seeds])
    
    all_instructions = []
    per_persona = n // len(PERSONAS) + 1
    
    for persona in PERSONAS:
        prompt = f"""You are generating training data for a customer support AI.

Domain: {DOMAIN_DESCRIPTION}

Here are example customer situations:
{seed_text}

Generate {per_persona} NEW and DIFFERENT customer situations/queries.
Write them as if coming from {persona}.

Rules:
- Each must be a DIFFERENT topic/issue (don't repeat)
- Vary complexity: some simple, some multi-step
- Include the customer's tone/emotion in the description
- Cover: billing, technical, features, account, integrations, complaints

Return as a JSON array of strings."""

        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            response_format={"type": "json_object"}
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            instructions = result.get("instructions", result.get("queries", list(result.values())[0]))
            all_instructions.extend(instructions[:per_persona])
        except (json.JSONDecodeError, KeyError):
            print(f"  Warning: Failed to parse generation for persona: {persona}")
    
    return all_instructions[:n]


def generate_response(instruction: str) -> str:
    """Generate an ideal response for a given instruction."""
    
    prompt = f"""Given this customer situation for a SaaS project management tool:
"{instruction}"

Write the IDEAL support response following these rules:
- Acknowledge the customer's situation/emotion first
- Provide a clear explanation or solution
- Offer 2-3 specific next steps or options
- Keep it concise (3-6 sentences)
- Never blame the customer
- Be professional but warm

Return ONLY the response text, nothing else."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    return response.choices[0].message.content.strip()


def score_example(instruction: str, response: str) -> dict:
    """Use LLM-as-judge to score quality."""
    
    prompt = f"""Rate this customer support training example on a 1-5 scale.

Domain: SaaS project management tool support
Instruction: {instruction}
Response: {response}

Score:
- correctness (1-5): Is the response appropriate and accurate?
- helpfulness (1-5): Does it resolve the customer's issue?
- tone (1-5): Is the tone empathetic and professional?
- overall (1-5): Overall quality for training

Return JSON: {{"correctness": N, "helpfulness": N, "tone": N, "overall": N, "reasoning": "brief note"}}"""

    response_obj = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    
    try:
        return json.loads(response_obj.choices[0].message.content)
    except json.JSONDecodeError:
        return {"correctness": 3, "helpfulness": 3, "tone": 3, "overall": 3, "reasoning": "parse_error"}


def deduplicate(examples: list, threshold: float = 0.92) -> list:
    """Remove near-duplicate examples using embedding similarity."""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        texts = [e["instruction"] + " " + e["response"] for e in examples]
        embeddings = model.encode(texts)
        
        keep = [0]
        for i in range(1, len(examples)):
            is_dup = False
            for j in keep:
                sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                if sim > threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep.append(i)
        
        print(f"  Deduplication: {len(examples)} → {len(keep)} (removed {len(examples)-len(keep)} duplicates)")
        return [examples[i] for i in keep]
    except ImportError:
        print("  Skipping deduplication (sentence-transformers not installed)")
        return examples


def format_for_finetuning(examples: list) -> list[dict]:
    """Convert to OpenAI fine-tuning JSONL format."""
    formatted = []
    for ex in examples:
        formatted.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ex["instruction"]},
                {"role": "assistant", "content": ex["response"]}
            ]
        })
    return formatted


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  TRAINING DATA GENERATOR")
    print("=" * 60)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Step 1: Generate diverse instructions
    print(f"\n[1/5] Generating {N_TO_GENERATE} diverse instructions...")
    instructions = generate_instructions(SEED_EXAMPLES, N_TO_GENERATE)
    print(f"  Generated {len(instructions)} instructions")
    
    # Step 2: Generate responses
    print(f"\n[2/5] Generating responses...")
    examples = []
    for i, instruction in enumerate(instructions):
        response = generate_response(instruction)
        examples.append({"instruction": instruction, "response": response})
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(instructions)}")
        time.sleep(0.5)  # Rate limiting
    
    # Step 3: Quality scoring
    print(f"\n[3/5] Scoring quality...")
    scored = []
    for i, ex in enumerate(examples):
        score = score_example(ex["instruction"], ex["response"])
        ex["scores"] = score
        scored.append(ex)
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(examples)}")
        time.sleep(0.5)
    
    # Step 4: Filter by quality
    print(f"\n[4/5] Filtering...")
    quality_threshold = 4
    passed = [ex for ex in scored if ex["scores"].get("overall", 0) >= quality_threshold]
    rejected = [ex for ex in scored if ex["scores"].get("overall", 0) < quality_threshold]
    print(f"  Quality filter: {len(scored)} → {len(passed)} (rejected {len(rejected)})")
    
    # Deduplication
    passed = deduplicate(passed)
    
    # Step 5: Format and save
    print(f"\n[5/5] Formatting and saving...")
    formatted = format_for_finetuning(passed)
    
    # Save JSONL
    output_file = output_dir / "training_data.jsonl"
    with open(output_file, "w") as f:
        for item in formatted:
            f.write(json.dumps(item) + "\n")
    print(f"  Saved {len(formatted)} examples to {output_file}")
    
    # Save report
    report = {
        "config": {
            "domain": DOMAIN_DESCRIPTION.strip(),
            "n_seeds": len(SEED_EXAMPLES),
            "n_requested": N_TO_GENERATE,
            "model": MODEL,
            "quality_threshold": quality_threshold
        },
        "results": {
            "generated": len(examples),
            "passed_quality": len(passed),
            "final_count": len(formatted),
            "acceptance_rate": len(formatted) / len(examples) if examples else 0,
            "avg_quality_score": np.mean([ex["scores"].get("overall", 0) for ex in passed]) if passed else 0
        },
        "sample_output": formatted[:3] if formatted else []
    }
    
    report_file = output_dir / "generation_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Report saved to {report_file}")
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"  Seeds: {len(SEED_EXAMPLES)} → Generated: {len(examples)} → Final: {len(formatted)}")
    print(f"  Acceptance rate: {report['results']['acceptance_rate']:.0%}")
    print(f"  Avg quality: {report['results']['avg_quality_score']:.1f}/5")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
