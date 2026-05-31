# Redis Idempotency Keys — Deep Dive

## Why Idempotency Keys Matter

Network failures, client retries, and duplicate webhooks can cause the same operation to execute multiple times. Idempotency keys guarantee that repeating a request produces the same result as the first execution — critical for payments, order creation, and any non-reversible operation.

```
Client → [POST /charge] → Network timeout → Client retries → [POST /charge again]
                                                                    ↓
Without idempotency: Customer charged TWICE
With idempotency:    Second request returns cached first response
```

---

## Part 1: Core Idempotency Engine

### Basic Implementation

```python
import redis
import json
import hashlib
import time
import uuid
from enum import Enum
from typing import Optional, Any, Dict, Callable
from dataclasses import dataclass, asdict


class IdempotencyStatus(Enum):
    PENDING = "pending"       # Request is currently being processed
    COMPLETED = "completed"   # Request finished successfully
    FAILED = "failed"         # Request failed (may be retryable)


@dataclass
class IdempotencyRecord:
    key: str
    status: str
    request_fingerprint: str
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    created_at: float = 0.0
    completed_at: float = 0.0
    lock_token: Optional[str] = None
    attempt_count: int = 0


class RedisIdempotencyStore:
    """
    Core idempotency implementation using Redis Hash per key.
    
    Key design:
      idempotency:{key} → Hash with status, fingerprint, response, timestamps
    
    Lifecycle:
      1. Client sends request with Idempotency-Key header
      2. Check if key exists → return cached response if completed
      3. If pending → return 409 Conflict (another request in flight)
      4. If new → create PENDING record, process, store response
    """

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 86400):
        self.r = redis_client
        self.ttl = ttl_seconds  # 24 hours default retention
        self.prefix = "idempotency"

    def _key(self, idempotency_key: str) -> str:
        return f"{self.prefix}:{idempotency_key}"

    def _fingerprint(self, method: str, path: str, body: dict) -> str:
        """
        Create a request fingerprint to detect misuse
        (same idempotency key with different request body).
        """
        content = json.dumps({"method": method, "path": path, "body": body}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ─── Atomic acquire using Lua ────────────────────────────────────

    ACQUIRE_SCRIPT = """
    local key = KEYS[1]
    local fingerprint = ARGV[1]
    local lock_token = ARGV[2]
    local now = ARGV[3]
    local ttl = tonumber(ARGV[4])
    local lock_timeout = tonumber(ARGV[5])

    local existing = redis.call('HGETALL', key)

    -- Key doesn't exist → create PENDING record
    if #existing == 0 then
        redis.call('HSET', key,
            'status', 'pending',
            'request_fingerprint', fingerprint,
            'lock_token', lock_token,
            'created_at', now,
            'attempt_count', '1')
        redis.call('EXPIRE', key, ttl)
        return {'acquired', ''}
    end

    -- Parse existing hash into table
    local data = {}
    for i = 1, #existing, 2 do
        data[existing[i]] = existing[i+1]
    end

    -- Fingerprint mismatch → client reusing key for different request
    if data['request_fingerprint'] ~= fingerprint then
        return {'fingerprint_mismatch', ''}
    end

    -- Already completed → return cached response
    if data['status'] == 'completed' then
        local response = redis.call('HGET', key, 'response_body')
        return {'completed', response or ''}
    end

    -- Failed → allow retry (re-acquire)
    if data['status'] == 'failed' then
        redis.call('HSET', key,
            'status', 'pending',
            'lock_token', lock_token,
            'attempt_count', tostring(tonumber(data['attempt_count'] or '0') + 1))
        redis.call('EXPIRE', key, ttl)
        return {'acquired', ''}
    end

    -- Pending → check if lock expired (stale processor)
    if data['status'] == 'pending' then
        local created = tonumber(data['created_at'] or '0')
        local now_num = tonumber(now)
        if (now_num - created) > lock_timeout then
            -- Stale lock, take over
            redis.call('HSET', key,
                'status', 'pending',
                'lock_token', lock_token,
                'created_at', now,
                'attempt_count', tostring(tonumber(data['attempt_count'] or '0') + 1))
            return {'acquired', ''}
        end
        return {'in_progress', ''}
    end

    return {'unknown_state', ''}
    """

    def acquire(
        self,
        idempotency_key: str,
        method: str,
        path: str,
        body: dict,
        lock_timeout: int = 30
    ) -> tuple:
        """
        Attempt to acquire processing rights for this idempotency key.
        
        Returns:
            ("acquired", lock_token) — proceed with processing
            ("completed", cached_response) — return cached response to client
            ("in_progress", None) — another processor is handling this
            ("fingerprint_mismatch", None) — key reused with different request
        """
        fingerprint = self._fingerprint(method, path, body)
        lock_token = str(uuid.uuid4())
        now = str(time.time())

        result = self.r.execute_command(
            "EVAL", self.ACQUIRE_SCRIPT, 1,
            self._key(idempotency_key),
            fingerprint, lock_token, now,
            str(self.ttl), str(lock_timeout)
        )

        status = result[0].decode() if isinstance(result[0], bytes) else result[0]
        payload = result[1].decode() if isinstance(result[1], bytes) else result[1]

        if status == "acquired":
            return ("acquired", lock_token)
        elif status == "completed":
            return ("completed", json.loads(payload) if payload else None)
        elif status == "in_progress":
            return ("in_progress", None)
        elif status == "fingerprint_mismatch":
            return ("fingerprint_mismatch", None)
        else:
            return ("error", None)

    # ─── Complete: store response ────────────────────────────────────

    COMPLETE_SCRIPT = """
    local key = KEYS[1]
    local expected_token = ARGV[1]
    local response_code = ARGV[2]
    local response_body = ARGV[3]
    local now = ARGV[4]
    local ttl = tonumber(ARGV[5])

    local current_token = redis.call('HGET', key, 'lock_token')
    if current_token ~= expected_token then
        return 0  -- Lost the lock (stale processor)
    end

    redis.call('HSET', key,
        'status', 'completed',
        'response_code', response_code,
        'response_body', response_body,
        'completed_at', now)
    redis.call('EXPIRE', key, ttl)
    return 1
    """

    def complete(
        self,
        idempotency_key: str,
        lock_token: str,
        response_code: int,
        response_body: dict
    ) -> bool:
        """Mark request as completed with cached response."""
        result = self.r.execute_command(
            "EVAL", self.COMPLETE_SCRIPT, 1,
            self._key(idempotency_key),
            lock_token, str(response_code),
            json.dumps(response_body), str(time.time()), str(self.ttl)
        )
        return result == 1

    # ─── Fail: mark as retryable ─────────────────────────────────────

    FAIL_SCRIPT = """
    local key = KEYS[1]
    local expected_token = ARGV[1]
    local error_message = ARGV[2]
    local now = ARGV[3]
    local ttl = tonumber(ARGV[4])

    local current_token = redis.call('HGET', key, 'lock_token')
    if current_token ~= expected_token then
        return 0
    end

    redis.call('HSET', key,
        'status', 'failed',
        'error_message', error_message,
        'completed_at', now)
    redis.call('EXPIRE', key, ttl)
    return 1
    """

    def fail(self, idempotency_key: str, lock_token: str, error: str) -> bool:
        """Mark request as failed — allows client retry with same key."""
        result = self.r.execute_command(
            "EVAL", self.FAIL_SCRIPT, 1,
            self._key(idempotency_key),
            lock_token, error, str(time.time()), str(self.ttl)
        )
        return result == 1

    def get_record(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        """Retrieve the full idempotency record for debugging."""
        data = self.r.hgetall(self._key(idempotency_key))
        if not data:
            return None
        decoded = {k.decode(): v.decode() for k, v in data.items()}
        return IdempotencyRecord(
            key=idempotency_key,
            status=decoded.get("status", ""),
            request_fingerprint=decoded.get("request_fingerprint", ""),
            response_code=int(decoded["response_code"]) if "response_code" in decoded else None,
            response_body=decoded.get("response_body"),
            created_at=float(decoded.get("created_at", 0)),
            completed_at=float(decoded.get("completed_at", 0)),
            lock_token=decoded.get("lock_token"),
            attempt_count=int(decoded.get("attempt_count", 0))
        )
```

