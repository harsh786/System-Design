# Capacity Planner

Calculates capacity requirements and cost projections for AI systems.

## Features

- Takes current usage metrics, growth rate, and SLO requirements
- Calculates required GPUs, vector DB nodes, Redis memory, storage
- Projects capacity needs at 3, 6, and 12 months
- Generates monthly cost projections
- Provides recommendations on when to scale and optimization opportunities

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

A capacity plan with current utilization, projections, cost forecasts, and actionable recommendations.
