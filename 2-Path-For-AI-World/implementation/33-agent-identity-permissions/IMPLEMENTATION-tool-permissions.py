"""
Per-Tool Permission System
===========================
Tool permission schema, pre-execution permission checks, scoped token
generation, risk classification, and dynamic permission adjustment.
"""

import uuid
import time
import json
import fnmatch
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Any, Tuple
from abc import ABC, abstractmethod
import hashlib
import jwt


# =============================================================================
# ENUMS
# =============================================================================

class ToolRiskLevel(Enum):
    """Risk classification for tools."""
    SAFE = 1           # Read-only, no side effects
    LOW = 2            # Read with potential data exposure
    MEDIUM = 3         # Write to non-critical resources
    HIGH = 4           # Write to critical resources, irreversible
    CRITICAL = 5       # Security-impacting, production-affecting


class ToolCategory(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMITED = "rate_limited"


# =============================================================================
# TOOL PERMISSION SCHEMA
# =============================================================================

@dataclass
class ToolPermissionSchema:
    """
    Defines the permission requirements for a tool.
    Every tool must declare what it needs upfront.
    """
    tool_id: str
    tool_name: str
    tool_version: str
    category: ToolCategory
    risk_level: ToolRiskLevel
    description: str

    # What scopes this tool requires
    required_scopes: List[str]        # e.g., ["repo:read", "file:read"]
    optional_scopes: List[str] = field(default_factory=list)

    # Resource patterns this tool accesses
    resource_patterns: List[str] = field(default_factory=list)  # Glob patterns

    # Rate limiting
    max_calls_per_minute: int = 60
    max_calls_per_hour: int = 1000
    max_concurrent: int = 5

    # Data sensitivity
    accesses_pii: bool = False
    accesses_secrets: bool = False
    accesses_financial: bool = False

    # Side effects
    has_side_effects: bool = False
    is_reversible: bool = True
    modifies_permissions: bool = False

    # Approval requirements
    always_requires_approval: bool = False
    approval_for_resources: List[str] = field(default_factory=list)  # Patterns

    # Token requirements
    max_token_lifetime_seconds: int = 300
    requires_single_use_token: bool = False

    def requires_scope(self, scope: str) -> bool:
        return scope in self.required_scopes

    def get_minimum_scopes(self) -> Set[str]:
        return set(self.required_scopes)


@dataclass
class ToolPermissionGrant:
    """A specific permission grant for a tool invocation."""
    grant_id: str
    tool_id: str
    agent_id: str
    user_id: str
    tenant_id: str
    granted_scopes: List[str]
    resource: str
    token: str
    issued_at: datetime
    expires_at: datetime
    max_uses: int = 1
    uses: int = 0
    revoked: bool = False

    @property
    def is_valid(self) -> bool:
        if self.revoked:
            return False
        if self.uses >= self.max_uses:
            return False
        return datetime.now(timezone.utc) < self.expires_at


# =============================================================================
# TOOL REGISTRY
# =============================================================================

class ToolRegistry:
    """Registry of all tools and their permission schemas."""

    def __init__(self):
        self._tools: Dict[str, ToolPermissionSchema] = {}

    def register_tool(self, schema: ToolPermissionSchema) -> None:
        self._tools[schema.tool_id] = schema

    def get_tool(self, tool_id: str) -> Optional[ToolPermissionSchema]:
        return self._tools.get(tool_id)

    def get_tools_by_category(self, category: ToolCategory) -> List[ToolPermissionSchema]:
        return [t for t in self._tools.values() if t.category == category]

    def get_tools_by_risk(self, max_risk: ToolRiskLevel) -> List[ToolPermissionSchema]:
        return [t for t in self._tools.values() if t.risk_level.value <= max_risk.value]

    def list_all(self) -> List[ToolPermissionSchema]:
        return list(self._tools.values())


# =============================================================================
# RATE LIMITER
# =============================================================================

class ToolRateLimiter:
    """Per-tool, per-user/agent rate limiting."""

    def __init__(self):
        # key: (tool_id, agent_id, user_id) -> list of timestamps
        self._calls: Dict[Tuple[str, str, str], List[float]] = {}
        self._concurrent: Dict[Tuple[str, str, str], int] = {}

    def check_rate_limit(
        self, tool_id: str, agent_id: str, user_id: str, schema: ToolPermissionSchema
    ) -> Tuple[bool, str]:
        """Check if the rate limit allows this call. Returns (allowed, reason)."""
        key = (tool_id, agent_id, user_id)
        now = time.time()

        # Clean old entries
        calls = self._calls.get(key, [])
        calls = [t for t in calls if t > now - 3600]
        self._calls[key] = calls

        # Check per-minute
        minute_ago = now - 60
        minute_calls = [t for t in calls if t > minute_ago]
        if len(minute_calls) >= schema.max_calls_per_minute:
            return False, f"Rate limit: {schema.max_calls_per_minute}/minute exceeded"

        # Check per-hour
        if len(calls) >= schema.max_calls_per_hour:
            return False, f"Rate limit: {schema.max_calls_per_hour}/hour exceeded"

        # Check concurrent
        concurrent = self._concurrent.get(key, 0)
        if concurrent >= schema.max_concurrent:
            return False, f"Concurrent limit: {schema.max_concurrent} exceeded"

        return True, "OK"

    def record_call_start(self, tool_id: str, agent_id: str, user_id: str) -> None:
        key = (tool_id, agent_id, user_id)
        self._calls.setdefault(key, []).append(time.time())
        self._concurrent[key] = self._concurrent.get(key, 0) + 1

    def record_call_end(self, tool_id: str, agent_id: str, user_id: str) -> None:
        key = (tool_id, agent_id, user_id)
        self._concurrent[key] = max(0, self._concurrent.get(key, 0) - 1)


# =============================================================================
# SCOPED TOKEN GENERATOR
# =============================================================================

class ScopedTokenGenerator:
    """Generates per-tool, per-action scoped tokens."""

    def __init__(self, signing_key: str, issuer: str = "tool-token-service"):
        self._signing_key = signing_key
        self._issuer = issuer
        self._active_tokens: Dict[str, ToolPermissionGrant] = {}

    def generate_tool_token(
        self,
        tool_id: str,
        tool_schema: ToolPermissionSchema,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        granted_scopes: List[str],
        resource: str,
        lifetime_seconds: Optional[int] = None,
        max_uses: int = 1,
    ) -> ToolPermissionGrant:
        """Generate a scoped token for a specific tool invocation."""
        now = datetime.now(timezone.utc)

        # Enforce tool's max lifetime
        effective_lifetime = min(
            lifetime_seconds or tool_schema.max_token_lifetime_seconds,
            tool_schema.max_token_lifetime_seconds,
        )

        # For single-use tools, enforce single use
        if tool_schema.requires_single_use_token:
            max_uses = 1

        grant_id = str(uuid.uuid4())

        # Create JWT token
        payload = {
            "iss": self._issuer,
            "sub": user_id,
            "act": {"sub": agent_id},
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=effective_lifetime)).timestamp()),
            "jti": grant_id,
            "tool_id": tool_id,
            "tenant_id": tenant_id,
            "scopes": granted_scopes,
            "resource": resource,
            "max_uses": max_uses,
            "risk_level": tool_schema.risk_level.value,
            "token_type": "tool_scoped",
        }
        token = jwt.encode(payload, self._signing_key, algorithm="HS256")

        grant = ToolPermissionGrant(
            grant_id=grant_id,
            tool_id=tool_id,
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            granted_scopes=granted_scopes,
            resource=resource,
            token=token,
            issued_at=now,
            expires_at=now + timedelta(seconds=effective_lifetime),
            max_uses=max_uses,
        )

        self._active_tokens[grant_id] = grant
        return grant

    def validate_tool_token(self, token: str, tool_id: str) -> Optional[Dict[str, Any]]:
        """Validate a tool token. Returns claims if valid."""
        try:
            payload = jwt.decode(
                token, self._signing_key, algorithms=["HS256"], issuer=self._issuer
            )
            # Verify tool binding
            if payload.get("tool_id") != tool_id:
                return None

            grant_id = payload.get("jti")
            grant = self._active_tokens.get(grant_id)
            if not grant or not grant.is_valid:
                return None

            # Record use
            grant.uses += 1
            return payload
        except jwt.InvalidTokenError:
            return None

    def revoke_tool_token(self, grant_id: str) -> None:
        grant = self._active_tokens.get(grant_id)
        if grant:
            grant.revoked = True


