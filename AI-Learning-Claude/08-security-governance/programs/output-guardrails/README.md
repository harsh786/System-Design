# Output Guardrails

Validates LLM responses BEFORE they reach the user. Catches PII leakage, hallucinated URLs, harmful content, off-topic responses, and system prompt leakage.

## What It Does

1. **PII leakage detection** — Scans output for personal data that shouldn't be exposed
2. **Hallucinated URL detection** — Checks if cited URLs actually exist
3. **Harmful content filtering** — Blocks toxic, dangerous, or inappropriate outputs
4. **Off-topic detection** — Ensures response stays within the system's scope
5. **Source verification** — Validates that citations reference real sources
6. **System prompt leak detection** — Catches if the AI reveals its instructions

## Run

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```
