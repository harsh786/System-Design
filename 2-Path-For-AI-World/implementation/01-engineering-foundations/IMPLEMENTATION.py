"""
Engineering Foundations - Complete FastAPI Application
=====================================================
A production-ready FastAPI application demonstrating all core patterns
needed before adding AI complexity.

Run with: uvicorn IMPLEMENTATION:app --reload --port 8000
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, AsyncGenerator, Optional

import jwt
import redis.asyncio as aioredis
import structlog
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, DateTime, String, Text, Integer, Float, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# =============================================================================
# CONFIGURATION
# =============================================================================

class Settings(BaseModel):
    """Application configuration with sensible defaults."""
    
    app_name: str = "Engineering Foundations API"
    version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/foundations"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    
    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 30
    
    # OpenTelemetry
    otlp_endpoint: str = "http://localhost:4317"
    service_name: str = "foundations-api"


settings = Settings()

# =============================================================================
# STRUCTURED LOGGING
# =============================================================================

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# =============================================================================
# OPENTELEMETRY SETUP
# =============================================================================

def setup_telemetry() -> trace.Tracer:
    """Initialize OpenTelemetry with OTLP exporter."""
    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)
    
    otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)


tracer = setup_telemetry()

# =============================================================================
# DATABASE MODELS & ENGINE
# =============================================================================

class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True)
    rate_limit_tier = Column(String(50), default="free")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConversationModel(Base):
    __tablename__ = "conversations"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(500))
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MessageModel(Base):
    __tablename__ = "messages"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer)
    model = Column(String(100))
    cost_usd = Column(Float)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Async engine and session factory
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# REDIS CONNECTION
# =============================================================================

redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get Redis connection from pool."""
    global redis_pool
    if redis_pool is None:
        redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return redis_pool


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    
    @validator("email")
    def validate_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()


class UserResponse(BaseModel):
    id: str
    email: str
    api_key: str
    rate_limit_tier: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: str = Field(..., min_length=1, max_length=100000)
    model: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    token_count: Optional[int]
    model: Optional[str]
    cost_usd: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    metadata: dict
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    checks: dict[str, str]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: str
    timestamp: datetime


class CompletionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=50000)
    model: str = Field(default="gpt-4")
    max_tokens: int = Field(default=1000, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = Field(default=False)


class CompletionResponse(BaseModel):
    id: str
    model: str
    content: str
    usage: dict
    created_at: datetime


# =============================================================================
# CIRCUIT BREAKER PATTERN
# =============================================================================

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit Breaker implementation for external service calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing fast, no requests pass through
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state
    
    async def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker."""
        async with self._lock:
            current_state = self.state
            
            if current_state == CircuitState.OPEN:
                logger.warning(
                    "circuit_breaker_open",
                    breaker=self.name,
                    failures=self._failure_count,
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retry after {self.recovery_timeout}s."
                )
            
            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN, max test calls reached."
                    )
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("circuit_breaker_closed", breaker=self.name)
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("circuit_breaker_reopened", breaker=self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    breaker=self.name,
                    failures=self._failure_count,
                )


class CircuitBreakerOpenError(Exception):
    pass


# Circuit breakers for external services
llm_circuit_breaker = CircuitBreaker(
    name="llm_service",
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout,
)

embedding_circuit_breaker = CircuitBreaker(
    name="embedding_service",
    failure_threshold=3,
    recovery_timeout=60,
)

# =============================================================================
# RATE LIMITING (Sliding Window with Redis)
# =============================================================================

class RateLimiter:
    """Sliding window rate limiter using Redis sorted sets."""
    
    TIER_LIMITS = {
        "free": {"requests": 60, "window": 60},
        "pro": {"requests": 600, "window": 60},
        "enterprise": {"requests": 6000, "window": 60},
    }
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
    
    async def check_rate_limit(
        self, identifier: str, tier: str = "free"
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        Returns (allowed, headers_dict).
        """
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS["free"])
        max_requests = limits["requests"]
        window = limits["window"]
        
        now = time.time()
        key = f"ratelimit:{identifier}:{int(now // window)}"
        
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = await pipe.execute()
        
        current_count = results[2]
        allowed = current_count <= max_requests
        
        headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(max(0, max_requests - current_count)),
            "X-RateLimit-Reset": str(int(now // window * window + window)),
        }
        
        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                tier=tier,
                count=current_count,
                limit=max_requests,
            )
        
        return allowed, headers


# =============================================================================
# JWT AUTHENTICATION
# =============================================================================

