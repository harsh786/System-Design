"""
Enterprise AI Platform - Platform API Design
=============================================

Self-service API layer for platform consumers with tenant isolation,
rate limiting, versioning, and comprehensive lifecycle management.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional


# =============================================================================
# API CONFIGURATION AND TYPES
# =============================================================================

class APIVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class TenantTier(str, Enum):
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class APIRequest:
    """Incoming API request."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: HTTPMethod = HTTPMethod.GET
    path: str = ""
    version: APIVersion = APIVersion.V1
    tenant_id: str = ""
    user_id: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class APIResponse:
    """API response."""
    status_code: int = 200
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    request_id: str = ""
    duration_ms: float = 0.0

    @staticmethod
    def success(data: Any, request_id: str = "", meta: Optional[dict] = None) -> "APIResponse":
        body: dict[str, Any] = {"data": data, "success": True}
        if meta:
            body["meta"] = meta
        return APIResponse(status_code=200, body=body, request_id=request_id)

    @staticmethod
    def created(data: Any, request_id: str = "") -> "APIResponse":
        return APIResponse(status_code=201, body={"data": data, "success": True}, request_id=request_id)

    @staticmethod
    def error(status: int, message: str, code: str, request_id: str = "", details: Optional[dict] = None) -> "APIResponse":
        """RFC 7807 Problem Details format."""
        body = {
            "type": f"https://platform.company.com/errors/{code}",
            "title": message,
            "status": status,
            "detail": details or {},
            "instance": f"/errors/{request_id}",
        }
        return APIResponse(status_code=status, body=body, request_id=request_id)


# =============================================================================
# RATE LIMITING
# =============================================================================

@dataclass
class RateLimitConfig:
    """Rate limit configuration per tenant tier."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10
    concurrent_requests: int = 10


TIER_RATE_LIMITS: dict[TenantTier, RateLimitConfig] = {
    TenantTier.FREE: RateLimitConfig(
        requests_per_minute=20, requests_per_hour=200,
        requests_per_day=1000, burst_size=5, concurrent_requests=3
    ),
    TenantTier.STANDARD: RateLimitConfig(
        requests_per_minute=60, requests_per_hour=2000,
        requests_per_day=20000, burst_size=15, concurrent_requests=10
    ),
    TenantTier.PREMIUM: RateLimitConfig(
        requests_per_minute=200, requests_per_hour=10000,
        requests_per_day=100000, burst_size=50, concurrent_requests=30
    ),
    TenantTier.ENTERPRISE: RateLimitConfig(
        requests_per_minute=1000, requests_per_hour=50000,
        requests_per_day=500000, burst_size=200, concurrent_requests=100
    ),
}


class TokenBucketRateLimiter:
    """Token bucket rate limiter with per-tenant isolation."""

    def __init__(self):
        self._buckets: dict[str, dict[str, Any]] = {}

    def check_and_consume(self, tenant_id: str, tier: TenantTier) -> tuple[bool, dict[str, int]]:
        """Check if request is allowed and consume a token."""
        config = TIER_RATE_LIMITS[tier]
        now = time.time()
        bucket_key = f"{tenant_id}:minute"

        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = {
                "tokens": config.requests_per_minute,
                "last_refill": now,
                "capacity": config.requests_per_minute,
            }

        bucket = self._buckets[bucket_key]
        elapsed = now - bucket["last_refill"]
        refill_rate = config.requests_per_minute / 60.0
        bucket["tokens"] = min(
            bucket["capacity"],
            bucket["tokens"] + elapsed * refill_rate
        )
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            remaining = int(bucket["tokens"])
            return True, {
                "X-RateLimit-Limit": config.requests_per_minute,
                "X-RateLimit-Remaining": remaining,
                "X-RateLimit-Reset": int(now + (config.requests_per_minute - remaining) / refill_rate),
            }
        else:
            retry_after = int((1 - bucket["tokens"]) / refill_rate) + 1
            return False, {
                "X-RateLimit-Limit": config.requests_per_minute,
                "X-RateLimit-Remaining": 0,
                "Retry-After": retry_after,
            }


# =============================================================================
# TENANT MANAGEMENT
# =============================================================================

@dataclass
class Tenant:
    """Platform tenant (team/project)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: TenantTier = TenantTier.STANDARD
    owner_email: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    budget_monthly_usd: float = 1000.0
    budget_used_usd: float = 0.0
    api_keys: list[dict[str, Any]] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    allowed_environments: list[str] = field(default_factory=lambda: ["development", "staging"])
    metadata: dict[str, Any] = field(default_factory=dict)
    suspended: bool = False
    suspension_reason: Optional[str] = None


