"""
Tool and Agent Registry Implementation
=======================================
Central registry for managing tools and agents:
1. Tool registration with risk tiering
2. Tool approval workflow
3. Tool permission management (per-user, per-role)
4. Tool version management
5. Tool usage analytics
6. Agent registration and capability discovery
7. Registry API endpoints (FastAPI)
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Header  # type: ignore[import-untyped]
from pydantic import BaseModel, Field  # type: ignore[import-untyped]


# ============================================================================
# Core Types
# ============================================================================


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class ToolStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


@dataclass
class ToolVersion:
    version: str
    checksum: str
    released_at: str
    changelog: str
    status: ToolStatus = ToolStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


@dataclass
class ToolPermission:
    tool_id: str
    allowed_roles: list[str] = field(default_factory=list)
    allowed_users: list[str] = field(default_factory=list)
    denied_users: list[str] = field(default_factory=list)
    rate_limit_per_user_per_hour: int = 100
    rate_limit_global_per_hour: int = 10000
    requires_approval_per_invocation: bool = False


@dataclass
class ToolRegistration:
    id: str
    name: str
    description: str
    server_name: str
    risk_tier: RiskTier
    input_schema: dict[str, Any]
    owner_team: str
    publisher: str
    versions: list[ToolVersion] = field(default_factory=list)
    current_version: Optional[str] = None
    permissions: ToolPermission = field(default_factory=lambda: ToolPermission(tool_id=""))
    status: ToolStatus = ToolStatus.DRAFT
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deprecation_notice: Optional[str] = None


@dataclass
class AgentRegistration:
    id: str
    name: str
    description: str
    agent_card_url: str
    risk_tier: RiskTier
    owner_team: str
    skills: list[dict[str, str]]  # [{id, name, description}]
    status: ToolStatus = ToolStatus.DRAFT
    sla_p99_seconds: float = 30.0
    delegation_policies: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    health_check_url: Optional[str] = None
    last_health_check: Optional[str] = None
    is_healthy: bool = True


@dataclass
class ApprovalRequest:
    id: str
    item_type: str  # "tool" or "agent"
    item_id: str
    item_name: str
    risk_tier: RiskTier
    requested_by: str
    requested_at: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None


@dataclass
class UsageRecord:
    tool_id: str
    user_id: str
    timestamp: str
    latency_ms: float
    success: bool
    error: Optional[str] = None


# ============================================================================
# Registry Storage (In-memory — swap for database in production)
# ============================================================================


class RegistryStore:
    """In-memory storage for the registry. Replace with a database in production."""

    def __init__(self):
        self.tools: dict[str, ToolRegistration] = {}
        self.agents: dict[str, AgentRegistration] = {}
        self.approvals: dict[str, ApprovalRequest] = {}
        self.usage_records: list[UsageRecord] = []
        self._rate_limit_counters: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, tool_id: str, user_id: str, limit_per_hour: int) -> bool:
        """Check if a user has exceeded their rate limit for a tool."""
        key = f"{tool_id}:{user_id}"
        now = time.time()
        hour_ago = now - 3600

        # Clean old entries
        self._rate_limit_counters[key] = [
            t for t in self._rate_limit_counters[key] if t > hour_ago
        ]

        if len(self._rate_limit_counters[key]) >= limit_per_hour:
            return False  # Rate limited

        self._rate_limit_counters[key].append(now)
        return True


# ============================================================================
# Registry Service
# ============================================================================


class ToolRegistry:
    """
    Central registry service for tools and agents.
    Handles registration, approval, permissions, versioning, and analytics.
    """

    # Required approver roles by risk tier
    APPROVER_ROLES: dict[RiskTier, list[str]] = {
        RiskTier.LOW: ["team_lead", "platform_engineer"],
        RiskTier.MEDIUM: ["team_lead", "security_engineer"],
        RiskTier.HIGH: ["security_engineer", "engineering_manager"],
        RiskTier.CRITICAL: ["ciso", "vp_engineering"],
    }

    def __init__(self):
        self.store = RegistryStore()

    # ---- Tool Registration ----

    def register_tool(
        self,
        name: str,
        description: str,
        server_name: str,
        input_schema: dict[str, Any],
        risk_tier: RiskTier,
        owner_team: str,
        publisher: str,
        version: str = "1.0.0",
        tags: list[str] | None = None,
    ) -> ToolRegistration:
        """Register a new tool in the registry."""
        tool_id = f"tool-{uuid.uuid4().hex[:8]}"

        # Auto-classify risk if not provided
        if risk_tier == RiskTier.LOW:
            risk_tier = self._auto_classify_risk(name, description, input_schema)

        tool = ToolRegistration(
            id=tool_id,
            name=name,
            description=description,
            server_name=server_name,
            risk_tier=risk_tier,
            input_schema=input_schema,
            owner_team=owner_team,
            publisher=publisher,
            versions=[ToolVersion(
                version=version,
                checksum=hashlib.sha256(json.dumps(input_schema).encode()).hexdigest(),
                released_at=datetime.now(timezone.utc).isoformat(),
                changelog="Initial release",
            )],
            current_version=version,
            permissions=ToolPermission(tool_id=tool_id),
            status=ToolStatus.PENDING_REVIEW,
            tags=tags or [],
        )

        self.store.tools[tool_id] = tool

        # Auto-approve low-risk tools
        if risk_tier == RiskTier.LOW:
            tool.status = ToolStatus.APPROVED
            tool.versions[0].status = ToolStatus.APPROVED
        else:
            # Create approval request
            self._create_approval("tool", tool_id, name, risk_tier, publisher)

        return tool

    def get_tool(self, tool_id: str) -> Optional[ToolRegistration]:
        return self.store.tools.get(tool_id)

    def list_tools(
        self,
        status: Optional[ToolStatus] = None,
        risk_tier: Optional[RiskTier] = None,
        tags: Optional[list[str]] = None,
    ) -> list[ToolRegistration]:
        """List tools with optional filters."""
        tools = list(self.store.tools.values())
        if status:
            tools = [t for t in tools if t.status == status]
        if risk_tier:
            tools = [t for t in tools if t.risk_tier == risk_tier]
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]
        return tools

    def search_tools(self, query: str) -> list[ToolRegistration]:
        """Search tools by name or description."""
        query_lower = query.lower()
        results = []
        for tool in self.store.tools.values():
            if tool.status != ToolStatus.APPROVED:
                continue
            if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                results.append(tool)
        return results

    # ---- Tool Versioning ----

    def publish_version(
        self,
        tool_id: str,
        version: str,
        changelog: str,
        input_schema: dict[str, Any],
    ) -> ToolVersion:
        """Publish a new version of an existing tool."""
        tool = self.store.tools.get(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")

        new_version = ToolVersion(
            version=version,
            checksum=hashlib.sha256(json.dumps(input_schema).encode()).hexdigest(),
            released_at=datetime.now(timezone.utc).isoformat(),
            changelog=changelog,
            status=ToolStatus.PENDING_REVIEW,
        )
        tool.versions.append(new_version)
        tool.updated_at = datetime.now(timezone.utc).isoformat()

        # Require re-approval for non-low-risk tools
        if tool.risk_tier != RiskTier.LOW:
            self._create_approval("tool", tool_id, f"{tool.name} v{version}", tool.risk_tier, tool.publisher)
        else:
            new_version.status = ToolStatus.APPROVED
            tool.current_version = version

        return new_version

    def deprecate_tool(self, tool_id: str, notice: str, sunset_date: str) -> None:
        """Mark a tool as deprecated with a sunset date."""
        tool = self.store.tools.get(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")
        tool.status = ToolStatus.DEPRECATED
        tool.deprecation_notice = f"{notice} (sunset: {sunset_date})"
        tool.updated_at = datetime.now(timezone.utc).isoformat()

    # ---- Permissions ----

    def set_permissions(
        self,
        tool_id: str,
        allowed_roles: list[str] | None = None,
        allowed_users: list[str] | None = None,
        denied_users: list[str] | None = None,
        rate_limit_per_user: int | None = None,
    ) -> ToolPermission:
        """Set permissions for a tool."""
        tool = self.store.tools.get(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")

        perm = tool.permissions
        if allowed_roles is not None:
            perm.allowed_roles = allowed_roles
        if allowed_users is not None:
            perm.allowed_users = allowed_users
        if denied_users is not None:
            perm.denied_users = denied_users
        if rate_limit_per_user is not None:
            perm.rate_limit_per_user_per_hour = rate_limit_per_user

        return perm

    def check_access(self, tool_id: str, user_id: str, user_roles: list[str]) -> tuple[bool, str]:
        """Check if a user can access a tool. Returns (allowed, reason)."""
        tool = self.store.tools.get(tool_id)
        if not tool:
            return False, "Tool not found"

        if tool.status != ToolStatus.APPROVED:
            return False, f"Tool status is {tool.status.value}"

        perm = tool.permissions

        # Explicit deny
        if user_id in perm.denied_users:
            return False, "User explicitly denied"

        # Explicit user allow
        if perm.allowed_users and user_id in perm.allowed_users:
            # Check rate limit
            if not self.store.check_rate_limit(tool_id, user_id, perm.rate_limit_per_user_per_hour):
                return False, "Rate limit exceeded"
            return True, "User explicitly allowed"

        # Role-based allow
        if perm.allowed_roles:
            if any(role in perm.allowed_roles for role in user_roles):
                if not self.store.check_rate_limit(tool_id, user_id, perm.rate_limit_per_user_per_hour):
                    return False, "Rate limit exceeded"
                return True, "Role allowed"
            return False, "No matching role"

        # Default: allow if no restrictions
        if not self.store.check_rate_limit(tool_id, user_id, perm.rate_limit_per_user_per_hour):
            return False, "Rate limit exceeded"
        return True, "No restrictions"

    # ---- Approval Workflow ----

    def _create_approval(
        self,
        item_type: str,
        item_id: str,
        item_name: str,
        risk_tier: RiskTier,
        requested_by: str,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            id=f"approval-{uuid.uuid4().hex[:8]}",
            item_type=item_type,
            item_id=item_id,
            item_name=item_name,
            risk_tier=risk_tier,
            requested_by=requested_by,
            requested_at=datetime.now(timezone.utc).isoformat(),
        )
        self.store.approvals[approval.id] = approval
        return approval

    def approve_item(
        self, approval_id: str, reviewer: str, reviewer_role: str, notes: str = ""
    ) -> ApprovalRequest:
        """Approve a pending registration/version."""
        approval = self.store.approvals.get(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval already {approval.status.value}")

        # Verify reviewer has authority
        required_roles = self.APPROVER_ROLES.get(approval.risk_tier, [])
        if reviewer_role not in required_roles:
            raise PermissionError(
                f"Role '{reviewer_role}' cannot approve {approval.risk_tier.value}-risk items. "
                f"Required: {required_roles}"
            )

        approval.status = ApprovalStatus.APPROVED
        approval.reviewer = reviewer
        approval.reviewed_at = datetime.now(timezone.utc).isoformat()
        approval.review_notes = notes

        # Update the item
        if approval.item_type == "tool":
            tool = self.store.tools.get(approval.item_id)
            if tool:
                tool.status = ToolStatus.APPROVED
                # Approve latest pending version
                for v in reversed(tool.versions):
                    if v.status == ToolStatus.PENDING_REVIEW:
                        v.status = ToolStatus.APPROVED
                        v.approved_by = reviewer
                        v.approved_at = approval.reviewed_at
                        tool.current_version = v.version
                        break
        elif approval.item_type == "agent":
            agent = self.store.agents.get(approval.item_id)
            if agent:
                agent.status = ToolStatus.APPROVED

        return approval

    def reject_item(self, approval_id: str, reviewer: str, reason: str) -> ApprovalRequest:
        """Reject a pending registration."""
        approval = self.store.approvals.get(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        approval.status = ApprovalStatus.REJECTED
        approval.reviewer = reviewer
        approval.reviewed_at = datetime.now(timezone.utc).isoformat()
        approval.review_notes = reason
        return approval

    def list_pending_approvals(self, risk_tier: Optional[RiskTier] = None) -> list[ApprovalRequest]:
        pending = [a for a in self.store.approvals.values() if a.status == ApprovalStatus.PENDING]
        if risk_tier:
            pending = [a for a in pending if a.risk_tier == risk_tier]
        return pending

    # ---- Agent Registration ----

    def register_agent(
        self,
        name: str,
        description: str,
        agent_card_url: str,
        risk_tier: RiskTier,
        owner_team: str,
        skills: list[dict[str, str]],
        sla_p99_seconds: float = 30.0,
    ) -> AgentRegistration:
        """Register a new agent in the registry."""
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        agent = AgentRegistration(
            id=agent_id,
            name=name,
            description=description,
            agent_card_url=agent_card_url,
            risk_tier=risk_tier,
            owner_team=owner_team,
            skills=skills,
            sla_p99_seconds=sla_p99_seconds,
            health_check_url=f"{agent_card_url.rstrip('/')}/health",
        )
        self.store.agents[agent_id] = agent

        if risk_tier == RiskTier.LOW:
            agent.status = ToolStatus.APPROVED
        else:
            self._create_approval("agent", agent_id, name, risk_tier, owner_team)

        return agent

    def discover_agents(self, capability: str) -> list[AgentRegistration]:
        """Find agents that match a capability description."""
        capability_lower = capability.lower()
        results = []
        for agent in self.store.agents.values():
            if agent.status != ToolStatus.APPROVED:
                continue
            if capability_lower in agent.description.lower():
                results.append(agent)
                continue
            for skill in agent.skills:
                if capability_lower in skill.get("description", "").lower():
                    results.append(agent)
                    break
        return results

    # ---- Usage Analytics ----

    def record_usage(
        self, tool_id: str, user_id: str, latency_ms: float, success: bool, error: Optional[str] = None
    ) -> None:
        """Record a tool usage event for analytics."""
        self.store.usage_records.append(UsageRecord(
            tool_id=tool_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            latency_ms=latency_ms,
            success=success,
            error=error,
        ))

    def get_usage_stats(self, tool_id: str, hours: int = 24) -> dict[str, Any]:
        """Get usage statistics for a tool over a time period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        records = [
            r for r in self.store.usage_records
            if r.tool_id == tool_id and r.timestamp >= cutoff_str
        ]

        if not records:
            return {"tool_id": tool_id, "period_hours": hours, "total_calls": 0}

        latencies = [r.latency_ms for r in records]
        successes = sum(1 for r in records if r.success)
        unique_users = len(set(r.user_id for r in records))

        return {
            "tool_id": tool_id,
            "period_hours": hours,
            "total_calls": len(records),
            "success_rate": successes / len(records),
            "unique_users": unique_users,
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": sorted(latencies)[len(latencies) // 2],
            "p99_latency_ms": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0],
            "error_count": len(records) - successes,
            "top_errors": self._top_errors(records),
        }

    def _top_errors(self, records: list[UsageRecord], top_n: int = 5) -> list[dict[str, Any]]:
        error_counts: dict[str, int] = defaultdict(int)
        for r in records:
            if r.error:
                error_counts[r.error] += 1
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"error": e, "count": c} for e, c in sorted_errors[:top_n]]

    # ---- Risk Classification ----

    def _auto_classify_risk(
        self, name: str, description: str, schema: dict[str, Any]
    ) -> RiskTier:
        """Auto-classify risk based on tool metadata."""
        text = f"{name} {description}".lower()

        critical_keywords = {"delete", "drop", "payment", "transfer", "admin", "credentials"}
        high_keywords = {"write", "create", "update", "pii", "personal", "financial", "external"}
        medium_keywords = {"email", "notify", "ticket", "comment"}

        if any(kw in text for kw in critical_keywords):
            return RiskTier.CRITICAL
        if any(kw in text for kw in high_keywords):
            return RiskTier.HIGH
        if any(kw in text for kw in medium_keywords):
            return RiskTier.MEDIUM
        return RiskTier.LOW


