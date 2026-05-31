# Few-Shot Prompting Demo

Demonstrates the impact of providing examples (shots) on LLM output quality and consistency.

## What This Shows

1. **Zero-shot vs 1-shot vs 3-shot vs 5-shot** — Accuracy progression
2. **Sentiment classification** — How examples clarify ambiguous cases
3. **Entity extraction** — How format examples ensure structured output
4. **Example ordering effects** — Same examples, different order, different results

## Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
pip install -r requirements.txt
python main.py
```

## Key Insight

Few-shot prompting is most valuable when your task has ambiguous definitions or custom formats. For standard tasks on modern models, zero-shot often suffices.