---

## Part 2: Payment Idempotency

### Stripe-Style Payment Processing

```python
@dataclass
class PaymentResult:
    charge_id: str
    amount: int
    currency: str
    status: str  # succeeded, failed, requires_action


class IdempotentPaymentProcessor:
    """
    Payment processing with idempotency — the highest-stakes use case.
    
    Critical properties:
      - A charge is NEVER executed twice for the same idempotency key
      - If the process crashes mid-charge, recovery is deterministic
      - Failed charges allow retry; successful charges return cached result
    
    Flow:
      1. Acquire idempotency lock
      2. Validate payment parameters
      3. Execute charge with payment gateway
      4. Store result atomically
      5. Return result (or cached result on replay)
    """

    def __init__(self, redis_client: redis.Redis):
        self.store = RedisIdempotencyStore(redis_client, ttl_seconds=172800)  # 48h for payments
        self.r = redis_client

    def process_payment(
        self,
        idempotency_key: str,
        customer_id: str,
        amount: int,
        currency: str,
        payment_method: str
    ) -> Dict[str, Any]:
        """
        Process a payment idempotently.
        
        The idempotency key should be generated by the client —
        typically a UUID stored in the client's local state.
        """
        request_body = {
            "customer_id": customer_id,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method
        }

        # Step 1: Acquire or retrieve cached
        status, payload = self.store.acquire(
            idempotency_key, "POST", "/v1/charges", request_body
        )

        if status == "completed":
            return {"status": "cached", "data": payload}

        if status == "in_progress":
            return {"status": "conflict", "message": "Request already being processed"}

        if status == "fingerprint_mismatch":
            return {"status": "error", "message": "Idempotency key already used for different request"}

        lock_token = payload  # From "acquired" status

        # Step 2: Validate
        if amount <= 0:
            self.store.fail(idempotency_key, lock_token, "Invalid amount")
            return {"status": "error", "message": "Amount must be positive"}

        # Step 3: Execute the actual charge
        try:
            charge_result = self._execute_charge(customer_id, amount, currency, payment_method)
        except PaymentGatewayError as e:
            if e.is_retryable:
                # Mark as failed so client can retry with same key
                self.store.fail(idempotency_key, lock_token, str(e))
                return {"status": "error", "message": str(e), "retryable": True}
            else:
                # Non-retryable failure — cache the failure response
                failure_response = {"error": str(e), "retryable": False}
                self.store.complete(idempotency_key, lock_token, 402, failure_response)
                return {"status": "failed", "data": failure_response}

        # Step 4: Store success
        success_response = {
            "charge_id": charge_result.charge_id,
            "amount": charge_result.amount,
            "currency": charge_result.currency,
            "status": charge_result.status
        }
        self.store.complete(idempotency_key, lock_token, 200, success_response)

        return {"status": "success", "data": success_response}

    def _execute_charge(self, customer_id, amount, currency, payment_method) -> PaymentResult:
        """Placeholder for actual payment gateway call."""
        # In production, this calls Stripe/Adyen/etc.
        return PaymentResult(
            charge_id=f"ch_{uuid.uuid4().hex[:16]}",
            amount=amount,
            currency=currency,
            status="succeeded"
        )


class PaymentGatewayError(Exception):
    def __init__(self, message: str, is_retryable: bool = False):
        super().__init__(message)
        self.is_retryable = is_retryable
```

