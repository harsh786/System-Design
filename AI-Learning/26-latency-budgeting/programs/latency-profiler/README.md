# Latency Profiler

Profiles latency of each component in an AI pipeline, showing time spent at each step
with a text-based waterfall diagram.

## What It Does

- Simulates a full AI pipeline (embedding, search, reranking, generation, guardrails)
- Measures time spent at each step
- Identifies the bottleneck (slowest step)
- Prints a waterfall diagram showing timing visually

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- Per-component timing breakdown
- Percentage of total time
- Visual waterfall chart
- Bottleneck identification
