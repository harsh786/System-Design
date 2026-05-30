# Engineering Foundations for AI Architects

## Why Engineering Excellence is Prerequisite for AI

Building AI systems without strong engineering foundations is like constructing a skyscraper on sand. AI adds complexity in every dimension—data pipelines, model serving, inference latency, token management, embedding storage, vector search, prompt versioning—and each of these compounds existing engineering challenges.

**The AI Tax on Bad Engineering:**
- A poorly designed API becomes catastrophic when each call costs $0.03 in LLM tokens
- Missing observability means you can't debug why your RAG pipeline returns hallucinations
- No rate limiting means a single user can burn through your entire OpenAI budget in minutes
- Lack of async patterns means your server blocks on 2-second LLM inference calls
- No circuit breakers means one OpenAI outage cascades through your entire system

**What separates an AI Engineer from an AI Architect:**
An AI Engineer can call `openai.chat.completions.create()`. An AI Architect designs the system that makes that call reliable at scale—with fallbacks, caching, streaming, observability, cost controls, and graceful degradation.

---

## Python Async/Await Deep Dive

### The Event Loop

Python's `asyncio` event loop is a single-threaded cooperative multitasking system. It maintains a queue of coroutines and switches between them at `await` points.

```python
import asyncio

async def main():
    loop = asyncio.get_running_loop()
    print(f"Loop running: {loop.is_running()}")
    print(f"Loop thread: {loop._thread_id}")

asyncio.run(main())
```

**Critical mental model:** The event loop never preempts a coroutine. Code between `await` statements runs atomically. This means:
- No race conditions on shared state between awaits
- A CPU-bound operation blocks the ENTIRE loop
- You must `await` to yield control

### Coroutines vs Tasks vs Futures

```python
import asyncio

# A coroutine FUNCTION (not yet executing)
async def fetch_data(url: str) -> dict:
    await asyncio.sleep(1)  # Simulates I/O
    return {"url": url, "data": "..."}

# A coroutine OBJECT (created but not scheduled)
coro = fetch_data("http://example.com")

# A Task (scheduled on the event loop, running concurrently)
async def main():
    task = asyncio.create_task(fetch_data("http://example.com"))
    # Task is now running! We can do other work...
    result = await task  # Wait for completion
```

### asyncio.gather vs TaskGroup

```python
import asyncio

# gather - runs coroutines concurrently, returns results in order
async def parallel_fetch():
    results = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
        fetch_data("url3"),
        return_exceptions=True  # Don't fail all if one fails
    )
    return results

# TaskGroup (Python 3.11+) - structured concurrency
async def structured_fetch():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch_data("url1"))
        task2 = tg.create_task(fetch_data("url2"))
    # All tasks guaranteed complete here
    return task1.result(), task2.result()
```

### Semaphores for Concurrency Control

```python
import asyncio

# Limit concurrent LLM calls to avoid rate limits
semaphore = asyncio.Semaphore(10)

async def rate_limited_llm_call(prompt: str):
    async with semaphore:
        # At most 10 concurrent calls
        return await call_openai(prompt)

async def process_batch(prompts: list[str]):
    tasks = [rate_limited_llm_call(p) for p in prompts]
    return await asyncio.gather(*tasks)
```

### Common Pitfalls

```python
# WRONG: This is sequential, not concurrent!
async def bad_parallel():
    result1 = await fetch_data("url1")  # Waits 1s
    result2 = await fetch_data("url2")  # Waits another 1s
    # Total: 2 seconds

# RIGHT: True concurrency
async def good_parallel():
    result1, result2 = await asyncio.gather(
        fetch_data("url1"),
        fetch_data("url2"),
    )
    # Total: 1 second

# WRONG: Blocking the event loop
async def blocks_everything():
    import time
    time.sleep(5)  # BLOCKS ALL OTHER COROUTINES

# RIGHT: Use run_in_executor for blocking code
async def non_blocking():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, time.sleep, 5)
```

---

## API Design Principles

### REST API Design

**Resource-oriented design:**
```
GET    /v1/models                    # List models
POST   /v1/models                    # Create model
GET    /v1/models/{id}               # Get model
PUT    /v1/models/{id}               # Replace model
PATCH  /v1/models/{id}               # Update model
DELETE /v1/models/{id}               # Delete model
GET    /v1/models/{id}/predictions   # Sub-resource
```

**Pagination:**
```json
{
  "data": [...],
  "meta": {
    "total": 1000,
    "page": 1,
    "per_page": 50,
    "next_cursor": "eyJpZCI6IDUwfQ=="
  }
}
```

**Cursor-based pagination** is preferred for large datasets (like embeddings or logs) because it's stable under concurrent writes.

### Streaming Responses (Server-Sent Events)

Critical for AI applications where LLM responses stream token-by-token:

```
GET /v1/chat/completions HTTP/1.1
Accept: text/event-stream

HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"choices": [{"delta": {"content": "Hello"}}]}

data: {"choices": [{"delta": {"content": " world"}}]}

data: [DONE]
```

### WebSocket Design

