# Confidence Scorer

## What This Does

Computes a composite confidence score for AI-generated answers by combining multiple signals. Demonstrates confidence-driven behavior (answer directly, add caveats, or abstain).

## Signals Used

1. **Retrieval Score** — How relevant are the retrieved documents?
2. **Source Count** — How many supporting sources found?
3. **Source Agreement** — Do sources agree with each other?
4. **Self-Consistency** — Generate multiple answers, check if they agree
5. **Citation Coverage** — What % of claims have supporting citations?

## How It Works

1. Takes a question + retrieved contexts + generated answer
2. Computes each confidence signal independently
3. Combines into a weighted composite score
4. Applies confidence-driven behavior rules
5. Shows calibration analysis

## Setup

```bash
cp .env.example .env
pip install -r requirements.txt
python main.py
```

## Output

```
=== Confidence Analysis ===

Question: "What is the refund policy?"
Confidence: 0.87 (HIGH)

Signals:
  Retrieval Score:    0.92
  Source Count:       0.80 (4/5 sources)
  Source Agreement:   0.88
  Self-Consistency:   0.90
  Citation Coverage:  0.85

Behavior: ANSWER DIRECTLY (no caveats needed)
```
