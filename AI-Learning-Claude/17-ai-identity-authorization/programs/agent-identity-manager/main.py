"""
Agent Identity Manager
Simulates the full lifecycle of AI agent identity management.
"""

import json
import uuid
import hashlib
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass
class Certificate:
    thumbprint: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False

    @property
    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        return not self.revoked and self.issued_at <= now <= self.expires_at


@dataclass
class AgentIdentity:
    agent_id: str
    client_id: str
    agent_type: str
    max_permissions: list[str]
    certificate: Certificate
    status: AgentStatus = AgentStatus.ACTIVE
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    registered_by: str = ""
    owner: str = ""
    version: str = "1.0.0"

    @property
    def is_active(self) -> bool:
        return self.status == AgentStatus.ACTIVE and self.certificate.is_valid


@dataclass
class AuthToken:
    agent_id: str
    scope: list[str]
    issued_at: datetime
    expires_at: datetime
    token_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class AgentRegistry:
    """Manages agent identities throughout their lifecycle."""

    def __init__(self):
        self.agents: dict[str, AgentIdentity] = {}
        self.audit_log: list[dict] = []

    def _log(self, event_type: str, agent_id: str, details: str):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "agent_id": agent_id,
            "details": details,
        }
        self.audit_log.append(entry)
        print(f"  [AUDIT] {event_type}: {details}")

    # --- 1. REGISTRATION ---
    def register_agent(
        self,
        agent_type: str,
        max_permissions: list[str],
        owner: str,
        registered_by: str,
        cert_valid_days: int = 90,
    ) -> AgentIdentity:
        """Register a new agent identity."""
        agent_id = f"agent:{agent_type}-{uuid.uuid4().hex[:8]}"
        client_id = str(uuid.uuid4())

        cert = Certificate(
            thumbprint=hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16],
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=cert_valid_days),
        )

        identity = AgentIdentity(
            agent_id=agent_id,
            client_id=client_id,
            agent_type=agent_type,
            max_permissions=max_permissions,
            certificate=cert,
            registered_by=registered_by,
            owner=owner,
        )

        self.agents[agent_id] = identity
        self._log("registration", agent_id, f"Registered by {registered_by}, owner={owner}")
        return identity

    # --- 2. AUTHENTICATION ---
    def authenticate(self, agent_id: str, cert_thumbprint: str) -> Optional[AuthToken]:
        """Agent proves its identity using its certificate."""
        agent = self.agents.get(agent_id)

        if not agent:
            self._log("auth_failure", agent_id, "Agent not found")
            return None

        if agent.status != AgentStatus.ACTIVE:
            self._log("auth_failure", agent_id, f"Agent status: {agent.status.value}")
            return None

        if not agent.certificate.is_valid:
            self._log("auth_failure", agent_id, "Certificate invalid or expired")
            return None

        if agent.certificate.thumbprint != cert_thumbprint:
            self._log("auth_failure", agent_id, "Certificate thumbprint mismatch")
            return None

        token = AuthToken(
            agent_id=agent_id,
            scope=agent.max_permissions,
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

        self._log("auth_success", agent_id, f"Token issued, scope={token.scope}")
        return token

    # --- 3. AUTHORIZATION ---
    def check_permission(self, token: AuthToken, required_permission: str) -> bool:
        """Check if agent's token grants the required permission."""
        if token.is_expired:
            self._log("authz_denied", token.agent_id, "Token expired")
            return False

        # Check if required permission is in token's scope
        allowed = required_permission in token.scope
        status = "allowed" if allowed else "denied"
        self._log(
            f"authz_{status}",
            token.agent_id,
            f"Permission '{required_permission}' {status}. Token scope: {token.scope}",
        )
        return allowed

    # --- 4. ROTATION ---
    def rotate_certificate(self, agent_id: str, new_valid_days: int = 90) -> Optional[Certificate]:
        """Rotate agent's certificate."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        old_thumbprint = agent.certificate.thumbprint
        agent.certificate.revoked = True  # Revoke old cert

        new_cert = Certificate(
            thumbprint=hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16],
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=new_valid_days),
        )
        agent.certificate = new_cert

        self._log(
            "cert_rotation",
            agent_id,
            f"Old cert {old_thumbprint} revoked, new cert {new_cert.thumbprint} issued",
        )
        return new_cert

    # --- 5. REVOCATION ---
    def revoke_agent(self, agent_id: str, reason: str, revoked_by: str):
        """Immediately revoke an agent's identity."""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        agent.status = AgentStatus.REVOKED
        agent.certificate.revoked = True

        self._log(
            "revocation",
            agent_id,
            f"REVOKED by {revoked_by}. Reason: {reason}",
        )


def main():
    print("=" * 70)
    print("AGENT IDENTITY MANAGER - Full Lifecycle Demo")
    print("=" * 70)

    registry = AgentRegistry()

    # --- Step 1: Registration ---
    print("\n" + "─" * 50)
    print("STEP 1: REGISTRATION")
    print("─" * 50)

    agent = registry.register_agent(
        agent_type="coordinator",
        max_permissions=["read:documents", "read:databases", "call:tools"],
        owner="platform-team@company.com",
        registered_by="admin:alice",
        cert_valid_days=90,
    )
    print(f"\n  Agent ID: {agent.agent_id}")
    print(f"  Client ID: {agent.client_id}")
    print(f"  Certificate: {agent.certificate.thumbprint}")
    print(f"  Max Permissions: {agent.max_permissions}")
    print(f"  Expires: {agent.certificate.expires_at.date()}")

    # --- Step 2: Authentication ---
    print("\n" + "─" * 50)
    print("STEP 2: AUTHENTICATION")
    print("─" * 50)

    print("\n  Attempt 1: Valid certificate")
    token = registry.authenticate(agent.agent_id, agent.certificate.thumbprint)
    if token:
        print(f"  ✓ Token issued: {token.token_id[:8]}...")
        print(f"    Scope: {token.scope}")
        print(f"    Expires: {token.expires_at.isoformat()}")

    print("\n  Attempt 2: Wrong certificate")
    bad_token = registry.authenticate(agent.agent_id, "wrong-thumbprint")
    if not bad_token:
        print("  ✗ Authentication failed (expected)")

    # --- Step 3: Authorization ---
    print("\n" + "─" * 50)
    print("STEP 3: AUTHORIZATION (Scope Checking)")
    print("─" * 50)

    print("\n  Check 1: read:documents (should ALLOW)")
    registry.check_permission(token, "read:documents")

    print("\n  Check 2: write:documents (should DENY - not in scope)")
    registry.check_permission(token, "write:documents")

    print("\n  Check 3: admin:delete (should DENY - not in scope)")
    registry.check_permission(token, "admin:delete")

    # --- Step 4: Rotation ---
    print("\n" + "─" * 50)
    print("STEP 4: CREDENTIAL ROTATION")
    print("─" * 50)

    old_thumbprint = agent.certificate.thumbprint
    new_cert = registry.rotate_certificate(agent.agent_id)
    print(f"\n  Old certificate: {old_thumbprint} (now revoked)")
    print(f"  New certificate: {new_cert.thumbprint}")

    print("\n  Attempt auth with OLD certificate:")
    old_token = registry.authenticate(agent.agent_id, old_thumbprint)
    if not old_token:
        print("  ✗ Old cert rejected (expected)")

    print("\n  Attempt auth with NEW certificate:")
    new_token = registry.authenticate(agent.agent_id, new_cert.thumbprint)
    if new_token:
        print(f"  ✓ New cert accepted, token: {new_token.token_id[:8]}...")

    # --- Step 5: Revocation ---
    print("\n" + "─" * 50)
    print("STEP 5: REVOCATION (Emergency)")
    print("─" * 50)

    registry.revoke_agent(
        agent.agent_id,
        reason="Suspicious behavior detected - accessing unauthorized resources",
        revoked_by="security-team",
    )

    print(f"\n  Agent status: {agent.status.value}")
    print(f"  Certificate valid: {agent.certificate.is_valid}")

    print("\n  Attempt auth after revocation:")
    revoked_token = registry.authenticate(agent.agent_id, new_cert.thumbprint)
    if not revoked_token:
        print("  ✗ Revoked agent cannot authenticate (expected)")

    # --- Audit Summary ---
    print("\n" + "─" * 50)
    print("FULL AUDIT LOG")
    print("─" * 50)
    for entry in registry.audit_log:
        print(f"  [{entry['timestamp'][:19]}] {entry['event_type']}: {entry['details'][:80]}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
