# Golden Dataset Builder

Interactive tool to build a golden dataset from source documents and user questions.

## What It Does

1. Takes source documents and user questions as input
2. For each question: retrieves relevant context, generates an expected answer
3. Asks for human validation (simulated with LLM as second annotator)
4. Computes inter-annotator agreement
5. Outputs a complete `golden_dataset.json` with full schema
6. Generates a quality report with coverage and difficulty distribution

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
```

## Run

```bash
python main.py
```

## Output

- `golden_dataset.json` — The built golden dataset
- Quality report printed to console (coverage, difficulty, IAA)
