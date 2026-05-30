"""
Delegated Authorization System
===============================
User-to-agent delegation, on-behalf-of token generation,
just-in-time privilege elevation, and approval workflows.
"""

import uuid
import time
import json
import hashlib
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Any, Callable, Awaitable
from abc import ABC, abstractmethod
import asyncio
import jwt


# =============================================================================
# ENUMS
# =============================================================================

class DelegationStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PrivilegeElevationStatus(Enum):
    REQUESTED = "requested"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    RELEASED = "released"


class RiskLevel(Enum):
    LOW = 1
    MEDIUM = 5
    HIGH = 8
    CRITICAL = 10


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Scope:
    """A single permission scope with optional resource constraint."""
    action: str              # e.g., "repo:read", "database:write"
    resources: List[str]     # Glob patterns: ["org/team-a/**", "db/users/*"]
    constraints: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"read_only": True, "max_rows": 1000, "branches": ["feature/*"]}

    def matches(self, action: str, resource: str) -> bool:
        import fnmatch
        if self.action != action and not action.startswith(self.action + ":"):
            # Check wildcard
            if not fnmatch.fnmatch(action, self.action):
                return False
        return any(fnmatch.fnmatch(resource, r) for r in self.resources)


@dataclass
class DelegationGrant:
    """A grant from a user to an agent specifying delegated permissions."""
    delegation_id: str
    delegator_user_id: str          # User granting permissions
    delegate_agent_id: str          # Agent receiving permissions
    tenant_id: str
    scopes: List[Scope]             # What the agent can do
    constraints: Dict[str, Any] = field(default_factory=dict)
    # Constraints:
    #   max_actions_per_hour: int
    #   allowed_time_window: {"start": "09:00", "end": "17:00", "timezone": "UTC"}
    #   require_approval_for: ["database:delete", "deploy:production"]
    #   allowed_ip_ranges: ["10.0.0.0/8"]
    #   max_token_lifetime_seconds: 300

    status: DelegationStatus = DelegationStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None

    # Usage tracking
    total_actions: int = 0
    last_used_at: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        if self.status != DelegationStatus.ACTIVE:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def covers_action(self, action: str, resource: str) -> bool:
        return any(scope.matches(action, resource) for scope in self.scopes)


@dataclass
class OnBehalfOfToken:
    """Token representing agent acting on behalf of user."""
    token_id: str
    agent_id: str
    user_id: str
    delegation_id: str
    tenant_id: str
    scopes: List[str]           # Effective scopes (intersection result)
    resource: Optional[str]     # Specific resource if scoped
    tool_id: Optional[str]      # Specific tool if scoped
    issued_at: datetime
    expires_at: datetime
    used: bool = False
    max_uses: int = 1

    @property
    def is_valid(self) -> bool:
        if self.used and self.max_uses <= 1:
            return False
        return datetime.now(timezone.utc) < self.expires_at


@dataclass
class ApprovalRequest:
    """Request for user approval of a risky action."""
    approval_id: str
    agent_id: str
    user_id: str
    delegation_id: str
    action: str
    resource: str
    tool_id: str
    risk_level: RiskLevel
    justification: str          # Why the agent needs this
    impact_description: str     # What will happen
    alternatives: List[str]     # Less risky alternatives
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    approval_token: Optional[str] = None  # Issued if approved


@dataclass
class PrivilegeElevation:
    """Just-in-time privilege elevation request and grant."""
    elevation_id: str
    agent_id: str
    user_id: str
    delegation_id: str
    requested_scopes: List[str]
    reason: str
    status: PrivilegeElevationStatus = PrivilegeElevationStatus.REQUESTED
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    credential_id: Optional[str] = None  # Elevated credential if granted


# =============================================================================
# DELEGATION STORE
# =============================================================================

