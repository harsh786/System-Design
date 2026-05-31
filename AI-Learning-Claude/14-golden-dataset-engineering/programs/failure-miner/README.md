# Failure Miner

Simulates production failure mining — extracting golden test cases from production errors.

## What It Does

1. Generates 100 simulated "production logs" (queries + responses + quality scores)
2. Identifies failures: low confidence, hallucinations, retrieval misses, errors
3. Categorizes failures by type
4. Extracts test cases from failures with expert validation (simulated)
5. Outputs: `mined_test_cases.json` + failure report
6. Shows the full funnel: 100 logs → ~15 failures → ~12 validated test cases

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

- `mined_test_cases.json` — Validated test cases ready to add to golden dataset
- `failure_report.txt` — Summary report of failure analysis