---

## Part 3: HTTP Middleware Pattern

### Framework-Agnostic Idempotency Middleware

```python
from functools import wraps


class IdempotencyMiddleware:
    """
    Middleware that intercepts requests with Idempotency-Key header
    and applies idempotency logic transparently.
    
    Usage with Flask:
        @app.route('/orders', methods=['POST'])
        @idempotency_middleware.protect
        def create_order():
            ...  # Only executes once per idempotency key
    
    Usage with FastAPI:
        @router.post('/orders')
        @idempotency_middleware.protect
        async def create_order(request: Request):
            ...
    """

    def __init__(self, redis_client: redis.Redis, ttl: int = 86400):
        self.store = RedisIdempotencyStore(redis_client, ttl_seconds=ttl)

    def protect(self, handler: Callable):
        """Decorator that adds idempotency to a route handler."""

        @wraps(handler)
        def wrapper(*args, **kwargs):
            # Extract idempotency key from request context
            # (Framework-specific — shown here as generic)
            request = self._get_request_from_context(args, kwargs)
            idem_key = request.headers.get("Idempotency-Key")

            if not idem_key:
                # No idempotency key — process normally (non-idempotent)
                return handler(*args, **kwargs)

            # Validate key format
            if len(idem_key) > 256 or len(idem_key) < 8:
                return self._error_response(400, "Invalid Idempotency-Key length")

            body = request.get_json() or {}
            method = request.method
            path = request.path

            status, payload = self.store.acquire(idem_key, method, path, body)

            if status == "completed":
                return self._cached_response(payload)

            if status == "in_progress":
                return self._error_response(
                    409, "A request with this idempotency key is already being processed"
                )

            if status == "fingerprint_mismatch":
                return self._error_response(
                    422, "Idempotency key already used for a different request"
                )

            lock_token = payload

            # Execute the actual handler
            try:
                response = handler(*args, **kwargs)
                response_data = self._extract_response_data(response)
                self.store.complete(idem_key, lock_token, response_data["code"], response_data["body"])
                return response
            except Exception as e:
                self.store.fail(idem_key, lock_token, str(e))
                raise

        return wrapper

    def _get_request_from_context(self, args, kwargs):
        """Override per framework."""
        raise NotImplementedError

    def _error_response(self, code: int, message: str):
        raise NotImplementedError

    def _cached_response(self, data: dict):
        raise NotImplementedError

    def _extract_response_data(self, response) -> dict:
        raise NotImplementedError


# ─── Flask Implementation ────────────────────────────────────────────

class FlaskIdempotencyMiddleware(IdempotencyMiddleware):
    """Concrete implementation for Flask."""

    def _get_request_from_context(self, args, kwargs):
        from flask import request
        return request

    def _error_response(self, code, message):
        from flask import jsonify
        return jsonify({"error": message}), code

    def _cached_response(self, data):
        from flask import jsonify
        response = jsonify(data.get("body", data))
        response.headers["X-Idempotency-Replayed"] = "true"
        return response, data.get("code", 200)

    def _extract_response_data(self, response):
        if isinstance(response, tuple):
            body, code = response[0], response[1]
        else:
            body, code = response, 200
        return {"body": body.get_json() if hasattr(body, 'get_json') else body, "code": code}
```