class TenantManager:
    """Manage tenants and their isolation."""

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._api_key_to_tenant: dict[str, str] = {}

    def create_tenant(self, name: str, owner_email: str, tier: TenantTier = TenantTier.STANDARD) -> Tenant:
        tenant = Tenant(name=name, owner_email=owner_email, tier=tier)
        api_key = self._generate_api_key(tenant.id)
        tenant.api_keys.append({"key": api_key, "created_at": datetime.utcnow().isoformat(), "active": True})
        self._tenants[tenant.id] = tenant
        self._api_key_to_tenant[api_key] = tenant.id
        return tenant

    def authenticate(self, api_key: str) -> Optional[Tenant]:
        """Authenticate a request by API key."""
        tenant_id = self._api_key_to_tenant.get(api_key)
        if not tenant_id:
            return None
        tenant = self._tenants.get(tenant_id)
        if tenant and not tenant.suspended:
            return tenant
        return None

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def suspend_tenant(self, tenant_id: str, reason: str) -> bool:
        tenant = self._tenants.get(tenant_id)
        if tenant:
            tenant.suspended = True
            tenant.suspension_reason = reason
            return True
        return False

    def _generate_api_key(self, tenant_id: str) -> str:
        raw = f"{tenant_id}:{uuid.uuid4()}:{time.time()}"
        return f"aip_{hashlib.sha256(raw.encode()).hexdigest()[:48]}"


# =============================================================================
# USAGE AND COST TRACKING
# =============================================================================

@dataclass
class UsageRecord:
    """A single usage record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resource_type: str = ""  # model, embedding, tool, eval
    resource_id: str = ""
    operation: str = ""  # inference, embed, execute, run
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class UsageTracker:
    """Track usage and costs per tenant."""

    def __init__(self):
        self._records: list[UsageRecord] = []
        self._tenant_totals: dict[str, dict[str, float]] = defaultdict(
            lambda: {"cost": 0.0, "tokens": 0, "requests": 0}
        )

    def record(self, record: UsageRecord):
        self._records.append(record)
        totals = self._tenant_totals[record.tenant_id]
        totals["cost"] += record.cost_usd
        totals["tokens"] += record.tokens_input + record.tokens_output
        totals["requests"] += 1

    def get_tenant_usage(
        self, tenant_id: str, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> dict[str, Any]:
        """Get usage summary for a tenant."""
        records = [r for r in self._records if r.tenant_id == tenant_id]
        if start:
            records = [r for r in records if r.timestamp >= start]
        if end:
            records = [r for r in records if r.timestamp <= end]

        total_cost = sum(r.cost_usd for r in records)
        total_tokens = sum(r.tokens_input + r.tokens_output for r in records)
        total_requests = len(records)
        by_resource: dict[str, float] = defaultdict(float)
        for r in records:
            by_resource[r.resource_type] += r.cost_usd

        return {
            "tenant_id": tenant_id,
            "period_start": (start or datetime.min).isoformat(),
            "period_end": (end or datetime.utcnow()).isoformat(),
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "cost_by_resource_type": dict(by_resource),
            "avg_latency_ms": sum(r.latency_ms for r in records) / max(len(records), 1),
            "success_rate": sum(1 for r in records if r.success) / max(len(records), 1),
        }

    def check_budget(self, tenant_id: str, monthly_budget: float) -> tuple[bool, float]:
        """Check if tenant is within budget. Returns (within_budget, remaining)."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        records = [
            r for r in self._records
            if r.tenant_id == tenant_id and r.timestamp >= month_start
        ]
        spent = sum(r.cost_usd for r in records)
        return spent <= monthly_budget, monthly_budget - spent


