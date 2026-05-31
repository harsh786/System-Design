# Shard Rebalancer

Simulates zero-downtime shard rebalancing when data becomes unevenly distributed.

## What it demonstrates
- Detecting imbalanced shards (60%/30%/10% distribution)
- Split, move, and verify operations
- Zero-downtime migration with dual-write
- Before/after distribution comparison
- Latency monitoring during rebalancing

## Run
```bash
pip install -r requirements.txt
python main.py
```
