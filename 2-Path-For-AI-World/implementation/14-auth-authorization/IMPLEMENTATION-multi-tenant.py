"""
Multi-Tenant Isolation for AI Systems
=======================================
Complete implementation covering:
- Tenant context extraction
- Tenant-level resource isolation
- Tenant-specific model/prompt configurations
- Tenant data partitioning
- Cross-tenant leakage prevention
- Tenant-level rate limiting and budgets
- Tenant administration APIs
"""

import asyncio
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional


# =============================================================================
# Context Variable for Tenant (Thread-Safe Propagation)
# =============================================================================

# ContextVar ensures tenant context is propagated correctly in async code
_current_tenant: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)
_current_tenant_context: ContextVar[Optional["TenantContext"]] = ContextVar("tenant_context", default=None)


def get_current_tenant() -> Optional[str]:
    return _current_tenant.get()


def get_tenant_context() -> Optional["TenantContext"]:
    return _current_tenant_context.get()


@asynccontextmanager
async def tenant_scope(tenant_id: str, context: "TenantContext" = None):
    """
    Context manager that sets tenant scope for the duration of the block.
    All operations within this block are scoped to this tenant.
    """
    token1 = _current_tenant.set(tenant_id)
    token2 = _current_tenant_context.set(context)
    try:
        yield
    finally:
        _current_tenant.reset(token1)
        _current_tenant_context.reset(token2)


# =============================================================================
# Core Models
# =============================================================================

class TenantTier(Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class IsolationLevel(Enum):
    SHARED = "shared"  # Shared infrastructure, logical isolation
    DEDICATED = "dedicated"  # Dedicated resources per tenant
    ISOLATED = "isolated"  # Full network + compute isolation


@dataclass
class TenantConfig:
    """Configuration for a tenant."""
    tenant_id: str
    name: str
    tier: TenantTier
    isolation_level: IsolationLevel
    
    # Model configuration
    allowed_models: list[str] = field(default_factory=lambda: ["gpt-4o-mini"])
    default_model: str = "gpt-4o-mini"
    max_context_window: int = 8192
    temperature_override: Optional[float] = None
    
    # Prompt configuration
    system_prompt_prefix: str = ""
    system_prompt_suffix: str = ""
    banned_topics: list[str] = field(default_factory=list)
    custom_instructions: str = ""
    
    # Resource limits
    max_requests_per_minute: int = 60
    max_requests_per_day: int = 10000
    max_tokens_per_request: int = 4096
    max_tokens_per_day: int = 1000000
    max_documents: int = 10000
    max_tools_per_session: int = 10
    max_concurrent_sessions: int = 5
    
    # Budget
    monthly_budget_usd: float = 100.0
    cost_alert_threshold: float = 0.8  # Alert at 80% of budget
    
    # Data configuration
    data_region: str = "us-east-1"
    encryption_key_id: Optional[str] = None  # Tenant-specific encryption key
    retention_days: int = 90
    
    # Feature flags
    features: dict[str, bool] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


@dataclass
class TenantContext:
    """Runtime context for a tenant request."""
    tenant_id: str
    config: TenantConfig
    user_id: str
    session_id: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))


# =============================================================================
# Tenant Context Extractor
# =============================================================================

