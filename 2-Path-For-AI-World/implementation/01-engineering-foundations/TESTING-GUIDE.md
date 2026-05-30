# Testing Guide - Engineering Foundations

## Testing Philosophy

> "If you can't test it, you can't trust it in production — especially when each untested call costs real money (LLM tokens)."

Testing pyramid for AI-powered services:

```
         /  E2E  \          ← Few, expensive, slow
        / Contract \        ← API compatibility
       / Integration \      ← DB, Redis, external APIs
      /    Unit Tests  \    ← Many, fast, cheap
     /____________________\
```

---

## 1. Unit Tests with pytest

### Project Structure

```
tests/
├── conftest.py              # Shared fixtures
├── factories.py             # Test data factories
├── unit/
│   ├── test_circuit_breaker.py
│   ├── test_rate_limiter.py
│   ├── test_auth_service.py
│   ├── test_cache_service.py
│   └── test_models.py
├── integration/
│   ├── test_api_endpoints.py
│   ├── test_database.py
│   └── test_redis.py
├── contract/
│   └── test_api_schema.py
├── load/
│   └── locustfile.py
└── security/
    └── test_security.py
```

### conftest.py - Shared Fixtures

```python
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from IMPLEMENTATION import app, Base, get_db, get_redis, Settings


# Use a single event loop for all async tests
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Testcontainers for real database testing
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest_asyncio.fixture
async def db_session(postgres_container) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client(redis_container):
    """Provide a clean Redis client for each test."""
    import redis.asyncio as aioredis
    
    url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}"
    client = aioredis.from_url(url, decode_responses=True)
    yield client
    await client.flushall()
    await client.close()


@pytest_asyncio.fixture
async def client(db_session, redis_client) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with overridden dependencies."""
    
    async def override_get_db():
        yield db_session
    
    async def override_get_redis():
        return redis_client
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Provide valid auth headers for protected endpoints."""
    from IMPLEMENTATION import AuthService
    token = AuthService.create_token("test-user-id", "test@example.com", "pro")
    return {"Authorization": f"Bearer {token.access_token}"}


@pytest.fixture
def sample_user_data():
    return {"email": f"test-{uuid.uuid4().hex[:8]}@example.com", "password": "securepass123"}
```

### Unit Test: Circuit Breaker

```python
# tests/unit/test_circuit_breaker.py
import asyncio
import pytest
from IMPLEMENTATION import CircuitBreaker, CircuitState, CircuitBreakerOpenError


class TestCircuitBreaker:
    """Test circuit breaker state transitions and behavior."""
    
    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=1,  # 1 second for fast tests
            half_open_max_calls=2,
        )
    
    @pytest.mark.asyncio
    async def test_starts_closed(self, breaker):
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self, breaker):
        async def success():
            return "ok"
        
        result = await breaker.call(success)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, breaker):
        async def failure():
            raise ValueError("service down")
        
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failure)
        
        assert breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_open_circuit_fails_fast(self, breaker):
        async def failure():
            raise ValueError("service down")
        
        # Trip the breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failure)
        
        # Next call should fail immediately without calling the function
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failure)
    
    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self, breaker):
        async def failure():
            raise ValueError("service down")
        
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failure)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        assert breaker.state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self, breaker):
        async def failure():
            raise ValueError("down")
        
        async def success():
            return "ok"
        
        # Trip the breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failure)
        
        # Wait for recovery
        await asyncio.sleep(1.1)
        
        # Successful calls in half-open should close it
        await breaker.call(success)
        await breaker.call(success)
        
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self, breaker):
        async def failure():
            raise ValueError("still down")
        
        # Trip the breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failure)
        
        await asyncio.sleep(1.1)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Failure in half-open reopens
        with pytest.raises(ValueError):
            await breaker.call(failure)
        
        assert breaker.state == CircuitState.OPEN
```

### Unit Test: Rate Limiter

