"""
AI Gateway - Simplified Enterprise AI Gateway

Demonstrates: routing, rate limiting, caching, cost tracking, and logging.
All AI requests flow through this gateway for centralized control.
"""

import hashlib
import json
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Gateway", description="Enterprise AI Gateway - Simplified")

# --- Configuration ---

# Cost per 1K tokens (approximate pricing)
MODEL_PRICING = {
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}

# Rate limits per user (requests per minute)
RATE_LIMIT_RPM = 60
RATE_LIMIT_WINDOW = 60  # seconds

# --- In-Memory State (use Redis in production) ---

# Cache: hash(prompt) -> response
response_cache: dict[str, dict] = {}

# Rate limiting: user_id -> list of timestamps
rate_limit_windows: dict[str, list[float]] = defaultdict(list)

# Cost tracking: user_id -> total cost
user_costs: dict[str, float] = defaultdict(float)

# Request log
request_log: list[dict] = []

# Stats
stats = {
    "total_requests": 0,
    "cache_hits": 0,
    "total_tokens": 0,
    "total_cost": 0.0,
}

# --- Models ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "gpt-3.5-turbo"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None


# --- Helper Functions ---


def get_cache_key(request: ChatRequest) -> str:
    """Generate a cache key from the request (hash of model + messages + temp)."""
    content = json.dumps({
        "model": request.model,
        "messages": [m.model_dump() for m in request.messages],
        "temperature": request.temperature,
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def check_rate_limit(user_id: str) -> bool:
    """Token bucket rate limiting. Returns True if allowed."""
    now = time.time()
    window = rate_limit_windows[user_id]

    # Remove timestamps outside the window
    rate_limit_windows[user_id] = [
        t for t in window if now - t < RATE_LIMIT_WINDOW
    ]

    if len(rate_limit_windows[user_id]) >= RATE_LIMIT_RPM:
        return False

    rate_limit_windows[user_id].append(now)
    return True


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost based on model pricing."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-3.5-turbo"])
    cost = (input_tokens / 1000) * pricing["input"] + \
           (output_tokens / 1000) * pricing["output"]
    return round(cost, 6)


def log_request(request_id: str, user_id: str, model: str,
                input_tokens: int, output_tokens: int,
                cost: float, cache_hit: bool, latency_ms: float):
    """Log request for observability."""
    entry = {
        "request_id": request_id,
        "user_id": user_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "cache_hit": cache_hit,
        "latency_ms": latency_ms,
        "timestamp": datetime.utcnow().isoformat(),
    }
    request_log.append(entry)
    # Keep only last 1000 entries in memory
    if len(request_log) > 1000:
        request_log.pop(0)


# --- API Endpoints ---


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    x_user_id: str = Header(default="anonymous"),
):
    """
    Main gateway endpoint. Proxies requests to LLM providers with:
    - Rate limiting
    - Caching
    - Cost tracking
    - Logging
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # 1. Rate limiting
    if not check_rate_limit(x_user_id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_RPM} requests per minute."
        )

    # 2. Check cache
    cache_key = get_cache_key(request)
    if cache_key in response_cache:
        cached = response_cache[cache_key]
        latency_ms = (time.time() - start_time) * 1000
        stats["total_requests"] += 1
        stats["cache_hits"] += 1

        log_request(request_id, x_user_id, request.model, 0, 0, 0.0, True, latency_ms)

        return JSONResponse(
            content=cached["response"],
            headers={
                "X-Request-ID": request_id,
                "X-Cache-Hit": "true",
                "X-Tokens-Used": "0",
                "X-Cost": "0.0",
                "X-Model-Used": request.model,
            }
        )

    # 3. Validate model
    if request.model not in MODEL_PRICING:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{request.model}' not supported. "
                   f"Available: {list(MODEL_PRICING.keys())}"
        )

    # 4. Route to provider (in this demo, all go to OpenAI)
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=request.model,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")

    # 5. Calculate cost
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens
    cost = calculate_cost(request.model, input_tokens, output_tokens)

    # 6. Track cost
    user_costs[x_user_id] += cost
    stats["total_requests"] += 1
    stats["total_tokens"] += total_tokens
    stats["total_cost"] += cost

    # 7. Build response
    response_data = {
        "id": response.id,
        "object": "chat.completion",
        "model": response.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                },
                "finish_reason": response.choices[0].finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    }

    # 8. Cache response (only for temperature=0 or low temperature)
    if request.temperature <= 0.1:
        response_cache[cache_key] = {"response": response_data}

    # 9. Log
    latency_ms = (time.time() - start_time) * 1000
    log_request(request_id, x_user_id, request.model,
                input_tokens, output_tokens, cost, False, latency_ms)

    return JSONResponse(
        content=response_data,
        headers={
            "X-Request-ID": request_id,
            "X-Cache-Hit": "false",
            "X-Tokens-Used": str(total_tokens),
            "X-Cost": str(cost),
            "X-Model-Used": request.model,
        }
    )


@app.get("/stats")
async def get_stats():
    """Get overall gateway statistics."""
    cache_hit_rate = (
        stats["cache_hits"] / stats["total_requests"] * 100
        if stats["total_requests"] > 0 else 0
    )
    return {
        **stats,
        "cache_hit_rate_pct": round(cache_hit_rate, 1),
        "cache_size": len(response_cache),
        "active_users": len(user_costs),
    }


@app.get("/stats/{user_id}")
async def get_user_stats(user_id: str):
    """Get per-user statistics."""
    user_requests = [r for r in request_log if r["user_id"] == user_id]
    return {
        "user_id": user_id,
        "total_cost": round(user_costs.get(user_id, 0), 6),
        "total_requests": len(user_requests),
        "recent_requests": user_requests[-10:],
    }


@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent request logs."""
    return {"logs": request_log[-limit:]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
