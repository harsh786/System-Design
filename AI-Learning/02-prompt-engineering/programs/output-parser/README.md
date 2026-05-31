# Output Parser Demo

Demonstrates parsing LLM output into typed Python objects using Pydantic, with validation and error recovery.

## What This Shows

1. **Pydantic schemas as output contracts** — Define what you expect
2. **Parsing LLM output into typed objects** — JSON → Pydantic models
3. **Handling failures with retry logic** — When the model breaks schema
4. **Validation errors and fixes** — See what goes wrong and how to recover
5. **Schema evolution** — Migrating from v1 to v2 without breaking

## Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
pip install -r requirements.txt
python main.py
```

## Key Pattern

```python
LLM Output (string) → JSON parse → Pydantic validate → Typed object
         ↑                                    |
         └──── retry with error message ──────┘ (on failure)
```