# =============================================================================
# API VERSIONING AND COMPATIBILITY
# =============================================================================

@dataclass
class APIEndpoint:
    """Definition of an API endpoint."""
    path: str = ""
    method: HTTPMethod = HTTPMethod.GET
    handler: Optional[Callable] = None
    version_introduced: APIVersion = APIVersion.V1
    version_deprecated: Optional[APIVersion] = None
    description: str = ""
    requires_auth: bool = True
    rate_limit_weight: int = 1  # Some endpoints count as multiple requests


class APIRouter:
    """Version-aware API router."""

    def __init__(self):
        self._routes: dict[APIVersion, dict[str, dict[HTTPMethod, APIEndpoint]]] = {
            v: {} for v in APIVersion
        }

    def register(self, endpoint: APIEndpoint):
        """Register an endpoint."""
        for version in APIVersion:
            if version.value >= endpoint.version_introduced.value:
                if endpoint.version_deprecated and version.value >= endpoint.version_deprecated.value:
                    continue
                if endpoint.path not in self._routes[version]:
                    self._routes[version][endpoint.path] = {}
                self._routes[version][endpoint.path][endpoint.method] = endpoint

    def resolve(self, version: APIVersion, path: str, method: HTTPMethod) -> Optional[APIEndpoint]:
        """Resolve a request to an endpoint."""
        version_routes = self._routes.get(version, {})
        path_routes = version_routes.get(path, {})
        return path_routes.get(method)

    def get_all_endpoints(self, version: APIVersion) -> list[APIEndpoint]:
        """Get all endpoints for a version (for OpenAPI spec generation)."""
        endpoints = []
        for path_routes in self._routes.get(version, {}).values():
            endpoints.extend(path_routes.values())
        return endpoints


# =============================================================================
# PLATFORM API SERVICE
# =============================================================================

