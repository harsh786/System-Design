# Memory Safety Demo

Demonstrates memory safety controls: PII detection, deletion cascades, access control, and memory poisoning defense.

## Features

- **Scenario 1**: PII detected in memory → automatically redacted before storage
- **Scenario 2**: User says "forget this" → memory deleted with cascade
- **Scenario 3**: User requests full deletion → all memories purged (GDPR)
- **Scenario 4**: Memory poisoning attempt → detected and blocked

## Setup

```bash
pip install -r requirements.txt
python main.py
```

No API key needed - this demo runs entirely locally to demonstrate safety patterns.

## Output

- Safety audit report showing what was blocked, redacted, or deleted
- Demonstration of each attack/risk scenario
- Final compliance status check