# =============================================================================
# PERMISSION CHECK ENGINE
# =============================================================================

@dataclass
class PermissionCheckResult:
    """Result of a permission check."""
    decision: PermissionDecision
    reason: str
    tool_id: str
    agent_id: str
    user_id: str
    resource: str
    granted_scopes: List[str] = field(default_factory=list)
    token: Optional[str] = None
    grant_id: Optional[str] = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # For rate limiting info
    remaining_calls_minute: Optional[int] = None
    remaining_calls_hour: Optional[int] = None


class ToolPermissionChecker:
    """
    Main permission check engine. Called before every tool execution.
    Implements the full check sequence.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        token_generator: ScopedTokenGenerator,
        rate_limiter: ToolRateLimiter,
    ):
        self._registry = tool_registry
        self._token_generator = token_generator
        self._rate_limiter = rate_limiter
        # Agent permission boundaries (would come from identity service in prod)
        self._agent_boundaries: Dict[str, Dict] = {}
        # User permissions (would come from IAM service in prod)
        self._user_permissions: Dict[str, Set[str]] = {}
        # Delegation scopes (would come from delegation service in prod)
        self._delegation_scopes: Dict[str, Set[str]] = {}

    def set_agent_boundary(self, agent_id: str, boundary: Dict) -> None:
        self._agent_boundaries[agent_id] = boundary

    def set_user_permissions(self, user_id: str, permissions: Set[str]) -> None:
        self._user_permissions[user_id] = permissions

    def set_delegation_scopes(self, delegation_id: str, scopes: Set[str]) -> None:
        self._delegation_scopes[delegation_id] = scopes

    async def check_permission(
        self,
        tool_id: str,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        delegation_id: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PermissionCheckResult:
        """
        Full permission check before tool execution.

        Check sequence:
        1. Tool exists and is registered
        2. Agent identity is valid
        3. Delegation is valid
        4. Tool's required scopes are within delegation
        5. Resource is within allowed patterns
        6. Agent boundary allows this
        7. User still has permission
        8. Rate limits OK
        9. Risk level check (approval needed?)
        """
        context = context or {}

        # Check 1: Tool exists
        tool_schema = self._registry.get_tool(tool_id)
        if not tool_schema:
            return PermissionCheckResult(
                decision=PermissionDecision.DENY,
                reason=f"Tool '{tool_id}' not registered",
                tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
            )

        # Check 2: Agent boundary
        boundary = self._agent_boundaries.get(agent_id, {})
        allowed_scopes = boundary.get("allowed_scopes", set())
        denied_scopes = boundary.get("denied_scopes", set())

        for required_scope in tool_schema.required_scopes:
            if required_scope in denied_scopes:
                return PermissionCheckResult(
                    decision=PermissionDecision.DENY,
                    reason=f"Scope '{required_scope}' denied by agent boundary",
                    tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
                )
            if allowed_scopes and required_scope not in allowed_scopes:
                return PermissionCheckResult(
                    decision=PermissionDecision.DENY,
                    reason=f"Scope '{required_scope}' not in agent boundary",
                    tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
                )

        # Check 3: Delegation covers tool scopes
        delegation_scopes = self._delegation_scopes.get(delegation_id, set())
        if delegation_scopes:
            missing = set(tool_schema.required_scopes) - delegation_scopes
            if missing:
                return PermissionCheckResult(
                    decision=PermissionDecision.DENY,
                    reason=f"Scopes {missing} not in delegation",
                    tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
                )

        # Check 4: User still has permission
        user_perms = self._user_permissions.get(user_id, set())
        if user_perms:
            missing = set(tool_schema.required_scopes) - user_perms
            if missing:
                return PermissionCheckResult(
                    decision=PermissionDecision.DENY,
                    reason=f"User no longer has scopes {missing}",
                    tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
                )

        # Check 5: Resource within allowed patterns
        if tool_schema.resource_patterns:
            resource_allowed = any(
                fnmatch.fnmatch(resource, pattern)
                for pattern in tool_schema.resource_patterns
            )
            if not resource_allowed:
                return PermissionCheckResult(
                    decision=PermissionDecision.DENY,
                    reason=f"Resource '{resource}' not in tool's allowed patterns",
                    tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
                )

        # Check 6: Rate limits
        rate_ok, rate_reason = self._rate_limiter.check_rate_limit(
            tool_id, agent_id, user_id, tool_schema
        )
        if not rate_ok:
            return PermissionCheckResult(
                decision=PermissionDecision.RATE_LIMITED,
                reason=rate_reason,
                tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
            )

        # Check 7: Risk level / approval
        if tool_schema.always_requires_approval:
            return PermissionCheckResult(
                decision=PermissionDecision.REQUIRE_APPROVAL,
                reason=f"Tool '{tool_id}' always requires approval (risk: {tool_schema.risk_level.name})",
                tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
            )

        if tool_schema.approval_for_resources:
            needs_approval = any(
                fnmatch.fnmatch(resource, pattern)
                for pattern in tool_schema.approval_for_resources
            )
            if needs_approval:
                return PermissionCheckResult(
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    reason=f"Resource '{resource}' requires approval for tool '{tool_id}'",
                    tool_id=tool_id, agent_id=agent_id, user_id=user_id, resource=resource,
                )

        # All checks passed — generate scoped token
        effective_scopes = list(
            set(tool_schema.required_scopes) & (delegation_scopes or set(tool_schema.required_scopes))
        )

        grant = self._token_generator.generate_tool_token(
            tool_id=tool_id,
            tool_schema=tool_schema,
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            granted_scopes=effective_scopes,
            resource=resource,
        )

        # Record rate limit
        self._rate_limiter.record_call_start(tool_id, agent_id, user_id)

        return PermissionCheckResult(
            decision=PermissionDecision.ALLOW,
            reason="All permission checks passed",
            tool_id=tool_id,
            agent_id=agent_id,
            user_id=user_id,
            resource=resource,
            granted_scopes=effective_scopes,
            token=grant.token,
            grant_id=grant.grant_id,
        )


# =============================================================================
# DYNAMIC PERMISSION ADJUSTMENT
# =============================================================================

class DynamicPermissionAdjuster:
    """
    Adjusts permissions dynamically based on agent behavior patterns.
    If an agent shows anomalous behavior, permissions can be tightened.
    """

    def __init__(self, tool_registry: ToolRegistry):
        self._registry = tool_registry
        self._action_history: Dict[str, List[Dict]] = {}  # agent_id -> actions
        self._adjustments: Dict[str, Dict] = {}  # agent_id -> adjustments

    def record_action(
        self, agent_id: str, tool_id: str, action: str, resource: str, success: bool
    ) -> None:
        """Record an action for behavior analysis."""
        if agent_id not in self._action_history:
            self._action_history[agent_id] = []

        self._action_history[agent_id].append({
            "tool_id": tool_id,
            "action": action,
            "resource": resource,
            "success": success,
            "timestamp": time.time(),
        })

        # Keep last 1000 actions
        if len(self._action_history[agent_id]) > 1000:
            self._action_history[agent_id] = self._action_history[agent_id][-1000:]

        # Check for anomalies
        self._check_anomalies(agent_id)

    def _check_anomalies(self, agent_id: str) -> None:
        """Check for anomalous patterns and adjust permissions."""
        history = self._action_history.get(agent_id, [])
        if len(history) < 10:
            return

        recent = history[-50:]

        # Anomaly 1: High failure rate
        failures = sum(1 for a in recent if not a["success"])
        failure_rate = failures / len(recent)
        if failure_rate > 0.5:
            self._adjustments[agent_id] = {
                "rate_multiplier": 0.5,  # Halve rate limits
                "reason": f"High failure rate: {failure_rate:.0%}",
                "applied_at": time.time(),
            }

        # Anomaly 2: Rapid resource scanning (accessing many different resources quickly)
        recent_10 = history[-10:]
        unique_resources = set(a["resource"] for a in recent_10)
        time_span = recent_10[-1]["timestamp"] - recent_10[0]["timestamp"]
        if len(unique_resources) > 8 and time_span < 5:  # 8+ resources in 5 seconds
            self._adjustments[agent_id] = {
                "rate_multiplier": 0.1,
                "require_approval_all": True,
                "reason": "Rapid resource scanning detected",
                "applied_at": time.time(),
            }

        # Anomaly 3: Escalating risk (moving from read to write to delete)
        risk_progression = []
        for a in recent_10:
            tool = self._registry.get_tool(a["tool_id"])
            if tool:
                risk_progression.append(tool.risk_level.value)
        if len(risk_progression) >= 5:
            if risk_progression == sorted(risk_progression) and risk_progression[-1] >= 4:
                self._adjustments[agent_id] = {
                    "block_high_risk": True,
                    "reason": "Escalating risk pattern detected",
                    "applied_at": time.time(),
                }

    def get_adjustment(self, agent_id: str) -> Optional[Dict]:
        """Get current permission adjustment for an agent."""
        adj = self._adjustments.get(agent_id)
        if adj:
            # Auto-expire adjustments after 1 hour
            if time.time() - adj.get("applied_at", 0) > 3600:
                del self._adjustments[agent_id]
                return None
        return adj

    def clear_adjustment(self, agent_id: str) -> None:
        """Manually clear an adjustment (e.g., after review)."""
        self._adjustments.pop(agent_id, None)


# =============================================================================
# PERMISSION HIERARCHY
# =============================================================================

class PermissionHierarchy:
    """
    Defines permission inheritance relationships.
    e.g., "repo:admin" implies "repo:write" implies "repo:read"
    """

    def __init__(self):
        self._hierarchy: Dict[str, Set[str]] = {}

    def define_hierarchy(self, parent: str, children: List[str]) -> None:
        """Define that 'parent' permission implies all 'children' permissions."""
        self._hierarchy[parent] = set(children)
        # Transitive closure
        for child in children:
            if child in self._hierarchy:
                self._hierarchy[parent].update(self._hierarchy[child])

    def expand_permissions(self, permissions: Set[str]) -> Set[str]:
        """Expand a set of permissions to include all implied permissions."""
        expanded = set(permissions)
        for perm in permissions:
            if perm in self._hierarchy:
                expanded.update(self._hierarchy[perm])
        return expanded

    def check_implies(self, held: str, required: str) -> bool:
        """Check if holding 'held' permission implies having 'required'."""
        if held == required:
            return True
        implied = self._hierarchy.get(held, set())
        return required in implied


# =============================================================================
# TOOL EXECUTION GUARD (Integration Point)
# =============================================================================

class ToolExecutionGuard:
    """
    Wraps tool execution with permission checks.
    This is the integration point — all tool calls go through here.
    """

    def __init__(
        self,
        permission_checker: ToolPermissionChecker,
        dynamic_adjuster: DynamicPermissionAdjuster,
    ):
        self._checker = permission_checker
        self._adjuster = dynamic_adjuster
        self._execution_log: List[Dict] = []

    async def execute_tool(
        self,
        tool_id: str,
        agent_id: str,
        user_id: str,
        tenant_id: str,
        delegation_id: str,
        action: str,
        resource: str,
        parameters: Dict[str, Any],
        tool_function: Any,  # The actual tool callable
    ) -> Dict[str, Any]:
        """
        Execute a tool with full permission checks.
        Returns the tool result or an error.
        """
        # Check dynamic adjustments
        adjustment = self._adjuster.get_adjustment(agent_id)
        if adjustment and adjustment.get("block_high_risk"):
            return {
                "success": False,
                "error": "execution_blocked",
                "reason": adjustment["reason"],
            }

        # Run permission check
        check_result = await self._checker.check_permission(
            tool_id=tool_id,
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            delegation_id=delegation_id,
            action=action,
            resource=resource,
        )

        if check_result.decision == PermissionDecision.DENY:
            self._adjuster.record_action(agent_id, tool_id, action, resource, False)
            return {
                "success": False,
                "error": "permission_denied",
                "reason": check_result.reason,
            }

        if check_result.decision == PermissionDecision.REQUIRE_APPROVAL:
            return {
                "success": False,
                "error": "approval_required",
                "reason": check_result.reason,
                "tool_id": tool_id,
                "action": action,
                "resource": resource,
            }

        if check_result.decision == PermissionDecision.RATE_LIMITED:
            return {
                "success": False,
                "error": "rate_limited",
                "reason": check_result.reason,
            }

        # Execute the tool
        try:
            result = await tool_function(
                token=check_result.token,
                parameters=parameters,
            )
            self._adjuster.record_action(agent_id, tool_id, action, resource, True)

            # Record call end for concurrency tracking
            self._checker._rate_limiter.record_call_end(tool_id, agent_id, user_id)

            return {"success": True, "result": result, "grant_id": check_result.grant_id}

        except Exception as e:
            self._adjuster.record_action(agent_id, tool_id, action, resource, False)
            self._checker._rate_limiter.record_call_end(tool_id, agent_id, user_id)
            return {"success": False, "error": "execution_error", "reason": str(e)}


# =============================================================================
# PREDEFINED TOOL SCHEMAS
# =============================================================================

def create_standard_tool_schemas() -> List[ToolPermissionSchema]:
    """Create standard tool permission schemas for common tools."""
    return [
        ToolPermissionSchema(
            tool_id="file-reader",
            tool_name="File Reader",
            tool_version="1.0.0",
            category=ToolCategory.READ,
            risk_level=ToolRiskLevel.SAFE,
            description="Reads file contents from a repository",
            required_scopes=["repo:read"],
            resource_patterns=["org/*/src/**", "org/*/docs/**"],
            max_calls_per_minute=120,
            max_calls_per_hour=5000,
        ),
        ToolPermissionSchema(
            tool_id="file-writer",
            tool_name="File Writer",
            tool_version="1.0.0",
            category=ToolCategory.WRITE,
            risk_level=ToolRiskLevel.MEDIUM,
            description="Writes file contents to a repository branch",
            required_scopes=["repo:write:branch"],
            resource_patterns=["org/*/src/**"],
            max_calls_per_minute=30,
            max_calls_per_hour=500,
            has_side_effects=True,
            is_reversible=True,
            approval_for_resources=["org/*/main/**"],  # Approval for main branch
        ),
        ToolPermissionSchema(
            tool_id="database-query",
            tool_name="Database Query",
            tool_version="1.0.0",
            category=ToolCategory.READ,
            risk_level=ToolRiskLevel.LOW,
            description="Executes read-only SQL queries",
            required_scopes=["database:query:readonly"],
            resource_patterns=["db/*"],
            max_calls_per_minute=30,
            max_calls_per_hour=200,
            accesses_pii=True,
        ),
        ToolPermissionSchema(
            tool_id="database-write",
            tool_name="Database Write",
            tool_version="1.0.0",
            category=ToolCategory.WRITE,
            risk_level=ToolRiskLevel.HIGH,
            description="Executes write SQL operations",
            required_scopes=["database:write"],
            resource_patterns=["db/*"],
            max_calls_per_minute=10,
            max_calls_per_hour=50,
            has_side_effects=True,
            is_reversible=False,
            accesses_pii=True,
            requires_single_use_token=True,
            approval_for_resources=["db/production/*"],
        ),
        ToolPermissionSchema(
            tool_id="deploy-staging",
            tool_name="Deploy to Staging",
            tool_version="1.0.0",
            category=ToolCategory.EXECUTE,
            risk_level=ToolRiskLevel.MEDIUM,
            description="Deploys application to staging environment",
            required_scopes=["deploy:staging"],
            resource_patterns=["deploy/staging/*"],
            max_calls_per_minute=2,
            max_calls_per_hour=10,
            has_side_effects=True,
            max_token_lifetime_seconds=600,
        ),
        ToolPermissionSchema(
            tool_id="deploy-production",
            tool_name="Deploy to Production",
            tool_version="1.0.0",
            category=ToolCategory.EXECUTE,
            risk_level=ToolRiskLevel.CRITICAL,
            description="Deploys application to production environment",
            required_scopes=["deploy:production"],
            resource_patterns=["deploy/production/*"],
            max_calls_per_minute=1,
            max_calls_per_hour=3,
            has_side_effects=True,
            is_reversible=True,  # Can rollback
            always_requires_approval=True,
            max_token_lifetime_seconds=300,
        ),
        ToolPermissionSchema(
            tool_id="secret-reader",
            tool_name="Secret Reader",
            tool_version="1.0.0",
            category=ToolCategory.READ,
            risk_level=ToolRiskLevel.CRITICAL,
            description="Reads secret references (not raw values)",
            required_scopes=["secrets:read:reference"],
            resource_patterns=["vault/*"],
            max_calls_per_minute=5,
            max_calls_per_hour=20,
            accesses_secrets=True,
            always_requires_approval=True,
            requires_single_use_token=True,
            max_token_lifetime_seconds=60,
        ),
    ]


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def example_usage():
    """Demonstrates the tool permission system."""

    # Setup
    registry = ToolRegistry()
    for schema in create_standard_tool_schemas():
        registry.register_tool(schema)

    token_gen = ScopedTokenGenerator(signing_key="tool-token-key")
    rate_limiter = ToolRateLimiter()
    checker = ToolPermissionChecker(registry, token_gen, rate_limiter)
    adjuster = DynamicPermissionAdjuster(registry)
    guard = ToolExecutionGuard(checker, adjuster)

    # Configure permissions
    checker.set_agent_boundary("agent-1", {
        "allowed_scopes": {"repo:read", "repo:write:branch", "database:query:readonly"},
        "denied_scopes": {"admin:*", "deploy:production"},
    })
    checker.set_user_permissions("user-1", {
        "repo:read", "repo:write:branch", "database:query:readonly", "deploy:staging",
    })
    checker.set_delegation_scopes("delegation-1", {
        "repo:read", "repo:write:branch", "database:query:readonly",
    })

    # Permission hierarchy
    hierarchy = PermissionHierarchy()
    hierarchy.define_hierarchy("repo:admin", ["repo:write", "repo:read"])
    hierarchy.define_hierarchy("repo:write", ["repo:write:branch", "repo:read"])
    hierarchy.define_hierarchy("database:admin", ["database:write", "database:query:readonly"])

    # Test 1: Read file (should pass)
    result = await checker.check_permission(
        tool_id="file-reader",
        agent_id="agent-1",
        user_id="user-1",
        tenant_id="tenant-abc",
        delegation_id="delegation-1",
        action="repo:read",
        resource="org/myteam/src/main.py",
    )
    print(f"File read: {result.decision.value} - {result.reason}")

    # Test 2: Production deploy (should require approval)
    result = await checker.check_permission(
        tool_id="deploy-production",
        agent_id="agent-1",
        user_id="user-1",
        tenant_id="tenant-abc",
        delegation_id="delegation-1",
        action="deploy:production",
        resource="deploy/production/api-service",
    )
    print(f"Prod deploy: {result.decision.value} - {result.reason}")

    # Test 3: Database query (should pass)
    result = await checker.check_permission(
        tool_id="database-query",
        agent_id="agent-1",
        user_id="user-1",
        tenant_id="tenant-abc",
        delegation_id="delegation-1",
        action="database:query:readonly",
        resource="db/analytics",
    )
    print(f"DB query: {result.decision.value} - {result.reason}")

    # Test 4: Write to main branch (should require approval)
    result = await checker.check_permission(
        tool_id="file-writer",
        agent_id="agent-1",
        user_id="user-1",
        tenant_id="tenant-abc",
        delegation_id="delegation-1",
        action="repo:write:branch",
        resource="org/myteam/main/src/critical.py",
    )
    print(f"Write main: {result.decision.value} - {result.reason}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
