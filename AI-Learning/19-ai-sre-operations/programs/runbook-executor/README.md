# Runbook Executor

Simulates runbook execution for AI incidents, walking through each step and demonstrating automated vs manual decision points.

## Incident Types Covered

1. **Provider Outage** - Detect, failover, verify, monitor, revert
2. **Hallucination Spike** - Detect, tighten guardrails, diagnose, fix, verify
3. **Cost Runaway** - Detect, identify source, mitigate, fix root cause

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

Incident response timeline showing each runbook step, diagnosis checks, decision points, and resolution summary.