class DelegationStore:
    """Storage for delegation grants."""

    def __init__(self):
        self._grants: Dict[str, DelegationGrant] = {}
        self._approvals: Dict[str, ApprovalRequest] = {}
        self._elevations: Dict[str, PrivilegeElevation] = {}
        self._audit_log: List[Dict[str, Any]] = []

    async def create_grant(self, grant: DelegationGrant) -> DelegationGrant:
        self._grants[grant.delegation_id] = grant
        self._log_event("delegation_created", {
            "delegation_id": grant.delegation_id,
            "user_id": grant.delegator_user_id,
            "agent_id": grant.delegate_agent_id,
            "scopes": [s.action for s in grant.scopes],
        })
        return grant

    async def get_grant(self, delegation_id: str) -> Optional[DelegationGrant]:
        return self._grants.get(delegation_id)

    async def get_grants_for_agent(
        self, agent_id: str, user_id: str
    ) -> List[DelegationGrant]:
        return [
            g for g in self._grants.values()
            if g.delegate_agent_id == agent_id
            and g.delegator_user_id == user_id
            and g.is_valid
        ]

    async def revoke_grant(self, delegation_id: str, reason: str) -> None:
        grant = self._grants.get(delegation_id)
        if grant:
            grant.status = DelegationStatus.REVOKED
            grant.revoked_at = datetime.now(timezone.utc)
            grant.revocation_reason = reason
            self._log_event("delegation_revoked", {
                "delegation_id": delegation_id, "reason": reason,
            })

    async def save_approval(self, approval: ApprovalRequest) -> None:
        self._approvals[approval.approval_id] = approval

    async def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._approvals.get(approval_id)

    async def get_pending_approvals(self, user_id: str) -> List[ApprovalRequest]:
        return [
            a for a in self._approvals.values()
            if a.user_id == user_id and a.status == ApprovalStatus.PENDING
        ]

    async def save_elevation(self, elevation: PrivilegeElevation) -> None:
        self._elevations[elevation.elevation_id] = elevation

    async def get_elevation(self, elevation_id: str) -> Optional[PrivilegeElevation]:
        return self._elevations.get(elevation_id)

    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self._audit_log.append({
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })


# =============================================================================
# DELEGATION POLICY ENGINE
# =============================================================================

@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False
    constraints: Dict[str, Any] = field(default_factory=dict)


