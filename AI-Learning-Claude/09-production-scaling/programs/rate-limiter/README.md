# Rate Limiter for AI APIs

A FastAPI middleware implementing token bucket rate limiting with per-user and per-model limits, designed for AI API endpoints.

## What This Demonstrates

- **Token bucket algorithm:** Allows bursts while enforcing average rate
- **Multi-dimensional limiting:** Per user AND per model limits
- **Proper HTTP headers:** X-RateLimit-Remaining, Retry-After
- **429 responses:** Clear communication when limits are exceeded

## How It Works

1. Each user gets a token bucket (refills at a steady rate)
2. Each AI model has its own bucket (expensive models have lower limits)
3. Requests consume tokens from both buckets
4. When empty, requests get 429 with Retry-After header

## Running

```bash
pip install -r requirements.txt
python main.py
```

Then test with:
```bash
# Normal request
curl http://localhost:8000/chat -H "X-User-ID: user1" -H "Content-Type: application/json" -d '{"model": "gpt-4", "message": "hello"}'

# Rapid fire (will hit rate limit)
for i in {1..20}; do curl -s http://localhost:8000/chat -H "X-User-ID: user1" -H "Content-Type: application/json" -d '{"model": "gpt-4", "message": "hello"}' | python -m json.tool; done
```

## Configuration

- User limits: 10 requests/minute (configurable)
- GPT-4 model limit: 5 requests/minute
- GPT-3.5 model limit: 20 requests/minute
