# Input Guardrails

Demonstrates a multi-layered input guardrail system that checks user input before it reaches the LLM. Combines regex pattern matching, LLM-based classification, PII detection, and format validation.

## What It Does

1. **Prompt injection detection** — Regex patterns catch known attack signatures
2. **LLM-based injection detection** — Uses a separate LLM call to classify suspicious inputs
3. **PII detection** — Identifies personal data in user input before it's sent to the model
4. **Content safety** — Checks for harmful/inappropriate content requests
5. **Format validation** — Length limits, encoding checks

## Run

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## Key Concepts

- Guardrails run BEFORE the main LLM call — blocked inputs never reach the model
- Multiple detection layers compensate for each other's weaknesses
- Each check returns a decision (PASS/BLOCK) with an explanation
- False positives are preferable to false negatives for security-critical checks