For bidirectional real-time communication (chat interfaces, collaborative editing):

```
Client → Server: {"type": "message", "content": "Hello", "conversation_id": "abc"}
Server → Client: {"type": "token", "content": "Hi", "message_id": "xyz"}
Server → Client: {"type": "token", "content": " there", "message_id": "xyz"}
Server → Client: {"type": "done", "message_id": "xyz", "usage": {"tokens": 15}}
```

### Idempotency

Every mutating operation should be idempotent in production AI systems:

```python
# Client sends idempotency key
POST /v1/completions
Idempotency-Key: req_abc123
Content-Type: application/json

{"prompt": "..."}

# Server checks if this key was already processed
# If yes: return cached response (no duplicate LLM call = no duplicate cost)
# If no: process and store result keyed by idempotency key
```

### API Versioning Strategy

```
/v1/completions          # URL versioning (clearest)
Accept: application/vnd.api+json;version=2  # Header versioning
```

---

## Database Patterns

### PostgreSQL for AI Systems

**What to store in PostgreSQL:**
- User accounts, API keys, billing
- Conversation history (structured)
- Model configurations and deployments
- Prompt templates with versions
- Evaluation results

**Key patterns:**

```sql
-- Conversation storage with JSONB for flexible metadata
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    token_count INTEGER,
    model TEXT,
    cost_usd DECIMAL(10, 6),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Partial index for active conversations
CREATE INDEX idx_conversations_active 
ON conversations(user_id, updated_at DESC) 
WHERE metadata->>'archived' IS NULL;

-- GIN index for JSONB queries
CREATE INDEX idx_messages_metadata ON messages USING GIN (metadata);
```

**Connection pooling with pgbouncer or async pools:**
- Each FastAPI worker needs its own connection pool
- Pool size = (2 * CPU cores) + number_of_disks (for PostgreSQL)
- Use `asyncpg` or `SQLAlchemy[asyncio]` for async access

### Redis Patterns for AI

```python
# 1. Response caching (semantic cache for LLM responses)
await redis.setex(
    f"llm:cache:{hash(prompt)}",
    ttl=3600,
    value=json.dumps(response)
)

# 2. Rate limiting (sliding window)
pipe = redis.pipeline()
now = time.time()
key = f"rate:{user_id}:{window}"
pipe.zremrangebyscore(key, 0, now - window_size)
pipe.zadd(key, {str(now): now})
pipe.zcard(key)
pipe.expire(key, window_size)
results = await pipe.execute()
request_count = results[2]

# 3. Distributed locks (for expensive operations)
async with redis.lock(f"embed:{document_id}", timeout=30):
    # Only one worker embeds this document
    embedding = await compute_embedding(document)

# 4. Pub/Sub for streaming tokens across workers
await redis.publish(f"stream:{request_id}", token)

# 5. Sorted sets for priority queues
await redis.zadd("inference_queue", {request_id: priority})
```

### Document Stores (MongoDB patterns)

Best for: storing variable-structure documents, embeddings with metadata, RAG chunks.

```javascript
// Chunk storage for RAG
{
  "_id": ObjectId("..."),
  "document_id": "doc_abc",
  "chunk_index": 3,
  "content": "The transformer architecture...",
  "embedding": [0.1, 0.2, ...],  // 1536 dimensions
  "metadata": {
    "source": "attention_paper.pdf",
    "page": 4,
    "section": "Architecture",
    "token_count": 256
  },
  "created_at": ISODate("2024-01-01")
}
```

---

## Container Orchestration Concepts

### Docker Best Practices for Python AI Apps

```dockerfile
# Multi-stage build
FROM python:3.12-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

# Non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Kubernetes Concepts

**Key resources for AI workloads:**
- **Deployment**: Stateless API servers (model serving endpoints)
- **StatefulSet**: Workers that need stable identity (embedding processors)
- **Job/CronJob**: Batch inference, model evaluation, data processing
- **HPA (Horizontal Pod Autoscaler)**: Scale based on request queue depth
- **PDB (Pod Disruption Budget)**: Ensure availability during rollouts
- **GPU scheduling**: `nvidia.com/gpu` resource requests

**Helm chart structure:**
```
my-ai-service/
├── Chart.yaml
├── values.yaml
├── values-production.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── configmap.yaml
│   └── secret.yaml
```

---

## Authentication & Authorization

### JWT Architecture

```
┌─────────┐     ┌──────────┐     ┌─────────────┐
│  Client  │────▶│  Auth    │────▶│  Token      │
│          │◀────│  Service │◀────│  Store      │
└─────────┘     └──────────┘     └─────────────┘
     │                                    
     │ Bearer Token                       
     ▼                                    