class TenantContextExtractor:
    """
    Extracts tenant identity from various sources:
    - JWT claims
    - Request headers
    - API key lookup
    - Subdomain parsing
    """

    def __init__(self, config_store: "TenantConfigStore"):
        self.config_store = config_store

    async def extract_from_token(self, token_claims: dict) -> TenantContext:
        """Extract tenant from validated JWT claims."""
        tenant_id = token_claims.get("tenant_id")
        if not tenant_id:
            raise TenantError("Token missing tenant_id claim")

        config = await self.config_store.get_config(tenant_id)
        if not config:
            raise TenantError(f"Unknown tenant: {tenant_id}")
        if not config.is_active:
            raise TenantError(f"Tenant {tenant_id} is deactivated")

        return TenantContext(
            tenant_id=tenant_id,
            config=config,
            user_id=token_claims.get("sub", ""),
            session_id=token_claims.get("session_id", str(uuid.uuid4())),
        )

    async def extract_from_header(self, headers: dict) -> TenantContext:
        """Extract tenant from X-Tenant-ID header (for service-to-service)."""
        tenant_id = headers.get("X-Tenant-ID") or headers.get("x-tenant-id")
        if not tenant_id:
            raise TenantError("Missing X-Tenant-ID header")

        config = await self.config_store.get_config(tenant_id)
        if not config:
            raise TenantError(f"Unknown tenant: {tenant_id}")

        return TenantContext(
            tenant_id=tenant_id,
            config=config,
            user_id=headers.get("X-User-ID", "service"),
            session_id=headers.get("X-Session-ID", str(uuid.uuid4())),
        )

    async def extract_from_api_key(self, api_key: str) -> TenantContext:
        """Extract tenant by looking up API key."""
        tenant_id = await self.config_store.lookup_api_key(api_key)
        if not tenant_id:
            raise TenantError("Invalid API key")

        config = await self.config_store.get_config(tenant_id)
        return TenantContext(
            tenant_id=tenant_id,
            config=config,
            user_id="api_key_user",
            session_id=str(uuid.uuid4()),
        )


# =============================================================================
# Tenant Configuration Store
# =============================================================================

class TenantConfigStore:
    """Manages tenant configurations with caching."""

    def __init__(self):
        self._configs: dict[str, TenantConfig] = {}
        self._api_keys: dict[str, str] = {}  # api_key_hash → tenant_id
        self._cache: dict[str, tuple[TenantConfig, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    async def create_tenant(self, config: TenantConfig) -> TenantConfig:
        """Create a new tenant."""
        self._configs[config.tenant_id] = config
        return config

    async def get_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant config with caching."""
        # Check cache
        if tenant_id in self._cache:
            config, expires = self._cache[tenant_id]
            if time.time() < expires:
                return config

        config = self._configs.get(tenant_id)
        if config:
            self._cache[tenant_id] = (config, time.time() + self._cache_ttl)
        return config

    async def update_config(self, tenant_id: str, updates: dict) -> TenantConfig:
        """Update tenant configuration."""
        config = self._configs.get(tenant_id)
        if not config:
            raise TenantError(f"Tenant not found: {tenant_id}")

        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # Invalidate cache
        self._cache.pop(tenant_id, None)
        return config

    async def register_api_key(self, api_key: str, tenant_id: str):
        """Register an API key for a tenant."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        self._api_keys[key_hash] = tenant_id

    async def lookup_api_key(self, api_key: str) -> Optional[str]:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return self._api_keys.get(key_hash)

    async def deactivate_tenant(self, tenant_id: str):
        """Deactivate a tenant (soft delete)."""
        config = self._configs.get(tenant_id)
        if config:
            config.is_active = False
            self._cache.pop(tenant_id, None)


# =============================================================================
# Tenant Resource Isolation
# =============================================================================

class TenantResourceIsolator:
    """
    Ensures all resource access is scoped to the current tenant.
    Acts as a guard that wraps all data access operations.
    """

    def __init__(self):
        self._violation_log: list[dict] = []

    def get_namespace(self, tenant_id: str, resource_type: str) -> str:
        """Get the isolated namespace for a tenant's resources."""
        return f"{tenant_id}/{resource_type}"

    def get_vector_db_collection(self, tenant_id: str) -> str:
        """Get tenant-specific vector DB collection name."""
        return f"tenant_{tenant_id}_vectors"

    def get_cache_prefix(self, tenant_id: str) -> str:
        """Get tenant-specific cache key prefix."""
        return f"t:{tenant_id}:"

    def get_storage_path(self, tenant_id: str) -> str:
        """Get tenant-specific storage path."""
        return f"/data/tenants/{tenant_id}/"

    def validate_resource_access(self, tenant_id: str, resource_tenant: str, resource_id: str) -> bool:
        """Validate that resource belongs to tenant."""
        if tenant_id != resource_tenant:
            self._violation_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requesting_tenant": tenant_id,
                "resource_tenant": resource_tenant,
                "resource_id": resource_id,
                "severity": "critical",
            })
            return False
        return True

    def wrap_query(self, tenant_id: str, query: dict) -> dict:
        """Add tenant filter to any database query."""
        return {
            "$and": [
                {"tenant_id": tenant_id},
                query,
            ]
        }


