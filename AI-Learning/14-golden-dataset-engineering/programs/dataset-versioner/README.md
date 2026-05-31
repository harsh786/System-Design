# Dataset Versioner

Implements dataset versioning with semantic versions, changelogs, and diff comparison.

## What It Does

1. Creates v1.0.0 of a golden dataset (initial 10 examples)
2. Adds new examples → creates v1.1.0
3. Modifies schema (adds field) → creates v2.0.0
4. Shows: diff between versions, coverage comparison, changelog
5. Outputs: versioned datasets in `versions/` directory

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# No API key needed - this runs entirely locally
```

## Run

```bash
python main.py
```

## Output

- `versions/` directory with versioned dataset files
- `CHANGELOG.md` — Auto-generated changelog
- Console output showing diffs and coverage comparisons
