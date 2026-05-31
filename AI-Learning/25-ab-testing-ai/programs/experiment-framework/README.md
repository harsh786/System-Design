# Experiment Framework

A complete A/B testing framework for AI systems that demonstrates the full experiment lifecycle from launch to decision.

## Features

- Define experiments with multiple variants and configurable weights
- Simulate traffic assignment to variants
- Collect quality metrics per variant (simulated LLM-judge scores)
- Perform statistical significance testing
- Make ship/no-ship decisions based on evidence

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## What It Demonstrates

1. Experiment configuration with variants and metrics
2. Traffic splitting with user-based hashing
3. Metric collection (simulated faithfulness, latency, cost)
4. Sequential significance checking
5. Final decision with reasoning
