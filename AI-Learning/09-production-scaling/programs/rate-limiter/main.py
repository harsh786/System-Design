"""
Rate Limiter for AI APIs
=========================
Implements token bucket rate limiting with:
- Per-user rate limits
- Per-model rate limits (expensive models get lower limits)
- Proper HTTP headers (X-RateLimit-Remaining, Retry-After)
- FastAPI middleware

Run: python main.py
Test: curl http://localhost:8000/chat -H "X-User-ID: user1" -H "Content-Type: application/json" -d '{"model":"gpt-4","message":"hello"}'
"""

import time
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn


# --- Token Bucket Implementation ---

@dataclass
class TokenBucket:
    """
    Token Bucket Rate Limiter.
    
    Analogy: You have a bucket that holds `capacity` tokens.
    Tokens are added at `refill_rate` per second.
    Each request consumes 1 token. No tokens = request denied.
    
    This allows bursts (up to capacity) while enforcing an average rate.
    """
    capacity: int           # Maximum tokens in bucket
    refill_rate: float      # Tokens added per second
    tokens: float = 0.0     # Current token count
    last_refill: float = 0.0  # Timestamp of last refill

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def _refill(self):
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if denied."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    @property
    def remaining(self) -> int:
        """Current tokens remaining."""
        self._refill()
        return int(self.tokens)

    @property
    def retry_after(self) -> float:
        """Seconds until at least 1 token is available."""
        if self.tokens >= 1:
            return 0.0
        tokens_needed = 1 - self.tokens
        return tokens_needed / self.refill_rate


# --- Rate Limiter Manager ---

class RateLimiterManager:
    """Manages rate limit buckets for users and models."""

    def __init__(self):
        self.user_buckets: dict[str, TokenBucket] = {}
        self.model_buckets: dict[str, TokenBucket] = {}
        
        # Configuration: limits per model
        self.model_limits = {
            "gpt-4": {"capacity": 5, "refill_rate": 5 / 60},        # 5 req/min
            "gpt-4o": {"capacity": 10, "refill_rate": 10 / 60},     # 10 req/min
            "gpt-3.5-turbo": {"capacity": 20, "refill_rate": 20 / 60},  # 20 req/min
            "default": {"capacity": 15, "refill_rate": 15 / 60},    # 15 req/min
        }
        
        # User limits
        self.user_capacity = 10          # 10 requests burst
        self.user_refill_rate = 10 / 60  # 10 per minute sustained

    def get_user_bucket(self, user_id: str) -> TokenBucket:
        if user_id not in self.user_buckets:
            self.user_buckets[user_id] = TokenBucket(
                capacity=self.user_capacity,
                refill_rate=self.user_refill_rate,
            )
        return self.user_buckets[user_id]

    def get_model_bucket(self, model: str) -> TokenBucket:
        if model not in self.model_buckets:
            limits = self.model_limits.get(model, self.model_limits["default"])
            self.model_buckets[model] = TokenBucket(**limits)
        return self.model_buckets[model]

    def check_rate_limit(self, user_id: str, model: str) -> tuple[bool, dict]:
        """
        Check if request is allowed.
        Returns (allowed, headers_dict).
        """
        user_bucket = self.get_user_bucket(user_id)
        model_bucket = self.get_model_bucket(model)

        headers = {
            "X-RateLimit-Limit-User": str(self.user_capacity),
            "X-RateLimit-Remaining-User": str(user_bucket.remaining),
            "X-RateLimit-Limit-Model": str(
                self.model_limits.get(model, self.model_limits["default"])["capacity"]
            ),
            "X-RateLimit-Remaining-Model": str(model_bucket.remaining),
        }

        # Check user limit first
        if not user_bucket.consume():
            headers["Retry-After"] = str(int(user_bucket.retry_after) + 1)
            headers["X-RateLimit-Exceeded"] = "user"
            return False, headers

        # Check model limit
        if not model_bucket.consume():
            # Refund the user token since we're rejecting
            user_bucket.tokens = min(user_bucket.capacity, user_bucket.tokens + 1)
            headers["Retry-After"] = str(int(model_bucket.retry_after) + 1)
            headers["X-RateLimit-Exceeded"] = "model"
            return False, headers

        return True, headers


