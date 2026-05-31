# PII Detector and Anonymizer

Uses Microsoft Presidio to detect and anonymize personally identifiable information (PII) in text. Demonstrates multiple anonymization strategies.

## What It Does

1. **Detects** emails, phone numbers, SSNs, credit cards, names, addresses, and more
2. **Anonymizes** using configurable strategies: redact, mask, replace, hash
3. **Reports** what was found, where, and confidence level
4. **Shows before/after** comparison for each strategy

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Key Concepts

- PII detection runs on BOTH input (before LLM) and output (before user)
- Different anonymization strategies suit different use cases
- Configurable sensitivity: high (catch everything, more false positives) vs low (fewer catches, fewer false positives)
- Presidio uses NLP models + regex for detection
