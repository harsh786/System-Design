"""
Authorization Engine for AI Systems
=====================================
Complete implementation covering:
- RBAC (Role-Based Access Control)
- ABAC (Attribute-Based Access Control)
- ReBAC (Relationship-Based Access Control)
- Policy engine with rules evaluation
- Document-level permission checking
- Tool permission evaluation
- Action approval workflow
- Tenant isolation enforcement
- Permission change propagation
"""

import asyncio
import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# =============================================================================
# Core Models
# =============================================================================

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"  # Policy doesn't apply


class Effect(Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class AuthorizationRequest:
    """A request to evaluate authorization."""
    subject: str  # Who is requesting
    action: str  # What action
    resource: str  # On what resource
    tenant_id: str
    context: dict = field(default_factory=dict)  # Additional attributes
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuthorizationResult:
    """Result of an authorization decision."""
    decision: Decision
    reason: str
    policy_id: Optional[str] = None
    evaluated_policies: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    request_id: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.decision == Decision.ALLOW


# =============================================================================
# RBAC Implementation
# =============================================================================

@dataclass
class Permission:
    """A permission that can be assigned to roles."""
    resource_type: str  # e.g., "document", "tool", "calendar"
    action: str  # e.g., "read", "write", "execute", "delete"
    
    @property
    def key(self) -> str:
        return f"{self.resource_type}:{self.action}"
    
    def matches(self, resource_type: str, action: str) -> bool:
        """Check if this permission covers the requested access."""
        type_match = self.resource_type == "*" or self.resource_type == resource_type
        action_match = self.action == "*" or self.action == action
        return type_match and action_match


@dataclass
class Role:
    """A role with permissions and optional parent roles."""
    name: str
    permissions: list[Permission]
    parent_roles: list[str] = field(default_factory=list)  # Role hierarchy
    description: str = ""
    tenant_id: Optional[str] = None  # None = global role


class RBACEngine:
    """
    Role-Based Access Control with hierarchy support.
    
    Features:
    - Role hierarchy (admin inherits all editor permissions)
    - Wildcard permissions
    - Tenant-scoped roles
    - Role assignment with expiry
    """

    def __init__(self):
        self._roles: dict[str, Role] = {}
        self._user_roles: dict[str, list[dict]] = {}  # user_id → [{role, tenant_id, expires_at}]
        self._role_cache: dict[str, set[str]] = {}  # Expanded permissions cache

    def define_role(self, role: Role):
        """Define a role in the system."""
        self._roles[role.name] = role
        self._role_cache.clear()  # Invalidate cache on role change

    def assign_role(self, user_id: str, role_name: str, tenant_id: str, expires_at: datetime = None):
        """Assign a role to a user within a tenant."""
        if role_name not in self._roles:
            raise ValueError(f"Unknown role: {role_name}")
        
        if user_id not in self._user_roles:
            self._user_roles[user_id] = []
        
        self._user_roles[user_id].append({
            "role": role_name,
            "tenant_id": tenant_id,
            "expires_at": expires_at,
            "assigned_at": datetime.now(timezone.utc),
        })

    def revoke_role(self, user_id: str, role_name: str, tenant_id: str):
        """Revoke a role from a user."""
        if user_id in self._user_roles:
            self._user_roles[user_id] = [
                r for r in self._user_roles[user_id]
                if not (r["role"] == role_name and r["tenant_id"] == tenant_id)
            ]

    def get_user_permissions(self, user_id: str, tenant_id: str) -> set[str]:
        """Get all effective permissions for a user in a tenant."""
        permissions = set()
        assignments = self._user_roles.get(user_id, [])
        now = datetime.now(timezone.utc)

        for assignment in assignments:
            # Check tenant match
            if assignment["tenant_id"] != tenant_id:
                continue
            # Check expiry
            if assignment["expires_at"] and assignment["expires_at"] < now:
                continue
            
            # Expand role hierarchy
            role_permissions = self._expand_role(assignment["role"])
            permissions.update(role_permissions)

        return permissions

    def _expand_role(self, role_name: str) -> set[str]:
        """Expand a role into all its permissions (including inherited)."""
        if role_name in self._role_cache:
            return self._role_cache[role_name]

        permissions = set()
        visited = set()
        stack = [role_name]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            role = self._roles.get(current)
            if not role:
                continue

            for perm in role.permissions:
                permissions.add(perm.key)

            stack.extend(role.parent_roles)

        self._role_cache[role_name] = permissions
        return permissions

    def evaluate(self, request: AuthorizationRequest, user_roles: list[str] = None) -> AuthorizationResult:
        """Evaluate an RBAC authorization request."""
        start = time.time()

        # Get user's effective permissions
        if user_roles:
            permissions = set()
            for role_name in user_roles:
                permissions.update(self._expand_role(role_name))
        else:
            permissions = self.get_user_permissions(request.subject, request.tenant_id)

        # Parse resource type from resource string (e.g., "document:doc_123" → "document")
        resource_type = request.resource.split(":")[0] if ":" in request.resource else request.resource

        # Check if any permission covers this request
        required = f"{resource_type}:{request.action}"
        
        allowed = False
        for perm_key in permissions:
            perm = Permission(*perm_key.split(":", 1))
            if perm.matches(resource_type, request.action):
                allowed = True
                break

        duration = (time.time() - start) * 1000
        return AuthorizationResult(
            decision=Decision.ALLOW if allowed else Decision.DENY,
            reason=f"RBAC: {'permission found' if allowed else 'no matching permission'}",
            policy_id="rbac",
            duration_ms=duration,
            request_id=request.request_id,
        )


# =============================================================================
# ABAC Implementation
# =============================================================================

@dataclass
class ABACRule:
    """An attribute-based access control rule."""
    rule_id: str
    description: str
    effect: Effect
    priority: int = 0  # Higher priority rules evaluated first
    
    # Conditions (all must be true for rule to apply)
    subject_conditions: dict = field(default_factory=dict)
    resource_conditions: dict = field(default_factory=dict)
    action_conditions: list[str] = field(default_factory=list)
    context_conditions: dict = field(default_factory=dict)

    def matches(self, request: AuthorizationRequest, subject_attrs: dict, resource_attrs: dict) -> bool:
        """Check if this rule applies to the given request."""
        # Check action
        if self.action_conditions and request.action not in self.action_conditions:
            return False

        # Check subject conditions
        for attr, expected in self.subject_conditions.items():
            actual = subject_attrs.get(attr)
            if not self._matches_condition(actual, expected):
                return False

        # Check resource conditions
        for attr, expected in self.resource_conditions.items():
            actual = resource_attrs.get(attr)
            if not self._matches_condition(actual, expected):
                return False

        # Check context conditions
        for attr, expected in self.context_conditions.items():
            actual = request.context.get(attr)
            if not self._matches_condition(actual, expected):
                return False

        return True

    def _matches_condition(self, actual: Any, expected: Any) -> bool:
        """Evaluate a single condition."""
        if isinstance(expected, dict):
            # Operator-based conditions
            for op, value in expected.items():
                if op == "$eq" and actual != value:
                    return False
                elif op == "$ne" and actual == value:
                    return False
                elif op == "$in" and actual not in value:
                    return False
                elif op == "$nin" and actual in value:
                    return False
                elif op == "$gt" and not (actual is not None and actual > value):
                    return False
                elif op == "$gte" and not (actual is not None and actual >= value):
                    return False
                elif op == "$lt" and not (actual is not None and actual < value):
                    return False
                elif op == "$lte" and not (actual is not None and actual <= value):
                    return False
                elif op == "$contains" and value not in (actual or []):
                    return False
                elif op == "$exists" and (actual is not None) != value:
                    return False
            return True
        else:
            return actual == expected


class ABACEngine:
    """
    Attribute-Based Access Control engine.
    
    Evaluates rules based on:
    - Subject attributes (user department, clearance level, etc.)
    - Resource attributes (classification, owner, type, etc.)
    - Action (read, write, delete, etc.)
    - Context (time, location, device, etc.)
    """

    def __init__(self):
        self._rules: list[ABACRule] = []
        self._subject_store: dict[str, dict] = {}  # user_id → attributes
        self._resource_store: dict[str, dict] = {}  # resource_id → attributes

    def add_rule(self, rule: ABACRule):
        """Add a rule to the engine."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def set_subject_attributes(self, subject_id: str, attributes: dict):
        """Set attributes for a subject."""
        self._subject_store[subject_id] = attributes

    def set_resource_attributes(self, resource_id: str, attributes: dict):
        """Set attributes for a resource."""
        self._resource_store[resource_id] = attributes

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationResult:
        """Evaluate ABAC rules. First matching rule wins (by priority)."""
        start = time.time()
        
        subject_attrs = self._subject_store.get(request.subject, {})
        resource_attrs = self._resource_store.get(request.resource, {})
        
        evaluated = []
        for rule in self._rules:
            evaluated.append(rule.rule_id)
            if rule.matches(request, subject_attrs, resource_attrs):
                duration = (time.time() - start) * 1000
                decision = Decision.ALLOW if rule.effect == Effect.ALLOW else Decision.DENY
                return AuthorizationResult(
                    decision=decision,
                    reason=f"ABAC rule matched: {rule.description}",
                    policy_id=rule.rule_id,
                    evaluated_policies=evaluated,
                    duration_ms=duration,
                    request_id=request.request_id,
                )

        # No rule matched - default deny
        duration = (time.time() - start) * 1000
        return AuthorizationResult(
            decision=Decision.DENY,
            reason="ABAC: no matching rule (default deny)",
            evaluated_policies=evaluated,
            duration_ms=duration,
            request_id=request.request_id,
        )


# =============================================================================
# ReBAC Implementation (Relationship-Based Access Control)
# =============================================================================

@dataclass
class Relationship:
    """A relationship between two entities."""
    subject_type: str  # e.g., "user", "group", "team"
    subject_id: str
    relation: str  # e.g., "member", "owner", "viewer", "parent"
    object_type: str  # e.g., "document", "folder", "organization"
    object_id: str


class ReBACEngine:
    """
    Relationship-Based Access Control (inspired by Google Zanzibar).
    
    Determines access by traversing relationship graphs:
    User --member-of--> Team --owns--> Project --contains--> Document
    
    If a path exists from user to resource through valid relationships,
    access is granted.
    """

    def __init__(self):
        # Adjacency list: (subject_type, subject_id) → [(relation, object_type, object_id)]
        self._forward: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
        # Reverse: (object_type, object_id) → [(relation, subject_type, subject_id)]
        self._reverse: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
        # Permission derivation rules: (object_type, relation) → implied permissions
        self._permission_rules: dict[tuple[str, str], list[str]] = {}

    def add_relationship(self, rel: Relationship):
        """Add a relationship to the graph."""
        subject_key = (rel.subject_type, rel.subject_id)
        object_key = (rel.object_type, rel.object_id)

        if subject_key not in self._forward:
            self._forward[subject_key] = []
        self._forward[subject_key].append((rel.relation, rel.object_type, rel.object_id))

        if object_key not in self._reverse:
            self._reverse[object_key] = []
        self._reverse[object_key].append((rel.relation, rel.subject_type, rel.subject_id))

    def remove_relationship(self, rel: Relationship):
        """Remove a relationship from the graph."""
        subject_key = (rel.subject_type, rel.subject_id)
        object_key = (rel.object_type, rel.object_id)

        if subject_key in self._forward:
            self._forward[subject_key] = [
                r for r in self._forward[subject_key]
                if r != (rel.relation, rel.object_type, rel.object_id)
            ]
        if object_key in self._reverse:
            self._reverse[object_key] = [
                r for r in self._reverse[object_key]
                if r != (rel.relation, rel.subject_type, rel.subject_id)
            ]

    def define_permission_rule(self, object_type: str, relation: str, permissions: list[str]):
        """
        Define what permissions a relation grants on an object type.
        e.g., ("document", "owner") → ["read", "write", "delete"]
              ("document", "viewer") → ["read"]
        """
        self._permission_rules[(object_type, relation)] = permissions

    def check_permission(
        self,
        subject_type: str,
        subject_id: str,
        permission: str,
        object_type: str,
        object_id: str,
        max_depth: int = 10,
    ) -> bool:
        """
        Check if subject has permission on object by traversing relationships.
        
        Algorithm:
        1. Find all subjects that have required relation to object (reverse lookup)
        2. Check if our subject can reach any of those subjects (forward traversal)
        """
        # Find which relations grant this permission on this object type
        granting_relations = []
        for (otype, relation), perms in self._permission_rules.items():
            if otype == object_type and permission in perms:
                granting_relations.append(relation)

        if not granting_relations:
            return False

        # Check direct relationships
        object_key = (object_type, object_id)
        if object_key in self._reverse:
            for relation, stype, sid in self._reverse[object_key]:
                if relation in granting_relations:
                    if stype == subject_type and sid == subject_id:
                        return True
                    # Check if subject is connected to this entity
                    if self._is_connected(subject_type, subject_id, stype, sid, max_depth):
                        return True

        # Check parent relationships (e.g., document in folder, folder in project)
        # Traverse up the containment hierarchy
        if object_key in self._reverse:
            for relation, parent_type, parent_id in self._reverse[object_key]:
                if relation in ("parent", "contains", "folder"):
                    if self.check_permission(
                        subject_type, subject_id, permission,
                        parent_type, parent_id, max_depth - 1
                    ):
                        return True

        return False

    def _is_connected(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        max_depth: int,
    ) -> bool:
        """BFS to check if from_entity can reach to_entity through relationships."""
        if max_depth <= 0:
            return False

        visited = set()
        queue = [(from_type, from_id, 0)]

        while queue:
            current_type, current_id, depth = queue.pop(0)
            
            if current_type == to_type and current_id == to_id:
                return True
            
            if depth >= max_depth:
                continue

            key = (current_type, current_id)
            if key in visited:
                continue
            visited.add(key)

            # Follow forward edges (member-of, belongs-to, etc.)
            for relation, obj_type, obj_id in self._forward.get(key, []):
                if (obj_type, obj_id) not in visited:
                    queue.append((obj_type, obj_id, depth + 1))

        return False

    def get_accessible_resources(
        self,
        subject_type: str,
        subject_id: str,
        permission: str,
        object_type: str,
    ) -> list[str]:
        """Get all resource IDs of given type that subject can access with permission."""
        accessible = []
        
        # Find relations that grant this permission
        granting_relations = []
        for (otype, relation), perms in self._permission_rules.items():
            if otype == object_type and permission in perms:
                granting_relations.append(relation)

        # Find all objects of this type
        for (otype, oid), relations in self._reverse.items():
            if otype != object_type:
                continue
            if self.check_permission(subject_type, subject_id, permission, object_type, oid):
                accessible.append(oid)

        return accessible

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationResult:
        """Evaluate a ReBAC authorization request."""
        start = time.time()
        
        # Parse resource into type:id
        if ":" in request.resource:
            resource_type, resource_id = request.resource.split(":", 1)
        else:
            resource_type = request.resource
            resource_id = request.resource

        allowed = self.check_permission(
            subject_type="user",
            subject_id=request.subject,
            permission=request.action,
            object_type=resource_type,
            object_id=resource_id,
        )

        duration = (time.time() - start) * 1000
        return AuthorizationResult(
            decision=Decision.ALLOW if allowed else Decision.DENY,
            reason=f"ReBAC: {'relationship path found' if allowed else 'no relationship path'}",
            policy_id="rebac",
            duration_ms=duration,
            request_id=request.request_id,
        )


# =============================================================================
# Unified Policy Engine
# =============================================================================

class CombiningAlgorithm(Enum):
    DENY_OVERRIDES = "deny_overrides"  # Any deny → deny
    ALLOW_OVERRIDES = "allow_overrides"  # Any allow → allow
    FIRST_APPLICABLE = "first_applicable"  # First non-abstain result wins
    UNANIMOUS = "unanimous"  # All must allow


class PolicyEngine:
    """
    Unified policy engine that combines RBAC, ABAC, and ReBAC decisions.
    
    Supports multiple combining algorithms and policy ordering.
    """

    def __init__(self, combining: CombiningAlgorithm = CombiningAlgorithm.DENY_OVERRIDES):
        self.combining = combining
        self._engines: list[tuple[str, Any]] = []  # (name, engine) pairs
        self._audit_log: list[dict] = []

    def register_engine(self, name: str, engine: Any):
        """Register an authorization engine."""
        self._engines.append((name, engine))

    async def evaluate(self, request: AuthorizationRequest) -> AuthorizationResult:
        """Evaluate request against all registered engines."""
        start = time.time()
        results: list[tuple[str, AuthorizationResult]] = []

        for name, engine in self._engines:
            result = engine.evaluate(request)
            results.append((name, result))

        # Apply combining algorithm
        final = self._combine(results)
        final.duration_ms = (time.time() - start) * 1000
        final.request_id = request.request_id
        final.evaluated_policies = [name for name, _ in results]

        # Audit
        self._audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request": {
                "subject": request.subject,
                "action": request.action,
                "resource": request.resource,
                "tenant_id": request.tenant_id,
            },
            "decision": final.decision.value,
            "reason": final.reason,
            "engines_evaluated": [(name, r.decision.value) for name, r in results],
            "duration_ms": final.duration_ms,
        })

        return final

    def _combine(self, results: list[tuple[str, AuthorizationResult]]) -> AuthorizationResult:
        """Combine multiple authorization results."""
        if self.combining == CombiningAlgorithm.DENY_OVERRIDES:
            for name, result in results:
                if result.decision == Decision.DENY:
                    return AuthorizationResult(
                        decision=Decision.DENY,
                        reason=f"Denied by {name}: {result.reason}",
                        policy_id=result.policy_id,
                    )
            # No deny found, check for at least one allow
            for name, result in results:
                if result.decision == Decision.ALLOW:
                    return AuthorizationResult(
                        decision=Decision.ALLOW,
                        reason=f"Allowed (no deny overrides). First allow: {name}",
                        policy_id=result.policy_id,
                    )
            return AuthorizationResult(decision=Decision.DENY, reason="No policy allowed access")

        elif self.combining == CombiningAlgorithm.ALLOW_OVERRIDES:
            for name, result in results:
                if result.decision == Decision.ALLOW:
                    return AuthorizationResult(
                        decision=Decision.ALLOW,
                        reason=f"Allowed by {name}: {result.reason}",
                        policy_id=result.policy_id,
                    )
            return AuthorizationResult(decision=Decision.DENY, reason="No policy allowed access")

        elif self.combining == CombiningAlgorithm.FIRST_APPLICABLE:
            for name, result in results:
                if result.decision != Decision.ABSTAIN:
                    return result
            return AuthorizationResult(decision=Decision.DENY, reason="No applicable policy")

        elif self.combining == CombiningAlgorithm.UNANIMOUS:
            for name, result in results:
                if result.decision == Decision.DENY:
                    return AuthorizationResult(
                        decision=Decision.DENY,
                        reason=f"Unanimous denied by {name}",
                        policy_id=result.policy_id,
                    )
                if result.decision == Decision.ABSTAIN:
                    return AuthorizationResult(
                        decision=Decision.DENY,
                        reason=f"Unanimous: {name} abstained (treated as deny)",
                    )
            return AuthorizationResult(decision=Decision.ALLOW, reason="All engines allowed unanimously")


# =============================================================================
# Document-Level Permission Checking
# =============================================================================

@dataclass
class DocumentACL:
    """Access Control List for a document."""
    document_id: str
    owner: str
    tenant_id: str
    viewers: list[str] = field(default_factory=list)  # User IDs
    editors: list[str] = field(default_factory=list)
    viewer_groups: list[str] = field(default_factory=list)  # Group IDs
    editor_groups: list[str] = field(default_factory=list)
    is_public: bool = False  # Public within tenant
    classification: str = "internal"  # public, internal, confidential, restricted
    inherit_parent: bool = True  # Inherit permissions from parent folder


class DocumentPermissionChecker:
    """
    Checks document-level permissions with group expansion and inheritance.
    """

    def __init__(self):
        self._acls: dict[str, DocumentACL] = {}  # doc_id → ACL
        self._parent_map: dict[str, str] = {}  # doc_id → parent_doc_id
        self._user_groups: dict[str, list[str]] = {}  # user_id → group_ids

    def set_acl(self, acl: DocumentACL):
        self._acls[acl.document_id] = acl

    def set_parent(self, doc_id: str, parent_id: str):
        self._parent_map[doc_id] = parent_id

    def set_user_groups(self, user_id: str, groups: list[str]):
        self._user_groups[user_id] = groups

    def check_access(
        self,
        user_id: str,
        document_id: str,
        action: str,  # "read" or "write"
        tenant_id: str,
    ) -> bool:
        """Check if user can perform action on document."""
        acl = self._acls.get(document_id)
        if not acl:
            return False

        # Tenant isolation - hard boundary
        if acl.tenant_id != tenant_id:
            return False

        # Owner has full access
        if acl.owner == user_id:
            return True

        # Get user's groups
        user_groups = set(self._user_groups.get(user_id, []))

        if action == "read":
            # Check public
            if acl.is_public:
                return True
            # Direct viewer/editor
            if user_id in acl.viewers or user_id in acl.editors:
                return True
            # Group-based
            if user_groups & set(acl.viewer_groups):
                return True
            if user_groups & set(acl.editor_groups):
                return True

        elif action == "write":
            if user_id in acl.editors:
                return True
            if user_groups & set(acl.editor_groups):
                return True

        # Check parent inheritance
        if acl.inherit_parent and document_id in self._parent_map:
            parent_id = self._parent_map[document_id]
            return self.check_access(user_id, parent_id, action, tenant_id)

        return False

    def get_accessible_documents(
        self,
        user_id: str,
        tenant_id: str,
        action: str = "read",
    ) -> list[str]:
        """Get all document IDs accessible by user (for pre-filtering)."""
        accessible = []
        for doc_id, acl in self._acls.items():
            if self.check_access(user_id, doc_id, action, tenant_id):
                accessible.append(doc_id)
        return accessible


# =============================================================================
# Tool Permission Evaluation
# =============================================================================

@dataclass
class ToolDefinition:
    """Definition of a tool with its permission requirements."""
    name: str
    description: str
    required_permissions: list[str]
    risk_level: str = "low"  # low, medium, high, critical
    requires_approval: bool = False
    max_calls_per_session: int = 100
    allowed_roles: list[str] = field(default_factory=list)  # Empty = all roles
    denied_roles: list[str] = field(default_factory=list)


class ToolPermissionEvaluator:
    """
    Evaluates whether a user/agent can invoke a specific tool.
    Considers permissions, roles, risk level, and rate limits.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._call_counts: dict[str, dict[str, int]] = {}  # session_id → {tool → count}

    def register_tool(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def evaluate(
        self,
        tool_name: str,
        user_permissions: list[str],
        user_roles: list[str],
        session_id: str,
    ) -> AuthorizationResult:
        """Evaluate if tool can be invoked."""
        tool = self._tools.get(tool_name)
        if not tool:
            return AuthorizationResult(
                decision=Decision.DENY,
                reason=f"Unknown tool: {tool_name}",
            )

        # Check denied roles
        if tool.denied_roles and any(r in tool.denied_roles for r in user_roles):
            return AuthorizationResult(
                decision=Decision.DENY,
                reason=f"User role is denied for tool {tool_name}",
            )

        # Check allowed roles (if specified)
        if tool.allowed_roles and not any(r in tool.allowed_roles for r in user_roles):
            return AuthorizationResult(
                decision=Decision.DENY,
                reason=f"User role not in allowed roles for tool {tool_name}",
            )

        # Check permissions
        for required in tool.required_permissions:
            has_perm = False
            for user_perm in user_permissions:
                if user_perm == required or user_perm == "*":
                    has_perm = True
                    break
                if user_perm.endswith(":*"):
                    prefix = user_perm[:-2]
                    if required.startswith(prefix + ":"):
                        has_perm = True
                        break
            if not has_perm:
                return AuthorizationResult(
                    decision=Decision.DENY,
                    reason=f"Missing permission {required} for tool {tool_name}",
                )

        # Check rate limit
        session_counts = self._call_counts.setdefault(session_id, {})
        current_count = session_counts.get(tool_name, 0)
        if current_count >= tool.max_calls_per_session:
            return AuthorizationResult(
                decision=Decision.DENY,
                reason=f"Rate limit exceeded for tool {tool_name} ({current_count}/{tool.max_calls_per_session})",
            )

        # Increment count
        session_counts[tool_name] = current_count + 1

        # Check if approval required
        if tool.requires_approval:
            return AuthorizationResult(
                decision=Decision.DENY,
                reason=f"Tool {tool_name} requires approval (risk_level={tool.risk_level})",
                policy_id="approval_required",
            )

        return AuthorizationResult(
            decision=Decision.ALLOW,
            reason=f"Tool {tool_name} authorized",
        )


# =============================================================================
# Action Approval Workflow
# =============================================================================

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """A request awaiting human approval."""
    request_id: str
    requester: str
    action: str
    resource: str
    tool_name: str
    reason: str
    tenant_id: str
    approvers: list[str]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: Optional[str] = None
    approval_comment: Optional[str] = None


class ApprovalWorkflow:
    """
    Manages approval workflows for high-risk actions.
    Agent pauses execution until approval is received.
    """

    def __init__(self, default_expiry_minutes: int = 60):
        self.default_expiry_minutes = default_expiry_minutes
        self._requests: dict[str, ApprovalRequest] = {}
        self._callbacks: dict[str, asyncio.Future] = {}

    async def request_approval(
        self,
        requester: str,
        action: str,
        resource: str,
        tool_name: str,
        reason: str,
        tenant_id: str,
        approvers: list[str],
        timeout_seconds: int = None,
    ) -> ApprovalRequest:
        """Create approval request and wait for decision."""
        request_id = str(uuid.uuid4())
        expiry = datetime.now(timezone.utc) + timedelta(
            minutes=self.default_expiry_minutes
        )

        approval = ApprovalRequest(
            request_id=request_id,
            requester=requester,
            action=action,
            resource=resource,
            tool_name=tool_name,
            reason=reason,
            tenant_id=tenant_id,
            approvers=approvers,
            expires_at=expiry,
        )
        self._requests[request_id] = approval

        # Create future for async waiting
        future = asyncio.get_event_loop().create_future()
        self._callbacks[request_id] = future

        # Notify approvers (webhook, email, Slack, etc.)
        await self._notify_approvers(approval)

        # Wait for approval (with timeout)
        timeout = timeout_seconds or (self.default_expiry_minutes * 60)
        try:
            await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            approval.status = ApprovalStatus.EXPIRED
            return approval

        return self._requests[request_id]

    def approve(self, request_id: str, approver: str, comment: str = None):
        """Approve a pending request."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Unknown approval request: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request already {request.status.value}")
        if approver not in request.approvers:
            raise ValueError(f"{approver} is not an authorized approver")

        request.status = ApprovalStatus.APPROVED
        request.approved_by = approver
        request.approval_comment = comment

        # Resolve the waiting future
        if request_id in self._callbacks:
            self._callbacks[request_id].set_result(True)

    def reject(self, request_id: str, approver: str, comment: str = None):
        """Reject a pending request."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Unknown approval request: {request_id}")
        
        request.status = ApprovalStatus.REJECTED
        request.approved_by = approver
        request.approval_comment = comment

        if request_id in self._callbacks:
            self._callbacks[request_id].set_result(False)

    async def _notify_approvers(self, approval: ApprovalRequest):
        """Send notifications to approvers. Override for real implementation."""
        print(f"[APPROVAL NEEDED] {approval.requester} wants to {approval.action} "
              f"on {approval.resource} using tool {approval.tool_name}")
        print(f"  Approvers: {approval.approvers}")
        print(f"  Expires: {approval.expires_at}")


# =============================================================================
# Tenant Isolation Enforcement
# =============================================================================

class TenantIsolationEnforcer:
    """
    Enforces strict tenant isolation at the authorization layer.
    Every resource access must pass tenant boundary check.
    """

    def __init__(self):
        self._resource_tenants: dict[str, str] = {}  # resource_id → tenant_id
        self._violations: list[dict] = []

    def register_resource(self, resource_id: str, tenant_id: str):
        self._resource_tenants[resource_id] = tenant_id

    def check_tenant_access(self, request_tenant: str, resource_id: str) -> bool:
        """Verify resource belongs to requester's tenant."""
        resource_tenant = self._resource_tenants.get(resource_id)
        if resource_tenant is None:
            # Unknown resource - deny by default
            self._log_violation(request_tenant, resource_id, "unknown_resource")
            return False
        
        if resource_tenant != request_tenant:
            self._log_violation(request_tenant, resource_id, "cross_tenant_access")
            return False
        
        return True

    def _log_violation(self, tenant: str, resource: str, violation_type: str):
        """Log tenant isolation violations for security monitoring."""
        self._violations.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requesting_tenant": tenant,
            "resource": resource,
            "violation_type": violation_type,
            "severity": "critical",
        })