# ============================================================================
# FastAPI Application
# ============================================================================


app = FastAPI(title="Tool & Agent Registry", version="1.0.0")
registry = ToolRegistry()


# ---- Pydantic Models for API ----

class RegisterToolRequest(BaseModel):
    name: str
    description: str
    server_name: str
    input_schema: dict[str, Any]
    risk_tier: RiskTier = RiskTier.LOW
    owner_team: str
    publisher: str
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)


class RegisterAgentRequest(BaseModel):
    name: str
    description: str
    agent_card_url: str
    risk_tier: RiskTier
    owner_team: str
    skills: list[dict[str, str]]
    sla_p99_seconds: float = 30.0


class ApproveRequest(BaseModel):
    reviewer: str
    reviewer_role: str
    notes: str = ""


class RejectRequest(BaseModel):
    reviewer: str
    reason: str


class SetPermissionsRequest(BaseModel):
    allowed_roles: Optional[list[str]] = None
    allowed_users: Optional[list[str]] = None
    denied_users: Optional[list[str]] = None
    rate_limit_per_user: Optional[int] = None


class CheckAccessRequest(BaseModel):
    user_id: str
    user_roles: list[str]


# ---- API Endpoints ----

@app.post("/api/v1/tools", tags=["Tools"])
async def register_tool(req: RegisterToolRequest):
    """Register a new tool in the registry."""
    tool = registry.register_tool(
        name=req.name,
        description=req.description,
        server_name=req.server_name,
        input_schema=req.input_schema,
        risk_tier=req.risk_tier,
        owner_team=req.owner_team,
        publisher=req.publisher,
        version=req.version,
        tags=req.tags,
    )
    return {"tool_id": tool.id, "status": tool.status.value, "risk_tier": tool.risk_tier.value}


