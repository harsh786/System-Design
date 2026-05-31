# Chain-of-Thought Prompting Demo

Demonstrates the difference between standard prompting and Chain-of-Thought (CoT) prompting on reasoning tasks.

## What This Shows

1. **Standard vs CoT** — Same problems, dramatic accuracy difference
2. **Zero-shot CoT** — Just adding "Let's think step by step"
3. **Few-shot CoT** — Providing examples with reasoning steps
4. **Side-by-side comparison** — Math, logic, and reasoning tasks

## Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
pip install -r requirements.txt
python main.py
```

## Expected Output

You'll see each problem solved twice — once with standard prompting (often wrong on tricky problems) and once with CoT (usually correct). The accuracy improvement is typically 30-60% on reasoning tasks.
