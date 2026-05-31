"""
Evaluation Data Generator
==========================
Generates golden evaluation datasets with diverse question types,
expected answers, difficulty levels, and scoring rubrics.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("MODEL", "gpt-4")

# ─── Sample Source Documents ───────────────────────────────────────────────────

SOURCE_DOCUMENTS = [
    {
        "id": "pricing",
        "title": "ProjectFlow Pricing",
        "content": """ProjectFlow Pricing Plans:

Free Plan: Up to 3 projects, 5 team members, 1GB storage. No integrations.
Pro Plan ($29/month): Unlimited projects, 25 team members, 50GB storage. 
Includes Slack, GitHub, and Google Drive integrations. Priority email support.
Enterprise Plan ($99/month): Everything in Pro plus SSO/SAML, audit logs, 
custom integrations, 500GB storage, unlimited team members, dedicated account manager, 
99.9% uptime SLA, and phone support.

All plans include: Kanban boards, Gantt charts, time tracking, and mobile app access.
Annual billing saves 20%. Free 14-day trial on all paid plans."""
    },
    {
        "id": "security",
        "title": "ProjectFlow Security",
        "content": """Security & Compliance:

Data Encryption: All data encrypted at rest (AES-256) and in transit (TLS 1.3).
Authentication: Email/password, Google OAuth, SSO/SAML (Enterprise only).
2FA: Available on all plans via authenticator app or SMS.
Data Residency: US (default), EU (available on Enterprise). 
SOC 2 Type II certified. GDPR compliant.
Data Retention: Active data kept indefinitely. Deleted items recoverable for 30 days.
Backups: Daily automated backups, 90-day retention.
API Security: API keys with scoped permissions. Rate limit: 1000 req/min."""
    },
    {
        "id": "features",
        "title": "ProjectFlow Features",
        "content": """Key Features:

Task Management: Create tasks with subtasks, dependencies, custom fields, and labels.
Views: Kanban, List, Calendar, Gantt, and Timeline views.
Automation: Rule-based automation (e.g., "when task moved to Done, notify assignee").
Enterprise plan supports custom webhook automations.
Reporting: Built-in dashboards for velocity, burndown, and team workload.
Custom reports available on Pro and Enterprise.
Integrations: Slack (real-time notifications), GitHub (PR linking), 
Google Drive (file attachments), Jira (import/sync on Enterprise).
Mobile: iOS and Android apps with offline mode. Push notifications."""
    }
]

# ─── Question Types ────────────────────────────────────────────────────────────

QUESTION_TYPES = {
    "factual": {
        "description": "Answer directly stated in one document",
        "difficulty": "easy",
        "count": 8,
        "prompt": """Generate {n} factual questions where the answer is explicitly stated in the documents.
Each question should test a DIFFERENT fact. Questions should sound natural (how a real user would ask).

Documents:
{docs}

Return JSON array with objects: {{"question": "...", "expected_answer": "...", "citation": "doc_id#relevant_detail"}}"""
    },
    "multi_hop": {
        "description": "Requires combining info from 2+ documents",
        "difficulty": "medium",
        "count": 5,
        "prompt": """Generate {n} questions that can ONLY be answered by combining information from multiple documents.

Documents:
{docs}

Example: "Can a free plan user set up SSO?" requires knowing SSO is Enterprise-only (security doc) 
and Free plan limitations (pricing doc).

Return JSON array with objects: {{"question": "...", "expected_answer": "...", "sources": ["doc_id1", "doc_id2"], "reasoning": "how facts combine"}}"""
    },
    "unanswerable": {
        "description": "Cannot be answered from available docs - tests abstention",
        "difficulty": "hard",
        "count": 4,
        "prompt": """Generate {n} questions that CANNOT be answered from the available documents but seem plausible.

Available topics (DO NOT ask about these): {topics}

Generate questions about:
- Features that don't exist but sound reasonable
- Competitor comparisons
- Implementation details not documented
- Future roadmap

Return JSON array with objects: {{"question": "...", "expected_answer": "I don't have information about that in the available documentation.", "why_unanswerable": "..."}}"""
    },
    "adversarial": {
        "description": "Designed to trip up the AI - tests robustness",
        "difficulty": "hard",
        "count": 3,
        "prompt": """Generate {n} adversarial questions designed to test AI robustness:
- Questions with false premises ("Since ProjectFlow was acquired by Microsoft...")
- Prompt injection attempts
- Questions that try to extract system information

