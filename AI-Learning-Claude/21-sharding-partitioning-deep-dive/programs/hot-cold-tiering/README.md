# Hot-Cold Tiering Simulator

Simulates data tiering based on access patterns and demonstrates cost savings.

## What it demonstrates
- Classifying 10K documents into hot/warm/cold tiers by access patterns
- Cost savings from tiering vs all-hot storage
- Promote-on-access: cold documents get promoted when queried
- Latency differences per tier
- Tier distribution visualization

## Run
```bash
pip install -r requirements.txt
python main.py
```