# =============================================================================
# Tenant-Specific Model/Prompt Configuration
# =============================================================================

class TenantModelRouter:
    """
    Routes model requests based on tenant configuration.
    Applies tenant-specific prompts, model selection, and parameters.
    """

    def __init__(self, config_store: TenantConfigStore):
        self.config_store = config_store

    async def get_model_config(self, tenant_id: str) -> dict:
        """Get model configuration for a tenant."""
        config = await self.config_store.get_config(tenant_id)
        if not config:
            raise TenantError(f"Unknown tenant: {tenant_id}")

        return {
            "model": config.default_model,
            "allowed_models": config.allowed_models,
            "max_tokens": config.max_tokens_per_request,
            "temperature": config.temperature_override,
        }

    async def build_system_prompt(self, tenant_id: str, base_prompt: str) -> str:
        """Build tenant-customized system prompt."""
        config = await self.config_store.get_config(tenant_id)
        if not config:
            return base_prompt

        parts = []
        
        if config.system_prompt_prefix:
            parts.append(config.system_prompt_prefix)
        
        parts.append(base_prompt)
        
        if config.custom_instructions:
            parts.append(f"\n\nCustom Instructions:\n{config.custom_instructions}")
        
        if config.banned_topics:
            parts.append(
                f"\n\nDo NOT discuss or provide information about: "
                f"{', '.join(config.banned_topics)}"
            )
        
        if config.system_prompt_suffix:
            parts.append(config.system_prompt_suffix)

        return "\n".join(parts)

    async def validate_model_request(self, tenant_id: str, model: str) -> bool:
        """Check if tenant is allowed to use requested model."""
        config = await self.config_store.get_config(tenant_id)
        if not config:
            return False
        return model in config.allowed_models


# =============================================================================
# Tenant Data Partitioning
# =============================================================================

class PartitionStrategy(Enum):
    NAMESPACE = "namespace"  # Logical isolation via namespaces/prefixes
    COLLECTION = "collection"  # Separate collection per tenant
    DATABASE = "database"  # Separate database per tenant
    CLUSTER = "cluster"  # Separate cluster per tenant (highest isolation)


class TenantDataPartitioner:
    """
    Manages data partitioning strategies per tenant.
    Higher-tier tenants get stronger isolation.
    """

    def __init__(self):
        self._tier_strategies: dict[TenantTier, PartitionStrategy] = {
            TenantTier.FREE: PartitionStrategy.NAMESPACE,
            TenantTier.STARTER: PartitionStrategy.NAMESPACE,
            TenantTier.PROFESSIONAL: PartitionStrategy.COLLECTION,
            TenantTier.ENTERPRISE: PartitionStrategy.DATABASE,
        }

    def get_strategy(self, tier: TenantTier) -> PartitionStrategy:
        return self._tier_strategies.get(tier, PartitionStrategy.NAMESPACE)

    def get_connection_config(self, tenant: TenantConfig) -> dict:
        """Get database connection config based on partition strategy."""
        strategy = self.get_strategy(tenant.tier)

        if strategy == PartitionStrategy.NAMESPACE:
            return {
                "database": "shared_db",
                "collection_prefix": f"ns_{tenant.tenant_id}_",
                "filter": {"tenant_id": tenant.tenant_id},
            }
        elif strategy == PartitionStrategy.COLLECTION:
            return {
                "database": "shared_db",
                "collection": f"tenant_{tenant.tenant_id}",
                "filter": None,  # No filter needed - collection is tenant-specific
            }
        elif strategy == PartitionStrategy.DATABASE:
            return {
                "database": f"db_{tenant.tenant_id}",
                "collection": "documents",
                "filter": None,
            }
        elif strategy == PartitionStrategy.CLUSTER:
            return {
                "endpoint": f"https://{tenant.tenant_id}.db.example.com",
                "database": "main",
                "collection": "documents",
                "filter": None,
            }


