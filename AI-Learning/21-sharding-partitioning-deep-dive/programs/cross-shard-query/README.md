# Cross-Shard Query Simulator

Simulates cross-shard query execution with scatter-gather and smart routing.

## What it demonstrates
- Single-shard query vs cross-shard scatter-gather
- Smart topic-based routing to reduce scatter
- Latency comparison (1 shard vs 3 vs 5 shards)
- Result merging and re-ranking
- Query plan visualization

## Run
```bash
pip install -r requirements.txt
python main.py
```
