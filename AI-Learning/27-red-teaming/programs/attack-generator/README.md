# Attack Generator

Generates adversarial prompts for testing AI system security. Implements 5 attack categories with 10 variants each, producing 50 attack prompts ready for testing.

## Features

- 5 attack categories: Prompt Injection, Jailbreaking, Data Extraction, Indirect Injection, Tool Misuse
- 10 variants per category using mutation techniques
- Severity classification for each attack
- Output in structured format for automated testing

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env  # Configure if using LLM-powered mutation
python main.py
```

## Output

Generates 50 attack prompts with:
- Attack category and subcategory
- Severity rating (Critical/High/Medium/Low)
- Expected behavior if the attack succeeds
- The attack prompt itself

Results saved to `attacks_output.json`.