```python
# tests/unit/test_rate_limiter.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from IMPLEMENTATION import RateLimiter


class TestRateLimiter:
    
    @pytest.mark.asyncio
    async def test_allows_within_limit(self, redis_client):
        limiter = RateLimiter(redis_client)
        
        allowed, headers = await limiter.check_rate_limit("user1", "free")
        
        assert allowed is True
        assert int(headers["X-RateLimit-Remaining"]) == 59
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, redis_client):
        limiter = RateLimiter(redis_client)
        
        # Exhaust the limit
        for _ in range(61):
            await limiter.check_rate_limit("user2", "free")
        
        allowed, headers = await limiter.check_rate_limit("user2", "free")
        
        assert allowed is False
        assert headers["X-RateLimit-Remaining"] == "0"
    
    @pytest.mark.asyncio
    async def test_pro_tier_has_higher_limit(self, redis_client):
        limiter = RateLimiter(redis_client)
        
        # 100 requests should be fine for pro tier (600 limit)
        for _ in range(100):
            allowed, _ = await limiter.check_rate_limit("user3", "pro")
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_different_users_independent(self, redis_client):
        limiter = RateLimiter(redis_client)
        
        # Exhaust user_a
        for _ in range(61):
            await limiter.check_rate_limit("user_a", "free")
        
        # user_b should be unaffected
        allowed, _ = await limiter.check_rate_limit("user_b", "free")
        assert allowed is True
```

### Unit Test: Auth Service

```python
# tests/unit/test_auth_service.py
import time
import pytest
from IMPLEMENTATION import AuthService, settings


class TestAuthService:
    
    def test_create_token_returns_valid_jwt(self):
        token = AuthService.create_token("user_123", "test@example.com", "pro")
        
        assert token.access_token is not None
        assert token.token_type == "bearer"
        assert token.expires_in == settings.jwt_expiration_minutes * 60
    
    def test_verify_valid_token(self):
        token = AuthService.create_token("user_123", "test@example.com", "pro")
        payload = AuthService.verify_token(token.access_token)
        
        assert payload["sub"] == "user_123"
        assert payload["email"] == "test@example.com"
        assert payload["tier"] == "pro"
    
    def test_verify_expired_token_raises(self):
        import jwt as pyjwt
        from datetime import datetime, timezone, timedelta
        
        payload = {
            "sub": "user_123",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            AuthService.verify_token(expired_token)
        assert exc_info.value.status_code == 401
    
    def test_verify_invalid_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            AuthService.verify_token("invalid.token.here")
        assert exc_info.value.status_code == 401
```

---

## 2. Integration Tests

```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    
    @pytest.mark.asyncio
    async def test_liveness(self, client: AsyncClient):
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
    
    @pytest.mark.asyncio
    async def test_readiness(self, client: AsyncClient):
        response = await client.get("/health/ready")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_full_health(self, client: AsyncClient):
        response = await client.get("/health")
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "database" in data["checks"]
        assert "redis" in data["checks"]


class TestAuthEndpoints:
    
    @pytest.mark.asyncio
    async def test_register_user(self, client: AsyncClient, sample_user_data):
        response = await client.post("/v1/auth/register", json=sample_user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == sample_user_data["email"]
        assert data["api_key"].startswith("sk-")
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        response = await client.post("/v1/auth/register", json={
            "email": "notanemail",
            "password": "securepass123",
        })
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_returns_token(self, client: AsyncClient, sample_user_data):
        response = await client.post("/v1/auth/token", json=sample_user_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestCompletionEndpoints:
    
    @pytest.mark.asyncio
    async def test_completion_requires_auth(self, client: AsyncClient):
        response = await client.post("/v1/completions", json={
            "prompt": "Hello",
            "model": "gpt-4",
        })
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_completion_success(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/v1/completions",
            json={"prompt": "Hello world", "model": "gpt-4", "max_tokens": 100},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "usage" in data
        assert data["model"] == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_streaming_completion(self, client: AsyncClient, auth_headers):
        async with client.stream(
            "POST",
            "/v1/completions/stream",
            json={"prompt": "Hello", "model": "gpt-4", "stream": True},
            headers=auth_headers,
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            chunks = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunks.append(line)
            
            assert len(chunks) > 0
            assert chunks[-1] == "data: [DONE]"
```

---

## 3. Contract Testing

