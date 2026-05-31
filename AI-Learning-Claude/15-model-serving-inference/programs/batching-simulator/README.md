# Batching Simulator

Simulates and compares different batching strategies for LLM serving.

## What It Does

- Generates random requests with varying input/output lengths
- Simulates no-batching, static batching, and continuous batching
- Compares throughput, latency, and GPU utilization

## Run

```bash
pip install -r requirements.txt
python main.py
```