# =============================================================================
# Permission Change Propagation
# =============================================================================

class PermissionChangeEvent(Enum):
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    PERMISSION_ADDED = "permission_added"
    PERMISSION_REMOVED = "permission_removed"
    GROUP_MEMBERSHIP_CHANGED = "group_membership_changed"
    DOCUMENT_ACL_CHANGED = "document_acl_changed"
    USER_DEACTIVATED = "user_deactivated"


@dataclass
class PermissionChange:
    event: PermissionChangeEvent
    user_id: str
    tenant_id: str
    details: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PermissionPropagator:
    """
    Propagates permission changes across the system.
    Ensures that when permissions change, all caches and derived state
    are updated immediately.
    """

    def __init__(self):
        self._listeners: list[callable] = []
        self._change_log: list[PermissionChange] = []

    def register_listener(self, callback: callable):
        """Register a listener for permission changes."""
        self._listeners.append(callback)

    async def propagate(self, change: PermissionChange):
        """Propagate a permission change to all listeners."""
        self._change_log.append(change)
        
        for listener in self._listeners:
            try:
                await listener(change)
            except Exception as e:
                # Log but don't fail - permission propagation must be resilient
                print(f"Error propagating permission change: {e}")

    async def handle_role_revoked(self, user_id: str, role: str, tenant_id: str):
        """Handle role revocation - invalidate all affected caches/sessions."""
        change = PermissionChange(
            event=PermissionChangeEvent.ROLE_REVOKED,
            user_id=user_id,
            tenant_id=tenant_id,
            details={"role": role},
        )
        await self.propagate(change)

    async def handle_user_deactivated(self, user_id: str, tenant_id: str):
        """Handle user deactivation - immediately revoke all access."""
        change = PermissionChange(
            event=PermissionChangeEvent.USER_DEACTIVATED,
            user_id=user_id,
            tenant_id=tenant_id,
            details={"action": "immediate_revocation"},
        )
        await self.propagate(change)