---

## Part 4: Request Fingerprinting Strategies

### Preventing Key Misuse

```python
class RequestFingerprinter:
    """
    Detects when a client reuses an idempotency key for a different request.
    
    This is critical for correctness: if a client sends:
      POST /charge {amount: 100} with key "abc"
    then later:
      POST /charge {amount: 200} with key "abc"
    
    The second request MUST be rejected — returning the first response
    for a different request body would be incorrect and dangerous.
    """

    @staticmethod
    def full_body_fingerprint(method: str, path: str, body: dict) -> str:
        """Hash the entire request. Strictest — any difference is rejected."""
        canonical = json.dumps(
            {"m": method, "p": path, "b": body},
            sort_keys=True, separators=(',', ':')
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @staticmethod
    def semantic_fingerprint(method: str, path: str, body: dict, key_fields: list) -> str:
        """
        Hash only semantically meaningful fields.
        
        Useful when the body contains timestamps, request IDs, or metadata
        that changes on retry but doesn't affect the operation.
        
        Example for a payment: key_fields = ['amount', 'currency', 'customer_id']
        Ignores: 'request_timestamp', 'client_trace_id'
        """
        relevant = {k: body.get(k) for k in sorted(key_fields) if k in body}
        canonical = json.dumps(
            {"m": method, "p": path, "b": relevant},
            sort_keys=True, separators=(',', ':')
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @staticmethod
    def path_only_fingerprint(method: str, path: str) -> str:
        """
        Weakest — only checks method and path match.
        Suitable for operations where body variation is expected on retry.
        """
        canonical = f"{method}:{path}"
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

---

## Part 5: Concurrent Request Handling

### Dealing with Rapid Duplicate Requests

```python
class ConcurrentIdempotencyHandler:
    """
    Handles the race condition where the same idempotency key arrives
    multiple times within milliseconds (e.g., user double-clicks).
    
    Strategy: First request acquires a short-lived lock. Subsequent
    requests poll for the result with exponential backoff.
    """

    def __init__(self, redis_client: redis.Redis):
        self.store = RedisIdempotencyStore(redis_client)
        self.r = redis_client

    def process_with_wait(
        self,
        idempotency_key: str,
        method: str,
        path: str,
        body: dict,
        processor: Callable,
        max_wait: float = 5.0
    ) -> Dict[str, Any]:
        """
        If the key is in-progress, wait for completion instead of
        immediately returning 409.
        
        This improves UX for rapid retries where the client can't
        easily handle "try again later" responses.
        """
        status, payload = self.store.acquire(idempotency_key, method, path, body)

        if status == "acquired":
            lock_token = payload
            try:
                result = processor()
                self.store.complete(idempotency_key, lock_token, 200, result)
                return {"status": "success", "data": result}
            except Exception as e:
                self.store.fail(idempotency_key, lock_token, str(e))
                raise

        if status == "completed":
            return {"status": "cached", "data": payload}

        if status == "in_progress":
            return self._wait_for_completion(idempotency_key, max_wait)

        return {"status": "error", "message": status}

    def _wait_for_completion(self, idempotency_key: str, max_wait: float) -> dict:
        """Poll with exponential backoff until the key transitions to completed/failed."""
        elapsed = 0.0
        interval = 0.05  # Start at 50ms

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            record = self.store.get_record(idempotency_key)
            if record is None:
                return {"status": "error", "message": "Record disappeared"}

            if record.status == "completed":
                data = json.loads(record.response_body) if record.response_body else None
                return {"status": "cached", "data": data}

            if record.status == "failed":
                return {"status": "error", "message": "Original request failed", "retryable": True}

            interval = min(interval * 2, 0.5)  # Cap at 500ms

        return {"status": "timeout", "message": "Original request still processing"}


# ─── Pub/Sub notification for faster completion detection ────────────

class PubSubIdempotencyNotifier:
    """
    Instead of polling, use Redis Pub/Sub to notify waiting clients
    the instant a key completes. Much lower latency than polling.
    """

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self.channel_prefix = "idempotency:done"

    def notify_complete(self, idempotency_key: str, result: dict):
        """Called by the processor when done."""
        channel = f"{self.channel_prefix}:{idempotency_key}"
        self.r.publish(channel, json.dumps(result))

    def wait_for_completion(self, idempotency_key: str, timeout: float = 5.0) -> Optional[dict]:
        """Block until notification arrives or timeout."""
        channel = f"{self.channel_prefix}:{idempotency_key}"
        pubsub = self.r.pubsub()
        pubsub.subscribe(channel)

        try:
            deadline = time.time() + timeout
            for message in pubsub.listen():
                if time.time() > deadline:
                    return None
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    return json.loads(data)
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

        return None
