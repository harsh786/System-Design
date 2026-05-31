# Red Team Report Generator

Generates a complete red team report from vulnerability scan results and attack results.

## Features

- Takes vulnerability scan + attack results as input
- Produces formatted markdown report with:
  - Executive summary
  - Findings by severity
  - Reproduction steps
  - Remediation recommendations
  - Risk scores
- Output: `red_team_report.md`

## Usage

```bash
pip install -r requirements.txt
python main.py
```

Optionally provide input files:
```bash
python main.py --vuln-report ../vulnerability-scanner/vulnerability_report.json --attack-report ../attack-generator/attacks_output.json
```

If no input files exist, generates a sample report for demonstration.
