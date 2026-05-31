# Model Benchmark

Benchmarks LLM API endpoints measuring key serving metrics.

## What It Does

- Measures Time to First Token (TTFT), tokens/sec, total latency
- Tests at different input/output lengths
- Calculates cost per token
- Outputs recommendations

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API endpoint
python main.py
```