class PlatformAPIService:
    """
    Main platform API service handling all self-service operations.
    Implements tenant isolation, rate limiting, versioning, and comprehensive
    lifecycle management for AI platform resources.
    """

    def __init__(self):
        self.tenant_manager = TenantManager()
        self.rate_limiter = TokenBucketRateLimiter()
        self.usage_tracker = UsageTracker()
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self):
        """Register all API routes."""
        routes = [
            # Agent Deployment
            APIEndpoint(path="/agents", method=HTTPMethod.POST, handler=self.deploy_agent, description="Deploy a new agent"),
            APIEndpoint(path="/agents", method=HTTPMethod.GET, handler=self.list_agents, description="List deployed agents"),
            APIEndpoint(path="/agents/{id}", method=HTTPMethod.GET, handler=self.get_agent, description="Get agent details"),
            APIEndpoint(path="/agents/{id}", method=HTTPMethod.PATCH, handler=self.update_agent, description="Update agent config"),
            APIEndpoint(path="/agents/{id}", method=HTTPMethod.DELETE, handler=self.undeploy_agent, description="Undeploy agent"),
            APIEndpoint(path="/agents/{id}/health", method=HTTPMethod.GET, handler=self.agent_health, description="Agent health check"),

            # Prompt Deployment
            APIEndpoint(path="/prompts", method=HTTPMethod.POST, handler=self.deploy_prompt, description="Deploy a prompt version"),
            APIEndpoint(path="/prompts", method=HTTPMethod.GET, handler=self.list_prompts, description="List prompts"),
            APIEndpoint(path="/prompts/{id}/render", method=HTTPMethod.POST, handler=self.render_prompt, description="Render prompt with variables"),
            APIEndpoint(path="/prompts/{id}/promote", method=HTTPMethod.POST, handler=self.promote_prompt, description="Promote prompt to environment"),

            # Eval Execution
            APIEndpoint(path="/evals", method=HTTPMethod.POST, handler=self.create_eval, description="Create eval suite"),
            APIEndpoint(path="/evals/{id}/run", method=HTTPMethod.POST, handler=self.run_eval, description="Execute eval suite"),
            APIEndpoint(path="/evals/{id}/results", method=HTTPMethod.GET, handler=self.get_eval_results, description="Get eval results"),

            # Model Access
            APIEndpoint(path="/models", method=HTTPMethod.GET, handler=self.list_models, description="List available models"),
            APIEndpoint(path="/models/{id}/request-access", method=HTTPMethod.POST, handler=self.request_model_access, description="Request access to a model"),
            APIEndpoint(path="/models/{id}/invoke", method=HTTPMethod.POST, handler=self.invoke_model, description="Invoke a model"),

            # Tool Registration
            APIEndpoint(path="/tools", method=HTTPMethod.POST, handler=self.register_tool, description="Register a new tool"),
            APIEndpoint(path="/tools", method=HTTPMethod.GET, handler=self.list_tools, description="List available tools"),
            APIEndpoint(path="/tools/{id}/invoke", method=HTTPMethod.POST, handler=self.invoke_tool, description="Invoke a tool"),

            # Health and Status
            APIEndpoint(path="/health", method=HTTPMethod.GET, handler=self.health_check, requires_auth=False, description="Platform health"),
            APIEndpoint(path="/status", method=HTTPMethod.GET, handler=self.platform_status, description="Detailed platform status"),

            # Usage and Cost
            APIEndpoint(path="/usage", method=HTTPMethod.GET, handler=self.get_usage, description="Get usage summary"),
            APIEndpoint(path="/usage/cost", method=HTTPMethod.GET, handler=self.get_cost_breakdown, description="Get cost breakdown"),
            APIEndpoint(path="/usage/budget", method=HTTPMethod.GET, handler=self.get_budget_status, description="Get budget status"),
        ]
        for route in routes:
            self.router.register(route)

    # -------------------------------------------------------------------------
    # REQUEST PROCESSING PIPELINE
    # -------------------------------------------------------------------------

    async def handle_request(self, request: APIRequest) -> APIResponse:
        """Main request processing pipeline."""
        start_time = time.time()

        # 1. Resolve route
        endpoint = self.router.resolve(request.version, request.path, request.method)
        if not endpoint:
            return APIResponse.error(404, "Not Found", "route_not_found", request.request_id)

        # 2. Authentication
        if endpoint.requires_auth:
            api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
            tenant = self.tenant_manager.authenticate(api_key)
            if not tenant:
                return APIResponse.error(401, "Unauthorized", "invalid_api_key", request.request_id)
            request.tenant_id = tenant.id
        else:
            tenant = None

        # 3. Rate limiting
        if tenant:
            allowed, rate_headers = self.rate_limiter.check_and_consume(tenant.id, tenant.tier)
            if not allowed:
                resp = APIResponse.error(429, "Rate limit exceeded", "rate_limited", request.request_id)
                resp.headers.update({k: str(v) for k, v in rate_headers.items()})
                return resp

        # 4. Budget check
        if tenant and tenant.budget_monthly_usd > 0:
            within_budget, remaining = self.usage_tracker.check_budget(tenant.id, tenant.budget_monthly_usd)
            if not within_budget:
                return APIResponse.error(
                    402, "Budget exceeded", "budget_exceeded", request.request_id,
                    {"monthly_budget": tenant.budget_monthly_usd, "remaining": remaining}
                )

        # 5. Execute handler
        try:
            response = await endpoint.handler(request)
        except ValidationError as e:
            response = APIResponse.error(400, str(e), "validation_error", request.request_id)
        except PermissionError as e:
            response = APIResponse.error(403, str(e), "forbidden", request.request_id)
        except NotFoundError as e:
            response = APIResponse.error(404, str(e), "not_found", request.request_id)
        except Exception as e:
            response = APIResponse.error(500, "Internal server error", "internal_error", request.request_id)

        # 6. Record metrics
        duration_ms = (time.time() - start_time) * 1000
        response.duration_ms = duration_ms
        response.request_id = request.request_id
        response.headers["X-Request-ID"] = request.request_id
        response.headers["X-Response-Time-Ms"] = str(int(duration_ms))

        return response

    # -------------------------------------------------------------------------
    # AGENT DEPLOYMENT API
    # -------------------------------------------------------------------------

    async def deploy_agent(self, request: APIRequest) -> APIResponse:
        """Deploy a new agent."""
        body = request.body
        required_fields = ["name", "model_id", "prompt_ids"]
        self._validate_required(body, required_fields)

        agent_id = str(uuid.uuid4())
        agent = {
            "id": agent_id,
            "tenant_id": request.tenant_id,
            "name": body["name"],
            "description": body.get("description", ""),
            "model_id": body["model_id"],
            "prompt_ids": body["prompt_ids"],
            "tool_ids": body.get("tool_ids", []),
            "guardrails": body.get("guardrails", {}),
            "environment": body.get("environment", "development"),
            "status": "deploying",
            "endpoint": f"https://agents.platform.company.com/{request.tenant_id}/{agent_id}",
            "created_at": datetime.utcnow().isoformat(),
            "health_check_url": f"https://agents.platform.company.com/{request.tenant_id}/{agent_id}/health",
        }
        # In production: trigger actual deployment pipeline
        agent["status"] = "active"
        return APIResponse.created(agent, request.request_id)

    async def list_agents(self, request: APIRequest) -> APIResponse:
        """List agents for the tenant."""
        # In production: query agent registry filtered by tenant
        return APIResponse.success([], request.request_id, meta={"total": 0, "page": 1, "page_size": 20})

    async def get_agent(self, request: APIRequest) -> APIResponse:
        """Get agent details."""
        agent_id = request.path.split("/")[-1]
        # In production: fetch from registry
        return APIResponse.success({"id": agent_id, "status": "active"}, request.request_id)

    async def update_agent(self, request: APIRequest) -> APIResponse:
        """Update agent configuration (rolling update)."""
        agent_id = request.path.split("/")[-1]
        updates = request.body
        # In production: validate changes, trigger rolling update
        return APIResponse.success({"id": agent_id, "status": "updating", "updates": updates}, request.request_id)

    async def undeploy_agent(self, request: APIRequest) -> APIResponse:
        """Undeploy (delete) an agent."""
        agent_id = request.path.split("/")[-1]
        return APIResponse.success({"id": agent_id, "status": "undeployed"}, request.request_id)

    async def agent_health(self, request: APIRequest) -> APIResponse:
        """Check agent health."""
        agent_id = request.path.split("/")[-2]
        return APIResponse.success({
            "id": agent_id,
            "healthy": True,
            "latency_p50_ms": 120,
            "latency_p99_ms": 850,
            "error_rate_1h": 0.002,
            "last_invocation": datetime.utcnow().isoformat(),
        }, request.request_id)

    # -------------------------------------------------------------------------
    # PROMPT DEPLOYMENT API
    # -------------------------------------------------------------------------

    async def deploy_prompt(self, request: APIRequest) -> APIResponse:
        """Deploy a new prompt version."""
        body = request.body
        self._validate_required(body, ["name", "template"])

        prompt = {
            "id": str(uuid.uuid4()),
            "tenant_id": request.tenant_id,
            "name": body["name"],
            "version": body.get("version", "1.0.0"),
            "template": body["template"],
            "system_prompt": body.get("system_prompt"),
            "variables": body.get("variables", []),
            "environment": body.get("environment", "development"),
            "created_at": datetime.utcnow().isoformat(),
        }
        return APIResponse.created(prompt, request.request_id)

    async def list_prompts(self, request: APIRequest) -> APIResponse:
        """List prompts for the tenant."""
        return APIResponse.success([], request.request_id, meta={"total": 0})

    async def render_prompt(self, request: APIRequest) -> APIResponse:
        """Render a prompt template with variables."""
        body = request.body
        variables = body.get("variables", {})
        # In production: fetch prompt, validate variables, render
        rendered = f"[Rendered prompt with variables: {variables}]"
        return APIResponse.success({"rendered": rendered, "token_count": len(rendered.split())}, request.request_id)

    async def promote_prompt(self, request: APIRequest) -> APIResponse:
        """Promote a prompt to a target environment."""
        body = request.body
        target_env = body.get("environment", "staging")
        prompt_id = request.path.split("/")[-2]

        # In production: check eval gate, perform promotion
        if target_env == "production":
            # Require passing evals
            return APIResponse.success({
                "id": prompt_id,
                "promoted_to": target_env,
                "eval_check": "passed",
                "promoted_at": datetime.utcnow().isoformat(),
            }, request.request_id)
        return APIResponse.success({"id": prompt_id, "promoted_to": target_env}, request.request_id)

    # -------------------------------------------------------------------------
    # EVAL EXECUTION API
    # -------------------------------------------------------------------------

    async def create_eval(self, request: APIRequest) -> APIResponse:
        """Create an eval suite."""
        body = request.body
        self._validate_required(body, ["name", "dataset", "metrics"])

        eval_suite = {
            "id": str(uuid.uuid4()),
            "tenant_id": request.tenant_id,
            "name": body["name"],
            "dataset_size": len(body["dataset"]),
            "metrics": body["metrics"],
            "target_type": body.get("target_type", "prompt"),
            "is_gate": body.get("is_gate", False),
            "created_at": datetime.utcnow().isoformat(),
        }
        return APIResponse.created(eval_suite, request.request_id)

    async def run_eval(self, request: APIRequest) -> APIResponse:
        """Execute an eval suite against a target."""
        body = request.body
        eval_id = request.path.split("/")[-2]
        target_id = body.get("target_id", "")
        target_version = body.get("target_version", "latest")

        # In production: queue eval job, return job ID for polling
        run = {
            "run_id": str(uuid.uuid4()),
            "eval_id": eval_id,
            "target_id": target_id,
            "target_version": target_version,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "estimated_duration_seconds": 120,
            "poll_url": f"/evals/{eval_id}/runs/{{run_id}}",
        }
        return APIResponse.success(run, request.request_id)

    async def get_eval_results(self, request: APIRequest) -> APIResponse:
        """Get eval results."""
        eval_id = request.path.split("/")[-2]
        return APIResponse.success({
            "eval_id": eval_id,
            "runs": [],
            "latest_score": None,
            "trend": "stable",
        }, request.request_id)

    # -------------------------------------------------------------------------
    # MODEL ACCESS API
    # -------------------------------------------------------------------------

    async def list_models(self, request: APIRequest) -> APIResponse:
        """List models available to the tenant."""
        # In production: filter by tenant's allowed models and risk tier
        models = [
            {
                "id": "gpt-4o",
                "provider": "openai",
                "risk_tier": "t2_standard",
                "capabilities": ["chat", "function_calling", "vision"],
                "cost_per_1k_input": 0.0025,
                "cost_per_1k_output": 0.01,
                "status": "available",
            },
            {
                "id": "claude-sonnet-4-20250514",
                "provider": "anthropic",
                "risk_tier": "t2_standard",
                "capabilities": ["chat", "function_calling", "reasoning"],
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "status": "available",
            },
        ]
        return APIResponse.success(models, request.request_id)

    async def request_model_access(self, request: APIRequest) -> APIResponse:
        """Request access to a restricted model."""
        model_id = request.path.split("/")[-2]
        body = request.body
        justification = body.get("justification", "")

        access_request = {
            "id": str(uuid.uuid4()),
            "model_id": model_id,
            "tenant_id": request.tenant_id,
            "justification": justification,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "estimated_review_time": "24-48 hours",
        }
        return APIResponse.created(access_request, request.request_id)

    async def invoke_model(self, request: APIRequest) -> APIResponse:
        """Invoke a model through the platform gateway."""
        model_id = request.path.split("/")[-2]
        body = request.body
        messages = body.get("messages", [])

        # In production: route through AI gateway with all policies applied
        response_data = {
            "id": str(uuid.uuid4()),
            "model": model_id,
            "usage": {"input_tokens": 150, "output_tokens": 300, "total_tokens": 450},
            "cost_usd": 0.0034,
            "latency_ms": 1200,
            "choices": [{"message": {"role": "assistant", "content": "[Model response]"}}],
            "cached": False,
        }

        # Record usage
        self.usage_tracker.record(UsageRecord(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            resource_type="model",
            resource_id=model_id,
            operation="inference",
            tokens_input=150,
            tokens_output=300,
            cost_usd=0.0034,
            latency_ms=1200,
        ))

        return APIResponse.success(response_data, request.request_id)

    # -------------------------------------------------------------------------
    # TOOL REGISTRATION API
    # -------------------------------------------------------------------------

    async def register_tool(self, request: APIRequest) -> APIResponse:
        """Register a new tool."""
        body = request.body
        self._validate_required(body, ["name", "description", "endpoint", "parameters"])

        tool = {
            "id": str(uuid.uuid4()),
            "tenant_id": request.tenant_id,
            "name": body["name"],
            "description": body["description"],
            "endpoint": body["endpoint"],
            "parameters": body["parameters"],
            "risk_level": body.get("risk_level", "read_only_internal"),
            "status": "active" if body.get("risk_level", "read_only_internal").startswith("read") else "pending_review",
            "created_at": datetime.utcnow().isoformat(),
        }
        return APIResponse.created(tool, request.request_id)

    async def list_tools(self, request: APIRequest) -> APIResponse:
        """List tools available to the tenant."""
        return APIResponse.success([], request.request_id, meta={"total": 0})

    async def invoke_tool(self, request: APIRequest) -> APIResponse:
        """Invoke a tool through the platform."""
        tool_id = request.path.split("/")[-2]
        body = request.body
        # In production: validate permissions, call tool, record usage
        return APIResponse.success({
            "tool_id": tool_id,
            "result": {"status": "success"},
            "latency_ms": 45,
        }, request.request_id)

    # -------------------------------------------------------------------------
    # HEALTH AND STATUS API
    # -------------------------------------------------------------------------

    async def health_check(self, request: APIRequest) -> APIResponse:
        """Platform health check (unauthenticated)."""
        return APIResponse.success({
            "status": "healthy",
            "version": "2.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "api": "healthy",
                "registry": "healthy",
                "gateway": "healthy",
                "eval_engine": "healthy",
            }
        }, request.request_id)

    async def platform_status(self, request: APIRequest) -> APIResponse:
        """Detailed platform status (authenticated)."""
        return APIResponse.success({
            "status": "operational",
            "models_available": 12,
            "models_degraded": 0,
            "active_agents": 47,
            "active_experiments": 5,
            "avg_gateway_latency_ms": 85,
            "requests_last_hour": 15420,
            "incidents_active": 0,
            "next_maintenance": None,
        }, request.request_id)

    # -------------------------------------------------------------------------
    # USAGE AND COST API
    # -------------------------------------------------------------------------

    async def get_usage(self, request: APIRequest) -> APIResponse:
        """Get usage summary for the tenant."""
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        start_dt = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(days=30)
        end_dt = datetime.fromisoformat(end) if end else datetime.utcnow()

        usage = self.usage_tracker.get_tenant_usage(request.tenant_id, start_dt, end_dt)
        return APIResponse.success(usage, request.request_id)

    async def get_cost_breakdown(self, request: APIRequest) -> APIResponse:
        """Get cost breakdown by resource type."""
        usage = self.usage_tracker.get_tenant_usage(request.tenant_id)
        return APIResponse.success({
            "total_cost_usd": usage["total_cost_usd"],
            "breakdown": usage["cost_by_resource_type"],
            "daily_trend": [],  # In production: daily cost data points
            "projected_monthly": usage["total_cost_usd"] * 30,
        }, request.request_id)

    async def get_budget_status(self, request: APIRequest) -> APIResponse:
        """Get budget status for the tenant."""
        tenant = self.tenant_manager.get_tenant(request.tenant_id)
        if not tenant:
            raise NotFoundError("Tenant not found")
        within_budget, remaining = self.usage_tracker.check_budget(request.tenant_id, tenant.budget_monthly_usd)
        return APIResponse.success({
            "monthly_budget_usd": tenant.budget_monthly_usd,
            "spent_usd": tenant.budget_monthly_usd - remaining,
            "remaining_usd": remaining,
            "within_budget": within_budget,
            "utilization_pct": ((tenant.budget_monthly_usd - remaining) / max(tenant.budget_monthly_usd, 0.01)) * 100,
            "projected_overage_usd": max(0, (tenant.budget_monthly_usd - remaining) * 30 / max(datetime.utcnow().day, 1) - tenant.budget_monthly_usd),
        }, request.request_id)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _validate_required(self, body: dict[str, Any], fields: list[str]):
        """Validate required fields are present."""
        missing = [f for f in fields if f not in body]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")