@app.get("/api/v1/tools", tags=["Tools"])
async def list_tools(
    status: Optional[ToolStatus] = None,
    risk_tier: Optional[RiskTier] = None,
    search: Optional[str] = None,
):
    """List or search tools."""
    if search:
        tools = registry.search_tools(search)
    else:
        tools = registry.list_tools(status=status, risk_tier=risk_tier)
    return {
        "tools": [
            {
                "id": t.id, "name": t.name, "description": t.description,
                "risk_tier": t.risk_tier.value, "status": t.status.value,
                "current_version": t.current_version, "owner_team": t.owner_team,
            }
            for t in tools
        ]
    }


@app.get("/api/v1/tools/{tool_id}", tags=["Tools"])
async def get_tool(tool_id: str):
    """Get full details of a tool."""
    tool = registry.get_tool(tool_id)
    if not tool:
        raise HTTPException(404, "Tool not found")
    return asdict(tool)


@app.post("/api/v1/tools/{tool_id}/permissions", tags=["Permissions"])
async def set_tool_permissions(tool_id: str, req: SetPermissionsRequest):
    """Set permissions for a tool."""
    try:
        perm = registry.set_permissions(
            tool_id, req.allowed_roles, req.allowed_users, req.denied_users, req.rate_limit_per_user
        )
        return asdict(perm)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/v1/tools/{tool_id}/check-access", tags=["Permissions"])