# =============================================================================
# Complete Authorization Service
# =============================================================================

class AuthorizationService:
    """
    Unified authorization service that combines all engines and provides
    a single evaluation point for the AI agent system.
    """

    def __init__(self):
        self.rbac = RBACEngine()
        self.abac = ABACEngine()
        self.rebac = ReBACEngine()
        self.policy_engine = PolicyEngine(CombiningAlgorithm.DENY_OVERRIDES)
        self.document_checker = DocumentPermissionChecker()
        self.tool_evaluator = ToolPermissionEvaluator()
        self.approval_workflow = ApprovalWorkflow()
        self.tenant_enforcer = TenantIsolationEnforcer()
        self.propagator = PermissionPropagator()

        # Register engines with policy engine
        self.policy_engine.register_engine("rbac", self.rbac)
        self.policy_engine.register_engine("abac", self.abac)
        self.policy_engine.register_engine("rebac", self.rebac)

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationResult:
        """
        Main authorization entry point.
        Checks tenant isolation, then evaluates policies.
        """
        # Step 1: Tenant isolation (hard boundary)
        if not self.tenant_enforcer.check_tenant_access(request.tenant_id, request.resource):
            return AuthorizationResult(
                decision=Decision.DENY,
                reason="Tenant isolation violation",
                request_id=request.request_id,
            )

        # Step 2: Policy evaluation
        return await self.policy_engine.evaluate(request)

    async def authorize_tool(
        self,
        tool_name: str,
        user_permissions: list[str],
        user_roles: list[str],
        session_id: str,
    ) -> AuthorizationResult:
        """Authorize tool invocation."""
        return self.tool_evaluator.evaluate(tool_name, user_permissions, user_roles, session_id)

    async def authorize_document(
        self,
        user_id: str,
        document_id: str,
        action: str,
        tenant_id: str,
    ) -> bool:
        """Authorize document access."""
        return self.document_checker.check_access(user_id, document_id, action, tenant_id)