class DelegationPolicyEngine:
    """
    Evaluates whether an action is permitted under a delegation grant.
    Implements the intersection rule and constraint checking.
    """

    def __init__(self):
        self._policies: List[Dict[str, Any]] = []
        self._rate_counters: Dict[str, List[float]] = {}  # agent_id -> timestamps

    def add_policy(self, policy: Dict[str, Any]) -> None:
        self._policies.append(policy)

    async def evaluate(
        self,
        agent_id: str,
        user_id: str,
        delegation: DelegationGrant,
        action: str,
        resource: str,
        tool_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluate whether an action is permitted."""
        context = context or {}

        # Check 1: Delegation is valid
        if not delegation.is_valid:
            return PolicyDecision(
                allowed=False, reason="Delegation grant is not active or has expired"
            )

        # Check 2: Delegation covers this action+resource
        if not delegation.covers_action(action, resource):
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action}' on '{resource}' not in delegation scope",
            )

        # Check 3: Rate limiting
        max_actions = delegation.constraints.get("max_actions_per_hour", 1000)
        if not self._check_rate_limit(agent_id, max_actions):
            return PolicyDecision(
                allowed=False,
                reason=f"Rate limit exceeded ({max_actions}/hour)",
            )

        # Check 4: Time window
        time_window = delegation.constraints.get("allowed_time_window")
        if time_window and not self._check_time_window(time_window):
            return PolicyDecision(
                allowed=False,
                reason=f"Action not permitted outside time window {time_window}",
            )

        # Check 5: Action requires approval?
        approval_actions = delegation.constraints.get("require_approval_for", [])
        import fnmatch
        requires_approval = any(
            fnmatch.fnmatch(action, pattern) for pattern in approval_actions
        )

        if requires_approval:
            return PolicyDecision(
                allowed=True,
                reason="Action permitted but requires user approval",
                requires_approval=True,
            )

        # Check 6: Custom policies
        for policy in self._policies:
            decision = self._evaluate_custom_policy(
                policy, agent_id, user_id, action, resource, tool_id, context
            )
            if decision and not decision.allowed:
                return decision

        # Record action for rate limiting
        self._record_action(agent_id)

        return PolicyDecision(allowed=True, reason="Action permitted by delegation")

    def _check_rate_limit(self, agent_id: str, max_per_hour: int) -> bool:
        now = time.time()
        hour_ago = now - 3600
        timestamps = self._rate_counters.get(agent_id, [])
        recent = [t for t in timestamps if t > hour_ago]
        self._rate_counters[agent_id] = recent
        return len(recent) < max_per_hour

    def _record_action(self, agent_id: str) -> None:
        if agent_id not in self._rate_counters:
            self._rate_counters[agent_id] = []
        self._rate_counters[agent_id].append(time.time())

    def _check_time_window(self, window: Dict[str, str]) -> bool:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(window.get("timezone", "UTC"))
        now = datetime.now(tz)
        start_h, start_m = map(int, window["start"].split(":"))
        end_h, end_m = map(int, window["end"].split(":"))
        start = now.replace(hour=start_h, minute=start_m, second=0)
        end = now.replace(hour=end_h, minute=end_m, second=0)
        return start <= now <= end

    def _evaluate_custom_policy(
        self, policy, agent_id, user_id, action, resource, tool_id, context
    ) -> Optional[PolicyDecision]:
        """Evaluate a custom policy rule."""
        import fnmatch

        # Match conditions
        if "actions" in policy:
            if not any(fnmatch.fnmatch(action, p) for p in policy["actions"]):
                return None  # Policy doesn't apply

        if "resources" in policy:
            if not any(fnmatch.fnmatch(resource, p) for p in policy["resources"]):
                return None

        # Apply effect
        if policy.get("effect") == "deny":
            return PolicyDecision(
                allowed=False, reason=policy.get("reason", "Denied by policy")
            )

        return None


# =============================================================================
# ON-BEHALF-OF TOKEN SERVICE
# =============================================================================

class OnBehalfOfTokenService:
    """Issues scoped tokens for agent actions on behalf of users."""

    def __init__(self, signing_key: str, issuer: str = "obo-token-service"):
        self._signing_key = signing_key
        self._issuer = issuer
        self._issued_tokens: Dict[str, OnBehalfOfToken] = {}

    async def issue_token(
        self,
        agent_id: str,
        user_id: str,
        delegation: DelegationGrant,
        requested_scopes: List[str],
        tool_id: Optional[str] = None,
        resource: Optional[str] = None,
        lifetime_seconds: int = 300,
        max_uses: int = 1,
    ) -> str:
        """
        Issue an on-behalf-of token.
        The token's effective scopes are the intersection of:
        - requested_scopes
        - delegation scopes
        - (caller should also intersect with agent boundary and user permissions)
        """
        # Compute effective scopes (intersection with delegation)
        delegation_actions = {s.action for s in delegation.scopes}
        effective_scopes = [s for s in requested_scopes if s in delegation_actions]

        if not effective_scopes:
            raise PermissionError(
                "No requested scopes are covered by the delegation grant"
            )

        # Enforce max lifetime from delegation constraints
        max_lifetime = delegation.constraints.get("max_token_lifetime_seconds", 900)
        lifetime_seconds = min(lifetime_seconds, max_lifetime)

        now = datetime.now(timezone.utc)
        token_record = OnBehalfOfToken(
            token_id=str(uuid.uuid4()),
            agent_id=agent_id,
            user_id=user_id,
            delegation_id=delegation.delegation_id,
            tenant_id=delegation.tenant_id,
            scopes=effective_scopes,
            resource=resource,
            tool_id=tool_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=lifetime_seconds),
            max_uses=max_uses,
        )

        self._issued_tokens[token_record.token_id] = token_record

        # Encode as JWT
        payload = {
            "iss": self._issuer,
            "sub": user_id,
            "act": {"sub": agent_id},  # Actor claim (RFC 8693)
            "iat": int(now.timestamp()),
            "exp": int(token_record.expires_at.timestamp()),
            "jti": token_record.token_id,
            "tenant_id": delegation.tenant_id,
            "delegation_id": delegation.delegation_id,
            "scopes": effective_scopes,
            "tool_id": tool_id,
            "resource": resource,
            "max_uses": max_uses,
            "token_type": "on_behalf_of",
        }
        return jwt.encode(payload, self._signing_key, algorithm="HS256")

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate an OBO token and return claims."""
        try:
            payload = jwt.decode(
                token, self._signing_key, algorithms=["HS256"], issuer=self._issuer
            )
            token_id = payload.get("jti")
            record = self._issued_tokens.get(token_id)
            if not record or not record.is_valid:
                return None

            # Mark as used
            record.used = True
            return payload
        except jwt.InvalidTokenError:
            return None

    async def revoke_token(self, token_id: str) -> None:
        """Revoke a specific token."""
        record = self._issued_tokens.get(token_id)
        if record:
            record.used = True  # Prevent further use
            record.expires_at = datetime.now(timezone.utc)


# =============================================================================
# APPROVAL WORKFLOW SERVICE
# =============================================================================

class ApprovalWorkflowService:
    """Manages approval requests for risky actions."""

    def __init__(
        self,
        store: DelegationStore,
        notification_callback: Optional[Callable[[ApprovalRequest], Awaitable[None]]] = None,
    ):
        self._store = store
        self._notify = notification_callback
        self._approval_timeout_seconds = 300  # 5 minutes

    async def request_approval(
        self,
        agent_id: str,
        user_id: str,
        delegation_id: str,
        action: str,
        resource: str,
        tool_id: str,
        risk_level: RiskLevel,
        justification: str,
        impact_description: str,
        alternatives: Optional[List[str]] = None,
    ) -> ApprovalRequest:
        """Create an approval request and notify the user."""
        now = datetime.now(timezone.utc)
        request = ApprovalRequest(
            approval_id=str(uuid.uuid4()),
            agent_id=agent_id,
            user_id=user_id,
            delegation_id=delegation_id,
            action=action,
            resource=resource,
            tool_id=tool_id,
            risk_level=risk_level,
            justification=justification,
            impact_description=impact_description,
            alternatives=alternatives or [],
            expires_at=now + timedelta(seconds=self._approval_timeout_seconds),
        )

        await self._store.save_approval(request)

        # Notify user
        if self._notify:
            await self._notify(request)

        return request

    async def approve(
        self, approval_id: str, approver_user_id: str, mfa_verified: bool = False
    ) -> Optional[str]:
        """Approve a request. Returns approval token if successful."""
        request = await self._store.get_approval(approval_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            return None

        if datetime.now(timezone.utc) > request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            await self._store.save_approval(request)
            return None

        # For CRITICAL risk, require MFA
        if request.risk_level == RiskLevel.CRITICAL and not mfa_verified:
            raise PermissionError("CRITICAL actions require MFA verification")

        # Only the delegating user (or designated approvers) can approve
        if approver_user_id != request.user_id:
            raise PermissionError("Only the delegating user can approve")

        request.status = ApprovalStatus.APPROVED
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = approver_user_id

        # Generate time-limited approval token
        approval_token = self._generate_approval_token(request)
        request.approval_token = approval_token

        await self._store.save_approval(request)
        return approval_token

    async def deny(self, approval_id: str, denier_user_id: str, reason: str = "") -> None:
        """Deny an approval request."""
        request = await self._store.get_approval(approval_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return

        request.status = ApprovalStatus.DENIED
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = denier_user_id
        await self._store.save_approval(request)

    def _generate_approval_token(self, request: ApprovalRequest) -> str:
        """Generate a short-lived token that proves approval was granted."""
        payload = {
            "type": "approval_token",
            "approval_id": request.approval_id,
            "agent_id": request.agent_id,
            "user_id": request.user_id,
            "action": request.action,
            "resource": request.resource,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
        # In production, sign with HSM
        return base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode()


# =============================================================================
# JUST-IN-TIME PRIVILEGE ELEVATION
# =============================================================================

class JITPrivilegeService:
    """Manages just-in-time privilege elevation for agents."""

    def __init__(self, store: DelegationStore, policy_engine: DelegationPolicyEngine):
        self._store = store
        self._policy_engine = policy_engine
        self._active_elevations: Dict[str, PrivilegeElevation] = {}

    async def request_elevation(
        self,
        agent_id: str,
        user_id: str,
        delegation_id: str,
        requested_scopes: List[str],
        reason: str,
        duration_seconds: int = 600,
    ) -> PrivilegeElevation:
        """
        Request just-in-time privilege elevation.
        The agent requests temporary access beyond its base level.
        """
        # Validate the delegation exists
        delegation = await self._store.get_grant(delegation_id)
        if not delegation or not delegation.is_valid:
            raise ValueError("Invalid delegation")

        # Check if the delegation even allows these scopes
        delegation_actions = {s.action for s in delegation.scopes}
        invalid_scopes = [s for s in requested_scopes if s not in delegation_actions]
        if invalid_scopes:
            raise PermissionError(
                f"Scopes {invalid_scopes} not covered by delegation"
            )

        elevation = PrivilegeElevation(
            elevation_id=str(uuid.uuid4()),
            agent_id=agent_id,
            user_id=user_id,
            delegation_id=delegation_id,
            requested_scopes=requested_scopes,
            reason=reason,
        )

        # Auto-grant if policy allows (LOW risk JIT)
        # For HIGH risk, this should go through approval workflow
        risk = self._assess_scope_risk(requested_scopes)
        if risk.value <= RiskLevel.MEDIUM.value:
            elevation.status = PrivilegeElevationStatus.GRANTED
            elevation.granted_at = datetime.now(timezone.utc)
            elevation.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=min(duration_seconds, 600)  # Cap at 10 min for auto-grant
            )
            self._active_elevations[elevation.elevation_id] = elevation
        else:
            elevation.status = PrivilegeElevationStatus.REQUESTED
            # Requires manual approval

        await self._store.save_elevation(elevation)
        return elevation

    async def release_elevation(self, elevation_id: str) -> None:
        """Agent explicitly releases elevated privileges."""
        elevation = self._active_elevations.get(elevation_id)
        if elevation:
            elevation.status = PrivilegeElevationStatus.RELEASED
            elevation.released_at = datetime.now(timezone.utc)
            del self._active_elevations[elevation_id]
            await self._store.save_elevation(elevation)

    async def check_elevation_valid(self, elevation_id: str) -> bool:
        """Check if an elevation is still valid."""
        elevation = self._active_elevations.get(elevation_id)
        if not elevation:
            return False
        if elevation.status != PrivilegeElevationStatus.GRANTED:
            return False
        if elevation.expires_at and datetime.now(timezone.utc) > elevation.expires_at:
            elevation.status = PrivilegeElevationStatus.EXPIRED
            del self._active_elevations[elevation_id]
            return False
        return True

    async def cleanup_expired(self) -> int:
        """Clean up expired elevations. Returns count cleaned."""
        now = datetime.now(timezone.utc)
        expired = [
            eid for eid, e in self._active_elevations.items()
            if e.expires_at and now > e.expires_at
        ]
        for eid in expired:
            self._active_elevations[eid].status = PrivilegeElevationStatus.EXPIRED
            del self._active_elevations[eid]
        return len(expired)

    def _assess_scope_risk(self, scopes: List[str]) -> RiskLevel:
        """Assess the risk level of requested scopes."""
        high_risk_patterns = ["delete", "deploy:prod", "admin", "security", "secret"]
        medium_risk_patterns = ["write", "deploy:staging", "modify"]

        for scope in scopes:
            scope_lower = scope.lower()
            if any(p in scope_lower for p in high_risk_patterns):
                return RiskLevel.HIGH
        for scope in scopes:
            scope_lower = scope.lower()
            if any(p in scope_lower for p in medium_risk_patterns):
                return RiskLevel.MEDIUM
        return RiskLevel.LOW


# =============================================================================
# DELEGATED AUTHORIZATION SERVICE (Main Facade)
# =============================================================================

class DelegatedAuthorizationService:
    """
    Main service that orchestrates delegation, policy evaluation,
    token issuance, and approval workflows.
    """

    def __init__(self, signing_key: str):
        self._store = DelegationStore()
        self._policy_engine = DelegationPolicyEngine()
        self._token_service = OnBehalfOfTokenService(signing_key)
        self._approval_service = ApprovalWorkflowService(self._store)
        self._jit_service = JITPrivilegeService(self._store, self._policy_engine)

    # -------------------------------------------------------------------------
    # Delegation Management
    # -------------------------------------------------------------------------

    async def create_delegation(
        self,
        user_id: str,
        agent_id: str,
        tenant_id: str,
        scopes: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]] = None,
        lifetime_hours: int = 24,
    ) -> DelegationGrant:
        """User creates a delegation grant for an agent."""
        scope_objects = [
            Scope(
                action=s["action"],
                resources=s.get("resources", ["*"]),
                constraints=s.get("constraints", {}),
            )
            for s in scopes
        ]

        grant = DelegationGrant(
            delegation_id=str(uuid.uuid4()),
            delegator_user_id=user_id,
            delegate_agent_id=agent_id,
            tenant_id=tenant_id,
            scopes=scope_objects,
            constraints=constraints or {},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=lifetime_hours),
        )

        return await self._store.create_grant(grant)

    async def revoke_delegation(self, delegation_id: str, reason: str) -> None:
        """User revokes a delegation."""
        await self._store.revoke_grant(delegation_id, reason)

    # -------------------------------------------------------------------------
    # Action Authorization
    # -------------------------------------------------------------------------

    async def authorize_action(
        self,
        agent_id: str,
        user_id: str,
        delegation_id: str,
        action: str,
        resource: str,
        tool_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Authorize an agent action. Returns authorization result with token if allowed.
        This is the main entry point for the permission check flow.
        """
        # Get delegation
        delegation = await self._store.get_grant(delegation_id)
        if not delegation:
            return {"allowed": False, "reason": "Delegation not found"}

        # Evaluate policy
        decision = await self._policy_engine.evaluate(
            agent_id=agent_id,
            user_id=user_id,
            delegation=delegation,
            action=action,
            resource=resource,
            tool_id=tool_id,
            context=context,
        )

        if not decision.allowed:
            return {"allowed": False, "reason": decision.reason}

        if decision.requires_approval:
            # Trigger approval workflow
            approval = await self._approval_service.request_approval(
                agent_id=agent_id,
                user_id=user_id,
                delegation_id=delegation_id,
                action=action,
                resource=resource,
                tool_id=tool_id,
                risk_level=RiskLevel.HIGH,
                justification=f"Agent needs to perform {action} on {resource}",
                impact_description=f"Will execute {action} on {resource}",
            )
            return {
                "allowed": False,
                "reason": "Approval required",
                "requires_approval": True,
                "approval_id": approval.approval_id,
            }

        # Issue scoped token
        token = await self._token_service.issue_token(
            agent_id=agent_id,
            user_id=user_id,
            delegation=delegation,
            requested_scopes=[action],
            tool_id=tool_id,
            resource=resource,
        )

        # Update delegation usage
        delegation.total_actions += 1
        delegation.last_used_at = datetime.now(timezone.utc)

        return {
            "allowed": True,
            "token": token,
            "reason": decision.reason,
            "constraints": decision.constraints,
        }

    # -------------------------------------------------------------------------
    # Approval
    # -------------------------------------------------------------------------

    async def approve_action(
        self, approval_id: str, user_id: str, mfa_verified: bool = False
    ) -> Optional[str]:
        return await self._approval_service.approve(approval_id, user_id, mfa_verified)

    async def deny_action(self, approval_id: str, user_id: str, reason: str = "") -> None:
        await self._approval_service.deny(approval_id, user_id, reason)

    # -------------------------------------------------------------------------
    # JIT Privilege
    # -------------------------------------------------------------------------

    async def request_jit_elevation(
        self,
        agent_id: str,
        user_id: str,
        delegation_id: str,
        scopes: List[str],
        reason: str,
    ) -> PrivilegeElevation:
        return await self._jit_service.request_elevation(
            agent_id, user_id, delegation_id, scopes, reason
        )

    async def release_jit_elevation(self, elevation_id: str) -> None:
        await self._jit_service.release_elevation(elevation_id)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def example_usage():
    """Demonstrates the delegated authorization system."""

    service = DelegatedAuthorizationService(signing_key="obo-signing-key")

    # 1. User creates delegation for agent
    delegation = await service.create_delegation(
        user_id="user-456",
        agent_id="agent-code-review",
        tenant_id="tenant-abc",
        scopes=[
            {"action": "repo:read", "resources": ["org/myteam/**"]},
            {"action": "issue:create", "resources": ["org/myteam/**"]},
            {"action": "repo:write:branch", "resources": ["org/myteam/*/feature/**"]},
        ],
        constraints={
            "max_actions_per_hour": 100,
            "require_approval_for": ["repo:delete*", "deploy:*"],
            "max_token_lifetime_seconds": 300,
        },
        lifetime_hours=8,  # Working day
    )
    print(f"Delegation created: {delegation.delegation_id}")

    # 2. Agent requests authorization for a read action (should succeed)
    result = await service.authorize_action(
        agent_id="agent-code-review",
        user_id="user-456",
        delegation_id=delegation.delegation_id,
        action="repo:read",
        resource="org/myteam/api-service/src/main.py",
        tool_id="file-reader",
    )
    print(f"Read action: allowed={result['allowed']}")

    # 3. Agent requests authorization for issue creation
    result = await service.authorize_action(
        agent_id="agent-code-review",
        user_id="user-456",
        delegation_id=delegation.delegation_id,
        action="issue:create",
        resource="org/myteam/api-service",
        tool_id="issue-creator",
    )
    print(f"Issue create: allowed={result['allowed']}, token={result.get('token', '')[:30]}...")

    # 4. Agent requests JIT elevation for write access
    elevation = await service.request_jit_elevation(
        agent_id="agent-code-review",
        user_id="user-456",
        delegation_id=delegation.delegation_id,
        scopes=["repo:write:branch"],
        reason="Need to push fix to feature branch",
    )
    print(f"JIT elevation: status={elevation.status.value}")

    # 5. Revoke delegation
    await service.revoke_delegation(delegation.delegation_id, "Session ended")
    print("Delegation revoked")

    # 6. Try action after revocation (should fail)
    result = await service.authorize_action(
        agent_id="agent-code-review",
        user_id="user-456",
        delegation_id=delegation.delegation_id,
        action="repo:read",
        resource="org/myteam/api-service/src/main.py",
        tool_id="file-reader",
    )
    print(f"After revocation: allowed={result['allowed']}, reason={result['reason']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
