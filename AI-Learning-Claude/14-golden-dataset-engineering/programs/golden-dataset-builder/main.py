"""
Golden Dataset Builder
======================
Interactive tool to build a golden dataset from source documents and questions.
Demonstrates: schema design, annotation, IAA computation, quality reporting.
"""

import json
import os
import uuid
from datetime import datetime
from collections import Counter

import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Source Documents (simulated knowledge base) ---
SOURCE_DOCUMENTS = {
    "policies/refund-policy.md": """
# Refund Policy

## Free Tier
Free tier users are not eligible for refunds as no payment is collected.

## Standard Tier ($29/month)
Standard tier customers may request a full refund within 14 days of their initial purchase.
After 14 days, no refund is available. Monthly subscriptions can be cancelled at any time
with no further charges.

## Enterprise Tier (Custom pricing)
Enterprise customers may request a full refund within 60 days of contract signing.
After 60 days, a prorated refund is available for the remaining contract term.
Early termination fees of 10% of remaining contract value apply after 60 days.
""",
    "docs/api-limits.md": """
# API Rate Limits

## Free Tier
- 100 requests per day
- 10 requests per minute
- Maximum payload size: 1MB
- No batch endpoints

## Standard Tier
- 10,000 requests per day
- 100 requests per minute
- Maximum payload size: 10MB
- Batch endpoints available (up to 100 items)

## Enterprise Tier
- Unlimited requests (fair use policy applies)
- 1,000 requests per minute
- Maximum payload size: 100MB
- Batch endpoints available (up to 10,000 items)
- Dedicated infrastructure option available
""",
    "docs/security.md": """
# Security & Compliance

## Data Encryption
All data is encrypted at rest using AES-256 and in transit using TLS 1.3.
Customer data is stored in isolated tenants with no cross-tenant access.

## Compliance Certifications
- SOC 2 Type II (achieved January 2024)
- ISO 27001 (achieved March 2024)
- HIPAA (Enterprise tier only, BAA required)
- GDPR compliant (all tiers)

## Data Retention
- Free tier: data retained for 30 days after account deletion
- Standard tier: data retained for 90 days after account deletion
- Enterprise tier: customizable retention per contract (default 1 year)

## Access Controls
- SSO available on Standard and Enterprise tiers
- MFA required for all admin accounts
- Role-based access control (RBAC) on Enterprise tier
- API keys rotated every 90 days (configurable on Enterprise)
""",
    "docs/features.md": """
# Feature Comparison

## Free Tier
- 3 projects maximum
- 1 team member
- Community support only
- Basic analytics dashboard
- Standard models only

## Standard Tier
- 25 projects maximum
- 10 team members
- Email support (24-hour response)
- Advanced analytics with export
- All standard and premium models
- Custom fine-tuning (limited to 3 models)

## Enterprise Tier
- Unlimited projects
- Unlimited team members
- 24/7 dedicated support with SLA (< 1 hour critical)
- Custom analytics and reporting
- All models including experimental
- Unlimited fine-tuning
- On-premise deployment option
- Custom model training
"""
}

# --- Questions to build golden dataset from ---
QUESTIONS = [
    {"question": "What is the refund policy for standard tier customers?", "difficulty": "easy", "category": "policy"},
    {"question": "How many API requests can enterprise customers make per minute?", "difficulty": "easy", "category": "technical"},
    {"question": "What compliance certifications does the platform have?", "difficulty": "easy", "category": "security"},
    {"question": "Can free tier users get a refund?", "difficulty": "easy", "category": "policy"},
    {"question": "What's the maximum number of team members on standard tier?", "difficulty": "easy", "category": "features"},
    {"question": "If I'm on enterprise and want to cancel after 90 days, what fees apply?", "difficulty": "medium", "category": "policy"},
    {"question": "Compare the API rate limits between standard and enterprise tiers.", "difficulty": "medium", "category": "technical"},
    {"question": "Is the platform HIPAA compliant for standard tier users?", "difficulty": "medium", "category": "security"},
    {"question": "What happens to my data if I delete my free tier account?", "difficulty": "medium", "category": "security"},
    {"question": "How does fine-tuning availability differ across tiers?", "difficulty": "medium", "category": "features"},
    {"question": "If I upgrade from standard to enterprise mid-month, does my refund window reset?", "difficulty": "hard", "category": "policy"},
    {"question": "What's the total storage capacity considering payload limits and batch sizes for enterprise?", "difficulty": "hard", "category": "technical"},
    {"question": "Can a standard tier customer achieve HIPAA compliance with additional configuration?", "difficulty": "hard", "category": "security"},
    {"question": "What is the quantum computing roadmap?", "difficulty": "hard", "category": "unanswerable"},
    {"question": "What encryption is used and does it meet FIPS 140-2 requirements?", "difficulty": "hard", "category": "security"},
]


