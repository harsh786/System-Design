# AI Gateway - Simplified Implementation

A simplified AI Gateway that demonstrates core enterprise gateway capabilities:
routing, rate limiting, caching, cost tracking, and logging.

## What This Demonstrates

- **Request routing** to different LLM providers based on model parameter
- **Rate limiting** per user (token bucket algorithm)
- **Response caching** for identical requests (saves cost)
- **Cost tracking** per request and per user
- **Request/response logging** for observability
- **Usage headers** returned with every response

## Running

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI API key
uvicorn main:app --reload --port 8000
```

## Usage

```bash
# Send a request through the gateway
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-123" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Check usage stats
curl http://localhost:8000/stats/user-123

# Check overall gateway stats
curl http://localhost:8000/stats
```

## Response Headers

Every response includes:
- `X-Tokens-Used`: Total tokens consumed
- `X-Cost`: Cost of this request in USD
- `X-Cache-Hit`: Whether this was served from cache
- `X-Model-Used`: Which model actually served the request
- `X-Request-ID`: Unique ID for tracing
