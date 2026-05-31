# Evaluation: Fine-Tuned vs Base Model

Compares a fine-tuned model against a base model across multiple dimensions to determine whether to deploy.

## What It Does

1. Simulates test set evaluation for both "base" and "fine-tuned" models
2. Compares: accuracy, format compliance, style consistency, latency, cost
3. Shows where fine-tuned model wins AND where it loses
4. Generates deployment recommendation with confidence score

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- Detailed comparison table
- Per-category breakdown (where does FT help most?)
- Regression analysis (where does FT hurt?)
- Final deployment recommendation

## Note

Uses simulated model outputs. In production, you'd run actual inference with both models on your test set.