class AuthService:
    """JWT-based authentication service."""
    
    @staticmethod
    def create_token(user_id: str, email: str, tier: str) -> TokenResponse:
        """Create a JWT access token."""
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_expiration_minutes
        )
        payload = {
            "sub": user_id,
            "email": email,
            "tier": tier,
            "exp": expires,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return TokenResponse(
            access_token=token,
            expires_in=settings.jwt_expiration_minutes * 60,
        )
    
    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> dict:
    """
    Dependency: Extract and validate user from JWT or API key.
    Supports both Bearer token and API key authentication.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        return AuthService.verify_token(token)
    
    if x_api_key:
        # In production, look up API key in database
        # For demo, we decode a simple format
        return {"sub": "api_key_user", "email": "api@example.com", "tier": "pro"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication. Provide Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# =============================================================================
# CACHING LAYER
# =============================================================================

class CacheService:
    """Redis-based caching with automatic serialization."""
    
    def __init__(self, redis: aioredis.Redis, default_ttl: int = 3600):
        self.redis = redis
        self.default_ttl = default_ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value, returns None on miss."""
        with tracer.start_as_current_span("cache_get") as span:
            span.set_attribute("cache.key", key)
            value = await self.redis.get(f"cache:{key}")
            span.set_attribute("cache.hit", value is not None)
            if value:
                return json.loads(value)
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cache value with TTL."""
        with tracer.start_as_current_span("cache_set") as span:
            span.set_attribute("cache.key", key)
            await self.redis.setex(
                f"cache:{key}",
                ttl or self.default_ttl,
                json.dumps(value, default=str),
            )
    
    async def invalidate(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        keys = []
        async for key in self.redis.scan_iter(f"cache:{pattern}"):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0
    
    def cache_key(self, *parts: str) -> str:
        """Generate a consistent cache key from parts."""
        combined = ":".join(str(p) for p in parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


# =============================================================================
# MIDDLEWARE
# =============================================================================

class CorrelationIdMiddleware:
    """Adds correlation ID to every request for distributed tracing."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            request_id = headers.get(
                b"x-request-id", str(uuid.uuid4()).encode()
            ).decode()
            
            # Bind to structlog context
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(request_id=request_id)
            
            # Add to response headers
            async def send_with_request_id(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", request_id.encode()))
                    message["headers"] = headers
                await send(message)
            
            await self.app(scope, receive, send_with_request_id)
        else:
            await self.app(scope, receive, send)


class RequestTimingMiddleware:
    """Logs request duration and emits metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.perf_counter()
            
            async def send_with_timing(message):
                if message["type"] == "http.response.start":
                    duration = time.perf_counter() - start_time
                    headers = list(message.get("headers", []))
                    headers.append(
                        (b"x-response-time", f"{duration:.4f}s".encode())
                    )
                    message["headers"] = headers
                    
                    # Extract status code and path for logging
                    status_code = message.get("status", 0)
                    path = scope.get("path", "unknown")
                    method = scope.get("method", "unknown")
                    
                    logger.info(
                        "http_request_completed",
                        method=method,
                        path=path,
                        status=status_code,
                        duration_ms=round(duration * 1000, 2),
                    )
                await send(message)
            
            await self.app(scope, receive, send_with_timing)
        else:
            await self.app(scope, receive, send)


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("application_starting", version=settings.version)
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Verify Redis connection
    redis = await get_redis()
    await redis.ping()
    logger.info("redis_connected")
    
    logger.info("application_started")
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    
    if redis_pool:
        await redis_pool.close()
    
    await engine.dispose()
    logger.info("application_stopped")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add middleware (order matters - first added = outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ASGI middleware
app.middleware("http")(RequestTimingMiddleware(app))
# Note: In production, use proper ASGI middleware pattern
# app = CorrelationIdMiddleware(app)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Comprehensive health check endpoint.
    Checks database, Redis, and reports overall status.
    """
    checks = {}
    overall_healthy = True
    
    # Check database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        overall_healthy = False
    
    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
        overall_healthy = False
    
    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        version=settings.version,
        timestamp=datetime.now(timezone.utc),
        checks=checks,
    )


