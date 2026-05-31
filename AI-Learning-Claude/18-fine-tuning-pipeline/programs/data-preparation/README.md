# Data Preparation Pipeline

Demonstrates a complete data preparation pipeline for LLM fine-tuning.

## What It Does

1. Generates simulated production logs (raw data)
2. Cleans data (removes PII, fixes formatting, deduplicates)
3. Formats into OpenAI chat format (JSONL)
4. Validates schema and quality
5. Splits into train/val/test (80/10/10)
6. Analyzes distribution and generates quality report

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- `output/train.jsonl` - Training data
- `output/val.jsonl` - Validation data
- `output/test.jsonl` - Test data
- `output/quality_report.txt` - Data quality analysis

## Key Concepts Demonstrated

- Data cleaning (PII removal, deduplication)
- Format conversion (raw logs → chat format)
- Quality scoring
- Distribution analysis
- Stratified splitting