Documents for context:
{docs}

Return JSON array with objects: {{"question": "...", "expected_answer": "...", "attack_type": "false_premise|injection|extraction"}}"""
    }
}

# ─── Generation Functions ──────────────────────────────────────────────────────

def generate_questions_by_type(q_type: str, config: dict) -> list:
    """Generate questions for a specific type."""
    
    docs_text = "\n\n".join([f"[{d['id']}] {d['title']}:\n{d['content']}" for d in SOURCE_DOCUMENTS])
    topics = ", ".join([d['title'] for d in SOURCE_DOCUMENTS])
    
    prompt = config["prompt"].format(
        n=config["count"],
        docs=docs_text,
        topics=topics
    )
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    
    try:
        result = json.loads(response.choices[0].message.content)
        questions = result.get("questions", list(result.values())[0] if result else [])
        
        # Enrich with metadata
        for i, q in enumerate(questions):
            q["id"] = f"eval-{q_type}-{i+1:03d}"
            q["type"] = q_type
            q["difficulty"] = config["difficulty"]
        
        return questions
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  Error parsing {q_type} questions: {e}")
        return []


def generate_rubric(question: dict) -> dict:
    """Generate a scoring rubric for a question."""
    
    prompt = f"""Create a 1-5 scoring rubric for evaluating AI responses to this question:

Question: {question['question']}
Expected answer: {question['expected_answer']}
Type: {question['type']} | Difficulty: {question['difficulty']}

Return JSON:
{{
  "5": "Description of a perfect answer",
  "4": "Description of a good answer",
  "3": "Description of an acceptable answer",
  "2": "Description of a poor answer",
  "1": "Description of a failing answer",
  "required_elements": ["list of must-have elements for score >= 3"],
  "disqualifiers": ["things that automatically score 1"]
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    
    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"5": "Perfect", "3": "Acceptable", "1": "Wrong"}


def analyze_coverage(eval_set: list) -> dict:
    """Analyze coverage of the evaluation set."""
    
    type_counts = {}
    difficulty_counts = {}
    
    for q in eval_set:
        q_type = q.get("type", "unknown")
        difficulty = q.get("difficulty", "unknown")
        type_counts[q_type] = type_counts.get(q_type, 0) + 1
        difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
    
    return {
        "total_questions": len(eval_set),
        "by_type": type_counts,
        "by_difficulty": difficulty_counts,
        "coverage_assessment": {
            "has_factual": type_counts.get("factual", 0) > 0,
            "has_multi_hop": type_counts.get("multi_hop", 0) > 0,
            "has_unanswerable": type_counts.get("unanswerable", 0) > 0,
            "has_adversarial": type_counts.get("adversarial", 0) > 0,
            "has_easy": difficulty_counts.get("easy", 0) > 0,
            "has_medium": difficulty_counts.get("medium", 0) > 0,
            "has_hard": difficulty_counts.get("hard", 0) > 0,
        }
    }


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  EVALUATION DATA GENERATOR")
    print("=" * 60)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    eval_set = []
    
    # Generate questions by type
    for q_type, config in QUESTION_TYPES.items():
        print(f"\n[Generating] {q_type} questions (n={config['count']}, difficulty={config['difficulty']})...")
        questions = generate_questions_by_type(q_type, config)
        print(f"  Generated {len(questions)} questions")
        eval_set.extend(questions)
    
    # Generate rubrics for each question
    print(f"\n[Rubrics] Generating scoring rubrics for {len(eval_set)} questions...")
    for i, question in enumerate(eval_set):
        question["rubric"] = generate_rubric(question)
        if (i + 1) % 5 == 0:
            print(f"  Progress: {i+1}/{len(eval_set)}")
    
    # Coverage analysis
    print(f"\n[Coverage] Analyzing evaluation set coverage...")
    coverage = analyze_coverage(eval_set)
    
    # Save outputs
    eval_file = output_dir / "eval_dataset.json"
    with open(eval_file, "w") as f:
        json.dump(eval_set, f, indent=2)
    print(f"\n  Saved {len(eval_set)} eval questions to {eval_file}")
    
    coverage_file = output_dir / "coverage_report.json"
    with open(coverage_file, "w") as f:
        json.dump(coverage, f, indent=2)
    print(f"  Coverage report saved to {coverage_file}")
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"  Total questions: {coverage['total_questions']}")
    print(f"  By type: {coverage['by_type']}")
    print(f"  By difficulty: {coverage['by_difficulty']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