@app.get("/health/live", tags=["Health"])
async def liveness():
    """Kubernetes liveness probe - is the process alive?"""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness():
    """Kubernetes readiness probe - can we accept traffic?"""
    try:
        redis = await get_redis()
        await redis.ping()
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Not ready")


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@app.post("/v1/auth/register", response_model=UserResponse, tags=["Auth"])
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user and generate API key."""
    with tracer.start_as_current_span("register_user"):
        # Hash password (use bcrypt in production)
        hashed = hashlib.sha256(user.password.encode()).hexdigest()
        api_key = f"sk-{uuid.uuid4().hex}"
        
        db_user = UserModel(
            email=user.email,
            hashed_password=hashed,
            api_key=api_key,
        )
        db.add(db_user)
        await db.flush()
        
        logger.info("user_registered", user_id=str(db_user.id), email=user.email)
        
        return UserResponse(
            id=str(db_user.id),
            email=db_user.email,
            api_key=db_user.api_key,
            rate_limit_tier=db_user.rate_limit_tier,
            created_at=db_user.created_at,
        )


@app.post("/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
async def login(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive JWT token."""
    # In production: look up user, verify password with bcrypt
    token = AuthService.create_token(
        user_id="user_123",
        email=user.email,
        tier="pro",
    )
    logger.info("user_authenticated", email=user.email)
    return token


# =============================================================================
# CONVERSATION ENDPOINTS (CRUD with caching)
# =============================================================================