# =============================================================================
# Usage Example
# =============================================================================

async def example():
    """Demonstrates the authorization engine."""
    service = AuthorizationService()

    # Define roles
    service.rbac.define_role(Role(
        name="admin",
        permissions=[Permission("*", "*")],
    ))
    service.rbac.define_role(Role(
        name="editor",
        permissions=[
            Permission("document", "read"),
            Permission("document", "write"),
            Permission("tool", "execute"),
        ],
    ))
    service.rbac.define_role(Role(
        name="viewer",
        permissions=[Permission("document", "read")],
        parent_roles=[]
    ))

    # Assign roles
    service.rbac.assign_role("user_1", "editor", "tenant_abc")
    service.rbac.assign_role("user_2", "viewer", "tenant_abc")

    # Register tools
    service.tool_evaluator.register_tool(ToolDefinition(
        name="web_search",
        description="Search the web",
        required_permissions=["tool:execute", "web:read"],
        risk_level="low",
    ))
    service.tool_evaluator.register_tool(ToolDefinition(
        name="send_email",
        description="Send an email",
        required_permissions=["email:send"],
        risk_level="high",
        requires_approval=True,
    ))

    # Define relationships (ReBAC)
    service.rebac.add_relationship(Relationship("user", "user_1", "member", "team", "engineering"))
    service.rebac.add_relationship(Relationship("team", "engineering", "owner", "project", "ai-platform"))
    service.rebac.add_relationship(Relationship("project", "ai-platform", "contains", "document", "design_doc"))
    service.rebac.define_permission_rule("document", "owner", ["read", "write", "delete"])
    service.rebac.define_permission_rule("document", "contains", ["read"])

    # Evaluate
    request = AuthorizationRequest(
        subject="user_1",
        action="read",
        resource="document:design_doc",
        tenant_id="tenant_abc",
    )
    
    # Register resource tenant
    service.tenant_enforcer.register_resource("document:design_doc", "tenant_abc")
    
    result = await service.authorize(request)
    print(f"Authorization result: {result.decision.value} - {result.reason}")


if __name__ == "__main__":
    asyncio.run(example())
