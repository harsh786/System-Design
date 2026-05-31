# Domain-Specific Generator

Generates domain-specific synthetic data for three domains: Legal, Medical, and Customer Support — demonstrating how style, vocabulary, and constraints change per domain.

## What It Does

- Generates 20 examples per domain (60 total)
- Applies domain-specific vocabulary, tone, and constraints
- Includes domain-specific validation
- Scores each example for domain authenticity

## Domains

| Domain | Style | Key Constraint |
|--------|-------|----------------|
| Legal | Formal, precise, hedged | Must include disclaimers |
| Medical | Clinical, evidence-based | Must recommend professional consultation |
| Customer Support | Warm, empathetic, actionable | Must offer specific resolution steps |

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Output

- `output/legal_data.json` — Legal domain examples
- `output/medical_data.json` — Medical domain examples  
- `output/support_data.json` — Customer support examples
- `output/domain_report.json` — Quality scores and validation results