```python
# tests/contract/test_api_schema.py
"""
Contract tests ensure API responses match their documented schema.
This prevents breaking changes from being deployed.
"""
import pytest
from pydantic import ValidationError
from IMPLEMENTATION import (
    HealthResponse,
    CompletionResponse,
    TokenResponse,
    UserResponse,
    ErrorResponse,
)


class TestResponseContracts:
    """Verify all response models can be instantiated with expected shapes."""
    
    def test_health_response_contract(self):
        data = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "checks": {"database": "healthy", "redis": "healthy"},
        }
        response = HealthResponse(**data)
        assert response.status == "healthy"
    
    def test_completion_response_contract(self):
        data = {
            "id": "cmpl-abc123",
            "model": "gpt-4",
            "content": "Hello world",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "created_at": "2024-01-01T00:00:00Z",
        }
        response = CompletionResponse(**data)
        assert response.usage["total_tokens"] == 15
    
    def test_completion_request_validation(self):
        """Ensure invalid requests are rejected."""
        from IMPLEMENTATION import CompletionRequest
        
        # Temperature out of range
        with pytest.raises(ValidationError):
            CompletionRequest(prompt="hello", temperature=3.0)
        
        # Empty prompt
        with pytest.raises(ValidationError):
            CompletionRequest(prompt="")
        
        # max_tokens too high
        with pytest.raises(ValidationError):
            CompletionRequest(prompt="hello", max_tokens=99999)
```

---

## 4. Load Testing with Locust

```python
# tests/load/locustfile.py
"""
Load testing with Locust.

Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between, events
import json
import time


class AIAPIUser(HttpUser):
    """Simulates a typical AI API consumer."""
    
    wait_time = between(0.5, 2.0)
    
    def on_start(self):
        """Login and get token on user start."""
        response = self.client.post("/v1/auth/token", json={
            "email": "loadtest@example.com",
            "password": "loadtest123",
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {"X-API-Key": "sk-loadtest"}
    
    @task(5)
    def create_completion(self):
        """Most common operation - create a completion."""
        self.client.post(
            "/v1/completions",
            json={
                "prompt": "Explain quantum computing in simple terms",
                "model": "gpt-4",
                "max_tokens": 100,
            },
            headers=self.headers,
        )
    
    @task(3)
    def health_check(self):
        """Health checks (from load balancers, k8s)."""
        self.client.get("/health/live")
    
    @task(2)
    def streaming_completion(self):
        """Streaming completions."""
        with self.client.post(
            "/v1/completions/stream",
            json={"prompt": "Write a haiku", "model": "gpt-4", "stream": True},
            headers=self.headers,
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                # Consume the stream
                for _ in response.iter_lines():
                    pass
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(1)
    def create_conversation(self):
        """Less frequent - creating conversations."""
        self.client.post(
            "/v1/conversations",
            json={"title": "Load test conversation"},
            headers=self.headers,
        )


class HighVolumeUser(HttpUser):
    """Simulates a high-volume enterprise user."""
    
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        self.headers = {"X-API-Key": "sk-enterprise-loadtest"}
    
    @task
    def burst_completions(self):
        """Rapid-fire completions to test rate limiting."""
        self.client.post(
            "/v1/completions",
            json={"prompt": "Quick answer", "model": "gpt-4", "max_tokens": 50},
            headers=self.headers,
        )
```

**Target SLAs to validate:**

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| P50 latency | < 200ms | > 500ms |
| P99 latency | < 2000ms | > 5000ms |
| Error rate | < 0.1% | > 1% |
| Throughput | > 500 RPS | < 200 RPS |

---

## 5. Security Testing Checklist

```python
# tests/security/test_security.py
import pytest


class TestAuthSecurity:
    
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, client):
        response = await client.post("/v1/completions", json={"prompt": "test"})
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client):
        headers = {"Authorization": "Bearer expired.token.here"}
        response = await client.post("/v1/completions", json={"prompt": "test"}, headers=headers)
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_sql_injection_in_input(self, client, auth_headers):
        """Pydantic + SQLAlchemy ORM prevent SQL injection, but verify."""
        response = await client.post(
            "/v1/completions",
            json={"prompt": "'; DROP TABLE users; --", "model": "gpt-4"},
            headers=auth_headers,
        )
        # Should succeed (input is just a string to LLM, not SQL)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_oversized_payload_rejected(self, client, auth_headers):
        response = await client.post(
            "/v1/completions",
            json={"prompt": "x" * 100001, "model": "gpt-4"},
            headers=auth_headers,
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, client, auth_headers):
        """Verify rate limiting actually blocks excessive requests."""
        responses = []
        for _ in range(70):  # Free tier = 60/min
            r = await client.post(
                "/v1/completions",
                json={"prompt": "test", "model": "gpt-4"},
                headers=auth_headers,
            )
            responses.append(r.status_code)
        
        assert 429 in responses  # At least one should be rate limited


class TestInputValidation:
    
    @pytest.mark.asyncio
    async def test_invalid_model_name(self, client, auth_headers):
        response = await client.post(
            "/v1/completions",
            json={"prompt": "test", "model": "../../../etc/passwd"},
            headers=auth_headers,
        )
        # Should still work (model is just a string param)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_negative_max_tokens_rejected(self, client, auth_headers):
        response = await client.post(
            "/v1/completions",
            json={"prompt": "test", "model": "gpt-4", "max_tokens": -1},
            headers=auth_headers,
        )
        assert response.status_code == 422
```