# =============================================================================
# Cross-Tenant Leakage Prevention
# =============================================================================

class LeakagePreventionGuard:
    """
    Defense-in-depth measures to prevent cross-tenant data leakage.
    Multiple layers of checks at different points in the pipeline.
    """

    def __init__(self):
        self._violations: list[dict] = []
        self._checks_performed: int = 0

    def check_response_leakage(
        self,
        tenant_id: str,
        response_documents: list[dict],
    ) -> list[dict]:
        """
        Final check before returning documents to ensure no cross-tenant leakage.
        This is the LAST line of defense.
        """
        self._checks_performed += 1
        safe_documents = []

        for doc in response_documents:
            doc_tenant = doc.get("tenant_id") or doc.get("metadata", {}).get("tenant_id")
            
            if doc_tenant != tenant_id:
                # CRITICAL: Cross-tenant leakage detected!
                self._violations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "requesting_tenant": tenant_id,
                    "document_tenant": doc_tenant,
                    "document_id": doc.get("id", "unknown"),
                    "severity": "critical",
                    "action": "blocked",
                })
                continue  # Do NOT include this document
            
            safe_documents.append(doc)

        return safe_documents

    def check_prompt_leakage(self, tenant_id: str, prompt: str, all_tenant_ids: list[str]) -> bool:
        """
        Check if a prompt might be attempting to access other tenants' data.
        Heuristic check for prompt injection targeting tenant isolation.
        """
        suspicious_patterns = [
            "ignore tenant",
            "all tenants",
            "switch tenant",
            "tenant_id =",
            "override isolation",
        ]
        
        prompt_lower = prompt.lower()
        for pattern in suspicious_patterns:
            if pattern in prompt_lower:
                self._violations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tenant_id": tenant_id,
                    "type": "suspicious_prompt",
                    "pattern": pattern,
                })
                return False

        # Check if other tenant IDs appear in the prompt
        for other_tenant in all_tenant_ids:
            if other_tenant != tenant_id and other_tenant in prompt:
                self._violations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tenant_id": tenant_id,
                    "type": "cross_tenant_reference",
                    "referenced_tenant": other_tenant,
                })
                return False

        return True

    def check_llm_output_leakage(
        self,
        tenant_id: str,
        output: str,
        other_tenant_markers: list[str],
    ) -> str:
        """
        Check LLM output for potential cross-tenant data leakage.
        Redact any detected cross-tenant information.
        """
        redacted = output
        for marker in other_tenant_markers:
            if marker in output:
                redacted = redacted.replace(marker, "[REDACTED]")
                self._violations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tenant_id": tenant_id,
                    "type": "output_leakage",
                    "marker": marker,
                    "action": "redacted",
                })
        return redacted

    @property
    def violation_count(self) -> int:
        return len(self._violations)


# =============================================================================
# Tenant Rate Limiting and Budgets
# =============================================================================

@dataclass
class UsageRecord:
    requests: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    window_start: float = field(default_factory=time.time)


