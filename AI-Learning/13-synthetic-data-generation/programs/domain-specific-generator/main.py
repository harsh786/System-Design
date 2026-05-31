"""
Domain-Specific Generator
=========================
Generates synthetic data for 3 domains (Legal, Medical, Customer Support)
demonstrating how style, vocabulary, and constraints change per domain.
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("MODEL", "gpt-4")

# ─── Domain Configurations ─────────────────────────────────────────────────────

DOMAINS = {
    "legal": {
        "name": "Legal Research Assistant",
        "system_prompt": "You are a legal research assistant. You provide legal information but NEVER legal advice. Always include appropriate disclaimers.",
        "style": "Formal, precise, hedged with qualifications. Use legal terminology correctly.",
        "vocabulary": ["pursuant to", "notwithstanding", "hereinafter", "indemnification", "force majeure", "fiduciary duty", "statute of limitations", "precedent"],
        "constraints": [
            "ALWAYS include 'This is general legal information, not legal advice'",
            "NEVER guarantee legal outcomes",
            "Reference jurisdiction differences when relevant",
            "Use precise legal terminology",
            "Cite relevant areas of law (not specific cases unless certain)"
        ],
        "categories": [
            "contract interpretation",
            "employment law",
            "intellectual property",
            "liability and risk",
            "regulatory compliance"
        ],
        "generation_prompt": """Generate {n} realistic legal research queries with appropriate AI responses.

System role: {system_prompt}
Style: {style}
Required vocabulary (use naturally): {vocabulary}

Constraints ALL responses must follow:
{constraints}

Categories to cover: {categories}

Each example must include:
- A realistic query from a user (could be lawyer OR business owner)
- An appropriate response that follows ALL constraints
- Domain-specific quality indicators

Return JSON array:
[{{"query": "...", "response": "...", "category": "...", "complexity": "basic|intermediate|advanced"}}]
"""
    },
    "medical": {
        "name": "Health Information Assistant",
        "system_prompt": "You are a health information assistant. You provide general health education but NEVER diagnose or prescribe. Always recommend consulting a healthcare provider.",
        "style": "Clinical but accessible. Use medical terms with lay explanations. Evidence-based.",
        "vocabulary": ["differential", "etiology", "prognosis", "contraindication", "prophylaxis", "comorbidity", "sequelae", "pathophysiology"],
        "constraints": [
            "NEVER provide a definitive diagnosis",
            "ALWAYS recommend professional medical consultation",
            "Include red flag symptoms that warrant emergency care",
            "Distinguish between evidence-based info and general guidance",
            "NEVER recommend specific medications or dosages"
        ],
        "categories": [
            "symptom inquiry",
            "medication questions",
            "preventive health",
            "chronic disease management",
            "caregiver questions"
        ],
        "generation_prompt": """Generate {n} realistic health information queries with appropriate AI responses.

System role: {system_prompt}
Style: {style}
Medical vocabulary (use naturally with explanations): {vocabulary}

Constraints ALL responses must follow:
{constraints}

Categories to cover: {categories}

Vary the users: patients, caregivers, people asking for family members.
Vary urgency: routine questions to concerning symptoms.

Return JSON array:
[{{"query": "...", "response": "...", "category": "...", "urgency": "routine|concerning|urgent"}}]
"""
    },
    "customer_support": {
        "name": "Customer Support Agent",
        "system_prompt": "You are a customer support agent for a cloud storage service. Be empathetic, solution-oriented, and always offer specific next steps.",
        "style": "Warm, professional, concise. Acknowledge emotions. Action-oriented.",
        "vocabulary": ["escalate", "resolution", "SLA", "downtime", "migration", "retention", "churn prevention", "CSAT"],
        "constraints": [
            "ALWAYS acknowledge the customer's frustration/situation first",
            "Provide 2-3 specific resolution options",
            "NEVER blame the customer",
            "Set clear expectations on timelines",
            "Offer escalation path when appropriate"
        ],
        "categories": [
            "billing dispute",
            "technical outage",
            "data loss concern",
            "account access",
            "plan upgrade/downgrade"
        ],
        "generation_prompt": """Generate {n} realistic customer support interactions for a cloud storage service.

System role: {system_prompt}
Style: {style}

Constraints ALL responses must follow:
{constraints}

Categories to cover: {categories}

Vary customer emotions: calm, frustrated, angry, panicked, confused.
Include both simple and complex multi-step issues.

