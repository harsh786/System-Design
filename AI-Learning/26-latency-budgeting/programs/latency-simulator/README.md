# Latency Simulator

Simulates AI pipeline latency under different configurations to compare optimization strategies.

## What It Does

- Simulates multiple configurations: no-streaming vs streaming, with/without cache, with/without model routing
- Shows user-perceived latency for each configuration
- Demonstrates streaming reduces PERCEIVED latency by ~80%
- Demonstrates caching reduces latency to near-zero for repeat queries
- Prints comparison table of all configurations

## Usage

```bash
pip install -r requirements.txt
python main.py
```

## Output

- Side-by-side comparison of 6+ configurations
- User experience simulation (what each feels like)
- Ranking by perceived latency