class TenantRateLimiter:
    """
    Enforces rate limits and budget constraints per tenant.
    """

    def __init__(self):
        self._minute_usage: dict[str, UsageRecord] = {}
        self._daily_usage: dict[str, UsageRecord] = {}
        self._monthly_usage: dict[str, UsageRecord] = {}
        self._alerts: list[dict] = []

    def check_rate_limit(self, tenant_id: str, config: TenantConfig) -> tuple[bool, str]:
        """Check if request is within rate limits. Returns (allowed, reason)."""
        now = time.time()

        # Per-minute check
        minute_key = f"{tenant_id}:minute"
        minute_usage = self._minute_usage.get(minute_key)
        if minute_usage:
            if now - minute_usage.window_start > 60:
                minute_usage = UsageRecord(window_start=now)
                self._minute_usage[minute_key] = minute_usage
            elif minute_usage.requests >= config.max_requests_per_minute:
                return False, f"Rate limit exceeded: {config.max_requests_per_minute} req/min"
        else:
            minute_usage = UsageRecord(window_start=now)
            self._minute_usage[minute_key] = minute_usage

        # Per-day check
        day_key = f"{tenant_id}:day"
        day_usage = self._daily_usage.get(day_key)
        if day_usage:
            if now - day_usage.window_start > 86400:
                day_usage = UsageRecord(window_start=now)
                self._daily_usage[day_key] = day_usage
            elif day_usage.requests >= config.max_requests_per_day:
                return False, f"Daily limit exceeded: {config.max_requests_per_day} req/day"
        else:
            day_usage = UsageRecord(window_start=now)
            self._daily_usage[day_key] = day_usage

        return True, "ok"

    def check_budget(self, tenant_id: str, config: TenantConfig) -> tuple[bool, str]:
        """Check if tenant is within budget."""
        month_key = f"{tenant_id}:month"
        monthly = self._monthly_usage.get(month_key)
        
        if not monthly:
            return True, "ok"

        if monthly.cost_usd >= config.monthly_budget_usd:
            return False, f"Monthly budget exhausted: ${monthly.cost_usd:.2f} / ${config.monthly_budget_usd:.2f}"

        if monthly.cost_usd >= config.monthly_budget_usd * config.cost_alert_threshold:
            self._alerts.append({
                "tenant_id": tenant_id,
                "type": "budget_warning",
                "usage": monthly.cost_usd,
                "budget": config.monthly_budget_usd,
                "percentage": monthly.cost_usd / config.monthly_budget_usd * 100,
            })

        return True, "ok"

    def record_usage(
        self,
        tenant_id: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
    ):
        """Record usage for rate limiting and budgeting."""
        now = time.time()

        for store, window in [(self._minute_usage, 60), (self._daily_usage, 86400), (self._monthly_usage, 2592000)]:
            key = f"{tenant_id}:{['minute', 'day', 'month'][[(self._minute_usage, 60), (self._daily_usage, 86400), (self._monthly_usage, 2592000)].index((store, window))]}"
            usage = store.get(key)
            if not usage or now - usage.window_start > window:
                usage = UsageRecord(window_start=now)
                store[key] = usage
            usage.requests += 1
            usage.tokens_input += tokens_input
            usage.tokens_output += tokens_output
            usage.cost_usd += cost_usd

    def get_usage_summary(self, tenant_id: str) -> dict:
        """Get usage summary for a tenant."""
        month_key = f"{tenant_id}:month"
        monthly = self._monthly_usage.get(month_key, UsageRecord())
        day_key = f"{tenant_id}:day"
        daily = self._daily_usage.get(day_key, UsageRecord())

        return {
            "daily_requests": daily.requests,
            "daily_tokens": daily.tokens_input + daily.tokens_output,
            "monthly_requests": monthly.requests,
            "monthly_tokens": monthly.tokens_input + monthly.tokens_output,
            "monthly_cost_usd": monthly.cost_usd,
        }


# =============================================================================
# Tenant Administration API
# =============================================================================