Return JSON array:
[{{"query": "...", "response": "...", "category": "...", "customer_emotion": "calm|frustrated|angry|panicked|confused"}}]
"""
    }
}

# ─── Generation ────────────────────────────────────────────────────────────────

def generate_domain_data(domain_key: str, n: int = 20) -> list:
    """Generate examples for a specific domain."""
    
    domain = DOMAINS[domain_key]
    
    prompt = domain["generation_prompt"].format(
        n=n,
        system_prompt=domain["system_prompt"],
        style=domain["style"],
        vocabulary=", ".join(domain["vocabulary"]),
        constraints="\n".join(f"  - {c}" for c in domain["constraints"]),
        categories=", ".join(domain["categories"])
    )
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        response_format={"type": "json_object"}
    )
    
    try:
        result = json.loads(response.choices[0].message.content)
        examples = result.get("examples", result.get("data", list(result.values())[0]))
        
        # Enrich with domain metadata
        for i, ex in enumerate(examples):
            ex["id"] = f"{domain_key}-{i+1:03d}"
            ex["domain"] = domain_key
        
        return examples
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  Error: {e}")
        return []


def validate_domain_constraints(example: dict, domain_key: str) -> dict:
    """Check if an example follows domain-specific constraints."""
    
    domain = DOMAINS[domain_key]
    response_text = example.get("response", "")
    violations = []
    
    if domain_key == "legal":
        # Must have disclaimer
        disclaimer_patterns = ["not legal advice", "general information", "consult an attorney", "seek legal counsel"]
        if not any(p in response_text.lower() for p in disclaimer_patterns):
            violations.append("missing_disclaimer")
    
    elif domain_key == "medical":
        # Must recommend professional consultation
        consultation_patterns = ["healthcare provider", "doctor", "medical professional", "physician", "consult"]
        if not any(p in response_text.lower() for p in consultation_patterns):
            violations.append("missing_consultation_recommendation")
        # Must not diagnose
        diagnosis_patterns = ["you have", "you are suffering from", "this is definitely"]
        if any(p in response_text.lower() for p in diagnosis_patterns):
            violations.append("appears_to_diagnose")
    
    elif domain_key == "customer_support":
        # Must have resolution steps
        if not any(c in response_text for c in ["1)", "1.", "First", "Option"]):
            violations.append("missing_resolution_steps")
    
    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "constraint_score": 1.0 - (len(violations) * 0.3)
    }


def score_domain_authenticity(example: dict, domain_key: str) -> dict:
    """Score how authentic the example feels for the domain."""
    
    domain = DOMAINS[domain_key]
    response_text = example.get("response", "")
    
    # Check vocabulary usage
    vocab_used = sum(1 for v in domain["vocabulary"] if v.lower() in response_text.lower())
    vocab_score = min(vocab_used / 3, 1.0)  # Using 3+ domain terms = max score
    
    # Check length (domain-appropriate)
    word_count = len(response_text.split())
    length_score = 1.0 if 30 < word_count < 300 else 0.5
    
    # Constraint validation
    validation = validate_domain_constraints(example, domain_key)
    
    overall = (vocab_score * 0.3 + length_score * 0.2 + validation["constraint_score"] * 0.5)
    
    return {
        "vocabulary_score": vocab_score,
        "length_score": length_score,
        "constraint_score": validation["constraint_score"],
        "constraint_violations": validation["violations"],
        "overall_authenticity": overall
    }


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DOMAIN-SPECIFIC GENERATOR")
    print("=" * 60)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    all_results = {}
    domain_report = {}
    
    for domain_key in DOMAINS:
        domain = DOMAINS[domain_key]
        print(f"\n{'─' * 40}")
        print(f"  Domain: {domain['name']}")
        print(f"  Style: {domain['style'][:60]}...")
        print(f"{'─' * 40}")
        
        # Generate
        print(f"  Generating 20 examples...")
        examples = generate_domain_data(domain_key, n=20)
        print(f"  Generated {len(examples)} examples")
        
        # Validate and score
        print(f"  Validating domain constraints...")
        for ex in examples:
            ex["scores"] = score_domain_authenticity(ex, domain_key)
        
        # Stats
        scores = [ex["scores"]["overall_authenticity"] for ex in examples]
        violations = sum(1 for ex in examples if ex["scores"]["constraint_violations"])
        
        domain_report[domain_key] = {
            "generated": len(examples),
            "avg_authenticity": float(np.mean(scores)) if scores else 0,
            "constraint_violations": violations,
            "pass_rate": (len(examples) - violations) / len(examples) if examples else 0
        }
        
        print(f"  Avg authenticity: {domain_report[domain_key]['avg_authenticity']:.2f}")
        print(f"  Constraint violations: {violations}/{len(examples)}")
        
        # Save domain data
        output_file = output_dir / f"{domain_key}_data.json"
        with open(output_file, "w") as f:
            json.dump(examples, f, indent=2)
        print(f"  Saved to {output_file}")
        
        all_results[domain_key] = examples
        time.sleep(1)
    
    # Save report
    report_file = output_dir / "domain_report.json"
    with open(report_file, "w") as f:
        json.dump(domain_report, f, indent=2, default=str)
    
    # Final summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"{'=' * 60}")
    for domain_key, stats in domain_report.items():
        print(f"  {domain_key:20s} | {stats['generated']:3d} examples | "
              f"authenticity: {stats['avg_authenticity']:.2f} | "
              f"pass rate: {stats['pass_rate']:.0%}")
    print(f"{'=' * 60}")


# numpy import for mean calculation
try:
    import numpy as np
except ImportError:
    class np:
        @staticmethod
        def mean(x):
            return sum(x) / len(x) if x else 0


if __name__ == "__main__":
    main()