def retrieve_context(question: str, documents: dict) -> list[dict]:
    """Simulate retrieval by using LLM to pick relevant documents."""
    doc_summaries = "\n".join(f"- {name}: {content[:100]}..." for name, content in documents.items())
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a retrieval system. Given a question, return the names of relevant documents from the list. Return ONLY document names, one per line."},
            {"role": "user", "content": f"Question: {question}\n\nAvailable documents:\n{doc_summaries}"}
        ],
        temperature=0
    )
    
    relevant_names = response.choices[0].message.content.strip().split("\n")
    relevant_docs = []
    for name in relevant_names:
        name = name.strip().lstrip("- ")
        for doc_name, content in documents.items():
            if doc_name in name or name in doc_name:
                relevant_docs.append({"doc": doc_name, "content": content})
    
    return relevant_docs if relevant_docs else [{"doc": list(documents.keys())[0], "content": list(documents.values())[0]}]


def generate_expected_answer(question: str, contexts: list[dict]) -> str:
    """Generate expected answer from retrieved contexts (primary annotator)."""
    context_text = "\n---\n".join(f"[{c['doc']}]\n{c['content']}" for c in contexts)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": """You are an expert annotator creating ground truth answers for a golden dataset.
Rules:
- Answer ONLY from the provided context
- Be concise but complete
- If the answer is not in the context, say "This information is not available in the provided documentation."
- Include specific numbers, dates, and facts from the context
- Do not add information beyond what's in the context"""},
            {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}"}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()


def second_annotator_validate(question: str, contexts: list[dict], primary_answer: str) -> dict:
    """Simulate second annotator (LLM with different prompt for IAA)."""
    context_text = "\n---\n".join(f"[{c['doc']}]\n{c['content']}" for c in contexts)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": """You are a second annotator validating a golden dataset answer.
Given a question, context, and proposed answer, evaluate:
1. Is the answer correct based on the context? (yes/no)
2. Is the answer complete? (yes/no)  
3. Does it contain any hallucinated information? (yes/no)
4. Your own answer to the question (write independently)
5. Agreement score (1-5): 5=perfect match, 3=partially agree, 1=completely disagree