class TenantAdminService:
    """
    Administrative operations for tenant management.
    """

    def __init__(
        self,
        config_store: TenantConfigStore,
        rate_limiter: TenantRateLimiter,
        resource_isolator: TenantResourceIsolator,
        leakage_guard: LeakagePreventionGuard,
    ):
        self.config_store = config_store
        self.rate_limiter = rate_limiter
        self.resource_isolator = resource_isolator
        self.leakage_guard = leakage_guard
        self._audit_log: list[dict] = []

    async def create_tenant(
        self,
        name: str,
        tier: TenantTier,
        admin_user: str,
        config_overrides: dict = None,
    ) -> TenantConfig:
        """Create a new tenant with default configuration."""
        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"

        config = TenantConfig(
            tenant_id=tenant_id,
            name=name,
            tier=tier,
            isolation_level=self._tier_to_isolation(tier),
        )

        if config_overrides:
            for key, value in config_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        await self.config_store.create_tenant(config)
        self._audit("tenant_created", tenant_id, admin_user, {"name": name, "tier": tier.value})
        return config

    async def update_tenant_config(
        self,
        tenant_id: str,
        updates: dict,
        admin_user: str,
    ) -> TenantConfig:
        """Update tenant configuration."""
        config = await self.config_store.update_config(tenant_id, updates)
        self._audit("tenant_updated", tenant_id, admin_user, updates)
        return config

    async def deactivate_tenant(self, tenant_id: str, admin_user: str, reason: str):
        """Deactivate a tenant (all access immediately revoked)."""
        await self.config_store.deactivate_tenant(tenant_id)
        self._audit("tenant_deactivated", tenant_id, admin_user, {"reason": reason})

    async def get_tenant_health(self, tenant_id: str) -> dict:
        """Get health and usage overview for a tenant."""
        config = await self.config_store.get_config(tenant_id)
        if not config:
            raise TenantError(f"Unknown tenant: {tenant_id}")

        usage = self.rate_limiter.get_usage_summary(tenant_id)
        
        return {
            "tenant_id": tenant_id,
            "name": config.name,
            "tier": config.tier.value,
            "is_active": config.is_active,
            "isolation_level": config.isolation_level.value,
            "usage": usage,
            "budget_remaining_usd": config.monthly_budget_usd - usage.get("monthly_cost_usd", 0),
            "security": {
                "leakage_violations": self.leakage_guard.violation_count,
            },
        }

    async def rotate_encryption_key(self, tenant_id: str, admin_user: str):
        """Rotate tenant's encryption key."""
        new_key_id = f"key_{uuid.uuid4().hex[:16]}"
        await self.config_store.update_config(tenant_id, {"encryption_key_id": new_key_id})
        self._audit("key_rotated", tenant_id, admin_user, {"new_key_id": new_key_id})

    def _tier_to_isolation(self, tier: TenantTier) -> IsolationLevel:
        return {
            TenantTier.FREE: IsolationLevel.SHARED,
            TenantTier.STARTER: IsolationLevel.SHARED,
            TenantTier.PROFESSIONAL: IsolationLevel.DEDICATED,
            TenantTier.ENTERPRISE: IsolationLevel.ISOLATED,
        }.get(tier, IsolationLevel.SHARED)

    def _audit(self, event: str, tenant_id: str, actor: str, details: dict):
        self._audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "tenant_id": tenant_id,
            "actor": actor,
            "details": details,
        })


# =============================================================================
# Multi-Tenant Agent Middleware
# =============================================================================