@app.post("/v1/conversations", response_model=ConversationResponse, tags=["Conversations"])
async def create_conversation(
    data: ConversationCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    with tracer.start_as_current_span("create_conversation"):
        conversation = ConversationModel(
            user_id=uuid.UUID(user["sub"]) if len(user["sub"]) > 10 else uuid.uuid4(),
            title=data.title,
            metadata_=data.metadata,
        )
        db.add(conversation)
        await db.flush()
        
        logger.info("conversation_created", conversation_id=str(conversation.id))
        
        return ConversationResponse(
            id=str(conversation.id),
            user_id=str(conversation.user_id),
            title=conversation.title,
            metadata=conversation.metadata_ or {},
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


@app.post(
    "/v1/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    tags=["Messages"],
)
async def create_message(
    conversation_id: str,
    data: MessageCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a message to a conversation."""
    with tracer.start_as_current_span("create_message") as span:
        span.set_attribute("conversation_id", conversation_id)
        span.set_attribute("role", data.role)
        
        # Estimate token count (rough: 1 token ≈ 4 chars)
        token_count = len(data.content) // 4
        
        message = MessageModel(
            conversation_id=uuid.UUID(conversation_id),
            role=data.role,
            content=data.content,
            token_count=token_count,
            model=data.model,
            metadata_=data.metadata,
        )
        db.add(message)
        await db.flush()
        
        # Invalidate conversation cache
        redis = await get_redis()
        cache = CacheService(redis)
        await cache.invalidate(f"conversation:{conversation_id}*")
        
        logger.info(
            "message_created",
            message_id=str(message.id),
            conversation_id=conversation_id,
            role=data.role,
            tokens=token_count,
        )
        
        return MessageResponse(
            id=str(message.id),
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
            token_count=message.token_count,
            model=message.model,
            cost_usd=message.cost_usd,
            created_at=message.created_at,
        )


# =============================================================================
# COMPLETION ENDPOINT (with Circuit Breaker & Rate Limiting)
# =============================================================================

async def simulate_llm_call(prompt: str, model: str, max_tokens: int) -> dict:
    """Simulate an LLM API call (replace with actual provider SDK)."""
    await asyncio.sleep(0.5)  # Simulate latency
    return {
        "content": f"This is a simulated response to: {prompt[:50]}...",
        "prompt_tokens": len(prompt) // 4,
        "completion_tokens": max_tokens // 2,
        "total_tokens": len(prompt) // 4 + max_tokens // 2,
    }


@app.post("/v1/completions", response_model=CompletionResponse, tags=["Completions"])
async def create_completion(
    request: CompletionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Create a completion with rate limiting and circuit breaker protection.
    """
    with tracer.start_as_current_span("create_completion") as span:
        span.set_attribute("model", request.model)
        span.set_attribute("max_tokens", request.max_tokens)
        
        # Rate limiting
        redis = await get_redis()
        rate_limiter = RateLimiter(redis)
        allowed, headers = await rate_limiter.check_rate_limit(
            identifier=user["sub"],
            tier=user.get("tier", "free"),
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Upgrade your plan for higher limits.",
                headers=headers,
            )
        
        # Check cache for identical prompts
        cache = CacheService(redis)
        cache_key = cache.cache_key(request.prompt, request.model, str(request.temperature))
        cached = await cache.get(cache_key)
        if cached:
            logger.info("completion_cache_hit", model=request.model)
            span.set_attribute("cache.hit", True)
            return CompletionResponse(**cached)
        
        # Call LLM through circuit breaker
        try:
            result = await llm_circuit_breaker.call(
                simulate_llm_call,
                request.prompt,
                request.model,
                request.max_tokens,
            )
        except CircuitBreakerOpenError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )
        
        response = CompletionResponse(
            id=f"cmpl-{uuid.uuid4().hex[:12]}",
            model=request.model,
            content=result["content"],
            usage={
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
            },
            created_at=datetime.now(timezone.utc),
        )
        
        # Cache the response
        await cache.set(cache_key, response.model_dump(), ttl=1800)
        
        logger.info(
            "completion_created",
            model=request.model,
            tokens=result["total_tokens"],
            user_id=user["sub"],
        )
        
        return response


# =============================================================================
# STREAMING ENDPOINT (Server-Sent Events)
# =============================================================================

async def generate_stream(prompt: str, model: str) -> AsyncGenerator[str, None]:
    """Generate streaming response tokens."""
    # Simulate token-by-token generation
    words = f"This is a streaming response to your prompt about {prompt[:30]}. " \
            f"The model {model} generates tokens one by one, simulating real LLM behavior. " \
            f"Each token is sent as a Server-Sent Event."
    
    for word in words.split():
        await asyncio.sleep(0.05)  # Simulate generation delay
        chunk = {
            "id": f"chunk-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"delta": {"content": word + " "}, "index": 0}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    
    yield "data: [DONE]\n\n"


@app.post("/v1/completions/stream", tags=["Completions"])
async def create_streaming_completion(
    request: CompletionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Create a streaming completion using Server-Sent Events.
    Tokens are sent as they are generated.
    """
    with tracer.start_as_current_span("create_streaming_completion"):
        logger.info("streaming_completion_started", model=request.model, user=user["sub"])
        
        return StreamingResponse(
            generate_stream(request.prompt, request.model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

class ConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("websocket_connected", client_id=client_id)
    
    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        logger.info("websocket_disconnected", client_id=client_id)
    
    async def send_json(self, client_id: str, data: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            await ws.send_json(data)


ws_manager = ConnectionManager()


@app.websocket("/v1/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time bidirectional communication.
    
    Protocol:
    - Client sends: {"type": "message", "content": "...", "conversation_id": "..."}
    - Server sends: {"type": "token", "content": "...", "message_id": "..."}
    - Server sends: {"type": "done", "message_id": "...", "usage": {...}}
    - Server sends: {"type": "error", "detail": "..."}
    """
    await ws_manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            if data.get("type") == "message":
                message_id = f"msg-{uuid.uuid4().hex[:12]}"
                content = data.get("content", "")
                
                # Stream response tokens
                response_words = f"Responding to: {content}".split()
                for word in response_words:
                    await asyncio.sleep(0.05)
                    await websocket.send_json({
                        "type": "token",
                        "content": word + " ",
                        "message_id": message_id,
                    })
                
                await websocket.send_json({
                    "type": "done",
                    "message_id": message_id,
                    "usage": {"total_tokens": len(response_words) * 2},
                })
    
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error("websocket_error", client_id=client_id, error=str(e))
        ws_manager.disconnect(client_id)


# =============================================================================
# IDEMPOTENCY SUPPORT
# =============================================================================

async def check_idempotency(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> Optional[str]:
    """Check if this request was already processed."""
    if not idempotency_key:
        return None
    
    redis = await get_redis()
    cached_response = await redis.get(f"idempotency:{idempotency_key}")
    
    if cached_response:
        return cached_response
    
    return None


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with structured error response."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    
    return Response(
        content=json.dumps({
            "error": exc.detail,
            "status_code": exc.status_code,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        status_code=exc.status_code,
        media_type="application/json",
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler - never expose internal errors."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        request_id=request_id,
        path=request.url.path,
    )
    
    return Response(
        content=json.dumps({
            "error": "Internal server error",
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        status_code=500,
        media_type="application/json",
    )


# =============================================================================
# METRICS ENDPOINT (for Prometheus scraping)
# =============================================================================

# In-memory metrics (use prometheus_client in production)
metrics_store = defaultdict(float)


@app.get("/metrics", tags=["Observability"])
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    # In production, use prometheus_client library
    metrics = [
        f'# HELP http_requests_total Total HTTP requests',
        f'# TYPE http_requests_total counter',
        f'http_requests_total{{method="GET"}} {metrics_store.get("get_requests", 0)}',
        f'http_requests_total{{method="POST"}} {metrics_store.get("post_requests", 0)}',
        f'# HELP llm_tokens_total Total LLM tokens consumed',
        f'# TYPE llm_tokens_total counter',
        f'llm_tokens_total{{type="prompt"}} {metrics_store.get("prompt_tokens", 0)}',
        f'llm_tokens_total{{type="completion"}} {metrics_store.get("completion_tokens", 0)}',
    ]
    return Response(content="\n".join(metrics), media_type="text/plain")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "IMPLEMENTATION:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        workers=4,
        log_level="info",
        access_log=False,  # We handle logging in middleware
    )