async def check_tool_access(tool_id: str, req: CheckAccessRequest):
    """Check if a user can access a tool."""
    allowed, reason = registry.check_access(tool_id, req.user_id, req.user_roles)
    return {"allowed": allowed, "reason": reason}


@app.get("/api/v1/tools/{tool_id}/usage", tags=["Analytics"])
async def get_tool_usage(tool_id: str, hours: int = 24):
    """Get usage analytics for a tool."""
    return registry.get_usage_stats(tool_id, hours)


# ---- Agent Endpoints ----

@app.post("/api/v1/agents", tags=["Agents"])
async def register_agent(req: RegisterAgentRequest):
    """Register a new agent."""
    agent = registry.register_agent(
        name=req.name,
        description=req.description,
        agent_card_url=req.agent_card_url,
        risk_tier=req.risk_tier,
        owner_team=req.owner_team,
        skills=req.skills,
        sla_p99_seconds=req.sla_p99_seconds,
    )
    return {"agent_id": agent.id, "status": agent.status.value}


@app.get("/api/v1/agents", tags=["Agents"])
async def list_agents(capability: Optional[str] = None):
    """List agents, optionally filtered by capability."""
    if capability:
        agents = registry.discover_agents(capability)
    else:
        agents = [a for a in registry.store.agents.values() if a.status == ToolStatus.APPROVED]
    return {
        "agents": [
            {
                "id": a.id, "name": a.name, "description": a.description,
                "risk_tier": a.risk_tier.value, "skills": a.skills,
                "is_healthy": a.is_healthy,
            }
            for a in agents
        ]
    }