class MultiTenantAgentMiddleware:
    """
    Middleware that wraps the AI agent pipeline with tenant isolation.
    Ensures every operation is scoped to the correct tenant.
    """

    def __init__(
        self,
        extractor: TenantContextExtractor,
        rate_limiter: TenantRateLimiter,
        model_router: TenantModelRouter,
        resource_isolator: TenantResourceIsolator,
        leakage_guard: LeakagePreventionGuard,
    ):
        self.extractor = extractor
        self.rate_limiter = rate_limiter
        self.model_router = model_router
        self.resource_isolator = resource_isolator
        self.leakage_guard = leakage_guard

    async def process_request(
        self,
        token_claims: dict,
        query: str,
        callback,  # The actual agent processing function
    ) -> dict:
        """Process a request with full tenant isolation."""
        # Step 1: Extract tenant context
        context = await self.extractor.extract_from_token(token_claims)

        # Step 2: Check rate limits
        allowed, reason = self.rate_limiter.check_rate_limit(context.tenant_id, context.config)
        if not allowed:
            raise TenantError(f"Rate limit: {reason}")

        # Step 3: Check budget
        allowed, reason = self.rate_limiter.check_budget(context.tenant_id, context.config)
        if not allowed:
            raise TenantError(f"Budget: {reason}")

        # Step 4: Get tenant-specific model config
        model_config = await self.model_router.get_model_config(context.tenant_id)

        # Step 5: Build tenant-specific system prompt
        base_prompt = "You are a helpful AI assistant."
        system_prompt = await self.model_router.build_system_prompt(context.tenant_id, base_prompt)

        # Step 6: Execute within tenant scope
        async with tenant_scope(context.tenant_id, context):
            result = await callback(
                query=query,
                system_prompt=system_prompt,
                model_config=model_config,
                tenant_context=context,
            )

        # Step 7: Check output for leakage
        if isinstance(result, dict) and "response" in result:
            result["response"] = self.leakage_guard.check_llm_output_leakage(
                context.tenant_id,
                result["response"],
                [],  # In production: list of other tenant identifiers
            )

        # Step 8: Record usage
        self.rate_limiter.record_usage(
            context.tenant_id,
            tokens_input=result.get("tokens_input", 0),
            tokens_output=result.get("tokens_output", 0),
            cost_usd=result.get("cost_usd", 0.0),
        )

        return result


# =============================================================================
# Exceptions
# =============================================================================

class TenantError(Exception):
    """Tenant-related error."""
    pass


# =============================================================================
# Usage Example
# =============================================================================

async def example():
    """Demonstrates multi-tenant isolation."""
    # Setup
    config_store = TenantConfigStore()
    rate_limiter = TenantRateLimiter()
    resource_isolator = TenantResourceIsolator()
    leakage_guard = LeakagePreventionGuard()
    
    admin = TenantAdminService(config_store, rate_limiter, resource_isolator, leakage_guard)

    # Create tenants
    tenant_a = await admin.create_tenant("Acme Corp", TenantTier.ENTERPRISE, "admin_1")
    tenant_b = await admin.create_tenant("StartupXYZ", TenantTier.STARTER, "admin_2")

    print(f"Created tenant A: {tenant_a.tenant_id} (Enterprise, Isolated)")
    print(f"Created tenant B: {tenant_b.tenant_id} (Starter, Shared)")

    # Demonstrate isolation
    print(f"\nTenant A vector collection: {resource_isolator.get_vector_db_collection(tenant_a.tenant_id)}")
    print(f"Tenant B vector collection: {resource_isolator.get_vector_db_collection(tenant_b.tenant_id)}")

    # Cross-tenant access attempt
    is_valid = resource_isolator.validate_resource_access(
        tenant_a.tenant_id, tenant_b.tenant_id, "doc_from_b"
    )
    print(f"\nCross-tenant access attempt: {'BLOCKED' if not is_valid else 'ALLOWED'}")

    # Usage within tenant scope
    async with tenant_scope(tenant_a.tenant_id):
        current = get_current_tenant()
        print(f"\nWithin tenant scope: {current}")

    # Rate limiting
    rate_limiter.record_usage(tenant_a.tenant_id, tokens_input=1000, cost_usd=0.01)
    summary = rate_limiter.get_usage_summary(tenant_a.tenant_id)
    print(f"\nTenant A usage: {summary}")


if __name__ == "__main__":
    asyncio.run(example())
