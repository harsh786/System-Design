# KV Cache Demo

Simulates KV cache memory behavior and demonstrates the impact of PagedAttention.

## What It Does

- Calculates KV cache memory for different models, context lengths, and batch sizes
- Compares static allocation waste vs PagedAttention efficiency
- Shows how KV cache limits concurrency

## Run

```bash
pip install -r requirements.txt
python main.py
```