# ---- Approval Endpoints ----

@app.get("/api/v1/approvals", tags=["Approvals"])
async def list_approvals(risk_tier: Optional[RiskTier] = None):
    """List pending approvals."""
    approvals = registry.list_pending_approvals(risk_tier)
    return {"approvals": [asdict(a) for a in approvals]}


@app.post("/api/v1/approvals/{approval_id}/approve", tags=["Approvals"])
async def approve(approval_id: str, req: ApproveRequest):
    """Approve a pending item."""
    try:
        result = registry.approve_item(approval_id, req.reviewer, req.reviewer_role, req.notes)
        return asdict(result)
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/v1/approvals/{approval_id}/reject", tags=["Approvals"])
async def reject(approval_id: str, req: RejectRequest):
    """Reject a pending item."""
    try:
        result = registry.reject_item(approval_id, req.reviewer, req.reason)
        return asdict(result)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ============================================================================
# Demo
# ============================================================================


def demo() -> None:
    """Demonstrate registry functionality."""
    print("=== Tool & Agent Registry Demo ===\n")

    r = ToolRegistry()

    # Register tools
    sql_tool = r.register_tool(
        name="execute_query",
        description="Execute read-only SQL queries",
        server_name="sql-readonly",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        risk_tier=RiskTier.LOW,
        owner_team="platform",
        publisher="platform-team",
    )
    print(f"Registered: {sql_tool.name} (status: {sql_tool.status.value}, tier: {sql_tool.risk_tier.value})")

    payment_tool = r.register_tool(
        name="initiate_payment",
        description="Initiate a payment transfer to a vendor",
        server_name="payment-gateway",
        input_schema={"type": "object", "properties": {"amount": {"type": "number"}, "recipient": {"type": "string"}}},
        risk_tier=RiskTier.CRITICAL,
        owner_team="finance",
        publisher="finance-team",
    )
    print(f"Registered: {payment_tool.name} (status: {payment_tool.status.value}, tier: {payment_tool.risk_tier.value})")

    # Check approvals
    pending = r.list_pending_approvals()
    print(f"\nPending approvals: {len(pending)}")
    for a in pending:
        print(f"  - {a.item_name} ({a.risk_tier.value}) requested by {a.requested_by}")

    # Approve
    if pending:
        approved = r.approve_item(pending[0].id, "ciso-jane", "ciso", "Reviewed and approved")
        print(f"\nApproved: {approved.item_name} by {approved.reviewer}")

    # Set permissions
    r.set_permissions(sql_tool.id, allowed_roles=["analyst", "engineer"])
    allowed, reason = r.check_access(sql_tool.id, "user-1", ["analyst"])
    print(f"\nAccess check (analyst): allowed={allowed}, reason={reason}")

    allowed, reason = r.check_access(sql_tool.id, "user-2", ["intern"])
    print(f"Access check (intern): allowed={allowed}, reason={reason}")

    # Usage analytics
    r.record_usage(sql_tool.id, "user-1", 45.0, True)
    r.record_usage(sql_tool.id, "user-1", 120.0, True)
    r.record_usage(sql_tool.id, "user-2", 500.0, False, "timeout")
    stats = r.get_usage_stats(sql_tool.id)
    print(f"\nUsage stats: {json.dumps(stats, indent=2)}")

    # Register agent
    agent = r.register_agent(
        name="expense-agent",
        description="Processes expense reports and reimbursements",
        agent_card_url="https://expense-agent.internal",
        risk_tier=RiskTier.MEDIUM,
        owner_team="finance",
        skills=[{"id": "process-expense", "name": "Process Expense", "description": "Submit and validate expenses"}],
    )
    print(f"\nRegistered agent: {agent.name} (status: {agent.status.value})")

    # Discover agents
    found = r.discover_agents("expense")
    print(f"Agents for 'expense': {[a.name for a in found]}")


if __name__ == "__main__":
    demo()
