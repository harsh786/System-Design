# Evaluation Data Generator

Generates golden evaluation datasets with diverse question types, expected answers, and scoring rubrics.

## What It Does

Takes source documents and generates a comprehensive evaluation dataset including:
- Factual questions (single-hop)
- Multi-hop questions (reasoning across content)
- Unanswerable questions (tests abstention)
- Adversarial questions (tests robustness)

## How It Works

1. Analyzes source documents to identify key facts and relationships
2. Generates questions at varying difficulty levels (easy/medium/hard)
3. Generates expected answers with citations
4. Creates scoring rubrics for each question
5. Validates coverage across topics and difficulty levels

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Output

- `output/eval_dataset.json` — Complete evaluation dataset
- `output/coverage_report.json` — Coverage analysis

## Example Output

```json
{
  "id": "eval-001",
  "question": "What is the maximum number of team members on the Pro plan?",
  "type": "factual",
  "difficulty": "easy",
  "expected_answer": "The Pro plan supports up to 25 team members.",
  "citation": "pricing.md#pro-plan",
  "rubric": {"5": "Exact number with plan name", "3": "Correct number, missing context"}
}
```
