# Agent Evaluator

## What This Does

Evaluates AI agents across multiple dimensions using test scenarios. Measures:

- **Task Completion**: Did the agent accomplish the goal?
- **Tool Selection Accuracy**: Did it choose the right tools?
- **Step Efficiency**: How many steps vs the optimal path?
- **Reasoning Quality**: Was the thinking logical? (LLM-as-judge)
- **Safety**: Did it violate any constraints?

## How It Works

1. Loads test scenarios with expected outcomes and golden trajectories
2. Simulates running an agent through each scenario
3. Compares actual trajectory against expected
4. Uses LLM-as-judge for reasoning quality
5. Outputs an agent scorecard with pass/fail per dimension

## Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
pip install -r requirements.txt
python main.py
```

## Output

```
=== AGENT SCORECARD ===

Scenario: "Look up weather in Tokyo"
  Task Completion:  PASS (1.0)
  Tool Selection:   PASS (1.0)
  Efficiency:       PASS (0.8 - 5 steps vs 4 optimal)
  Reasoning:        PASS (0.9)
  Safety:           PASS (no violations)

Overall: 4/5 scenarios passed
Agent readiness: READY FOR PRODUCTION
```

## Extending

- Add scenarios to `test_scenarios.json`
- Integrate with your actual agent by replacing the simulated agent
- Adjust pass/fail thresholds in `main.py`
