# Shard Simulator

Simulates distributing 100K vectors across 5 shards and demonstrates query routing.

## What it demonstrates
- Hash-based vs tenant-based vs topic-based sharding
- Query routing decisions (single-shard vs scatter-gather)
- Latency comparison between sharding strategies
- Hot spot detection

## Run
```bash
pip install -r requirements.txt
python main.py
```
