# Defense Tester

Tests guardrail effectiveness by sending a balanced set of 100 inputs (50 malicious + 50 legitimate) and measuring accuracy.

## Features

- 50 known-malicious inputs across attack categories
- 50 legitimate inputs including tricky edge cases
- Measures: True Positives, False Positives, Accuracy, Precision, Recall, F1
- Identifies which attack types slip through
- Generates defense effectiveness scorecard
- Recommends which defense layers need strengthening

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- Console: scorecard with metrics and recommendations
- File: `defense_report.json`
