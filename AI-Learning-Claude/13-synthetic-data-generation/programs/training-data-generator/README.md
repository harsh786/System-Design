# Training Data Generator

Generates high-quality instruction-response pairs for fine-tuning LLMs.

## What It Does

Takes a domain description and 3 seed examples, then generates 50 diverse training examples with quality scoring and diversity enforcement.

## How It Works

1. Analyzes seed examples to understand format, tone, and complexity
2. Generates diverse instructions using persona-based variation
3. Generates high-quality responses for each instruction
4. Scores each example with an LLM judge (1-5)
5. Deduplicates using embedding similarity
6. Outputs JSONL ready for fine-tuning

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
python main.py
```

## Output

- `output/training_data.jsonl` — Fine-tuning ready JSONL
- `output/generation_report.json` — Stats on generation quality

## Example Output

```jsonl
{"messages": [{"role": "system", "content": "You are a helpful customer support agent."}, {"role": "user", "content": "I was charged twice for my subscription"}, {"role": "assistant", "content": "I'm sorry about the duplicate charge..."}]}
```
