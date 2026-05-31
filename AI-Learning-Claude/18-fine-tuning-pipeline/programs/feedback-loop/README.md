# Production Feedback Loop Simulator

Simulates the continuous improvement cycle: model serves traffic, collects feedback, extracts training examples, and demonstrates the flywheel effect.

## What It Does

1. Simulates 100 production responses with varying quality
2. Generates realistic user feedback (thumbs up/down, edits, regenerations)
3. Extracts high-value training examples from feedback signals
4. Filters for quality (PII, duplicates, noise)
5. Demonstrates which examples are worth retraining on
6. Shows the flywheel: each cycle produces better data

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- `new_training_examples.jsonl` - Extracted training examples
- Console: quality report showing feedback distribution and extraction stats