```

---

## Part 6: Distributed Idempotency (Multi-Service)

### Cross-Service Idempotency with Outbox Pattern

```python
class DistributedIdempotencyCoordinator:
    """
    When a single client request triggers multiple downstream services,
    each service needs its own idempotency guarantee.
    
    Pattern: Derive child idempotency keys from the parent key.
    
    Client key: "order-abc-123"
    → Payment service key: "order-abc-123:payment"
    → Inventory service key: "order-abc-123:inventory"  
    → Notification service key: "order-abc-123:notification"
    
    This ensures:
    1. Retrying the parent retries all children with the same derived keys
    2. Each child service independently deduplicates
    3. Partial failures can be retried without re-executing successful steps
    """

    def __init__(self, redis_client: redis.Redis):
        self.store = RedisIdempotencyStore(redis_client, ttl_seconds=172800)
        self.r = redis_client

    def derive_child_key(self, parent_key: str, service: str, operation: str) -> str:
        """Deterministically derive a child key from parent."""
        raw = f"{parent_key}:{service}:{operation}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def execute_saga(
        self,
        parent_key: str,
        steps: list  # List of (service_name, operation_name, callable)
    ) -> Dict[str, Any]:
        """
        Execute a multi-step saga with per-step idempotency.
        
        Each step is independently idempotent — if the saga is retried,
        completed steps return cached results and only pending/failed
        steps are re-executed.
        """
        results = {}
        completed_steps = []

        for service_name, operation_name, executor in steps:
            child_key = self.derive_child_key(parent_key, service_name, operation_name)

            # Check if this step already completed
            status, payload = self.store.acquire(
                child_key, "INTERNAL", f"/{service_name}/{operation_name}",
                {"parent_key": parent_key}
            )

            if status == "completed":
                results[f"{service_name}:{operation_name}"] = payload
                completed_steps.append((service_name, operation_name))
                continue

            if status != "acquired":
                return {
                    "status": "error",
                    "message": f"Cannot acquire {service_name}:{operation_name}",
                    "completed_steps": completed_steps
                }

            lock_token = payload

            try:
                step_result = executor(results)  # Pass previous results for chaining
                self.store.complete(child_key, lock_token, 200, step_result)
                results[f"{service_name}:{operation_name}"] = step_result
                completed_steps.append((service_name, operation_name))
            except Exception as e:
                self.store.fail(child_key, lock_token, str(e))
                return {
                    "status": "partial_failure",
                    "failed_step": f"{service_name}:{operation_name}",
                    "error": str(e),
                    "completed_steps": completed_steps
                }

        return {"status": "success", "results": results}


# ─── Usage Example ───────────────────────────────────────────────────

def create_order_saga(coordinator: DistributedIdempotencyCoordinator, parent_key: str, order: dict):
    steps = [
        ("payment", "charge", lambda prev: charge_customer(order)),
        ("inventory", "reserve", lambda prev: reserve_items(order, prev)),
        ("notification", "confirm", lambda prev: send_confirmation(order, prev)),
    ]
    return coordinator.execute_saga(parent_key, steps)
