# Quality Filter

Filters synthetic data through a multi-stage pipeline: rule-based checks, LLM quality scoring, deduplication, and diversity analysis.

## What It Does

Takes a batch of synthetic examples and produces a filtered, high-quality subset with a detailed rejection report.

## Pipeline

```
100 input examples
  → Rule-based filter (format, length, language)
  → LLM judge scoring (quality 1-5)
  → Embedding deduplication (cosine > 0.92 = duplicate)
  → Diversity check
  → ~75 accepted examples + rejection report
```

## Usage

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Output

- `output/filtered_data.json` — Accepted examples
- `output/rejected_data.json` — Rejected with reasons
- `output/filter_report.json` — Statistics and breakdown
