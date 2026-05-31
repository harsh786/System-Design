# Differential Privacy for Embeddings

Demonstrates the privacy-utility tradeoff when adding differential privacy noise to embeddings.

## What It Shows

1. Creates embeddings (TF-IDF vectors) for a set of documents
2. Adds calibrated Gaussian noise at different epsilon values
3. Measures search quality degradation at each privacy level
4. Prints comparison table showing the tradeoff

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Key Insight

Lower epsilon = more privacy = more noise = worse search quality. The program shows exactly how much quality you lose at each level.