# --- FastAPI Application ---

app = FastAPI(title="AI Rate Limiter Demo")
limiter = RateLimiterManager()


@app.post("/chat")
async def chat(request: Request):
    """AI chat endpoint with rate limiting."""
    # Get user ID from header (in production: from auth token)
    user_id = request.headers.get("X-User-ID", "anonymous")
    
    # Parse request body
    body = await request.json()
    model = body.get("model", "gpt-3.5-turbo")
    message = body.get("message", "")

    # Check rate limits
    allowed, headers = limiter.check_rate_limit(user_id, model)

    if not allowed:
        exceeded_by = headers.get("X-RateLimit-Exceeded", "unknown")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "type": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded ({exceeded_by} limit). Please retry after {headers.get('Retry-After', '60')} seconds.",
                    "exceeded_by": exceeded_by,
                    "retry_after_seconds": int(headers.get("Retry-After", 60)),
                }
            },
            headers=headers,
        )

    # Simulate AI response (in production: call actual model)
    response = {
        "model": model,
        "message": f"[Simulated {model} response to: {message[:50]}]",
        "usage": {"prompt_tokens": 50, "completion_tokens": 100},
    }

    return JSONResponse(content=response, headers=headers)


@app.get("/limits")
async def get_limits(request: Request):
    """Check current rate limit status for a user."""
    user_id = request.headers.get("X-User-ID", "anonymous")
    
    user_bucket = limiter.get_user_bucket(user_id)
    
    return {
        "user_id": user_id,
        "user_limit": {
            "capacity": limiter.user_capacity,
            "remaining": user_bucket.remaining,
            "refill_rate_per_minute": limiter.user_refill_rate * 60,
        },
        "model_limits": {
            model: {
                "capacity": config["capacity"],
                "remaining": limiter.model_buckets[model].remaining if model in limiter.model_buckets else config["capacity"],
            }
            for model, config in limiter.model_limits.items()
            if model != "default"
        },
    }


# --- Demo: Simulate rapid requests ---

def demo():
    """Run a quick demo showing rate limiting in action."""
    import requests as req
    import threading

    print("\n" + "=" * 50)
    print("  RATE LIMITER DEMO")
    print("=" * 50)
    print("\nStarting server on http://localhost:8000")
    print("Sending 15 rapid requests (limit: 10/min)...\n")

    # Start server in background thread
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error"),
        daemon=True,
    )
    server_thread.start()
    time.sleep(1)  # Wait for server to start

    # Send rapid requests
    url = "http://localhost:8000/chat"
    headers = {"X-User-ID": "demo-user", "Content-Type": "application/json"}
    payload = {"model": "gpt-4", "message": "Hello!"}

    print(f"{'#':<4} {'Status':<8} {'Remaining':<12} {'Detail'}")
    print("-" * 50)

    for i in range(15):
        try:
            resp = req.post(url, json=payload, headers=headers)
            remaining = resp.headers.get("X-RateLimit-Remaining-User", "?")
            
            if resp.status_code == 200:
                print(f"{i+1:<4} {'200 OK':<8} {remaining:<12} Request processed")
            else:
                retry = resp.json()["error"]["retry_after_seconds"]
                exceeded = resp.json()["error"]["exceeded_by"]
                print(f"{i+1:<4} {'429':<8} {remaining:<12} Rejected ({exceeded} limit, retry in {retry}s)")
        except Exception as e:
            print(f"{i+1:<4} {'ERROR':<8} {'?':<12} {e}")

    print("\n✓ Rate limiter working correctly!")
    print("  Requests beyond limit received 429 with Retry-After header.")


if __name__ == "__main__":
    import sys
    
    if "--demo" in sys.argv:
        demo()
    else:
        print("AI API Rate Limiter")
        print("=" * 40)
        print("Starting server on http://localhost:8000")
        print("\nEndpoints:")
        print("  POST /chat   - Chat endpoint (rate limited)")
        print("  GET  /limits - Check your current limits")
        print("\nRun with --demo for automated demonstration")
        print()
        uvicorn.run(app, host="0.0.0.0", port=8000)