```

---

## Part 7: Idempotency Key Generation

### Client-Side Key Strategies

```python
class IdempotencyKeyGenerator:
    """
    The idempotency key should be generated CLIENT-SIDE and stored
    in the client's local state. This ensures retries use the same key.
    
    Key properties:
      - Unique per logical operation
      - Deterministic for the same user action
      - Survives page refreshes and app restarts
    """

    @staticmethod
    def uuid_key() -> str:
        """
        Simple UUID — generated once per user action, stored in client state.
        Best for: Generic API calls, one-off operations.
        """
        return str(uuid.uuid4())

    @staticmethod
    def deterministic_key(user_id: str, action: str, params: dict) -> str:
        """
        Derived from the operation — same inputs always produce same key.
        
        Best for: Operations where the client might lose its state
        (e.g., mobile app killed mid-request). User retrying the same
        action naturally produces the same key.
        
        Risk: Window collisions — user intentionally doing the same
        action twice (e.g., buying the same item again) gets deduplicated.
        Mitigate with a time window component.
        """
        window = int(time.time() // 300)  # 5-minute window
        content = json.dumps(
            {"u": user_id, "a": action, "p": params, "w": window},
            sort_keys=True
        )
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    @staticmethod
    def scoped_key(user_id: str, resource: str, operation: str) -> str:
        """
        Scoped to user + resource + operation.
        
        Best for: CRUD operations where you want at-most-once per
        user per resource per time window.
        
        Example: User can only create one order per cart per minute.
        """
        window = int(time.time() // 60)  # 1-minute window
        content = f"{user_id}:{resource}:{operation}:{window}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
```

---

## Part 8: Cleanup and Garbage Collection

### Managing Idempotency Key Lifecycle

```python
class IdempotencyKeyManager:
    """
    Manages the lifecycle of idempotency records:
    - Active keys: being processed or recently completed
    - Stale keys: pending for too long (crashed processor)
    - Expired keys: handled by Redis TTL, but may need manual intervention
    """

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self.prefix = "idempotency"

    # ─── Stale lock recovery ─────────────────────────────────────────

    RECOVER_STALE_SCRIPT = """
    local cursor = ARGV[1]
    local prefix = ARGV[2]
    local max_age = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])
    local batch_size = tonumber(ARGV[5])

    local result = redis.call('SCAN', cursor, 'MATCH', prefix .. ':*', 'COUNT', batch_size)
    local new_cursor = result[1]
    local keys = result[2]
    local recovered = 0

    for _, key in ipairs(keys) do
        local status = redis.call('HGET', key, 'status')
        if status == 'pending' then
            local created = tonumber(redis.call('HGET', key, 'created_at') or '0')
            if (now - created) > max_age then
                redis.call('HSET', key, 'status', 'failed', 'error_message', 'stale_lock_recovered')
                recovered = recovered + 1
            end
        end
    end

    return {new_cursor, tostring(recovered)}
    """

    def recover_stale_locks(self, max_age_seconds: int = 60, batch_size: int = 100) -> int:
        """
        Find and recover keys stuck in PENDING state (crashed processor).
        Mark them as FAILED so clients can retry.
        
        Run this periodically (e.g., every 30 seconds) as a background job.
        """
        total_recovered = 0
        cursor = "0"

        while True:
            result = self.r.execute_command(
                "EVAL", self.RECOVER_STALE_SCRIPT, 0,
                cursor, self.prefix, str(max_age_seconds),
                str(time.time()), str(batch_size)
            )

            cursor = result[0].decode() if isinstance(result[0], bytes) else str(result[0])
            recovered = int(result[1].decode() if isinstance(result[1], bytes) else result[1])
            total_recovered += recovered

            if cursor == "0":
                break

        return total_recovered

    # ─── Metrics and monitoring ──────────────────────────────────────

    def get_stats(self) -> dict:
        """Get counts of keys by status for monitoring dashboards."""
        stats = {"pending": 0, "completed": 0, "failed": 0, "total": 0}
        cursor = 0

        while True:
            cursor, keys = self.r.scan(cursor, match=f"{self.prefix}:*", count=500)
            if keys:
                pipe = self.r.pipeline(transaction=False)
                for key in keys:
                    pipe.hget(key, "status")
                statuses = pipe.execute()

                for s in statuses:
                    if s:
                        status = s.decode() if isinstance(s, bytes) else s
                        stats[status] = stats.get(status, 0) + 1
                    stats["total"] += 1

            if cursor == 0:
                break

        return stats

    def purge_completed(self, older_than_hours: int = 24) -> int:
        """
        Manually purge completed keys older than threshold.
        Normally Redis TTL handles this, but useful for bulk cleanup
        or reducing memory pressure.
        """
        threshold = time.time() - (older_than_hours * 3600)
        purged = 0
        cursor = 0

        while True:
            cursor, keys = self.r.scan(cursor, match=f"{self.prefix}:*", count=500)
            if keys:
                pipe = self.r.pipeline(transaction=False)
                for key in keys:
                    pipe.hmget(key, "status", "completed_at")
                results = pipe.execute()

                to_delete = []
                for key, (status, completed_at) in zip(keys, results):
                    if status and status.decode() == "completed":
                        if completed_at and float(completed_at.decode()) < threshold:
                            to_delete.append(key)

                if to_delete:
                    self.r.delete(*to_delete)
                    purged += len(to_delete)

            if cursor == 0:
                break

        return purged
```

---

## Part 9: Webhook Deduplication

### Idempotency for Incoming Webhooks

```python
class WebhookDeduplicator:
    """
    External services (Stripe, Twilio, GitHub) may deliver webhooks
    multiple times. Use idempotency to process each event exactly once.
    
    Key difference from API idempotency:
    - Key is derived from the webhook event ID (set by the sender)
    - No response caching needed (webhooks are fire-and-forget)
    - Focus is on ensuring side effects happen exactly once
    """

    def __init__(self, redis_client: redis.Redis, ttl_hours: int = 72):
        self.r = redis_client
        self.ttl = ttl_hours * 3600
        self.prefix = "webhook:seen"

    # ─── Atomic check-and-mark ───────────────────────────────────────

    DEDUP_SCRIPT = """
    local key = KEYS[1]
    local ttl = tonumber(ARGV[1])
    local now = ARGV[2]

    local exists = redis.call('EXISTS', key)
    if exists == 1 then
        -- Already processed — increment duplicate counter
        redis.call('HINCRBY', key, 'duplicate_count', 1)
        redis.call('HSET', key, 'last_duplicate_at', now)
        return 0  -- Duplicate
    end

    -- First time seeing this event
    redis.call('HSET', key,
        'first_seen_at', now,
        'processed', '0',
        'duplicate_count', '0')
    redis.call('EXPIRE', key, ttl)
    return 1  -- New event
    """

    def is_new_event(self, event_id: str) -> bool:
        """
        Atomically check if this webhook event has been seen before.
        Returns True if this is the first delivery, False if duplicate.
        """
        key = f"{self.prefix}:{event_id}"
        result = self.r.execute_command(
            "EVAL", self.DEDUP_SCRIPT, 1,
            key, str(self.ttl), str(time.time())
        )
        return result == 1

    def mark_processed(self, event_id: str):
        """Mark event as successfully processed (for monitoring)."""
        key = f"{self.prefix}:{event_id}"
        self.r.hset(key, mapping={
            "processed": "1",
            "processed_at": str(time.time())
        })

    def process_webhook(self, event_id: str, event_type: str, payload: dict, handler: Callable):
        """
        Full webhook processing flow with deduplication.
        
        Usage:
            deduplicator.process_webhook(
                event_id="evt_123abc",
                event_type="payment.succeeded",
                payload={...},
                handler=handle_payment_success
            )
        """
        if not self.is_new_event(event_id):
            # Duplicate delivery — acknowledge but don't process
            return {"status": "duplicate", "event_id": event_id}

        try:
            handler(event_type, payload)
            self.mark_processed(event_id)
            return {"status": "processed", "event_id": event_id}
        except Exception as e:
            # Remove the seen marker so the next delivery can retry
            self.r.delete(f"{self.prefix}:{event_id}")
            raise


# ─── Ordered webhook processing ─────────────────────────────────────

class OrderedWebhookProcessor:
    """
    Some webhooks must be processed in order (e.g., subscription events:
    created → updated → cancelled). Use Redis to enforce ordering.
    
    Each entity gets a sequence counter. Events are only processed
    if their sequence number is the expected next value.
    """

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self.dedup = WebhookDeduplicator(redis_client)

    ORDERED_PROCESS_SCRIPT = """
    local seq_key = KEYS[1]
    local event_key = KEYS[2]
    local expected_seq = tonumber(ARGV[1])
    local ttl = tonumber(ARGV[2])
    local now = ARGV[3]

    -- Check current sequence for this entity
    local current_seq = tonumber(redis.call('GET', seq_key) or '0')

    if expected_seq <= current_seq then
        return -1  -- Already processed (out-of-order duplicate)
    end

    if expected_seq > current_seq + 1 then
        return 0  -- Gap — earlier events haven't arrived yet, buffer this
    end

    -- expected_seq == current_seq + 1: Process in order
    redis.call('SET', seq_key, tostring(expected_seq))
    redis.call('EXPIRE', seq_key, ttl)
    redis.call('HSET', event_key, 'processed', '1', 'processed_at', now)
    return 1  -- Process this event
    """

    def process_ordered(
        self,
        entity_id: str,
        event_id: str,
        sequence: int,
        handler: Callable
    ) -> str:
        """
        Process an event only if it's the next expected sequence.
        Returns: 'processed', 'duplicate', or 'buffered'
        """
        seq_key = f"webhook:seq:{entity_id}"
        event_key = f"webhook:seen:{event_id}"

        result = self.r.execute_command(
            "EVAL", self.ORDERED_PROCESS_SCRIPT, 2,
            seq_key, event_key,
            str(sequence), str(259200), str(time.time())  # 72h TTL
        )

        if result == 1:
            handler()
            return "processed"
        elif result == -1:
            return "duplicate"
        else:
            # Buffer for later processing when gap fills
            self.r.zadd(f"webhook:buffer:{entity_id}", {event_id: sequence})
            return "buffered"
```

---

## Part 10: Testing Idempotency

### Comprehensive Test Patterns

```python
class IdempotencyTestSuite:
    """
    Test patterns for verifying idempotency correctness.
    These should be part of your integration test suite.
    """

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client
        self.store = RedisIdempotencyStore(redis_client, ttl_seconds=60)

    def test_basic_idempotency(self):
        """Same key + same body → same result, no re-execution."""
        key = f"test-{uuid.uuid4()}"
        body = {"amount": 100}
        call_count = 0

        def processor():
            nonlocal call_count
            call_count += 1
            return {"charge_id": "ch_123"}

        # First call — processes
        status1, payload1 = self.store.acquire(key, "POST", "/charge", body)
        assert status1 == "acquired"
        result = processor()
        self.store.complete(key, payload1, 200, result)

        # Second call — returns cached
        status2, payload2 = self.store.acquire(key, "POST", "/charge", body)
        assert status2 == "completed"
        assert payload2 == {"charge_id": "ch_123"}
        assert call_count == 1  # Processor only called once

    def test_fingerprint_mismatch(self):
        """Same key + different body → rejected."""
        key = f"test-{uuid.uuid4()}"

        # First request
        status1, _ = self.store.acquire(key, "POST", "/charge", {"amount": 100})
        assert status1 == "acquired"

        # Same key, different body
        status2, _ = self.store.acquire(key, "POST", "/charge", {"amount": 200})
        assert status2 == "fingerprint_mismatch"

    def test_failed_allows_retry(self):
        """Failed request → same key can be retried."""
        key = f"test-{uuid.uuid4()}"
        body = {"amount": 100}

        # First attempt — fails
        status1, token1 = self.store.acquire(key, "POST", "/charge", body)
        assert status1 == "acquired"
        self.store.fail(key, token1, "gateway_timeout")

        # Retry — should re-acquire
        status2, token2 = self.store.acquire(key, "POST", "/charge", body)
        assert status2 == "acquired"
        assert token2 != token1  # New lock token

    def test_concurrent_requests(self):
        """Two simultaneous requests — only one processes."""
        key = f"test-{uuid.uuid4()}"
        body = {"amount": 100}

        # First acquires
        status1, token1 = self.store.acquire(key, "POST", "/charge", body)
        assert status1 == "acquired"

        # Second blocked while first is processing
        status2, _ = self.store.acquire(key, "POST", "/charge", body)
        assert status2 == "in_progress"

    def test_stale_lock_recovery(self):
        """Crashed processor lock is recovered after timeout."""
        key = f"test-{uuid.uuid4()}"
        body = {"amount": 100}

        # Simulate a request that started 60s ago (lock_timeout = 30)
        self.r.hset(f"idempotency:{key}", mapping={
            "status": "pending",
            "request_fingerprint": hashlib.sha256(
                json.dumps({"method": "POST", "path": "/charge", "body": body}, sort_keys=True).encode()
            ).hexdigest()[:16],
            "lock_token": "stale-token",
            "created_at": str(time.time() - 60),
            "attempt_count": "1"
        })

        # New request should take over the stale lock
        status, token = self.store.acquire(key, "POST", "/charge", body, lock_timeout=30)
        assert status == "acquired"
```

---

## Production Considerations

| Concern | Recommendation |
|---------|---------------|
| **Key TTL** | 24h for API calls, 48-72h for payments, 72h for webhooks |
| **Key format** | UUID v4 (client-generated) or deterministic hash (server-derived) |
| **Lock timeout** | 30-60s for API, 120s for long-running operations |
| **Memory** | ~500 bytes per key. 1M keys ≈ 500MB. Set aggressive TTLs |
| **Persistence** | Use AOF with `appendfsync everysec` — losing a completed key means re-processing |
| **Replication** | Use Redis Sentinel/Cluster. WAIT command for strong consistency on writes |
| **Monitoring** | Alert on: pending keys > 60s old, duplicate rate spikes, memory growth |
| **Client SDKs** | Generate key before first attempt, store in local state, reuse on retry |
| **Response size** | Cap cached responses at 1MB. For larger, store in S3 and cache a pointer |
| **Cluster mode** | All operations per key use single hash slot — no cross-slot issues |

---

## Decision Matrix: When to Use Each Pattern

| Scenario | Pattern | Key Source |
|----------|---------|-----------|
| API mutation (POST/PUT/DELETE) | Full idempotency with response cache | Client-generated UUID |
| Payment processing | Full idempotency + 48h TTL + failure allows retry | Client UUID, stored pre-submit |
| Webhook deduplication | Simple seen-set (no response cache) | Event ID from sender |
| Saga / multi-step | Derived child keys from parent | Parent key + step name |
| Background job | Job-specific dedup | Job ID or content hash |
| Form submission | Deterministic key from form data | Hash of user + form + time window |

---

## Common Pitfalls

1. **Server-generated keys**: If the server generates the idempotency key, a network failure before the client receives it means the client can't retry with the same key. Always generate client-side.

2. **GET requests**: Never apply idempotency to reads. GET is already idempotent by definition.

3. **Non-deterministic processing**: If your processor uses `time.time()` or `random()`, the cached response won't match what a re-execution would produce. This is fine — idempotency guarantees same-result, meaning the response from the first execution.

4. **TTL too short**: If the key expires before the client retries, the operation executes again. For payments, use 48h minimum.

5. **No fingerprint validation**: Without checking the request body matches, a reused key with different parameters returns incorrect cached data.

6. **Forgetting to handle PENDING state**: A crashed processor leaves keys in PENDING forever without stale lock recovery.
