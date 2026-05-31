# Bottleneck Detector

Analyzes latency traces to find bottlenecks in an AI pipeline.

## What It Does

- Generates 100 simulated request traces with realistic per-component latency distributions
- Detects which component contributes most to P95 latency
- Shows percentage contribution of each component
- Recommends which component to optimize first for biggest impact
- Prints a complete bottleneck analysis report

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- Percentile analysis (P50, P95, P99) per component
- Contribution to tail latency
- Optimization recommendations ranked by impact