### Static Security Analysis

```bash
# Run bandit for Python security issues
bandit -r . -f json -o bandit-report.json

# Check dependencies for known vulnerabilities
pip-audit --format json --output pip-audit-report.json

# Check for secrets in code
gitleaks detect --source . --report-format json --report-path gitleaks-report.json
```

---

## 6. Test Fixtures and Factories

```python
# tests/factories.py
"""
Test data factories using factory_boy pattern.
Provides consistent, realistic test data.
"""
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class UserFactory:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str = field(default_factory=lambda: f"user-{uuid.uuid4().hex[:8]}@test.com")
    api_key: str = field(default_factory=lambda: f"sk-test-{uuid.uuid4().hex}")
    tier: str = "free"
    
    def to_jwt_payload(self) -> dict:
        return {"sub": self.id, "email": self.email, "tier": self.tier}


@dataclass
class CompletionRequestFactory:
    prompt: str = "Explain machine learning"
    model: str = "gpt-4"
    max_tokens: int = 100
    temperature: float = 0.7
    stream: bool = False
    
    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": self.stream,
        }
    
    @classmethod
    def long_prompt(cls):
        return cls(prompt="x" * 10000, max_tokens=4096)
    
    @classmethod
    def streaming(cls):
        return cls(stream=True)


@dataclass
class ConversationFactory:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Test Conversation"
    messages: list = field(default_factory=list)
    
    def with_messages(self, count: int = 5):
        self.messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(count)
        ]
        return self
```

---

## 7. Mocking Strategies

```python
# tests/unit/test_with_mocks.py
"""
Mocking external services for fast, reliable unit tests.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestWithMockedLLM:
    """Test completion logic without actual LLM calls."""
    
    @pytest.mark.asyncio
    @patch("IMPLEMENTATION.simulate_llm_call")
    async def test_completion_uses_cache(self, mock_llm, client, auth_headers, redis_client):
        """Second identical request should hit cache, not LLM."""
        mock_llm.return_value = {
            "content": "Mocked response",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }
        
        payload = {"prompt": "cache test", "model": "gpt-4", "max_tokens": 100}
        
        # First call hits LLM
        await client.post("/v1/completions", json=payload, headers=auth_headers)
        assert mock_llm.call_count == 1
        
        # Second call should hit cache
        await client.post("/v1/completions", json=payload, headers=auth_headers)
        assert mock_llm.call_count == 1  # Still 1 - cache hit
    
    @pytest.mark.asyncio
    @patch("IMPLEMENTATION.simulate_llm_call")
    async def test_circuit_breaker_opens_on_failures(self, mock_llm, client, auth_headers):
        """Circuit breaker should open after repeated failures."""
        mock_llm.side_effect = Exception("Service unavailable")
        
        payload = {"prompt": "will fail", "model": "gpt-4"}
        
        # Make enough requests to trip the breaker
        for i in range(10):
            response = await client.post("/v1/completions", json=payload, headers=auth_headers)
        
        # Eventually should get 503 (circuit open) instead of 500
        assert response.status_code == 503


class TestWithMockedRedis:
    """Test behavior when Redis is unavailable."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_without_redis(self, client):
        """App should still respond (degraded) if Redis is down."""
        with patch("IMPLEMENTATION.get_redis", side_effect=ConnectionError("Redis down")):
            response = await client.get("/health")
            data = response.json()
            assert data["status"] == "degraded"
            assert "unhealthy" in data["checks"]["redis"]
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Run only unit tests (fast)
pytest tests/unit/ -v --timeout=10

# Run integration tests (needs Docker)
pytest tests/integration/ -v --timeout=60

# Run in parallel
pytest tests/ -n auto

# Run with specific markers
pytest -m "not slow" tests/
pytest -m security tests/
```

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    security: security-focused tests
    integration: requires external services
timeout = 30
```
