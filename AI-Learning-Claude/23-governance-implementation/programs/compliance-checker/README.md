# AI Compliance Checker

Automated compliance checking tool that validates AI system configurations against defined policies.

## Features
- 10 compliance policies defined as executable rules
- Takes system configuration as input
- Checks each policy and reports compliant/non-compliant
- Generates compliance report with recommendations
- Demonstrates policy-as-code for AI governance

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Modes
- **Demo**: runs checks against example system configurations
- **Interactive**: input your own system configuration
- **File**: check a JSON configuration file

```bash
python main.py                    # Demo mode
python main.py --interactive      # Interactive mode
python main.py --file config.json # File mode
```
