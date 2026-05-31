# Trajectory Recorder

Records agent trajectories and creates a golden trajectory dataset for agent evaluation.

## What It Does

1. Runs a simulated agent through 5 tasks
2. Records every step: thought, tool, args, result
3. Lets you mark trajectories as "golden" (approved) or "failed"
4. Outputs `golden_trajectories.json` ready for agent evaluation
5. Shows trajectory comparison (agent path vs golden path)

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

- `golden_trajectories.json` — Approved golden trajectories
- Console output showing step-by-step execution and comparison