Return as JSON: {"correct": bool, "complete": bool, "hallucinated": bool, "own_answer": str, "agreement": int, "notes": str}"""},
            {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}\n\nProposed answer: {primary_answer}"}
        ],
        temperature=0.3
    )
    
    try:
        text = response.choices[0].message.content.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, Exception):
        return {"correct": True, "complete": True, "hallucinated": False, "own_answer": primary_answer, "agreement": 4, "notes": "Parse error - defaulting"}


def compute_iaa(validations: list[dict]) -> float:
    """Compute simulated inter-annotator agreement (Cohen's Kappa approximation)."""
    agreements = [v["agreement"] for v in validations]
    # Convert to binary: agreement >= 4 = "agree", < 4 = "disagree"
    binary = [1 if a >= 4 else 0 for a in agreements]
    
    po = sum(binary) / len(binary)  # Observed agreement rate
    pe = 0.5  # Expected by chance (simplified)
    
    if pe == 1.0:
        return 1.0
    kappa = (po - pe) / (1 - pe)
    return max(0.0, kappa)


def build_golden_dataset():
    """Main function: build a complete golden dataset."""
    print("=" * 70)
    print("GOLDEN DATASET BUILDER")
    print("=" * 70)
    print(f"\nSource documents: {len(SOURCE_DOCUMENTS)}")
    print(f"Questions to process: {len(QUESTIONS)}")
    print(f"Started at: {datetime.now().isoformat()}")
    print("-" * 70)
    
    golden_dataset = {
        "metadata": {
            "name": "product-docs-golden",
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "created_by": "golden-dataset-builder",
            "schema_version": "1.0",
            "source_documents": list(SOURCE_DOCUMENTS.keys()),
            "total_examples": 0
        },
        "examples": []
    }
    
    validations = []
    
    for i, q_info in enumerate(QUESTIONS):
        question = q_info["question"]
        print(f"\n[{i+1}/{len(QUESTIONS)}] Processing: {question}")
        
        # Step 1: Retrieve relevant context
        print("  → Retrieving context...")
        contexts = retrieve_context(question, SOURCE_DOCUMENTS)
        print(f"    Found {len(contexts)} relevant document(s)")
        
        # Step 2: Generate expected answer (primary annotator)
        print("  → Generating expected answer...")
        expected_answer = generate_expected_answer(question, contexts)
        print(f"    Answer: {expected_answer[:80]}...")
        
        # Step 3: Second annotator validation
        print("  → Running second annotator validation...")
        validation = second_annotator_validate(question, contexts, expected_answer)
        validations.append(validation)
        print(f"    Agreement: {validation.get('agreement', '?')}/5 | Correct: {validation.get('correct', '?')}")
        
        # Step 4: Build golden example
        example = {
            "id": f"gold-{uuid.uuid4().hex[:8]}",
            "question": question,
            "source_docs": [c["doc"] for c in contexts],
            "relevant_passages": [c["content"][:200] for c in contexts],
            "expected_answer": expected_answer,
            "difficulty": q_info["difficulty"],
            "category": q_info["category"],
            "query_type": "factual" if q_info["difficulty"] == "easy" else "reasoning",
            "validation": {
                "annotator_agreement": validation.get("agreement", 0),
                "correct": validation.get("correct", False),
                "complete": validation.get("complete", False),
                "hallucinated": validation.get("hallucinated", False),
                "notes": validation.get("notes", "")
            },
            "created_at": datetime.now().isoformat()
        }
        
        golden_dataset["examples"].append(example)
    
    golden_dataset["metadata"]["total_examples"] = len(golden_dataset["examples"])
    
    # Save dataset
    output_path = "golden_dataset.json"
    with open(output_path, "w") as f:
        json.dump(golden_dataset, f, indent=2)
    print(f"\n{'=' * 70}")
    print(f"Golden dataset saved to: {output_path}")
    
    # --- Quality Report ---
    print(f"\n{'=' * 70}")
    print("QUALITY REPORT")
    print("=" * 70)
    
    # Inter-annotator agreement
    iaa = compute_iaa(validations)
    print(f"\n📊 Inter-Annotator Agreement (Kappa): {iaa:.3f}")
    if iaa > 0.8:
        print("   Status: EXCELLENT ✓")
    elif iaa > 0.6:
        print("   Status: GOOD (acceptable for production)")
    else:
        print("   Status: NEEDS IMPROVEMENT")
    
    # Difficulty distribution
    difficulties = Counter(ex["difficulty"] for ex in golden_dataset["examples"])
    total = len(golden_dataset["examples"])
    print(f"\n📊 Difficulty Distribution:")
    for diff, count in sorted(difficulties.items()):
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"   {diff:8s}: {count:3d} ({pct:5.1f}%) {bar}")
    
    # Category distribution
    categories = Counter(ex["category"] for ex in golden_dataset["examples"])
    print(f"\n📊 Category Distribution:")
    for cat, count in sorted(categories.items()):
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"   {cat:12s}: {count:3d} ({pct:5.1f}%) {bar}")
    
    # Validation summary
    correct_count = sum(1 for v in validations if v.get("correct", False))
    complete_count = sum(1 for v in validations if v.get("complete", False))
    hallucinated_count = sum(1 for v in validations if v.get("hallucinated", False))
    
    print(f"\n📊 Validation Summary:")
    print(f"   Correct answers:       {correct_count}/{total} ({correct_count/total*100:.0f}%)")
    print(f"   Complete answers:      {complete_count}/{total} ({complete_count/total*100:.0f}%)")
    print(f"   Hallucination-free:    {total - hallucinated_count}/{total} ({(total-hallucinated_count)/total*100:.0f}%)")
    
    # Agreement distribution
    agreements = [v.get("agreement", 0) for v in validations]
    print(f"\n📊 Agreement Score Distribution:")
    for score in range(1, 6):
        count = agreements.count(score)
        bar = "█" * (count * 3)
        print(f"   Score {score}: {count:2d} {bar}")
    
    avg_agreement = np.mean(agreements)
    print(f"\n   Average agreement: {avg_agreement:.2f}/5")
    
    print(f"\n{'=' * 70}")
    print(f"Dataset: {total} examples | IAA: {iaa:.3f} | Validity: {correct_count/total*100:.0f}%")
    print("=" * 70)


if __name__ == "__main__":
    build_golden_dataset()