┌─────────────┐                           
│  API        │  Validates JWT locally    
│  Gateway    │  (no auth service call)   
└─────────────┘                           
```

**Token structure for AI APIs:**
```json
{
  "sub": "user_123",
  "org": "org_456",
  "scopes": ["models:read", "models:write", "completions:create"],
  "rate_limit_tier": "pro",
  "token_budget_remaining": 1000000,
  "exp": 1700000000
}
```

### API Key Management

For machine-to-machine (SDK access):
- Prefix keys for identification: `sk-proj-abc123...`
- Hash keys in storage (bcrypt or SHA-256)
- Support key rotation without downtime
- Track usage per key for billing

---

## Observability Fundamentals

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Every log line is JSON with correlation context
logger.info(
    "llm_completion_requested",
    user_id="user_123",
    model="gpt-4",
    prompt_tokens=500,
    request_id="req_abc",
    trace_id="trace_xyz"
)

# Output:
# {"event": "llm_completion_requested", "user_id": "user_123", 
#  "model": "gpt-4", "prompt_tokens": 500, "request_id": "req_abc",
#  "trace_id": "trace_xyz", "timestamp": "2024-01-01T00:00:00Z"}
```

### Distributed Tracing

```
[Client Request] ──▶ [API Gateway: 2ms]
                         │
                         ├──▶ [Auth Middleware: 1ms]
                         │
                         ├──▶ [Prompt Template: 3ms]
                         │
                         ├──▶ [Vector Search: 45ms]
                         │         │
                         │         └──▶ [Embedding API: 30ms]
                         │
                         ├──▶ [LLM Inference: 2100ms]
                         │
                         └──▶ [Response Streaming: 50ms]
                         
Total: 2201ms
```

### Key Metrics for AI Systems

```
# Latency percentiles
api_request_duration_seconds{endpoint="/v1/completions", quantile="0.99"}

# Token usage
llm_tokens_total{model="gpt-4", type="prompt"}
llm_tokens_total{model="gpt-4", type="completion"}

# Cost tracking
llm_cost_dollars_total{model="gpt-4", org="org_123"}

# Error rates
llm_errors_total{model="gpt-4", error_type="rate_limit"}
llm_errors_total{model="gpt-4", error_type="timeout"}

# Cache hit rates
cache_hits_total{cache="semantic"} / cache_requests_total{cache="semantic"}

# Queue depth (for async inference)
inference_queue_depth{priority="high"}
```

---

## Testing Strategy

| Layer | What | Tools | Speed |
|-------|------|-------|-------|
| Unit | Business logic, prompt templates, parsers | pytest, unittest.mock | < 1s |
| Integration | DB queries, Redis ops, API calls | testcontainers, pytest-asyncio | < 30s |
| Contract | API schema compatibility | schemathesis, pact | < 10s |
| Load | Throughput, latency under load | locust, k6 | minutes |
| Security | Auth bypass, injection, SSRF | bandit, safety, OWASP ZAP | minutes |
| E2E | Full user flows | playwright, httpx | minutes |

### Testing AI-specific concerns:
- **Prompt regression tests**: Assert that prompt changes don't degrade output quality
- **Cost tests**: Assert that a request doesn't exceed token budget
- **Latency SLA tests**: Assert P99 < threshold
- **Fallback tests**: Assert graceful degradation when LLM is unavailable

---

## Resilience Patterns

### Circuit Breaker

```
States: CLOSED → OPEN → HALF_OPEN → CLOSED

CLOSED:   All requests pass through. Track failure rate.
          If failure_rate > threshold → transition to OPEN

OPEN:     All requests fail immediately (no actual call).
          After timeout → transition to HALF_OPEN

HALF_OPEN: Allow limited requests through.
           If they succeed → transition to CLOSED
           If they fail → transition to OPEN
```

### Retry with Exponential Backoff + Jitter

```python
import random

def retry_delay(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    """Exponential backoff with full jitter."""
    delay = min(base * (2 ** attempt), max_delay)
    return random.uniform(0, delay)

# Attempt 0: 0-1s
# Attempt 1: 0-2s
# Attempt 2: 0-4s
# Attempt 3: 0-8s
# Attempt 4: 0-16s
```

### Bulkhead Pattern

Isolate failures to prevent cascade:

```python
# Separate thread/connection pools for different services
openai_semaphore = asyncio.Semaphore(20)      # Max 20 concurrent OpenAI calls
anthropic_semaphore = asyncio.Semaphore(15)   # Max 15 concurrent Anthropic calls
db_pool = create_pool(max_size=10)            # Max 10 DB connections

# If OpenAI is slow and consuming all 20 slots,
# Anthropic calls are unaffected
```

---

## Summary: The Foundation Checklist

Before adding any AI complexity, ensure you can answer YES to all:

- [ ] Can your API handle 1000 concurrent connections?
- [ ] Do you have sub-second health checks?
- [ ] Can you trace a request end-to-end across services?
- [ ] Do you have automated rollback on deployment failure?
- [ ] Is every external call wrapped in timeout + retry + circuit breaker?
- [ ] Can you rate-limit by user, org, and API key independently?
- [ ] Do you have cost alerts before hitting budget limits?
- [ ] Can your tests run in CI in under 5 minutes?
- [ ] Is your database schema versioned and migrated automatically?
- [ ] Can you rotate secrets without downtime?

Only when these foundations are solid should you layer on LLM calls, vector databases, embedding pipelines, and agent orchestration.