class ValidationError(Exception):
    pass

class NotFoundError(Exception):
    pass


# =============================================================================
# OPENAPI SPEC GENERATION
# =============================================================================

def generate_openapi_spec(service: PlatformAPIService, version: APIVersion = APIVersion.V1) -> dict[str, Any]:
    """Generate OpenAPI 3.1 specification for the platform API."""
    endpoints = service.router.get_all_endpoints(version)
    paths: dict[str, Any] = {}

    for ep in endpoints:
        if ep.path not in paths:
            paths[ep.path] = {}
        paths[ep.path][ep.method.value.lower()] = {
            "summary": ep.description,
            "security": [{"bearerAuth": []}] if ep.requires_auth else [],
            "responses": {
                "200": {"description": "Success"},
                "400": {"description": "Validation error"},
                "401": {"description": "Unauthorized"},
                "429": {"description": "Rate limited"},
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Enterprise AI Platform API",
            "version": version.value,
            "description": "Self-service API for AI platform consumers",
        },
        "servers": [
            {"url": f"https://api.aiplatform.company.com/{version.value}"}
        ],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"}
            }
        }
    }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def main():
    """Demonstrate platform API usage."""
    service = PlatformAPIService()

    # Create a tenant
    tenant = service.tenant_manager.create_tenant(
        name="product-team-alpha",
        owner_email="alpha@company.com",
        tier=TenantTier.STANDARD,
    )
    api_key = tenant.api_keys[0]["key"]
    print(f"Created tenant: {tenant.name} (key: {api_key[:20]}...)")

    # Make API requests
    # 1. Health check (no auth)
    resp = await service.handle_request(APIRequest(
        method=HTTPMethod.GET, path="/health", version=APIVersion.V1
    ))
    print(f"Health: {resp.status_code} - {resp.body['data']['status']}")

    # 2. List models (with auth)
    resp = await service.handle_request(APIRequest(
        method=HTTPMethod.GET, path="/models", version=APIVersion.V1,
        headers={"Authorization": f"Bearer {api_key}"}
    ))
    print(f"Models: {resp.status_code} - {len(resp.body['data'])} available")

    # 3. Deploy an agent
    resp = await service.handle_request(APIRequest(
        method=HTTPMethod.POST, path="/agents", version=APIVersion.V1,
        headers={"Authorization": f"Bearer {api_key}"},
        body={
            "name": "support-agent",
            "model_id": "gpt-4o",
            "prompt_ids": ["prompt-001"],
            "tool_ids": ["tool-lookup-customer"],
            "environment": "development",
        }
    ))
    print(f"Deploy agent: {resp.status_code} - {resp.body['data'].get('status')}")

    # 4. Invoke model
    resp = await service.handle_request(APIRequest(
        method=HTTPMethod.POST, path="/models/{id}/invoke", version=APIVersion.V1,
        headers={"Authorization": f"Bearer {api_key}"},
        body={"messages": [{"role": "user", "content": "Hello"}]}
    ))
    print(f"Invoke model: {resp.status_code} - cost: ${resp.body['data'].get('cost_usd', 0)}")

    # 5. Check usage
    resp = await service.handle_request(APIRequest(
        method=HTTPMethod.GET, path="/usage", version=APIVersion.V1,
        headers={"Authorization": f"Bearer {api_key}"}
    ))
    print(f"Usage: {resp.status_code} - total cost: ${resp.body['data']['total_cost_usd']}")

    # Generate OpenAPI spec
    spec = generate_openapi_spec(service)
    print(f"\nOpenAPI spec: {len(spec['paths'])} paths registered")


if __name__ == "__main__":
    asyncio.run(main())
